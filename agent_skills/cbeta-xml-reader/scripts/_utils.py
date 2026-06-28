#!/usr/bin/env python3
"""Shared utilities for CBETA TX XML processing scripts.

Used by extract_book_catalog.py and extract_article_fulltext.py.
"""

import re

# ── Chinese numeral utilities ─────────────────────────────────────────

CHINESE_NUM = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
}

def chinese_to_int(s):
    """Convert Chinese numeral to int (e.g. 十九→19, 二十六→26, 十→10)."""
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
    """Extract leading month/season from rest string.

    Returns (month_str, remaining).
    month_str examples: '1 月', '春', '夏', '秋', '冬', '' if no match.
    """
    rest = rest.strip()
    if not rest:
        return '', ''
    # Month: 一月, 二月, ... 十二月, 正月
    m = re.match(r'(正|一|二|三|四|五|六|七|八|九|十[一二]?|[一二]?十[一二]?)月', rest)
    if m:
        mm = MONTH_MAP.get(m.group(1))
        if mm:
            return f'{mm} 月', rest[m.end():].strip()
    # Season: 春, 夏, 秋, 冬 (as first char)
    if rest[0] in SEASONS:
        return rest[0], rest[1:].strip()
    return '', rest


def build_suffix(month, rest):
    """Build suffix string; season (1-char, e.g. 春) gets no leading space."""
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
    """Normalize byline: 民国/宣统纪年→公元, ——→().

    Examples:
        '——十九年一月在閩南佛學院編述——' → '（1930 年 1 月，在閩南佛學院編述）'
        '——民國四年春作於普陀——' → '（1915 年春，作於普陀）'
        '——宣統二年作——' → '（1910 年，作）'
    """
    raw = raw.strip()
    if not raw:
        return ''

    # Strip —— delimiters (single or repeated)
    raw = re.sub(r'^——+|——+$', '', raw).strip()

    # Skip 見海刊 type publication notes
    if re.match(r'見海刊', raw):
        return ''

    # 记录者 only: （…記）
    m_rec = re.match(r'^（(.+記)）$', raw)
    if m_rec:
        return f'（{m_rec.group(1)}）'

    # 宣統N年...
    m = re.match(r'宣統(.+?)年(.*)', raw)
    if m:
        yr = chinese_to_int(m.group(1))
        if yr is not None:
            rest = m.group(2).strip()
            month, rest = split_month_season(rest)
            suffix = build_suffix(month, rest)
            return f'（{1908 + yr} 年{suffix}）'

    # 民國N年...
    m = re.match(r'民國(.+?)年(.*)', raw)
    if m:
        yr = chinese_to_int(m.group(1))
        if yr is not None:
            rest = m.group(2).strip()
            month, rest = split_month_season(rest)
            suffix = build_suffix(month, rest)
            return f'（{1911 + yr} 年{suffix}）'

    # N年... (bare 民国 year, Chinese or Arabic numeral)
    m = re.match(r'(.+?)年(.*)', raw)
    if m:
        yr = chinese_to_int(m.group(1))
        if yr is not None and 1 <= yr <= 99:
            rest = m.group(2).strip()
            month, rest = split_month_season(rest)
            suffix = build_suffix(month, rest)
            return f'（{1911 + yr} 年{suffix}）'

    # Fallback: just wrap
    return f'（{raw}）'


def parse_byline_fields(byline):
    """Parse 題注 into structured fields: date (YYYY-MM), location, context.

    Shared by extract_article_fulltext.py and add_frontmatter_to_existing.py
    so that frontmatter `date` formatting is identical across the extraction
    pipeline and the migration tool (no month → 'YYYY-01', not bare 'YYYY').

    Input: 題注 like '（1930 年 1 月，在閩南佛學院編述）'.
    Returns: dict with date, location, context.
    """
    result = {'date': '', 'location': '', 'context': ''}
    if not byline:
        return result

    # Strip outer （）
    inner = byline.strip('（ ）()')

    # Extract year: YYYY 年
    m_yr = re.match(r'(\d+)\s*年', inner)
    if m_yr:
        year = m_yr.group(1)
        rest = inner[m_yr.end():].strip()
        # Extract month
        m_mon = re.match(r'(\d+)\s*月', rest)
        if m_mon:
            result['date'] = f"{year}-{int(m_mon.group(1)):02d}"
            rest = rest[m_mon.end():].strip()
        else:
            # Check for season
            season_map = {'春': '03', '夏': '06', '秋': '09', '冬': '12'}
            if rest and rest[0] in season_map:
                result['date'] = f"{year}-{season_map[rest[0]]}"
                rest = rest[1:].strip()
            else:
                result['date'] = f"{year}-01"
        # Strip leading ，or comma
        rest = re.sub(r'^[，,]\s*', '', rest)
    else:
        rest = inner

    # Extract location: 在… / 於… / 作於…
    m_loc = re.match(r'在(.+?)([編講作記述說]+)$', rest)
    if m_loc:
        result['location'] = m_loc.group(1).strip()
        result['context'] = m_loc.group(2).strip()
    elif rest:
        m_loc2 = re.match(r'作於(.+)', rest)
        if m_loc2:
            result['location'] = m_loc2.group(1).strip()
            result['context'] = '作'
        else:
            for suffix in ['編述', '編', '講', '作', '記', '說']:
                if rest.endswith(suffix):
                    result['context'] = suffix
                    result['location'] = rest[:-len(suffix)].strip()
                    break
            else:
                result['location'] = rest

    return result


# ── Publication info extraction utilities ─────────────────────────────

# Known publication sources (whitelist for classifying references)
PUB_SOURCES = [
    '海刊', '海潮音', '海潮音月刊',
    '覺社叢書', '覺社', '覺書', '覺刊',
    '正信', '居士林林刊', '林刊', '世界佛教居士林林刊',
    '佛教日報', '佛教月報',
    '中流', '廬山學', '演說集',
    '佛化策進會會刊', '太虛叢書', '人生佛教',
    '訪問日記', '朝日新聞', '彌陀淨土法門集',
    '西來講演集', '學僧之路',
    '文鈔', '文庫', '文史雜誌',
    '東方文化', '東方雜誌', '軍事與政治',
    '中國佛學旬刊', '時代精神',
    '昧盦詩錄', '道學論衡', '覺群', '覺書',
    '文化先鋒', '大公報', '新國民日報',
    '淨土宗月刊',
    # Imprint patterns
    '印行', '印本', '印單行本', '流通本', '單行本', '出版', '發行',
    '佛學書局', '正信會', '華北居士林', '昆明雲棲寺',
    '重慶佛經流通處', '漢藏教理院', '中央刻經院', '天童寺',
    '大東書局', '世界書局', '廈門慈宗學會', '武昌正信印務館',
    '漢口印行', '佛學院', '油印',
]


def classify_byline_content(raw_text):
    """Classify byline/note text into a type label.

    Returns one of:
      '刊载出处' — original periodical publication reference (見海刊X卷Y期 etc.)
      '印行信息' — book/separate printing info (佛學書局印行 etc.)
      '讲演信息' — lecture/writing date and location
      '记録者' — scribe/note-taker attribution (XX記)
      '作者署名' — author signature/date
      '出处说明' — editorial note about provenance, title changes
      '综合' — combination of multiple types
    """
    text = raw_text.strip()

    if not text:
        return '空'

    has_pub = False
    has_imprint = False
    has_lecture = False
    has_scribe = False
    has_author = False
    has_note = False

    # Check for publication reference patterns
    # Pattern 1: （見...）, （錄自...）, （出...）
    if re.search(r'[（(][見见錄录出]', text):
        has_pub = True
    # Pattern 2: Starts with 見/錄自 (standalone or after byline prefix)
    elif re.match(r'^[見见錄录出]', text.strip()):
        has_pub = True
    elif re.match(r'^[原并並散]?[見见]', text.strip()):
        has_pub = True  # 原見, 並見, 散見, etc.
    # Pattern 3: （XX記）見海刊X卷Y期 or similar
    elif re.search(r'[)）]\s*[原并並散]?[見见]', text):
        has_pub = True
    # Pattern 4: Contains 刊載, 轉載, 登載
    elif re.search(r'[刊载載刊轉转登][載载刊登]', text):
        has_pub = True

    # Check for imprint patterns
    for kw in ['印行', '印本', '流通本', '單行本', '印刷', '印發', '油印']:
        if kw in text:
            has_imprint = True
            break

    # Check for lecture date/location patterns (—— or ── or bare 某年某月在某處...)
    if re.search(r'——|──', text):
        has_lecture = True
    elif re.search(r'(民國|宣統)?\d+年.*?(在|於|作|編|講|述|記)', text):
        has_lecture = True

    # Check for scribe pattern: （...記） or （...記, ...編） etc.
    if re.search(r'[（(][^)）]*[記记]', text):
        has_scribe = True

    # Check for author signature: 太虛 + date, or bare Chinese date
    if re.search(r'太虛[識撰跋敘序記附書簽]|釋太虛|雪山太虛', text):
        has_author = True
    elif re.search(r'(?<![，,])太虛[，,、]', text):
        has_author = True
    elif re.search(r'^[（(]?太虛', text):
        has_author = True
    # Also: bare date patterns that look like author dates
    elif re.match(r'^[（(]?(民國|民|佛曆|佛)[\d一二三四五六七八九十百千]+年', text):
        has_author = True
    # Also: date-only bylines (no explicit 太虛, but clearly authorial dating)
    # 卅二年八月卅日，... — with or without location
    elif re.match(r'^[（(]?[廿卅第]?[\d一二三四五六七八九十百千万廿卅]+[，,\s]*年?[，,\s]*[\d一二三四五六七八九十廿卅]+[，,\s]*月?[\d一二三四五六七八九十廿卅]+[日，,\s]', text):
        has_author = True

    # Check for editorial note: 原題, 改題, 附註, 附注, 此下
    for kw in ['原題', '改題', '附註', '附注', '原名', '原題為',
               '題作', '署名', '刊載', '轉載', '登載', '載於',
               '今依', '今仍', '今改', '此係', '初版', '再版', '重版']:
        if kw in text:
            has_note = True
            break

    # Count active types
    types = []
    if has_pub:
        types.append('刊载出处')
    if has_imprint:
        types.append('印行信息')
    if has_lecture:
        types.append('讲演信息')
    if has_scribe:
        types.append('记録者')
    if has_author:
        types.append('作者署名')
    if has_note:
        types.append('出处说明')

    if len(types) == 0:
        # Unclassified — try broader matching
        if re.search(r'[見见].*[刊报報叢书書集鈔钞誌志月周旬]', text):
            return '刊载出处'
        if re.match(r'^[（(].{1,12}[)）]$', text.strip()):
            return '记録者'
        # Check against known publication sources
        for source in PUB_SOURCES:
            if source in text and len(source) >= 2:
                return '刊载出处'
        return '其他'

    if len(types) >= 2:
        return '综合'

    return types[0]


def is_publication_related(text):
    """Check if text contains publication-related information.

    Used for filtering 附註 paragraphs and foot notes.
    """
    keywords = [
        '刊載', '刊载', '海刊', '改題', '原題', '出版', '印行',
        '轉載', '登載', '初版', '再版', '發行', '編入', '流通',
        '載於', '單行本', '流通本', '題作', '署名', '原題為',
        '原題作', '今改', '今仍', '今依', '此處', '原見',
        '原載', '錄自', '選自', '節自', '出「', '出自',
        '見海刊', '見海潮音', '見覺', '見正信', '見佛教',
        '見居士', '見林刊', '見朝日', '原刊',
    ]
    return any(kw in text for kw in keywords)


def extract_all_byline_info(article_elem, tei_ns, cbeta_ns=None):
    """Extract and classify all byline content from an article XML element.

    Handles: byline, tei:byline, cb:type="other", cb:type="author", cb:type="editor",
    and bare byline tags.

    Args:
        article_elem: An ElementTree element (the article div or root of the chunk)
        tei_ns: TEI namespace URL (e.g. 'http://www.tei-c.org/ns/1.0')
        cbeta_ns: CBETA namespace URL (optional)

    Returns:
        List of dicts: [{type, raw_text, byline_type, source_tag}, ...]
    """
    results = []
    seen_texts = set()  # deduplicate within same article

    # Search for all byline elements (namespaced and non-namespaced)
    byline_tags = set()
    if tei_ns:
        byline_tags.add(f'{{{tei_ns}}}byline')
    byline_tags.add('byline')
    for tag in byline_tags:
        for elem in article_elem.iter(tag):
            raw = ''.join(elem.itertext()).strip()
            # Normalize whitespace
            raw = ' '.join(raw.split())
            if not raw or raw in seen_texts:
                continue
            seen_texts.add(raw)

            # Determine byline type from cb:type attribute
            byline_type = elem.get(f'{{{cbeta_ns}}}type') if cbeta_ns else elem.get('cb:type')
            if not byline_type:
                byline_type = elem.get('type', 'none')

            classification = classify_byline_content(raw)
            results.append({
                'type': classification,
                'raw_text': raw,
                'byline_type': byline_type,
                'source_tag': 'byline',
            })

    return results


def extract_inline_notes(article_elem, tei_ns, cbeta_ns=None, byline_only=True):
    """Extract <note place="inline"> content from an article XML element.

    Args:
        article_elem: An ElementTree element
        tei_ns: TEI namespace URL
        cbeta_ns: CBETA namespace URL (optional)
        byline_only: If True, only extract notes inside <byline> elements.
                     If False, extract all notes and filter non-publication ones.

    Returns:
        List of dicts: [{type, raw_text, source_tag}, ...]
    """
    results = []
    seen_texts = set()

    if byline_only:
        # Search for notes only within byline elements (much faster)
        byline_tags = set()
        if tei_ns:
            byline_tags.add(f'{{{tei_ns}}}byline')
        byline_tags.add('byline')

        note_tag_tei = f'{{{tei_ns}}}note' if tei_ns else 'note'

        for bl_tag in byline_tags:
            for bl in article_elem.iter(bl_tag):
                # Search for note elements within this byline
                for note in bl.iter():
                    note_local = note.tag.split('}')[-1] if '}' in note.tag else note.tag
                    if note_local != 'note':
                        continue
                    if note.get('place') != 'inline':
                        continue
                    if note.get('type') == 'add' and note.get('rend') == 'hide':
                        continue
                    raw = ''.join(note.itertext()).strip()
                    raw = ' '.join(raw.split())
                    if not raw or raw in seen_texts:
                        continue
                    seen_texts.add(raw)
                    classification = classify_byline_content(raw)
                    results.append({
                        'type': classification,
                        'raw_text': raw,
                        'source_tag': 'inline_note',
                    })
    else:
        # Search all notes, filter non-publication ones
        note_tags = set()
        if tei_ns:
            note_tags.add(f'{{{tei_ns}}}note')
        note_tags.add('note')

        for tag in note_tags:
            for elem in article_elem.iter(tag):
                if elem.get('place') != 'inline':
                    continue
                if elem.get('type') == 'add' and elem.get('rend') == 'hide':
                    continue
                raw = ''.join(elem.itertext()).strip()
                raw = ' '.join(raw.split())
                if not raw or raw in seen_texts:
                    continue
                seen_texts.add(raw)
                classification = classify_byline_content(raw)
                results.append({
                    'type': classification,
                    'raw_text': raw,
                    'source_tag': 'inline_note',
                })

    return results


def extract_fuzhu_paragraphs(article_elem, tei_ns=None):
    """Extract content from （附註） styled paragraphs.

    Scans for <p> elements with style="margin-left:6em;text-indent:-4em"
    or containing （附註） or （附注） text.

    Args:
        article_elem: An ElementTree element
        tei_ns: TEI namespace URL (optional)

    Returns:
        List of dicts: [{type, raw_text, source_tag}, ...]
    """
    results = []
    seen_texts = set()

    # Search for non-namespaced p elements (most common in CBETA)
    p_tags = ['p']
    if tei_ns:
        p_tags.append(f'{{{tei_ns}}}p')

    for tag in p_tags:
        for elem in article_elem.iter(tag):
            raw = ''.join(elem.itertext()).strip()
            raw = ' '.join(raw.split())
            if not raw or raw in seen_texts:
                continue

            # Check if this paragraph contains 附註/附注
            if '附註' in raw or '附注' in raw:
                # Only include if publication-related
                if is_publication_related(raw):
                    seen_texts.add(raw)
                    classification = classify_byline_content(raw)
                    results.append({
                        'type': classification,
                        'raw_text': raw,
                        'source_tag': '附註段落',
                    })

    return results


def extract_back_notes_for_article(full_xml_path, article_byte_start, article_byte_end):
    """Extract publication-related <note place="foot text" type="orig">
    from <back> section whose targets appear in the article's byte range.

    Args:
        full_xml_path: Path to the full XML file
        article_byte_start: Start byte offset of article
        article_byte_end: End byte offset of article

    Returns:
        List of dicts: [{type, raw_text, source_tag, note_n, target}, ...]
    """
    import os
    results = []

    try:
        with open(full_xml_path, 'rb') as f:
            f.seek(article_byte_start)
            article_chunk = f.read(article_byte_end - article_byte_start).decode('utf-8', errors='replace')
    except Exception:
        return results

    # Collect anchor IDs from the article chunk
    anchor_ids = set(re.findall(r'anchor xml:id="(nkr_note_orig_\d+)"', article_chunk))
    if not anchor_ids:
        return results

    # Read full file to find <back> section (use regex, faster than full parse)
    try:
        with open(full_xml_path, 'r', encoding='utf-8') as f:
            full_text = f.read()
    except Exception:
        return results

    back_match = re.search(r'<back>.*?</back>', full_text, re.DOTALL)
    if not back_match:
        return results

    # Find publication-related <note> elements
    note_pattern = re.compile(
        r'<note n="(\d+)"[^>]*target="#(nkr_note_orig_\d+)"[^>]*>(.*?)</note>',
        re.DOTALL
    )
    seen_texts = set()
    for m in note_pattern.finditer(back_match.group()):
        anchor_id = m.group(2)
        if anchor_id not in anchor_ids:
            continue
        raw = re.sub(r'<[^>]+>', '', m.group(3)).strip()
        raw = ' '.join(raw.split())
        if not raw or raw in seen_texts:
            continue

        if not is_publication_related(raw):
            continue

        seen_texts.add(raw)
        classification = classify_byline_content(raw)
        results.append({
            'type': classification,
            'raw_text': raw,
            'source_tag': 'foot_note',
            'note_n': m.group(1),
            'target': anchor_id,
        })

    return results
