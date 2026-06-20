import sys, base64
# Read the current file up to the taixu-llm-wiki-planning block
with open('/Users/xin/.codex/memories/MEMORY.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the position of the first unchanged block
marker = '# Task Group: china-history-doc-to-md'
idx = content.find(marker)
print(f'Marker found at position {idx}')

# Keep only the part before the first unchanged block
prefix = content[:idx]
print(f'Prefix length: {len(prefix)}')
