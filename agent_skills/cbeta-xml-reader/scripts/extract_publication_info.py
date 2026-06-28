#!/usr/bin/env python3
"""Extract all 文末刊载信息 from CBETA TX XML files for the 太虚大师全书.

Scans all 20 编 catalogs, reads each article's XML chunk, and extracts
end-of-article metadata from four locations:
  1. <byline cb:type="*"> — all byline content
  2. <note place="inline"> — inline notes (inside and outside bylines)
  3. （附註） paragraphs — styled editorial notes
  4. <note place="foot text" type="orig"> — back-section foot notes

Output: _research/太虚大师全书刊载信息全录_v2.md

Usage:
  python3 extract_publication_info.py
  python3 extract_publication_info.py --verbose  # show per-article progress
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

# Add scripts dir to path for _utils import
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from _utils import (
    extract_all_byline_info,
    extract_inline_notes,
    extract_fuzhu_paragraphs,
    extract_back_notes_for_article,
)

CBETA_NS = 'http://www.cbeta.org/ns/1.0'
TEI_NS = 'http://www.tei-c.org/ns/1.0'

# ── Helpers ────────────────────────────────────────────────────────────

def find_catalog_json_files(research_dir):
    """Find all _{編名}_編目錄.json files under research_dir."""
    research_path = Path(research_dir)
    catalogs = []
    for d in sorted(research_path.iterdir()):
        if d.is_dir() and re.match(r'\d{2}_', d.name):
            for f in d.glob('_*_編目錄.json'):
                catalogs.append(f)
    return sorted(catalogs)


def load_catalog(catalog_path):
    """Load a catalog JSON file, return (book_name, book_number, articles)."""
    with open(catalog_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    book_name = data.get('编', '')
    book_number = data.get('编序号', 0)

    # Extract articles from the linked list
    articles = []
    if '篇目鏈表' in data:
        for entry in data['篇目鏈表']:
            articles.append({
                '篇名': entry.get('篇名', ''),
                '子目': entry.get('子目', ''),
                '編號': entry.get('編號', entry.get('子目內編號', '')),
                'file': entry.get('file', ''),
                'byte_start': entry.get('byte_start', 0),
                'byte_end': entry.get('byte_end', 0),
            })
    return book_name, book_number, articles


def get_all_xml_files(data_dir):
    """Build mapping of filename → full path for all TX XML files."""
    xml_map = {}
    data_path = Path(data_dir)
    for xml_file in data_path.rglob('TX*.xml'):
        xml_map[xml_file.name] = str(xml_file)
    return xml_map


def parse_article_chunk(file_path, byte_start, byte_end):
    """Read and parse an article's XML chunk, return the root element.

    Since byte offsets may fall inside XML tags, we scan forward to the first
    complete '<' character and strip any orphaned attribute text.
    """
    try:
        with open(file_path, 'rb') as f:
            f.seek(byte_start)
            chunk = f.read(byte_end - byte_start).decode('utf-8', errors='replace')
    except Exception:
        return None

    # Scan forward to the first '<' that starts a complete element
    lt_pos = chunk.find('<')
    if lt_pos > 0:
        chunk = chunk[lt_pos:]

    # Wrap in a root element for parsing with both TEI and CBETA namespaces
    try:
        wrapped = f'<root xmlns="{TEI_NS}" xmlns:cb="{CBETA_NS}">{chunk}</root>'
        root = ET.fromstring(wrapped)
        return root
    except ET.ParseError:
        try:
            wrapped = f'<root>{chunk}</root>'
            root = ET.fromstring(wrapped)
            return root
        except ET.ParseError:
            return None


def extract_article_info(file_path, byte_start, byte_end):
    """Extract all end-of-article info from an article's XML chunk.

    Returns dict with all_items, byline_items, inline_note_items, fuzhu_items, foot_note_items.
    """
    result = {
        'all_items': [],
        'byline_items': [],
        'inline_note_items': [],
        'fuzhu_items': [],
        'foot_note_items': [],
    }

    root = parse_article_chunk(file_path, byte_start, byte_end)
    if root is None:
        return result

    # Pass 1: byline content
    byline_items = extract_all_byline_info(root, TEI_NS, CBETA_NS)
    result['byline_items'] = byline_items
    result['all_items'].extend(byline_items)

    # Pass 2: inline notes
    inline_items = extract_inline_notes(root, TEI_NS)
    # Deduplicate against byline items (inline notes inside bylines are
    # captured by both passes)
    byline_texts = {item['raw_text'] for item in byline_items}
    deduped_inline = [item for item in inline_items if item['raw_text'] not in byline_texts]
    result['inline_note_items'] = deduped_inline
    result['all_items'].extend(deduped_inline)

    # Pass 3: 附註 paragraphs
    fuzhu_items = extract_fuzhu_paragraphs(root, TEI_NS)
    result['fuzhu_items'] = fuzhu_items
    result['all_items'].extend(fuzhu_items)

    # Pass 4: foot notes (need to read full file, done externally)
    # Handled separately by the caller

    return result


# ── Markdown Output ────────────────────────────────────────────────────

def render_markdown(all_results, stats):
    """Render the complete Markdown output."""
    lines = []
    lines.append('# 太虚大师全书 文末信息全录（完整版 v2）')
    lines.append('')
    lines.append(f'> 扫描日期：2026-06-28')
    lines.append(f'> 数据来源：CBETA TEI P5 XML（TX00–TX32），共 40 个文件')
    lines.append(f'> 提取范围：byline 全部内容、inline note 全部内容、附註段落、篇末注')
    lines.append(f'> 总条数：{stats["total_items"]} 条（覆盖 {stats["articles_with_info"]}/{stats["total_articles"]} 篇文章）')
    lines.append('')
    lines.append('---')
    lines.append('')

    # ── Classification overview ──
    lines.append('## 分类总览')
    lines.append('')
    lines.append('| 类型 | 条数 | 占比 |')
    lines.append('|------|------|------|')
    total = stats['total_items']
    for type_name, count in stats['type_counts'].most_common():
        pct = f'{count / total * 100:.1f}%' if total > 0 else '0%'
        lines.append(f'| {type_name} | {count} | {pct} |')
    lines.append('')

    # Source tag distribution
    lines.append('| 来源位置 | 条数 | 占比 |')
    lines.append('|----------|------|------|')
    for tag, count in stats['source_counts'].most_common():
        pct = f'{count / total * 100:.1f}%' if total > 0 else '0%'
        lines.append(f'| {tag} | {count} | {pct} |')
    lines.append('')

    # Byline type distribution
    if stats['byline_type_counts']:
        lines.append('| byline cb:type | 条数 |')
        lines.append('|-----------------|------|')
        for bt, count in stats['byline_type_counts'].most_common():
            lines.append(f'| {bt} | {count} |')
        lines.append('')

    lines.append('---')
    lines.append('')

    # ── Per-编 sections ──
    for book_name, book_data in all_results:
        lines.append(f'## {book_name}')
        lines.append('')

        book_total = sum(len(a['all_items']) for a in book_data['articles'] if a['all_items'])
        articles_with = sum(1 for a in book_data['articles'] if a['all_items'])
        articles_without = sum(1 for a in book_data['articles'] if not a['all_items'])
        lines.append(f'> {articles_with} 篇文章有文末信息，{articles_without} 篇无，共 {book_total} 条')
        lines.append('')

        for article in book_data['articles']:
            if not article['all_items'] and not article['foot_note_items']:
                continue  # Skip articles with no info at all

            # Combine all items (deduplicated)
            all_raw_texts = set()
            display_items = []

            for item in article['all_items']:
                if item['raw_text'] not in all_raw_texts:
                    all_raw_texts.add(item['raw_text'])
                    display_items.append(item)

            for item in article['foot_note_items']:
                if item['raw_text'] not in all_raw_texts:
                    all_raw_texts.add(item['raw_text'])
                    display_items.append(item)

            if not display_items:
                continue

            # Article header
            lines.append(f"### {article['篇名']}")
            lines.append('')
            lines.append(f"- **编**：{book_name}　**子目**：{article['子目']}　**编号**：{article['編號']}")
            lines.append('')

            for item in display_items:
                type_label = item['type']
                source = item['source_tag']
                raw = item['raw_text']

                # Build extra info string
                extras = []
                if 'byline_type' in item and item['byline_type'] != 'none':
                    extras.append(f'cb:type="{item["byline_type"]}"')
                if 'note_n' in item:
                    extras.append(f'注号：{item["note_n"]}')
                if 'target' in item:
                    extras.append(f'target：{item["target"]}')

                extra_str = f'（{", ".join(extras)}）' if extras else ''

                lines.append(f'- **[{type_label}]** [{source}]{extra_str}：{raw}')
                lines.append('')

    # ── Articles with no info ──
    lines.append('---')
    lines.append('')
    lines.append('## 无文末信息的文章')
    lines.append('')
    for book_name, book_data in all_results:
        missing = [a for a in book_data['articles'] if not a['all_items'] and not a['foot_note_items']]
        if missing:
            lines.append(f'### {book_name}（{len(missing)} 篇）')
            lines.append('')
            for a in missing:
                lines.append(f'- {a["篇名"]}（子目：{a["子目"]}，编号：{a["編號"]}）')
            lines.append('')

    return '\n'.join(lines)


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Extract all 文末刊载信息 from CBETA TX XML files'
    )
    parser.add_argument(
        '--data-dir', default='_data/cbeta/TX',
        help='Path to _data/cbeta/TX directory'
    )
    parser.add_argument(
        '--research-dir', default='_research',
        help='Path to _research directory'
    )
    parser.add_argument(
        '--output', default='_research/太虚大师全书刊载信息全录_v2.md',
        help='Output Markdown file path'
    )
    parser.add_argument(
        '--verbose', action='store_true',
        help='Show per-article progress'
    )
    args = parser.parse_args()

    # Resolve paths relative to project root
    # Script is at agent_skills/cbeta-xml-reader/scripts/ → up 3 levels to project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
    data_dir = os.path.join(project_root, args.data_dir)
    research_dir = os.path.join(project_root, args.research_dir)
    output_path = os.path.join(project_root, args.output)

    # Find catalog files
    catalog_files = find_catalog_json_files(research_dir)
    if not catalog_files:
        print('ERROR: No catalog JSON files found.')
        sys.exit(1)

    print(f'Found {len(catalog_files)} catalog files')

    # Build XML file map
    xml_map = get_all_xml_files(data_dir)
    print(f'Found {len(xml_map)} XML files')

    # Statistics
    stats = {
        'total_articles': 0,
        'articles_with_info': 0,
        'total_items': 0,
        'type_counts': Counter(),
        'source_counts': Counter(),
        'byline_type_counts': Counter(),
    }

    all_results = []  # [(book_name, book_data), ...]

    for cat_path in catalog_files:
        book_name, book_number, articles = load_catalog(cat_path)
        if args.verbose:
            print(f'\n{"="*60}')
            print(f'{book_name} ({len(articles)} articles)')
            print(f'{"="*60}')

        book_data = {
            'book_name': book_name,
            'book_number': book_number,
            'articles': [],
        }

        for i, article in enumerate(articles):
            stats['total_articles'] += 1

            filename = article['file']
            file_path = xml_map.get(filename)
            if not file_path:
                if args.verbose:
                    print(f'  [{i+1}/{len(articles)}] SKIP {article["篇名"]}: file {filename} not found')
                article['all_items'] = []
                article['byline_items'] = []
                article['inline_note_items'] = []
                article['fuzhu_items'] = []
                article['foot_note_items'] = []
                book_data['articles'].append(article)
                continue

            byte_start = article['byte_start']
            byte_end = article['byte_end']

            # Extract from XML chunk
            info = extract_article_info(file_path, byte_start, byte_end)

            # Pass 4: foot notes (uses full file path)
            foot_notes = extract_back_notes_for_article(file_path, byte_start, byte_end)
            info['foot_note_items'] = foot_notes

            article['all_items'] = info['all_items']
            article['byline_items'] = info['byline_items']
            article['inline_note_items'] = info['inline_note_items']
            article['fuzhu_items'] = info['fuzhu_items']
            article['foot_note_items'] = info['foot_note_items']

            total_article_items = len(info['all_items']) + len(foot_notes)
            if total_article_items > 0:
                stats['articles_with_info'] += 1
                stats['total_items'] += total_article_items

                # Update counters
                for item in info['all_items']:
                    stats['type_counts'][item['type']] += 1
                    stats['source_counts'][item['source_tag']] += 1
                    if 'byline_type' in item:
                        stats['byline_type_counts'][item['byline_type']] += 1
                for item in foot_notes:
                    stats['type_counts'][item['type']] += 1
                    stats['source_counts'][item['source_tag']] += 1

            if args.verbose:
                count_str = f'{total_article_items} items' if total_article_items > 0 else 'no items'
                print(f'  [{i+1}/{len(articles)}] {article["篇名"]}: {count_str}')

            book_data['articles'].append(article)

        all_results.append((book_name, book_data))

    # ── Generate output ──
    print(f'\n{"="*60}')
    print(f'Total: {stats["total_articles"]} articles, '
          f'{stats["articles_with_info"]} with info, '
          f'{stats["total_items"]} items')
    print(f'Writing to {output_path}...')

    md_content = render_markdown(all_results, stats)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f'Done! Output: {output_path}')
    print(f'Size: {len(md_content):,} chars, {md_content.count(chr(10))+1:,} lines')


if __name__ == '__main__':
    main()
