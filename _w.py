import sys
content = sys.argv[1]
with open("/Users/xin/.codex/memories/MEMORY.md", "w", encoding="utf-8") as f:
    f.write(content)
print("OK")
