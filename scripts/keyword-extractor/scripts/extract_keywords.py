#!/usr/bin/env python3
"""
關鍵詞提取 — Phase A 程序化粗篩 + 候選集輸出。

用法:
  python scripts/extract_keywords.py --article MD_PATH
  python scripts/extract_keywords.py --catalog CATALOG_JSON [--start N --end M]
  python scripts/extract_keywords.py --apply MD_PATH --concepts '["KW1","KW2"]'
  python scripts/extract_keywords.py --build-prompt MD_PATH

選項:
  --vocab PATH    術語表 JSON (預設 _research/keyword_vocabulary_v4.json)
  --output-dir DIR 候選輸出目錄 (預設 _research/_keyword_candidates/)
"""
import argparse
import re
import json
import os
import sys
from pathlib import Path

# Allow import of sibling _kw_utils
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kw_utils import (
    SKILL_DIR,
    REPO, RESEARCH, is_cjk, cjk_len,
    strip_yaml_and_toc, parse_frontmatter, extract_context,
    recommended_count, load_vocab, find_headings, heading_hit_count,
    score_candidate,
    load_standard_labels, format_label_list,
    normalize_label,
    extract_standard_term,
)

DEFAULT_VOCAB = SKILL_DIR / "vocabulary" / "keyword_vocabulary_v4.json"
DEFAULT_GAP_LOG = SKILL_DIR / "logs" / "_keyword_gap_log.jsonl"
DEFAULT_COUNTER = SKILL_DIR / "logs" / "_kw_counter.json"
DEFAULT_OUTDIR = SKILL_DIR / "candidates"


# ── 匹配引擎 ──────────────────────────────────────────────

def match_article(text, match_table, length_index):
    """n-gram 滑動窗口最長匹配。
    Returns {matched_str: {occurrences, positions[], in_heading}}"""
    hits = {}
    heading_ranges = find_headings(text)
    i, n = 0, len(text)
    max_len = max(length_index.keys()) if length_index else 7
    while i < n:
        matched = False
        for L in range(max_len, 1, -1):
            if i + L > n:
                continue
            window = text[i:i + L]
            if cjk_len(window) != L:
                continue
            if window in length_index.get(L, set()):
                in_h = any(s <= i < e for s, e in heading_ranges)
                rec = hits.setdefault(window, {
                    "occurrences": 0, "positions": [], "in_heading": False})
                rec["occurrences"] += 1
                rec["positions"].append(i)
                rec["in_heading"] = rec["in_heading"] or in_h
                i += L
                matched = True
                break
        if not matched:
            i += 1
    return hits


# ── 候選集構建 ────────────────────────────────────────────

def build_candidates(hits, match_table, text):
    """去重（按 standard 聚合），排序，附加上下文。
    Returns (candidates_list, dim_candidates_list)
    dim_match unused now; reserved for backward compat."""
    by_std = {}
    for mstr, info in hits.items():
        entry = match_table.get(mstr)
        if entry is None:
            continue
        std = entry.get("standard", mstr)
        rec = by_std.setdefault(std, {
            "matched": mstr,
            "standard": std,
            "occurrences": 0,
            "positions": [],
            "in_heading": False,
            "domain": entry.get("domain", ""),
            "subdomain": entry.get("subdomain", ""),
            "is_standard": (mstr == std),
            "variants_of_standard": entry.get("variants", []),
            "vocab_note": entry.get("note", ""),
            "source": entry.get("source", ""),
            "_positions": [],
            "matched_via": [],
        })
        rec["occurrences"] += info["occurrences"]
        rec["positions"].extend(info["positions"])
        rec["in_heading"] = rec["in_heading"] or info["in_heading"]
        rec["matched_via"].append(mstr)
        if mstr == std:
            rec["is_standard"] = True
            rec["matched"] = mstr

    heading_ranges = find_headings(text)
    candidates = []
    for std, info in by_std.items():
        positions = sorted(info["positions"])
        heading_hits = heading_hit_count(positions, heading_ranges)
        ctx = ""
        for pos in positions:
            in_h = any(s <= pos < e for s, e in heading_ranges)
            if not in_h or len(positions) == 1:
                ctx = extract_context(text, pos)
                break
        candidates.append({
            "matched": info["matched"],
            "standard": info["standard"],
            "occurrences": info["occurrences"],
            "domain": info["domain"],
            "subdomain": info["subdomain"],
            "is_standard": info["is_standard"],
            "variants_of_standard": info["variants_of_standard"],
            "vocab_note": info["vocab_note"],
            "source": info["source"],
            "in_heading": info["in_heading"],
            "_heading_hits": heading_hits,
            "matched_via": sorted(set(info["matched_via"])),
            "sample_context": ctx,
        })
    candidates.sort(key=lambda c: -score_candidate(c, None))
    # Build summary
    single_hit = sum(1 for c in candidates if c["occurrences"] == 1)
    high_freq = [c["standard"] for c in candidates if c["occurrences"] >= 10]
    summary = {
        "total_candidates": len(candidates),
        "unique_standards": len(set(c["standard"] for c in candidates)),
        "single_occurrence_ratio": f"{single_hit}/{len(candidates)}",
        "high_frequency_terms": high_freq,
        "heading_weighted": True,
        "heading_weight": 3,
    }
    return candidates, summary


# ── 文章讀取 ──────────────────────────────────────────────

def read_article(md_path):
    """讀取 MD 返回 {path, title, cjk_chars, body, ...}。"""
    with open(md_path, encoding="utf-8") as f:
        raw = f.read()
    fm = parse_frontmatter(raw)
    body = strip_yaml_and_toc(raw)
    title = fm.get("book", "")  # fallback
    h1 = None
    for line in body.split("\n"):
        if line.startswith("# ") and not line.startswith("## "):
            h1 = line.lstrip("# ").strip()
            # strip trailing [1] etc
            h1 = re.sub(r'\s*\[\d+\]$', '', h1)
            break
    if h1:
        title = h1
    cjk_chars = cjk_len(body)
    return {
        "path": str(md_path),
        "title": title,
        "cjk_chars": cjk_chars,
        "recommended_count": recommended_count(cjk_chars),
        "编": fm.get("book", ""),
        "编_number": fm.get("book_number", ""),
        "category": fm.get("category", ""),
        "body": body,
    }


# ── 寫入 keywords ─────────────────────────────────────────

def apply_annotations(md_path, concepts=None, domains=None,
                       functions=None, bearings=None):
    """将多维标注写入 YAML frontmatter。
    每个维度独立写入，已存在的同名块会被替换。
    写入顺序：concepts → domains → functions → bearings
    """
    all_fields = [
        ("concepts", concepts),
        ("domains", domains),
        ("functions", functions),
        ("bearings", bearings),
    ]
    for field_name, values in all_fields:
        if values is None:
            continue
        _write_yaml_list_field(md_path, field_name, values)


def _write_yaml_list_field(md_path, field_name, values):
    """将单个 YAML list 字段写入 frontmatter。"""
    with open(md_path, encoding="utf-8") as f:
        raw = f.read()
    lines = raw.split("\n")
    block = [f"{field_name}:"]
    for v in values:
        block.append(f"  - {v}")
    # Find existing block for this field
    in_yaml = False
    field_start = field_end = None
    for i, line in enumerate(lines):
        if line.strip() == "---":
            if not in_yaml:
                in_yaml = True
                continue
            else:
                break
        if in_yaml and line.strip().startswith(f"{field_name}:"):
            field_start = i
            for j in range(i + 1, len(lines)):
                stripped = lines[j].strip()
                if stripped == "" or (stripped and not lines[j].startswith("  - ")):
                    field_end = j
                    break
            if field_end is None:
                field_end = i + 1
            break
    if field_start is not None:
        lines = lines[:field_start] + block + lines[field_end:]
    else:
        # Insert before themes or closing ---
        insert_at = None
        in_yaml = False
        for i, line in enumerate(lines):
            if line.strip() == "---":
                if not in_yaml:
                    in_yaml = True
                    continue
                else:
                    insert_at = i
                    break
            if in_yaml and line.strip().startswith("themes:"):
                insert_at = i
                break
        if insert_at is not None:
            lines = lines[:insert_at] + block + lines[insert_at:]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ── 找 MD 路徑（從 catalog 條目） ──────────────────────────

def find_md_from_catalog_entry(entry, catalog):
    """從編目錄條目推算文章 MD 路徑。"""
    bian_name = catalog.get("编", "")
    zimu_list = catalog.get("子目", [])
    zimu_name = entry.get("子目", "")
    bian_seq = entry.get("編號", 0)  # global seq 1-based
    title = entry.get("篇名", "")

    # Find subdir index
    subdir_idx = None
    for idx, z in enumerate(zimu_list):
        if z == zimu_name:
            subdir_idx = idx + 1  # 1-based
            break
    if subdir_idx is None:
        return None

    # Build path components
    bian_prefix = bian_name.replace(" ", "")
    bian_dir = f"{catalog.get('编序号',0):02d}_{bian_prefix}"
    subdir = f"{subdir_idx:02d}_{zimu_name}"
    fname = f"{bian_seq:02d}_{title}.md"

    md_path = RESEARCH / bian_dir / subdir / fname

    # Try alternate structure (no subdirectory)
    if not md_path.exists():
        alt_path = RESEARCH / bian_dir / fname
        if alt_path.exists():
            return str(alt_path)
    if md_path.exists():
        return str(md_path)
    return None



def _build_domain_summary(candidates):
    """Build domain/subdomain distribution summary from candidates."""
    from collections import Counter
    domains = Counter(c["domain"] for c in candidates if c.get("domain"))
    subdomains = Counter(c["subdomain"] for c in candidates if c.get("subdomain"))
    return {
        "domains": dict(domains.most_common()),
        "subdomains": dict(subdomains.most_common()),
    }


# ── Prompt 構建輔助函數 ────────────────────────────────

def build_domain_taxonomy(match_table):
    """從詞彙表構建 domain/subdomain 分類樹，供 prompt 使用。"""
    from collections import defaultdict
    domains = defaultdict(set)
    seen = set()
    for entry in match_table.values():
        domain = entry.get("domain", "")
        subdomain = entry.get("subdomain", "")
        key = (domain, subdomain)
        if domain and subdomain and key not in seen:
            seen.add(key)
            domains[domain].add(subdomain)
    lines = []
    for domain in sorted(domains.keys()):
        lines.append(f"- **{domain}**")
        for sub in sorted(domains[domain]):
            lines.append(f"  - {sub}")
    return "\n".join(lines)


def build_candidate_context(candidates, summary, top_n=30):
    """格式化候選術語上下文，供 prompt 使用。"""
    lines = []
    lines.append(f"候選術語總數：{summary['total_candidates']}（去重後 {summary['unique_standards']}）")
    hf = summary.get('high_frequency_terms', [])
    if hf:
        lines.append(f"高頻術語（≥10次）：{', '.join(hf[:15])}")
    lines.append(f"推薦關鍵詞數量：{summary.get('recommended_count', '5-10')}")
    lines.append("")
    lines.append("排序靠前的候選術語（標題命中已加權，✓ 表示出現在章節標題中）：")
    lines.append("")
    lines.append("| 術語 | 頻次 | 知識域/子域 | 標題命中 |")
    lines.append("|------|:--:|------|:--:|")
    for c in candidates[:top_n]:
        domain = c.get('domain', '')
        subdomain = c.get('subdomain', '')
        domain_str = f"{domain}/{subdomain}" if domain else "—"
        hh = c.get('_heading_hits', 0)
        hh_str = "✓" if hh > 0 else ""
        lines.append(f"| {c['standard']} | {c['occurrences']} | {domain_str} | {hh_str} |")
    return "\n".join(lines)


def build_prompt(md_path, match_table, length_index):
    """構建完整的 Phase B prompt，填入所有佔位符並輸出到 stdout。"""
    md_path = str(Path(md_path).resolve())
    art = read_article(md_path)
    if not art["title"]:
        print(f"⚠ 無法解析標題 → {md_path}", file=sys.stderr)
        return None
    body = art["body"]
    hits = match_article(body, match_table, length_index)
    candidates, summary = build_candidates(hits, match_table, body)
    # Inject recommended_count into summary for context builder
    summary["recommended_count"] = art["recommended_count"]
    taxonomy = build_domain_taxonomy(match_table)
    context = build_candidate_context(candidates, summary)
    prompt_template_path = SKILL_DIR / "prompts" / "_keyword_prompt_v2.md"
    with open(prompt_template_path, encoding="utf-8") as f:
        template = f.read()
    prompt = template.replace("<!-- {article_body} -->", body)
    prompt = prompt.replace("<!-- {candidate_context} -->", context)
    prompt = prompt.replace("<!-- {domain_taxonomy} -->", taxonomy)
    prompt = prompt.replace("{recommended_count}", art["recommended_count"])
    # Fill standard label lists from labels.json
    func_stds, spirit_stds = load_standard_labels()
    prompt = prompt.replace("{func_labels}", format_label_list(sorted(func_stds)))
    prompt = prompt.replace("{spirit_labels}", format_label_list(sorted(spirit_stds)))
    return prompt

# ── 主流程 ────────────────────────────────────────────────

def process_article(md_path, match_table, length_index, output_dir):
    """處理單篇文章，輸出候選 JSON。"""
    md_path = str(Path(md_path).resolve())
    art = read_article(md_path)
    if not art["title"]:
        print(f"  ⚠ 跳過：無法解析標題 → {md_path}", file=sys.stderr)
        return None
    body = art["body"]
    hits = match_article(body, match_table, length_index)
    candidates, summary = build_candidates(hits, match_table, body)

    output = {
        "summary": summary,
        "article": {
            "path": art["path"],
            "title": art["title"],
            "cjk_chars": art["cjk_chars"],
            "recommended_count": art["recommended_count"],
            "编": art["编"],
            "编_number": art["编_number"],
            "category": art["category"],
        },
        "vocab_source": str(DEFAULT_VOCAB),
        "match_stats": {
            "raw_hits": len(hits),
            "after_dedup": len(candidates),
        },
        "candidates": candidates,
        "domain_summary": _build_domain_summary(candidates),
    }

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rel = Path(md_path).relative_to(REPO)
    out_name = str(rel).replace("/", "_").replace(".md", "_candidates.json")
    out_path = out_dir / out_name
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  → {out_path}")
    print(f"  原始命中 {len(hits)} → 去重後 {len(candidates)} 條候選")
    return out_path




def print_review_report():
    """Analyze gap log and print a review-frequency summary.
    Called when article counter hits a multiple of 5 (5, 10, 15, ...).
    Automatically applies changes for gaps with freq ≥ 2.
    """
    report, actions = review_gaps(apply_changes=True)
    if report.get("status") == "no_gap_log":
        print("  (尚無缺口日誌)")
        return
    print("")
    print("  ═══════════════════════════════════════")
    print(f"  📋 自動評審完成（≥2 次已自動補入）")
    print("  ═══════════════════════════════════════")

    sections = [
        ("要义 → 術語表", report.get("concepts", {})),
        ("论域 → labels.json", report.get("domains", {})),
        ("论用 → labels.json", report.get("functions", {})),
        ("旨归 → labels.json", report.get("bearings", {})),
    ]

    any_found = False
    for label, freq in sections:
        if freq:
            any_found = True
            print(f"  [{label}]")
            for term, count in sorted(freq.items(), key=lambda x: -x[1]):
                print(f"    {term} ({count}篇) → 建議補入")
        else:
            na = "暫無 ≥2 者"
            print(f"  [{label}] {na}")

    if not any_found:
        print("  ✅ 無需立即處理的缺口（或均為單次出現）")

    print("  ═══════════════════════════════════════")
    print("")

    if actions:
        print("  ⚡ 本次自動補入：")
        for a in actions:
            print(f"    {a}")
        print("")


def review_gaps(apply_changes=False):
    """自动化缺口审查：过滤假阳性、对频次≥2的真实缺口自动补入词表/labels。

    返回 (report_dict, actions_taken_list) 供调用方汇报。
    """
    if not DEFAULT_GAP_LOG.exists():
        return {"status": "no_gap_log"}, []

    # ── 1. 加载当前标准集 ──
    with open(str(DEFAULT_VOCAB), encoding="utf-8") as f:
        vdata = json.load(f)
    terms_list = vdata.get("terms", [])
    vocab_stds = {t["standard"] for t in terms_list}
    variant_stds = set()
    std_to_entry = {}
    for t in terms_list:
        std_to_entry[t["standard"]] = t
        for v in t.get("variants", []):
            variant_stds.add(v)
    concept_check = {normalize_label(s) for s in (vocab_stds | variant_stds)}

    domain_stds = ({t["domain"] for t in terms_list}
                   | {t["subdomain"] for t in terms_list if t.get("subdomain")})
    domain_check = {normalize_label(s) for s in domain_stds}

    func_stds_raw, spirit_stds_raw = load_standard_labels()
    func_check = {normalize_label(s) for s in func_stds_raw}
    spirit_check = {normalize_label(s) for s in spirit_stds_raw}

    # ── 2. 读取缺口日志 ──
    raw_entries = []
    repo_prefix = "/Users/xin/Documents/Road_Of_Taixu/"
    for line in open(str(DEFAULT_GAP_LOG), encoding="utf-8"):
        try:
            raw_entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    # ── 3. 逐条检查，分离真缺口和假阳性 ──
    from collections import Counter

    true_cn = Counter()
    true_dm = Counter()
    true_fn = Counter()
    true_br = Counter()
    false_positive_count = 0
    clean_entries = []  # 去除假阳性后的日志条目

    seen = set()
    for entry in raw_entries:
        art_path = entry.get("article_path", "")
        if "/tmp/" in art_path:
            clean_entries.append(entry)  # 保留测试条目
            continue
        if art_path.startswith(repo_prefix):
            art_path = art_path[len(repo_prefix):]
        # Normalize ../../ relative paths (from older gap log entries)
        while art_path.startswith("../"):
            art_path = art_path[3:]

        # 处理旧格式 (gap_terms / keywords)
        old_terms = entry.get("gap_terms", []) or entry.get("keywords", [])
        true_old = []
        false_old = 0
        for t in old_terms:
            check_val = normalize_label(extract_standard_term(t))
            if check_val in concept_check:
                false_old += 1
                false_positive_count += 1
            else:
                true_old.append(t)
                key = (art_path, "concepts", check_val)
                if key not in seen:
                    seen.add(key)
                    true_cn[check_val] += 1

        # 处理新格式
        dim_map = [
            ("concepts", concept_check, true_cn),
            ("domains", domain_check, true_dm),
            ("functions", func_check, true_fn),
            ("bearings", spirit_check, true_br),
        ]
        new_gaps = {}
        for field, check_set, freq_map in dim_map:
            vals = entry.get(field, [])
            true_vals = []
            for v in vals:
                check_val = normalize_label(v)
                if check_val in check_set:
                    false_positive_count += 1
                else:
                    true_vals.append(v)
                    key = (art_path, field, check_val)
                    if key not in seen:
                        seen.add(key)
                        freq_map[check_val] += 1
            if true_vals:
                new_gaps[field] = true_vals

        # 重建干净的条目
        cleaned = {}
        if true_old:
            cleaned["gap_terms"] = true_old
        else:
            # 旧格式 keywords 全部是假阳性时，过滤后只保留真正的缺口
            clean_kw = [t for t in entry.get("keywords", [])
                       if normalize_label(extract_standard_term(t)) not in concept_check]
            if clean_kw:
                cleaned["keywords"] = clean_kw
        # 只有在至少有一个维度真正存在缺口时，才保留其他维度信息
        if cleaned or new_gaps:
            cleaned.update(new_gaps)
            # 保留旧条目中与缺口共存的其他元信息（如 knowledge_domains）
            for legacy_key in ["knowledge_domains", "functional_purposes",
                               "spiritual_directions"]:
                if legacy_key in entry:
                    cleaned[legacy_key] = entry[legacy_key]
        if cleaned:
            cleaned["article_path"] = art_path
            cleaned["timestamp"] = entry.get("timestamp", "")
            clean_entries.append(cleaned)
        # 如果整条都是假阳性（无 cleaned 内容），直接丢弃

    # ── 4. 统计 ──
    report = {
        "status": "ok",
        "total_entries": len(raw_entries),
        "false_positives_removed": false_positive_count,
        "concepts": {k: v for k, v in true_cn.items() if v >= 2},
        "concepts_all": dict(true_cn),
        "domains": {k: v for k, v in true_dm.items() if v >= 2},
        "domains_all": dict(true_dm),
        "functions": {k: v for k, v in true_fn.items() if v >= 2},
        "functions_all": dict(true_fn),
        "bearings": {k: v for k, v in true_br.items() if v >= 2},
        "bearings_all": dict(true_br),
    }

    actions = []
    if not apply_changes:
        # 只报告不修改
        return report, actions

    # ── 5. 自动补入 ──
    vocab_changed = False

    # 5a. concepts → 词表
    for term_val, freq in true_cn.items():
        if freq < 2:
            continue
        # 推断 domain/subdomain：从词条的 domain 分布中推断
        # 先尝试从原始缺口日志中找上下文
        context_domain = _infer_domain(term_val, raw_entries, concept_check, terms_list)
        new_entry = {
            "standard": term_val,
            "variants": [],
            "domain": context_domain.get("domain", "教理"),
            "subdomain": context_domain.get("subdomain", ""),
            "source": "gap_review_auto",
            "note": f"自動補入：{freq}篇缺口"
        }
        terms_list.append(new_entry)
        std_to_entry[term_val] = new_entry
        vocab_changed = True
        actions.append(f"➕ 術語表: {term_val}（{context_domain.get('domain','教理')}/{context_domain.get('subdomain','')}，{freq}篇）")

    # 5b. domains → labels.json
    labels_changed = False
    labels_path = SKILL_DIR / "vocabulary" / "labels.json"
    with open(str(labels_path), encoding="utf-8") as f:
        labels = json.load(f)

    domains_list = labels.get("domains", [])
    for d, freq in true_dm.items():
        if freq < 2:
            continue
        nd = normalize_label(d)
        if nd not in {normalize_label(x) for x in domains_list}:
            domains_list.append(d)
            labels_changed = True
            actions.append(f"➕ labels.domains: {d}（{freq}篇）")

    # 5c. functions → labels.json
    funcs_list = labels.get("functions", [])
    for fv, freq in true_fn.items():
        if freq < 2:
            continue
        nf = normalize_label(fv)
        if nf not in {normalize_label(x) for x in funcs_list}:
            funcs_list.append(fv)
            labels_changed = True
            actions.append(f"➕ labels.functions: {fv}（{freq}篇）")

    # 5d. bearings → labels.json
    bearings_list = labels.get("bearings", [])
    for b, freq in true_br.items():
        if freq < 2:
            continue
        nb = normalize_label(b)
        if nb not in {normalize_label(x) for x in bearings_list}:
            bearings_list.append(b)
            labels_changed = True
            actions.append(f"➕ labels.bearings: {b}（{freq}篇）")

    if labels_changed:
        with open(str(labels_path), "w", encoding="utf-8") as f:
            json.dump(labels, f, ensure_ascii=False, indent=2)

    if vocab_changed:
        vdata["terms"] = terms_list
        with open(str(DEFAULT_VOCAB), "w", encoding="utf-8") as f:
            json.dump(vdata, f, ensure_ascii=False, indent=2)

    # ── 6. 回写清洁后的缺口日志 ──
    with open(str(DEFAULT_GAP_LOG), "w", encoding="utf-8") as f:
        for e in clean_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    return report, actions


def _print_review_gaps_report(report, actions, apply_flag):
    """格式化输出 review_gaps 报告。"""
    if report.get("status") == "no_gap_log":
        print("✅ 尚無缺口日誌，無需審閱")
        return

    fp = report.get("false_positives_removed", 0)
    total = report.get("total_entries", 0)
    print(f"\n{'='*50}")
    print(f"📋 缺口日志審閱完成（{total} 條記錄，{fp} 條假陽性已過濾）")
    print(f"{'='*50}")

    sections = [
        ("要义 (concepts)", report.get("concepts", {}), report.get("concepts_all", {}), "詞表"),
        ("论域 (domains)", report.get("domains", {}), report.get("domains_all", {}), "labels.json"),
        ("论用 (functions)", report.get("functions", {}), report.get("functions_all", {}), "labels.json"),
        ("旨归 (bearings)", report.get("bearings", {}), report.get("bearings_all", {}), "labels.json"),
    ]

    any_gap = False
    for label, qualified, all_items, target in sections:
        print(f"\n  [{label}]")
        if qualified:
            any_gap = True
            for term, count in sorted(qualified.items(), key=lambda x: -x[1]):
                action_mark = "✓ 已補入" if apply_flag else "→ 建議補入"
                print(f"    {term} ({count}篇) {action_mark} {target}")
        else:
            if all_items:
                low_freq = [f"{t}({c})" for t, c in sorted(all_items.items(), key=lambda x: -x[1])]
                print(f"    暫無 ≥2 者（單次出現：{', '.join(low_freq)}）")
            else:
                print(f"    無缺口")

    if not any_gap:
        print(f"\n  ✅ 無需立即處理的頻次≥2缺口")
    else:
        print(f"\n  📝 共 {sum(len(v) for v in [report['concepts'], report['domains'], report['functions'], report['bearings']])} 類缺口達 ≥2 閾值")
    print(f"{'='*50}\n")


def _infer_domain(term_name, raw_entries, concept_check, terms_list):
    """为缺口术语推断 domain/subdomain 分类。

    策略：从同一文章的其他概念（已在词表中的）的 domain 分布推断。
    """
    from collections import Counter
    domain_votes = Counter()
    subdomain_votes = Counter()

    for entry in raw_entries:
        concepts = entry.get("concepts", entry.get("keywords", entry.get("gap_terms", [])))
        has_this_term = any(
            normalize_label(extract_standard_term(c)) == normalize_label(term_name)
            for c in concepts
        )
        if not has_this_term:
            continue
        # 同一篇文章中的其他概念，看它们所属的 domain
        for c in concepts:
            check_val = normalize_label(extract_standard_term(c))
            if check_val == normalize_label(term_name):
                continue
            if check_val in concept_check:
                # 在词表中，查找其 domain
                for t in terms_list:
                    s = t.get("standard", "")
                    if normalize_label(s) == check_val:
                        if t.get("domain"):
                            domain_votes[t["domain"]] += 1
                        if t.get("subdomain"):
                            subdomain_votes[t["subdomain"]] += 1
                        break

    domain = domain_votes.most_common(1)[0][0] if domain_votes else "教理"
    subdomain = subdomain_votes.most_common(1)[0][0] if subdomain_votes else ""
    return {"domain": domain, "subdomain": subdomain}


def process_catalog(catalog_path, match_table, length_index, output_dir,
                    start=None, end=None):
    """批次處理編目錄中的文章。"""
    with open(catalog_path, encoding="utf-8") as f:
        catalog = json.load(f)
    articles = catalog.get("篇目鏈表", [])
    bian_name = catalog.get("编", "未知")
    total = len(articles)
    print(f"\n{bian_name} — {total} 篇文章")

    processed = 0
    for art in articles:
        seq = art.get("編號", 0)
        if start is not None and seq < start:
            continue
        if end is not None and seq > end:
            continue
        md_path = find_md_from_catalog_entry(art, catalog)
        if md_path is None:
            print(f"  ⚠ 找不到 MD：#{seq} {art.get('篇名','?')}", file=sys.stderr)
            continue
        print(f"\n#{seq} {art.get('篇名','?')}")
        process_article(md_path, match_table, length_index, output_dir)
        processed += 1
    print(f"\n處理完成：{processed} 篇")


# ── CLI ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="太虚文章關鍵詞提取 — Phase A 粗篩")
    parser.add_argument("--article", help="單篇文章 MD 路徑")
    parser.add_argument("--catalog", help="編目錄 JSON 路徑 (批次模式)")
    parser.add_argument("--start", type=int, help="起始編號")
    parser.add_argument("--end", type=int, help="結束編號")
    parser.add_argument("--apply", help="寫入關鍵詞的目標 MD 路徑")
    parser.add_argument("--concepts", "--keywords", help="要义 JSON 列表字串")
    parser.add_argument("--domains", "--knowledge-domains", help="论域 JSON 列表字串")
    parser.add_argument("--functions", "--functional-purposes", help="论用 JSON 列表字串")
    parser.add_argument("--bearings", "--spiritual-directions", help="旨归 JSON 列表字串")
    parser.add_argument("--vocab", default=str(DEFAULT_VOCAB), help="術語表路徑")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTDIR), help="候選輸出目錄")
    parser.add_argument("--build-prompt", help="構建完整 Phase B prompt 並輸出到 stdout")
    parser.add_argument("--review-gaps", action="store_true",
                        help="自動審閱缺口日誌：過濾假陽性、報告頻次統計")
    parser.add_argument("--review-gaps-apply", action="store_true",
                        help="審閱後自動補入頻次≥2的缺口詞到詞表和 labels")
    args = parser.parse_args()

    # --review-gaps mode
    if args.review_gaps or args.review_gaps_apply:
        apply_flag = args.review_gaps_apply
        report, actions = review_gaps(apply_changes=apply_flag)
        _print_review_gaps_report(report, actions, apply_flag)
        return

    # --apply mode
    if args.apply:
        cn_list = json.loads(args.concepts) if args.concepts else None
        dm_list = json.loads(args.domains) if args.domains else None
        fn_list = json.loads(args.functions) if args.functions else None
        br_list = json.loads(args.bearings) if args.bearings else None

        if cn_list is None and dm_list is None and fn_list is None and br_list is None:
            print("⚠ 未提供任何标注字段 (--concepts / --domains / --functions / --bearings)", file=sys.stderr)
            return

        apply_annotations(args.apply,
                          concepts=cn_list,
                          domains=dm_list,
                          functions=fn_list,
                          bearings=br_list)
        
        # Log gaps for all four dimensions
        # Each dimension checked against its own standard value set
        try:
            # Load standard sets
            with open(str(DEFAULT_VOCAB), encoding="utf-8") as f:
                vdata = json.load(f)
            vocab_stds = {t["standard"] for t in vdata.get("terms", [])}
            # domains: validate against both parent domains and subdomains
            domain_stds = ({t["domain"] for t in vdata.get("terms", [])}
                           | {t["subdomain"] for t in vdata.get("terms", []) if t.get("subdomain")})
            # -- functions and bearings from labels.json
            # Build variant→standard mapping for concept gap detection
            variant_stds = set()
            for t in vdata.get("terms", []):
                for v in t.get("variants", []):
                    variant_stds.add(v)
            func_stds, spirit_stds = load_standard_labels()

            dims = [
                ("concepts", cn_list, vocab_stds),
                ("domains", dm_list, domain_stds),
                ("functions", fn_list, func_stds),
                ("bearings", br_list, spirit_stds),
            ]
            from datetime import datetime
            all_gaps = {}
            for dim_name, vals, std_set in dims:
                if not vals:
                    continue
                check_set = {normalize_label(s) for s in (std_set | variant_stds)} if dim_name == "concepts" else {normalize_label(s) for s in std_set}
                g = [v for v in vals if normalize_label(extract_standard_term(v)) not in check_set]
                if g:
                    all_gaps[dim_name] = g

            if all_gaps:
                gap_entry = {
                    "article_path": args.apply,
                    "timestamp": datetime.now().isoformat(),
                    **all_gaps,
                }
                with open(str(DEFAULT_GAP_LOG), "a", encoding="utf-8") as gf:
                    gf.write(json.dumps(gap_entry, ensure_ascii=False) + "\n")
                total = sum(len(v) for v in all_gaps.values())
                dim_names = " / ".join(all_gaps.keys())
                print(f"📝 記錄 {total} 個缺口 ({dim_names}) → {str(DEFAULT_GAP_LOG)}")
        except Exception as e:
            print(f"  ⚠ gap log 失敗：{e}", file=sys.stderr)

        # Update article counter (dedup by article path)
        try:
            counter = {}
            if DEFAULT_COUNTER.exists():
                raw = json.loads(open(str(DEFAULT_COUNTER), encoding="utf-8").read())
                # Unwrap nested structure if present (legacy bug: repeated wrapping)
                counter = raw.get("articles", raw)
            # Normalize to relative path from project root
            rel = str(Path(args.apply).resolve().relative_to(Path(SKILL_DIR).resolve().parent.parent))
            counter[rel] = datetime.now().isoformat()
            counter_wrap = {
                "total_articles_processed": len(counter),
                "articles": counter,
            }
            with open(str(DEFAULT_COUNTER), "w", encoding="utf-8") as cf:
                json.dump(counter_wrap, cf, ensure_ascii=False, indent=2)
            next_review = ((len(counter) // 5) + 1) * 5 if len(counter) >= 5 else 5
            remaining = next_review - len(counter)
            if len(counter) % 5 == 0:
                print(f"📊 已處理文章數: {len(counter)}（已達評審閾值，建議立即評審！）")
                print_review_report()
            else:
                print(f"📊 已處理文章數: {len(counter)}（累計），距下次評審還差 {remaining} 篇")
        except Exception as e:
            print(f"  ⚠ counter 更新失败：{e}", file=sys.stderr)
        
        written = []
        if cn_list: written.append(f"{len(cn_list)} 個要义")
        if dm_list: written.append(f"{len(dm_list)} 個论域")
        if fn_list: written.append(f"{len(fn_list)} 個论用")
        if br_list: written.append(f"{len(br_list)} 個旨归")
        print(f"✅ 已寫入 {' / '.join(written)} → {args.apply}")
        return

    # Load vocab
    print(f"加載術語表：{args.vocab}")
    terms, match_table, length_index = load_vocab(args.vocab)
    print(f"  {len(terms)} 條術語，{len(match_table)} 個匹配鍵 (含異名)\n")

    # --build-prompt mode (outputs complete prompt to stdout)
    if args.build_prompt:
        prompt = build_prompt(args.build_prompt, match_table, length_index)
        if prompt:
            print(prompt)
        return

    # Single article
    if args.article:
        process_article(args.article, match_table, length_index, args.output_dir)

    # Batch from catalog
    elif args.catalog:
        process_catalog(args.catalog, match_table, length_index,
                        args.output_dir, args.start, args.end)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
