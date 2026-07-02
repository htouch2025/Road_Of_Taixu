#!/usr/bin/env python3
"""Add YAML frontmatter to existing extracted articles and rename to 編號 prefix.

For each article in a 编级 JSON catalog:
1. Locate the existing .md file (old naming: {子目內編號}_{篇名}.md)
2. Prepend YAML frontmatter with structured metadata
3. Rename to new naming: {編號}_{篇名}.md

Usage:
  python add_frontmatter_to_existing.py _research/01_佛法總學/_01_佛法總學_編目錄.json
"""

import argparse
import json
from pathlib import Path

from _utils import parse_byline_fields


def build_frontmatter(entry, book_name, book_number):
    """Build YAML frontmatter string from catalog entry.

    Note: publication/publish_* fields are NOT populated by this migration
    script (requires XML access). They are only set during fresh extraction
    via extract_article_fulltext.py.
    """
    byline = entry.get('題注', '')
    fields = parse_byline_fields(byline)

    yaml_lines = ['---']
    yaml_lines.append(f"book: {book_name}")
    yaml_lines.append(f"book_number: {book_number}")
    yaml_lines.append(f"category: {entry.get('子目', '')}")
    yaml_lines.append(f"sequence: {entry.get('編號', 0)}")
    wc = entry.get('字数') or 0
    yaml_lines.append(f"word_count: {wc // 1000}")
    yaml_lines.append(f"location: {fields['location']}")
    yaml_lines.append(f"create_y: {fields['create_y']}")
    yaml_lines.append(f"create_m: {fields['create_m']}")
    yaml_lines.append(f"create_d: {fields['create_d']}")
    yaml_lines.append('concepts:')
    yaml_lines.append('domains:')
    yaml_lines.append('functions:')
    yaml_lines.append('bearings:')
    yaml_lines.append('---')
    yaml_lines.append('')
    return '\n'.join(yaml_lines)


def main():
    parser = argparse.ArgumentParser(
        description='Add YAML frontmatter to existing articles + rename to 編號 prefix')
    parser.add_argument('catalog_json', help='Path to 编级 JSON catalog')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without writing')
    args = parser.parse_args()

    json_path = Path(args.catalog_json)
    with open(json_path, encoding='utf-8') as f:
        catalog = json.load(f)

    book_name = catalog.get('编', '')
    book_number = catalog.get('编序号', 0)
    base_dir = json_path.parent

    renamed = 0
    frontmattered = 0
    skipped = 0

    # Build zi_mu → index map for subdirectory names
    zi_mu_map = {}
    for i, zm in enumerate(catalog.get('子目', [])):
        zi_mu_map[zm['名稱']] = i + 1

    for entry in catalog.get('篇目鏈表', []):
        zi_mu = entry.get('子目', '')
        zi_mu_idx = zi_mu_map.get(zi_mu, 0)
        sub_dir = base_dir / f'{zi_mu_idx:02d}_{zi_mu}'

        old_num = entry.get('子目內編號', 0)
        new_num = entry.get('編號', 0)
        article_name = entry.get('篇名', '')

        old_path = sub_dir / f'{old_num:02d}_{article_name}.md'
        new_path = sub_dir / f'{new_num:02d}_{article_name}.md'

        if not old_path.exists():
            print(f'  ⚠️  跳过 (文件不存在): {old_path}')
            skipped += 1
            continue

        # Read existing content
        content = old_path.read_text(encoding='utf-8')

        # Skip if already has frontmatter
        if content.startswith('---'):
            print(f'  ⚠️  跳过 (已有 frontmatter): {old_path.name}')
            skipped += 1
            continue

        # Build frontmatter
        fm = build_frontmatter(entry, book_name, book_number)
        new_content = fm + content

        if args.dry_run:
            if old_path != new_path:
                print(f'  📝 [DRY] {old_path.name} → {new_path.name} (+frontmatter)')
            else:
                print(f'  📝 [DRY] {old_path.name} (+frontmatter)')
            renamed += 1
            frontmattered += 1
        else:
            # Write with frontmatter to new path
            new_path.write_text(new_content, encoding='utf-8')

            # If path changed, remove old file
            if old_path != new_path:
                old_path.unlink()
                print(f'  ✅ 重命名: {old_path.name} → {new_path.name}')
            else:
                print(f'  ✅ 加 frontmatter: {new_path.name}')
            renamed += 1
            frontmattered += 1

    print(f'\n📊 总计: {frontmattered} 篇已处理, {skipped} 篇跳过')


if __name__ == '__main__':
    main()
