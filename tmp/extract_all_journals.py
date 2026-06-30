#!/usr/bin/env python3
"""
Extract ALL journal publication references from 太虚大师全书 (excl. 海刊/正信),
match against mfqk.db for publication dates, sort by citation frequency.
"""
import os, re, sqlite3, xml.etree.ElementTree as ET
from collections import defaultdict, OrderedDict

PROJECT = "/Users/xin/Documents/Road_Of_Taixu"
XML_DIR = os.path.join(PROJECT, "_data/cbeta/TX")
DB_PATH = os.path.join(PROJECT, "_data/mfqk/mfqk.db")
OUT_PATH = os.path.join(PROJECT, "tmp/太虚全书_各刊物卷期引用对照表.md")

CN = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,
      '十一':11,'十二':12,'十三':13,'十四':14,'十五':15,'十六':16,'十七':17,'十八':18,
      '十九':19,'二十':20,'二十一':21,'二十二':22,'二十三':23,'二十四':24,'二十五':25,
      '二十六':26,'二十七':27,'二十八':28,'二十九':29,'三十':30,'三十一':31,'三十二':32,
      '三十三':33,'三十四':34,'三十五':35,'三十六':36,'三十七':37,'三十八':38,'三十九':39,'四十':40,
      '四十一':41,'四十二':42,'四十三':43,'四十四':44,'四十五':45,'四十六':46,'四十七':47,'四十八':48,'四十九':49,'五十':50,
      # 廿 = 20
      '廿':20,'廿一':21,'廿二':22,'廿三':23,'廿四':24,'廿五':25,'廿六':26,'廿七':27,'廿八':28,'廿九':29,
      # 卅 = 30
      '卅':30,'卅一':31,'卅二':32,'卅三':33,'卅四':34,'卅五':35,'卅六':36,'卅七':37,'卅八':38,'卅九':39}
INT2CN = {v:k for k,v in CN.items() if not k.startswith('廿') and not k.startswith('卅')}
# For display, map back to regular CN
INT2CN_DISPLAY = {v:k for k,v in CN.items()}

EXCLUDE = ['海刊', '海潮音', '海潮', '正信']
NON_PER = ['大乘起信論','維摩詰','真實義品','南普陀寺誌','訪問團日記','訪問日記',
           '淡遠樓','演說集','西來講演集','川東講演','昧盦詩錄','廬山學','學僧之路',
           '太虛大師紀念集','太虛不師文','彌陀淨土法門集','東方文化','東瀛釆真錄','道學論衡',
           '玄嬰與太虛上人書']

def is_bare_vol_issue(ref_text):
    """Check if ref is just a bare volume/issue without journal name (likely 海刊 remnant)."""
    # Pattern: just 見X卷Y期 or 見XY期 without any journal identifier
    bare = re.sub(r'[見散載刊錄轉原]', '', ref_text)
    # If after removing prefix, it matches just a vol/issue pattern → bare
    if re.match(r'^[一二三四五六七八九十廿卅百]+卷[一二三四五六七八九十廿卅百]+期$', bare):
        return True
    if re.match(r'^[一二三四五六七八九十廿卅百]+期$', bare):
        return True
    # 海二十七卷八期 → 海=海刊
    if re.match(r'^海[一二三四五六七八九十廿卅百]+卷', bare):
        return True
    return False

# Journal mapping: (ref_patterns, [mfqk_candidates]) — try candidates in order
JOURNAL_MAP = [
    (['覺群周報', '覺群週報'], ['覺群週報']),
    (['覺群'], ['覺群報', '覺群週報']),  # 覺群 can be either
    (['佛教月報', '佛學月報'], ['佛教月報']),
    (['覺社叢書'], ['覺社叢書']),
    (['居士林林刊', '世界佛教居士林林刊', '林刊'], ['世界佛教居士林林刊']),
    (['覺音'], ['覺音']),
    (['漢藏教理院年刊', '漢藏教理院'], ['世界佛學苑漢藏教理院年刊', '世界佛學苑漢藏教理院特刊']),
    (['佛化新聞'], ['佛化新聞']),
    (['覺書'], ['覺書']),
    (['現代僧伽'], ['現代僧伽']),
    (['現代佛教'], ['現代佛教']),
    (['時代精神'], ['時代精神']),
    (['文化先鋒', '文藝先鋒'], ['文化先鋒']),
    (['宇宙風'], ['宇宙風']),
    (['覺有情'], ['覺有情', '覺有情半月刊']),
    (['覺世'], ['覺世']),
    (['華南覺音'], ['華南覺音']),
    (['中國佛學旬刊', '中國佛學'], ['中國佛學']),
    (['人間覺'], ['人間覺']),
    (['佛學半月刊'], ['佛學半月刊']),
    (['佛學日報'], ['佛學日報']),
    (['佛教日報'], ['佛教日報']),
    (['佛教新聞'], ['佛教新聞']),
    (['淨土宗月刊'], ['淨土宗月刊']),
    (['香海佛化刊'], ['香海佛化刊']),
    (['軍事與政治'], ['軍事與政治']),
    (['民族正氣'], ['民族正氣']),
    (['黃鐘'], ['黃鐘']),
    (['讀書通訊'], ['讀書通訊']),
    (['反侵略'], ['反侵略']),
    (['世界宗教會記載'], ['世界宗教會記載']),
    (['慈航畫報'], ['慈航畫報']),
    (['新中華'], ['新中華']),
    (['大公報', '大公'], ['大公報']),
    (['中央日報'], ['中央日報']),
    (['時事新報'], ['時事新報']),
    (['益世報'], ['益世報']),
    (['星洲叻報', '星洲叨報'], ['星洲叻報']),
]

def match_journal(ref_text):
    for patterns, candidates in JOURNAL_MAP:
        for pat in patterns:
            if pat in ref_text:
                return candidates, pat
    return None, None

def should_exclude(ref_text):
    for pat in EXCLUDE:
        if pat in ref_text: return True
    for pat in NON_PER:
        if pat in ref_text: return True
    if is_bare_vol_issue(ref_text): return True
    return False

# ── Scan XML ──
def scan_xml():
    all_refs = []
    def find_refs(elem, context, results):
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        if tag == 'mulu':
            lv = elem.get('level','')
            txt = ''.join(elem.itertext()).strip()
            context['mulu'][lv] = txt
            for k in list(context['mulu'].keys()):
                if k > lv: del context['mulu'][k]
        elif tag == 'head':
            txt = ''.join(elem.itertext()).strip()
            context['current_head'] = txt
            context['head_info'] = {
                'head': txt, 'level1': context['mulu'].get('1',''),
                'level2': context['mulu'].get('2',''), 'level3': context['mulu'].get('3','')}
        elif tag in ('byline','note'):
            raw = ''.join(elem.itertext())
            text = re.sub(r'\s+', '', raw)
            for m in re.finditer(r'[（\(](見|散見|載|刊|原載|錄|轉載|原刊)([^）\)]{2,80})[）\)]', text):
                full_ref = m.group(0).strip('（）()')
                if should_exclude(full_ref): continue
                candidates, pat = match_journal(full_ref)
                if candidates is None:
                    candidates = ['__unmatched__']; pat = full_ref
                hi = context.get('head_info',{})
                results.append({
                    'ref': full_ref, 'candidates': candidates, 'pat': pat,
                    'head': hi.get('head',context.get('current_head','')),
                    'level1': hi.get('level1',context['mulu'].get('1','')),
                    'level2': hi.get('level2',context['mulu'].get('2','')),
                })
        for child in elem:
            find_refs(child, context, results)
    
    for root,dirs,files in os.walk(XML_DIR):
        for f in sorted(files):
            if not f.endswith('.xml'): continue
            fp = os.path.join(root,f)
            try:
                tree = ET.parse(fp)
                results = []
                ctx = {'mulu':{},'current_head':'','head_info':{}}
                find_refs(tree.getroot(), ctx, results)
                vn = int(re.match(r'TX(\d+)',f).group(1))
                for r in results:
                    r['tx_file']=f; r['tx_vol']=vn
                all_refs.extend(results)
            except Exception as e:
                print(f"  Err: {fp}: {e}")
    return all_refs

# ── Build mfqk lookup (keep ALL dates, mark 0000 as None) ──
def build_mfqk_lookup():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Load ALL publicCode, keep vol as TEXT
    cur.execute("""
        SELECT j.journalName, p.vol, p.noFrom, p.noTo, p.publicDate
        FROM publicCode p JOIN journal j ON p.jNum = j.jNum
    """)
    # lookup[key] → date or None
    lookup = {}
    for jn, vol, nf, nt, pd in cur.fetchall():
        if pd == '0000-00-00': pd = None
        try: nf=int(nf); nt=int(nt)
        except: continue
        
        # Try to parse vol as int, fall back to text
        try: vi = int(vol)
        except:
            # Non-numeric vol like '創刊號', '0'
            if vol == '0':
                vi = 0
            else:
                vi = vol  # keep as string
        
        if isinstance(vi, int):
            for iss in range(nf, nt+1):
                key = (jn, vi, iss)
                # Prefer existing date over None
                if key not in lookup or (lookup[key] is None and pd is not None):
                    lookup[key] = pd
        else:
            # Non-numeric vol: store as (jn, vol_str, 0)
            key = (jn, vi, nf)
            if key not in lookup or (lookup[key] is None and pd is not None):
                lookup[key] = pd
    
    conn.close()
    return lookup

# ── Parse vol/issue ──
def parse_ref(ref_text):
    """Returns list of (vol, issue_str) possibilities to try."""
    results = []
    # X卷Y期
    for m in re.finditer(r'(?:第)?([一二三四五六七八九十廿卅百]+)卷(?:第)?([一二三四五六七八九十廿卅百]+)期', ref_text):
        v = CN.get(m.group(1))
        i = CN.get(m.group(2))
        if v and i: results.append((v, str(i)))
    # X卷Y號
    for m in re.finditer(r'(?:第)?([一二三四五六七八九十廿卅百]+)卷(?:第)?([一二三四五六七八九十廿卅百]+)號', ref_text):
        v = CN.get(m.group(1))
        i = CN.get(m.group(2))
        if v and i: results.append((v, str(i)))
    # Just Y期 (with 第)
    for m in re.finditer(r'第([一二三四五六七八九十廿卅百]+)期', ref_text):
        i = CN.get(m.group(1))
        if i: results.append((0, str(i)))  # 0 = unknown vol
    # Just Y期 (without 第)
    for m in re.finditer(r'(?<!\d)([一二三四五六七八九十廿卅百]+)期(?!\d)', ref_text):
        i = CN.get(m.group(1))
        if i: results.append((0, str(i)))
    # Y號
    for m in re.finditer(r'(?:第)?([一二三四五六七八九十廿卅百]+)號', ref_text):
        i = CN.get(m.group(1))
        if i: results.append((0, str(i)))
    # 合刊
    for m in re.finditer(r'([一二三四五六七八九])([一二三四五六七八九])期合刊', ref_text):
        i1=CN.get(m.group(1)); i2=CN.get(m.group(2))
        if i1 and i2: results.append((0, f"{i1}-{i2}"))
    # 至 合刊
    for m in re.finditer(r'([一二三四五六七八九十廿卅]+)至([一二三四五六七八九十廿卅]+)期合刊', ref_text):
        s1=m.group(1).replace('廿','二十').replace('卅','三十')
        s2=m.group(2).replace('廿','二十').replace('卅','三十')
        i1=CN.get(s1); i2=CN.get(s2)
        if i1 and i2: results.append((0, f"{i1}-{i2}"))
    # 二卷X期 (二三五期 style)
    for m in re.finditer(r'([一二三四五六七八九十]+)卷([一二三四五六七八九十]+)期', ref_text):
        v=CN.get(m.group(1)); i=CN.get(m.group(2))
        if v and i: results.append((v, str(i)))
    return results if results else [(None, None)]

def lookup_date(lookup, candidates, vol, iss_str):
    """Try to find date across all candidate journal names and vol/iss combos."""
    if vol is None or iss_str is None:
        return None
    try:
        iss_first = int(iss_str.split('-')[0])
    except: return None
    
    for jn in candidates:
        # Exact: (jn, vol, iss)
        key = (jn, vol, iss_first)
        if key in lookup and lookup[key] is not None:
            return lookup[key]
        # Try vol=0
        if vol != 0:
            key = (jn, 0, iss_first)
            if key in lookup and lookup[key] is not None:
                return lookup[key]
        # Try vol=1
        if vol != 1:
            key = (jn, 1, iss_first)
            if key in lookup and lookup[key] is not None:
                return lookup[key]
    
    # Fallback: any date (even 0000) for any candidate
    for jn in candidates:
        key = (jn, vol, iss_first)
        if key in lookup:
            return '—'
    
    return None

# ── Main ──
def main():
    print("Step 1: Scanning XML...")
    all_refs = scan_xml()
    print(f"  Found {len(all_refs)} refs")
    
    print("Step 2: Building mfqk lookup...")
    mfqk = build_mfqk_lookup()
    print(f"  {len(mfqk)} entries")
    
    # Group
    by_journal = defaultdict(list)
    for r in all_refs:
        jn = r['candidates'][0]  # primary candidate
        by_journal[jn].append(r)
    
    # Dedup & lookup
    journal_data = OrderedDict()
    for jn in sorted(by_journal.keys()):
        refs = by_journal[jn]
        seen = set(); unique = []
        for r in refs:
            key = (r['ref'], r['head'], r['tx_file'])
            if key not in seen:
                seen.add(key); unique.append(r)
        
        for r in unique:
            parsed = parse_ref(r['ref'])
            best_date = None
            best_vi = (None, None)
            for vol, iss_str in parsed:
                d = lookup_date(mfqk, r['candidates'], vol, iss_str)
                if d is not None and d != '—':
                    best_date = d; best_vi = (vol, iss_str); break
                elif d == '—' and best_date is None:
                    best_date = '—'; best_vi = (vol, iss_str)
            if best_date is None:
                best_vi = parsed[0] if parsed else (None, None)
            r['vol_int'] = best_vi[0]
            r['iss_str'] = best_vi[1]
            r['date'] = best_date
        
        journal_data[jn] = unique
    
    # Merge 覺群報 + 覺群週報 (same publication, renamed after issue 52)
    if '覺群報' in journal_data and '覺群週報' in journal_data:
        merged = journal_data['覺群報'] + journal_data['覺群週報']
        journal_data['覺群週報／覺群報'] = merged
        del journal_data['覺群報']
        del journal_data['覺群週報']
    elif '覺群報' in journal_data:
        journal_data['覺群週報／覺群報'] = journal_data.pop('覺群報')
    elif '覺群週報' in journal_data:
        journal_data['覺群週報／覺群報'] = journal_data.pop('覺群週報')

    sorted_journals = sorted(journal_data.items(), key=lambda x: len(x[1]), reverse=True)

    print(f"\n  Journals: {len(sorted_journals)}")
    for jn, refs in sorted_journals:
        wd = sum(1 for r in refs if r.get('date') and r['date'] != '—')
        wu = sum(1 for r in refs if r.get('date') == '—')
        print(f"  {jn}: {len(refs)} refs, {wd} dated, {wu} unknown-date")
    
    if '__unmatched__' in journal_data:
        print(f"\n  Unmatched: {len(journal_data['__unmatched__'])}")
        for r in sorted(set(r['ref'] for r in journal_data['__unmatched__'])):
            print(f"    {r}")
    
    # ── Markdown ──
    lines = []
    lines.append("# 太虚大师全书各刊物卷期引用对照表")
    lines.append("")
    lines.append("> 生成日期：2026年6月30日")
    lines.append("> 数据来源：太虚大师全书 CBETA TEI XML + 民国佛教期刊数据库（`_data/mfqk/mfqk.db`）")
    lines.append("> 说明：已排除《海潮音》（海刊）和《正信》，按引用次数从高到低排列；出版时间标「—」者表示数据库中有记录但日期缺失")
    lines.append("")
    
    lines.append("## 总览")
    lines.append("")
    lines.append("| 序号 | 刊物名称 | 引用次数 | 有出版时间 | 仅知卷期 |")
    lines.append("|------|---------|---------|-----------|---------|")
    
    for i,(jn,refs) in enumerate(sorted_journals,1):
        if jn == '__unmatched__': continue
        wd = sum(1 for r in refs if r.get('date') and r['date'] != '—')
        wu = sum(1 for r in refs if r.get('date') == '—')
        lines.append(f"| {i} | {jn} | {len(refs)} | {wd} | {wu} |")
    lines.append("")
    
    for ji,(jn,refs) in enumerate(sorted_journals,1):
        if jn == '__unmatched__':
            lines.append(f"## 附录：未识别引用（{len(refs)}条）")
            lines.append("")
            for r in sorted(set(r['ref'] for r in refs)):
                lines.append(f"- {r}")
            lines.append("")
            continue
        
        wd = sum(1 for r in refs if r.get('date') and r['date'] != '—')
        lines.append(f"## {ji}. {jn}（{len(refs)}次引用，{wd}条有日期）")
        lines.append("")
        
        def sk(r):
            v = r.get('vol_int')
            iss = r.get('iss_str') or '999'
            try: fi = int(iss.split('-')[0]) if '-' in iss else int(iss)
            except: fi = 999
            return (0 if v is None else (999 if v==0 else v), fi)
        
        refs_sorted = sorted(refs, key=sk)
        
        # 卷期→日期 对照表
        unique_vi = OrderedDict()
        for r in refs_sorted:
            vk = (r.get('vol_int'), r.get('iss_str'))
            if vk not in unique_vi:
                d = r.get('date')
                unique_vi[vk] = d.replace('-','.') if d and d != '—' else ('—' if d == '—' else '—')
        
        lines.append("### 卷期号—出版时间对照")
        lines.append("")
        lines.append("| 卷期号 | 出版时间 | 依据 |")
        lines.append("|--------|---------|------|")
        for (vol,iss), date in unique_vi.items():
            if vol and vol != 0:
                vcn = INT2CN_DISPLAY.get(vol, str(vol))
                d = f"{vcn}卷{iss}期" if iss else f"{vcn}卷"
            elif vol == 0:
                d = f"{iss}期" if iss else '—'
            else:
                d = str(iss) if iss else '—'
            lines.append(f"| {d} | {date} | mfqk |")
        lines.append("")
        
        # 引用明细
        lines.append("### 引用明细")
        lines.append("")
        lines.append("| 原始标注 | 卷期号 | 出版时间 | 编名 | 文章名 | 全书卷 |")
        lines.append("|---------|--------|---------|------|--------|-------|")
        for r in refs_sorted:
            ref = r['ref'].replace('|','｜')
            d = r.get('date')
            date = d.replace('-','.') if d and d != '—' else ('—' if d == '—' else '—')
            vol, iss = r.get('vol_int'), r.get('iss_str')
            if vol and vol != 0:
                vcn = INT2CN_DISPLAY.get(vol, str(vol))
                vi = f"{vcn}卷{iss}期" if iss else str(vcn)
            elif vol == 0:
                vi = f"{iss}期" if iss else '—'
            else:
                vi = str(iss) if iss else '—'
            bian = ' → '.join(p for p in [r.get('level1',''),r.get('level2','')] if p) or '—'
            bian = bian.replace('|','｜')
            head = (r.get('head') or '—').replace('|','｜')
            tx = f"TX{r['tx_vol']:02d}"
            lines.append(f"| {ref} | {vi} | {date} | {bian} | {head} | {tx} |")
        lines.append("")
    
    with open(OUT_PATH,'w',encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"\nOutput: {OUT_PATH}")

if __name__ == '__main__':
    main()
