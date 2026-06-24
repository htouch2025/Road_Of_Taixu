#!/usr/bin/env python3
"""
關鍵詞提取 — Phase A 程序化粗篩 + 候選集輸出。

用法:
  python scripts/extract_keywords.py --article MD_PATH
  python scripts/extract_keywords.py --catalog CATALOG_JSON [--start N --end M]
  python scripts/extract_keywords.py --apply MD_PATH --keywords '["KW1","KW2"]'
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
)

DEFAULT_VOCAB = SKILL_DIR / "vocabulary" / "keyword_vocabulary_v4.json"
DEFAULT_GAP_LOG = SKILL_DIR / "logs" / "_keyword_gap_log.jsonl"
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

def apply_annotations(md_path, keywords=None, knowledge_domains=None,
                       functional_purposes=None, spiritual_directions=None):
    """将多维标注写入 YAML frontmatter。
    每个维度独立写入，已存在的同名块会被替换。
    写入顺序：keywords → knowledge_domains → functional_purposes → spiritual_directions
    """
    all_fields = [
        ("keywords", keywords),
        ("knowledge_domains", knowledge_domains),
        ("functional_purposes", functional_purposes),
        ("spiritual_directions", spiritual_directions),
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
    parser.add_argument("--keywords", help="關鍵詞 JSON 列表字串")
    parser.add_argument("--knowledge-domains", help="知识域 JSON 列表字串")
    parser.add_argument("--functional-purposes", help="功能取向 JSON 列表字串")
    parser.add_argument("--spiritual-directions", help="精神指向 JSON 列表字串")
    parser.add_argument("--vocab", default=str(DEFAULT_VOCAB), help="術語表路徑")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTDIR), help="候選輸出目錄")
    parser.add_argument("--build-prompt", help="構建完整 Phase B prompt 並輸出到 stdout")
    args = parser.parse_args()

    # --apply mode
    if args.apply:
        kw_list = json.loads(args.keywords) if args.keywords else None
        kd_list = json.loads(args.knowledge_domains) if args.knowledge_domains else None
        fp_list = json.loads(args.functional_purposes) if args.functional_purposes else None
        sd_list = json.loads(args.spiritual_directions) if args.spiritual_directions else None
        
        if kw_list is None and kd_list is None and fp_list is None and sd_list is None:
            print("⚠ 未提供任何标注字段 (--keywords / --knowledge-domains / --functional-purposes / --spiritual-directions)", file=sys.stderr)
            return
        
        apply_annotations(args.apply,
                          keywords=kw_list,
                          knowledge_domains=kd_list,
                          functional_purposes=fp_list,
                          spiritual_directions=sd_list)
        
        # Log gaps for all four dimensions
        # Each dimension checked against its own standard value set
        try:
            # Load standard sets
            with open(str(DEFAULT_VOCAB), encoding="utf-8") as f:
                vdata = json.load(f)
            vocab_stds = {t["standard"] for t in vdata.get("terms", [])}
            domain_stds = {t["domain"] for t in vdata.get("terms", [])}
            # -- functional_purposes and spiritual_directions from labels.json
            func_stds, spirit_stds = load_standard_labels()

            dims = [
                ("keywords", kw_list, vocab_stds),
                ("knowledge_domains", kd_list, domain_stds),
                ("functional_purposes", fp_list, func_stds),
                ("spiritual_directions", sd_list, spirit_stds),
            ]
            from datetime import datetime
            all_gaps = {}
            for dim_name, vals, std_set in dims:
                if not vals:
                    continue
                g = [v for v in vals if v not in std_set]
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
        
        written = []
        if kw_list: written.append(f"{len(kw_list)} 個內容概念")
        if kd_list: written.append(f"{len(kd_list)} 個知識域")
        if fp_list: written.append(f"{len(fp_list)} 個功能取向")
        if sd_list: written.append(f"{len(sd_list)} 個精神指向")
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
