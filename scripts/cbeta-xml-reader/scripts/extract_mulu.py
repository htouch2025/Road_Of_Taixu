#!/usr/bin/env python3
"""Extract cb:mulu directory structure from CBETA TEI P5 XML.

Usage:
  python extract_mulu.py <xml_file> [--max-level N] [--format tree|csv|flat]
  python extract_mulu.py --text "<cb:mulu ...>...</cb:mulu>" [--max-level N]

Output modes:
  tree  - indented tree (default)
  csv   - level,text CSV
  flat  - one entry per line with level prefix
"""

import re
import sys
import argparse
from pathlib import Path


def parse_mulu(text):
    """Parse all cb:mulu elements from CBETA XML text."""
    pattern = re.compile(
        r'<cb:mulu\s+[^>]*?level="(\d+)"[^>]*?>\s*(.+?)\s*</cb:mulu>',
        re.DOTALL
    )
    entries = []
    for m in pattern.finditer(text):
        entries.append({
            'level': int(m.group(1)),
            'text': m.group(2).strip()
        })
    return entries


def to_tree(entries, include_semantic=True):
    """Convert entries to indented tree format."""
    if not entries:
        return "(empty)"

    lines = []
    ancestors = []

    for i, e in enumerate(entries):
        level = e['level']

        # Adjust ancestor stack
        while len(ancestors) >= level:
            ancestors.pop()
        while len(ancestors) < level - 1:
            ancestors.append(False)

        # Check if last sibling
        remaining = [x for x in entries[i+1:] if x['level'] <= level]
        is_last = not remaining or remaining[0]['level'] < level

        prefix_parts = []
        for a in ancestors:
            if a:
                prefix_parts.append('    ')
            else:
                prefix_parts.append('|   ')

        connector = '`-- ' if is_last else '|-- '
        prefix = ''.join(prefix_parts) + connector

        if include_semantic:
            label = f"{e['text']} (level {e['level']})"
        else:
            label = e['text']

        lines.append(f"{prefix}{label}")
        ancestors.append(is_last)

    return '\n'.join(lines)


def to_csv(entries):
    """Convert entries to CSV format."""
    lines = ['level,text']
    for e in entries:
        lines.append(f'{e["level"]},"{e["text"]}"')
    return '\n'.join(lines)


def to_flat(entries):
    """Convert entries to flat format with level prefix."""
    lines = []
    for e in entries:
        indent = '  ' * (e['level'] - 1)
        lines.append(f"{indent}{e['text']}")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Extract cb:mulu directory structure from CBETA XML')
    parser.add_argument('input', nargs='?',
                        help='XML file path or --text for inline text')
    parser.add_argument('--text', help='Inline CBETA XML text')
    parser.add_argument('--max-level', type=int, default=99,
                        help='Maximum level to include')
    parser.add_argument('--format', choices=['tree', 'csv', 'flat'],
                        default='tree', help='Output format')
    parser.add_argument('--no-semantic', action='store_true',
                        help='Omit semantic labels')

    args = parser.parse_args()

    if args.text:
        xml_text = args.text
    elif args.input:
        xml_text = Path(args.input).read_text(encoding='utf-8')
    else:
        xml_text = sys.stdin.read()

    entries = parse_mulu(xml_text)
    entries = [e for e in entries if e['level'] <= args.max_level]

    if args.format == 'tree':
        output = to_tree(entries, include_semantic=not args.no_semantic)
    elif args.format == 'csv':
        output = to_csv(entries)
    elif args.format == 'flat':
        output = to_flat(entries)
    else:
        output = to_tree(entries)

    print(output)


if __name__ == '__main__':
    main()
