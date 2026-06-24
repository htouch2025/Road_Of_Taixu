#!/usr/bin/env python3
"""关键词提取共享工具函数。"""
import re
import json
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
REPO = SKILL_DIR.parent.parent
RESEARCH = REPO / "_research"


def is_cjk(c):
    cp = ord(c)
    return (0x4E00 <= cp <= 0x9FFF or
            0x3400 <= cp <= 0x4DBF or
            0x20000 <= cp <= 0x2A6DF)


def cjk_len(s):
    return sum(1 for c in s if is_cjk(c))


def strip_yaml_and_toc(text):
    """移除 YAML frontmatter 和 ## 目錄 區塊。"""
    lines = text.split("\n")
    body_lines = []
    in_yaml = False
    yaml_done = False
    for line in lines:
        if not yaml_done:
            if line.strip() == "---":
                if not in_yaml:
                    in_yaml = True
                    continue
                else:
                    in_yaml = False
                    yaml_done = True
                    continue
            if in_yaml:
                continue
        body_lines.append(line)
    # Strip ## 目錄 through to next heading or end
    toc_pat = re.compile(r'^##\s+目錄\s*$')
    heading_pat = re.compile(r'^(#|##)\s+\S')
    toc_start = None
    content_start = None
    for i, line in enumerate(body_lines):
        if toc_start is None and toc_pat.match(line):
            toc_start = i
        elif toc_start is not None and content_start is None:
            if heading_pat.match(line):
                content_start = i
                break
    if toc_start is not None:
        if content_start is not None:
            body_lines = body_lines[:toc_start] + body_lines[content_start:]
        else:
            body_lines = body_lines[:toc_start]
    return "\n".join(body_lines)


def parse_frontmatter(raw):
    """從原始 MD 文字中解析 YAML frontmatter 返回 dict。"""
    fm = {}
    in_yaml = False
    for line in raw.split("\n"):
        if line.strip() == "---":
            if not in_yaml:
                in_yaml = True
                continue
            else:
                break
        if in_yaml and ":" in line:
            key, val = line.split(":", 1)
            fm[key.strip()] = val.strip()
    return fm


def extract_context(text, pos, window=40):
    """提取匹配位置周圍的上下文片段。"""
    start = max(0, pos - window)
    end = min(len(text), pos + window + 2)
    ctx = text[start:end].replace("\n", " ")
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{ctx}{suffix}"


def recommended_count(cjk_chars):
    if cjk_chars <= 5000:
        return "5-8"
    elif cjk_chars <= 15000:
        return "8-12"
    elif cjk_chars <= 30000:
        return "10-15"
    else:
        return "12-18"


def load_vocab(vocab_path):
    """加載標準術語表，建立 variant → entry 映射。
    Returns (terms_list, match_table, length_index)"""
    with open(vocab_path, encoding="utf-8") as f:
        data = json.load(f)
    terms = data.get("terms", [])
    match_table = {}
    length_index = {}
    for entry in terms:
        std = entry.get("standard", "")
        variants = entry.get("variants", [])
        for v in [std] + variants:
            L = cjk_len(v)
            if L < 2:
                continue
            # Always map to standard entry; if conflict (variant matches another
            # entry's standard), prefer the standard-owning entry
            if v not in match_table:
                match_table[v] = entry
            length_index.setdefault(L, set()).add(v)
    return terms, match_table, length_index


def find_headings(text):
    """找出所有 #/##/### 開頭的行，返回 (start, end) 位置列表。"""
    positions = []
    for m in re.finditer(r'^#{1,3}\s+', text, re.MULTILINE):
        line_end = text.find("\n", m.start())
        if line_end == -1:
            line_end = len(text)
        positions.append((m.start(), line_end))
    return positions

def heading_hit_count(positions, heading_ranges):
    """統計 positions 中有多少落在標題範圍內。"""
    if not heading_ranges:
        return 0
    count = 0
    for pos in positions:
        if any(s <= pos < e for s, e in heading_ranges):
            count += 1
    return count


def score_candidate(candidate, heading_ranges, heading_weight=3):
    """計算候選排序分數：occurrences + heading_weight × 標題命中數。
    優先使用 candidate 中的 _heading_hits（由 build_candidates 預算），
    否則退回 position-based 計算。"""
    hh = candidate.get("_heading_hits")
    if hh is None:
        positions = candidate.get("_positions", [])
        hh = heading_hit_count(positions, heading_ranges)
    occ = candidate.get("occurrences", 0)
    return occ + heading_weight * hh


def load_standard_labels():
    """从 labels.json 读取功能取向和精神指向的标准标签集。
    返回 (func_set, spirit_set) 两个 frozenset。"""
    labels_path = SKILL_DIR / "vocabulary" / "labels.json"
    with open(labels_path, encoding="utf-8") as f:
        data = json.load(f)
    return (
        frozenset(data.get("functional_purposes", [])),
        frozenset(data.get("spiritual_directions", [])),
    )


def format_label_list(labels):
    """将标签列表格式化为 prompt 中的 、 分隔展示。"""
    return "、".join(labels)
