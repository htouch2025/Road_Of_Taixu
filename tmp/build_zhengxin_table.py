#!/usr/bin/env python3
"""Build 正信杂志刊载引用对照表 with publication dates from mfqk.db."""
import sqlite3
import re
import os
from collections import OrderedDict

PROJECT_ROOT = "/Users/xin/Documents/Road_Of_Taixu"
DB_PATH = os.path.join(PROJECT_ROOT, "_data/mfqk/mfqk.db")
MD_PATH = os.path.join(PROJECT_ROOT, "tmp/正信杂志_太虚大师全书_刊载引用.md")

# ── Chinese number conversion ──────────────────────────────────
CN_NUMS = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8,
    '九': 9, '十': 10, '十一': 11, '十二': 12, '十三': 13, '十四': 14,
    '十五': 15, '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20,
    '二十一': 21, '二十二': 22, '二十三': 23, '二十四': 24, '二十五': 25,
    '二十六': 26, '二十七': 27, '二十八': 28, '二十九': 29, '三十': 30,
    '三十一': 31, '三十二': 32, '三十三': 33, '三十四': 34, '三十五': 35,
    '三十六': 36, '三十七': 37, '三十八': 38, '三十九': 39, '四十': 40,
    '四十一': 41, '四十二': 42, '四十三': 43, '四十四': 44, '四十五': 45,
    '四十六': 46, '四十七': 47, '四十八': 48, '四十九': 49, '五十': 50,
}

def cn_to_int(s):
    return CN_NUMS.get(s)

def get_journal_name(vol):
    """Determine the actual journal name based on volume number."""
    if 1 <= vol <= 8:
        return '正信'
    elif 9 <= vol <= 10:
        return '正信週刊'
    elif vol == 11:
        return '正信抗戰半月刊'
    else:
        return '正信'

def parse_vol_issue(ref_text):
    """
    Parse a 正信 reference text.
    Returns (journal_name, vol_int, issue_str, is_range, range_end_info)
    where issue_str is '5', '3-4', '15-16', etc.
    For ranges, returns the start issue info plus range_end_info.
    """
    clean = re.sub(r'^[見散載刊]', '', ref_text).strip()
    
    # ── Pattern: Range "正信X卷Y期至X卷Y期" ──
    range_match = re.search(
        r'正信(?:第)?([一二三四五六七八九十]+)卷(?:第)?([一二三四五六七八九十]+)期'
        r'至(?:第)?([一二三四五六七八九十]+)卷(?:第)?([一二三四五六七八九十]+)期',
        clean
    )
    if range_match:
        vol1 = cn_to_int(range_match.group(1))
        iss1 = cn_to_int(range_match.group(2))
        vol2 = cn_to_int(range_match.group(3))
        iss2 = cn_to_int(range_match.group(4))
        if all(v is not None for v in [vol1, iss1, vol2, iss2]):
            jname = get_journal_name(vol1)
            return (jname, vol1, str(iss1), True, (vol2, iss2))
    
    # ── Pattern: Combined issue with two-digit+one-digit "十五六期合刊" ──
    # Check this BEFORE single pattern!
    com2 = re.search(
        r'正信(?:第)?([一二三四五六七八九十]+)卷(?:第)?'
        r'([一二三四五六七八九十]{2})([一二三四五六七八九])期合刊',
        clean
    )
    if com2:
        vol = cn_to_int(com2.group(1))
        iss1 = cn_to_int(com2.group(2))  # e.g., 十五=15
        iss2_digit = cn_to_int(com2.group(3))  # e.g., 六=6
        if vol is not None and iss1 is not None and iss2_digit is not None:
            # 十五六 → 15-16, 十七八 → 17-18, 十三四 → 13-14
            iss_end = (iss1 // 10) * 10 + iss2_digit
            jname = get_journal_name(vol)
            return (jname, vol, f"{iss1}-{iss_end}", False, None)
    
    # ── Pattern: Combined issue with single+single "三四期合刊" or "六七期合刊" ──
    com1 = re.search(
        r'正信(?:第)?([一二三四五六七八九十]+)卷(?:第)?'
        r'([一二三四五六七八九])([一二三四五六七八九])期合刊',
        clean
    )
    if com1:
        vol = cn_to_int(com1.group(1))
        iss1 = cn_to_int(com1.group(2))
        iss2 = cn_to_int(com1.group(3))
        if vol is not None and iss1 is not None and iss2 is not None:
            jname = get_journal_name(vol)
            return (jname, vol, f"{iss1}-{iss2}", False, None)
    
    # ── Pattern: Single issue "正信X卷Y期" ──
    # Must verify the issue number is actually convertible
    single_match = re.search(
        r'正信(?:第)?([一二三四五六七八九十]+)卷(?:第)?([一二三四五六七八九十]+)期',
        clean
    )
    if single_match:
        vol = cn_to_int(single_match.group(1))
        iss = cn_to_int(single_match.group(2))
        if vol is not None and iss is not None:
            jname = get_journal_name(vol)
            return (jname, vol, str(iss), False, None)
    
    return None


def build_lookup_table(db_path):
    """Build a dict: (journal_name, vol_int, issue_int) → publicDate from mfqk.db."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT j.journalName, CAST(p.vol AS INTEGER), p.noFrom, p.noTo, p.publicDate
        FROM publicCode p
        JOIN journal j ON p.jNum = j.jNum
        WHERE j.journalName LIKE '%正信%'
          AND p.publicDate != '0000-00-00'
          AND p.publicDate IS NOT NULL
    """)
    
    lookup = {}
    for journal_name, vol, no_from, no_to, pub_date in cur.fetchall():
        if vol is None:
            continue
        try:
            vol_int = int(vol)
        except (ValueError, TypeError):
            continue
        
        for iss in range(no_from, no_to + 1):
            key = (journal_name, vol_int, iss)
            if key not in lookup:
                lookup[key] = pub_date
    
    conn.close()
    return lookup


def lookup_date(lookup, journal_name, vol, issue_str):
    """
    Look up publication date.
    issue_str can be '5', '3-4', '15-16', etc.
    For combined issues, returns the date of the first issue in the range.
    Returns date string in 'YYYY.MM.DD' format or '—' if not found.
    """
    # Determine the first issue number to look up
    if '-' in issue_str:
        first_iss = int(issue_str.split('-')[0])
    else:
        first_iss = int(issue_str)
    
    # Try exact journal name first
    key = (journal_name, vol, first_iss)
    if key in lookup:
        return lookup[key].replace('-', '.')
    
    # Fallback to '正信'
    if journal_name != '正信':
        key = ('正信', vol, first_iss)
        if key in lookup:
            return lookup[key].replace('-', '.')
    
    return '—'


def extract_unique_refs_from_md(md_path):
    """Extract unique (vol, issue_str) mapping from the markdown reference table."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    refs = OrderedDict()
    for line in content.split('\n'):
        m = re.match(r'\|\s*\d+\s*\|\s*(.+?)\s*\|', line)
        if m:
            ref_text = m.group(1).strip()
            if '正信' in ref_text and ('卷' in ref_text):
                parsed = parse_vol_issue(ref_text)
                if parsed:
                    jname, vol, iss_str, is_range, range_end = parsed[0], parsed[1], parsed[2], parsed[3], parsed[4] if len(parsed) > 4 else None
                    # For dedup, use (vol, issue_str, is_range)
                    dedup_key = (vol, iss_str, is_range)
                    if dedup_key not in refs:
                        refs[dedup_key] = {
                            'ref_text': ref_text,
                            'jname': jname,
                            'vol': vol,
                            'iss_str': iss_str,
                            'is_range': is_range,
                            'range_end': parsed[4] if len(parsed) > 4 and parsed[3] else None,
                        }
    return refs

def cn_vol_issue(vol, iss_str, is_range=False, range_end=None):
    """Convert (vol_int, issue_str) back to Chinese display format."""
    int_to_cn = {v: k for k, v in CN_NUMS.items()}
    vol_cn = int_to_cn.get(vol, str(vol))
    
    if is_range and range_end:
        vol2_cn = int_to_cn.get(range_end[0], str(range_end[0]))
        iss2 = range_end[1]
        return f"{vol_cn}卷{iss_str}期至{vol2_cn}卷{iss2}期"
    elif '-' in iss_str:
        return f"{vol_cn}卷{iss_str}期（合刊）"
    else:
        return f"{vol_cn}卷{iss_str}期"


def main():
    # Build lookup table from DB
    print("Building lookup table from mfqk.db...")
    lookup = build_lookup_table(DB_PATH)
    print(f"  Loaded {len(lookup)} issue-date mappings")
    
    # Extract unique refs from md
    print("Extracting unique 卷期号 from md...")
    unique_refs = extract_unique_refs_from_md(MD_PATH)
    print(f"  Found {len(unique_refs)} unique volume/issue combinations")
    
    # Build 对照表 rows
    table_rows = []
    for (vol, iss_str, is_range), info in unique_refs.items():
        jname = info['jname']
        range_end = info.get('range_end')
        
        date_str = lookup_date(lookup, jname, vol, iss_str)
        
        display = cn_vol_issue(vol, iss_str, is_range, range_end)
        table_rows.append((vol, iss_str, display, date_str, info['ref_text']))
    
    # Sort by volume then first issue number
    def sort_key(row):
        vol, iss_str, _, _, _ = row
        first_iss = int(iss_str.split('-')[0]) if '-' in iss_str else int(iss_str)
        return (vol, first_iss)
    
    table_rows.sort(key=sort_key)
    
    # Read the existing md file
    with open(MD_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the split points
    detail_start = content.find('\n## 详细信息')
    if detail_start == -1:
        detail_start = content.find('\n## 按正信卷期汇总')
    
    if detail_start == -1:
        print("ERROR: Could not find '## 详细信息' or '## 按正信卷期汇总' section")
        return
    
    # Keep the header + 引用列表 (everything before 详细信息)
    header_section = content[:detail_start].rstrip()
    
    # Build 对照表
    crossref_lines = []
    crossref_lines.append("")
    crossref_lines.append("## 正信卷期号与出版时间对照表")
    crossref_lines.append("")
    crossref_lines.append("> 数据来源：民国佛教期刊数据库（`_data/mfqk/mfqk.db`）")
    crossref_lines.append(f"> 共 **{len(table_rows)}** 个唯一卷期号")
    crossref_lines.append("")
    crossref_lines.append("| 卷期号 | 出版时间 | 依据 |")
    crossref_lines.append("|--------|---------|------|")
    
    for vol, iss_str, display, date_str, ref_text in table_rows:
        crossref_lines.append(f"| {display} | {date_str} | mfqk |")
    
    # Combine — ensure blank line between 引用列表 and 对照表
    new_content = header_section + '\n' + '\n'.join(crossref_lines) + '\n'
    
    # Write
    with open(MD_PATH, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"\nOutput written to {MD_PATH}")
    print(f"对照表: {len(table_rows)} rows")
    
    # Print summary
    found = sum(1 for r in table_rows if r[3] != '—')
    missing = sum(1 for r in table_rows if r[3] == '—')
    print(f"  有日期: {found}")
    print(f"  无日期: {missing}")
    if missing > 0:
        print("  缺失项:")
        for r in table_rows:
            if r[3] == '—':
                print(f"    - {r[2]} (原始标注: {r[4]})")
    
    # Print full table
    print("\n--- Full 对照表 ---")
    for _, _, display, date_str, _ in table_rows:
        print(f"  {display} | {date_str}")


if __name__ == '__main__':
    main()
