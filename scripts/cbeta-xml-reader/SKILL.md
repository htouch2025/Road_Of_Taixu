---
name: cbeta-xml-reader
description: "Read CBETA TEI P5 XML files for the 太虚大师全书 (Collected Works of Master Taixu). Use when Codex needs to: (1) read or navigate CBETA XML source texts from local _data/cbeta/TX/ files, (2) extract article catalogs and document hierarchy (编/篇/部/章/节/小节) from CBETA structured data, (3) interpret cb:mulu level attributes and disambiguate semantic levels like 章 vs 节 vs 部, (4) cross-reference CBETA content against the paper edition table of contents, (5) process legacy DOC/HTML editions and compare them with the authoritative CBETA TEI version."
metadata:
  version: "0.15.0"
  last_updated: "2026-06-21"
  status: active
  task_type: open-ended
---

> **用户要求**：见 [requirements.md](requirements.md)。此文件仅记录用户需求，非实现方法。当用户说「更新 skill」时：先分析本次新经验是否涉及需求变更（新增需求、需求语义变化）。若是纯实现方法改进（bug 修复、算法调整、代码结构优化——需求未变），则不改 requirements.md。仅当需求确有新增或变更时，才修改 requirements.md。

# CBETA XML Reader — 太虚大师全书

> **⛔ 本项目无 MCP 服务器，禁止一切 MCP 工具调用。** 所有操作均通过本地文件系统（`cat`/`sed`/`grep`/Python）和 shell 命令完成。不要使用 `read_mcp_resource`、`list_mcp_resources`、`list_mcp_resource_templates`，也不要以任何形式搜索或调用 MCP server。读取本地文件一律用 `exec_command`（如 `cat`/`grep`/`sed`），不要用 `read_mcp_resource`。

Read and navigate CBETA TEI P5 XML files for the 太虚大师全书 from local `_data/cbeta/TX/` files. This skill consolidates knowledge gained from analyzing the CBETA catalog, loading XML source files, and interpreting the TEI markup for directory structure extraction.

**⛔ 硬规定：本项目绝不使用 buddha MCP（`mcp__buddha__*`）。** 全部 40 个 TX XML 文件已下载至 `_data/cbeta/TX/` 本地目录，所有 CBETA 读取操作直接用 Python + ElementTree 解析本地文件。不得调用 `mcp__buddha__fetch`、`mcp__buddha__search`、`mcp__buddha__pipeline`、`mcp__buddha__resolve` 等任何 buddha MCP 工具。

**全项目中文规范：本项目所有产出（目录树、JSON、备註等）统一采用繁体中文，与 CBETA 源文件一致，不做繁简转换。搜索时注意用户输入可能为简体，需先转换为繁体再匹配 CBETA 内容。**


## Quick Start

### 读取单篇文章（字节偏移法 — 推荐）

先查 JSON 目录获取字节偏移，再仅读取目标文章范围的 XML 片段：

```python
import json, xml.etree.ElementTree as ET

# 1. 查 JSON 目录获取偏移量
with open('_research/01_佛法總學/_01_佛法總學_編目錄.json') as f:
    catalog = json.load(f)
art = catalog['篇目鏈表'][22]  # 0-based index

# 2. 仅读取该文章字节范围（全文件 920KB，只读 51KB）
with open(f'_data/cbeta/TX/TX01/{art["file"]}', 'rb') as f:
    f.seek(art['byte_start'])
    chunk = f.read(art['byte_end'] - art['byte_start'])

# 3. 包装命名空间后解析
wrap = '<root xmlns:cb="http://www.cbeta.org/ns/1.0" xmlns:tei="http://www.tei-c.org/ns/1.0">' \
     + chunk.decode('utf-8') + '</root>'
el = ET.fromstring(wrap)
all_text = ''.join(el.itertext())  # 纯文本全文
```

### 读取整卷 XML（不推荐，上下文太大）

读取本地 TX XML 文件：

## 篇目链JSON 结构规范

编级 `_編目錄.json` 是目录的核心数据结构，所有后续文章提取都以此为入口。

### 顶层结构

```json
{
  "编": "第一编 佛法總學",
  "编序号": 1,
  "來源文件": [
    {"file": "TX01n0001.xml", "lb_start": "0001a01", "lb_end": "0529a08", "lb_count": 6330},
    ...
  ],
  "子目": [
    {"名稱": "概論", "篇數": 8, "篇名": ["佛學概論", ...]},
    ...
  ],
  "篇目總數": 34,
  "篇目鏈表": [...]
}
```

### 篇目鏈表条目结构

每个条目是一个文章节点，同时也是一个链表节点：

| 字段 | 类型 | 说明 |
|------|------|------|
| `編號` | int | 编内全局流水号（1-based），跨子目连续编号 |
| `子目內編號` | int | 子目内流水号（1-based），每个子目独立从 1 起编 |
| `篇名` | string | 文章名，与 CBETA `<cb:mulu level="2">` 一致 |
| `子目` | string | 所属子目类别（概論/判攝/源流等） |
| `file` | string | CBETA XML 文件名（如 `TX01n0001.xml`） |
| `mulu_index` | int | CBETA `<cb:mulu>` 全局序号（从 0 起计） |
| `byte_start` | int | 文章 `<cb:div>` 起始字节偏移 |
| `byte_end` | int | 文章结束字节偏移（下一篇文章的起始，或文件末尾） |
| `byte_size` | int | 文章原始字节长度（byte_end - byte_start） |
| `prev` | string/null | 前一篇文章名（链表前驱，首篇为 null） |
| `next` | string/null | 后一篇文章名（链表后继，末篇为 null） |
| `prev_index` | int/null | 前一篇文章的 mulu_index |
| `next_index` | int/null | 后一篇文章的 mulu_index |

> **字节偏移计算方式**：`scan_byte_offsets()` 通过深度追踪（`find_div_end`）正确定位每个 `<cb:div>` 的闭合标签，而非简单取下一个 div 的起始位置。提取后自动校验相邻文章 byte 范围，发现越界（overshoot）或异常大间距（>500 bytes）时输出警告。

### 链表语义

链表按编内顺序串联所有文章，跨文件过渡也自然衔接（如第 26 篇在 `TX01n0001.xml`，第 27 篇在 `TX02n0001.xml`，`next`/`prev` 不受文件边界影响）。

**读前一篇文章：** `catalog['篇目鏈表'][i - 1]`（验证 `prev` 名匹配）
**读后一篇文章：** `catalog['篇目鏈表'][i + 1]`（验证 `next` 名匹配）

## 高效文章提取工作流

### 原则：先查目录，再定点读取

绝不将完整 XML 文件加载到上下文中（单个 TX 文件 500KB–900KB）。所有文章提取遵循「目录定位 → 字节读取 → 片段解析」三步：

```
用户请求某文章
    │
    ▼
查编级 `_編目錄.json`，获取 file + byte_start + byte_end
    │
    ▼
open(file, 'rb') → seek(byte_start) → read(byte_end - byte_start)
    │
    ▼
包装命名空间 → ET.fromstring() → itertext() 或 walk tree
```

### 典型用法

**提取全文：** 按 Quick Start 中的字节偏移法，`itertext()` 一次拿全部纯文本。

**提取目录树：** 解析 XML 片段中的 `<cb:mulu>` 元素，按 shift rule 构建层级。

**提取题注：** 解析片段中的 `<head>` + `<byline>` + `<note>` 元素。

### 边界情况

- **图表文章**（如《佛藏擇法眼圖》1.1KB）：字节偏移仍准确，但内容为表格/标注，`itertext()` 能提取但格式受损。此类文章应优先查阅纸质版。
- **跨卷文章**：如果单篇文章跨两个 TX 文件（目前第一编未发现此情况），需分别从两个文件读取片段后拼接。

```python
import xml.etree.ElementTree as ET
tree = ET.parse('_data/cbeta/TX/TX01/TX01n0001.xml')
root = tree.getroot()
ns = '{http://www.cbeta.org/ns/1.0}'
```

- 所有 TX 文件在 `_data/cbeta/TX/TXnn/TXnnn000n.xml`
- CBETA 命名空间: `{http://www.cbeta.org/ns/1.0}`

提取目录：
```python
mulu_elems = root.findall(f'.//{ns}mulu')
```

搜索正文：
```python
# 在 body 中搜索
body = root.find(f'.//{ns}text/{ns}body')
```

## The cb:mulu Level System

The TEI header contains `<cb:mulu>` (目录) elements with `level` attributes that encode the document hierarchy. **The level number is relative to the parent node, NOT a fixed semantic label.**

### Standard hierarchy (when all levels present)

| Level | Semantic | Pattern | Example |
|:-----:|----------|---------|---------|
| 1 | 子目类别 | — | 概論 / 判攝 / 源流 |
| 2 | 篇（文章名） | — | 佛學概論 / 中國佛學 |
| 3 | 部 或 章 | 无编号，或 第X章 | 緒言 / 學史，或 第一章 佛學大綱 |
| 4 | 章 或 節 | 第X章，或 第一節 | 第一章 釋尊略傳，或 第一節 解釋… |
| 5 | 節 或 小節 | 第一節，或 一、二、三 | 第一節 總論，或 一 心之分析 |
| 6 | 小節 或 小小節 | 一、二、三，或 甲、乙、丙 | 一 安般禪，或 甲 慧文慧思之創發 |

### Shift rule: levels shift depending on what levels exist

- **有「部」的文章**（如《佛學概論》：緒言/學史/學理/結論）→ level 3 = 部、level 4 = 章、level 5 = 節
- **無「部」的文章**（如《中國佛學》）→ level 3 = 章、level 4 = 節
- **無「章」僅有「節」的段落**（如結論下的節）→ 節直接從 level 4 開始（跳過章）

Full examples and edge cases in `references/level_guide.md`.

### How to interpret a level

1. Read the `level` attribute value from `<cb:mulu>`
2. Look at how many levels are above it in the current subtree
3. Match the text pattern: 「第一章」→ 章、「第一節」→ 節、「一／二／三」→ 小節、「甲／乙／丙」→ 小小節
4. If the text has no numbering (like 緒言、學史、結論), check its depth: directly under 篇 (level 3) → 可能是「部」；under 章 → 可能是節

## 太虚全书 CBETA ID 体系

| CBETA ID 范围 | 内容 |
|---------------|------|
| TX00na001 | 编纂说明 |
| TX01n0001–TX02n0001 | 第一编 佛法總學 |
| TX03n0002 | 第二编 五乘共學 |
| TX03n0003 | 第三编 三乘共學 |
| TX04n0004–TX05n0004 | 第四编 大乘通學 |
| TX06n0005–TX07n0005 | 第五编 法性空慧學 |
| TX07n0006–TX09n0006 | 第六编 法相唯識學 |
| TX10n0007–TX15n0007 | 第七编 法界圓覺學 |
| TX16n0008 | 第八编 律釋 |
| TX17n0009 | 第九编 制議 |
| TX18n0010 | 第十编 學行 |
| TX18n0011–TX19n0011 | 第十一编 真现实論宗依論 |
| TX20n0012 | 第十二编 真现实論宗體論 |
| TX20n0013–TX23n0013 | 第十三编 真现实論宗用論 |
| TX23n0014–TX24n0014 | 第十四编 支論 |
| TX24n0015 | 第十五编 時論 |
| TX25n0016 | 第十六编 書評 |
| TX26n0017–TX27n0017 | 第十七编 酬對 |
| TX27n0018–TX28n0018 | 第十八编 講演 |
| TX29n0019–TX31n0019 | 第十九编 文叢 |
| TX32n0020 | 第二十编 詩存 |

Full catalog with 四藏分类 in `references/taixu_catalog.md`.

## 核心工作流

### 进度状态

| 编 | 名称 | 状态 | 文章数 |
|----|------|------|--------|
| 第一编 | 佛法總學 | ✅ 已完成 | 34 |
| 第二编 | 五乘共學 | ✅ 已完成 | 22 |
| 第三编 | 三乘共學 | ⏳ 待提取 | — |
| 第四编 | 大乘通學 | ✅ 已完成 | 21 |
| 第五编 | 法性空慧學 | ✅ 已完成 | 16 |
| 第十八编 | 講演 | ✅ 已完成 | 30 |
| 第六编/第七编/第九至二十编 | — | ⏳ 待提取 | — |

**⛔ 实验阶段说明：本项目处于研究性、实验性阶段。** 各编目录下的文件提取不完备是正常现象——文件可能已被提取后测试完删除、或尚未提取。**提取不完整不构成 skill 健康问题**，健康检查应关注：脚本可运行性、文档内部一致性、代码与文档是否同步、数据文件完整性（XML 是否就位、catalog JSON 结构是否正确），而非文章 MD 的提取覆盖率。

**原则：所有 CBETA 文件读取均在本地 `_data/cbeta/TX/` 目录完成。**
全部 40 个 TX XML 文件已就位于本地，直接用 Python + ElementTree 解析，跳过网络开销。

**重要：TX 文件的 `<cb:mulu>` 在 `<text>` body 中，不在 TEI header 中。** 在 CBETA TEI P5 的 TX（太虚全书）文件中，目录标记以嵌套 `<cb:div><cb:mulu>` 结构承载于 body 内。

### 1. 提取整编篇名目录（编级 catalog）

**⚠️ 提取後須做兩項人工複核：**（1）檢查是否有帶「（附）」前綴的 level-2 條目需合併入前一篇；（2）確認編內連續編號正確（跨子目不重置，从 1 递增至编末）。
詳見 Known Pitfalls 第 12、13 條。

使用 `scripts/extract_book_catalog.py`（路径相对于 skill 目录，即 `scripts/cbeta-xml-reader/scripts/`），仅提取 level 1（子目类别）和 level 2（篇名）。
脚本自动为每篇文章扫描原始文件字节偏移量，构建增强 JSON（含链表 + byte_start/byte_end）。

```
python scripts/extract_book_catalog.py \
  _data/cbeta/TX/TX01/TX01n0001.xml _data/cbeta/TX/TX02/TX02n0001.xml \
  --book "第一编 佛法總學" --book-num 1
```

`--out-dir` 可选，默认从 `--book-num` + `--book` 自动推导为 `_research/{编号}_{编名}/`。
输出 `_{编号}_{编名}_編目錄.md` + `_{编号}_{编名}_編目錄.json`。
**编目录 MD 已简化：** 从 v0.14 起，编目录 MD 仅展示编内连续编号 + 文章名，不再包含題注、字数等元数据（这些信息现在通过 YAML frontmatter 存入文章 MD 正文中，並由 Dataview 仪表盘汇总展示）。JSON 不变，仍保留完整元数据（`byte_start`、`byte_end`、`file`、`題注`、`字数`、`編號`、`子目內編號` 等），供提取脚本使用。

**编內连续编号规则：** 文章编号跨子目连续递增，不复位。例如第一编：概論 1–8、判攝 9–26、源流 27–34。文件名前缀使用 `編號`（编内全局序号），如 `22_新與融貫.md`。文件存储结构不变：依然 `_research/{NN}_{编名}/{NN}_{子目}/{編號:02d}_{篇名}.md`。

**提取其他编时**，改 `--book`、`--book-num` 和 XML 文件列表即可，路径自动填入。

### 2. 提取单篇文章完整目录树

1. 读取本地 XML 文件，构建 `parent_map`（见实现备忘 A），在 body 中搜集所有 `<cb:mulu>` 元素。
2. 找到 `<cb:mulu level="2">` 标签匹配文章名的条目，获取其所在卷 `div` 容器。
3. 以相邻 `level="2"` 条目位置为边界切分出目标文章的条目范围（见实现备忘 B）——该卷 `div` 内包含同卷所有文章。
4. 过滤掉纲要类节点（label 为「綱要」「目次」「科分」等纯结构预览条目）；如有「前言」则保留。
5. Apply the shift rule to assign semantic labels (部/章/节/小节)。
6. 递归构建树形结构（从 level 2 向下）。
7. Output two files to auto-derived path: `_research/{编dir}/{子目编号}_{子目名}/{文章编号}_{篇名}_目錄樹.md` + `_目錄.json`（从 `_編目錄.json` 查子目与编号，自动填入现有文件夹框架）。细节见下一节「双文件输出模式」。

### 3. 双文件输出模式

每提取一篇文章的目录树，同时生成两份文件，放在 `_research/{编}/` 的子目录下。目录结构采用三级编号命名：
- `_research/` → `{编号}_{编名}/`（如 `01_佛法總學/`）
- 编下 → `{编号}_{子目名}/`（如 `01_概論/`）
- 子目下 → `{编号}_{篇名}_目錄樹.md` / `_目錄.json`（如 `01_佛學概論_目錄樹.md`）

每篇文章的两份输出：

1. **`{篇名}_目錄樹.md`** — 给人看的清洁目录树：
   - 篇名顶格，若有题注则紧接一行（如 `（1932 年 12 月，在閩南佛學院講）`）；其后一空行再接 `## 目錄`
   - 篇名与目录树之间加 `## 目錄` 二级标题（Obsidian 可折叠），标题与目录树之间、目录树与備註之间各空一行
   - 使用 `- ` 嵌套列表表示层级
   - 不含 CBETA 内部标记（level、n 等）
   - 末尾附「備註」段说明特殊处理

2. **`{篇名}_目錄.json`** — 给机器看的完整元数据：
   - `article`：篇名
   - `cbeta_id`：所在 CBETA 文件 ID
   - `编`：编号
   - `子目`：子目类别（概论/判摄/源流）
   - `処理`：记录特殊处理（纲要去掉、前言保留等）
   - `tree`：树形数组，每个节点包含：
     - `label`：节点名称
     - `level`：CBETA 原始 `cb:mulu` level 值
     - `semantic`：语义解释（部/章/节/小节）
     - `n`：CBETA 位置标记（如 `008_18`）
     - `children`：子节点数组

**后续使用原则：**
- 生成其他文章目录时，按此模式自动出两份。
- 需要查找层级对应、n 标记、CBETA 位置等信息时，优先读 JSON 文件而非重新解析 XML。



### 4. 提取题下注释（byline/note）

许多太虚文章标题 `<head>` 之下、正文之前有题注（题下注释），记录讲说时间、地点、记录者等信息。常见 XML 标记：

| 标记 | 含义 | 示例 |
|------|------|------|
| `<byline cb:type="other">——…——</byline>` | 讲说时间地点 | `——二十一年十二月在閩南佛學院講——` |
| `<byline>（…記）</byline>` | 记录者 | `（碧松記）` |
| `<note place="inline">見海刊…</note>` | 刊载来源 | `見海刊十八卷九期` |

**提取方法：**
1. 找到文章 `<head>` 元素后的 `<byline>` 元素，提取其文本
2. 找到同区域的 `<note>` 元素，提取刊载信息

### 4a. 题注格式规范化

规范化规则（脚本中由 `normalize_byline()` 实现）：

**纪年转换：**

| 原始格式 | 规范化格式 | 规则 |
|----------|-----------|------|
| `——二十一年十二月在閩南佛學院講——` | `（1932 年 12 月，在閩南佛學院講）` | 民国纪年 +1911 → 公元 |
| `——宣統三年作——` | `（1911 年，作）` | 宣统纪年 +1908 → 公元 |
| `——三十三年春在漢藏教理院——` | `（1944 年春，在漢藏教理院）` | 裸中文数字 +1911 → 公元 |

**月份与季节空格规则（重要）：**

- 月份（如 `1 月`、`12 月`）前保留空格：`（1930 年 1 月，…）`
- 季节是单字（`春`/`夏`/`秋`/`冬`，`len=1`），前不加空格：`（1915 年春，…）`
- 实现方式：`split_month_season()` 拆分月份/季节与剩余文本，`build_suffix(month, rest)` 按 `len(month)==1` 判断分隔符（季节 → `''`，月份 → `' '`）

**不提取的注释：**

- ⛔ `見《海潮音》第X卷第X期` 等篇尾刊载来源 — 仅记录讲说信息（时间＋地点），不提取刊载出处
- 原因：刊载来源属于篇尾附注，非题下注释，在编级目录中不需要

**其它：**

- 本项目所有中文产出统一采用繁体，与 CBETA 原文一致，不做繁简转换
- `——…——` 外围符号 → `（…）`，日期与地点间加中文逗号
- 记录者保留原样：`（碧松記）`

**MD 输出：** 题注放在篇名之下、目录树之前，单独一行。格式如 `（1932 年 12 月，在閩南佛學院講）`。
**JSON 输出：** 放在 `題注` 字段中，无则为空字符串。


### 5. 全文输出（extract_article_fulltext.py）

部分太虚文章有篇末注释（back-notes），在 XML 中通过 `<back>` 区域的 `<note>` 元素标记，正文中通过 `<anchor xml:id="nkr_note_orig_N"/>` 引用。

**提取脚本** `extract_article_fulltext.py` 输出完整的文章 Markdown 全文。输出格式如下：

- 篇名 + 题注（第 1–2 行）
- `## 目錄` + 目录树（仅当文章内部有章节结构时才显示此标题；文章内部无目录时，不输出 `## 目錄`）
- 目录与正文之间以一道空行分隔（`normalize_blank_lines()` 将连续空行压缩为一行）
- 正文无 `## 正文` 分隔标题、无 `### 前言` 标题（前言内容直接作为正文首段）
- 正文标题从 `##`（H2）起步（因 `## 正文` 已删除，原 H3→H2、H4→H3 依此类推）
- 文末注释（如有）
- 文末记录者 + 刊载来源

脚本自动完成以下工作：

1. **注释发现**：扫描文章范围内的 `nkr_note_orig_*` 锚点 ID，按出现顺序编号
1. **正文标记**：在对应锚点位置插入纯数字 `N`（如 `1`、`2`），标题后注释号与标题正文间空一格（如 `# 佛學概論 1`、`### 學史 2`）
1. **文末注释**：每行格式为 `- N：注释正文`（如 `- 1：本論略本...`）
1. **篇末附注**：自动提取文章末尾的 `<byline>` 记录者信息和 `<note place="inline">` 刊载来源，如 `（碧松記）（原見海潮音月刊十八卷十一期）`

**处理嵌套 `<note>` 在 `<byline>` 内的情形：** 部分 CBETA 文件中，篇末刊载来源 `<note place="inline">` 嵌套在 `<byline>` 元素内部（而非平级），如 `<byline>（碧松記）<note place="inline">原見海潮音月刊十八卷十一期</note></byline>`。`extract_paragraphs()` 函数用 `child.itertext()`（而非 `child.text`）获取 byline 的完整文本（跨 `<lb/>` 断点），再从子 `<note>` 提取刊载文本，将 note 文本从 itertext 结果中剥离后组合为 `{own_text}（{nt}）`，两段文本均不丢失。

**图片提取**：当 CBETA XML 中包含 `<figure><graphic url="..."/>` 元素时，脚本自动识别并将其转换为本地 Markdown 图片引用。

- 图片存放于 `_research/figures/TX/` 目录（共 228 张，从 `cbeta-git/CBR2X-figures` 仓库获取）
- `render_paragraph()` 检测 `<p>` 唯一子元素为 `<figure>` 时，提取 `<graphic url="..."/>` 的 URL，取其文件名作为图片引用
- 图片路径通过 `os.path.relpath(figures_dir, out_dir)` 动态计算，自动适配不同输出深度（有子目两级深 `../../`、无子目一级深 `../` 等）
- CLI 参数 `--figures-dir` 可指定图片根目录，默认 `_research/figures/TX`
- 输出格式：`![filename](relative_path/filename)`

**输出格式**：纯文本 Markdown，无任何 Obsidian 特有语法（无 `[[...]]` 链接、无 `^` 块锚点、无 `{#...}` 自定义锚点）。在不同 Markdown 渲染器中表现一致，不依赖特定编辑器的扩展语法。


### 5a. YAML Frontmatter（文章元数据）

当使用 `--catalog` 模式提取全文时，脚本自动在文章 Markdown 文件开头插入 YAML frontmatter，从中提取元数据供 Obsidian Dataview 插件索引。

**Frontmatter schema：**

```yaml
---
book: 第一编 佛法總學
book_number: 1
category: 判攝
sequence: 22
publication: 原見海潮音月刊十八卷十一期
word_count: 4
date: 1937-08
location: 世界佛學苑研究部
keywords:
themes:
---
```

**字段说明：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `book` | 编目录 JSON `编` | 编名全称 |
| `book_number` | 编目录 JSON `编序号` | 编编号 |
| `category` | 编目录 JSON 条目 `子目` | 所属子目类别 |
| `sequence` | 编目录 JSON 条目 `編號` | 编内全局序号（跨子目连续） |
| `word_count` | 编目录 JSON 条目 `字数` | 千字整数（CJK 字符数 // 1000） |
| `publication` | XML `<byline><note place="inline">` | 刊载/印行信息，单值字符串；多条时用「；」连接（可选，无刊载信息时不出现） |
| `date` | 编目录 JSON 条目 `題注` 解析 | YYYY-MM 格式，无月份则为 YYYY |
| `location` | 编目录 JSON 条目 `題注` 解析 | 讲说/编述地点 |
| `keywords` | 手工填写 | 关键字，预留空值 |
| `themes` | 手工填写 | 核心思想，预留空值 |

**生成规则：**
- `build_frontmatter()` 函数从 catalog JSON 条目读取 `編號`、`子目`、`題注`、`字数`，调用 `parse_byline_fields()` 解析題注中的年代/地点/场合
- 年代格式化为 YYYY-MM（有月份）或 YYYY（无月份）
- `publication` 字段为单值字符串，来自 CBETA XML 原文中 `<byline>` 元素内的 `<note place="inline">` 文本，保持原貌不分类；多条刊载来源时以「；」连接；正文尾注中亦保留同样信息
- `word_count` 为字数 // 1000 的整数值
- frontmatter 与正文之间保留一个空行

**⚠️ 已有文章的迁移：** 使用迁移脚本 `add_frontmatter_to_existing.py`（详见下文「文章元数据迁移脚本」一节）。

## Known Pitfalls

1. **章名被误列为独立文章** — 网页版常见错误。如《中国佛学》下的「佛學大綱」「悟心成佛禪」等是章名，非独立文章。
2. **绪言歧义** — 「緒言」可以是 level‑3 部名（《佛學概論》），也可以是 level‑4 节名（《中國佛學》第三章第一節）。
3. **结论层级不等** — 在《佛學概論》中「結論」为 level‑3 部，其下直接是 level‑4 节（无章层）。
4. **level 号不作语义标签** — 不要假设 level="4" 一定是「章」或一定是「节」。
5. **纲要/科分/目次等纯结构预览须去掉** — 有些文章开头有「綱要」「目次」或「科分」，它们只是文章結構的預覽列表（科分即科判，揭示全文分科结构），不是獨立章節，在目錄樹中應去掉。判断标准：若条目为全文结构概览、无实质论述内容，即应过滤。
    - **skip 关键词完整列表：** `目次`、`綱要`、`目錄`、`目録`、`科分`。脚本 `should_skip_div()` 中须涵盖全部五个。
6. **前言保留** — 綱要之後如有「前言」，前言是文章的有用開場，應保留。在目錄樹中可將前言列於綱要原本所在的位置，或在備註中說明。
7. **简体搜索须转换为繁体** — 搜索时注意做简繁转换（CBETA 为繁体，用户输入可能为简体）。
8. **裸数字前缀贪婪匹配** — normalize_heading() 中裸数字的 regex 须只匹配第一个数字字符 `[{NUM}]`，不得用 `[{NUM}]+` 贪婪捕获连续数字，否则「一五蘊」会被误切为「一五　蘊」（正确：「一　五蘊」）。同理「二三法印」应为「二　三法印」而非「二三　法印」。
9. **TX 文件的 `<cb:mulu>` 在 body 中，不在 TEI header 中** — 在 CBETA TEI P5 的 TX（太虚全书）文件中，目录标记不在 `teiHeader` 内，而是以嵌套 `<cb:div>` 结构承载于 `<text>` body 中。提取目录时应在 body 中 walk `<cb:div>` 树，而非搜索 header 中的 `<cb:mulu>`。
10. **MD 缩进格式：使用 `- ` 嵌套列表而非纯空格** — 纯空格缩进在 Obsidian 等 Markdown 渲染器的阅读模式下不可见。应采用 `- ` 嵌套列表格式：
   ```
   - 文章名
       - 章
           - 节
   ```
11. **ElementTree 无 parent 指针** — Python 标准库 `xml.etree.ElementTree` 不支持 `lxml` 的 `iterancestors()`。需手动构建 `parent_map = {child: parent for parent in root.iter() for child in parent}`。见实现备忘 A。
12. **卷 div ≠ 文章 div** — 从 `<cb:mulu level="2">` 向上爬两级 div 得到的是整卷的容器 div（如 TX01n0001 全文），非单篇文章专属容器。不得对该 div 直接提取，而应以相邻 level=2 条目为边界切分。见实现备忘 B。
13. **CBETA 附錄文章誤列為獨立篇目** — 某些帶「（附）」前綴的 level-2 條目（如「（附）答生命研究之疑問」）是前一篇文章的附錄，CBETA 標為獨立 level-2，但依紙質版不應獨立成篇。特徵：
   - 篇名以「（附）」開頭
   - 緊跟前一篇之後，其間無 level-1（子目分隔）
   - 紙質版目錄中附屬於前一篇

   處理方式：
   - 將附錄合併入前一篇：前一篇的 `byte_end` 延伸到附錄的 `byte_end`
   - 從 `篇目鏈表` 中移除附錄條目，重連鏈表
   - 在前一篇的 `備註` 字段標註「含附錄：（附）…」
   - 更新對應子目的 `篇名` 列表和 `篇數`
   - 後續文章 `編號` 重新編排
14. **子目內篇號應獨立編號** — 每個子目下的文章編號從 1 起編，而非跨子目連續編號。例如：
15. **orig/commentary div 正文提取** — 部分文章（如《般若波羅密多心經講義》）的释经段落将正文存放在 `type="orig"` 和 `type="commentary"` 的 `<cb:div>` 子节点中，而这些 div 自身**没有** `<cb:mulu>` 或 `<head>` 标记作为标题。`extract_article_fulltext.py` 的 `walk_div_tree()` 原来遇到无标题的 div 就直接 `return`，导致整个释经部分只剩标题列表、没有任何正文。
    - **根因：** 标题 div（`type="other"`，含 `<cb:mulu>` + `<head>`）与正文 div（`type="orig"`/`type="commentary"`）是**同一个父 div 下的兄弟节点**关系。标题 div 本身不含 `<p>` 段落，正文全在兄弟 div 中。
    - **修复：** `walk_div_tree()` 在 `heading` 为空时不再直接 return，而是先尝试 `extract_paragraphs()`（正文 div 中有 `<p>` 子元素），再递归进入子 div。无标题的 div 不新增 TOC 条目、不输出标题行，只将正文段落追加到父级上下文。
    - **格式区分：** `type="orig"`（经论原文）的段落输出为 `> **原文**`（块引用 + 粗体）；`type="commentary"`（讲义注解）的段落照常输出为普通段落。这是根据 CBETA 原文中 orig div 使用 `margin-left:0em`、commentary div 使用 `margin-left:1em` 的排版差异还原的视觉区分。
16. **byline 内 `<lb/>` 导致 tail 文本丢失** — 部分 `<byline>` 内部嵌有 `<lb/>` 换行标记（如 `<byline>（明性<lb/>、湧泉合記）<note place="inline">見海刊...</note></byline>`）。旧代码用 `child.text` 取 byline 文本，但 `child.text` 只返回 `<byline>` 起始标签到第一个子元素（`<lb/>`）之间的文本——即 `（明性`，而 `<lb/>` 的 tail 文本 `、湧泉合記）` 被完全丢弃。修复：改用 `"".join(child.itertext())` 遍历所有子节点的 text 和 tail 以获取完整文本，再压缩空白。若有嵌套 `<note>`，需将 note 文本从 itertext 结果中剥离后分别输出。参见实现备忘 F。

    **空白压缩须一致（`own_text` 与 `nt` 同款处理）：** 若 `<note>` 内也含 `<lb/>`（如 `<note place="inline">見海刊<lb/>二卷四期</note>`），则 `nt = "".join(itertext()).strip()` 会保留 `<lb/>` tail 前的 `\n`，而 `own_text` 已通过 `"".join(split())` 去掉了该换行。两者空白格式不一致导致 `own_text.replace(nt, "")` 匹配失败，`own_text` 未被清掉，最终输出重复文本 `見海刊二卷四期（見海刊二卷四期）`。修复：`nt` 也必须用 `"".join(split())` 压缩，不使用 `.strip()`。
17. **文末 byline/note 被 extract_article_fulltext 跳過** — `extract_article()` 遍歷 `article_div` 子元素時僅處理 `<cb:div>`（第 457–459 行），而文末的記錄人 `<byline>` 和刊載來源 `<note place="inline">` 是 `article_div` 的直接子元素而非 `<cb:div>`，因而被整段跳過。結果是 `extract_article_fulltext.py` 生成的全文不含記錄人／刊載附注（如「（倪德薰記）（見海刊三卷五期）」）。
    - **根因：** `for child in article_div: if child.tag == f'{CBETA_NS}div':` 僅匹配 `<cb:div>`，漏掉同層的 `<byline>` 和 `<note>`。
    - **修復：** 在處理完所有子 `<cb:div>` 之後，額外對 `article_div` 本身調用 `extract_paragraphs(article_div)`，這樣就能把文末的 byline/note 也撿回來。題注 byline（`——…——` 格式）由 `get_byline_text()` 單獨處理，不會被重複加入。
18. **`extract_paragraphs` 丟棄 byline 自身文本（嵌套 `<note>` 情形）** — 當 `<byline>` 內部嵌套 `<note place="inline">` 時（如 `<byline>（碧松記）<note place="inline">原見海潮音月刊十八卷十一期</note></byline>`），舊代碼僅提取 `<note>` 的刊載文本並包裹為 `（{nt}）`，byline 自身的記錄者文本（`（碧松記）`）被完全丟掉。
    - **根因：** `extract_paragraphs()` 中遇到 byline/note 元素時，僅查找子 `<note>` 並輸出 `（{nt}）`，未提取 byline 自身文本。
    - **修復：** 改用 `child.itertext()`（而非 `child.text`）獲取完整文本，再將子 `<note>` 文本從中剝離後分別輸出。參見坑 #16 及實現備忘 E。
19. **刪掉 `## 正文` 後正文標題層級應上提一級** — 原結構中 `## 正文` 為 H2 級分隔標題，其下章節從 H3（`###`）起步。刪除後，正文標題應從 H2（`##`）起步，整體上提一級。
    - **實現：** 初始調用 `walk_div_tree()` 時傳 `level_offset=-1`，使 `effective_lv = mulu_lv - 1`。配合已有 floor 邏輯（`level_offset < 0` 時 floor=2），自動將 H3→H2、H4→H3 等。
20. **圖片引用路徑須動態計算，不得硬編碼** — 不同編的輸出目錄深度不同（有子目兩級深 `_research/{編}/{子目}/`，無子目一級深 `_research/{編}/`）。硬編碼固定層級的 `../` 會導致部分文章圖片無法載入。
    - **實現：** 在 `main()` 中通過 `os.path.relpath(FIGURES_BASE_DIR, out_dir)` 動態計算，`FIGURES_BASE_DIR` 預設為 `_research/figures/TX`。


21. **無嵌套 `<cb:div>` 的文章正文被完全跳過** — 部分文章（如圖表類《佛藏擇法眼圖》）沒有下級 `<cb:div>` 結構，`<p>` 段落和 `<figure>` 圖片是 `article_div` 的直接子元素。原代碼 `for child in article_div: if child.tag == cb:div:` 只遍歷 `<cb:div>` 子節點，若文章無嵌套 div，整個正文（段落 + 圖片 + 文末註記）被完全跳過，觸發 `is_chart=True` 空輸出。
    - **根因：** 與坑 #17 同源——`extract_article()` 的主循環僅匹配 `<cb:div>` 子節點。坑 #17 修復時僅處理了有嵌套 div 情況下丟失文末 byline/note 的情形，但未考慮**完全沒有嵌套 div** 的更極端情況。
    - **修復：** 加入 `has_child_div` 標記——若循環結束後仍為 `False`（即文章無任何下級 `<cb:div>`），則將 `article_div` 自身的 `<p>`、`<figure>`、`<byline>` 等直接子元素全部透過 `extract_paragraphs()` 提取進 `body_lines`。如此圖表文章也能正常輸出圖片鏈接和說明文字。


**批量提取（`--batch` 模式）：** 一次性提取同一子目下的连续多篇文章。

```bash
python extract_article_fulltext.py \
  --batch \
  --catalog _research/01_佛法總學/_01_佛法總學_編目錄.json \
  --子目 概論 \
  --from 3 --to 5 \
  --data-dir _data/cbeta/TX
```

参数说明：
- `--batch`：激活批量模式
- `--子目 <名称>`：目标子目（如 `概論`、`判攝`），须与编目录 JSON 中 `子目` 字段精确匹配
- `--from <n>` / `--to <m>`：起始/结束 編號（编内全局序号，1-based，含两端），仅筛选 range 内子目匹配的文章
- `--toc-only` 也可使用（批量只出目录树不提取正文）

批量模式特性：
- 每篇文章独立输出为单独的 `.md` 文件，命名规则与单篇模式一致（`{编号:02d}_{篇名}.md`）
- XML 文件查找仅执行一次（建立 `{filename: full_path}` 缓存），避免重复遍历目录树
- 编目录回写优化：每篇文章更新 JSON 字数后，仅在全部文章提取完毕后统一调用 `regenerate_catalog_md()` 刷新 MD 一次
- 支持跨文件提取（同一子目内文章可能分布在多个 TX XML 文件中）

### 6. 字数统计

21. **`<seg rend="bold">` 加粗丟失（旧版脚本生成的文件）** — CBETA TX 中使用 `<seg rend="bold">…</seg>` 标记的条目小标题（如佛法僧義廣論中的甲、乙、丙…条目），在用旧版提取脚本生成的 MD 文件中丢失了加粗格式（`**…**`）。
    - **CBETA 标记现状**：整个太虚全书 40 个 TX XML 文件中，`rend="bold"` 仅出现 25 次：TX01（佛法僧義廣論）21 次（甲—庚 × 三章）、TX29（另一篇文章）4 次（一—四 藏名）。全部为 `<seg rend="bold">` 形式，无 `<hi rend="bold">`，无 `type`/`n` 等额外语义属性。CBETA 没有 italic、underline、emph 等其他强调标记。
    - **语义**：纯排版加粗，无语义分层。`<seg rend="bold">` 用于段落内的条目小标题（天干 甲/乙/丙… 或 CJK 数字 一/二/三…），以视觉加粗区分层级。之所以用 `<seg>` 而非 `<head>`，是因为纸质版中这些条目是段落内的加粗开头句，而非独立标题行。
    - **脚本处理**：当前版 `extract_article_fulltext.py` 的 `render_paragraph()` 已正确处理 `seg` → `**...**` 的转换：
      ```python
      elif tag == "seg":
          if child.get("rend") == "bold":
              parts.append("**" + "".join(child.itertext()).strip() + "**")
      ```
   - **修复旧文件**：对于旧版脚本生成的 MD 文件（如 `08_佛法僧義廣論.md`），可手动补加 `**…**` 包裹全部 21 条 甲—庚 行，或重新运行当前版脚本重新提取。

22. **`cb:type="other"` 的 `<byline>` 在 fallback 路径中被重复输出** — 当文章无嵌套 `<cb:div>`（`has_child_div=False`）时，`extract_paragraphs(article_div)` 将 article_div 的所有直接子元素（包括题下注释 `<byline cb:type="other">——…——</byline>`）都输出到正文。但这条 byline 已被 `get_byline_text()` 提取并规范化为标题下方的题注，导致同一文本出现两遍（一次规范化、一次原始格式）。
    - **CBETA 结构特征**：无嵌套 div 的文章中，题注 `<byline cb:type="other">`、正文 `<p>`、文末记录者 `<byline>`、刊载 `<note>` 全是 article_div 的直接子元素，而非被 `<cb:div>` 包裹。这与有章节结构的文章不同。
    - **⚠️ `cb:type="other"` 不能作为判断依据** — CBETA 同时将此属性用于题下注释（`——…——` 格式）和文末记录者（`（…記）` 格式），纯靠属性区分会误伤尾注。正确方法是按文本格式：题下注释始终以 `——` 开头结尾，记录者以 `（` 开头。
    - **修复**：`extract_paragraphs()` 在处理 `<byline>` 时检查文本是否匹配 `——…——` 模式，是则 `continue` 跳过（题下注释，已由 `get_byline_text()` 处理）；否则照常输出（记录者）。这与 `get_byline_text()` 的位置判断逻辑互补，但用文本特征而非 XML 树位置做区分。

23. **「第X部分第N篇」歧义 — 全局编号 vs 子目内编号** — 当用户说「第一编第二部分第 15–18 篇」时，AI 容易将「15–18」误解为编级全局编号（`_編目錄.json` `篇目鏈表` 的 0-based index），而非「在第二部分内部编号 15–18」。本错误已重复发生，根因是数字编号在全局目录刚被读取时激活极强，压过了「第X部分」作为范围限定符的语义。
    - **用户表达规范：** 「第X部分」=「第X个子目」= `子目` 列表中的第 X 项。`_編目錄.json` 中 `子目` 为 `["概論", "判攝", "源流"]`，故「第二部分」→ `判攝`。
    - **正确流程：** ①先解析「第X部分」→ 子目名；②在该子目的 `篇目鏈表` 条目中按 `子目內編號` 定位第 N–M 篇；③绝不将数字范围直接用于全局 `篇目鏈表` index，除非用户明确说「编级全局编号」。
    - **检查方法：** 映射完编号后，验证 `art["子目"]` 是否匹配目标子目名。若不匹配，说明编号映射错误。

`extract_article_fulltext.py` 在提取正文后自动统计全文（不含 `## 目錄` 区块）的中文字符数。

**正文 MD 格式：** 在 byline 与 `## 目錄` 之间插入一行：

```
**21 千字**
```

**编目录回写：** 提取时若使用 `--catalog` 模式，自动将原始 CJK 字符数写入编目录 JSON 的 `字数` 字段，并刷新编目录 MD。MD 顯示简化为仅含连续编号 + 文章名。字数信息同步写入该文章的 YAML frontmatter 的 `word_count` 字段（千字整数）。

**计算方法：** 统计全文 `md_lines` 中除 `## 目錄` 至下一 `## ` 标题区间外的所有 CJK 字符（0x4E00–0x9FFF, 0x3400–0x4DBF, 0xF900–0xFAFF），千字 = 原始字符数 // 1000，取整数。

**编目录排序修复：** `regenerate_catalog_md()` 中子目排列从 JSON 的 `子目` 数组读取原始顺序，不再按字母序排列。


### 7. 标题编号空格规则

**基本原则：章节编号（前缀）与标题正文之间统一使用一个全角空格。**

此规则由 `extract_article_fulltext.py` 的 `normalize_heading()` 函数自动执行，适用于 TOC 条目和正文标题。`get_heading_text()` 会优先从 `<head>` 提取标题文本（已 strip 全角空格），无 `<head>` 时退到 `<cb:mulu>`（**也会 strip 全角空格**），确保 `normalize_heading()` 从干净文本出发统一插入一空格。

**六种前缀模式及处理：**

| 前缀类型 | 示例输入 | 输出 |
|---------|---------|------|
| CJK 裸数字+数字（2a） | `二三法印` | `二　三法印` |
| 第X章/节/篇 | `第一章釋尊略傳` | `第一章　釋尊略傳` |
| CJK 裸数字 | `一契理與應機` | `一　契理與應機` |
| 天干（非数字后） | `甲契理之實義` | `甲　契理之實義` |
| 天干+数字组合 | `甲一證信` | `甲一　證信` |
| 全角数字 | `１十善業為…` | `１　十善業為…` |

**天干组合规则（关键）：**
- Pattern 2a 处理**裸数字后紧跟另一个数字**的特殊情况（如 `二三法印`，取首数字 `二` 为前缀，结果为 `二　三法印` 而非 `二三　法印`）
- Pattern 3 仅在**天干后不紧跟 CJK 数字**时插入空格（负前瞻）
- Pattern 3b 处理**天干+数字**复合前缀（如 `甲一`、`乙二`），在组合后插入空格
- 这保证了 `甲一證信` 不被拆成 `甲　　一證信`，而是正确的 `甲一　證信`

**⚠️ 空标题跳过：**
`walk_div_tree()` 中，若 `normalize_heading()` 返回空字符串，直接 `return` 跳过该 `<cb:div>`。这消除了大量空字符串 MD5 的垃圾 TOC 条目。

## 目录树格式规范
 
整理目录树时应统一以下格式约定：
 
1. **缩进表示层级** — 使用 `- ` 嵌套列表表示层级关系（Markdown 可正确渲染嵌套），不使用树形绘制字符（├──、└──、│等）。每层缩进 **4 个空格**，即章 0 空格、节 4 空格、小节 8 空格、小小节 12 空格，依此类推。
2. **文章名为根** — 目录树以文章名（篇名）为根节点，全文左起顶格。
3. **不标注 level 编号** — 缩进本身已足以表示层级，不需要加 `(level N)` 之类的标注。
4. **纲要去掉** — 见 Known Pitfalls 第 5 条。
5. **前言保留** — 见 Known Pitfalls 第 6 条。
6. **備註说明例外** — 如有特殊处理（移除了纲要、保留了前言等），在目录树后的「備註」段落说明。
 
## 实现备忘 (Implementation Notes)

这些是本 skill 反复踩坑后沉淀的实战经验，后续生成目录树时直接照做。

### A. ElementTree 无内建 parent 指针

Python 标准库 `xml.etree.ElementTree` 不支持 `elem.parent` 或 `lxml` 的 `iterancestors()`。需要手动构建 parent 字典：

```python
parent_map = {}
for parent in root.iter():
    for child in parent:
        parent_map[child] = parent
```

之后用 `parent_map[elem]` 向上导航。

### B. 整卷 div 和单篇文章 div

从 `<cb:mulu level="2">` 向上爬两级 `div` 得到的并非该文章的专属容器，而是整个 CBETA 卷（如整卷 TX01n0001）的容器 `div`。该 `div` 包含同一卷内所有文章的全部 `<cb:mulu>` 条目。

正确做法：先收集整个卷 `div` 内所有 `<cb:mulu>` 条目（含所有文章），然后以相邻 `level="2"` 条目的位置为边界切分出目标文章的条目范围：

```python
# art_start = 首个 level=2 且 label 匹配的文章条目索引
# art_end   = 下一个 level=2 条目的索引（若为最后一篇则取 len(all_mulu)）
article_entries = all_mulu[art_start:art_end]
```



### C. 篇末注释提取（纯文本模式）

### 8. Dataview 仪表盘（编级概览页面）


**自动生成：** `extract_book_catalog.py` 在生成编目录时同时输出仪表盘，无需手工创建。
每编在 `_research/{NN}_{编名}/` 下配有 `_{NN}_{编名}_仪表盘.md`，使用 Obsidian Dataview 插件动态汇总该编所有文章的元数据。

**仪表盘查询（Dataview TABLE）：**

````
```dataview
TABLE word_count AS "千字", date AS "年代", location AS "地点", category AS "子目"
FROM "_research/01_佛法總學"
WHERE book AND sequence
SORT sequence ASC
```
````

**说明：**
- 无需手工维护——文章提取后 frontmatter 自动写入，仪表盘自动更新
- 可按 `category` 列筛选特定子目，也可按 `word_count` 排序找长文/短文
- `keywords` 和 `themes` 列可在需要时加入 TABLE
- 未来可添加 `WHERE category = "判攝"` 等过滤条件做子目专属视图

### 9. 文章元数据迁移脚本

[`scripts/add_frontmatter_to_existing.py`](scripts/add_frontmatter_to_existing.py) 用于为已提取的旧文章补加 YAML frontmatter，并同时将文件名前缀从子目內編號重命名为編號（编内全局序号）。

**用法：**

```bash
# 预览模式（推荐先运行）
python3 scripts/cbeta-xml-reader/scripts/add_frontmatter_to_existing.py \
  _research/01_佛法總學/_01_佛法總學_編目錄.json --dry-run

# 实际执行
python3 scripts/cbeta-xml-reader/scripts/add_frontmatter_to_existing.py \
  _research/01_佛法總學/_01_佛法總學_編目錄.json
```

**行为：**
1. 遍历编目录 JSON 的 `篇目鏈表`，找到每篇文章对应的已提取 `.md` 文件
2. 检查文件是否已有 YAML frontmatter（以 `---` 开头），有则跳过
3. 无 frontmatter 则从 JSON 条目生成并前置
4. 若文件名前缀为旧版 `子目內編號`，自动重命名为 `編號` 前缀
5. `--dry-run` 模式仅预览变更，不实际写入

**⚠️ 注意：** 重命名后 Obsidian 内部链接可能断裂，需手动核对。


`extract_article_fulltext.py` 的注释系统输出纯文本，无任何 Obsidian 跳转链接：

1. **`extract_article_notes()`**：扫描文章范围的 `<anchor xml:id="nkr_note_orig_N"/>` ID，与 `<back>` 区域的 `<note n="N" target="#nkr_note_orig_N">` 交叉匹配，返回 `[(num_label, note_text), ...]` 和 `anchor_ids` 有序列表
1. **正文标记**：在对应锚点位置插入纯数字 `N`，无链接。标题后注释号与标题正文间有一个空格（如 `# 佛學概論 1`）
1. **文末注释**：每行格式为 `- N：注释正文`（如 `- 1：本論略本...`），无回链
1. **篇末附注**：`extract_paragraphs()` 额外处理 `<byline>` 和 `<note place="inline">`，自动提取记录者（如「碧松記」）和刊载来源（如「原見海潮音月刊十八卷十一期」）
1. **无锚点**：不生成 `^h-xxxxxx` 块锚点、不生成 `^fn-body-N` 回链锚点、不生成 `{#h-xxxxxx}` 自定义锚点

### D. orig/commentary div 模式与格式区分

解经类文章（对佛经做逐句解读的文章）在 CBETA 中采用特殊的 div 结构：标题 div（`type="other"`）与正文 div（`type="orig"`/`type="commentary"`）是兄弟节点。

```xml
<cb:div>
  <cb:div type="other"><cb:mulu>甲一 序分</cb:mulu><head>甲一 序分</head></cb:div>
  <cb:div type="orig"><p style="margin-left:0em">觀自在菩薩...</p></cb:div>
  <cb:div type="commentary"><p style="margin-left:1em">本段序分之文...</p></cb:div>
</cb:div>
```

处理要点：
1. `type="orig"` 和 `type="commentary"` div 没有 `<cb:mulu>` 也没有 `<head>`，`get_heading_text()` 返回空。
2. `walk_div_tree()` 遇到空标题时不 return，而是照常 `extract_paragraphs()` + 递归。
3. `type="orig"` 段落的 Markdown 输出格式为 `> **正文**`（块引用 + 粗体），对应 CBETA `margin-left:0em` 样式的经论原文。
4. `type="commentary"` 段落保持普通格式，对应 CBETA `margin-left:1em` 缩进样式的讲义注解。


### E. byline 内 `<lb/>` 导致的 tail 文本丢失及 `itertext()` 修复

`child.text` 只返回元素起始标签到第一个子元素之间的文本，不包含子元素的 `tail` 文本。当 `<byline>` 内含 `<lb/>` 换行标记时（如 `<byline>（明性<lb/>、湧泉合記）</byline>`），`child.text` 仅拿到 `（明性`，`<lb/>` 的 tail `、湧泉合記）` 被丢弃。

**修复：** 改用 `"".join(child.itertext())` 遍历所有子节点的 text 和 tail。

若 `<byline>` 内嵌套 `<note place="inline">`（如 `<byline>（明性<lb/>、湧泉合記）<note>見海刊...</note></byline>`），`itertext()` 也会带入 note 文本。此时需先提取 note 文本，再从 itertext 结果中 `replace(nt, '')` 剥离，然后分别输出为 `{own_text}（{nt}）`。

```python
# extract_paragraphs() 中 byline/note 处理的核心逻辑：
own_text = ''.join(child.itertext())
own_text = ''.join(own_text.split())  # compress whitespace across <lb/>
inline_note = child.find(f'{{{TEI_NS}}}note') or child.find('note')
if inline_note is not None and inline_note.get('place') == 'inline':
    nt = ''.join(inline_note.itertext()).strip()
    if nt:
        own_text = own_text.replace(nt, '').rstrip()
        own_text = ''.join(own_text.split())
    if own_text and nt:
        out.append(f'{own_text}（{nt}）')
    elif nt:
        out.append(f'（{nt}）')
elif own_text:
    out.append(own_text)
```


## Reference Files

- `references/xml_structure.md` — TEI P5 XML structure, key elements, tag meanings
- `references/level_guide.md` — Detailed level hierarchy with real CBETA examples
- `references/taixu_catalog.md` — Full 太虚全书 20编 catalog with IDs

## Scripts

- `scripts/extract_book_catalog.py` — 提取编级篇名目录 (level 1-2)，含字节偏移扫描与增强 JSON 输出
- `scripts/extract_mulu.py` — 提取单篇文章的完整 `<cb:mulu>` 层级结构
- `scripts/extract_article_fulltext.py` — 提取单篇文章完整全文 Markdown（纯文本，无 Obsidian 特有语法），含目录树、正文、字数统计、篇末注释及篇末附注
- `scripts/_utils.py` — 共享工具函数：`chinese_to_int`、`normalize_byline`、`split_month_season`、`build_suffix`
- `scripts/add_frontmatter_to_existing.py` — 为已提取的旧文章补加 YAML frontmatter，并重命名文件前缀为编内全局序号
**⚠️ CX 限制：Python 环境可用但受限。** 在 Codex 沙箱中以下能力受影响：
- `pip install` 可能因网络限制失败，优先使用本地已安装的库（xml.etree.ElementTree、json、re 均为标准库无需安装）
- 大批量文件 I/O 应在项目工作区 `_data/cbeta/TX/` 和 `_research/` 内完成
- XML 文件在 UTF-8 编码下操作，字节偏移按原始字节流计算（`open(xml_path, 'rb')`）
