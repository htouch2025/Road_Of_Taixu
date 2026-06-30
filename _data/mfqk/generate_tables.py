#!/usr/bin/env python3
"""生成非海潮音刊物的卷期-年月对照表 v2"""

import sqlite3
import re
import os
from collections import defaultdict

# ============================================================
# 1. 配置：刊物别名映射、出版类型
# ============================================================

ALIAS_MAP = {
    # 卷期制期刊 - 注意繁简体都要覆盖，长名优先
    '正信抗戰半月刊': '正信', '正信抗战半月刊': '正信',
    '正信半月刊': '正信', '正信周刊': '正信', '正信週刊': '正信', '正信月刊': '正信',
    '正信': '正信',
    '覺群週報': '觉群周报', '觉群周报': '觉群周报', '覺群周報': '觉群周报',
    '覺群報': '觉群周报', '觉群报': '觉群周报',
    '覺群': '觉群周报', '觉群': '觉群周报',
    '現代僧伽': '现代僧伽', '现代僧伽': '现代僧伽',
    '中流月刊': '中流', '中流': '中流',
    '軍事與政治': '军事与政治', '军事与政治': '军事与政治',
    '文化先鋒': '文化先锋', '文化先锋': '文化先锋',
    '時代精神': '时代精神', '时代精神': '时代精神',
    '東方文化': '东方文化', '东方文化': '东方文化',
    '宇宙風': '宇宙风', '宇宙风': '宇宙风',
    '現代佛教': '现代佛教', '现代佛教': '现代佛教',
    '文史雜誌': '文史杂志', '文史杂志': '文史杂志',
    '文藝先鋒': '文艺先锋', '文艺先锋': '文艺先锋',
    '新中華': '新中华', '新中华': '新中华',
    '讀書通訊': '读书通讯', '读书通讯': '读书通讯',
    '民族正氣': '民族正气', '民族正气': '民族正气',
    '黃鐘': '黄钟', '黄钟': '黄钟',
    '東方雜誌': '东方杂志', '东方杂志': '东方杂志',
    # 期号制刊物
    '覺社叢書': '觉社丛书', '觉社丛书': '觉社丛书',
    '覺書': '觉社丛书', '觉书': '觉社丛书', '覺刊': '觉社丛书', '觉刊': '觉社丛书',
    '佛教月報': '佛教月报', '佛教月报': '佛教月报',
    '世界佛教居士林林刊': '世界佛教居士林林刊',
    '上海居士林林刊': '世界佛教居士林林刊',
    '世界佛教居士林刊': '世界佛教居士林林刊',
    '世界居士林林刊': '世界佛教居士林林刊',
    '居士林林刊': '世界佛教居士林林刊', '林刊': '世界佛教居士林林刊',
    '華南覺音': '觉音', '华南觉音': '觉音', '覺音': '觉音', '觉音': '觉音',
    '漢藏教理院開學紀念特刊': '汉藏教理院年刊', '汉藏教理院开学纪念特刊': '汉藏教理院年刊',
    '世界佛學苑漢藏教理院年刊': '汉藏教理院年刊',
    '漢藏教理院年刊': '汉藏教理院年刊', '汉藏教理院年刊': '汉藏教理院年刊',
    '佛化策進會會刊': '佛化策进会会刊', '佛化策进会会刊': '佛化策进会会刊',
    '佛學月報': '佛学月报', '佛学月报': '佛学月报',
    '覺有情半月刊': '觉有情', '觉有情半月刊': '觉有情',
    '覺有情': '觉有情', '觉有情': '觉有情',
    '中國佛學旬刊': '中国佛学旬刊', '中国佛学旬刊': '中国佛学旬刊',
    '淨土宗月刊': '净土宗月刊', '净土宗月刊': '净土宗月刊',
    '佛學半月刊': '佛学半月刊', '佛学半月刊': '佛学半月刊',
    # 日期嵌入型
    '佛教日報': '佛教日报', '佛教日报': '佛教日报',
    '佛化新聞': '佛化新闻', '佛化新闻': '佛化新闻',
    '佛教新聞': '佛化新闻', '佛教新闻': '佛化新闻',
    '佛學日報': '佛学日报', '佛学日报': '佛学日报',
}

PUB_TYPE = {
    '正信': '卷期制', '觉群周报': '卷期制', '现代僧伽': '卷期制', '中流': '卷期制',
    '军事与政治': '卷期制', '文化先锋': '卷期制', '时代精神': '卷期制',
    '东方文化': '卷期制', '宇宙风': '卷期制', '现代佛教': '卷期制',
    '文史杂志': '卷期制', '文艺先锋': '卷期制', '新中华': '卷期制',
    '读书通讯': '卷期制', '民族正气': '卷期制', '黄钟': '卷期制', '东方杂志': '卷期制',
    '觉社丛书': '期号制', '佛教月报': '期号制', '世界佛教居士林林刊': '期号制',
    '觉音': '期号制', '汉藏教理院年刊': '期号制', '佛化策进会会刊': '期号制',
    '佛学月报': '期号制', '觉有情': '期号制', '中国佛学旬刊': '期号制',
    '净土宗月刊': '期号制', '佛学半月刊': '期号制',
    '佛教日报': '日期嵌入型', '佛化新闻': '日期嵌入型', '佛学日报': '日期嵌入型',
}

MFQK_JOURNAL_MAP = {
    '正信': '正信', '正信週刊': '正信', '正信周刊': '正信', '正信抗戰半月刊': '正信', '正信抗战半月刊': '正信',
    '覺群週報': '觉群周报', '觉群周报': '觉群周报', '覺群周報': '觉群周报', '覺群報': '觉群周报', '觉群报': '觉群周报',
    '現代僧伽': '现代僧伽', '现代僧伽': '现代僧伽',
    '現代佛教': '现代佛教', '现代佛教': '现代佛教',
    '中流': '中流', '中流月刊': '中流',
    '覺社叢書': '觉社丛书', '觉社丛书': '觉社丛书',
    '佛教月報': '佛教月报', '佛教月报': '佛教月报',
    '世界佛教居士林林刊': '世界佛教居士林林刊',
    '覺音': '觉音', '觉音': '觉音', '華南覺音': '觉音', '华南觉音': '觉音',
    '世界佛學苑漢藏教理院年刊': '汉藏教理院年刊',
    '佛化策進會會刊': '佛化策进会会刊', '佛化策进会会刊': '佛化策进会会刊',
    '佛學月報': '佛学月报', '佛学月报': '佛学月报',
    '覺有情': '觉有情', '觉有情': '觉有情', '覺有情半月刊': '觉有情', '觉有情半月刊': '觉有情',
    '淨土宗月刊': '净土宗月刊', '净土宗月刊': '净土宗月刊',
    '佛學半月刊': '佛学半月刊', '佛学半月刊': '佛学半月刊',
    '東方文化': '东方文化', '东方文化': '东方文化',
    '佛化新聞': '佛化新闻', '佛化新闻': '佛化新闻',
}

# ============================================================
# 2. 中文数字转换（支持更大范围）
# ============================================================

# Pre-built Chinese numeral lookup
_CN_DIRECT = {
    '一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,
    '十一':11,'十二':12,'十三':13,'十四':14,'十五':15,
    '十六':16,'十七':17,'十八':18,'十九':19,'二十':20,
    '廿':20,'卅':30,'卌':40,'圩':50,'進':60,'圆':70,'枯':80,'枠':90,
    '零':0,'０':0,
}
# Also add 21-99 for faster lookup
for _i in range(21, 100):
    tens = _i // 10
    ones = _i % 10
    tens_cn = {2:'二十',3:'三十',4:'四十',5:'五十',6:'六十',7:'七十',8:'八十',9:'九十'}[tens]
    ones_cn = {0:'',1:'一',2:'二',3:'三',4:'四',5:'五',6:'六',7:'七',8:'八',9:'九'}[ones]
    _CN_DIRECT[tens_cn + ones_cn] = _i

def cn_to_int(s):
    """Convert Chinese numeral to int. Non-recursive."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None

    # Direct lookup
    if s in _CN_DIRECT:
        return _CN_DIRECT[s]

    # Arabic numerals
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return int(s.translate(str.maketrans('０１２３４５６７８９', '0123456789')))
    except ValueError:
        pass

    # Consecutive Chinese digits: only for pattern like "一四一" = 141
    # Only apply when string length >= 3 to avoid false positives with 七八 etc.
    if len(s) >= 3 and re.match(r'^[一二三四五六七八九〇零]{3,}$', s):
        digit_map = {'一':'1','二':'2','三':'3','四':'4','五':'5','六':'6','七':'7','八':'8','九':'9','〇':'0','零':'0'}
        try:
            return int(''.join(digit_map[c] for c in s))
        except (KeyError, ValueError):
            pass

    # Compound: 一百三十三
    result = 0
    remaining = s

    if '百' in remaining:
        parts = remaining.split('百', 1)
        h = _CN_DIRECT.get(parts[0], 1) if parts[0] else 1
        result += h * 100
        remaining = parts[1] if len(parts) > 1 else ''

    if '十' in remaining:
        parts = remaining.split('十', 1)
        t = _CN_DIRECT.get(parts[0], 1) if parts[0] else 1
        result += t * 10
        remaining = parts[1] if len(parts) > 1 else ''

    if remaining:
        o = _CN_DIRECT.get(remaining)
        if o is not None:
            result += o

    return result if result > 0 else None


# ============================================================
# 3. 从v2文件中提取卷期引用
# ============================================================

def extract_references(v2_path):
    """从刊载信息全录v2中提取所有刊物的卷期引用"""
    results = []

    with open(v2_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    pub_names_sorted = sorted(ALIAS_MAP.keys(), key=len, reverse=True)

    for line in lines:
        line = line.strip()

        # Extract reference text from various patterns
        ref_texts = []

        # Pattern 1: 見XXX）
        for m in re.finditer(r'見(.+?)(?:）|\)|$)', line):
            ref_texts.append(m.group(1).strip())

        # Pattern 2: 載XXX。 or 載XXX，
        for m in re.finditer(r'載(.+?)(?:[。，,;；]|$)', line):
            ref_texts.append(m.group(1).strip())

        # Pattern 3: 錄自XXX
        for m in re.finditer(r'錄自(.+?)(?:[。，,;；）\)]|$)', line):
            ref_texts.append(m.group(1).strip())

        for ref_text in ref_texts:
            # Find which publication this references
            matched_name = None
            for name in pub_names_sorted:
                if name in ref_text:
                    matched_name = name
                    break

            if not matched_name:
                continue

            # Skip 海潮音 references
            canonical = ALIAS_MAP[matched_name]
            if canonical == '海潮音':
                continue

            # Extract the part after the publication name
            pos = ref_text.index(matched_name)
            remaining = ref_text[pos + len(matched_name):].strip()

            # Parse volume/issue
            vol_issues = parse_vol_issue(remaining, canonical, PUB_TYPE.get(canonical, '卷期制'))

            for vol, issue in vol_issues:
                results.append((canonical, vol, issue, ref_text[:120]))

    return results


def parse_vol_issue(text, pub_name, pub_type):
    """从引用文本提取卷期号"""
    text_clean = re.sub(r'\s+', '', text)

    # 日期嵌入型 publications don't have conventional issue numbers -
    # their references contain dates (民国YY年M月) instead
    if pub_type == '日期嵌入型':
        return []

    # Always try vol/issue extraction first
    result = extract_vol_issue(text_clean)
    if result:
        return _filter_implausible(result)

    # Fall back to issue-only extraction
    result = extract_issue(text_clean)
    if result:
        return _filter_implausible(result)

    return []

def _filter_implausible(results):
    """Filter out implausible parses like treating '七八' as issue 78"""
    if not results:
        return results

    # Collect vol→issues mapping
    vol_issues = defaultdict(set)
    for vol, iss in results:
        vol_issues[vol].add(iss)

    filtered = []
    for vol, iss in results:
        keep = True
        if isinstance(iss, int) and iss > 60:
            # Could be a misparse of two separate issues
            # Check if there are decomposed versions
            iss_str = str(iss)
            if len(iss_str) == 2:
                d1, d2 = int(iss_str[0]), int(iss_str[1])
                if d1 <= 12 and d2 <= 12:
                    combined_key = f"{d1}-{d2}"
                    # If we also have the split or combined version, skip this one
                    if (vol, d1) in results or (vol, d2) in results or (vol, combined_key) in results:
                        keep = False
        if keep:
            filtered.append((vol, iss))

    return filtered


def extract_vol_issue(text):
    """提取「卷X期Y」格式"""
    results = []

    # 多数字匹配（支持 一百二十三 这种大数）
    num_pat = r'[零一二三四五六七八九十廿卅百]+|\d+'

    # 1. 范围: X卷Y期至A卷B期
    range_m = re.findall(
        rf'({num_pat})\s*卷\s*({num_pat})\s*期?\s*[至到\-~]\s*({num_pat})\s*卷\s*({num_pat})\s*期',
        text
    )
    for v1s, i1s, v2s, i2s in range_m:
        v1, i1, v2, i2 = cn_to_int(v1s), cn_to_int(i1s), cn_to_int(v2s), cn_to_int(i2s)
        if v1 and v2:
            for v in range(v1, v2 + 1):
                si = i1 if v == v1 and i1 else 1
                ei = i2 if v == v2 and i2 else 12
                for i in range(si, ei + 1):
                    if (v, i) not in results:
                        results.append((v, i))

    # 2. 单卷范围期: X卷Y至Z期
    range2_m = re.findall(
        rf'({num_pat})\s*卷\s*({num_pat})\s*期?\s*[至到\-~]\s*({num_pat})\s*期',
        text
    )
    for vs, i1s, i2s in range2_m:
        v, i1, i2 = cn_to_int(vs), cn_to_int(i1s), cn_to_int(i2s)
        if v and i1 and i2:
            for i in range(i1, i2 + 1):
                if (v, i) not in results:
                    results.append((v, i))

    # 3a. 卷+多期 WITH separator: X卷Y、Z期, X卷Y,Z期
    multi_sep = re.findall(
        rf'({num_pat})\s*卷\s*({num_pat})[、,，]\s*({num_pat})\s*期',
        text
    )
    for vs, i1s, i2s in multi_sep:
        v, i1, i2 = cn_to_int(vs), cn_to_int(i1s), cn_to_int(i2s)
        if v and i1 and i2:
            results.append((v, i1))
            results.append((v, i2))
            if i1 != i2:
                results.append((v, f"{min(i1,i2)}-{max(i1,i2)}"))

    # 3b. 卷+无分隔符两期: 四卷七八期 (two single Chinese digits stuck together)
    multi_nosep = re.findall(
        rf'({num_pat})\s*卷\s*([一二三四五六七八九])([一二三四五六七八九])\s*期',
        text
    )
    for vs, i1s, i2s in multi_nosep:
        v = cn_to_int(vs)
        i1, i2 = cn_to_int(i1s), cn_to_int(i2s)
        if v and i1 and i2:
            results.append((v, i1))
            results.append((v, i2))
            results.append((v, f"{min(i1,i2)}-{max(i1,i2)}"))

    # 4. 标准单卷单期: X卷Y期 or 第X卷Y期 or X卷第Y期
    single_m = re.findall(
        rf'第?\s*({num_pat})\s*卷\s*第?\s*({num_pat})\s*[期號号]',
        text
    )
    for vs, iss in single_m:
        v, i = cn_to_int(vs), cn_to_int(iss)
        if v and i:
            if (v, i) not in results:
                results.append((v, i))

    # 5. X卷Y号 (for some publications that use 号 instead of 期)
    hao_m = re.findall(
        rf'({num_pat})\s*卷\s*({num_pat})\s*[號号]',
        text
    )
    for vs, iss in hao_m:
        v, i = cn_to_int(vs), cn_to_int(iss)
        if v and i:
            if (v, i) not in results:
                results.append((v, i))

    # 6. 简化数字: 二三期 meaning 2, 3期 (for publications with vol context)
    # "二三期" but NOT preceded by 卷 (which would be caught above)
    short_m = re.findall(rf'(?<!\d)({num_pat})({num_pat})期(?!\s*[刊報杂志誌])', text)
    for i1s, i2s in short_m:
        i1, i2 = cn_to_int(i1s), cn_to_int(i2s)
        if i1 and i2 and i1 <= 12 and i2 <= 60:
            # Could be 二三期 = issues 2 and 3, or 十二期 = issue 12
            # If single digit + single digit, treat as combined
            if i1 < 10 and i2 < 10:
                if (None, i1) not in results:
                    results.append((None, i1))
                if (None, i2) not in results:
                    results.append((None, i2))

    return results


def extract_issue(text):
    """提取「第X期」格式（期号制）"""
    results = []

    num_pat = r'[零一二三四五六七八九十廿卅百]+|\d+'

    # 1. 第X期
    for m in re.finditer(rf'第\s*({num_pat})\s*期', text):
        i = cn_to_int(m.group(1))
        if i:
            results.append((None, i))

    # 2. 初X期
    for m in re.finditer(rf'初\s*({num_pat})\s*期', text):
        i = cn_to_int(m.group(1))
        if i:
            results.append((None, i))

    # 3. X辑
    for m in re.finditer(rf'({num_pat})\s*輯', text):
        i = cn_to_int(m.group(1))
        if i:
            results.append((None, i))

    # 4. X号/X號 (for 觉有情)
    for m in re.finditer(rf'({num_pat})\s*[號号]', text):
        i = cn_to_int(m.group(1))
        if i:
            results.append((None, i))

    # 5. 合刊: 卅至卅二期合刊, 三十四卅五期合刊
    for m in re.finditer(rf'({num_pat})\s*[至及、,，和與]\s*({num_pat})\s*期?\s*合?刊?', text):
        i1, i2 = cn_to_int(m.group(1)), cn_to_int(m.group(2))
        if i1:
            results.append((None, i1))
        if i2:
            results.append((None, i2))
        if i1 and i2:
            results.append((None, f"{i1}-{i2}"))

    # 6. 列表: 十、十一、十二、十四、十六各期
    list_pat = r'([零一二三四五六七八九十廿卅百\d、，,]+)\s*各?期'
    list_m = re.findall(list_pat, text)
    for nums_str in list_m:
        nums = re.split(r'[、，,]', nums_str)
        for n in nums:
            n = n.strip()
            if n:
                i = cn_to_int(n)
                if i:
                    results.append((None, i))

    # 7. X期Y期 (consecutive without separator)
    for m in re.finditer(rf'(?<!\d)({num_pat})期\s*({num_pat})期', text):
        i1, i2 = cn_to_int(m.group(1)), cn_to_int(m.group(2))
        if i1:
            results.append((None, i1))
        if i2:
            results.append((None, i2))

    # 8. Standalone X期 (without 第)
    # Be more careful to not match things like 月刊, 季刊
    for m in re.finditer(rf'(?<![第卷\d])({num_pat})期(?!\s*[刊報杂志誌])', text):
        i = cn_to_int(m.group(1))
        if i and i < 200:  # reasonable upper bound
            results.append((None, i))

    # 9. 卷+号格式（如八卷六號 for 觉有情）
    for m in re.finditer(rf'({num_pat})\s*卷\s*({num_pat})\s*[號号]', text):
        v, i = cn_to_int(m.group(1)), cn_to_int(m.group(2))
        if v and i:
            results.append((v, i))

    return results


# ============================================================
# 4. 查询mfqk.db
# ============================================================

def load_mfqk_data(db_path):
    """加载mfqk数据"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 构建 jNum → canonical 映射
    cursor.execute("SELECT jNum, journalName FROM journal")
    jnum_to_canonical = {}
    for jnum, jname in cursor.fetchall():
        if jname in MFQK_JOURNAL_MAP:
            jnum_to_canonical[jnum] = MFQK_JOURNAL_MAP[jname]

    # Check which canonicals have entries in mfqk
    canonicals_with_data = set(jnum_to_canonical.values())

    # 加载 publicCode
    cursor.execute("SELECT jNum, vol, noFrom, noTo, publicDate FROM publicCode")
    pubcodes = cursor.fetchall()

    # (canonical, vol, issue) → best_date
    date_index = {}
    for jnum, vol, noFrom, noTo, pubdate in pubcodes:
        canon = jnum_to_canonical.get(jnum)
        if not canon:
            continue

        # Parse vol
        vol_str = str(vol).strip() if vol else ''
        try:
            vol_int = int(vol_str) if vol_str else None
        except ValueError:
            vol_int = None

        date_str = pubdate.strip() if pubdate else ''
        # Treat "0000-00-00" as no date
        if date_str in ('0000-00-00', '0000', ''):
            date_str = ''

        # For each issue in range, record the BEST date (non-empty preferred)
        for issue in range(noFrom, noTo + 1):
            key = (canon, vol_int, issue)
            if key not in date_index or (date_str and not date_index[key]):
                date_index[key] = date_str

        # Record combined issue
        if noFrom != noTo:
            key = (canon, vol_int, f"{noFrom}-{noTo}")
            if key not in date_index or (date_str and not date_index[key]):
                date_index[key] = date_str

    conn.close()
    return date_index, canonicals_with_data


def lookup_date(canonical, vol, issue, date_index, canonicals_with_data):
    """查询出版日期"""

    def try_key(v, iss):
        k = (canonical, v, iss)
        if k in date_index:
            d = date_index[k]
            return (d, 'mfqk') if d else (None, '已匹配但缺日期')
        return None

    # Try with given vol
    if vol is not None:
        r = try_key(vol, issue)
        if r:
            return r

    # Try vol = None (期号制)
    r = try_key(None, issue)
    if r:
        return r

    # Try vol = 0 (some mfqk entries use vol=0 for 期号制)
    r = try_key(0, issue)
    if r:
        return r

    # Also try vol=0 with combined issue
    if isinstance(issue, str) and '-' in issue:
        r = try_key(0, issue)
        if r:
            return r
        r = try_key(None, issue)
        if r:
            return r

    # Check if this publication exists in mfqk at all
    if canonical in canonicals_with_data:
        return None, '已匹配但缺日期'

    return None, '未能匹配'


# ============================================================
# 5. 生成输出
# ============================================================

def format_vol_issue(vol, issue):
    if vol is not None:
        return f"{vol}卷{issue}期"
    else:
        return f"第{issue}期"


def format_date(date_str):
    if not date_str:
        return ''
    date_str = date_str.strip()
    if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
        return date_str.replace('-', '.')
    return date_str


def generate_markdown(all_refs, date_index, canonicals_with_data):
    # Count raw references per publication (for sorting)
    ref_counts = defaultdict(int)
    for canonical, _, _, _ in all_refs:
        ref_counts[canonical] += 1

    # Deduplicate
    pub_refs = defaultdict(set)
    for canonical, vol, issue, _ in all_refs:
        pub_refs[canonical].add((vol, issue))

    # Query dates
    pub_entries = defaultdict(list)
    # Sort by reference count descending, then alphabetically
    sorted_pubs = sorted(pub_refs.keys(), key=lambda p: (-ref_counts.get(p, 0), p))
    for canonical in sorted_pubs:
        seen = set()
        for vol, issue in sorted(pub_refs[canonical], key=lambda x: (
            x[0] if x[0] is not None else 99999,
            int(str(x[1]).split('-')[0]) if isinstance(x[1], (int, str)) and str(x[1]).split('-')[0].lstrip('-').isdigit() else 99999
        )):
            key = (vol, issue)
            if key in seen:
                continue
            seen.add(key)
            date, basis = lookup_date(canonical, vol, issue, date_index, canonicals_with_data)
            pub_entries[canonical].append((vol, issue, date, basis))

    # Stats
    stats = {}
    for canonical, entries in pub_entries.items():
        total = len(entries)
        wd = sum(1 for _, _, d, _ in entries if d)
        md = sum(1 for _, _, _, b in entries if b == '已匹配但缺日期')
        nm = sum(1 for _, _, _, b in entries if b == '未能匹配')
        stats[canonical] = (total, wd, md, nm)

    # Build markdown
    lines = []
    lines.append('# 太虚大师全书 · 非海潮音刊物卷期对照表')
    lines.append('')
    lines.append('> 生成日期：2026-06-29')
    lines.append('> 数据来源：太虚大师全书刊载信息全录v2 + mfqk.db')
    lines.append('> 已跳过海潮音（已有独立对照表）')
    lines.append('')

    # Global stats
    gt = sum(s[0] for s in stats.values())
    gw = sum(s[1] for s in stats.values())
    gm = sum(s[2] for s in stats.values())
    gn = sum(s[3] for s in stats.values())

    lines.append('## 全局统计')
    lines.append('')
    lines.append('| 刊物数 | 去重卷期总数 | ✅ 有日期 | ⚠️ 已匹配但缺日期 | ❌ 未能匹配 |')
    lines.append('|--------|------------|----------|-----------------|----------|')
    lines.append(f'| {len(stats)} | {gt} | {gw} | {gm} | {gn} |')
    lines.append('')
    lines.append('---')
    lines.append('')

    # Category stats
    cat_stats = defaultdict(lambda: [0,0,0,0,0])
    for canonical, (t, wd, md, nm) in stats.items():
        ptype = PUB_TYPE.get(canonical, '未知')
        cat_stats[ptype][0] += 1
        cat_stats[ptype][1] += t
        cat_stats[ptype][2] += wd
        cat_stats[ptype][3] += md
        cat_stats[ptype][4] += nm

    lines.append('## 分类统计')
    lines.append('')
    lines.append('| 类别 | 刊物数 | 卷期总数 | ✅ 有日期 | ⚠️ 缺日期 | ❌ 未能匹配 |')
    lines.append('|------|--------|---------|----------|----------|----------|')
    for cat in ['卷期制', '期号制', '日期嵌入型']:
        n, t, wd, md, nm = cat_stats[cat]
        if n > 0:
            lines.append(f'| {cat} | {n} | {t} | {wd} | {md} | {nm} |')
    lines.append('')
    lines.append('---')
    lines.append('')

    # Per-publication tables
    for canonical in sorted_pubs:
        entries = pub_entries[canonical]
        if not entries:
            continue

        ptype = PUB_TYPE.get(canonical, '未知')
        t, wd, md, nm = stats[canonical]

        lines.append(f'## {canonical} （引用 {ref_counts.get(canonical, 0)} 次）')
        lines.append('')
        lines.append(f'> 类型：{ptype}')
        lines.append(f'>')
        lines.append(f'> | 状态 | 数量 |')
        lines.append(f'> |------|------|')
        lines.append(f'> | ✅ 有日期 | {wd} |')
        lines.append(f'> | ⚠️ 已匹配但缺日期 | {md} |')
        lines.append(f'> | ❌ 未能匹配 | {nm} |')
        lines.append(f'>')
        lines.append(f'> **去重后卷期总数：{t}**')
        lines.append('')

        lines.append('| # | 卷期 | 出版年月 | 填入依据 |')
        lines.append('|---|---|---|---|')

        for idx, (vol, issue, date, basis) in enumerate(entries, 1):
            label = format_vol_issue(vol, issue)
            date_col = format_date(date) if date else basis
            lines.append(f'| {idx} | {label} | {date_col} | {basis} |')

        lines.append('')
        lines.append('---')
        lines.append('')

    # ===== List publications from publication_calendar that had no references =====
    # These are publications in the calendar but not in our extraction results
    all_target_pubs = set(ALIAS_MAP.values())
    found_pubs = set(pub_entries.keys())
    no_ref_pubs = all_target_pubs - found_pubs

    # Filter to only show those that should have had references
    # (exclude aliases that are just alternate names)
    lines.append('## 附录：无卷期引用的刊物')
    lines.append('')
    lines.append('以下刊物在 publication_calendar.md 中有记录，但在太虚大师全书中未提取到可用的卷期号引用：')
    lines.append('')
    lines.append('| 刊物名 | 类型 | 说明 |')
    lines.append('|--------|------|------|')
    for pub in sorted(no_ref_pubs):
        ptype = PUB_TYPE.get(pub, '未知')
        if ptype == '日期嵌入型':
            note = '引用中自带日期，无需卷期对照'
        elif pub in ('东方文化',):
            note = '引用中无明确的卷期号'
        elif pub in ('东方杂志',):
            note = '仅作为间接触及，无直接卷期引用'
        elif pub in ('佛化新闻',):
            note = '引用中自带日期（民国纪年），无需卷期对照'
        else:
            note = '无卷期引用或尚未匹配'
        lines.append(f'| {pub} | {ptype} | {note} |')
    lines.append('')

    return '\n'.join(lines)


# ============================================================
# 6. 主程序
# ============================================================

def main():
    base_dir = '/Users/xin/Documents/Road_Of_Taixu'
    v2_path = os.path.join(base_dir, '_research/太虚大师全书刊载信息全录_v2.md')
    db_path = os.path.join(base_dir, '_data/mfqk/mfqk.db')
    output_path = os.path.join(base_dir, '_data/mfqk/非海潮音刊物卷期对照表.md')

    print("Step 1: Extracting references from v2...")
    all_refs = extract_references(v2_path)
    print(f"  Total references extracted: {len(all_refs)}")

    pub_counts = defaultdict(int)
    for r in all_refs:
        pub_counts[r[0]] += 1
    print(f"  Publications found: {len(pub_counts)}")
    for pub, count in sorted(pub_counts.items(), key=lambda x: -x[1]):
        print(f"    {pub}: {count}")

    print("\nStep 2: Loading mfqk.db...")
    date_index, canonicals_with_data = load_mfqk_data(db_path)
    print(f"  Date entries loaded: {len(date_index)}")
    print(f"  Publications with mfqk data: {len(canonicals_with_data)}")

    print("\nStep 3: Generating markdown...")
    md_content = generate_markdown(all_refs, date_index, canonicals_with_data)

    print(f"\nStep 4: Writing to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    # Print summary
    pub_refs = defaultdict(set)
    for canonical, vol, issue, _ in all_refs:
        pub_refs[canonical].add((vol, issue))
    print(f"\n  Summary: {len(pub_refs)} publications, {sum(len(v) for v in pub_refs.values())} unique vol/issues")
    print("Done!")


if __name__ == '__main__':
    main()
