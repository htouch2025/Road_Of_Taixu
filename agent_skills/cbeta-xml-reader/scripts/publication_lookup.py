#!/usr/bin/env python3
"""Publication volume/issue → date lookup from 刊载信息卷期对照表.

Parses _data/刊载信息卷期对照表.md at import time and provides:
  normalize_publication_name(raw) → canonical name or None
  parse_volume_issue(text)          → (pub_name, vol, issue_list) or None
  lookup_date(pub_name, vol, issue) → (y, m, d) or None
"""

import re
import os

# ── Path resolution ────────────────────────────────────────────────────

_LOOKUP_MD = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    '_data', '刊载信息卷期对照表.md'
)
# Fallback: try relative to cwd
if not os.path.exists(_LOOKUP_MD):
    _LOOKUP_MD = '_data/刊载信息卷期对照表.md'


# ── Alias table ─────────────────────────────────────────────────────────
# Maps abbreviated / variant names → canonical publication name.
# Canonical names must match the headers in 刊载信息卷期对照表.md.

ALIASES = {
    # 海潮音 variants
    '海刊': '海潮音',
    '海潮音月刊': '海潮音',
    '人海灯': '海潮音',
    # 正信 variants
    '正信周刊': '正信',
    '正信半月刊': '正信',
    '正信月刊': '正信',
    # 觉群 variants
    '覺群': '覺群週報',
    '覺群報': '覺群週報',
    '覺群周報': '覺群週報',
    '覺群週報': '覺群週報',
    # 世界佛教居士林林刊 variants
    '居士林林刊': '世界佛教居士林林刊',
    '林刊': '世界佛教居士林林刊',
    '世界居士林林刊': '世界佛教居士林林刊',
    # 觉社丛书
    '覺社': '覺社叢書',
    # 觉书
    '覺書': '覺書',
    # 佛教月报
    '佛教月報': '佛教月報',
    '佛學月報': '佛教月報',  # typo in CBETA
    # 佛教日报
    '佛教日報': '佛教日報',
    # 佛化新闻
    '佛化新聞': '佛化新聞',
    # 觉音 / 华南觉音
    '華南覺音': '覺音',
    '覺音': '覺音',
    # 现代佛教
    '現代佛教': '現代佛教',
    # 现代僧伽
    '現代僧伽': '現代僧伽',
    # 文化先锋
    '文化先鋒': '文化先鋒',
    '文藝先鋒': '文化先鋒',  # typo in CBETA
    # 时代精神
    '時代精神': '時代精神',
    # 宇宙风
    '宇宙風': '宇宙風',
    # 大公报
    '大公報': '大公報',
    # 佛学半月刊
    '佛學半月刊': '佛學半月刊',
    # 佛学日报
    '佛學日報': '佛學日報',
    # 净土宗月刊
    '淨土宗月刊': '淨土宗月刊',
    # 觉有情
    '覺有情': '覺有情',
    # 读书通讯
    '讀書通訊': '讀書通訊',
    # 反侵略
    '反侵略': '反侵略',
    # 慈航画报
    '慈航畫報': '慈航畫報',
    # 新中华
    '新中華': '新中華',
    # 益世报
    '益世報': '益世報',
    # 黄钟
    '黃鐘': '黃鐘',
    # 香海佛化刊
    '香海佛化刊': '香海佛化刊',
    # 军事与政治
    '軍事與政治': '軍事與政治',
    # 民族正气
    '民族正氣': '民族正氣',
    # 时事新报
    '時事新報': '時事新報',
    # 中国佛学
    '中國佛學': '中國佛學',
    '中國佛學旬刊': '中國佛學',
    # 中央日报
    '中央日報': '中央日報',
    # 星洲叻报
    '星洲叻報': '星洲叻報',
    '星洲叨報': '星洲叻報',  # typo variant
    # 世界宗教会记载
    '世界宗教會記載': '世界宗教會記載',
    # 汉藏教理院
    '漢藏教理院年刊': '世界佛學苑漢藏教理院年刊',
    '漢藏教理院開學紀念特刊': '世界佛學苑漢藏教理院年刊',
    '漢藏教理院': '世界佛學苑漢藏教理院年刊',
    # 佛教新闻
    '佛教新聞': '佛教新聞',
}

# Additional non-periodical imprints that may appear as "publication"
IMPRINTS = {
    '佛學書局', '上海佛學書局', '正信會', '華北居士林',
    '昆明雲棲寺', '重慶佛經流通處', '漢藏教理院',
    '中央刻經院', '天童寺', '大東書局', '世界書局',
    '廈門慈宗學會', '武昌正信印務館', '漢口印行', '佛學院',
}


def normalize_publication_name(raw):
    """Normalize a raw publication name to its canonical form.

    Returns the canonical name, or the original raw text if not recognized.
    Returns None for empty input.
    """
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    # Direct alias match
    if raw in ALIASES:
        return ALIASES[raw]
    # Case-insensitive / whitespace-normalized fallback not needed for CJK
    return raw


# ── Lookup table ────────────────────────────────────────────────────────
# _LOOKUP: {(pub_name, vol_int, issue_int): (year, month, day)}
# Built at import time.

_LOOKUP = {}


def _parse_date(date_str):
    """Parse a date string like '1920.03.10' or '1920-03-10' into (y, m, d)."""
    date_str = date_str.strip()
    # Try YYYY.MM.DD
    m = re.match(r'(\d{4})\.(\d{2})\.(\d{2})', date_str)
    if m:
        return m.group(1), m.group(2), m.group(3)
    # Try YYYY-MM-DD
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if m:
        return m.group(1), m.group(2), m.group(3)
    return None


def _parse_vol_issue_cell(cell_text):
    """Parse a 卷期号 table cell into (vol, issue) integers.

    Handles formats like:
      '1卷1期'       → (1, 1)
      '一卷1期'      → (1, 1)
      '8卷4-5期'    → (8, 4)  -- take first issue of range
      '8卷11-12期'  → (8, 11)
      '8卷11-2期'   → (8, 11)  -- '11-2' means 11-12
      '1期'          → (None, 1)  -- no volume
      '4期'          → (None, 4)
      '六卷3-4期（合刊）' → (6, 3)
      '一卷11期至三卷5期' → (1, 11) -- range across volumes, take first
      '二卷11期至三卷5期' → (2, 11)
    """
    text = cell_text.strip()
    # Remove parenthetical notes like （合刊）
    text = re.sub(r'[（(][^)）]*[)）]', '', text).strip()

    # Try cross-volume range: X卷Y期至X卷Y期 → take first vol/issue
    m = re.match(r'([一二三四五六七八九十\d]+)卷(\d+)期至', text)
    if m:
        vol = _chinese_num_to_int(m.group(1))
        if vol is None:
            vol = int(m.group(1))
        issue = int(m.group(2))
        return (vol, issue)

    # Extract volume
    vol = None
    m_vol = re.match(r'([一二三四五六七八九十\d]+)卷', text)
    if m_vol:
        vol = _chinese_num_to_int(m_vol.group(1))
        if vol is None:
            vol = int(m_vol.group(1))

    # Extract issue (first number after 卷 or at start)
    if vol is not None:
        rest = text[text.index('卷') + 1:]
    else:
        rest = text

    # Issue pattern: number followed by 期/号
    # For ranges like '4-5期' or '11-12期', take the first number
    m_issue = re.search(r'(\d+)(?:[-‐-―](\d+))?期', rest)
    if m_issue:
        issue = int(m_issue.group(1))
        return (vol, issue)

    # Bare number + 期 (no vol)
    m_issue2 = re.match(r'(\d+)期', rest)
    if m_issue2:
        return (vol, int(m_issue2.group(1)))

    return (vol, None)


def _chinese_num_to_int(s):
    """Convert Chinese numeral to int (一→1, 十→10, 十二→12, 二十六→26)."""
    s = s.strip()
    if s.isdigit():
        return int(s)
    mapping = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
               '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
    total = 0
    section = 0
    for c in s:
        if c == '十':
            total += (section or 1) * 10
            section = 0
        elif c in mapping:
            section = mapping[c]
        else:
            return None
    total += section
    return total if total > 0 else None


def _build_lookup():
    """Parse _data/刊载信息卷期对照表.md and populate _LOOKUP."""
    global _LOOKUP
    if _LOOKUP:
        return

    if not os.path.exists(_LOOKUP_MD):
        print(f'[publication_lookup] WARNING: lookup table not found at {_LOOKUP_MD}')
        return

    with open(_LOOKUP_MD, 'r', encoding='utf-8') as f:
        text = f.read()

    # Split by publication sections: # NN、刊物名
    sections = re.split(r'\n(?=# \d+、)', text)

    for section in sections:
        # Extract publication name from header
        m_header = re.match(r'# \d+、(.+)', section)
        if not m_header:
            continue
        pub_name = m_header.group(1).strip()
        # Strip citation count suffix like （22次引用） or （30次引用）
        pub_name = re.sub(r'[（(]\d+次引用[)）]$', '', pub_name).strip()
        # Strip alternate name after ／ (e.g. 覺群週報／覺群報 → 覺群週報)
        pub_name = re.sub(r'／.+$', '', pub_name).strip()
        # Strip empty parentheses like （）
        pub_name = re.sub(r'[（(]\s*[)）]$', '', pub_name).strip()

        # Find the 卷期对照表 table
        # Look for table rows: | ... | ... | ... |
        table_start = section.find('## 卷期对照表')
        if table_start < 0:
            table_start = section.find('## 卷期对照表')  # alternate encoding
        if table_start < 0:
            continue

        table_section = section[table_start:]

        # Find next ## heading to bound the table
        next_heading = re.search(r'\n## ', table_section[4:])  # skip the first ##
        if next_heading:
            table_section = table_section[:next_heading.start() + 4]

        # Parse table rows
        for line in table_section.split('\n'):
            line = line.strip()
            if not line.startswith('|'):
                continue
            cells = [c.strip() for c in line.split('|')]
            cells = [c for c in cells if c]  # remove empty from leading/trailing |

            # Skip header separator row and header row
            if not cells:
                continue
            if cells[0] in ('#', '---', '--'):
                continue
            if all(c in '-: ' for c in cells[0]):
                continue
            # Skip header row: first cell looks like '#', '卷期号', etc.
            if cells[0] in ('#', '卷期号', '卷期號'):
                continue
            # Skip 海潮音's specific header
            if cells[0] == '#' and '海潮音卷期' in line:
                continue

            # Determine which cells contain vol/issue and date
            # Usually:  | # | vol_issue | date | source |
            # or:       | vol_issue | date | source |
            # or for 佛教日报: date is embedded in vol_issue text
            if len(cells) < 2:
                continue

            # Try to find date cell (contains YYYY pattern)
            date_cell = None
            vol_cell = None
            for cell in cells:
                if re.search(r'\d{4}[\.\-]\d{2}[\.\-]\d{2}', cell):
                    date_cell = cell
                elif re.search(r'卷|期', cell):
                    vol_cell = cell

            if date_cell is None:
                # Try cells that look like dates with extra text
                for cell in cells:
                    m = re.search(r'(\d{4}[\.\-]\d{2}[\.\-]\d{2})', cell)
                    if m:
                        date_cell = m.group(1)
                        break
                if date_cell is None:
                    continue

            if vol_cell is None:
                # Take the cell before the date cell
                for i, cell in enumerate(cells):
                    if cell == date_cell and i > 0:
                        vol_cell = cells[i - 1]
                        # Skip if it's a sequence number
                        if re.match(r'^\d+$', vol_cell):
                            vol_cell = cells[i - 2] if i > 1 else None
                        break
                if vol_cell is None:
                    continue

            # Parse vol/issue
            parsed_vi = _parse_vol_issue_cell(vol_cell)
            if parsed_vi is None or parsed_vi[1] is None:
                continue
            vol, issue = parsed_vi

            # Parse date
            parsed_date = _parse_date(date_cell)
            if parsed_date is None:
                continue
            y, m, d = parsed_date

            # Store with vol as None meaning "any vol" (for publications without volumes)
            key = (pub_name, vol if vol is not None else 0, issue)
            _LOOKUP[key] = (y, m, d)

            # For publications like 佛教月報 without volume, also store with vol=0
            if vol is None:
                key2 = (pub_name, 0, issue)
                _LOOKUP[key2] = (y, m, d)


def lookup_date(pub_name, vol, issue):
    """Look up publication date for a given publication, volume, and issue.

    Args:
        pub_name: canonical publication name (str)
        vol: volume number (int or None)
        issue: issue number (int or None)

    Returns:
        (year, month, day) tuple of strings, or None if not found.
    """
    if _LOOKUP is None or len(_LOOKUP) == 0:
        _build_lookup()
    if not _LOOKUP:
        return None

    if pub_name is None or issue is None:
        return None

    # Try exact match
    v = vol if vol is not None else 0
    key = (pub_name, v, issue)
    if key in _LOOKUP:
        return _LOOKUP[key]

    # Try vol=0 (no-volume publications)
    if vol is not None and vol != 0:
        key2 = (pub_name, 0, issue)
        if key2 in _LOOKUP:
            return _LOOKUP[key2]

    return None


# ── Volume/issue text parser ────────────────────────────────────────────

def parse_volume_issue(text):
    """Parse a publication reference text to extract (pub_name, vol, issue_list).

    Handles formats like:
      '原見海潮音月刊十八卷十一期'     → ('海潮音', 18, [11])
      '見海刊九卷第九及十期'          → ('海潮音', 9, [9, 10])
      '散見正信二卷十一期至三卷五期'   → ('正信', 2, [11])
      '見海刊十卷十期'               → ('海潮音', 10, [10])
      '見覺群周報一卷一期'            → ('覺群週報', 1, [1])
      '見覺社叢書第一期'              → ('覺社叢書', None, [1])
      '上海佛學書局印行'              → ('上海佛學書局', None, None)  # imprint

    Returns:
        (pub_name, vol, issues) where:
          pub_name: canonical publication name or raw imprint name
          vol: int or None
          issues: list of int (first issue only for cross-volume ranges), or None
        Returns None if no publication reference found.
    """
    if not text or not text.strip():
        return None
    text = text.strip()

    # Remove common prefixes
    text = re.sub(r'^[原并並散]?[見见]', '', text).strip()
    text = re.sub(r'^[錄录]自?', '', text).strip()
    text = re.sub(r'^[（(][^)）]*[)）]', '', text).strip()

    # ── Try to find a known publication name in the text ──

    # Build a combined set of all known names (aliases + canonical names)
    # sorted by length descending for longest-match-first
    all_names = {}
    for alias, canonical in ALIASES.items():
        all_names[alias] = canonical
    # Also add canonical names as self-mappings
    for canonical in set(ALIASES.values()):
        if canonical not in all_names:
            all_names[canonical] = canonical

    found_pub = None
    found_alias = None
    for name in sorted(all_names.keys(), key=len, reverse=True):
        if name in text:
            found_alias = name
            found_pub = all_names[name]
            break

    # If no publication name matched, check IMPRINTS
    if found_pub is None:
        for imp in sorted(IMPRINTS, key=len, reverse=True):
            if imp in text:
                return (imp, None, None)

    # ── Parse volume and issue ──

    vol = None
    issues = None

    # Pattern 1: X卷Y期 (with optional Chinese numerals)
    # Also handles X卷Y及Z期, X卷Y至Z期
    if found_pub is not None:
        # Find the position of the pub name alias in text
        idx = text.find(found_alias)
        rest = text[idx + len(found_alias):]

        # Try cross-volume range first: X卷Y期至X卷Y期
        m_range = re.search(
            r'([一二三四五六七八九十\d]+)卷(\d+)期[至及和]'
            r'([一二三四五六七八九十\d]+)卷(\d+)期',
            rest
        )
        if m_range:
            vol = _chinese_num_to_int(m_range.group(1))
            if vol is None:
                vol = int(m_range.group(1))
            issues = [int(m_range.group(2))]
            return (found_pub, vol, issues)

        # Pattern: X卷Y期
        # X can be Chinese numeral or Arabic
        m_vi = re.search(
            r'([一二三四五六七八九十\d]+)卷\s*'
            r'(?:第\s*)?'
            r'([一二三四五六七八九十\d]+)'
            r'(?:[及和至、,\-/‐-―]?'
            r'(?:第\s*)?'
            r'([一二三四五六七八九十\d]+))?'
            r'\s*[期号號]',
            rest
        )
        if m_vi:
            vol = _chinese_num_to_int(m_vi.group(1))
            if vol is None:
                vol = int(m_vi.group(1))
            i1 = _chinese_num_to_int(m_vi.group(2))
            if i1 is None:
                i1 = int(m_vi.group(2))
            issues = [i1]
            # Second issue in range (e.g. 九卷第九及十期)
            if m_vi.group(3):
                i2 = _chinese_num_to_int(m_vi.group(3))
                if i2 is None:
                    i2 = int(m_vi.group(3))
                issues.append(i2)
            return (found_pub, vol, issues)

        # Pattern: 仅期号, e.g. 第一期, 第X期
        m_issue = re.search(
            r'(?:第\s*)?([一二三四五六七八九十\d]+)\s*[期号號]',
            rest
        )
        if m_issue:
            i1 = _chinese_num_to_int(m_issue.group(1))
            if i1 is None:
                i1 = int(m_issue.group(1))
            return (found_pub, None, [i1])

        # Pattern: X卷 without 期 (rare)
        m_vol = re.search(
            r'([一二三四五六七八九十\d]+)卷',
            rest
        )
        if m_vol:
            vol = _chinese_num_to_int(m_vol.group(1))
            if vol is None:
                vol = int(m_vol.group(1))
            return (found_pub, vol, None)

        # Found publication name but no volume/issue → still return pub name
        return (found_pub, None, None)

    # ── Fallback: try to match imprint patterns ──
    for imp_pattern in ['印行', '印本', '流通本', '單行本', '出版', '發行']:
        if imp_pattern in text:
            # Extract organization name before the imprint word
            m = re.match(r'(.+?)(?:' + imp_pattern + r')', text)
            if m:
                org = m.group(1).strip()
                # Clean up: remove leading punctuation
                org = re.sub(r'^[，,、。]', '', org).strip()
                if org:
                    return (org, None, None)

    return None


# ── Convenience: parse + lookup in one call ─────────────────────────────

def resolve_publication_date(pub_text):
    """Parse publication text and resolve to a date.

    Args:
        pub_text: raw publication reference text, e.g. '原見海潮音月刊十八卷十一期'

    Returns:
        dict with keys: publication (canonical name), publish_y, publish_m, publish_d,
        and optionally 'unmatched' (str) if reference found but lookup failed.
        Returns None if pub_text contains no recognizable publication reference.
    """
    if not pub_text or not pub_text.strip():
        return None

    parsed = parse_volume_issue(pub_text)
    if parsed is None:
        return None

    pub_name, vol, issues = parsed

    if pub_name is None:
        return None

    # If it's an imprint (no periodical volume/issue), return just the name
    if issues is None and vol is None and pub_name in IMPRINTS:
        return {
            'publication': pub_name,
            'publish_y': '',
            'publish_m': '',
            'publish_d': '',
        }

    # If no volume/issue info, we can still set publication name
    if issues is None or len(issues) == 0:
        return {
            'publication': pub_name,
            'publish_y': '',
            'publish_m': '',
            'publish_d': '',
        }

    # Look up first issue (user confirmed: take the first issue's date)
    first_issue = issues[0]
    date = lookup_date(pub_name, vol, first_issue)

    result = {'publication': pub_name}

    if date is not None:
        result['publish_y'] = date[0]
        result['publish_m'] = date[1]
        result['publish_d'] = date[2]
        result['unmatched'] = None
    else:
        result['publish_y'] = ''
        result['publish_m'] = ''
        result['publish_d'] = ''
        result['unmatched'] = pub_text

    return result


# ── Module init ─────────────────────────────────────────────────────────

_build_lookup()
