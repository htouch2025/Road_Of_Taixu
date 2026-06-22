#!/usr/bin/env python3
"""Extract 编级篇名目录 (level 1-2 only) from CBETA TX XML files,
with enriched JSON including mulu indices, prev/next linked list,
byte-level file offsets, byline extraction, and 子目内编号.

Usage:
  python extract_book_catalog.py _data/cbeta/TX/TX01/TX01n0001.xml \
      _data/cbeta/TX/TX02/TX02n0001.xml \
      --book "第一编 佛法總學" --out-dir _research/01_佛法總學
"""

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

CBETA_NS = 'http://www.cbeta.org/ns/1.0'
TEI_NS = 'http://www.tei-c.org/ns/1.0'

from _utils import chinese_to_int, normalize_byline, split_month_season, build_suffix


def extract_article_byline(xml_path, byte_start, byte_end):
    """Extract byline from the head area of an article using byte range.

    Reads up to 5000 bytes from byte_start, searches for <byline> and
    <note> elements containing 見海刊.
    """
    with open(xml_path, 'rb') as f:
        f.seek(byte_start)
        max_read = min(5000, byte_end - byte_start)
        chunk = f.read(max_read)
    text = chunk.decode('utf-8', errors='replace')

    # Primary: <byline> element
    byline_m = re.findall(r'<byline[^>]*>(.*?)</byline>', text, re.DOTALL)
    if byline_m:
        raw = re.sub(r'<[^>]+>', '', byline_m[0]).strip()
        return normalize_byline(raw)

    return ''


def scan_byte_offsets(xml_path):
    """Scan raw file to find byte positions of each article's inner cb:div.

    Each article lives in an inner <cb:div> that directly contains a
    level-2 <cb:mulu>. We locate the mulu tag, then search backward for
    the parent <cb:div opening.

    Returns list of {byte_start, byte_end} per article, in file order.
    """
    raw = Path(xml_path).read_bytes()

    # Find all <cb:mulu level="2" positions
    mulu_positions = []
    for m in re.finditer(rb'<cb:mulu[^>]*level="2"[^>]*>', raw):
        mulu_positions.append(m.start())

    # For each mulu, find the parent <cb:div opening
    div_starts = []
    for pos in mulu_positions:
        # Search backward up to 200 bytes for <cb:div
        search_start = max(0, pos - 200)
        before = raw[search_start:pos]
        last_div = before.rfind(b'<cb:div')
        div_start = search_start + last_div if last_div != -1 else pos
        div_starts.append(div_start)

    # Build byte ranges: depth-track each <cb:div> to its matching </cb:div>
    def find_div_end(raw_bytes, div_start):
        """Scan forward from div_start to find the matching </cb:div>."""
        depth = 1
        pos = raw_bytes.index(b'>', div_start) + 1
        while depth > 0 and pos < len(raw_bytes):
            nxt_open = raw_bytes.find(b'<cb:div', pos)
            nxt_close = raw_bytes.find(b'</cb:div>', pos)
            if nxt_close == -1:
                return len(raw_bytes)
            if nxt_open != -1 and nxt_open < nxt_close:
                depth += 1
                pos = raw_bytes.index(b'>', nxt_open) + 1
            else:
                depth -= 1
                pos = nxt_close + len(b'</cb:div>')
        return pos

    byte_ranges = []
    for i, start in enumerate(div_starts):
        end = find_div_end(raw, start)
        byte_ranges.append({'byte_start': start, 'byte_end': end})

    # ── Consistency validation: adjacent-article boundary check ──
    for i in range(len(byte_ranges) - 1):
        gap = byte_ranges[i + 1]['byte_start'] - byte_ranges[i]['byte_end']
        if gap < 0:
            print(f'   ⚠️  第{i+1}篇 byte_end ({byte_ranges[i]["byte_end"]}) '
                  f'超出第{i+2}篇 byte_start ({byte_ranges[i+1]["byte_start"]}) '
                  f'— 深度追蹤可能 overshoot（多了 {-gap} bytes）')
        elif gap > 500:
            print(f'   ⚠️  第{i+1}篇 byte_end={byte_ranges[i]["byte_end"]} '
                  f'第{i+2}篇 byte_start={byte_ranges[i+1]["byte_start"]} '
                  f'— 間距 {gap} bytes，超出同文件正常範圍（~106 bytes）')

    return byte_ranges


def extract_catalog(xml_paths):
    """Extract enriched level 1-2 mulu entries from XML files.

    Returns (entries, file_map).
    entries[i] = {子目, 篇名, cbeta_id, mulu_index, file_index,
                  byte_start, byte_end, 題注}
    file_map[i] = {file, lb_start, lb_end, lb_count}
    """
    entries = []
    file_map = []
    current_section = None
    global_mulu_idx = 0

    for fi, xml_path in enumerate(xml_paths):
        xml_path = Path(xml_path)
        tree = ET.parse(str(xml_path))
        root = tree.getroot()

        cbeta_id = xml_path.stem

        # Extract body's tei:lb range
        body = root.find(f'.//{{{TEI_NS}}}text/{{{TEI_NS}}}body')
        tei_lbs = body.findall(f'.//{{{TEI_NS}}}lb') if body is not None else []
        lb_start = tei_lbs[0].get('n') if tei_lbs else None
        lb_end = tei_lbs[-1].get('n') if tei_lbs else None

        file_info = {
            'file': cbeta_id + '.xml',
            'lb_start': lb_start,
            'lb_end': lb_end,
            'lb_count': len(tei_lbs),
        }

        # Scan byte offsets for this file
        byte_ranges = scan_byte_offsets(xml_path)

        # Parse XML mulu entries
        mulu_elems = root.findall(f'.//{{{CBETA_NS}}}mulu')

        article_count = 0  # per-file article index for byte ranges
        for m in mulu_elems:
            level = int(m.get('level', '0'))
            if level > 2:
                global_mulu_idx += 1
                continue
            text = ''.join(m.itertext()).strip()
            if level == 1:
                current_section = text
            elif level == 2:
                br = byte_ranges[article_count]
                byline = extract_article_byline(xml_path, br['byte_start'], br['byte_end'])
                entries.append({
                    '子目': current_section,
                    '篇名': text,
                    'cbeta_id': cbeta_id,
                    'mulu_index': global_mulu_idx,
                    'file_index': fi,
                    'byte_start': br['byte_start'],
                    'byte_end': br['byte_end'],
                    '題注': byline,
                })
                article_count += 1
            global_mulu_idx += 1

        file_map.append(file_info)

    return entries, file_map


def build_md(entries, book_name):
    """Build Markdown catalog in - nested-list format with 编内连续编号."""
    # Build section → article list (preserve order)
    by_section = {}
    for e in entries:
        by_section.setdefault(e['子目'], []).append(e)

    lines = [f'# {book_name} 篇名目錄', '',
             '## 篇目']
    lines.append('')
    lines.append(f'- {book_name}')
    global_idx = 1
    for i, (sec, arts) in enumerate(by_section.items(), 1):
        lines.append(f'    - {i}. {sec}')
        for art in arts:
            lines.append(f'        - {global_idx}. {art["篇名"]}')
            global_idx += 1
    lines.extend(['', '## 篇數統計', '',
             '| 子目 | 篇數 |',
             '|------|------|'])
    total = 0
    for i, (sec, arts) in enumerate(by_section.items(), 1):
        lines.append(f'| {sec} | {len(arts)} |')
        total += len(arts)
    lines.append(f'| **合計** | **{total}** |')
    lines.append('')
    return '\n'.join(lines)


def build_json(entries, book_name, book_num, file_map):
    """Build enriched JSON catalog with byte offsets, linked list, and 子目内编号."""
    # Compute 子目内编号
    sub_counter = {}
    for e in entries:
        sec = e['子目']
        sub_counter.setdefault(sec, 0)
        sub_counter[sec] += 1
        e['_sub_num'] = sub_counter[sec]

    # Build sub-category stats
    by_section = {}
    for e in entries:
        by_section.setdefault(e['子目'], []).append(e)

    article_list = []
    for i, e in enumerate(entries):
        article_list.append({
            '編號': i + 1,
            '篇名': e['篇名'],
            '子目': e['子目'],
            '子目內編號': e['_sub_num'],
            '題注': e.get('題注', ''),
            'file': e['cbeta_id'] + '.xml',
            'mulu_index': e['mulu_index'],
            'byte_start': e['byte_start'],
            'byte_end': e['byte_end'],
            'byte_size': e['byte_end'] - e['byte_start'],
            'prev': entries[i - 1]['篇名'] if i > 0 else None,
            'next': entries[i + 1]['篇名'] if i < len(entries) - 1 else None,
            'prev_index': entries[i - 1]['mulu_index'] if i > 0 else None,
            'next_index': entries[i + 1]['mulu_index'] if i < len(entries) - 1 else None,
        })

    return {
        '编': book_name,
        '编序号': book_num,
        '來源文件': file_map,
        '子目': [
            {'名稱': sec, '篇數': len(arts),
             '篇名': [a['篇名'] for a in arts]}
            for sec, arts in by_section.items()
        ],
        '篇目總數': len(entries),
        '篇目鏈表': article_list,
    }


def build_dashboard(book_name, out_dir):
    """Generate 仪表盘 Dataview dashboard Markdown for the 编."""
    template_path = Path(__file__).parent.parent / 'templates' / 'book_dashboard.md'
    template = template_path.read_text(encoding='utf-8')
    return template.format(book_name=book_name, out_dir=out_dir)

def main():
    parser = argparse.ArgumentParser(
        description='Extract 编级篇名目录 with byte offsets from CBETA TX XML')
    parser.add_argument('xml_files', nargs='+', help='TX XML file paths')
    parser.add_argument('--book', required=True, help='编名')
    parser.add_argument('--book-num', type=int, default=1, help='编序号')
    parser.add_argument('--out-dir', default=None, help='Output directory (auto: _research/{book-num:02d}_{book-suffix})')
    parser.add_argument('--prefix', default=None, help='Output filename prefix (auto: _{out_dir_basename}_編目錄)')
    args = parser.parse_args()

    if args.out_dir is None:
        book_parts = args.book.split(None, 1)
        bian_suffix = bian_parts[1] if len(bian_parts) > 1 else args.book
        args.out_dir = f'_research/{args.book_num:02d}_{bian_suffix}'

    entries, file_map = extract_catalog(args.xml_files)

    md_text = build_md(entries, args.book)
    json_data = build_json(entries, args.book, args.book_num, file_map)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.prefix is None:
        basename = out_dir.name
        args.prefix = f'_{basename}_編目錄'

    md_path = out_dir / f'{args.prefix}.md'
    json_path = out_dir / f'{args.prefix}.json'

    md_path.write_text(md_text, encoding='utf-8')
    json_path.write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

    # Generate dashboard
    dashboard_text = build_dashboard(args.book, args.out_dir)
    dashboard_path = out_dir / f'_{basename}_仪表盘.md'
    dashboard_path.write_text(dashboard_text, encoding='utf-8')

    print(f'✅ 仪表盘 → {dashboard_path}')
    print(f'✅ MD   → {md_path}')
    print(f'✅ JSON → {json_path}')
    print(f'   {len(entries)} 篇文章, {len(set(e["子目"] for e in entries))} 個子目')
    for fm in file_map:
        print(f'   📄 {fm["file"]}: tei:lb {fm["lb_start"]} → {fm["lb_end"]} ({fm["lb_count"]} 行)')
    print(f'   📏 byte offsets: 第1篇 {entries[0]["byte_start"]} → 末篇 {entries[-1]["byte_end"]}')


if __name__ == '__main__':
    main()
