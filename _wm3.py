import sys, base64
with open('/Users/xin/.codex/memories/MEMORY.md', 'r', encoding='utf-8') as f:
    content = f.read()
marker = '# Task Group: china-history-doc-to-md'
idx = content.find(marker)
prefix = content[:idx]
with open('/Users/xin/Documents/Road_Of_Taixu/_b64_uc.txt', 'r', encoding='ascii') as f:
    b64 = f.read()
unchanged = base64.b64decode(b64).decode("utf-8")
full = prefix + unchanged
with open('/Users/xin/.codex/memories/MEMORY.md', 'w', encoding='utf-8') as f:
    f.write(full)
print(f'Written: {len(full)} chars')
