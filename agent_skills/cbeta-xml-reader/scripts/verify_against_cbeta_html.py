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

import os, sys, re, json, argparse
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
            elements.append(Element("heading", text, level, {}))
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
            elements.append(Element("list_item", text, 0, {}))
            i += 1
            continue

        # Ordered list item
        ol_match = re.match(r"^(\s*)\d+[.)]\s+(.+)", line)
        if ol_match:
            if not in_list:
                elements.append(Element("list_start", "", 0, {"ordered": True}))
                in_list = True
            text = ol_match.group(2).strip()
            elements.append(Element("list_item", text, 0, {}))
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
        # Merge continuation lines (lines starting with non-markup text)
        while i + 1 < len(lines) and lines[i + 1].strip() and \
              not re.match(r"^(#{1,6}\s|!\[|- |\* |\d+[.)] |\||---)", lines[i + 1]):
            i += 1
            text += " " + lines[i].strip()
        elements.append(Element("paragraph", text, 0, {}))
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


# ─── 比较逻辑 ──────────────────────────────────────────────

class DiffReporter:
    """收集和输出差异"""

    def __init__(self):
        self.issues: List[Dict] = []
        self.stats = defaultdict(int)

    def add(self, article_title: str, severity: str, category: str,
            detail: str, expected: str = "", actual: str = ""):
        self.issues.append({
            "article": article_title,
            "severity": severity,  # error, warning, info
            "category": category,
            "detail": detail,
            "expected": expected,
            "actual": actual,
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
            for issue in issues:
                sev_icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}[issue["severity"]]
                lines.append(f"- **{sev_icon} [{issue['category']}]** {issue['detail']}")
                if issue["expected"]:
                    lines.append(f"  - 期望（CBETA HTML）：`{issue['expected'][:120]}`")
                if issue["actual"]:
                    lines.append(f"  - 实际（本地 MD）：`{issue['actual'][:120]}`")
            lines.append("")

        return "\n".join(lines)


def compare_articles(html_article: Article, md_article: Article,
                     reporter: DiffReporter):
    """比较一篇文章的 HTML 和 MD 版本"""
    title = html_article.title or md_article.title
    h_els = html_article.elements
    m_els = md_article.elements

    # ── 分类提取 ──
    h_headings = [(el.level, el.content) for el in h_els if el.etype == "heading"]
    m_headings = [(el.level, el.content) for el in m_els if el.etype == "heading"]

    h_has_list = any(el.etype == "list_start" for el in h_els)
    m_has_list = any(el.etype == "list_start" for el in m_els)

    h_list_items = [el.content for el in h_els if el.etype == "list_item"]
    m_list_items = [el.content for el in m_els if el.etype == "list_item"]

    h_notes = [el.content for el in h_els if el.etype == "note_inline"]
    m_notes_count = 0
    for el in m_els:
        if el.etype == "paragraph" or el.etype == "list_item":
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

    # Build heading maps for comparison
    h_heading_map = {normalize_text(c): (lv, c) for lv, c in h_headings}
    m_heading_map = {normalize_text(c): (lv, c) for lv, c in m_headings}

    # Normalize: strip footnote markers like [1] [2], normalize full-width spaces
    def strip_footnote_ref(text: str) -> str:
        text = re.sub(r"\s*\[\d+\]", "", text)
        text = text.replace("　", "")  # 全角空格归一化
        return text.strip()

    h_heading_norm = {strip_footnote_ref(normalize_text(c)): (lv, c) for lv, c in h_headings}
    m_heading_norm = {strip_footnote_ref(normalize_text(c)): (lv, c) for lv, c in m_headings}

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
            m_lv, m_orig = m_heading_norm[h_norm]
            # Level comparison: HTML L2 = MD L1, so m_lv should be h_lv - 1
            expected_md_lv = h_lv - 1
            if m_lv != expected_md_lv:
                reporter.add(title, "warning", "heading_level",
                             f"标题「{h_heading_map[h_text][1]}」层级不一致: "
                             f"CBETA L{h_lv} → MD L{m_lv} (期望 L{expected_md_lv})",
                             expected=f"L{expected_md_lv}", actual=f"L{m_lv}")

    # Headings in MD but NOT in HTML → extra (like 綱要/前言 case)
    skip_extra_headings = {"目錄", "目录", "註釋", "注释"}
    for m_text in m_heading_map:
        m_norm = strip_footnote_ref(normalize_text(m_text))
        if m_norm not in h_heading_norm:
            lv, orig = m_heading_map[m_text]
            if orig.strip() not in skip_extra_headings:
                reporter.add(title, "info", "heading_extra",
                             f"MD 中有标题「{orig}」(L{lv})，但 CBETA HTML 中无此标题",
                             actual=orig)

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
                reporter.add(title, "error", "list_item_missing",
                             f"列表项「{h_list_items[i]}」在 MD 中缺失",
                             expected=h_list_items[i])

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
            for p in m_paragraphs + m_list_items:
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

    # ── 5. 纯文本一致性（粗略） ──
    # Extract all text from both, normalize, compare length
    h_all_text = normalize_text("".join(
        el.content for el in h_els
        if el.etype in ("paragraph", "heading", "list_item", "pre")
    ))
    m_all_text = normalize_text("".join(
        el.content for el in m_els
        if el.etype in ("paragraph", "heading", "list_item")
    ))

    if h_all_text and m_all_text:
        len_ratio = len(m_all_text) / len(h_all_text) if len(h_all_text) > 0 else 0
        if len_ratio < 0.85:
            reporter.add(title, "error", "text_truncated",
                         f"MD 文本量仅为 CBETA 的 {len_ratio:.0%}，可能有大段缺漏",
                         expected=f"{len(h_all_text)} chars", actual=f"{len(m_all_text)} chars")
        elif len_ratio < 0.95:
            reporter.add(title, "warning", "text_length",
                         f"MD 文本量为 CBETA 的 {len_ratio:.0%}，可能有少量缺漏",
                         expected=f"{len(h_all_text)} chars", actual=f"{len(m_all_text)} chars")


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
        if f"{args.book:02d}" in d.name or f"佛法" in d.name:
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
    else:
        article_map = {}
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
        compare_articles(html_art, md_art, reporter)
        compared += 1
        print(f"✓ {title}")

    print(f"\n✅ 对比完成: {compared}/{len(html_files)} 篇")

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
