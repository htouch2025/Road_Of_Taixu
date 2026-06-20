#!/usr/bin/env python3
"""Extract a full article from CBETA TX XML as Markdown with TOC and body.

Two modes:
  1. --catalog + --article  → look up byte offsets from 编级 JSON
  2. --file + --byte-start + --byte-end  → direct byte-range extraction

Output: {篇名}.md with TOC ↔ body anchor links.

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
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

CBETA_NS = 'http://www.cbeta.org/ns/1.0'
TEI_NS = 'http://www.tei-c.org/ns/1.0'

# ── Chinese numeral utilities ─────────────────────────────────────────

CHINESE_NUM = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
}

def chinese_to_int(s):
    s = s.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    total = 0
    section = 0
    for c in s:
        if c == '十':
            total += (section or 1) * 10
            section = 0
        elif c in CHINESE_NUM:
            section = CHINESE_NUM[c]
        else:
            return None
    total += section
    return total if total > 0 else None

MONTH_MAP = {
    '正': 1, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '十一': 11, '十二': 12,
}
SEASONS = {'春', '夏', '秋', '冬'}

def split_month_season(rest):
    rest = rest.strip()
    if not rest:
        return '', ''
    m = re.match(r'(正|一|二|三|四|五|六|七|八|九|十[一二]?|[一二]?十[一二]?)月', rest)
    if m:
        mm = MONTH_MAP.get(m.group(1))
        if mm:
            return f'{mm} 月', rest[m.end():].strip()
    if rest[0] in SEASONS:
        return rest[0], rest[1:].strip()
    return '', rest

def build_suffix(month, rest):
    if month and rest:
        sep = '' if len(month) == 1 else ' '
        return f'{sep}{month}，{rest}'
    elif month:
        sep = '' if len(month) == 1 else ' '
        return f'{sep}{month}'
    elif rest:
        return f'，{rest}'
    return ''

def normalize_byline(raw):
    raw = raw.strip()
    if not raw:
        return ''
    raw = re.sub(r'^——+|——+$', '', raw).strip()
    if re.match(r'見海刊', raw):
        return ''
    m_rec = re.match(r'^（(.+記)）$', raw)
    if m_rec:
        return f'（{m_rec.group(1)}）'
    m = re.match(r'宣統(.+?)年(.*)', raw)
    if m:
        yr = chinese_to_int(m.group(1))
        if yr is not None:
            rest = m.group(2).strip()
            month, rest = split_month_season(rest)
            suffix = build_suffix(month, rest)
            return f'（{1908 + yr} 年{suffix}）'
    m = re.match(r'民國(.+?)年(.*)', raw)
    if m:
        yr = chinese_to_int(m.group(1))
        if yr is not None:
            rest = m.group(2).strip()
            month, rest = split_month_season(rest)
            suffix = build_suffix(month, rest)
            return f'（{1911 + yr} 年{suffix}）'
    m = re.match(r'(.+?)年(.*)', raw)
    if m:
        yr = chinese_to_int(m.group(1))
        if yr is not None and 1 <= yr <= 99:
            rest = m.group(2).strip()
            month, rest = split_month_season(rest)
            suffix = build_suffix(month, rest)
            return f'（{1911 + yr} 年{suffix}）'
    return f'（{raw}）'

# ── Anchor ID ─────────────────────────────────────────────────────────

CJK_RANGES = [
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3400, 0x4DBF),   # CJK Extension A
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
]

def _is_cjk(ch):
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in CJK_RANGES)

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
        rf'^([{NUM}]+)(?=[一-鿿])',
        r'\1' + '\u3000',
        heading
    )
    return heading

def make_anchor_id(heading_text):
    """Generate stable, Obsidian-compatible anchor ID from heading text via MD5 hash.

    Uses {#h-xxxxxx} custom anchor syntax that Obsidian natively supports.
    This bypasses auto-generation issues with fullwidth spaces (U+3000).
    """
    import hashlib
    # Clean: remove U+3000 and non-CJK/non-alnum for consistent hashing
    clean = heading_text.replace('\u3000', '')
    clean = ''.join(ch for ch in clean
                    if _is_cjk(ch) or (ch.isascii() and (ch.isalpha() or ch.isdigit())))
    hash_hex = hashlib.md5(clean.encode('utf-8')).hexdigest()[:6]
    return f'h-{hash_hex}'
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
    head = div.find(f"{{{TEI_NS}}}head") or div.find("head")
    note_anchor = None
    if head is not None:
        # Check for nkr_note_orig anchor inside head
        anchor = head.find(f"{{{TEI_NS}}}anchor") or head.find("anchor")
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
    byline = div.find(f'{{{TEI_NS}}}byline') or div.find('byline')
    if byline is not None:
        raw = ''.join(byline.itertext()).strip()
        return normalize_byline(raw)
    return ''

def should_skip_div(mulu_text):
    for kw in ['目次', '綱要', '目錄', '目録', '科分']:
        if kw in mulu_text:
            return True
    return False

def render_paragraph(p_elem, notes_map=None, heading_anchor=None, note_backrefs=None):
    """Render <p> to text, notes → （...）, lb/pb discarded, note anchors → [N]."""
    parts = []

    def walk(node):
        if node.text:
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
                    if note_backrefs is not None and heading_anchor:
                        note_backrefs[n] = heading_anchor
                    parts.append(f' [[#^n-{n}|〔{n}〕]]')
                parts.append(f' ^fn-body-{n}')
            elif tag in ('lb', 'pb'):
                pass
            elif tag in ('byline', 'head'):
                pass
            else:
                parts.append(''.join(child.itertext()))
            if child.tail:
                parts.append(child.tail)

    walk(p_elem)
    text = ''.join(parts)
    text = ''.join(text.split())
    return text
def _is_tei_tag(tag, name):
    return tag == f'{{{TEI_NS}}}{name}' or tag == name

def extract_paragraphs(div, notes_map=None, heading_anchor=None, note_backrefs=None):
    out = []
    for child in div:
        if _is_tei_tag(child.tag, 'p'):
            text = render_paragraph(child, notes_map, heading_anchor, note_backrefs)
            if text.strip():
                out.append(text)
    return out


# ── Back-note extraction ─────────────────────────────────────────────

def extract_article_notes(full_xml_path, article_byte_start, article_byte_end):
    """Find <note> elements in <back> that target anchors inside the article.

    Returns list of (note_n, anchor_id, note_text) sorted by anchor position.
    """
    import re as _re
    with open(full_xml_path, 'rb') as f:
        f.seek(article_byte_start)
        article_chunk = f.read(article_byte_end - article_byte_start).decode('utf-8', errors='replace')

    # Collect all nkr_note_orig_* anchor IDs from the article, in order
    anchor_ids = _re.findall(r'anchor xml:id="(nkr_note_orig_\d+)"', article_chunk)
    if not anchor_ids:
        return [], []

    # Read the <back> section from the full file
    with open(full_xml_path, 'r', encoding='utf-8') as f:
        full_text = f.read()

    back_match = _re.search(r'<back>.*?</back>', full_text, _re.DOTALL)
    if not back_match:
        return [], []

    back_text = back_match.group()
    notes = []
    note_pattern = _re.compile(
        r'<note n="(\d+)"[^>]*target="#(nkr_note_orig_\d+)"[^>]*>(.*?)</note>',
        _re.DOTALL
    )
    note_map = {}
    for m in note_pattern.finditer(back_text):
        note_map[m.group(2)] = (int(m.group(1)), m.group(3))

    # Build ordered list matching anchor order in article
    CHINESE_NUMERALS = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
    for idx, aid in enumerate(anchor_ids):
        if aid in note_map:
            note_n, raw_body = note_map[aid]
            body = _re.sub(r'<[^>]+>', '', raw_body).strip()
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
        head = child.find(f'{{{TEI_NS}}}head') or child.find('head')
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

def walk_div_tree(div, toc_entries, body_lines, notes_map=None, note_backrefs=None, level_offset=0):
    mulu_text = get_mulu_text(div)
    mulu_lv = get_mulu_level(div)
    heading, note_anchor = get_heading_text(div)

    heading = normalize_heading(heading)


    if not heading:
        div_type = div.get('type', '')
        for para in extract_paragraphs(div, notes_map, None, note_backrefs):
            if div_type == 'orig':
                body_lines.append(f'> **{para}**')
            else:
                body_lines.append(para)
            body_lines.append('')
        for child in div:
            if child.tag == f'{{{CBETA_NS}}}div':
                walk_div_tree(child, toc_entries, body_lines, notes_map, note_backrefs, level_offset)
        return

    if should_skip_div(mulu_text):
        return

    if mulu_lv == 1:
        for child in div:
            if child.tag == f'{{{CBETA_NS}}}div':
                walk_div_tree(child, toc_entries, body_lines, notes_map, note_backrefs, level_offset)
        return

    # No anchors — pure plain text output

    effective_lv = mulu_lv + level_offset
    floor = 2 if level_offset < 0 else 3
    heading_level = '#' * max(floor, effective_lv)

    # Split appendix heading: "附：标题" → heading="附：" + subtitle line
    appendix_subtitle = None
    if (heading.startswith('附：') or heading.startswith('附\u3000')) and len(heading) > 2:
        appendix_subtitle = heading[2:]
        heading = '附：'
    elif heading.startswith('附') and len(heading) > 1 and _is_cjk(heading[1]):
        appendix_subtitle = heading[1:]
        heading = '附：'

    # TOC — link via Obsidian block reference [[#^anchor-id|heading]]
    toc_indent = '    ' * max(0, mulu_lv - 3)
    toc_heading = f'{heading}{appendix_subtitle}' if appendix_subtitle else heading
    toc_entries.append(f'{toc_indent}- {toc_heading}')

    # Body heading — Obsidian block reference ^anchor (hidden in reading view)
    body_lines.append('')
    indent = '\u3000\u3000' * max(0, effective_lv - floor)
    note_marker = ''
    if note_anchor and notes_map and note_anchor in notes_map:
        n = notes_map[note_anchor]
        note_marker = f' {n}'
    body_lines.append(f'{heading_level} {indent}{heading}{note_marker}')
    if appendix_subtitle:
        subtitle_level = "#"
        body_lines.append(f"{subtitle_level} {appendix_subtitle}")
    body_lines.append('')

    # Body paragraphs — flush-left, no indent (Obsidian-compatible)
    for para in extract_paragraphs(div, notes_map, None, note_backrefs):
        body_lines.append(para)
        body_lines.append('')

    recurse_offset = level_offset
    if appendix_subtitle:
        recurse_offset = -(mulu_lv - 1)

    # Recurse
    for child in div:
        if child.tag == f'{{{CBETA_NS}}}div':
            walk_div_tree(child, toc_entries, body_lines, notes_map, note_backrefs, recurse_offset)

# ── Main extract ──────────────────────────────────────────────────────

def extract_article(xml_path, byte_start, byte_end):
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

    # Get article title heading and its note anchor
    title_heading, title_note_anchor = get_heading_text(article_div)

    # Extract back-notes (篇末注) and build notes_map for in-text markers
    back_notes, note_anchor_order = extract_article_notes(
        str(xml_path), byte_start, byte_end)
    notes_map = {}
    for idx, aid in enumerate(note_anchor_order):
        notes_map[aid] = idx + 1

    toc_entries = []
    body_lines = []

    note_backrefs = {}

    for child in article_div:
        if child.tag == f'{{{CBETA_NS}}}div':
            walk_div_tree(child, toc_entries, body_lines, notes_map, note_backrefs)

    # Detect chart articles (no toc entries, no body paragraphs)
    is_chart = len(toc_entries) == 0 and len(body_lines) == 0

    title_note = ''
    if title_note_anchor and title_note_anchor in notes_map:
        n = notes_map[title_note_anchor]
        title_note = f' {n}'
        
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

    md_lines.extend(['', '## 目錄', ''])
    md_lines.extend(toc_entries)
    md_lines.extend(['', '## 正文'])
    md_lines.extend(body_lines)

    # Append back-notes section
    if back_notes:
        md_lines.extend(['', '## 註釋', ''])
        for idx, (num_label, note_text) in enumerate(back_notes):
            n = idx + 1
            md_lines.append(f'- **{n}**：{note_text}')

    if is_chart:
        md_lines.extend(['', '---', '',
            '**備註**：本文為圖表型文章，CBETA 原文為圖表/標記格式，'
            '建議查閱紙質版。'])

    return {
        'article_name': article_name,
        'byline': byline,
        'markdown': '\n'.join(md_lines) + '\n',
        'appendixes': appendixes,
    }


# ── Catalog update ────────────────────────────────────────────────────

def regenerate_catalog_md(json_path):
    """Regenerate the MD catalog from the JSON catalog data."""
    NL = chr(10)
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    articles = sorted(data.get('篇目鏈表', []),
                      key=lambda a: (a.get('子目', ''), a.get('子目內編號', 0)))
    zi_mu_order = []
    zi_mu_map = {}
    for art in articles:
        zm = art.get('子目', '')
        if zm not in zi_mu_map:
            zi_mu_map[zm] = []
            zi_mu_order.append(zm)
        zi_mu_map[zm].append(art)

    bian_name = data.get(chr(0x7f16), '')  # 编

    md_lines = [
        f"# {bian_name} 篇名目錄",
        '',
        '## 篇目',
        '',
        f"- {bian_name}",
    ]

    idx = 1
    for zm in zi_mu_order:
        arts = zi_mu_map[zm]
        md_lines.append(f'    - {idx}. {zm}')
        idx += 1
        for art in arts:
            article_line = f"        - {art['子目內編號']}. {art['篇名']}"
            if art.get('題注'):
                article_line += f' {art["題注"]}'
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
        count = len(zi_mu_map[zm])
        total += count
        md_lines.append(f'| {zm} | {count} |')
    md_lines.append(f'| **合計** | **{total}** |')

    md_path = json_path.replace('.json', '.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(NL.join(md_lines) + NL)
    print(f'   📋 編目錄 MD 已更新 → {md_path}')

def update_catalog_with_appendixes(json_path, article_name, appendixes):
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

    regenerate_catalog_md(json_path)


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Extract full article Markdown from CBETA TX XML')
    parser.add_argument('--catalog', help='Path to 编级 JSON catalog')
    parser.add_argument('--article', help='Article name (篇名) to extract')
    parser.add_argument('--file', help='CBETA XML filename')
    parser.add_argument('--byte-start', type=int)
    parser.add_argument('--byte-end', type=int)
    parser.add_argument('--data-dir', default='_data/cbeta/TX')
    parser.add_argument('--out-dir', help='Output directory')
    args = parser.parse_args()

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
        zi_mu_num = entry.get("子目內編號", 0)
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

    data_dir = Path(args.data_dir)
    xml_path = None
    for root_dir, _, files in Path(data_dir).walk():
        for f in files:
            if f == xml_file:
                xml_path = root_dir / f
                break
        if xml_path:
            break

    if xml_path is None:
        print(f'❌ XML file "{xml_file}" not found under {data_dir}')
        return 1

    result = extract_article(str(xml_path), byte_start, byte_end)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'{zi_mu_num:02d}_{result["article_name"]}.md'
    out_path.write_text(result['markdown'], encoding='utf-8')

    # Update catalog with appendix info if found
    if args.catalog and result.get("appendixes"):
        update_catalog_with_appendixes(
            args.catalog, result["article_name"], result["appendixes"]
        )

    print(f'✅ 全文 → {out_path}')
    print(f'   {result["article_name"]}')
    if result['byline']:
        print(f'   {result["byline"]}')
    print(f'   {len(result["markdown"])} 字符')

if __name__ == '__main__':
    main()
