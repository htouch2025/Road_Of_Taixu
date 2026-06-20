import sys, base64
# Read b64 from file and write to memory_summary.md
with open('/Users/xin/Documents/Road_Of_Taixu/_b64_ms.txt', 'r', encoding='ascii') as f:
    b64 = f.read()
content = base64.b64decode(b64).decode("utf-8")
with open('/Users/xin/.codex/memories/memory_summary.md', 'w', encoding='utf-8') as f:
    f.write(content)
print(f"Written: {len(content)} chars")
