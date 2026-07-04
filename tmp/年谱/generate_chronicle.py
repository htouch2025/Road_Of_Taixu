#!/usr/bin/env python3
"""
解析 Y13n0013_001.xml + Y13n0013_002.xml（太虚大师年谱），
生成：
  1. 太虚大师年谱.md  — 完整 Markdown 年谱
  2. 太虚大师年谱.json — 结构化数据，含丰富分类信息，便于动态调用
"""
import xml.etree.ElementTree as ET
import json
import re
import os
from datetime import datetime
from collections import OrderedDict

CB_NS = 'http://www.cbeta.org/ns/1.0'
DATA_DIR = '/Users/xin/Documents/Road_Of_Taixu/_data/cbeta/YS'
OUT_DIR = '/Users/xin/Documents/Road_Of_Taixu/tmp/年谱'

# ─── helpers ───────────────────────────────────────────────────

def tag_local(elem):
    """Return local tag name without namespace."""
    t = elem.tag
    return t.split('}', 1)[1] if '}' in t else t

def iter_cb_divs(parent, ns={'cb': CB_NS}):
    """Yield all cb:div descendants of parent in document order."""
    for div in parent.iter(f'{{{CB_NS}}}div'):
        yield div

def get_text_content(elem, ns={'cb': CB_NS}):
    """Extract clean text from an element, stripping lb/pb tags and normalising whitespace."""
    parts = []
    _collect_text(elem, parts, ns)
    text = ''.join(parts)
    # Normalise whitespace but preserve paragraph boundaries
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.strip()
    return text

def _collect_text(elem, parts, ns):
    """Recursively collect text, inserting newlines at block boundaries."""
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        local = tag_local(child)
        if local in ('lb', 'pb', 'milestone'):
            # skip line breaks / page breaks - just add space
            parts.append(' ')
        elif local == 'p':
            parts.append('\n\n')
            _collect_text(child, parts, ns)
            parts.append('\n\n')
        elif local == 'head':
            parts.append('\n\n### ')
            _collect_text(child, parts, ns)
            parts.append('\n\n')
        elif local == 'byline':
            parts.append('\n\n*— ')
            _collect_text(child, parts, ns)
            parts.append('*\n\n')
        elif local == 'quote':
            parts.append('\n\n> ')
            _collect_text(child, parts, ns)
            parts.append('\n\n')
        elif local == 'list':
            _collect_text(child, parts, ns)
        elif local == 'item':
            parts.append('\n- ')
            _collect_text(child, parts, ns)
        elif local == 'table':
            parts.append('\n\n')
            _collect_text(child, parts, ns)
            parts.append('\n\n')
        elif local == 'row':
            parts.append('\n| ')
            for cell in child:
                _collect_text(cell, parts, ns)
                parts.append(' | ')
        elif local == 'bibl':
            _collect_text(child, parts, ns)
        elif local == 'hi':
            rend = child.get('rend', '')
            if 'bold' in rend:
                parts.append('**')
                _collect_text(child, parts, ns)
                parts.append('**')
            else:
                _collect_text(child, parts, ns)
        elif local == 'persName':
            _collect_text(child, parts, ns)
        elif local == 'name':
            _collect_text(child, parts, ns)
        elif local == 'title':
            parts.append('《')
            _collect_text(child, parts, ns)
            parts.append('》')
        elif local == 'biblScope':
            parts.append('（')
            _collect_text(child, parts, ns)
            parts.append('）')
        else:
            _collect_text(child, parts, ns)
        if child.tail:
            parts.append(child.tail)

def strip_elements(elem, tags_to_strip, ns={'cb': CB_NS}):
    """Remove specified elements (by local tag name) from elem in-place."""
    to_remove = []
    for child in elem:
        if tag_local(child) in tags_to_strip:
            to_remove.append(child)
    for child in to_remove:
        elem.remove(child)
    for child in elem:
        strip_elements(child, tags_to_strip, ns)

# ─── header metadata ───────────────────────────────────────────

def extract_header_meta(xml_path_001):
    """Extract metadata from teiHeader of 001 file."""
    tree = ET.parse(xml_path_001)
    root = tree.getroot()
    ns = {'cb': CB_NS}

    meta = {}
    # Find teiHeader
    header = root.find('teiHeader')
    if header is None:
        return meta

    file_desc = header.find('fileDesc')
    if file_desc is not None:
        title_stmt = file_desc.find('titleStmt')
        if title_stmt is not None:
            titles = title_stmt.findall('title')
            for t in titles:
                meta.setdefault('titles', []).append(t.text.strip() if t.text else '')
            author = title_stmt.find('author')
            if author is not None and author.text:
                meta['author'] = author.text.strip()

        edition_stmt = file_desc.find('editionStmt')
        if edition_stmt is not None:
            edition = edition_stmt.find('edition')
            if edition is not None and edition.text:
                meta['edition'] = edition.text.strip()

        extent = file_desc.find('extent')
        if extent is not None and extent.text:
            meta['extent'] = extent.text.strip()

        publication_stmt = file_desc.find('publicationStmt')
        if publication_stmt is not None:
            date_el = publication_stmt.find('date')
            if date_el is not None and date_el.text:
                meta['publication_date'] = date_el.text.strip()
            idno = publication_stmt.find('idno')
            if idno is not None:
                meta['cbeta_id'] = {}
                for child in idno.findall('idno'):
                    typ = child.get('type', '')
                    meta['cbeta_id'][typ] = child.text.strip() if child.text else ''

        source_desc = file_desc.find('sourceDesc')
        if source_desc is not None:
            bibl = source_desc.find('bibl')
            if bibl is not None:
                for t in bibl.findall('title'):
                    level = t.get('level', '')
                    if t.text:
                        meta.setdefault('source', {})[level] = t.text.strip()

    return meta

# ─── parse 001 (preface + editor notes) ────────────────────────

def parse_001(xml_path):
    """Parse 001 file: 序 and 编者附言."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    ns = {'cb': CB_NS}

    sections = []
    for div in iter_cb_divs(root):
        div_type = div.get('type', '')
        if div_type not in ('other',):
            continue

        mulu_el = div.find('cb:mulu', ns)
        head_el = div.find('head')
        title = None
        if head_el is not None:
            title = get_text_content(head_el)
        elif mulu_el is not None:
            title = mulu_el.text.strip() if mulu_el.text else None

        # strip lb/pb for clean text extraction
        content = get_text_content(div)

        sections.append({
            'type': div_type,
            'title': title,
            'content': content,
        })

    return sections

# ─── parse 002 (main chronicle) ────────────────────────────────

def parse_year_entry(div, ns):
    """Parse a single year's cb:div into structured data.

    The div has:
    - cb:mulu level="2" as the year heading
    - Multiple child cb:mulu elements for sub-sections (months/events)
    - p, quote, table children with the actual content
    """
    mulu_el = div.find('cb:mulu', ns)
    head_el = div.find('head')
    year_title = None
    if head_el is not None:
        year_title = get_text_content(head_el)
    elif mulu_el is not None and mulu_el.text:
        year_title = mulu_el.text.strip()

    # Parse year info from the title
    year_info = parse_year_title(year_title) if year_title else {}

    # Extract child cb:mulu items and their associated text blocks
    events = []
    current_event = None
    waiting_for_content = False

    for child in div:
        local = tag_local(child)

        if local == 'mulu':
            # New sub-heading → save previous event, start new one
            if current_event and current_event.get('content', '').strip():
                events.append(current_event)
            elif current_event and waiting_for_content:
                events.append(current_event)

            sub_title = child.text.strip() if child.text else ''
            current_event = {
                'type': 'heading',
                'title': sub_title,
                'content': '',
                'raw_text': '',
            }
            waiting_for_content = True

        elif local in ('p', 'quote', 'table'):
            if current_event is None:
                current_event = {
                    'type': 'content',
                    'title': '',
                    'content': '',
                    'raw_text': '',
                }

            # Extract clean text
            text = get_text_content(child)
            local_text = _extract_local_text(child)

            if local == 'quote':
                current_event['content'] += f'\n\n> {text}\n\n'
                current_event['raw_text'] += f'\n[引文]\n{text}\n[/引文]\n'
            elif local == 'table':
                current_event['content'] += f'\n\n{text}\n\n'
                current_event['raw_text'] += f'\n[表格]\n{text}\n[/表格]\n'
            else:
                current_event['content'] += text + '\n\n'
                current_event['raw_text'] += text + '\n\n'

            waiting_for_content = False

        elif local == 'pb':
            # Just note page breaks for reference
            if current_event:
                n = child.get('n', '')
                current_event['raw_text'] += f'[{n}]'

    # Don't forget the last event
    if current_event and (current_event.get('content', '').strip() or waiting_for_content):
        events.append(current_event)

    # Merge consecutive heading-only events (empty content) with next event
    merged = []
    pending_headings = []
    for ev in events:
        content = ev.get('content', '').strip()
        if not content and ev.get('type') == 'heading' and ev.get('title'):
            pending_headings.append(ev['title'])
        else:
            if pending_headings:
                # Prepend headings as context
                ev['subtitles'] = list(pending_headings)
                pending_headings = []
            merged.append(ev)
    # Remaining headings with no content
    for h in pending_headings:
        merged.append({'type': 'heading_only', 'title': h, 'content': '', 'raw_text': ''})

    return {
        'year_title': year_title,
        'year_info': year_info,
        'events': merged,
    }


def _extract_local_text(elem):
    """Get direct text of element without child markup."""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        parts.append(child.text or '')
        if child.tail:
            parts.append(child.tail)
    return ''.join(parts)


# Chinese numeral helpers
_CN_DIGITS = {'〇': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
              '零': 0, '１': 1, '２': 2, '３': 3, '４': 4, '５': 5, '６': 6, '７': 7, '８': 8, '９': 9,
              '○': 0, '０': 0}
_CN_UNITS = {'十': 10, '百': 100, '千': 1000, '萬': 10000, '万': 10000}

def cnum_to_int(s):
    """Convert Chinese numeral string to integer.
    Handles: '一八八九' → 1889, '十五' → 15, '一九五〇' → 1950, '元年' → 1
    Returns None if cannot parse.
    """
    if not s:
        return None
    if s in ('元年', '元'):
        return 1
    # If already arabic digits
    if re.match(r'^\d+$', s):
        return int(s)

    # Sequential digits (year format): '一八八九' → 1889
    if all(ch in _CN_DIGITS for ch in s):
        result = 0
        for ch in s:
            result = result * 10 + _CN_DIGITS[ch]
        return result

    # Number with unit: '十五' → 15, '三十九' → 39
    # Pattern: ([digit]unit)+ [digit]?
    val = 0
    tmp = 0
    for ch in s:
        if ch in _CN_DIGITS:
            tmp = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            unit = _CN_UNITS[ch]
            if tmp == 0:
                tmp = 1
            tmp *= unit
            if unit >= 10:
                val += tmp
                tmp = 0
        else:
            return None
    val += tmp
    return val if val > 0 else None


def parse_year_title(title):
    """Parse the year title string into structured year info.

    Examples:
    - "淸光緖十五年，己丑（一八八九⸺一八九〇），大师生。"
    - "中华民国元年，一九一二（辛亥⸺壬子），大师二十四岁。"
    - "民国三十九年，一九五〇（己亥⸺庚子）。"
    """
    info = {
        'raw': title,
        'dynasty': None,
        'era': None,
        'era_year': None,
        'sexagenary': None,
        'western_start': None,
        'western_end': None,
        'rocs_year': None,  # 民国纪年
        'master_age': None,
        'is_birth': False,
        'is_posthumous': False,  # 身后年份
    }

    if not title:
        return info

    # Check eras
    if '淸' in title or '清' in title or '光緖' in title or '光緒' in title:
        info['dynasty'] = '清'
        info['era'] = '光緒'
    elif '宣统' in title or '宣統' in title:
        info['dynasty'] = '清'
        info['era'] = '宣統'
    elif '中华民国' in title or '民國' in title or '民国' in title:
        info['era'] = '民國'

    # Extract western years: handle both Arabic and Chinese numerals
    # Pattern 1: （一八八九⸺一八九〇） or （1919⸺1920）
    western_match = re.search(r'[（(]([〇一二三四五六七八九○\d]{4})[\s⸺⸺\-\–]+([〇一二三四五六七八九○\d]{4})[）)]', title)
    if western_match:
        info['western_start'] = cnum_to_int(western_match.group(1))
        info['western_end'] = cnum_to_int(western_match.group(2))

    # Pattern 2: ，一九一九（戊午...） — western year before （sexagenary）
    if info['western_start'] is None:
        w2_match = re.search(r'[，,]\s*([〇一二三四五六七八九○\d]{4})\s*[（(]', title)
        if w2_match:
            yr = cnum_to_int(w2_match.group(1))
            info['western_start'] = yr
            info['western_end'] = yr + 1

    # Extract sexagenary cycle
    sexa_match = re.search(r'[（(]([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])[\s⸺⸺\-\–]+([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])[）)]', title)
    if sexa_match:
        info['sexagenary'] = f'{sexa_match.group(1)}→{sexa_match.group(2)}'
    else:
        # Try comma-separated: "己丑（"
        sexa_match2 = re.search(r'[，,]\s*([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])', title)
        if sexa_match2:
            info['sexagenary'] = sexa_match2.group(1)

    # Extract age (handle Chinese numerals with units): "大师二十四岁" or "大师二岁"
    _CN_NUM_CHARS = r'[〇一二三四五六七八九○十百千万\d]+'
    age_match = re.search(r'大师(' + _CN_NUM_CHARS + r')岁', title)
    if age_match:
        info['master_age'] = cnum_to_int(age_match.group(1))

    # Check if birth year
    if '大师生' in title or '诞生' in title:
        info['is_birth'] = True
        info['master_age'] = 0

    # Check if posthumous (no master mentioned in title after 1947)
    if info['western_start'] and info['western_start'] >= 1948:
        info['is_posthumous'] = True

    # ROC year: "民国八年" → 8, "民国三十九年" → 39
    roc_match = re.search(r'民国(' + _CN_NUM_CHARS + r')年', title)
    if roc_match:
        info['rocs_year'] = cnum_to_int(roc_match.group(1))
    # Handle "中华民国元年"
    if not info.get('rocs_year') and '元年' in title and info.get('era') == '民國':
        info['rocs_year'] = 1

    # Era year: "光緒十五年" → 15, "宣統元年" → 1
    _ERA_NUM_CHARS = r'[〇一二三四五六七八九○十百千万\d元]+'
    if info['era'] == '光緒':
        era_match = re.search(r'光緖(' + _ERA_NUM_CHARS + r')年', title)
        if era_match:
            info['era_year'] = cnum_to_int(era_match.group(1))
    elif info['era'] == '宣統':
        era_match = re.search(r'宣统(' + _ERA_NUM_CHARS + r')年', title)
        if era_match:
            info['era_year'] = cnum_to_int(era_match.group(1))

    return info


def parse_002_biographical(xml_path):
    """Parse 002 file: biographical details (名号/籍贯/年龄/眷属) + chronicle."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    ns = {'cb': CB_NS}

    # Find the two main cb:div sections in body
    # They're inside text/body
    text = root.find('text')
    body = text.find('body') if text is not None else None
    if body is None:
        return None

    bio_section = None
    chronicle_section = None

    # The two main cb:div are direct-ish children of body
    # body has: [mulu milestone=2], pb, pb, lb, lb, cb:div(bio), pb, pb, lb, lb, cb:div(chronicle)
    all_divs = body.findall(f'{{{CB_NS}}}div')

    for div in all_divs:
        div_type = div.get('type', '')
        mulu_el = div.find('cb:mulu', ns)
        mulu_text = mulu_el.text.strip() if mulu_el is not None and mulu_el.text else ''

        if '名号' in mulu_text or '籍贯' in mulu_text or '年龄' in mulu_text or '眷属' in mulu_text:
            bio_section = div
        elif '年谱' in mulu_text or '年譜' in mulu_text:
            chronicle_section = div

    # ── Parse biographical section ──
    bio_data = {}
    if bio_section is not None:
        sub_divs = bio_section.findall(f'{{{CB_NS}}}div')
        for sd in sub_divs:
            sd_mulu = sd.find('cb:mulu', ns)
            sd_head = sd.find('head')
            key = get_text_content(sd_head) if sd_head is not None else (
                sd_mulu.text.strip() if sd_mulu is not None and sd_mulu.text else '')
            content = get_text_content(sd)
            bio_data[key] = content

    # ── Parse chronicle section (year entries) ──
    years = []
    if chronicle_section is not None:
        year_divs = chronicle_section.findall(f'{{{CB_NS}}}div')
        for yd in year_divs:
            year_entry = parse_year_entry(yd, ns)
            years.append(year_entry)

    return {
        'biographical': bio_data,
        'years': years,
    }


# ─── entity extraction ─────────────────────────────────────────

def extract_entities_from_text(text):
    """Extract mentions of people, places, works, etc. from text."""
    entities = {
        'people': [],
        'places': [],
        'works': [],
        'organizations': [],
        'dates': [],
    }

    # Book titles: 《...》
    book_pattern = re.findall(r'《([^》]+)》', text)
    entities['works'] = list(set(book_pattern))

    # Journal volumes: 海…卷…期 style
    journal_pattern = re.findall(r'((?:海潮音|覺書|覺社叢書|海)\s*(?:\d+[卷期])?)', text)
    # Simplified - this is hard to get perfect

    # Place names - common patterns
    place_keywords = [
        '南京', '北京', '上海', '重慶', '武漢', '漢口', '武昌', '漢陽',
        '廣州', '成都', '杭州', '寧波', '廈門', '福州', '西安', '長安',
        '奉化', '普陀', '九華', '五台', '峨眉', '天童', '育王', '雪竇',
        '縉雲', '漢藏', '重慶', '縉雲山', '北碚', '漢藏教理院',
        '日本', '東京', '神戶', '高野山',
        '南洋', '新加坡', '檳城', '仰光', '曼谷', '錫蘭', '科倫坡',
        '印度', '菩提伽耶', '加爾各答',
        '法國', '巴黎', '英國', '倫敦', '德國', '柏林',
        '美國', '紐約', '華盛頓', '三藩市', '芝加哥',
        '緬甸', '泰國', '斯里蘭卡', '西藏', '蒙古',
        '香港', '澳門', '臺灣', '台灣',
    ]
    for place in place_keywords:
        if place in text:
            entities['places'].append(place)
    entities['places'] = list(set(entities['places']))

    # Organizations
    org_keywords = [
        '佛教會', '佛學院', '佛教協進會', '覺社', '世界佛教聯合會',
        '中國佛教會', '中華佛教總會', '世界佛學苑', '漢藏教理院',
        '閩南佛學院', '武昌佛學院', '內學院', '支那內學院',
        '海潮音', '正信', '佛化新青年', '佛青',
        '國民黨', '同盟會', '臨時政府',
        '泰東圖書局', '正聞出版社',
    ]
    for org in org_keywords:
        if org in text:
            entities['organizations'].append(org)
    entities['organizations'] = list(set(entities['organizations']))

    return entities


def classify_year_events(events, year_info):
    """Given a year's events, classify into thematic categories."""
    categories = []
    full_text = ' '.join(e.get('content', '') + ' ' + e.get('title', '') for e in events)

    # Classification keywords
    if any(kw in full_text for kw in ['出家', '受戒', '剃度', '披剃']):
        categories.append('出家受戒')
    if any(kw in full_text for kw in ['講經', '講學', '講座', '演講', '講演', '說法', '開示']):
        categories.append('講經說法')
    if any(kw in full_text for kw in ['創辦', '創立', '成立', '開辦', '設立', '組織']):
        categories.append('創辦組織')
    if any(kw in full_text for kw in ['佛學院', '閩南', '武昌', '漢藏教理院', '教育']):
        categories.append('佛教教育')
    if any(kw in full_text for kw in ['海潮音', '出版', '發行', '叢書', '覺社', '正信']):
        categories.append('出版編輯')
    if any(kw in full_text for kw in ['改革', '佛教會', '協會', '教制', '教產']):
        categories.append('佛教改革')
    if any(kw in full_text for kw in ['出國', '訪問', '南洋', '日本', '歐美', '環遊', '訪問團', '印度']):
        categories.append('國際交流')
    if any(kw in full_text for kw in ['閉關', '掩關', '閱藏', '禪修', '修持', '止觀']):
        categories.append('閉關修持')
    if any(kw in full_text for kw in ['革命', '政治', '國民黨', '政府', '抗戰', '救國']):
        categories.append('政治社會')
    if any(kw in full_text for kw in ['著作', '撰', '寫', '成書', '編', '述']):
        categories.append('著作撰述')
    if any(kw in full_text for kw in ['病', '疾', '療養', '示寂', '圓寂', '逝世', '荼毘']):
        categories.append('健康生死')
    if any(kw in full_text for kw in ['詩', '偈', '酬唱', '和詩']):
        categories.append('詩文酬唱')
    if any(kw in full_text for kw in ['書信', '函', '致書', '來書']):
        categories.append('書信往來')
    if any(kw in full_text for kw in ['論諍', '辯論', '駁', '諍論', '爭論']):
        categories.append('論諍辯駁')
    if any(kw in full_text for kw in ['遊', '行腳', '參訪', '朝山']):
        categories.append('遊歷參訪')

    # Add dynasty/era context
    if year_info.get('dynasty') == '清':
        categories.append('晚清時期')
    western = year_info.get('western_start') or 0
    if year_info.get('era') == '民國' and 1937 <= western <= 1945:
        categories.append('抗戰時期')

    return categories


# ─── MD generation ─────────────────────────────────────────────

def generate_md(header_meta, sections_001, chronicle_data):
    """Generate the full MD document."""
    lines = []

    # Title
    lines.append('# 太虛大師年譜')
    lines.append('')
    lines.append(f'**作者**：{header_meta.get("author", "釋印順")}')
    lines.append(f'**來源**：CBETA 印順法師佛學著作集 Y13n0013')
    lines.append(f'**版本**：{header_meta.get("edition", "")}')
    lines.append(f'**卷數**：{header_meta.get("extent", "2卷")}')
    lines.append('')

    # TOC placeholder
    lines.append('## 目次')
    lines.append('')
    lines.append('- [序](#序)')
    lines.append('- [編者附言](#編者附言)')
    lines.append('- [名號、籍貫、年齡、眷屬](#名號籍貫年齡眷屬)')
    lines.append('- [年譜正文](#年譜正文)')
    lines.append('')

    # 001 sections
    for sec in sections_001:
        title = sec['title'] or ''
        lines.append(f'## {title}')
        lines.append('')
        lines.append(sec['content'])
        lines.append('')

    # Biographical
    if chronicle_data and chronicle_data.get('biographical'):
        lines.append('## 名號、籍貫、年齡、眷屬')
        lines.append('')
        for key, content in chronicle_data['biographical'].items():
            lines.append(f'### {key}')
            lines.append('')
            lines.append(content)
            lines.append('')

    # Chronicle years
    if chronicle_data and chronicle_data.get('years'):
        lines.append('## 年譜正文')
        lines.append('')

        for year_entry in chronicle_data['years']:
            yi = year_entry.get('year_info', {})
            title = year_entry.get('year_title', '')
            lines.append(f'### {title}')
            lines.append('')

            # Year info summary if available
            western = yi.get('western_start')
            age = yi.get('master_age')
            if western and age is not None:
                pass  # already in title

            for ev in year_entry.get('events', []):
                ev_title = ev.get('title', '')
                ev_content = ev.get('content', '')

                if ev.get('type') == 'heading' and ev_title and ev_content.strip():
                    lines.append(f'**{ev_title}**')
                    lines.append('')
                    lines.append(ev_content.strip())
                    lines.append('')

                elif ev.get('type') == 'heading_only':
                    lines.append(f'**{ev_title}**')
                    lines.append('')

                elif ev.get('type') == 'content' and not ev_title:
                    lines.append(ev_content.strip())
                    lines.append('')

                else:
                    if ev_title:
                        lines.append(f'**{ev_title}**')
                        lines.append('')
                    if ev_content.strip():
                        lines.append(ev_content.strip())
                        lines.append('')

            lines.append('')

    # Footer
    lines.append('---')
    lines.append('')
    lines.append(f'*由 CBETA Y13n0013 XML 自動生成，{datetime.now().strftime("%Y-%m-%d")}*')
    lines.append('')

    return '\n'.join(lines)


# ─── JSON generation ────────────────────────────────────────────

def generate_json(header_meta, sections_001, chronicle_data):
    """Generate the rich JSON document."""
    result = OrderedDict()

    # Metadata
    result['metadata'] = OrderedDict([
        ('title', '太虛大師年譜'),
        ('author', header_meta.get('author', '釋印順')),
        ('cbeta_id', header_meta.get('cbeta_id', {})),
        ('edition', header_meta.get('edition', '')),
        ('extent', header_meta.get('extent', '2卷')),
        ('source', header_meta.get('source', {})),
        ('publication_date', header_meta.get('publication_date', '')),
        ('generated_at', datetime.now().isoformat()),
        ('generated_from', ['Y13n0013_001.xml', 'Y13n0013_002.xml']),
    ])

    # Front matter
    result['front_matter'] = []
    for sec in sections_001:
        result['front_matter'].append(OrderedDict([
            ('type', sec['type']),
            ('title', sec['title']),
            ('content', sec['content']),
        ]))

    # Biographical
    if chronicle_data:
        result['biographical'] = OrderedDict()
        for key, content in chronicle_data.get('biographical', {}).items():
            result['biographical'][key] = content

    # Year entries with rich metadata
    if chronicle_data and chronicle_data.get('years'):
        result['chronicle'] = []

        for year_entry in chronicle_data['years']:
            yi = year_entry.get('year_info', {})

            year_record = OrderedDict([
                ('title', year_entry.get('year_title', '')),
                ('year_info', OrderedDict([
                    ('dynasty', yi.get('dynasty')),
                    ('era', yi.get('era')),
                    ('era_year', yi.get('era_year')),
                    ('rocs_year', yi.get('rocs_year')),
                    ('western_start', yi.get('western_start')),
                    ('western_end', yi.get('western_end')),
                    ('sexagenary', yi.get('sexagenary')),
                    ('master_age', yi.get('master_age')),
                    ('is_birth', yi.get('is_birth', False)),
                    ('is_posthumous', yi.get('is_posthumous', False)),
                ])),
                ('categories', []),
                ('entities', OrderedDict([
                    ('people', []),
                    ('places', []),
                    ('works', []),
                    ('organizations', []),
                ])),
                ('events', []),
                ('full_text', ''),  # for search
            ])

            # Process events and extract entities
            all_text_parts = []
            for ev in year_entry.get('events', []):
                ev_content = ev.get('content', '')
                ev_title = ev.get('title', '')
                all_text_parts.append(ev_title)
                all_text_parts.append(ev_content)

                event_record = OrderedDict([
                    ('type', ev.get('type', 'content')),
                    ('title', ev_title),
                    ('content', ev_content.strip()),
                ])
                if ev.get('subtitles'):
                    event_record['subtitles'] = ev['subtitles']
                year_record['events'].append(event_record)

            full_text = ' '.join(all_text_parts)
            year_record['full_text'] = full_text

            # Extract entities
            entities = extract_entities_from_text(full_text)
            year_record['entities'] = OrderedDict([
                ('people', entities.get('people', [])),
                ('places', entities.get('places', [])),
                ('works', entities.get('works', [])),
                ('organizations', entities.get('organizations', [])),
            ])

            # Classify
            year_record['categories'] = classify_year_events(year_entry.get('events', []), yi)

            result['chronicle'].append(year_record)

    # Summary indices for quick lookup
    result['indices'] = OrderedDict([
        ('years_by_age', OrderedDict()),
        ('years_by_western', OrderedDict()),
        ('years_by_era', OrderedDict()),
        ('all_categories', []),
        ('all_places', []),
        ('all_works', []),
        ('all_organizations', []),
    ])

    all_cats = set()
    all_places = set()
    all_works = set()
    all_orgs = set()

    for yr in result.get('chronicle', []):
        yi = yr.get('year_info', {})
        age = yi.get('master_age')
        western = yi.get('western_start')
        era = yi.get('era')

        if age is not None:
            result['indices']['years_by_age'][str(age)] = yr['title']
        if western is not None:
            result['indices']['years_by_western'][str(western)] = yr['title']
        if era:
            era_key = f"{era}_{yi.get('era_year', '')}"
            result['indices']['years_by_era'][era_key] = yr['title']

        all_cats.update(yr.get('categories', []))
        all_places.update(yr.get('entities', {}).get('places', []))
        all_works.update(yr.get('entities', {}).get('works', []))
        all_orgs.update(yr.get('entities', {}).get('organizations', []))

    result['indices']['all_categories'] = sorted(all_cats)
    result['indices']['all_places'] = sorted(all_places)
    result['indices']['all_works'] = sorted(all_works)
    result['indices']['all_organizations'] = sorted(all_orgs)

    return result


# ─── main ───────────────────────────────────────────────────────

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    xml_001 = os.path.join(DATA_DIR, 'Y13n0013_001.xml')
    xml_002 = os.path.join(DATA_DIR, 'Y13n0013_002.xml')

    print('📖 解析 001: 序 + 编者附言 ...')
    header_meta = extract_header_meta(xml_001)
    sections_001 = parse_001(xml_001)
    print(f'   找到 {len(sections_001)} 个前导章节')

    print('📖 解析 002: 传记资料 + 年谱正文 ...')
    chronicle_data = parse_002_biographical(xml_002)
    if chronicle_data:
        bio_count = len(chronicle_data.get('biographical', {}))
        years_count = len(chronicle_data.get('years', []))
        print(f'   传记资料: {bio_count} 节')
        print(f'   年份条目: {years_count} 年')

    print('📝 生成 Markdown ...')
    md_content = generate_md(header_meta, sections_001, chronicle_data)
    md_path = os.path.join(OUT_DIR, '太虛大師年譜.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    print(f'   ✅ {md_path} ({len(md_content)} 字)')

    print('📝 生成 JSON ...')
    json_content = generate_json(header_meta, sections_001, chronicle_data)
    json_path = os.path.join(OUT_DIR, '太虛大師年譜.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_content, f, ensure_ascii=False, indent=2)
    print(f'   ✅ {json_path} ({len(json.dumps(json_content, ensure_ascii=False))} 字)')

    print('\n🎉 完成！')


if __name__ == '__main__':
    main()
