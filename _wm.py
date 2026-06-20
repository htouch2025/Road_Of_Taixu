import sys
import base64

# Full MEMORY.md content will be decoded from base64
content_b64 = sys.argv[1]
content = base64.b64decode(content_b64).decode('utf-8')
with open('/Users/xin/.codex/memories/MEMORY.md', 'w', encoding='utf-8') as f:
    f.write(content)
print('Written: ' + str(len(content)) + ' chars')
