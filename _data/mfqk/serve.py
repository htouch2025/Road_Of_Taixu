#!/usr/bin/env python3
"""Start a local HTTP server to browse mfqk.db."""
import http.server
import os
import webbrowser

PORT = 8765
DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(DIR)

class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      '.wasm': 'application/wasm',
                      '.db': 'application/octet-stream'}
    def log_message(self, format, *args):
        pass  # quiet

print(f'📰 mfqk 民国佛教期刊阅览')
print(f'   地址: http://localhost:{PORT}/index.html')
print(f'   按 Ctrl+C 停止服务器')

webbrowser.open(f'http://localhost:{PORT}/index.html')

with http.server.HTTPServer(('', PORT), Handler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')
