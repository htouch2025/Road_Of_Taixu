# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

整理《太虚大师全书》的文本资料，产出可用的数字版本。以 CBETA TEI P5 XML（本地 `_data/cbeta/TX/`，共 40 个文件）为权威源，按 CBETA 的 20 编（na001–na020）组织，不按实体书 32 册。所有产出统一使用 CBETA 繁体中文。

## Essential Commands

### 提取编级目录（catalog）
```bash
python3 agent_skills/cbeta-xml-reader/scripts/extract_book_catalog.py \
  _data/cbeta/TX/TX01/TX01n0001.xml _data/cbeta/TX/TX02/TX02n0001.xml \
  --book "第一编 佛法總學" --book-num 1
```
输出 `_research/{NN}_{编名}/_{NN}_{编名}_編目錄.json` + `.md` + 仪表盘。

### 提取文章全文
```bash
# 单篇（--catalog 模式自动写入 YAML frontmatter + 回写字数到编目录）
python3 agent_skills/cbeta-xml-reader/scripts/extract_article_fulltext.py \
  --catalog _research/01_佛法總學/_01_佛法總學_編目錄.json \
  --article "佛學概論" --data-dir _data/cbeta/TX

# 批量（同一子目下：--from/--to 是子目內編號；不加 --子目 时是全局編號）
python3 agent_skills/cbeta-xml-reader/scripts/extract_article_fulltext.py \
  --batch --catalog _research/01_佛法總學/_01_佛法總學_編目錄.json \
  --子目 概論 --from 1 --to 5 --data-dir _data/cbeta/TX

# 批量（跨子目：不加 --子目，--from/--to 是全局編號，一次只生成一份校对报告）
python3 agent_skills/cbeta-xml-reader/scripts/extract_article_fulltext.py \
  --batch --catalog _research/02_五乘共學/_02_五乘共學_編目錄.json \
  --from 1 --to 10 --data-dir _data/cbeta/TX
```

### 关键词提取
```bash
# Phase A：生成候选 JSON
python3 agent_skills/keyword-extractor/scripts/extract_keywords.py \
  --article _research/01_佛法總學/01_概論/03_佛法導言.md

# Phase A+B：生成完整 prompt 供 Codex 标注
python3 agent_skills/keyword-extractor/scripts/extract_keywords.py --build-prompt \
  _research/01_佛法總學/01_概論/03_佛法導言.md > /tmp/prompt.md

# 写入四维标注
python3 agent_skills/keyword-extractor/scripts/extract_keywords.py \
  --apply _research/01_佛法總學/01_概論/03_佛法導言.md \
  --concepts '["菩提心","涅槃"]' --domains '["基礎教義"]' \
  --functions '["入门导引"]' --bearings '["解脱道"]'

# 缺口审查
python3 agent_skills/keyword-extractor/scripts/extract_keywords.py --review-gaps-apply
```

### 刊载信息批量扫描
```bash
python3 agent_skills/cbeta-xml-reader/scripts/extract_publication_info.py
# 输出：_research/太虚大师全书刊载信息全录_v2.md
```

### 旧文章迁移（补加 frontmatter + 重命名）
```bash
python3 agent_skills/cbeta-xml-reader/scripts/add_frontmatter_to_existing.py \
  _research/01_佛法總學/_01_佛法總學_編目錄.json --dry-run  # 先预览
```

### 刊载信息查表
```bash
python3 agent_skills/cbeta-xml-reader/scripts/publication_lookup.py "海潮音" "18卷9期"
```

## Architecture

### Data flow
```
_data/cbeta/TX/*.xml  (CBETA TEI P5, 40 files, 500-900KB each)
    │
    ▼ extract_book_catalog.py
_research/{NN}_{编名}/_{NN}_{编名}_編目錄.json  (catalog with byte offset + linked list)
    │
    ▼ extract_article_fulltext.py
_research/{NN}_{编名}/{NN}_{子目}/{NN}_{篇名}.md  (article MD with YAML frontmatter)
    │
    ▼ extract_keywords.py (Phase A + Phase B via Codex)
frontmatter updated: concepts / domains / functions / bearings
    │
    ▼ Obsidian Dataview
_{NN}_{编名}_仪表盘.md  (auto-generated per-编 dashboard)
```

### Directory structure
- `_data/cbeta/TX/` — 40 个本地 CBETA TEI P5 XML 文件，按 `TXnn/TXnnn000n.xml` 组织
- `_data/dict/` — 佛学字典（Soothill-Hodous、丁福保等）
- `_data/mfqk/` — 民国期刊数据库（SQLite + Web 前端），用于查刊物出版日期
- `_data/刊载信息卷期对照表.md` — 海潮音等刊物的卷期→日期对照表，`publication_lookup.py` 查表用
- `_research/` — 工作产出：按 `{NN}_{编名}/{NN}_{子目}/` 组织，每篇文章一个 `.md`
- `agent_skills/cbeta-xml-reader/` — 核心 skill：XML 解析、目录提取、全文生成、刊载信息扫描
- `agent_skills/keyword-extractor/` — 关键词提取 skill：Phase A 程序匹配 + Phase B LLM 四维标注
- `source/` — 原始文本资料（20 编空目录框架）
- `docs/cbeta-tei-reference.md` — CBETA TEI P5 XML 结构参考手册

### CBETA ID mapping
| CBETA ID | 编 |
|----------|----|
| TX00na001 | 编纂说明 |
| TX01–TX02 | 第一编 佛法總學 |
| TX03n0002 | 第二编 五乘共學 |
| TX03n0003 | 第三编 三乘共學 |
| TX04–TX05 | 第四编 大乘通學 |
| TX06–TX07 | 第五编 法性空慧學 |
| TX07n0006–TX09 | 第六编 法相唯識學 |
| TX10–TX15 | 第七编 法界圓覺學 |
| TX16 | 第八编 律釋 |
| TX17 | 第九编 制議 |
| TX18n0010 | 第十编 學行 |
| TX18n0011–TX19 | 第十一编 真现实論宗依論 |
| TX20n0012 | 第十二编 真现实論宗體論 |
| TX20n0013–TX23 | 第十三编 真现实論宗用論 |
| TX23n0014–TX24 | 第十四编 支論 |
| TX24n0015 | 第十五编 時論 |
| TX25 | 第十六编 書評 |
| TX26–TX27n0017 | 第十七编 酬對 |
| TX27n0018–TX28 | 第十八编 講演 |
| TX29–TX31 | 第十九编 文叢 |
| TX32 | 第二十编 詩存 |

## Key Conventions

### 编目录 JSON（核心数据结构）
`_編目錄.json` 是目录入口，`篇目鏈表` 中每条记录含：`編號`（编内全局连续序号）、`子目內編號`、`file`、`byte_start`/`byte_end`（字节偏移）、`prev`/`next`（链表指针）、`題注`、`字数`。读取文章时先查此 JSON 获取字节偏移，用 `open(path, 'rb')` + `seek()` + `read()` 定点读取 XML 片段，绝不加载完整 XML 到上下文。

### YAML frontmatter schema
每篇文章 MD 以 YAML frontmatter 开头：`book`, `book_number`, `category`, `sequence`, `word_count`（千字）, `create_y/m/d`（创作日期）, `publication`（刊名）, `publish_y/m/d`（出版日期，查刊载信息卷期对照表获得）, `location`（讲说地点）, `concepts`/`domains`/`functions`/`bearings`（四个手工/LLM 标注维度）。

### cb:mulu level 体系（shift rule）
CBETA 的 `<cb:mulu level="N">` 中 level 数字是相对于父节点的层级，非固定语义。需按 shift rule 判定：有无「部」层会影响 level 3/4/5 的语义映射。详見 `agent_skills/cbeta-xml-reader/references/level_guide.md`。

### 命名空间
CBETA 命名空间 `{http://www.cbeta.org/ns/1.0}`，TEI 命名空间 `{http://www.tei-c.org/ns/1.0}`。使用 Python `xml.etree.ElementTree`（无 lxml，需手动构建 `parent_map`）。

### 本项目的硬约束
- **⛔ 不调用任何 MCP 服务器**（包括 buddha MCP）。所有 CBETA 读取走本地文件。
- 所有产出为纯 Markdown（非 Obsidian 特有语法：无 `[[]]`、`^` 块锚点、`{#}` 自定义锚点）。
- 全文提取时绝不加载完整 XML 到上下文，始终走「查 JSON → 字节偏移 → 定点读取」路径。
- 用户输入可能为简体，搜索 CBETA 内容前需转为繁体。
