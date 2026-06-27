#!/usr/bin/env python3
"""Extract a full article from CBETA TX XML as Markdown with TOC and body.

Two modes:
  1. --catalog + --article  → look up byte offsets from 编级 JSON
  2. --file + --byte-start + --byte-end  → direct byte-range extraction

Output: {篇名}.md — pure plain-text Markdown (no Obsidian syntax, no anchor links).

Usage:
  python extract_article_fulltext.py \
    --catalog _research/01_佛法總學/_01_佛法總學_編目錄.json \
    --article "佛學概論"

  python extract_article_fulltext.py \
    --file TX01n0001.xml --byte-start 3652 --byte-end 122954 \
    --out-dir _research/01_佛法總學
"""

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
import os

CBETA_NS = 'http://www.cbeta.org/ns/1.0'
TEI_NS = 'http://www.tei-c.org/ns/1.0'

from _utils import (chinese_to_int, normalize_byline, split_month_season,
                    build_suffix, parse_byline_fields)

# Workspace-relative figures base directory; relative path computed dynamically in main()
FIGURES_BASE_DIR = '_research/figures/TX'
FIGURES_REL_PATH = ''  # set in main()

# ── Anchor ID ─────────────────────────────────────────────────────────

CJK_RANGES = [
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3400, 0x4DBF),   # CJK Extension A
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
]

def _is_cjk(ch):
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in CJK_RANGES)

def count_chinese_chars(text):
    """Count Chinese characters (CJK) in text."""
    count = 0
    for ch in text:
        if _is_cjk(ch):
            count += 1
    return count

def normalize_heading(heading):
    """Insert space after Chinese ordinal prefix for readability.

    Examples:
        一緒言 → 一 緒言
        第一章釋尊略傳 → 第一章 釋尊略傳
        一心之分析 → 一 心之分析
    """
    NUM = '一二三四五六七八九十百千万'
    SEC = '章節节篇部'
    GAN = '甲乙丙丁戊己庚辛壬癸'
    # Pattern 1: 第 + numerals + section word → insert space before rest
    heading = re.sub(
        rf'^(第[{NUM}]+[{SEC}])(?=[一-鿿])',
        r'\1' + '\u3000',
        heading
    )
    # Pattern 2: bare numerals at start → insert space before rest
    # Pattern 1a: 天干 + numerals → insert space before rest (e.g. 甲一序分)
    heading = re.sub(
        rf'^([{GAN}][{NUM}]+)(?=[一-鿿])',
        r'\1' + '\u3000',
        heading
    )
    # Pattern 1b: 天干 alone → insert space before rest (e.g. 甲色蘊)
    heading = re.sub(
        rf'^([{GAN}])(?=(?![{NUM}])[一-鿿])',
        r'\1' + '\u3000',
        heading
    )
    heading = re.sub(
        rf'^([{NUM}])(?=[一-鿿])',
        r'\1' + '\u3000',
        heading
    )
    return heading
# ── XML helpers ───────────────────────────────────────────────────────

def parse_article_chunk(xml_path, byte_start, byte_end):
    with open(xml_path, 'rb') as f:
        f.seek(byte_start)
        chunk = f.read(byte_end - byte_start)
    wrap = (
        '<root xmlns:cb="http://www.cbeta.org/ns/1.0"'
        ' xmlns:tei="http://www.tei-c.org/ns/1.0">'
        + chunk.decode('utf-8', errors='replace')
        + '</root>'
    )
    return ET.fromstring(wrap)

def get_heading_text(div):
    """Return (heading_text, note_anchor_id_or_None)."""
    head = div.find(f"{{{TEI_NS}}}head")
    if head is None:
        head = div.find("head")
    note_anchor = None
    if head is not None:
        # Check for nkr_note_orig anchor inside head
        anchor = head.find(f"{{{TEI_NS}}}anchor")
        if anchor is None:
            anchor = head.find("anchor")
        if anchor is not None:
            aid = anchor.get("{http://www.w3.org/XML/1998/namespace}id") or anchor.get("xml:id", "")
            if aid.startswith("nkr_note_orig_"):
                note_anchor = aid
        atext = re.sub(r"[\u3000]+", "", "".join(head.itertext()).strip())
        if atext:
            return atext, note_anchor
    mulu = div.find(f"{{{CBETA_NS}}}mulu")
    if mulu is not None:
        return "".join(mulu.itertext()).strip(), note_anchor
    return "", note_anchor
def get_mulu_text(div):
    mulu = div.find(f'{{{CBETA_NS}}}mulu')
    if mulu is not None:
        return ''.join(mulu.itertext()).strip()
    return ''

def get_mulu_level(div):
    mulu = div.find(f'{{{CBETA_NS}}}mulu')
    if mulu is not None:
        return int(mulu.get('level', '0'))
    return 0

def get_byline_text(div):
    # Only search direct children — walk_div_tree handles nested bylines in body
    # Also: only return byline if BEFORE any <p>; after <p> it's 篇末附注, not 題注
    byline = None
    for child in div:
        local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if local_tag == 'p':
            return ''  # <p> before any <byline> → subsequent byline is end-of-article
        if local_tag == 'byline':
            byline = child
            break
    # Fallback: also try namespace-aware search on direct children
    if byline is None:
        for child in div:
            if child.tag == f'{{{TEI_NS}}}byline':
                byline = child
                break
    if byline is not None:
        raw = ''.join(byline.itertext()).strip()
        return normalize_byline(raw)
    return ''

def should_skip_div(mulu_text):
    for kw in ['目次', '綱要', '目錄', '目録', '科分']:
        if kw in mulu_text:
            return True
    return False

def render_paragraph(p_elem, notes_map=None):
    """Render <p> to text, notes → （...）, lb/pb discarded, note anchors → [N]."""
    parts = []
    is_pre = p_elem.get(f'{{{CBETA_NS}}}type') == 'pre'

    # Detect <p><figure><graphic url='...'/> — output Markdown image
    p_children = list(p_elem)
    if len(p_children) == 1:
        only_child = p_children[0]
        only_tag = only_child.tag.split('}')[-1] if '}' in only_child.tag else only_child.tag
        if only_tag == 'figure':
            graphic = only_child.find('graphic')
            if graphic is None:
                for ns_pfx in [f'{{{CBETA_NS}}}', f'{{{TEI_NS}}}']:
                    graphic = only_child.find(f'{ns_pfx}graphic')
                    if graphic is not None:
                        break
            if graphic is not None:
                url = graphic.get('url', '')
                basename = url.split('/')[-1] if '/' in url else url
                return f'![{basename}]({FIGURES_REL_PATH}/{basename})\n'

    def walk(node):
        if node.text and is_pre:
            parts.append(node.text.rstrip('\n'))
        elif node.text:
            parts.append(node.text)
        for child in node:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag == 'note':
                nt = ''.join(child.itertext()).strip()
                if nt:
                    parts.append(f'（{nt}）')
            elif tag == 'anchor':
                aid = child.get("{http://www.w3.org/XML/1998/namespace}id") or child.get("xml:id", "")
                if notes_map and aid in notes_map:
                    n = notes_map[aid]
                    parts.append(f'[{n}]')
            elif tag in ('lb', 'pb'):
                if is_pre and tag == 'lb':
                    parts.append('\n')
            elif tag in ('byline', 'head'):
                pass
            elif tag == 'seg':
                if child.get('rend') == 'bold':
                    parts.append('**' + ''.join(child.itertext()).strip() + '**')
                else:
                    parts.append(''.join(child.itertext()))
            else:
                parts.append(''.join(child.itertext()))
            if child.tail and is_pre:
                parts.append(child.tail.rstrip('\n'))
            elif child.tail:
                parts.append(child.tail)

    walk(p_elem)
    text = ''.join(parts)
    if is_pre:
        # Only strip trailing newlines; preserve leading spaces for alignment
        return '\n```\n' + text.rstrip('\n') + '\n```\n'
    text = text.strip()
    text = ''.join(text.split())
    return text
def _is_tei_tag(tag, name):
    return tag == f'{{{TEI_NS}}}{name}' or tag == name

def extract_paragraphs(div, notes_map=None):
    out = []
    for child in div:
        local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        # Skip bylines that are 题下注释 (——...—— format, date/location)
        # already extracted by get_byline_text() and placed after the article title.
        # Do NOT use cb:type="other" for this — CBETA uses it on both
        # 题下注释 AND 记录者 bylines (pitfall #22).
        if local_tag == 'byline':
            raw = ''.join(child.itertext()).strip()
            if raw.startswith('——') and raw.endswith('——'):
                continue
        if local_tag in ('byline', 'note'):
            # byline/note as direct children of a div (sibling of <p>)
            # Use itertext() to capture text across <lb/> breaks (pitfall #16)
            own_text = ''.join(child.itertext())
            own_text = ''.join(own_text.split())  # compress whitespace
            # Check for nkr_note_orig_* anchors inside byline/note elements.
            # itertext() skips anchor elements (they have no text), so we
            # must explicitly collect footnote number(s) and append them.
            if notes_map:
                for anchor_elem in child.iter(f'{{{TEI_NS}}}anchor'):
                    aid = anchor_elem.get("{http://www.w3.org/XML/1998/namespace}id") or anchor_elem.get("xml:id", "")
                    if aid and aid in notes_map:
                        own_text += f'[{notes_map[aid]}]'
                for anchor_elem in child.findall('.//anchor'):
                    aid = anchor_elem.get("{http://www.w3.org/XML/1998/namespace}id") or anchor_elem.get("xml:id", "")
                    if aid and aid in notes_map:
                        own_text += f'[{notes_map[aid]}]'
            inline_note = child.find(f'{{{TEI_NS}}}note')
            if inline_note is None:
                inline_note = child.find('note')
            if inline_note is not None and inline_note.get('place') == 'inline':
                nt = ''.join(inline_note.itertext())
                nt = ''.join(nt.split())  # compress same as own_text
                # Remove note text from own_text (it's caught by itertext above)
                if nt:
                    own_text = own_text.replace(nt, '').rstrip()
                    own_text = ''.join(own_text.split())
                if own_text and nt:
                    out.append(f'{own_text}（{nt}）')
                elif nt:
                    out.append(f'（{nt}）')
                elif own_text:
                    out.append(own_text)
            elif own_text:
                out.append(own_text)
        elif _is_tei_tag(child.tag, 'p'):
            text = render_paragraph(child, notes_map)
            if text.strip():
                out.append(text)
    return out


def normalize_blank_lines(lines):
    """Collapse consecutive blank lines into a single blank line."""
    result = []
    prev_blank = False
    for line in lines:
        is_blank = (line.strip() == '')
        if is_blank:
            if not prev_blank:
                result.append(line)
            prev_blank = True
        else:
            result.append(line)
            prev_blank = False
    return result


# ── Back-note extraction ─────────────────────────────────────────────

# Per-file cache of {anchor_id: (note_n, raw_body)} parsed from <back>.
# Keyed by absolute file path. The full file is read + regex-scanned only
# once per file instead of once per article (batch mode previously paid
# O(N × file size) re-reading the same ~900KB file for every article).
_BACK_NOTE_CACHE = {}

def _get_back_note_map(full_xml_path):
    """Return {anchor_id: (note_n, raw_body)} for a file's <back> notes.

    Reads the whole file and scans <back> exactly once per file, caching
    the result. <back> is unique per CBETA TX file, so the cache is safe.
    """
    key = os.path.abspath(str(full_xml_path))
    cached = _BACK_NOTE_CACHE.get(key)
    if cached is not None:
        return cached

    with open(full_xml_path, 'r', encoding='utf-8') as f:
        full_text = f.read()

    note_map = {}
    back_match = re.search(r'<back>.*?</back>', full_text, re.DOTALL)
    if back_match:
        note_pattern = re.compile(
            r'<note n="(\d+)"[^>]*target="#(nkr_note_orig_\d+)"[^>]*>(.*?)</note>',
            re.DOTALL
        )
        for m in note_pattern.finditer(back_match.group()):
            note_map[m.group(2)] = (int(m.group(1)), m.group(3))

    _BACK_NOTE_CACHE[key] = note_map
    return note_map


def extract_article_notes(full_xml_path, article_byte_start, article_byte_end):
    """Find <note> elements in <back> that target anchors inside the article.

    Returns (notes, anchor_ids) where notes is a list of (label, body)
    matching anchor order in the article.
    """
    with open(full_xml_path, 'rb') as f:
        f.seek(article_byte_start)
        article_chunk = f.read(article_byte_end - article_byte_start).decode('utf-8', errors='replace')

    # Collect all nkr_note_orig_* anchor IDs from the article, in order
    anchor_ids = re.findall(r'anchor xml:id="(nkr_note_orig_\d+)"', article_chunk)
    if not anchor_ids:
        return [], []

    # Look up the per-file <back> note map (cached across articles)
    note_map = _get_back_note_map(full_xml_path)
    if not note_map:
        return [], []

    # Build ordered list matching anchor order in article
    CHINESE_NUMERALS = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
    notes = []
    for idx, aid in enumerate(anchor_ids):
        if aid in note_map:
            note_n, raw_body = note_map[aid]
            body = re.sub(r'<[^>]+>', '', raw_body).strip()
            num_label = CHINESE_NUMERALS[idx] if idx < len(CHINESE_NUMERALS) else str(idx + 1)
            notes.append((f'注{num_label}', body))

    return notes, anchor_ids


def find_appendix_info(article_div):
    """Find appendix (附) divs within the article.

    Scans direct child divs of the article div for any whose <cb:mulu>
    text starts with '附', treating those as attached articles.

    Returns list of dicts: {title, date_location}
    """
    appendixes = []
    for child in article_div:
        if child.tag != f'{{{CBETA_NS}}}div':
            continue
        mulu = child.find(f'{{{CBETA_NS}}}mulu')
        if mulu is None:
            continue
        mulu_text = ''.join(mulu.itertext()).strip()
        if not mulu_text.startswith('附'):
            continue
        # Found an appendix div — prefer <head> text, fall back to mulu
        head = child.find(f'{{{TEI_NS}}}head')
        if head is None:
            head = child.find('head')
        title = ''.join(head.itertext()).strip() if head is not None else mulu_text
        # Replace full-width space (U+3000) between 附 and title with ：
        title = re.sub(r"^附[：\u3000]*(?=[一-鿿])", "附：", title)
        dl = _extract_appendix_date_location(child)
        appendixes.append({'title': title, 'date_location': dl})
    return appendixes


def _extract_appendix_date_location(appendix_div):
    """Try to extract date/location from an appendix div.

    Looks for:
    1. （附註） paragraph with date/location info
    2. A <byline> (skipping publication-only notes starting with 見)
    """
    for elem in appendix_div.iter():
        local_tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        text = ''.join(elem.itertext()).strip()
        if local_tag == 'p':
            # Look for （附註） … ，DATE；今附於此 pattern
            m = re.match(
                r'[（(]附[註注][）)]\s*[「](.+?)[」]\s*[，,]\s*(.+?)[；;]\s*今附[於于]此',
                text
            )
            if m:
                raw_dl = m.group(2).strip()
                return _normalize_appendix_date_location(raw_dl)
        elif local_tag == 'byline':
            if text and not text.startswith('見'):
                return normalize_byline(text)
    return ''


def _normalize_appendix_date_location(raw):
    """Normalize appendix date/location text.

    Input:  '二十四年七月講於莫干山'
    Output: '（1935 年 7 月，在莫干山講）'
    """
    raw = raw.strip()
    if not raw:
        return ''
    # Split into date part (year + optional month/season) and location part
    m = re.match(r'(.+?年(?:[一二三四五六七八九十]+月|[春夏秋冬])?)\s*(.*)', raw)
    if not m:
        return normalize_byline(raw)
    date_part = m.group(1).strip()
    loc_part = m.group(2).strip().lstrip('，,。.')
    normalized = normalize_byline(date_part)
    if not normalized:
        return ''
    if not loc_part:
        return normalized
    # Process location: 講於X → 在X講  /  X講 → 在X講
    if '講於' in loc_part:
        loc_part = '在' + loc_part[2:] + '講'
    elif loc_part.endswith('講') and not loc_part.startswith('在'):
        loc_part = '在' + loc_part
    elif not loc_part.startswith('在'):
        loc_part = '在' + loc_part
    date_inner = normalized.strip('（）')
    return f'（{date_inner}，{loc_part}）'


# ── Tree walker ───────────────────────────────────────────────────────

def walk_div_tree(div, toc_entries, body_lines, notes_map=None, level_offset=0):
    mulu_text = get_mulu_text(div)
    mulu_lv = get_mulu_level(div)
    heading, note_anchor = get_heading_text(div)

    heading = normalize_heading(heading)


    if not heading:
        div_type = div.get('type', '')
        for para in extract_paragraphs(div, notes_map):
            if div_type == 'orig':
                body_lines.append(f'> **{para}**')
            else:
                body_lines.append(para)
            body_lines.append('')
        for child in div:
            if child.tag == f'{{{CBETA_NS}}}div':
                walk_div_tree(child, toc_entries, body_lines, notes_map, level_offset)
        return

    if should_skip_div(mulu_text):
        return

    if mulu_lv == 1:
        for child in div:
            if child.tag == f'{{{CBETA_NS}}}div':
                walk_div_tree(child, toc_entries, body_lines, notes_map, level_offset)
        return

    # No anchors — pure plain text output

    effective_lv = mulu_lv + level_offset
    floor = 2 if level_offset < 0 else 3
    heading_level = '#' * min(6, max(floor, effective_lv))

    # Split appendix heading: "附：标题" → heading="附：" + subtitle line
    appendix_subtitle = None
    if (heading.startswith('附：') or heading.startswith('附\u3000')) and len(heading) > 2:
        appendix_subtitle = heading[2:]
        heading = '附：'
    elif heading.startswith('附') and len(heading) > 1 and _is_cjk(heading[1]):
        appendix_subtitle = heading[1:]
        heading = '附：'

   # TOC — plain Markdown nested list
    toc_indent = '    ' * max(0, mulu_lv - 3)
    toc_heading = f'{heading}{appendix_subtitle}' if appendix_subtitle else heading
    toc_entries.append(f'{toc_indent}- {toc_heading}')

   # Body heading — plain Markdown heading
    if heading != '前言':
        if heading_level == '##' and (not body_lines or body_lines[-1] != ''):
            body_lines.append('')
        body_lines.append('')
        indent = '\u3000\u3000' * max(0, effective_lv - floor)
        note_marker = ''
        if note_anchor and notes_map and note_anchor in notes_map:
            n = notes_map[note_anchor]
            note_marker = f' [{n}]'
        body_lines.append(f'{heading_level} {indent}{heading}{note_marker}')
        if appendix_subtitle:
            subtitle_level = "#"
            body_lines.append(f"{subtitle_level} {appendix_subtitle}")
        body_lines.append('')
    else:
        body_lines.append('')
   # Body paragraphs — flush-left, no indent
    for para in extract_paragraphs(div, notes_map):
        body_lines.append(para)
        body_lines.append('')

    recurse_offset = level_offset
    if appendix_subtitle:
        recurse_offset = -(mulu_lv - 1)

    # Recurse
    for child in div:
        if child.tag == f'{{{CBETA_NS}}}div':
            walk_div_tree(child, toc_entries, body_lines, notes_map, recurse_offset)


def extract_publication_notes(div):
    """Recursively extract publication notes from <byline><note place="inline"> elements.

    Walks the div tree, finds all byline elements that contain inline notes,
    and returns a list of unique, order-preserved note texts.
    """
    notes = []
    for child in div:
        local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if local_tag == 'byline':
            inline_note = child.find(f'{{{TEI_NS}}}note')
            if inline_note is None:
                inline_note = child.find('note')
            if inline_note is not None and inline_note.get('place') == 'inline':
                nt = ''.join(inline_note.itertext()).strip()
                nt = ''.join(nt.split())  # compress whitespace
                if nt and nt not in notes:
                    notes.append(nt)
        elif local_tag == 'div' or child.tag == f'{{{CBETA_NS}}}div':
            notes.extend(extract_publication_notes(child))
    # Deduplicate while preserving order
    seen = set()
    result = []
    for n in notes:
        if n not in seen:
            seen.add(n)
            result.append(n)
    return result


def render_frontmatter(title, publication_notes):
    """Render YAML frontmatter block for the output Markdown file.

    Always includes a 'title' field. The 'publication' field is a single string
    of original publication note texts and is omitted when empty.
    """
    def yaml_quote(s):
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    lines = ['---', f'title: {yaml_quote(title)}']
    if publication_notes:
        pub_str = '；'.join(publication_notes)
        lines.append(f'publication: {yaml_quote(pub_str)}')
    lines.append('---')
    return '\n'.join(lines)


# ── Main extract ──────────────────────────────────────────────────────

# ── TOC-only: shift-rule semantic labeling + JSON tree ───────────────

NUM_CJK = '一二三四五六七八九十百千'
GAN = '甲乙丙丁戊己庚辛壬癸'
ZHI = '子丑寅卯辰巳午未申酉戌亥'


def assign_semantic(heading, mulu_text, parent_semantic):
    """Assign semantic label (部/章/節/小節/小小節) via shift rule.

    Uses the detection algorithm from level_guide.md:
    1. Explicit patterns first (第X章 → 章, 第一節 → 節)
    2. Bare-numeral / stem patterns → context-dependent
    3. Unnumbered entries → parent context
    """
    # Explicit 第X章
    if re.match(rf'^第[{NUM_CJK}]+章', heading):
        return '章'
    # Explicit 第一節
    if re.match(rf'^第[{NUM_CJK}]+[節节]', heading):
        return '節'
    # Full-width digits (１、２…)
    if re.match(r'^[０１２３４５６７８９]+[　、．]', heading):
        return '小節'
    # Stem+numeral compound (甲一、乙二…)
    if re.match(rf'^[{GAN}][{NUM_CJK}]+', heading):
        if parent_semantic == '部':
            return '章'
        if parent_semantic == '章':
            return '節'
        if parent_semantic == '節':
            return '小節'
        if parent_semantic == '小節':
            return '小小節'
        return '節'
    # Bare heavenly stem (甲、乙…)
    if re.match(rf'^[{GAN}][　、]', heading):
        if parent_semantic == '章':
            return '節'
        if parent_semantic == '節':
            return '小節'
        if parent_semantic == '小節':
            return '小小節'
        return '節'
    # Bare earthly branch (子、丑…)
    if re.match(rf'^[{ZHI}][　、]', heading):
        if parent_semantic == '節':
            return '小節'
        return '小小節'
    # Bare CJK numeral (一、二、三…)
    if re.match(rf'^[{NUM_CJK}]+[　、]', heading):
        if parent_semantic == '部':
            return '章'
        if parent_semantic == '章':
            return '節'
        if parent_semantic == '節':
            return '小節'
        return '小節'

    # Unnumbered — fall back to parent context
    if parent_semantic == '篇':
        return '部'
    if parent_semantic == '部':
        return '章'
    if parent_semantic == '章':
        return '節'
    if parent_semantic == '節':
        return '小節'
    return '?'


def build_toc_json_tree(div, parent_semantic='篇', level_offset=0):
    """Walk a cb:div subtree and return a TOC tree as list of dict nodes.

    Mirrors walk_div_tree() logic (纲要 skip, level-1 pass-through,
    appendix offset) but produces nested JSON-ready structures.
    """
    nodes = []
    for child in div:
        if child.tag != f'{{{CBETA_NS}}}div':
            continue

        mulu_text = get_mulu_text(child)
        mulu_lv = get_mulu_level(child)
        heading, _note_anchor = get_heading_text(child)
        heading = normalize_heading(heading)

        # Empty heading — recurse for orig/commentary divs
        if not heading:
            children = build_toc_json_tree(child, parent_semantic, level_offset)
            nodes.extend(children)
            continue

        # Skip structural-only entries (纲要, 目次, 科分, etc.)
        if should_skip_div(mulu_text):
            continue

        # Level-1 (子目类别) — pass through, don't create a node
        if mulu_lv == 1:
            children = build_toc_json_tree(child, parent_semantic, level_offset)
            nodes.extend(children)
            continue

        # Appendix heading split
        appendix_subtitle = None
        node_label = heading
        if (heading.startswith('附：') or heading.startswith('附\u3000')) and len(heading) > 2:
            appendix_subtitle = heading[2:]
            node_label = '附：' + appendix_subtitle

        effective_lv = mulu_lv + level_offset
        semantic = assign_semantic(heading, mulu_text, parent_semantic)

        # Build child recursion with correct offset and parent context
        child_offset = level_offset
        if appendix_subtitle:
            child_offset = -(mulu_lv - 1)

        children = build_toc_json_tree(child, semantic, child_offset)

        n_attr = ''
        mulu_elem = child.find(f'{{{CBETA_NS}}}mulu')
        if mulu_elem is not None:
            n_attr = mulu_elem.get('n', '')

        nodes.append({
            'label': node_label,
            'level': effective_lv,
            'semantic': semantic,
            'n': n_attr,
            'children': children,
        })

    return nodes


def _flatten_toc_tree(nodes, depth=0):
    """Convert nested TOC tree nodes to flat '- ' Markdown lines."""
    lines = []
    indent = '    ' * depth
    for node in nodes:
        lines.append(f'{indent}- {node["label"]}')
        if node['children']:
            lines.extend(_flatten_toc_tree(node['children'], depth + 1))
    return lines


def _collect_skipped(article_div):
    """Collect names of 纲要-type divs that were skipped."""
    skipped = []
    for child in article_div:
        if child.tag != f'{{{CBETA_NS}}}div':
            continue
        mulu_text = get_mulu_text(child)
        if should_skip_div(mulu_text):
            skipped.append(mulu_text)
    return skipped
# ── Main extract ──────────────────────────────────────────────────────

def extract_article(xml_path, byte_start, byte_end, toc_only=False):
    root = parse_article_chunk(str(xml_path), byte_start, byte_end)

    article_div = None
    for div in root:
        if div.tag == f'{{{CBETA_NS}}}div':
            if get_mulu_level(div) == 2:
                article_div = div
                break

    if article_div is None:
        raise RuntimeError('Could not find article-level (level 2) cb:div')

    article_name = get_mulu_text(article_div)
    byline = get_byline_text(article_div)
    title_heading, title_note_anchor = get_heading_text(article_div)

    if toc_only:
        toc_tree = build_toc_json_tree(article_div, parent_semantic='篇')
        # Detect chart articles (no tree nodes)
        is_chart = len(toc_tree) == 0
        # Build flat toc entries from tree
        toc_entries = _flatten_toc_tree(toc_tree)
        skipped = _collect_skipped(article_div)
        return {
            'article_name': article_name,
            'byline': byline,
            'toc_tree': toc_tree,
            'toc_entries': toc_entries,
            'is_chart': is_chart,
            'skipped': skipped,
        }

    # Extract back-notes (篇末注) and build notes_map for in-text markers
    back_notes, note_anchor_order = extract_article_notes(
        str(xml_path), byte_start, byte_end)
    notes_map = {}
    for idx, aid in enumerate(note_anchor_order):
        notes_map[aid] = idx + 1

    toc_entries = []
    body_lines = []

    has_child_div = False
    for child in article_div:
        if child.tag == f'{{{CBETA_NS}}}div':
            has_child_div = True
            walk_div_tree(child, toc_entries, body_lines, notes_map, level_offset=-1)

    # Fallback: articles with no nested cb:div (e.g. charts, simple single-block articles)
    # have <p> / <figure> / <byline> as direct children of the article div
    if not has_child_div:
        body_lines.append('')
        for para in extract_paragraphs(article_div, notes_map):
            body_lines.append(para)
            body_lines.append('')

    # Detect chart articles (no toc entries, no body paragraphs)
    is_chart = len(toc_entries) == 0 and len(body_lines) == 0

    # Collect publication notes from <byline><note place="inline">
    pub_notes = extract_publication_notes(article_div)

    title_note = ''
    if title_note_anchor and title_note_anchor in notes_map:
        n = notes_map[title_note_anchor]
        title_note = f' [{n}]'
        
    md_lines = [f'# {article_name}{title_note}']
    if byline:
        md_lines.append(byline)

    # Appendix headers — shown right after the main title / byline
    appendixes = find_appendix_info(article_div)
    if appendixes:
        for app in appendixes:
            md_lines.append('')
            # Split "附：Title" → "### 附：" + "# Title"
            app_title = app["title"]
            if app_title.startswith('附：'):
                md_lines.append('### 附：')
                md_lines.append(f"# {app_title[2:]}")
            else:
                md_lines.append(f"### {app_title}")
            if app['date_location']:
                md_lines.append(app['date_location'])

    if toc_entries:
        md_lines.extend(['', '## 目錄', ''])
        md_lines.extend(toc_entries)
    md_lines.extend(body_lines)

    # Split trailing publication note （見...） from last paragraph
    # Also collect for frontmatter
    trailing_notes = []
    for _i in range(len(md_lines) - 1, -1, -1):
        if md_lines[_i].strip():
            _line = md_lines[_i]
            _m = re.search(r'。（見[^）]+）$', _line)
            if _m:
                _body = _line[:_m.start() + 1]
                _note = _line[_m.start() + 1:]
                md_lines[_i] = _body
                md_lines.insert(_i + 1, '')
                md_lines.insert(_i + 2, _note)
                trailing_notes.append(_note.strip('（）'))
            break

    # Merge byline publication notes with trailing notes, deduplicate
    publication_notes = []
    for n in pub_notes + trailing_notes:
        if n not in publication_notes:
            publication_notes.append(n)

    # Append back-notes section
    if back_notes:
        md_lines.extend(['', '## 註釋', ''])
        for idx, (num_label, note_text) in enumerate(back_notes):
            n = idx + 1
            md_lines.append(f'- [{n}]：{note_text}')

    if is_chart:
        md_lines.extend(['', '---', '',
            '**備註**：本文為圖表型文章，CBETA 原文為圖表/標記格式，'
            '建議查閱紙質版。'])

    md_lines = normalize_blank_lines(md_lines)

    # Count Chinese chars (excluding ## 目錄 section)
    toc_start = None
    toc_end = None
    for i, line in enumerate(md_lines):
        if line.startswith('## 目錄'):
            toc_start = i
        elif toc_start is not None and line.startswith('## '):
            toc_end = i
            break
    cjk_count = 0
    for i, line in enumerate(md_lines):
        if toc_start is not None and toc_start <= i < (toc_end or len(md_lines)):
            continue
        cjk_count += count_chinese_chars(line)


   # Ensure exactly 3 blank lines between TOC and body.
    # Find ## 目錄, then locate the last TOC entry and first body line structurally.
    toc_heading_idx = None
    for j, line in enumerate(md_lines):
        if line.startswith('## 目錄'):
            toc_heading_idx = j
            break
    if toc_heading_idx is not None:
        # Find the actual last TOC entry: lstrip starts with '- ' but not '- **'
        last_toc_idx = None
        for j in range(toc_heading_idx, len(md_lines)):
            s = md_lines[j].lstrip()
            if s.startswith('- ') and not s.startswith('- **'):
                last_toc_idx = j
            elif last_toc_idx is not None:
                stripped = md_lines[j].strip()
                if stripped.startswith('## ') or stripped.startswith('### '):
                    body_start_idx = j
                    break
                elif stripped and not s.startswith('- '):
                    body_start_idx = j
                    break
        else:
            body_start_idx = None
        if last_toc_idx is not None and body_start_idx is not None:
            blank_count = 0
            for j in range(last_toc_idx + 1, body_start_idx):
                if md_lines[j].strip() == '':
                    blank_count += 1
                else:
                    break
            if blank_count < 3:
                for _ in range(3 - blank_count):
                    md_lines.insert(body_start_idx, '')
    return {
        'article_name': article_name,
        'byline': byline,
        'markdown': '\n'.join(md_lines) + '\n',
        'appendixes': appendixes,
        'word_count': cjk_count,
        'publication_notes': publication_notes,
    }


# ── Catalog update ────────────────────────────────────────────────────

def regenerate_catalog_md(json_path):
    """Regenerate the MD catalog from the JSON catalog data."""
    NL = chr(10)
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    zi_mu_order = [zm['名稱'] for zm in data.get('子目', [])]
    zi_mu_map = {}
    for art in data.get('篇目鏈表', []):
        zm = art.get('子目', '')
        zi_mu_map.setdefault(zm, []).append(art)
    # Sort articles within each 子目 by 編號
    for arts in zi_mu_map.values():
        arts.sort(key=lambda a: a.get('編號', 0))

    book_name = data.get(chr(0x7f16), '')  # 编

    md_lines = [
        f"# {book_name} 篇名目錄",
        '',
        '## 篇目',
        '',
        f"- {book_name}",
    ]

    idx = 1
    for zm in zi_mu_order:
        arts = zi_mu_map.get(zm, [])
        md_lines.append(f'    - {idx}. {zm}')
        idx += 1
        for art in arts:
            article_line = f"        - {art['編號']}. {art['篇名']}"
            md_lines.append(article_line)

            for app in art.get('附文', []):
                app_line = f"            - 附：{app['標題']}"
                if app.get('時間地點'):
                    app_line += f' {app["時間地點"]}'
                md_lines.append(app_line)

    md_lines.extend([
        '',
        '## 篇數統計',
        '',
        '| 子目 | 篇數 |',
        '|------|------|',
    ])
    total = 0
    for zm in zi_mu_order:
        count = len(zi_mu_map.get(zm, []))
        total += count
        md_lines.append(f'| {zm} | {count} |')
    md_lines.append(f'| **合計** | **{total}** |')

    md_path = json_path.replace('.json', '.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(NL.join(md_lines) + NL)
    print(f'   📋 編目錄 MD 已更新 → {md_path}')

def update_catalog_with_appendixes(json_path, article_name, appendixes, skip_md=False):
    """Update catalog JSON and MD with appendix (附文) info for an article."""
    if not appendixes:
        return

    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    found = False
    for art in data.get('篇目鏈表', []):
        if art['篇名'] == article_name:
            # Build 附文 entries
            fu_wen = []
            for app in appendixes:
                entry = {'標題': re.sub(r'^附[：\u3000]*', '', app['title'])}
                if app.get('date_location'):
                    entry['時間地點'] = app['date_location']
                fu_wen.append(entry)
            art['附文'] = fu_wen
            found = True
            break

    if not found:
        print(f'   ⚠️  在編目錄中找不到文章「{article_name}」')
        return

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write(chr(10))
    print(f'   📋 編目錄 JSON 已更新 → {json_path}')

    if not skip_md:
        regenerate_catalog_md(json_path)

def update_catalog_with_word_count(json_path, article_name, word_count, skip_md=False):
    """Update catalog JSON with word count for an article, then regenerate MD."""
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    found = False
    for art in data.get('篇目鏈表', []):
        if art['篇名'] == article_name:
            art['字数'] = word_count
            found = True
            break

    if not found:
        print(f'   ⚠️  在編目錄中找不到文章「{article_name}」')
        return

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write(chr(10))
    print(f'   📋 編目錄字數已更新 → {json_path}')

    if not skip_md:
        regenerate_catalog_md(json_path)



def build_frontmatter(entry, book_name, book_number, publication_notes=None):
    """Build YAML frontmatter string from catalog entry.

    Args:
        entry: dict from catalog JSON 篇目鏈表 (must have 編號, 篇名, 子目, 題注, 字数)
        book_name: str like '第一编 佛法總學'
        book_number: int like 1
        publication_notes: list of str or None, publication/source notes from byline

    Returns: YAML frontmatter string including --- delimiters and trailing newline.
    """
    byline = entry.get('題注', '')
    fields = parse_byline_fields(byline)

    # Build YAML lines
    yaml_lines = ['---']
    yaml_lines.append(f"book: {book_name}")
    yaml_lines.append(f"book_number: {book_number}")
    yaml_lines.append(f"category: {entry.get('子目', '')}")
    yaml_lines.append(f"sequence: {entry.get('編號', 0)}")
    wc = entry.get('字数') or 0
    yaml_lines.append(f"word_count: {wc // 1000}")
    # parse_byline_fields always yields YYYY-MM (or ''), so no bare-year quoting needed
    yaml_lines.append(f"date: {fields['date']}")
    if publication_notes:
        def _yq(s):
            if '\n' in s or '"' in s or ':' in s and s[0] != ' ':
                return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
            return s
        pub_str = '；'.join(publication_notes)
        yaml_lines.append(f'publication: {_yq(pub_str)}')
    yaml_lines.append(f"location: {fields['location']}")
    yaml_lines.append('keywords:')
    yaml_lines.append('themes:')
    yaml_lines.append('---')
    yaml_lines.append('')  # blank line between frontmatter and body
    return '\n'.join(yaml_lines)



# ── CLI ───────────────────────────────────────────────────────────────

def main():
    global FIGURES_REL_PATH
    parser = argparse.ArgumentParser(
        description='Extract full article Markdown from CBETA TX XML')
    parser.add_argument('--catalog', help='Path to 编级 JSON catalog')
    parser.add_argument('--article', help='Article name (篇名) to extract')
    parser.add_argument('--file', help='CBETA XML filename')
    parser.add_argument('--byte-start', type=int)
    parser.add_argument('--byte-end', type=int)
    parser.add_argument('--data-dir', default='_data/cbeta/TX')
    parser.add_argument('--out-dir', help='Output directory')
    parser.add_argument('--toc-only', action='store_true', help='Output _目錄樹.md + _目錄.json only (no body text)')
    parser.add_argument('--figures-dir', default='_research/figures/TX',
                        help='Workspace-relative path to figures directory')
    parser.add_argument('--batch', action='store_true',
                        help='Batch mode: extract multiple consecutive articles')
    parser.add_argument('--子目', help='Sub-category name (for --batch)')
    parser.add_argument('--from', type=int, dest='from_article',
                        help='Starting 編號 (1-based, inclusive, for --batch)')
    parser.add_argument('--to', type=int, dest='to_article',
                        help='Ending 編號 (1-based, inclusive, for --batch)')
    args = parser.parse_args()

    if args.batch:
        if not args.catalog:
            parser.error('--batch requires --catalog')
        if not args.子目:
            parser.error('--batch requires --子目')
        if args.from_article is None or args.to_article is None:
            parser.error('--batch requires --from and --to')
        if args.from_article > args.to_article:
            parser.error('--from must be <= --to')

        with open(args.catalog, encoding='utf-8') as f:
            catalog = json.load(f)

        articles = [
            e for e in catalog['篇目鏈表']
            if e.get('子目') == args.子目
            and args.from_article <= e.get('編號', 0) <= args.to_article
        ]
        if not articles:
            print(f'❌ 在 子目="{args.子目}" 中找不到 編號 [{args.from_article}, {args.to_article}] 的文章')
            return 1
        articles.sort(key=lambda a: a.get('編號', 0))

        zi_mu_index = 0
        for i, zm in enumerate(catalog.get("子目", [])):
            if zm.get("名稱") == args.子目:
                zi_mu_index = i
                break
        sub_dir = f"{zi_mu_index+1:02d}_{args.子目}"
        out_dir = Path(args.catalog).parent / sub_dir

        figures_abs = Path(args.figures_dir).resolve()
        FIGURES_REL_PATH = os.path.relpath(str(figures_abs), str(out_dir.resolve()))

        # Build XML path cache (walk once)
        data_dir = Path(args.data_dir)
        xml_path_cache = {}
        for root_dir, _, files in os.walk(data_dir):
            for f in files:
                if f.endswith('.xml'):
                    xml_path_cache[f] = Path(root_dir) / f

        total = len(articles)
        success = 0
        first_error = True
        for i, entry in enumerate(articles):
            xml_file = entry['file']
            xml_path = xml_path_cache.get(xml_file)
            if xml_path is None:
                if first_error:
                    print()
                print(f'❌ [{i+1}/{total}] XML 文件 "{xml_file}" 找不到，跳過「{entry["篇名"]}」')
                first_error = False
                continue

            try:
                result = extract_article(str(xml_path), entry['byte_start'], entry['byte_end'], toc_only=args.toc_only)
            except Exception as e:
                if first_error:
                    print()
                print(f'❌ [{i+1}/{total}] 「{entry["篇名"]}」提取失敗: {e}')
                first_error = False
                continue

            zi_mu_num = entry['編號']
            zi_mu = entry.get('子目', '')

            if args.toc_only:
                out_dir.mkdir(parents=True, exist_ok=True)
                article_slug = result["article_name"]
                md_lines = [f'{article_slug}']
                if result['byline']:
                    md_lines.append(result['byline'])
                md_lines.extend(['', '## 目錄', ''])
                md_lines.extend(result['toc_entries'])
                notes = []
                if result.get('skipped'):
                    notes.append(f'「{"」「".join(result["skipped"])}」為全文結構綱要，已移除。')
                if result.get('is_chart'):
                    notes.append('本文為圖表型文章，CBETA 原文為圖表/標記格式，建議查閱紙質版。')
                if notes:
                    md_lines.extend(['', '**備註**：', ''])
                    for n in notes:
                        md_lines.append(f'- {n}')
                md_path = out_dir / f'{zi_mu_num:02d}_{article_slug}_目錄樹.md'
                md_path.write_text(chr(10).join(md_lines) + chr(10), encoding='utf-8')
                json_data = {
                    'article': article_slug,
                    'cbeta_id': xml_file,
                    '编': catalog.get('编', ''),
                    '子目': zi_mu,
                    '題注': result.get('byline', ''),
                    '処理': {
                        '綱要去掉': result.get('skipped', []),
                        '前言保留': False,
                    },
                    'tree': result['toc_tree'],
                }
                json_path = out_dir / f'{zi_mu_num:02d}_{article_slug}_目錄.json'
                json_path.write_text(
                    json.dumps(json_data, ensure_ascii=False, indent=2),
                    encoding='utf-8'
                )
                print(f'✅ [{i+1}/{total}] {article_slug} (目錄樹)')
            else:
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f'{zi_mu_num:02d}_{result["article_name"]}.md'
                entry['字数'] = result['word_count']
                fm = build_frontmatter(entry, catalog.get('编', ''), catalog.get('编序号', 0), result.get('publication_notes'))
                out_path.write_text(fm + result['markdown'], encoding='utf-8')

                if result.get("appendixes"):
                    update_catalog_with_appendixes(
                        args.catalog, result["article_name"], result["appendixes"], skip_md=True
                    )
                update_catalog_with_word_count(
                    args.catalog, result["article_name"], result["word_count"], skip_md=True
                )

                wc_qian = result['word_count'] // 1000
                print(f'✅ [{i+1}/{total}] {result["article_name"]}（{wc_qian} 千字）')

            success += 1
            first_error = True  # reset for next article

        if success > 0:
            regenerate_catalog_md(args.catalog)

        if success == total:
            print(f'\n🎉 全部完成：{success}/{total} 篇')
            return 0
        else:
            print(f'\n⚠️  部分完成：{success}/{total} 篇')
            return 1


    if args.catalog and args.article:
        with open(args.catalog, encoding='utf-8') as f:
            catalog = json.load(f)
        entry = None
        for e in catalog['篇目鏈表']:
            if e['篇名'] == args.article:
                entry = e
                break
        if entry is None:
            print(f'❌ Article "{args.article}" not found in catalog')
            return 1
        xml_file = entry['file']
        byte_start = entry['byte_start']
        byte_end = entry['byte_end']
        zi_mu = entry.get("子目", "")
        zi_mu_num = entry.get("編號", 0)
        # Find subdirectory index from 子目 array
        zi_mu_index = 0
        for i, zm in enumerate(catalog.get("子目", [])):
            if zm.get("名稱") == zi_mu:
                zi_mu_index = i
                break
        sub_dir = f"{zi_mu_index+1:02d}_{zi_mu}"
        out_dir = Path(args.catalog).parent / sub_dir
    elif args.file and args.byte_start is not None and args.byte_end is not None:
        xml_file = args.file
        byte_start = args.byte_start
        byte_end = args.byte_end
        zi_mu_num = 0
        out_dir = Path(args.out_dir) if args.out_dir else Path(".")
    else:
        parser.error('Need --catalog+--article or --file+--byte-start+--byte-end')

    figures_abs = Path(args.figures_dir).resolve()
    FIGURES_REL_PATH = os.path.relpath(str(figures_abs), str(out_dir.resolve()))

    data_dir = Path(args.data_dir)
    xml_path = None
    for root_dir, _, files in os.walk(data_dir):
        for f in files:
            if f == xml_file:
                xml_path = Path(root_dir) / f
                break
        if xml_path:
            break

    if xml_path is None:
        print(f'❌ XML file "{xml_file}" not found under {data_dir}')
        return 1

    # Single-article mode: wrap extraction so a malformed byte range or a
    # missing level-2 div surfaces a readable error instead of a raw
    # traceback (batch mode already does this per-article; pitfall #4/#20).
    try:
        result = extract_article(str(xml_path), byte_start, byte_end, toc_only=args.toc_only)
    except Exception as e:
        article_label = args.article if args.catalog else xml_file
        print(f'❌ 「{article_label}」提取失敗 '
              f'(byte {byte_start}–{byte_end}): {e}')
        return 1
    if args.toc_only:
        out_dir.mkdir(parents=True, exist_ok=True)
        article_slug = result["article_name"]
        # _目錄樹.md
        md_lines = [f'{article_slug}']
        if result['byline']:
            md_lines.append(result['byline'])
        md_lines.extend(['', '## 目錄', ''])
        md_lines.extend(result['toc_entries'])
        # 備註
        notes = []
        if result.get('skipped'):
            notes.append(f'「{"」「".join(result["skipped"])}」為全文結構綱要，已移除。')
        if result.get('is_chart'):
            notes.append('本文為圖表型文章，CBETA 原文為圖表/標記格式，建議查閱紙質版。')
        if notes:
            md_lines.extend(['', '**備註**：', ''])
            for n in notes:
                md_lines.append(f'- {n}')
        md_path = out_dir / f'{zi_mu_num:02d}_{article_slug}_目錄樹.md'
        md_path.write_text('\n'.join(md_lines) + '\n', encoding='utf-8')
        print(f'✅ 目錄樹 → {md_path}')
        # _目錄.json
        json_data = {
            'article': article_slug,
            'cbeta_id': xml_file,
            '编': catalog.get('编', '') if args.catalog else '',
            '子目': zi_mu,
            '題注': result.get('byline', ''),
            '処理': {
                '綱要去掉': result.get('skipped', []),
                '前言保留': False,
            },
            'tree': result['toc_tree'],
        }
        json_path = out_dir / f'{zi_mu_num:02d}_{article_slug}_目錄.json'
        json_path.write_text(
            json.dumps(json_data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        print(f'✅ 目錄JSON → {json_path}')
        print(f'   {article_slug}')
        if result['byline']:
            print(f'   {result["byline"]}')
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f'{zi_mu_num:02d}_{result["article_name"]}.md'
        if args.catalog:
            entry['字数'] = result['word_count']
        publication_notes = result.get('publication_notes', [])
        fm = build_frontmatter(entry, catalog.get('编', ''), catalog.get('编序号', 0), publication_notes) if args.catalog else ''
        if not args.catalog and publication_notes:
            fm = render_frontmatter(result['article_name'], publication_notes) + '\n'
        out_path.write_text(fm + result['markdown'], encoding='utf-8')

        # Update catalog with appendix info if found
        if args.catalog and result.get("appendixes"):
            update_catalog_with_appendixes(
                args.catalog, result["article_name"], result["appendixes"]
            )

        # Update catalog with word count
        if args.catalog:
            update_catalog_with_word_count(
                args.catalog, result["article_name"], result["word_count"]
            )

        print(f'✅ 全文 → {out_path}')
        print(f'   {result["article_name"]}')
        wc_qian = result['word_count'] // 1000
        print(f'   {wc_qian} 千字')
        if result['byline']:
            print(f'   {result["byline"]}')

if __name__ == '__main__':
    main()
