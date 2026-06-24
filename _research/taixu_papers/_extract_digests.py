#!/usr/bin/env python3
"""Extract structured digests from Taixu research papers (v2).
Fixes: intro extraction, conclusion detection, title parsing."""

import json, os, re, glob

PAPERS_DIR = os.path.dirname(os.path.abspath(__file__))
DIGESTS_DIR = os.path.join(PAPERS_DIR, '_digests')
os.makedirs(DIGESTS_DIR, exist_ok=True)

# Clean up old digests
for f in glob.glob(os.path.join(DIGESTS_DIR, '*.json')):
    os.remove(f)

def parse_paper(text):
    """Parse paper into structured components."""
    lines = text.split('\n')
    
    # Extract H1 title (first # heading that isn't generic like 硕士学位论文)
    h1_candidates = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('# ') and not stripped.startswith('## '):
            h1_candidates.append((i, stripped[2:].strip()))
    
    title = ''
    title_line = 0
    generic_titles = {'硕士学位论文', '博士学位论文', '博士论文', '硕士论文'}
    for idx, t in h1_candidates:
        if t not in generic_titles:
            title = t
            title_line = idx
            break
    if not title and h1_candidates:
        title = h1_candidates[0][1]
        title_line = h1_candidates[0][0]
    
    # Extract metadata: author, keywords, abstract
    author = ''
    keywords_raw = ''
    abstract_raw = ''
    
    for i, line in enumerate(lines[:80]):
        stripped = line.strip()
        if not author and '◎' in stripped:
            author = re.sub(r'[◎\s·]', '', stripped[:50]).strip().rstrip('1234567890')
        m = re.search(r'(关键词|關鍵詞)[：:]\s*(.+)', stripped)
        if m:
            keywords_raw = stripped
        if re.search(r'(摘\s*要|内容提要)[：:]', stripped):
            abstract_raw = stripped
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith('##') and j < i + 20:
                abstract_raw += '\n' + lines[j]
                j += 1
    
    # Parse sections by ## headings
    sections = []
    current_heading = ''
    current_start = title_line + 1
    
    for i in range(title_line + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith('## ') and not stripped.startswith('### '):
            if current_heading or i > current_start:
                sections.append({
                    'heading': current_heading,
                    'content': '\n'.join(lines[current_start:i])
                })
            current_heading = stripped[3:].strip()
            current_start = i + 1
    
    if current_start < len(lines):
        sections.append({
            'heading': current_heading,
            'content': '\n'.join(lines[current_start:])
        })
    
    return {
        'title': title,
        'author': author,
        'keywords_raw': keywords_raw,
        'abstract_raw': abstract_raw,
        'sections': sections,
        'title_line': title_line
    }

def get_paras(text, n=5):
    """Get first n non-empty paragraphs."""
    paras = [p.strip() for p in text.split('\n\n') if p.strip() and len(p.strip()) > 20]
    return '\n\n'.join(paras[:n])

def get_last_paras(text, n=5):
    """Get last n non-empty paragraphs."""
    paras = [p.strip() for p in text.split('\n\n') if p.strip() and len(p.strip()) > 20]
    return '\n\n'.join(paras[-n:]) if len(paras) >= n else '\n\n'.join(paras)

def is_reference_section(heading, content):
    """Check if a section is references/footnotes."""
    rf = ['注释', '注釋', '参考', '參考', '文献', '文獻', '引用', '书目', '書目']
    if any(k in heading for k in rf):
        return True
    lines = content.strip().split('\n')
    fn = sum(1 for l in lines if re.match(r'^\s*\[\d+\]', l.strip()))
    if fn > len(lines) * 0.5 and len(lines) > 5:
        return True
    return False

def build_digest(parsed):
    """Build digest from parsed paper."""
    sections = parsed['sections']
    headings = [s['heading'] for s in sections if s['heading']]
    
    # Filter out reference sections
    body_secs = [s for s in sections if s['heading'] and not is_reference_section(s['heading'], s['content'])]
    
    # Intro: first body section content
    intro = ''
    if body_secs:
        intro = get_paras(body_secs[0]['content'], n=8)
    elif sections and sections[0]['content'].strip():
        intro = get_paras(sections[0]['content'], n=8)
    if len(intro) < 50 and len(sections) > 1:
        intro = get_paras(sections[0]['content'], n=8) if sections[0]['content'].strip() else ''
    
    # Conclusion: last body section
    conclusion = ''
    if body_secs:
        conclusion = get_last_paras(body_secs[-1]['content'], n=8)
    if len(conclusion) < 50:
        for s in reversed(sections[:-1]):
            if s['content'].strip():
                conclusion = get_last_paras(s['content'], n=8)
                break
    
    # Clean headings
    clean_headings = []
    skip = ['注释', '注釋', '参考文献', '參考文獻', 'Abstract', 'ABSTRACT',
            '独创声明', '学位论文', '版权', '目录', '目 录']
    for h in headings:
        if not any(p in h for p in skip):
            clean_headings.append(h)
    
    return {
        'title': parsed['title'],
        'author': parsed['author'],
        'keywords': parsed['keywords_raw'],
        'abstract': parsed['abstract_raw'],
        'headings': clean_headings,
        'intro': intro,
        'conclusion': conclusion
    }

if __name__ == '__main__':
    papers = sorted(glob.glob(os.path.join(PAPERS_DIR, '*.md')))
    digests = []
    total_full = 0
    total_digest = 0
    issues = []

    for i, paper in enumerate(papers):
        fname = os.path.basename(paper)
        with open(paper, 'r', encoding='utf-8') as f:
            text = f.read()
        
        parsed = parse_paper(text)
        digest = build_digest(parsed)
        digest['char_count'] = len(text)
        digest['digest_chars'] = len(json.dumps(digest, ensure_ascii=False))
        digest['type'] = 'paper'
        digest['_file'] = fname
        
        ilen = len(digest['intro'])
        clen = len(digest['conclusion'])
        if ilen < 100:
            issues.append('SHORT_INTRO (%dc): %s' % (ilen, fname[:60]))
        if clen < 100:
            issues.append('SHORT_CONC (%dc): %s' % (clen, fname[:60]))
        
        outpath = os.path.join(DIGESTS_DIR, fname.replace('.md', '.json'))
        with open(outpath, 'w', encoding='utf-8') as f:
            json.dump(digest, f, ensure_ascii=False, indent=2)
        
        digests.append(digest)
        total_full += digest['char_count']
        total_digest += digest['digest_chars']
        
        if (i + 1) % 15 == 0:
            print('  Processed %d/%d...' % (i + 1, len(papers)))
    
    # Generate index
    index = []
    for d in digests:
        index.append({
            'file': d['_file'],
            'title': d['title'],
            'author': d.get('author', ''),
            'char_count': d['char_count'],
            'digest_chars': d['digest_chars'],
            'has_keywords': bool(d.get('keywords', '').strip()),
            'has_abstract': bool(d.get('abstract', '').strip()),
            'headings_count': len(d.get('headings', []))
        })
    
    idx_path = os.path.join(PAPERS_DIR, '_papers_index.json')
    with open(idx_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    print('\nDone. %d papers processed.' % len(papers))
    print('  Full text total:    %10s chars' % format(total_full, ','))
    print('  Digest total:       %10s chars' % format(total_digest, ','))
    print('  Compression ratio:   %.1fx' % (total_full / max(total_digest, 1)))
    if issues:
        print('\n  Issues (%d):' % len(issues))
        for issue in issues[:10]:
            print(issue)
        if len(issues) > 10:
            print('  ... (%d more)' % (len(issues) - 10))
