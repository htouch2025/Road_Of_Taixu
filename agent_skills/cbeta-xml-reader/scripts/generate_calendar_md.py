#!/usr/bin/env python3
"""Generate publication_calendar.md from publication_calendar.json."""

import json
from pathlib import Path


def format_sources(sources):
    """Format verification_sources list into markdown string.

    Each source is a dict {name, url}. If url is not None, render as [name](url).
    If url is None, render as plain text.
    """
    parts = []
    for s in sources:
        name = s.get('name', '')
        url = s.get('url')
        if url:
            parts.append(f'[{name}]({url})')
        else:
            parts.append(name)
    return ' / '.join(parts)


def main():
    root = Path(__file__).parent.parent.parent.parent
    json_path = root / '_research' / 'publication_calendar.json'
    md_path = root / '_research' / 'publication_calendar.md'

    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    meta = data['_meta']
    pubs = data['publications']
    heuristics = data.get('heuristics', {})

    lines = []

    # Title
    lines.append('# 太虚大师全书 刊物卷期对照表')
    lines.append('')
    lines.append(f'> 生成日期：{meta["created"]}')
    lines.append(f'> 总刊物数：{meta["total_publications"]}')
    lines.append(f'> 状态：**{meta["status"]}**')
    lines.append('')
    lines.append('---')
    lines.append('')

    # Intro
    lines.append('## 说明')
    lines.append('')
    lines.append('本文档是太虚大师全书刊载信息全录v2中所有出现过的刊物的卷号/期号与公历年月对照表。')
    lines.append('用于将刊载出处（如「见海刊九卷第九期」）中的卷期引用解析为具体日期。')
    lines.append('')
    lines.append('### 分类说明')
    lines.append('')
    lines.append('| 类别 | 说明 | 对照表作用 |')
    lines.append('|------|------|-----------|')
    lines.append('| **卷期制期刊** | 引用格式为X卷Y期 | 需建立 卷→年、期→月 映射 |')
    lines.append('| **期号制刊物** | 仅有期号无卷号 | 需建立 期号→年月 映射 |')
    lines.append('| **日期嵌入型** | 引用中直接带日期 | 无需额外对照表 |')
    lines.append('| **报纸** | 日报，引用带日期 | 无需对照表 |')
    lines.append('| **单行本/丛书** | 书籍/讲演集/出版社 | 无期号概念 |')
    lines.append('| **出版机构** | 出版社/书局 | 非刊物 |')
    lines.append('')
    lines.append('### 换算公式')
    lines.append('')
    lines.append('- **海潮音**：`卷N ≈ 公元1919+N年`，`期M ≈ M月`')
    lines.append('- **通用**：若每年一卷，则 `卷N = 创刊年 + N - 1`')
    lines.append('- **中国数码**：`一=1, 二=2, ... 十=10, 廿=20, 卅=30`')
    lines.append('- **合刊**：取第一个期号的月份')
    lines.append('')
    lines.append('---')
    lines.append('')

    # Categorize publications
    categories = {
        '卷期制期刊': [],
        '期号制刊物': [],
        '日期嵌入型': [],
        '报纸': [],
        '单行本': [],
        '出版机构': [],
    }

    for name, pub in pubs.items():
        cat = pub.get('category', '单行本')
        if cat in categories:
            categories[cat].append((name, pub))
        else:
            categories['单行本'].append((name, pub))

    # Sort each category by ref_count descending
    for cat in categories:
        categories[cat].sort(key=lambda x: -x[1].get('ref_count', 0))

    # ── Section 1: 卷期制期刊 ──
    lines.append('## 一、卷期制期刊（有卷号有期号）')
    lines.append('')
    lines.append('需要建立 **卷→公元年** 和 **期→月份** 的映射。')

    for name, pub in categories['卷期制期刊']:
        lines.append('')
        lines.append(f'### {name}')
        lines.append('')
        # Basic info table
        aliases = ' / '.join(pub.get('aliases', []))
        ref_count = pub.get('ref_count', 0)
        date_range = f'{pub.get("date_range", {}).get("start", "?")} — {pub.get("date_range", {}).get("end", "?")}'
        period = pub.get('period', '?')
        place = pub.get('place', '?')
        confidence = pub.get('confidence', '?')

        lines.append('| 项目 | 内容 |')
        lines.append('|------|------|')
        lines.append(f'| v2引用次数 | {ref_count} |')
        if aliases:
            lines.append(f'| 别名 | {aliases} |')
        lines.append(f'| 出版时间 | {date_range} |')
        lines.append(f'| 刊期 | {period} |')
        lines.append(f'| 出版地 | {place} |')
        if 'publisher' in pub:
            lines.append(f'| 出版者 | {pub["publisher"]} |')
        if 'founder' in pub:
            lines.append(f'| 创办人 | {pub["founder"]} |')
        if 'editor' in pub:
            lines.append(f'| 主编 | {pub["editor"]} |')
        lines.append(f'| 置信度 | {confidence} |')
        if 'verification_sources' in pub:
            sources_str = format_sources(pub.get('verification_sources', []))
            lines.append(f'| 查证来源 | {sources_str} |')

        # Volume→Year table
        vol_to_year = pub.get('volume_to_year', {})
        if vol_to_year:
            lines.append('')
            lines.append('**卷号→公元年对照：**')
            lines.append('')
            lines.append('| 卷号 | 公元年 | 卷号 | 公元年 | 卷号 | 公元年 |')
            lines.append('|------|--------|------|--------|------|--------|')
            vols = sorted(vol_to_year.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0)
            # Split into 3 columns
            for i in range(0, len(vols), 3):
                row = vols[i:i+3]
                cells = []
                for v, y in row:
                    cells.append(f'卷{v}')
                    cells.append(str(y))
                while len(cells) < 6:
                    cells.append('')
                lines.append(f'| {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {cells[4]} | {cells[5]} |')

        # Issues detail
        if 'issues' in pub:
            lines.append('')
            lines.append('**已知期号→年月：**')
            lines.append('')
            if isinstance(pub['issues'], dict):
                lines.append('| 期号 | 出版年月 |')
                lines.append('|------|----------|')
                for iss, date in sorted(pub['issues'].items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
                    lines.append(f'| 第{iss}期 | {date} |')

        if 'issue_to_year' in pub:
            lines.append('')
            lines.append('**期号→年份速查（详见JSON）：**')
            lines.append('')
            ite = pub.get('issue_to_year', {})
            lines.append(f'| 期号范围 | 公元年 |')
            lines.append(f'|----------|--------|')
            # Group consecutive issues
            items = sorted(ite.items(), key=lambda x: int(x[0]))
            # Show first 5 and last 2
            for iss, yr in items[:5]:
                lines.append(f'| 第{iss}期 | {yr} |')
            if len(items) > 7:
                lines.append(f'| ... | ... |')
            for iss, yr in items[-2:]:
                lines.append(f'| 第{iss}期 | {yr} |')

        # History
        if 'history' in pub:
            lines.append('')
            lines.append('**刊史沿革：**')
            lines.append('')
            for h in pub['history']:
                lines.append(f'- {h["period"]}：《{h["name"]}》（{h.get("volumes", "")}）')

        if 'notes' in pub:
            lines.append('')
            lines.append(f'> 📝 {pub["notes"]}')

        # v2 locations (for low-count publications)
        if pub.get('v2_locations'):
            lines.append('')
            lines.append('**v2 出处：**')
            lines.append('')
            for loc in pub['v2_locations']:
                lines.append(f'- [{loc["编"]}] **{loc["article"]}**（{loc.get("子目", "")}）— `[{loc["type"]}]` {loc["raw_text"][:120]}')

        lines.append('')

    # ── Section 2: 期号制刊物 ──
    lines.append('---')
    lines.append('')
    lines.append('## 二、期号制刊物（仅有期号）')
    lines.append('')
    lines.append('需要建立 **期号→年月** 的映射。')

    for name, pub in categories['期号制刊物']:
        lines.append('')
        lines.append(f'### {name}')
        lines.append('')
        aliases = ' / '.join(pub.get('aliases', []))
        ref_count = pub.get('ref_count', 0)
        date_range = f'{pub.get("date_range", {}).get("start", "?")} — {pub.get("date_range", {}).get("end", "?")}'
        confidence = pub.get('confidence', '?')

        lines.append('| 项目 | 内容 |')
        lines.append('|------|------|')
        lines.append(f'| v2引用次数 | {ref_count} |')
        if aliases:
            lines.append(f'| 别名 | {aliases} |')
        lines.append(f'| 出版时间 | {date_range} |')
        lines.append(f'| 出版地 | {pub.get("place", "?")} |')
        if 'publisher' in pub:
            lines.append(f'| 出版者 | {pub["publisher"]} |')
        lines.append(f'| 置信度 | {confidence} |')
        if 'verification_sources' in pub:
            sources_str = format_sources(pub.get('verification_sources', []))
            lines.append(f'| 查证来源 | {sources_str} |')

        if 'issues' in pub:
            lines.append('')
            lines.append('**期号→年月：**')
            lines.append('')
            lines.append('| 期号 | 出版年月 |')
            lines.append('|------|----------|')
            for iss, date in pub['issues'].items():
                lines.append(f'| 第{iss}期 | {date} |')

        if 'issue_to_year' in pub:
            lines.append('')
            lines.append('详见 JSON 文件中的 `issue_to_year` 字段。')

        if 'notes' in pub:
            lines.append('')
            lines.append(f'> 📝 {pub["notes"]}')

        # v2 locations (for low-count publications)
        if pub.get('v2_locations'):
            lines.append('')
            lines.append('**v2 出处：**')
            lines.append('')
            for loc in pub['v2_locations']:
                lines.append(f'- [{loc["编"]}] **{loc["article"]}**（{loc.get("子目", "")}）— `[{loc["type"]}]` {loc["raw_text"][:120]}')

        lines.append('')

    # ── Section 3: 日期嵌入型 ──
    lines.append('---')
    lines.append('')
    lines.append('## 三、日期嵌入型（引用自带日期）')
    lines.append('')
    lines.append('此类刊物的引用文本中直接包含日期（如「见二十五年七月佛教日报」），不需要额外对照表。')

    for name, pub in categories['日期嵌入型']:
        lines.append('')
        lines.append(f'### {name}')
        lines.append('')
        lines.append('| 项目 | 内容 |')
        lines.append('|------|------|')
        lines.append(f'| v2引用次数 | {pub.get("ref_count", 0)} |')
        if pub.get('aliases'):
            lines.append(f'| 别名 | {" / ".join(pub["aliases"])} |')
        lines.append(f'| 出版时间 | {pub.get("date_range", {}).get("start", "?")} — {pub.get("date_range", {}).get("end", "?")} |')
        lines.append(f'| 出版地 | {pub.get("place", "?")} |')
        if 'date_format_in_reference' in pub:
            lines.append(f'| 引用日期格式 | {pub["date_format_in_reference"]} |')
        lines.append(f'| 置信度 | {pub.get("confidence", "?")} |')
        if 'verification_sources' in pub:
            sources_str = format_sources(pub.get('verification_sources', []))
            lines.append(f'| 查证来源 | {sources_str} |')
        if 'notes' in pub:
            lines.append('')
            lines.append(f'> 📝 {pub["notes"]}')
        lines.append('')

    # ── Section 4: 报纸 ──
    lines.append('---')
    lines.append('')
    lines.append('## 四、报纸')
    lines.append('')
    lines.append('报纸引用通常自带日期，无需卷期对照。')

    lines.append('')
    lines.append('| 报纸名 | v2次数 | 别名 | 出版时间 | 查证来源 | 备注 |')
    lines.append('|--------|--------|------|----------|----------|------|')
    for name, pub in categories['报纸']:
        aliases = ' / '.join(pub.get('aliases', []))
        date_range = f'{pub.get("date_range", {}).get("start", "?")} — {pub.get("date_range", {}).get("end", "?")}'
        sources = format_sources(pub.get('verification_sources', []))
        notes = pub.get('notes', '')[:60]
        lines.append(f'| {name} | {pub.get("ref_count", 0)} | {aliases} | {date_range} | {sources} | {notes} |')

    # ── Section 5: 单行本 ──
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 五、单行本 / 丛书 / 讲演集')
    lines.append('')
    lines.append('这些是书籍或特定出版物，无卷期号。引用中的信息通常为出版者或出版年份。')

    lines.append('')
    lines.append('| 名称 | v2次数 | 类型 | 出版时间 | 查证来源 | 备注 |')
    lines.append('|------|--------|------|----------|----------|------|')
    for name, pub in categories['单行本']:
        date_range = f'{pub.get("date_range", {}).get("start", "?")} — {pub.get("date_range", {}).get("end", "?")}'
        sources = format_sources(pub.get('verification_sources', []))
        notes = pub.get('notes', '')[:80]
        lines.append(f'| {name} | {pub.get("ref_count", 0)} | {pub.get("period", "—")} | {date_range} | {sources} | {notes} |')

    # ── Section 6: 出版机构 ──
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 六、出版机构')
    lines.append('')
    lines.append('非刊物，是出版社。在刊载信息中出现时，通常表示单行本由此机构印行。')

    lines.append('')
    lines.append('| 机构名 | v2次数 | 出版时间 | 查证来源 | 备注 |')
    lines.append('|--------|--------|----------|----------|------|')
    for name, pub in categories['出版机构']:
        date_range = f'{pub.get("date_range", {}).get("start", "?")} — {pub.get("date_range", {}).get("end", "?")}'
        sources = format_sources(pub.get('verification_sources', []))
        lines.append(f'| {name} | {pub.get("ref_count", 0)} | {date_range} | {sources} | {pub.get("notes", "")} |')

    # ── Section 7: 快速换算参考 ──
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 七、快速换算参考')
    lines.append('')
    lines.append('### 海潮音速查表')
    lines.append('')
    lines.append('| 海刊卷号 | 公元年 | 民国年 | 备注 |')
    lines.append('|----------|--------|--------|------|')
    for vol in range(1, 31):
        yr = 1919 + vol
        mg = yr - 1911
        notes = ''
        if vol == 1:
            notes = '创刊（杭州）'
        elif vol == 9:
            notes = '曾改名《人海灯》'
        elif vol == 18:
            notes = '抗战爆发'
        elif vol == 30:
            notes = '迁台（第5期起）'
        elif vol == 26:
            notes = '抗战胜利'
        lines.append(f'| {vol} | {yr} | {mg} | {notes} |')

    lines.append('')
    lines.append('### 佛历换算（参考）')
    lines.append('')
    lines.append('太虚全书中出现的佛历年有不同换算标准，常见两种：')
    lines.append('- 佛历 = 公元 + 544（标准南传佛教历）')
    lines.append('- 佛历 = 公元 + 989～1027（某些中国佛教文献使用的偏移）')
    lines.append('')
    lines.append('实际使用时，建议以文本上下文和太虚生平（1889-1947）为约束，取落在合理范围内的年份。')

    # ── Section 8: 数据来源 ──
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 八、主要数据来源')
    lines.append('')
    for src in meta.get('sources', []):
        lines.append(f'- {src}')
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('### 待查证项（Low Confidence）')
    lines.append('')
    low_conf = [(n, p) for n, p in pubs.items() if p.get('confidence') == '低']
    lines.append(f'以下{len(low_conf)}种刊物标记为低置信度，需要进一步查证：')
    lines.append('')
    for name, pub in low_conf:
        notes = pub.get('notes', '')[100:]
        lines.append(f'- **{name}**（{pub.get("ref_count", 0)}次引用）：{pub.get("notes", "")[:120]}')
    lines.append('')

    # ── Section 9: Full publication list ──
    lines.append('---')
    lines.append('')
    lines.append('## 九、刊物总目（按引用次数排序）')
    lines.append('')
    lines.append('| 序号 | 刊物名 | 引用次数 | 类别 | 置信度 | 别名 |')
    lines.append('|------|--------|----------|------|--------|------|')
    all_pubs = sorted(pubs.items(), key=lambda x: -x[1]['ref_count'])
    for i, (name, pub) in enumerate(all_pubs, 1):
        cat = pub.get('category', '?')
        conf = pub.get('confidence', '?')
        aliases = ' / '.join(pub.get('aliases', [])) if pub.get('aliases') else '—'
        lines.append(f'| {i} | {name} | {pub["ref_count"]} | {cat} | {conf} | {aliases} |')

    lines.append('')
    lines.append(f'> 共 {len(pubs)} 种刊物。引用次数为 0 的为 v2 中间接触及但无直接条目的。')

    # Write
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    print(f'Generated {md_path}')
    print(f'  Sections: 卷期制期刊({len(categories["卷期制期刊"])}), '
          f'期号制({len(categories["期号制刊物"])}), '
          f'日期嵌入型({len(categories["日期嵌入型"])}), '
          f'报纸({len(categories["报纸"])}), '
          f'单行本({len(categories["单行本"])}), '
          f'出版机构({len(categories["出版机构"])})')


if __name__ == '__main__':
    main()
