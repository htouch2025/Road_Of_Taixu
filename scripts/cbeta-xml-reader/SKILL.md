---
name: cbeta-xml-reader
description: "Read CBETA TEI P5 XML files for the 太虚大师全书 (Collected Works of Master Taixu). Use when Codex needs to: (1) read or navigate CBETA XML source texts from local _data/cbeta/TX/ files, (2) extract article catalogs and document hierarchy (编/篇/部/章/节/小节) from CBETA structured data, (3) interpret cb:mulu level attributes and disambiguate semantic levels like 章 vs 节 vs 部, (4) cross-reference CBETA content against the paper edition table of contents, (5) process legacy DOC/HTML editions and compare them with the authoritative CBETA TEI version."
metadata:
  version: "0.10.0"
  last_updated: "2026-06-20"
  status: active
  task_type: open-ended
---

> **用户要求**：见 [requirements.md](requirements.md)。此文件仅记录用户需求，非实现方法。当用户说「更新 skill」时：先分析本次新经验是否涉及需求变更（新增需求、需求语义变化）。若是纯实现方法改进（bug 修复、算法调整、代码结构优化——需求未变），则不改 requirements.md。仅当需求确有新增或变更时，才修改 requirements.md。

# CBETA XML Reader — 太虚大师全书

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
| 第三至二十编 | — | ⏳ 待提取 | — |

**原则：所有 CBETA 文件读取均在本地 `_data/cbeta/TX/` 目录完成。**
全部 40 个 TX XML 文件已就位于本地，直接用 Python + ElementTree 解析，跳过网络开销。

**重要：TX 文件的 `<cb:mulu>` 在 `<text>` body 中，不在 TEI header 中。** 在 CBETA TEI P5 的 TX（太虚全书）文件中，目录标记以嵌套 `<cb:div><cb:mulu>` 结构承载于 body 内。

### 1. 提取整编篇名目录（编级 catalog）

**⚠️ 提取後須做兩項人工複核：**（1）檢查是否有帶「（附）」前綴的 level-2 條目需合併入前一篇；（2）確認每子目內文章編號從 1 起編而非跨子目連續。
詳見 Known Pitfalls 第 12、13 條。

使用 `scripts/extract_bian_catalog.py`（路径相对于 skill 目录，即 `~/.codex/skills/cbeta-xml-reader/scripts/`），仅提取 level 1（子目类别）和 level 2（篇名）。
脚本自动为每篇文章扫描原始文件字节偏移量，构建增强 JSON（含链表 + byte_start/byte_end）。

```
python scripts/extract_bian_catalog.py \
  _data/cbeta/TX/TX01/TX01n0001.xml _data/cbeta/TX/TX02/TX02n0001.xml \
  --bian "第一编 佛法總學" --bian-num 1
```

`--out-dir` 可选，默认从 `--bian-num` + `--bian` 自动推导为 `_research/{编号}_{编名}/`。
输出 `_{编号}_{编名}_編目錄.md` + `_{编号}_{编名}_編目錄.json`。
MD 中篇目的「子目」層帶數字編號（如 `1. 教釋` `2. 義繹`）。

**提取其他编时**，改 `--bian`、`--bian-num` 和 XML 文件列表即可，路径自动填入。

### 2. 提取单篇文章完整目录树

1. 读取本地 XML 文件，构建 `parent_map`（见实现备忘 A），在 body 中搜集所有 `<cb:mulu>` 元素。
2. 找到 `<cb:mulu level="2">` 标签匹配文章名的条目，获取其所在卷 `div` 容器。
3. 以相邻 `level="2"` 条目位置为边界切分出目标文章的条目范围（见实现备忘 B）——该卷 `div` 内包含同卷所有文章。
4. 过滤掉纲要类节点（label 为「綱要」「目次」「科分」等纯结构预览条目）；如有「前言」则保留。
5. Apply the shift rule to assign semantic labels (部/章/节/小节)。
6. 递归构建树形结构（从 level 2 向下）。
7. Output two files to auto-derived path: `_research/{编dir}/{子目编号}_{子目名}/{文章编号}_{篇名}_目錄樹.md` + `_目錄.json`（从 `_編目錄.json` 查子目与编号，自动填入现有文件夹框架）。See §4 below.

### 4. 双文件输出模式

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



### 5. 提取题下注释（byline/note）

许多太虚文章标题 `<head>` 之下、正文之前有题注（题下注释），记录讲说时间、地点、记录者等信息。常见 XML 标记：

| 标记 | 含义 | 示例 |
|------|------|------|
| `<byline cb:type="other">——…——</byline>` | 讲说时间地点 | `——二十一年十二月在閩南佛學院講——` |
| `<byline>（…記）</byline>` | 记录者 | `（碧松記）` |
| `<note place="inline">見海刊…</note>` | 刊载来源 | `見海刊十八卷九期` |

**提取方法：**
1. 找到文章 `<head>` 元素后的 `<byline>` 元素，提取其文本
2. 找到同区域的 `<note>` 元素，提取刊载信息

### 5a. 题注格式规范化

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


### 6. 篇末注释提取

部分太虚文章有篇末注释（back-notes），在 XML 中通过 `<back>` 区域的 `<note>` 元素标记，正文中通过 `<anchor xml:id="nkr_note_orig_N"/>` 引用。

**提取脚本** `extract_article_fulltext.py` 自动完成以下工作：

1. **注释发现**：扫描文章范围内的 `nkr_note_orig_*` 锚点 ID，按出现顺序编号
1. **正文标记**：在对应锚点位置插入纯数字 `N`（如 `1`、`2`），标题后注释号与标题正文间空一格（如 `# 佛學概論 1`、`### 學史 2`）
1. **文末注释**：每行格式为 `- **N**：注释正文`（如 `- **1**：本論略本...`）
1. **篇末附注**：自动提取文章末尾的 `<byline>` 记录者信息和 `<note place="inline">` 刊载来源，如 `（碧松記）（原見海潮音月刊十八卷十一期）`

**处理嵌套 `<note>` 在 `<byline>` 内的情形：** 部分 CBETA 文件中，篇末刊载来源 `<note place="inline">` 嵌套在 `<byline>` 元素内部（而非平级）。`extract_article_fulltext.py` 的 `extract_paragraphs()` 函数使用 `re.DOTALL` 匹配跨行文本，确保刊载来源也被正确包裹为 `（見海刊…）` 格式。

**输出格式**：纯文本 Markdown，无任何 Obsidian 特有语法（无 `[[...]]` 链接、无 `^` 块锚点、无 `{#...}` 自定义锚点）。在不同 Markdown 渲染器中表现一致，不依赖特定编辑器的扩展语法。

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
16. **byline 换行符残留** — 部分 `<byline>` 内部嵌有 `<lb/>` 换行标记（如 `（李了<lb/>空、胡法智合記）`）。`itertext()` 拼接时会把 `<lb>` 的 tail 文本前的换行符也带入，导致输出断开成两行。修复：对 byline 文本做 `"".join(text.split())` 压缩全部空白，与 `render_paragraph()` 处理 `<p>` 文本的方式一致，不要只用 `.strip()`。
17. **文末 byline/note 被 extract_article_fulltext 跳過** — `extract_article()` 遍歷 `article_div` 子元素時僅處理 `<cb:div>`（第 457–459 行），而文末的記錄人 `<byline>` 和刊載來源 `<note place="inline">` 是 `article_div` 的直接子元素而非 `<cb:div>`，因而被整段跳過。結果是 `extract_article_fulltext.py` 生成的全文不含記錄人／刊載附注（如「（倪德薰記）（見海刊三卷五期）」）。
    - **根因：** `for child in article_div: if child.tag == f'{CBETA_NS}div':` 僅匹配 `<cb:div>`，漏掉同層的 `<byline>` 和 `<note>`。
    - **修復：** 在處理完所有子 `<cb:div>` 之後，額外對 `article_div` 本身調用 `extract_paragraphs(article_div)`，這樣就能把文末的 byline/note 也撿回來。題注 byline（`——…——` 格式）由 `get_byline_text()` 單獨處理，不會被重複加入。

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

`extract_article_fulltext.py` 的注释系统输出纯文本，无任何 Obsidian 跳转链接：

1. **`extract_article_notes()`**：扫描文章范围的 `<anchor xml:id="nkr_note_orig_N"/>` ID，与 `<back>` 区域的 `<note n="N" target="#nkr_note_orig_N">` 交叉匹配，返回 `[(num_label, note_text), ...]` 和 `anchor_ids` 有序列表
1. **正文标记**：在对应锚点位置插入纯数字 `N`，无链接。标题后注释号与标题正文间有一个空格（如 `# 佛學概論 1`）
1. **文末注释**：每行格式为 `- **N**：注释正文`（如 `- **1**：本論略本...`），无回链
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


## Reference Files

- `references/xml_structure.md` — TEI P5 XML structure, key elements, tag meanings
- `references/level_guide.md` — Detailed level hierarchy with real CBETA examples
- `references/taixu_catalog.md` — Full 太虚全书 20编 catalog with IDs

## Scripts

- `scripts/extract_bian_catalog.py` — 提取编级篇名目录 (level 1-2)，含字节偏移扫描与增强 JSON 输出
- `scripts/extract_mulu.py` — 提取单篇文章的完整 `<cb:mulu>` 层级结构
- `scripts/extract_article_fulltext.py` — 提取单篇文章完整全文 Markdown（纯文本，无 Obsidian 特有语法），含目录树、正文、篇末注释及篇末附注
**⚠️ CX 限制：Python 环境可用但受限。** 在 Codex 沙箱中以下能力受影响：
- `pip install` 可能因网络限制失败，优先使用本地已安装的库（xml.etree.ElementTree、json、re 均为标准库无需安装）
- 大批量文件 I/O 应在项目工作区 `_data/cbeta/TX/` 和 `_research/` 内完成
- XML 文件在 UTF-8 编码下操作，字节偏移按原始字节流计算（`open(xml_path, 'rb')`）
