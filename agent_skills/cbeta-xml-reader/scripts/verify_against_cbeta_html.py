#!/usr/bin/env python3
"""
校对脚本：对比 CBETA Online 导出 HTML 与本地解析 MD。
逐篇检查结构性差异：标题层级、列表、夹注、图片、段落文本。

用法：
  # 单篇对比
  python3 verify_against_cbeta_html.py --article 佛法大系

  # 整编批量对比
  python3 verify_against_cbeta_html.py --book 1

  # 输出到文件
  python3 verify_against_cbeta_html.py --book 1 --output report.md

依赖：仅 Python 3 标准库（html.parser）。
"""

import os, sys, re, json, argparse, difflib
from pathlib import Path
from html.parser import HTMLParser
from collections import defaultdict, namedtuple
from typing import List, Optional, Dict, Tuple

# ─── 项目路径 ───────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RESEARCH_DIR = PROJECT_ROOT / "_research"
DATA_DIR = PROJECT_ROOT / "_data"

# HTML 导出目录（注意：目录名可能带尾部空格）
def find_html_dirs() -> List[Path]:
    """查找所有 TX_HTML 子目录"""
    dirs = []
    for d in DATA_DIR.iterdir():
        if d.is_dir() and d.name.strip().startswith("TX_HTML"):
            dirs.append(d)
    return dirs

# ─── 数据结构 ───────────────────────────────────────────────

Element = namedtuple("Element", ["etype", "content", "level", "meta"])
# etype: heading, paragraph, list_start, list_end, list_item,
#        note_inline, figure, pre, byline, ignore
# level: for headings (1-6), 0 otherwise
# meta: dict with extra info (e.g. {'lineref': '0334a02'})

class Article:
    """一篇文章的结构化表示"""
    def __init__(self, title: str, source: str):
        self.title = title
        self.source = source  # 'html' or 'md'
        self.elements: List[Element] = []
        self.raw_text: str = ""

# ─── HTML 解析器 ────────────────────────────────────────────

class CBETAHTMLParser(HTMLParser):
    """解析 CBETA Online 导出的 HTML，提取结构化元素"""

    def __init__(self):
        super().__init__()
        self.elements: List[Element] = []
        self._current_tag = ""
        self._current_attrs: Dict[str, str] = {}
        self._text_buf = ""
        self._in_ul = False
        self._in_li = False
        self._in_note = False
        self._in_byline = False
        self._in_pre = False
        self._pre_lines: List[str] = []
        self._in_head = False
        self._head_level = 0
        self._in_div_body = False
        self._div_depth = 0
        self._skip_copyright = False
        self._skip_note_anchor = False  # 跳过注释编号 [1] 等

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)

        if tag == "div" and attrs_d.get("id") == "body":
            self._in_div_body = True
        elif tag == "div" and attrs_d.get("id") == "cbeta-copyright":
            self._skip_copyright = True

        if self._skip_copyright:
            return

        if tag == "div" and self._in_div_body:
            self._div_depth += 1

        if tag == "p":
            cls = attrs_d.get("class", "")
            head_lv = attrs_d.get("data-head-level", "")
            if head_lv:
                self._in_head = True
                self._head_level = int(head_lv)
            elif cls == "byline":
                self._in_byline = True
            # regular paragraph
            self._current_tag = "p"
            self._current_attrs = attrs_d
            self._text_buf = ""

        elif tag == "ul":
            self._in_ul = True
            self.elements.append(Element("list_start", "", 0, {}))

        elif tag == "ol":
            self._in_ul = True  # treat same
            self.elements.append(Element("list_start", "", 0, {"ordered": True}))

        elif tag == "li":
            self._in_li = True
            self._text_buf = ""

        elif tag == "span":
            cls = attrs_d.get("class", "")
            if cls == "doube-line-note":
                self._in_note = True
                self._text_buf = ""
            elif cls == "lineInfo":
                pass  # ignore line references

        elif tag == "img":
            src = attrs_d.get("src", "")
            self.elements.append(Element("figure", src, 0, {}))

        elif tag == "pre":
            self._in_pre = True
            self._pre_lines = []

        elif tag == "a":
            if attrs_d.get("class") == "noteAnchor":
                self._skip_note_anchor = True  # skip [1] etc.

        elif tag == "table":
            # table not found in current data but handle for completeness
            self.elements.append(Element("table_start", "", 0, {}))

    def handle_endtag(self, tag):
        if self._skip_copyright:
            if tag == "div":
                self._skip_copyright = False
            return

        if tag == "div" and self._in_div_body:
            self._div_depth -= 1

        if tag == "p":
            if self._in_head:
                self.elements.append(Element(
                    "heading",
                    self._text_buf.strip(),
                    self._head_level,
                    {"lineref": self._current_attrs.get("line", "")}
                ))
                self._in_head = False
                self._head_level = 0
            elif self._in_byline:
                self.elements.append(Element("byline", self._text_buf.strip(), 0, {}))
                self._in_byline = False
            else:
                text = self._text_buf.strip()
                if text:
                    self.elements.append(Element("paragraph", text, 0, {}))
            self._text_buf = ""
            self._current_tag = ""

        elif tag == "ul" or tag == "ol":
            self._in_ul = False
            self.elements.append(Element("list_end", "", 0, {}))

        elif tag == "li":
            self._in_li = False
            text = self._text_buf.strip()
            if text:  # 跳过只有 lineInfo 的空 li
                self.elements.append(Element("list_item", text, 0, {}))
            self._text_buf = ""

        elif tag == "span":
            if self._in_note:
                self.elements.append(Element("note_inline", self._text_buf.strip(), 0, {}))
                self._in_note = False
                self._text_buf = ""

        elif tag == "pre":
            self._in_pre = False
            text = "\n".join(self._pre_lines).strip()
            if text:
                self.elements.append(Element("pre", text, 0, {}))
            self._pre_lines = []

        elif tag == "a":
            if self._skip_note_anchor:
                self._skip_note_anchor = False

        elif tag == "table":
            self.elements.append(Element("table_end", "", 0, {}))

    def handle_data(self, data):
        if self._skip_copyright or self._skip_note_anchor:
            return
        if self._in_pre:
            self._pre_lines.append(data)
        elif self._in_head or self._current_tag == "p" or self._in_li or self._in_note:
            self._text_buf += data

    def handle_entityref(self, name):
        # Map common HTML entities to characters
        entity_map = {
            "quot": '"', "amp": "&", "apos": "'", "lt": "<", "gt": ">",
            "nbsp": " ", "copy": "©",
        }
        char = entity_map.get(name, f"&{name};")
        if self._skip_copyright or self._skip_note_anchor:
            return
        if self._in_head or self._current_tag == "p" or self._in_li or self._in_note or self._in_pre:
            self._text_buf += char


def parse_html(filepath: str) -> Article:
    """解析 CBETA Online HTML 文件"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    parser = CBETAHTMLParser()
    parser.feed(content)

    # Extract title from first level-2 heading, strip footnote anchors like [1]
    title = ""
    for el in parser.elements:
        if el.etype == "heading" and el.level == 2:
            title = re.sub(r"\[\d+\]", "", el.content).strip()
            break

    article = Article(title, "html")
    article.elements = parser.elements
    article.raw_text = content
    return article


# ─── MD 解析器 ──────────────────────────────────────────────

def parse_md(filepath: str) -> Article:
    """解析本地 MD 文件为结构化元素"""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Skip YAML frontmatter
    content_start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                content_start = i + 1
                break

    elements: List[Element] = []
    in_list = False
    list_items: List[str] = []

    def flush_list():
        nonlocal in_list, list_items
        if in_list:
            elements.append(Element("list_end", "", 0, {}))
            in_list = False
            list_items = []

    i = content_start
    while i < len(lines):
        line = lines[i]

        # Skip empty lines
        if not line.strip():
            flush_list()
            i += 1
            continue

        # Heading
        heading_match = re.match(r"^(#{1,6})\s+(.+)", line)
        if heading_match:
            flush_list()
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            elements.append(Element("heading", text, level, {"line": i + 1}))
            i += 1
            continue

        # Figure
        fig_match = re.match(r"^!\[.*?\]\((.+?)\)", line)
        if fig_match:
            flush_list()
            url = fig_match.group(1)
            elements.append(Element("figure", url, 0, {}))
            i += 1
            continue

        # Unordered list item
        list_match = re.match(r"^(\s*)[-*]\s+(.+)", line)
        if list_match:
            if not in_list:
                elements.append(Element("list_start", "", 0, {}))
                in_list = True
            text = list_match.group(2).strip()
            elements.append(Element("list_item", text, 0, {"line": i + 1}))
            i += 1
            continue

        # Ordered list item
        ol_match = re.match(r"^(\s*)\d+[.)]\s+(.+)", line)
        if ol_match:
            if not in_list:
                elements.append(Element("list_start", "", 0, {"ordered": True}))
                in_list = True
            text = ol_match.group(2).strip()
            elements.append(Element("list_item", text, 0, {"line": i + 1}))
            i += 1
            continue

        # Table
        if line.strip().startswith("|"):
            flush_list()
            elements.append(Element("table_start", "", 0, {}))
            while i < len(lines) and lines[i].strip().startswith("|"):
                if "---" not in lines[i] or "|" not in lines[i].split("---")[0]:
                    elements.append(Element("paragraph", lines[i].strip(), 0, {"table_row": True}))
                i += 1
            elements.append(Element("table_end", "", 0, {}))
            continue

        # Regular paragraph
        flush_list()
        text = line.strip()
        para_line = i + 1  # 1-based line number
        # Merge continuation lines (lines starting with non-markup text)
        while i + 1 < len(lines) and lines[i + 1].strip() and \
              not re.match(r"^(#{1,6}\s|!\[|- |\* |\d+[.)] |\||---)", lines[i + 1]):
            i += 1
            text += " " + lines[i].strip()
        # Detect byline: standalone line wrapped in full-width parentheses
        if text.startswith("（") and text.endswith("）") and para_line == i + 1:
            elements.append(Element("byline", text, 0, {"line": para_line}))
        else:
            elements.append(Element("paragraph", text, 0, {"line": para_line}))
        i += 1

    flush_list()

    # Extract title
    title = ""
    for el in elements:
        if el.etype == "heading" and el.level == 1:
            title = el.content
            break

    article = Article(title, "md")
    article.elements = elements
    article.raw_text = "".join(lines)
    return article


# ─── 文本标准化 ────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """标准化文本用于比较：去空格、统一标点、统一数字"""
    text = text.replace("　", "")  # 去全角空格
    text = re.sub(r"\s+", "", text)  # 去所有空格
    # 统一括号
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("「", "'").replace("」", "'")
    text = text.replace("『", "\"").replace("』", "\"")
    # 统一标点分隔符
    text = text.replace("、", "")   # 顿号
    text = text.replace("，", "")   # 逗号
    text = text.replace("。", "")   # 句号
    # 统一中文/阿拉伯数字
    num_map = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
               '六': '6', '七': '7', '八': '8', '九': '9',
               '１': '1', '２': '2', '３': '3', '４': '4', '５': '5',
               '６': '6', '７': '7', '８': '8', '９': '9'}
    for k, v in num_map.items():
        text = text.replace(k, v)
    # Normalize dashes
    text = text.replace("——", "—").replace("——", "—")
    return text


def normalize_text_light(text: str) -> str:
    """轻量归一化：去空格、统一括号，保留标点和数字，用于段落文本相似度对比。"""
    text = text.replace("　", "")       # 去全角空格
    text = re.sub(r"\s+", "", text)         # 压缩所有空白
    text = text.replace("（", "(").replace("）", ")")  # 全角→半角括号
    # Strip markdown formatting markers not present in CBETA HTML.
    # - Blockquote (>) + bold (**) wrapper: type="orig" div → "> **text**"
    # - Standalone bold wrapping: <seg rend="bold"> → "**text**" (inline)
    # - List markers: "- ", "* ", "1. " → normalized away for cross-structure
    #   matching (CBETA <list> items become MD list items but HTML renders
    #   each as a separate <p>, so the "- " prefix must be stripped to match).
    text = re.sub(r'^>\**', '', text)   # leading ">" or ">**"
    text = re.sub(r'^[-*+]', '', text)  # leading unordered list markers
    text = re.sub(r'^\d+\.', '', text)  # leading ordered list markers
    text = re.sub(r'\**$', '', text)    # trailing "**"
    # NOTE: 保留 、，。等标点符号和中文数字，不转换
    return text


# ─── ASCII 結構性藝術檢測 ─────────────────────────────────────
# CBETA HTML 以 <img> 呈現的圖表，在 MD 中可能以 code block 保存為 ASCII art。
# 這類段落不是真正的文本差異，應列入白名單不予報告。

_BOX_DRAWING_CHARS = set(
    "┌┐└┘├┤┬┴┼│─"
    "╭╮╯╰╌╍╎╏"
    "→←↑↓↔"
)


def is_structural_art(text: str) -> bool:
    """檢測段落是否為結構性/元數據內容（圖表、代碼塊、刊載提示等），非 CBETA 自然語言文本。"""
    if not text:
        return False
    # 代碼塊包裹
    if text.startswith("```") or text.endswith("```"):
        return True
    # 提取腳本注入的刊載資訊提示（非 CBETA 原文）
    if "原文刊載資訊" in text:
        return True
    # 包含大量 box-drawing 字符
    box_count = sum(1 for c in text if c in _BOX_DRAWING_CHARS)
    if box_count >= 3:
        return True
    # CJK 字符佔比極低且含多個特殊符號
    cjk_count = sum(1 for c in text if '一' <= c <= '鿿'
                    or '㐀' <= c <= '䶿')
    total = len(text.replace(" ", "").replace("\n", ""))
    if total > 20 and cjk_count / max(total, 1) < 0.15 and box_count >= 1:
        return True
    return False


def generate_para_diff(html_text: str, md_text: str, context_len: int = 60,
                       max_snippets: int = 10) -> str:
    """生成段落差异片段，用于校对报告展示。

    对每个差异块标明操作类型（刪除/插入/替換），
    并输出 CBETA 和 MD 两侧的上下文片段。
    """
    s = difflib.SequenceMatcher(None, html_text, md_text)
    tag_names = {"delete": "CBETA有而MD無", "insert": "MD有而CBETA無",
                 "replace": "替換"}
    diffs = []
    for tag, i1, i2, j1, j2 in s.get_opcodes():
        if tag == "equal":
            continue
        ctx_start = max(0, i1 - context_len)
        ctx_end = min(len(html_text), i2 + context_len)
        html_snip = html_text[ctx_start:ctx_end]
        md_snip = md_text[max(0, j1 - context_len):min(len(md_text), j2 + context_len)]

        # 标注被刪除/插入/替換的具體內容
        del_text = html_text[i1:i2] if tag in ("delete", "replace") else ""
        ins_text = md_text[j1:j2] if tag in ("insert", "replace") else ""

        tag_label = tag_names.get(tag, tag)
        line = f"  [{tag_label}]"
        if del_text:
            line += f"\n  CBETA 刪: 「{del_text[:120]}」"
        if ins_text:
            line += f"\n  MD    增: 「{ins_text[:120]}」"
        if html_snip.strip() or md_snip.strip():
            line += f"\n  CBETA: …{html_snip}…\n  MD:    …{md_snip}…"
        diffs.append(line)
        if len(diffs) >= max_snippets:
            remaining = len(s.get_opcodes()) - len(diffs) - 1  # subtract equal blocks
            if remaining > 0:
                diffs.append(f"  …（還有 {remaining} 處差異未展示）")
            break
    return "\n".join(diffs)


# ─── 段落对齐 ──────────────────────────────────────────────

def align_paragraphs(h_paras: List[str], m_paras: List[str],
                     match_threshold: float = 0.5) -> Tuple[List[Tuple[int, int, float]],
                                                           List[int], List[int]]:
    """用内容相似度对 HTML 和 MD 段落做模糊对齐。

    不依赖位置索引——先计算全量相似度矩阵，再用贪心匹配找到
    每对最佳配对。这样即使段落数不一致、某处多一段或少一段，
    也不会导致后续所有段落全部错位。

    Args:
        h_paras: CBETA HTML 段落文本列表
        m_paras: 本地 MD 段落文本列表
        match_threshold: 最低相似度阈值（低于此值视为无匹配）

    Returns:
        (matched_pairs, unmatched_h, unmatched_m)
        matched_pairs: [(h_idx, m_idx, ratio), ...] 已配对的段落
        unmatched_h:   在 MD 中找不到匹配的 HTML 段落索引
        unmatched_m:   在 HTML 中找不到匹配的 MD 段落索引
    """
    hn = len(h_paras)
    mn = len(m_paras)
    if hn == 0 and mn == 0:
        return [], [], []
    if hn == 0:
        return [], [], list(range(mn))
    if mn == 0:
        return [], list(range(hn)), []

    # 预计算归一化文本
    h_norms = [normalize_text_light(p) for p in h_paras]
    m_norms = [normalize_text_light(p) for p in m_paras]

    # 计算全量相似度矩阵（双方段落数通常 < 100，完整 N×M 可行）
    sim = {}  # (i, j) -> ratio
    for i in range(hn):
        for j in range(mn):
            # 跳过长度差异过大的配对（>10x），节省计算
            if h_norms[i] and m_norms[j]:
                len_ratio = max(len(h_norms[i]), len(m_norms[j])) / \
                            max(1, min(len(h_norms[i]), len(m_norms[j])))
                if len_ratio > 10:
                    sim[(i, j)] = 0.0
                    continue
            sim[(i, j)] = difflib.SequenceMatcher(
                None, h_norms[i], m_norms[j]).ratio()

    # 贪心匹配：按相似度从高到低配对
    pairs = []  # (ratio, h_idx, m_idx)
    for (i, j), ratio in sim.items():
        if ratio >= match_threshold:
            pairs.append((ratio, i, j))
    pairs.sort(reverse=True)  # 最高相似度优先

    used_h = set()
    used_m = set()
    matched = []

    for ratio, i, j in pairs:
        if i not in used_h and j not in used_m:
            used_h.add(i)
            used_m.add(j)
            matched.append((i, j, ratio))

    # 按 HTML 段落顺序排序（保持原文顺序便于阅读报告）
    matched.sort(key=lambda x: x[0])

    unmatched_h = [i for i in range(hn) if i not in used_h]
    unmatched_m = [j for j in range(mn) if j not in used_m]

    return matched, unmatched_h, unmatched_m


# ─── 比较逻辑 ──────────────────────────────────────────────

class DiffReporter:
    """收集和输出差异"""

    # 白名单路径（相对于本脚本所在 skill 目录）
    WHITELIST_REL_PATH = "../references/verify_whitelist.json"

    def __init__(self):
        self.issues: List[Dict] = []
        self.stats = defaultdict(int)
        self._whitelist_rules: List[Dict] = []

    def _load_whitelist(self):
        """加载白名单 JSON 文件。找不到或格式错误时静默跳过。"""
        script_dir = Path(__file__).resolve().parent
        whitelist_path = script_dir / self.WHITELIST_REL_PATH
        if not whitelist_path.exists():
            return
        try:
            with open(whitelist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._whitelist_rules = data.get("rules", [])
        except (json.JSONDecodeError, IOError):
            self._whitelist_rules = []

    @staticmethod
    def _match_rule(issue: Dict, rule: Dict) -> bool:
        """检查一条 finding 是否匹配某条白名单规则。ALL 条件均满足才命中。"""
        conditions = rule.get("match", {})
        if not conditions:
            return False
        for field, pattern in conditions.items():
            value = issue.get(field, "")
            if not re.search(pattern, str(value)):
                return False
        return True

    def apply_whitelist(self):
        """按白名单规则过滤 findings。命中 silence → 移除；命中 downgrade → 降级为 info。"""
        if not self._whitelist_rules:
            self._load_whitelist()
        if not self._whitelist_rules:
            return

        silenced = 0
        downgraded = 0
        filtered = []
        for issue in self.issues:
            matched = False
            for rule in self._whitelist_rules:
                if self._match_rule(issue, rule):
                    action = rule.get("action", "silence")
                    if action == "silence":
                        matched = True
                        silenced += 1
                    elif action == "downgrade":
                        issue["severity"] = "info"
                        downgraded += 1
                    break  # 首条命中即停止
            if not matched:
                filtered.append(issue)

        if silenced or downgraded:
            # 重新统计（stats 基于 issues 列表，重建）
            self.issues = filtered
            self.stats.clear()
            for issue in self.issues:
                self.stats[f"{issue['severity']}_{issue['category']}"] += 1

    def add(self, article_title: str, severity: str, category: str,
            detail: str, expected: str = "", actual: str = "",
            md_line: int = 0, md_text: str = ""):
        self.issues.append({
            "article": article_title,
            "severity": severity,  # error, warning, info
            "category": category,
            "detail": detail,
            "expected": expected,
            "actual": actual,
            "md_line": md_line,
            "md_text": md_text,
        })
        self.stats[f"{severity}_{category}"] += 1

    def report_markdown(self) -> str:
        lines = []
        lines.append("# CBETA HTML ↔ 本地 MD 校对报告\n")

        # Summary
        errors = sum(1 for i in self.issues if i["severity"] == "error")
        warnings = sum(1 for i in self.issues if i["severity"] == "warning")
        infos = sum(1 for i in self.issues if i["severity"] == "info")
        lines.append("## 总览\n")
        lines.append(f"| 类别 | 数量 |")
        lines.append(f"|------|------|")
        lines.append(f"| 🔴 错误（缺漏/错位） | {errors} |")
        lines.append(f"| 🟡 警告（可能问题） | {warnings} |")
        lines.append(f"| 🔵 信息（注意项） | {infos} |")
        lines.append("")

        # By category
        lines.append("### 按问题类型\n")
        lines.append("| 类型 | 严重度 | 数量 |")
        lines.append("|------|--------|------|")
        for key, count in sorted(self.stats.items()):
            sev, cat = key.split("_", 1)
            sev_icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(sev, "")
            lines.append(f"| {cat} | {sev_icon} {sev} | {count} |")
        lines.append("")

        # Per-article details
        by_article = defaultdict(list)
        for issue in self.issues:
            by_article[issue["article"]].append(issue)

        lines.append("## 逐篇详情\n")
        for article in sorted(by_article.keys()):
            issues = by_article[article]
            has_error = any(i["severity"] == "error" for i in issues)
            icon = "🔴" if has_error else ("🟡" if any(i["severity"] == "warning" for i in issues) else "🔵")
            lines.append(f"### {icon} {article}\n")
            for idx, issue in enumerate(issues, 1):
                sev_icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}[issue["severity"]]
                lines.append(f"- **{idx}. {sev_icon} [{issue['category']}]** {issue['detail']}")
                if issue["expected"]:
                    lines.append(f"  - 期望（CBETA HTML）：`{issue['expected'][:120]}`")
                if issue["actual"]:
                    md_loc = f"（第 {issue['md_line']} 行）" if issue.get("md_line") else ""
                    lines.append(f"  - 实际（本地 MD{md_loc}）：`{issue['actual'][:120]}`")
                if issue.get("md_text"):
                    md_loc = f"第 {issue['md_line']} 行" if issue.get("md_line") else "MD"
                    lines.append(f"  - 本地 {md_loc} 有近似项：`{issue['md_text'][:120]}`")
            lines.append("")

        return "\n".join(lines)


def compare_articles(html_article: Article, md_article: Article,
                     reporter: DiffReporter, display_title: str = ""):
    """比较一篇文章的 HTML 和 MD 版本"""
    title = display_title or html_article.title or md_article.title
    h_els = html_article.elements
    m_els = md_article.elements

    # ── 分类提取 ──
    h_headings = [(el.level, el.content) for el in h_els if el.etype == "heading"]
    # MD headings: (level, text, line_number)
    m_headings = [(el.level, el.content, el.meta.get("line", 0)) for el in m_els if el.etype == "heading"]

    h_has_list = any(el.etype == "list_start" for el in h_els)
    m_has_list = any(el.etype == "list_start" for el in m_els)

    h_list_items = [el.content for el in h_els if el.etype == "list_item"]
    # MD list items: (text, line_number)
    m_list_items_raw = [(el.content, el.meta.get("line", 0)) for el in m_els if el.etype == "list_item"]
    m_list_items = [t for t, _ in m_list_items_raw]
    m_bylines = [el.content for el in m_els if el.etype == "byline"]

    h_notes = [el.content for el in h_els if el.etype == "note_inline"]
    m_notes_count = 0
    for el in m_els:
        if el.etype == "paragraph" or el.etype == "list_item" or el.etype == "byline":
            m_notes_count += len(re.findall(r"[（(][^）)]*?[）)]", el.content))
    # Also count notes in heading content
    for el in m_els:
        if el.etype == "heading":
            m_notes_count += len(re.findall(r"[（(][^）)]*?[）)]", el.content))

    h_figures = [el.content for el in h_els if el.etype == "figure"]
    m_figures = [el.content for el in m_els if el.etype == "figure"]

    h_paragraphs = [el.content for el in h_els if el.etype == "paragraph"]
    m_paragraphs = [el.content for el in m_els if el.etype == "paragraph"]

    # ── 1. 标题结构对比 ──
    # HTML: headings start at level 2, MD: headings start at level 1
    # Normalize: shift MD headings down by 1 (h1→treat as level 2 for comparison)

    # Build heading maps for comparison: norm_text → (level, orig_text)
    h_heading_map = {normalize_text(c): (lv, c) for lv, c in h_headings}
    # MD heading map: norm_text → (level, orig_text, line_number)
    m_heading_map = {normalize_text(c): (lv, c, ln) for lv, c, ln in m_headings}

    # Normalize: strip footnote markers like [1] [2], normalize full-width spaces
    def strip_footnote_ref(text: str) -> str:
        text = re.sub(r"\s*\[\d+\]", "", text)
        text = text.replace("　", "")  # 全角空格归一化
        return text.strip()

    h_heading_norm = {strip_footnote_ref(normalize_text(c)): (lv, c) for lv, c in h_headings}
    # MD normalized: norm_text → (level, orig_text, line_number)
    m_heading_norm = {}
    for lv, c, ln in m_headings:
        key = strip_footnote_ref(normalize_text(c))
        m_heading_norm[key] = (lv, c, ln)

    # Headings in HTML but NOT in MD → possibly dropped
    for h_text in h_heading_map:
        h_norm = strip_footnote_ref(normalize_text(h_text))
        if h_norm not in m_heading_norm:
            lv, orig = h_heading_map[h_text]
            reporter.add(title, "error", "heading_missing",
                         f"CBETA 有标题「{orig}」(L{lv})，但 MD 中缺失",
                         expected=orig)
        else:
            h_lv, _ = h_heading_map[h_text]
            m_lv, m_orig, _m_ln = m_heading_norm[h_norm]
            # Level comparison: HTML L2 = MD L1, so m_lv should be h_lv - 1
            expected_md_lv = h_lv - 1
            # heading_level 警告已抑制：MD 最多 6 层深度，层级漂移不影响内容正确性

    # Headings in MD but NOT in HTML → extra (like 綱要/前言 case)
    skip_extra_headings = {"目錄", "目录", "註釋", "注释"}
    for m_text in m_heading_map:
        m_norm = strip_footnote_ref(normalize_text(m_text))
        if m_norm not in h_heading_norm:
            lv, orig, ln = m_heading_map[m_text]
            if orig.strip() not in skip_extra_headings:
                reporter.add(title, "info", "heading_extra",
                             f"MD 中有标题「{orig}」(L{lv})，但 CBETA HTML 中无此标题",
                             actual=orig, md_line=ln)

    # ── 2. 列表对比 ──
    if h_has_list and not m_has_list:
        reporter.add(title, "error", "list_missing",
                     f"CBETA 有列表（{len(h_list_items)} 项），MD 中完全缺失",
                     expected=f"{len(h_list_items)} items")
    elif h_has_list and m_has_list:
        # Compare list items — MD may have expanded descriptions,
        # so use substring matching (HTML item ⊂ MD item)
        m_items_norm = [normalize_text(li) for li in m_list_items]
        for i, hi in enumerate(h_list_items):
            hi_norm = normalize_text(hi)
            if not hi_norm:
                continue
            # Check if HTML item text appears as substring of any MD item
            found = any(hi_norm in mi for mi in m_items_norm)
            if not found:
                # Try to find the closest matching MD item by text similarity
                md_line = 0
                md_similar = ""
                if m_items_norm:
                    matches = difflib.get_close_matches(hi_norm, m_items_norm, n=1, cutoff=0.5)
                    if matches:
                        idx = m_items_norm.index(matches[0])
                        if idx < len(m_list_items_raw):
                            md_similar = m_list_items_raw[idx][0]
                            md_line = m_list_items_raw[idx][1]
                reporter.add(title, "error", "list_item_missing",
                             f"列表项「{h_list_items[i]}」在 MD 中缺失",
                             expected=h_list_items[i],
                             md_line=md_line,
                             md_text=md_similar)

    # ── 3. 夹注对比 ──
    h_note_count = len(h_notes)
    if h_note_count > 0:
        # Count inline notes in MD (parenthetical content)
        # This is approximate since MD doesn't mark notes explicitly
        note_diff = h_note_count - m_notes_count
        if note_diff > 0:
            reporter.add(title, "warning", "note_inline",
                         f"CBETA 有 {h_note_count} 条夹注 (doube-line-note)，"
                         f"MD 中检测到约 {m_notes_count} 处括号内容，"
                         f"可能有 {note_diff} 条夹注的语义标记丢失",
                         expected=str(h_note_count), actual=f"~{m_notes_count}")
        # Show the actual notes that might be missing
        for note in h_notes[:5]:  # first 5
            note_norm = normalize_text(note)
            found = False
            for p in m_paragraphs + m_list_items + m_bylines:
                if note_norm in normalize_text(p):
                    found = True
                    break
            if not found:
                reporter.add(title, "warning", "note_content_missing",
                             f"夹注内容「{note}」可能在 MD 中丢失",
                             expected=note)

    # ── 4. 图片对比 ──
    if len(h_figures) != len(m_figures):
        reporter.add(title, "warning", "figure_count",
                     f"图片数量不一致: CBETA {len(h_figures)} vs MD {len(m_figures)}",
                     expected=str(len(h_figures)), actual=str(len(m_figures)))
    elif len(h_figures) > 0:
        # All match count-wise; check if URLs are reasonable
        for hf in h_figures:
            if hf.startswith("data:image"):
                continue  # base64 inline in HTML, OK
            # check if MD has corresponding figure
            found = any(
                os.path.basename(hf) in mf or os.path.basename(mf) in hf
                for mf in m_figures
            )
            if not found:
                reporter.add(title, "warning", "figure_mismatch",
                             f"图片引用不匹配: CBETA「{hf}」",
                             expected=hf[:80])

    # ── 5. 段落级文本对比（模糊对齐）──
    h_paras = [el.content for el in h_els if el.etype == "paragraph"]
    m_paras = [el.content for el in m_els if el.etype == "paragraph"]
    # Also map paragraph line numbers from MD
    m_para_lines = [el.meta.get("line", 0) for el in m_els if el.etype == "paragraph"]

    # ── 5a. 模糊对齐：用内容相似度配对段落 ──
    matched_pairs, unmatched_h, unmatched_m = align_paragraphs(h_paras, m_paras)

    # 段落数差异（排除 ASCII 結構性段落後再比較）
    m_non_structural = [p for p in m_paras if not is_structural_art(p)]
    h_non_structural = [p for p in h_paras if not is_structural_art(p)]
    if len(h_non_structural) != len(m_non_structural):
        reporter.add(title, "info", "paragraph_count",
                     f"段落数不同: CBETA {len(h_non_structural)} vs MD {len(m_non_structural)}"
                     f"（已用模糊对齐，{len(matched_pairs)} 对匹配成功）",
                     expected=str(len(h_non_structural)), actual=str(len(m_non_structural)))

    # ── 5b. 逐对比较已匹配段落 ──
    for h_idx, m_idx, align_ratio in matched_pairs:
        hp = h_paras[h_idx]
        mp = m_paras[m_idx]
        mdl = m_para_lines[m_idx] if m_idx < len(m_para_lines) else 0

        hp_norm = normalize_text_light(hp)
        mp_norm = normalize_text_light(mp)

        # 跳过空段落
        if not hp_norm and not mp_norm:
            continue

        # 完全一致，跳过
        if hp_norm == mp_norm:
            continue

        # 计算精确相似度
        ratio = difflib.SequenceMatcher(None, hp_norm, mp_norm).ratio()

        # 字符数差异
        char_diff = len(hp_norm) - len(mp_norm)
        char_note = f"，MD 少 {char_diff} 字符" if char_diff > 0 else \
                    f"，MD 多 {-char_diff} 字符" if char_diff < 0 else ""

        # 始终生成差异片段（只要不是完全一致）
        diff_snippet = generate_para_diff(hp_norm, mp_norm)

        if ratio < 0.90:
            reporter.add(title, "error", "paragraph_mismatch",
                         f"段落 {h_idx+1}（→MD {m_idx+1}）严重不一致"
                         f"（相似度 {ratio:.0%}{char_note}）",
                         expected=hp[:200] + ("…" if len(hp) > 200 else ""),
                         actual=mp[:200] + ("…" if len(mp) > 200 else ""),
                         md_line=mdl, md_text=diff_snippet)
        elif ratio < 0.995 or abs(char_diff) >= 3:
            # 相似度高但有实质性差异（ratio不够高 或 缺/多 >=3 字符）
            reporter.add(title, "warning", "paragraph_diverged",
                         f"段落 {h_idx+1}（→MD {m_idx+1}）有差异"
                         f"（相似度 {ratio:.0%}{char_note}）",
                         expected=hp[:200] + ("…" if len(hp) > 200 else ""),
                         actual=mp[:200] + ("…" if len(mp) > 200 else ""),
                         md_line=mdl, md_text=diff_snippet)
        elif abs(char_diff) > 0:
            # ratio >= 0.995 但仍有 1-2 字符差异——info 级别，但必须展示
            reporter.add(title, "info", "paragraph_minor_diff",
                         f"段落 {h_idx+1}（→MD {m_idx+1}）微小差异"
                         f"（相似度 {ratio:.0%}{char_note}）",
                         expected=hp[:200] + ("…" if len(hp) > 200 else ""),
                         actual=mp[:200] + ("…" if len(mp) > 200 else ""),
                         md_line=mdl, md_text=diff_snippet)

    # ── 5c. 未匹配的 HTML 段落（CBETA 有，MD 中缺失）──
    # 先构建 MD 全文本索引：用于交叉检查"缺失"段落是否在 MD 中以
    # 其他结构形式（列表项、标题等）出现
    m_all_content_texts = {
        "list_item": [normalize_text_light(t) for t in m_list_items],
        "heading": [normalize_text_light(el.content) for el in m_els
                    if el.etype == "heading"],
        "pre": [normalize_text_light(el.content) for el in m_els
                if el.etype == "pre"],
        "byline": [normalize_text_light(el.content) for el in m_els
                   if el.etype == "byline"],
    }
    # 也检查 MD 段落文本中包含该内容（子串匹配）
    m_all_para_text = normalize_text_light("".join(m_paras))

    for h_idx in unmatched_h:
        hp = h_paras[h_idx]
        hp_norm = normalize_text_light(hp)

        # 交叉检查：是否在 MD 中以其他结构形式存在？
        found_as = None
        for struct_type, texts in m_all_content_texts.items():
            for t in texts:
                if hp_norm and len(hp_norm) >= 3 and hp_norm in t:
                    found_as = struct_type
                    break
                # 较短的文本：检查是否为 MD 列表项或段落子串
                if hp_norm and len(hp_norm) < 60 and hp_norm in m_all_para_text:
                    found_as = "paragraph_substring"
                    break
            if found_as:
                break
        # 也检查简单子串匹配（短文本可能是列表项被合并到段落中）
        if not found_as and hp_norm and len(hp_norm) < 60:
            if hp_norm in m_all_para_text:
                found_as = "paragraph_substring"

        if found_as:
            reporter.add(title, "info", "paragraph_structure_diff",
                         f"CBETA 第 {h_idx+1} 段在 MD 中非独立段落"
                         f"（作为「{found_as}」出现）",
                         expected=hp[:120] + ("…" if len(hp) > 120 else ""))
        else:
            reporter.add(title, "warning", "paragraph_missing",
                         f"CBETA 第 {h_idx+1} 段在 MD 中缺失"
                         f"（模糊对齐未找到匹配，且未在列表/标题/段落中找到）",
                         expected=hp[:200] + ("…" if len(hp) > 200 else ""))

    # ── 5d. 未匹配的 MD 段落（MD 有，CBETA HTML 中无对应）──
    for m_idx in unmatched_m:
        mp = m_paras[m_idx]
        if is_structural_art(mp):
            continue  # ASCII 圖表/代碼塊：HTML 以 <img> 呈現，不屬於文本缺失
        mdl = m_para_lines[m_idx] if m_idx < len(m_para_lines) else 0
        reporter.add(title, "info", "paragraph_extra",
                     f"MD 第 {m_idx+1} 段在 CBETA HTML 中无对应"
                     f"（可能为 XML 特有结构如表格/代码块）",
                     actual=mp[:200] + ("…" if len(mp) > 200 else ""),
                     md_line=mdl)

    # ── 5e. 全局逐字 diff（安全网：捕获任何段落对齐遗漏的文本差异）──
    # 逐段归一化后再拼接：确保 blockquote 标记 (>、**) 在每段开头被正确剥离，
    # 而非在全文中被当作中段文本保留。此前先 join 再 normalize 导致内段标记
    # 不在字符串开头 ^ 处，regex 无法匹配 → 产生结构性误报。
    h_all_text = "".join(normalize_text_light(p) for p in h_paras)
    m_all_text = "".join(normalize_text_light(p) for p in m_paras)
    if h_all_text and m_all_text:
        len_ratio = len(m_all_text) / len(h_all_text) if len(h_all_text) > 0 else 0
        global_char_diff = len(h_all_text) - len(m_all_text)

        if len_ratio < 0.85:
            reporter.add(title, "error", "text_truncated",
                         f"MD 文本量仅为 CBETA 的 {len_ratio:.0%}，可能有大段缺漏",
                         expected=f"{len(h_all_text)} chars",
                         actual=f"{len(m_all_text)} chars")
        elif abs(global_char_diff) > 0:
            # 用 get_opcodes 找出全局差异的确切位置
            s = difflib.SequenceMatcher(None, h_all_text, m_all_text)
            op_counts = {"delete": 0, "insert": 0, "replace": 0}
            total_del_chars = 0
            total_ins_chars = 0
            # 收集所有非 equal 的 opcode 做摘要
            diff_summary_parts = []
            for tag, i1, i2, j1, j2 in s.get_opcodes():
                if tag == "equal":
                    continue
                op_counts[tag] = op_counts.get(tag, 0) + 1
                if tag in ("delete", "replace"):
                    total_del_chars += (i2 - i1)
                if tag in ("insert", "replace"):
                    total_ins_chars += (j2 - j1)
                # 取差异处前后各 30 字符作为上下文
                ctx_start = max(0, i1 - 30)
                ctx_end = min(len(h_all_text), i2 + 30)
                snippet = h_all_text[ctx_start:ctx_end]
                if len(diff_summary_parts) < 5:  # 最多展示 5 处
                    if tag == "delete":
                        diff_summary_parts.append(
                            f"  CBETA「…{snippet}…」處刪除 {i2-i1} 字符")
                    elif tag == "insert":
                        diff_summary_parts.append(
                            f"  CBETA「…{snippet}…」處插入 {j2-j1} 字符")
                    else:
                        diff_summary_parts.append(
                            f"  CBETA「…{snippet}…」處替換 ({i2-i1}→{j2-j1} 字符)")

            total_ops = sum(op_counts.values())
            if total_ops > 0:
                # 计算「不可解释」的字符差异：
                # 未匹配段落的字符量差异属于结构性差异（HTML pre vs MD 段落等），
                # 不是真正的文本缺失
                unmatched_h_chars = sum(
                    len(normalize_text_light(h_paras[i])) for i in unmatched_h)
                unmatched_m_chars = sum(
                    len(normalize_text_light(m_paras[j])) for j in unmatched_m)
                structural_diff = abs(unmatched_h_chars - unmatched_m_chars)
                unexplained = abs(global_char_diff) - structural_diff

                summary = (f"全文字符級比對：CBETA {len(h_all_text)} 字符 vs "
                           f"MD {len(m_all_text)} 字符，"
                           f"淨差異 {global_char_diff} 字符"
                           f"（{total_ops} 處差異塊，"
                           f"刪 {total_del_chars} / 插 {total_ins_chars} 字符")
                if structural_diff > 0:
                    summary += (f"，其中 {structural_diff} 字符為結構性差異"
                                f"（未匹配段落），實際文本差異約 {unexplained} 字符")
                summary += "）"

                if len_ratio < 0.85:
                    severity = "error"
                elif unexplained > max(200, len(h_all_text) * 0.02):
                    # Error only when unexplained chars exceed 2% of total
                    # AND at least 200 chars. This tolerates paragraph
                    # segmentation differences (orig/commentary divs) that
                    # typically account for 1-2% of article length.
                    severity = "error"
                elif unexplained > max(50, len(h_all_text) * 0.005):
                    severity = "warning"
                elif unexplained > 0:
                    severity = "info"
                else:
                    # 全部為結構性差異（ASCII 圖 vs <img> 等），跳過不報
                    severity = None
                if severity is not None:
                    reporter.add(title, severity, "global_text_diff",
                                 summary,
                                 expected=f"{len(h_all_text)} chars",
                                 actual=f"{len(m_all_text)} chars",
                                 md_text="\n".join(diff_summary_parts)
                                         if diff_summary_parts else "")


# ─── 主流程 ──────────────────────────────────────────────────

def load_catalog(book_num: int) -> dict:
    """加载编目录 JSON"""
    for d in RESEARCH_DIR.iterdir():
        if d.is_dir() and d.name.startswith(f"{book_num:02d}_"):
            catalog_files = list(d.glob("*編目錄.json"))
            if catalog_files:
                with open(catalog_files[0], "r", encoding="utf-8") as f:
                    return json.load(f)
    return {}


def build_article_map(catalog: dict) -> Dict[str, Path]:
    """建立篇名→MD文件路径 的映射。
    MD 文件命名规则: {編號:02d}_{篇名}.md，放在 {子目}/ 子目录下。
    """
    mapping = {}
    book_num = catalog.get('编序号') or catalog.get('編號') or 0
    for d in RESEARCH_DIR.iterdir():
        if not d.is_dir() or not d.name.startswith(f"{book_num:02d}_"):
            continue
        # 建立目录下所有 MD 文件的 (編號, 篇名) 索引
        md_by_seq = {}   # global_seq -> Path
        md_by_title = {}  # title -> Path
        for md_path in d.rglob("*.md"):
            if md_path.name.startswith("_"):
                continue  # skip dashboard, catalog, etc.
            stem = md_path.stem
            # 解析 {seq:02d}_{title} 格式
            match = re.match(r"^(\d{1,2})_(.+)", stem)
            if match:
                seq = int(match.group(1))
                title = match.group(2)
                md_by_seq[seq] = md_path
                md_by_title[title] = md_path

        # 按 catalog 条目建立映射
        for entry in catalog.get("篇目鏈表", []):
            title = entry.get("篇名", "")
            seq = entry.get("編號", 0)
            # 优先按全局序号匹配
            if seq in md_by_seq:
                mapping[title] = md_by_seq[seq]
            elif title in md_by_title:
                mapping[title] = md_by_title[title]
        break
    return mapping


def main():
    parser = argparse.ArgumentParser(description="校对 CBETA HTML vs 本地 MD")
    parser.add_argument("--book", type=int, default=1, help="编号 (默认 1)")
    parser.add_argument("--article", action='append', type=str, help="文章名（可多次指定，仅校对指定文章）")
    parser.add_argument("--output", type=str, help="输出报告文件路径")
    parser.add_argument("--html-dir", type=str, help="HTML 目录路径（覆盖自动检测）")
    args = parser.parse_args()

    # 找到 HTML 目录
    html_dirs = find_html_dirs()
    if args.html_dir:
        html_dir = Path(args.html_dir)
    elif html_dirs:
        html_dir = html_dirs[0]  # 使用第一个找到的
    else:
        print("❌ 未找到 TX_HTML 目录，请用 --html-dir 指定")
        sys.exit(1)

    # 找到对应编的子目录
    book_dirs = [d for d in html_dir.iterdir() if d.is_dir()]
    if not book_dirs:
        print(f"❌ HTML 目录下未找到子目录: {html_dir}")
        sys.exit(1)

    book_html_dir = book_dirs[0]  # 默认第一个
    for d in book_dirs:
        if d.name.startswith(f"{args.book:02d}_"):
            book_html_dir = d
            break

    print(f"📂 HTML 目录: {book_html_dir}")
    html_files = sorted(book_html_dir.glob("*.html"))
    print(f"📄 找到 {len(html_files)} 个 HTML 文件")

    # 加载编目录
    catalog = load_catalog(args.book)
    if catalog:
        article_map = build_article_map(catalog)
        print(f"📋 编目录加载: {catalog.get('編名', '?')}，{len(catalog.get('篇目鏈表', []))} 篇文章")
        print(f"🗺️  已映射 {len(article_map)} 个 MD 文件")
        # 构建 篇名 → 編號 映射，用于报告中显示编号
        title_to_seq = {e['篇名']: e['編號'] for e in catalog.get('篇目鏈表', [])}
    else:
        article_map = {}
        title_to_seq = {}
        print("⚠️  未找到编目录 JSON，将仅按文件名匹配")

    # 逐篇对比
    reporter = DiffReporter()
    compared = 0

    for hf in html_files:
        # 解析 HTML
        try:
            html_art = parse_html(str(hf))
        except Exception as e:
            print(f"⚠️  解析 HTML 失败: {hf.name}: {e}")
            continue

        title = html_art.title
        if not title:
            print(f"⚠️  无法提取标题: {hf.name}")
            continue

        # 在标题前附加編號，方便对照查找（保留原标题用于内部匹配）
        seq = title_to_seq.get(title, 0)
        display_title = f"第{seq}篇 {title}" if seq else title

        # 筛选指定文章
        if args.article and not any(a in title for a in args.article):
            continue

        # 找到对应 MD
        md_path = article_map.get(title)
        if not md_path:
            # Try normalized title (strip full-width spaces, footnote refs)
            title_norm = re.sub(r"[　\s]", "", title)
            title_norm = re.sub(r"\[\d+\]", "", title_norm)
            for t, p in article_map.items():
                t_norm = re.sub(r"[　\s]", "", t)
                t_norm = re.sub(r"\[\d+\]", "", t_norm)
                if title_norm == t_norm or title in t or t in title:
                    md_path = p
                    break

        if not md_path or not md_path.exists():
            if args.article:
                # 用戶指定文章但 MD 不存在 → 報錯
                reporter.add(title, "error", "md_not_found",
                             f"找不到对应的 MD 文件",
                             expected=f"research/**/{title}.md")
                print(f"⚠️  {title}: MD 文件未找到")
            # 未指定文章時 → 跳過未提取的文章，不報錯
            continue

        # 解析 MD
        try:
            md_art = parse_md(str(md_path))
        except Exception as e:
            reporter.add(title, "error", "md_parse_error",
                         f"解析 MD 失败: {e}")
            print(f"⚠️  {title}: MD 解析失败: {e}")
            continue

        # 对比
        compare_articles(html_art, md_art, reporter, display_title)
        compared += 1
        print(f"✓ {display_title}")

    print(f"\n✅ 对比完成: {compared}/{len(html_files)} 篇")

    # 应用白名单过滤
    reporter.apply_whitelist()

    # 输出报告
    report = reporter.report_markdown()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"📝 报告已保存: {args.output}")
    else:
        print("\n" + report)


if __name__ == "__main__":
    main()
