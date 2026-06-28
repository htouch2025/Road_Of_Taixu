#!/usr/bin/env python3
"""Extract unique publication list from 太虚大师全书刊载信息全录_v2.md.

Parses the v2 markdown file to identify all cited publications, their aliases,
reference counts, and volume/issue ranges. Outputs a structured JSON for the
next stage: building the publication calendar.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def parse_v2_entries(v2_path):
    """Parse v2 markdown into structured entries.

    Returns list of dicts:
      {article, 编, 子目, 编号, type, source_tag, raw_text}
    """
    entries = []
    current_article = None
    current_编 = None
    current_子目 = None
    current_编号 = None

    with open(v2_path, encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        line = line.rstrip('\n')

        # Track section headers (编 headers)
        m_bian = re.match(r'^##\s+第[一二三四五六七八九十廿]+编\s+\S+', line)
        if m_bian:
            current_编 = line.strip('# ').strip()
            continue

        # Article header
        m_article = re.match(r'^###\s+(.+)$', line)
        if m_article:
            current_article = m_article.group(1).strip()
            continue

        # Metadata line: 编/子目/编号
        m_meta = re.match(r'^-\s+\*\*编\*\*：(.+?)　\*\*子目\*\*：(.+?)　\*\*编号\*\*：(\d+)', line)
        if m_meta:
            current_编_short = m_meta.group(1).strip()
            current_子目 = m_meta.group(2).strip()
            current_编号 = m_meta.group(3).strip()
            continue

        # Entry line: - **[type]** [source]（...）：text
        m_entry = re.match(
            r'^-\s+\*\*\[(.+?)\]\*\*\s+\[(.+?)\]\s*(?:（.+?）)?[：:]\s*(.+)$',
            line
        )
        if m_entry:
            entry_type = m_entry.group(1).strip()
            source_tag = m_entry.group(2).strip()
            raw_text = m_entry.group(3).strip()

            entries.append({
                'article': current_article,
                '编': current_编,
                '子目': current_子目,
                '编号': current_编号,
                'type': entry_type,
                'source_tag': source_tag,
                'raw_text': raw_text,
            })

    return entries


# ── Publication name extraction ──────────────────────────────────────────

# Known publication patterns with their canonical names and aliases
# Canonical name first, then aliases
KNOWN_PUBLICATIONS = [
    # Major periodicals
    ('海潮音', ['海潮音', '海潮音月刊', '海刊', '海潮音月 刊', '海 刊',
                  '人海灯', '人海燈']),
    ('觉社丛书', ['覺社叢書', '覺書', '覺刊', '觉社丛书', '觉书', '觉刊']),
    ('正信', ['正信', '正信周刊', '正信半月刊', '正信月刊']),
    ('佛教日报', ['佛教日報', '佛教日报']),
    ('佛化新闻', ['佛化新聞', '佛化新闻']),
    ('觉群周报', ['覺群週報', '覺群周報', '觉群周报', '覺群', '觉群']),
    ('觉有情', ['覺有情', '觉有情']),
    ('现代僧伽', ['現代僧伽', '现代僧伽']),
    ('现代佛教', ['現代佛教', '现代佛教']),
    ('佛学半月刊', ['佛學半月刊', '佛学半月刊']),
    ('净土宗月刊', ['淨土宗月刊', '净土宗月刊']),
    ('中国佛学旬刊', ['中國佛學旬刊', '中国佛学旬刊']),
    ('华南觉音', ['華南覺音', '华南觉音']),
    ('觉音', ['覺音', '觉音']),
    ('佛教月报', ['佛教月報', '佛教月报']),
    ('佛学日报', ['佛學日報', '佛学日报']),
    ('佛学月报', ['佛學月報', '佛学月报']),

    # Secular periodicals
    ('东方杂志', ['東方雜誌', '东方杂志']),
    ('东方文化', ['東方文化', '东方文化']),
    ('宇宙风', ['宇宙風', '宇宙风']),
    ('文化先锋', ['文化先鋒', '文化先锋']),
    ('文艺先锋', ['文藝先鋒', '文艺先锋']),
    ('时代精神', ['時代精神', '时代精神']),
    ('读书通讯', ['讀書通訊', '读书通讯']),
    ('军事与政治', ['軍事與政治', '军事与政治']),
    ('新中华', ['新中華', '新中华']),
    ('民族正气', ['民族正氣', '民族正气']),
    ('黄钟', ['黃鐘', '黄钟']),
    ('道学论衡', ['道學論衡', '道学论衡']),
    ('文史杂志', ['文史雜誌', '文史杂志']),
    ('中流', ['中流']),

    # Newspapers
    ('大公报', ['大公報', '大公报']),
    ('中央日报', ['中央日報', '中央日报']),
    ('益世报', ['益世報', '益世报']),
    ('朝日新闻', ['朝日新聞', '朝日新闻']),
    ('新国民日报', ['新國民日報', '新国民日报']),

    # Buddhist institutional publications
    ('世界佛教居士林林刊', ['世界佛教居士林林刊', '居士林林刊', '林刊',
                             '上海居士林林刊']),
    ('汉藏教理院年刊', ['漢藏教理院年刊', '汉藏教理院年刊',
                         '漢藏教理院開學紀念特刊', '汉藏教理院开学纪念特刊']),
    ('佛化策进会会刊', ['佛化策進會會刊', '佛化策进会会刊']),
    ('廬山學', ['廬山學', '庐山学']),

    # Book series / collections
    ('太虚丛书', ['太虛叢書', '太虚丛书']),
    ('人生佛教', ['人生佛教']),
    ('演说集', ['演說集', '演说集']),
    ('西来讲演集', ['西來講演集', '西来讲演集']),
    ('访问日记', ['訪問日記', '访问日记']),
    ('学僧之路', ['學僧之路', '学僧之路']),
    ('弥陀净土法门集', ['彌陀淨土法門集', '弥陀净土法门集']),
    ('昧庵诗录', ['昧盦詩錄', '昧庵诗录']),
    ('慈航画报', ['慈航畫報', '慈航画报']),

    # Publishing imprints (not periodicals, but treated as publication sources)
    ('佛学书局', ['佛學書局', '佛学书局']),
    ('世界书局', ['世界書局', '世界书局']),
    ('大东书局', ['大東書局', '大东书局']),
    ('中华书局', ['中華書局', '中华书局']),
]

# Build alias → canonical lookup
ALIAS_TO_CANONICAL = {}
for canon, aliases in KNOWN_PUBLICATIONS:
    for alias in aliases:
        ALIAS_TO_CANONICAL[alias.lower()] = canon


def find_publication_in_text(text):
    """Try to identify a known publication in the given text.

    Returns (canonical_name, matched_alias) or (None, None).
    """
    text_lower = text.lower()
    # Sort by length descending to match longer names first
    sorted_aliases = sorted(ALIAS_TO_CANONICAL.keys(), key=len, reverse=True)
    for alias in sorted_aliases:
        if alias.lower() in text_lower:
            return ALIAS_TO_CANONICAL[alias.lower()], alias
    return None, None


def extract_volume_issue_patterns(text):
    """Extract volume/issue references from text.

    Returns list of dicts with {volume, issue, raw_pattern}.
    """
    patterns_found = []

    # Pattern 1: X卷Y期 (Chinese or Arabic numerals)
    # 海刊九卷第九期, 海刊9卷9期, 九卷第九期
    vol_issue = re.findall(
        r'([一二三四五六七八九十廿卅\d]+)\s*卷\s*[第]?([一二三四五六七八九十廿卅\d]+(?:\s*[及和、,\s]\s*[一二三四五六七八九十廿卅\d]+)?)\s*[期号號]',
        text
    )
    for v, i in vol_issue:
        # Handle combined issues like "九及十" or "八九"
        issues = re.findall(r'[一二三四五六七八九十廿卅\d]+', i)
        patterns_found.append({
            'volume': v.strip(),
            'issue': [x.strip() for x in issues],
            'raw': f'{v}卷{i}期',
        })

    # Pattern 2: X年第Y期 (less common)
    yr_issue = re.findall(
        r'[第]?([一二三四五六七八九十廿卅\d]+)\s*年\s*[第]?([一二三四五六七八九十廿卅\d]+)\s*[期号號]',
        text
    )
    for y, i in yr_issue:
        patterns_found.append({
            'year_ref': y.strip(),
            'issue': [i.strip()],
            'raw': f'{y}年第{i}期',
        })

    # Pattern 3: X卷Y号
    vol_hao = re.findall(
        r'([一二三四五六七八九十廿卅\d]+)\s*卷\s*[第]?([一二三四五六七八九十廿卅\d]+)\s*[号號]',
        text
    )
    for v, h in vol_hao:
        patterns_found.append({
            'volume': v.strip(),
            'issue': [h.strip()],
            'raw': f'{v}卷第{h}号',
        })

    # Pattern 4: 第X期 (issue only, no volume)
    issue_only = re.findall(
        r'(?<![卷年\d])[第]([一二三四五六七八九十廿卅\d]+)\s*[期号號]',
        text
    )
    for i in issue_only:
        if i.strip() not in [p.get('issue', [''])[0] for p in patterns_found]:
            patterns_found.append({
                'issue': [i.strip()],
                'raw': f'第{i}期',
            })

    return patterns_found


def extract_date_embedded_patterns(text):
    """Extract embedded dates like 二四，七，一八 (民国YY, MM, DD).

    Returns list of raw date strings found.
    """
    # Pattern: 民国/民 + 数字 + 年
    dates = re.findall(r'[民民國][國国]?\s*[\d一二三四五六七八九十廿卅]{1,3}\s*年', text)

    # Pattern: abbreviated 数字，数字，数字
    abbreviated = re.findall(
        r'[\d一二三四五六七八九十廿卅]{1,3}[，,]\s*[\d一二三四五六七八九十廿卅]{1,2}[，,]\s*[\d一二三四五六七八九十廿卅]{1,2}',
        text
    )
    dates.extend(abbreviated)
    return dates


# ── Main extraction ─────────────────────────────────────────────────────

def extract_publications(v2_path):
    """Extract all publication references from v2 markdown.

    Returns:
      dict with keys:
        - publications: canonical_name → {aliases, count, entries, volume_issue_patterns}
        - unrecognized: list of texts where no known publication was found
        - stats: summary statistics
    """
    entries = parse_v2_entries(v2_path)

    # Only process relevant entry types
    relevant_types = {'刊载出处', '综合', '出处说明', '印行信息'}
    relevant_entries = [e for e in entries if e['type'] in relevant_types]

    pubs = defaultdict(lambda: {
        'aliases': set(),
        'count': 0,
        'entries': [],
        'vol_issue_patterns': [],
        'date_embedded': [],
    })
    unrecognized = []

    for entry in relevant_entries:
        text = entry['raw_text']
        canon, alias = find_publication_in_text(text)

        if canon:
            pub = pubs[canon]
            pub['aliases'].add(alias)
            pub['count'] += 1
            pub['entries'].append({
                'article': entry['article'],
                '编': entry['编'],
                'raw_text': text[:200],  # truncate long texts
            })

            # Extract volume/issue patterns
            vi = extract_volume_issue_patterns(text)
            if vi:
                pub['vol_issue_patterns'].extend(vi)

            # Extract date-embedded patterns
            de = extract_date_embedded_patterns(text)
            if de:
                pub['date_embedded'].extend(de)
        else:
            # Check if it might be a publication reference we don't know about
            if re.search(r'[見见原].*[刊报報叢书書集鈔钞誌志月周旬期]', text):
                unrecognized.append({
                    'article': entry['article'],
                    '编': entry['编'],
                    'raw_text': text[:200],
                })

    # Convert sets to lists for JSON
    result = {}
    for canon, data in sorted(pubs.items(), key=lambda x: -x[1]['count']):
        result[canon] = {
            'aliases': sorted(data['aliases']),
            'count': data['count'],
            'entries': data['entries'][:10],  # Keep first 10 examples
            'vol_issue_patterns': data['vol_issue_patterns'][:50],  # Keep up to 50
            'date_embedded': data['date_embedded'][:20],
        }

    stats = {
        'total_relevant_entries': len(relevant_entries),
        'entries_matched': sum(1 for e in relevant_entries
                               if find_publication_in_text(e['raw_text'])[0]),
        'entries_unmatched': len(unrecognized),
        'unique_publications': len(result),
    }

    return {
        'publications': result,
        'unrecognized': unrecognized[:100],
        'stats': stats,
    }


def main():
    v2_path = Path(__file__).parent.parent.parent.parent / '_research' / '太虚大师全书刊载信息全录_v2.md'
    output_path = Path(__file__).parent.parent.parent.parent / '_research' / 'publication_list_raw.json'

    if not v2_path.exists():
        print(f'Error: v2 file not found at {v2_path}')
        sys.exit(1)

    print(f'Parsing {v2_path}...')
    result = extract_publications(str(v2_path))

    # Print summary
    stats = result['stats']
    print(f"\n=== Summary ===")
    print(f"Total relevant entries (刊载出处+综合+出处说明+印行信息): {stats['total_relevant_entries']}")
    print(f"Entries matched to known publications: {stats['entries_matched']}")
    print(f"Entries unmatched: {stats['entries_unmatched']}")
    print(f"Unique publications found: {stats['unique_publications']}")

    print(f"\n=== Publications by frequency ===")
    for i, (name, data) in enumerate(
        sorted(result['publications'].items(), key=lambda x: -x[1]['count'])
    ):
        aliases_str = ' / '.join(a for a in data['aliases'] if a != name)
        alias_info = f"  (aliases: {aliases_str})" if aliases_str else ''
        print(f"  {i+1:3d}. {name}: {data['count']} refs{alias_info}")

    # Print unmatched
    if result['unrecognized']:
        print(f"\n=== Top unrecognized entries (first 20) ===")
        for u in result['unrecognized'][:20]:
            print(f"  [{u['编']}] {u['article']}: {u['raw_text'][:120]}")

    # Save output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nFull results saved to {output_path}")


if __name__ == '__main__':
    main()
