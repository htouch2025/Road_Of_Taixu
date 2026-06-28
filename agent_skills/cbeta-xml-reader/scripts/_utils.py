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
