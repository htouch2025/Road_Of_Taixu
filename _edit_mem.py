import pathlib
p = pathlib.Path("/Users/xin/.codex/memories/MEMORY.md")
content = p.read_text(encoding="utf-8")
print("File read, length:", len(content))