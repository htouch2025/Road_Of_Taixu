#!/usr/bin/env python3
"""Shared utilities for CBETA TX XML processing scripts.

Used by extract_bian_catalog.py and extract_article_fulltext.py.
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
