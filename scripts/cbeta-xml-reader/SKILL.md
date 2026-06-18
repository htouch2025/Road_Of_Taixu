---
name: cbeta-xml-reader
description: "Read CBETA TEI P5 XML files for the 太虚大师全书 (Collected Works of Master Taixu). Use when Codex needs to: (1) read or navigate CBETA XML source texts from local _data/cbeta/TX/ files, (2) extract article catalogs and document hierarchy (编/篇/部/章/节/小节) from CBETA structured data, (3) interpret cb:mulu level attributes and disambiguate semantic levels like 章 vs 节 vs 部, (4) cross-reference CBETA content against the paper edition table of contents, (5) process legacy DOC/HTML editions and compare them with the authoritative CBETA TEI version."
metadata:
  version: "0.4.0"
  last_updated: "2026-06-18"
  status: active
  task_type: open-ended
---

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
with open('_research/01_佛法總學/_篇名目錄.json') as f:
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

`_篇名目錄.json` 是编级目录的核心数据结构，所有后续文章提取都以此为入口。

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
| `編號` | int | 编内流水号（1-based） |
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
查 _篇名目錄.json，获取 file + byte_start + byte_end
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
| 第二至二十编 | — | ⏳ 待提取 | — |

**原则：所有 CBETA 文件读取均在本地 `_data/cbeta/TX/` 目录完成。**
全部 40 个 TX XML 文件已就位于本地，直接用 Python + ElementTree 解析，跳过网络开销。

**重要：TX 文件的 `<cb:mulu>` 在 `<text>` body 中，不在 TEI header 中。** 在 CBETA TEI P5 的 TX（太虚全书）文件中，目录标记以嵌套 `<cb:div><cb:mulu>` 结构承载于 body 内。

### 1. 提取整编篇名目录（编级 catalog）

使用 `scripts/extract_bian_catalog.py`，仅提取 level 1（子目类别）和 level 2（篇名）。
脚本自动为每篇文章扫描原始文件字节偏移量，构建增强 JSON（含链表 + byte_start/byte_end）。

```
python scripts/cbeta-xml-reader/scripts/extract_bian_catalog.py \
  _data/cbeta/TX/TX01/TX01n0001.xml _data/cbeta/TX/TX02/TX02n0001.xml \
  --bian "第一编 佛法總學" --out-dir _research/01_佛法總學
```

输出：`_篇名目錄.md` + `_篇名目錄.json`

**提取其他编时**，仅需修改 `--bian` 参数和传入对应 XML 文件列表即可。

### 2. 提取单篇文章完整目录树

1. 读取本地 XML 文件，构建 `parent_map`（见实现备忘 A），在 body 中搜集所有 `<cb:mulu>` 元素。
2. 找到 `<cb:mulu level="2">` 标签匹配文章名的条目，获取其所在卷 `div` 容器。
3. 以相邻 `level="2"` 条目位置为边界切分出目标文章的条目范围（见实现备忘 B）——该卷 `div` 内包含同卷所有文章。
4. 过滤掉「綱要」（label == '綱要' 或 '目次'）节点；如有「前言」则保留。
5. Apply the shift rule to assign semantic labels (部/章/节/小节)。
6. 递归构建树形结构（从 level 2 向下）。
7. Output two files: `_research/{编}/{篇名}_目錄樹.md` (human) and `_research/{编}/{篇名}_目錄.json` (machine) — see §4 below

### 3. 跨来源校对

- CBETA is authoritative (以 CBETA 为准)
- HTML/网页版目录 is a secondary reference with known errors (混淆层级)
- 纸质书总目录 (user holds) is the final arbiter
- When in doubt: ask the user to verify against the paper edition


### 4. 双文件输出模式

每提取一篇文章的目录树，同时生成两份文件，放在 `_research/{编}/` 目录下：

1. **`{篇名}_目錄樹.md`** — 给人看的清洁目录树：
   - 篇名顶格，若有题注则紧接一行（如 `（1932 年 12 月，在閩南佛學院講）`）
   - 篇名与目录树之间、目录树与備註之间各空一行
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

许多太虚文章标题 `<head>` 之下、正文之前有注释信息，常见形式：

| 标记 | 含义 | 示例 |
|------|------|------|
| `<byline cb:type="other">——…——</byline>` | 讲说时间地点 | `——二十一年十二月在閩南佛學院講——` |
| `<byline>（…記）</byline>` | 记录者 | `（碧松記）` |
| `<note place="inline">見海刊…</note>` | 刊载来源 | `見海刊十八卷九期` |

**提取方法：**
1. 找到文章 `<head>` 元素后的 `<byline>` 元素，提取其文本
2. 找到同区域的 `<note>` 元素，提取刊载信息

**格式规范化（MD / JSON 输出时）：**

| 原始格式 | 规范化格式 |
|----------|-----------|
| `——二十一年十二月在閩南佛學院講——` | `（1932 年 12 月，在閩南佛學院講）` |
| `（碧松記）` | `（碧松記）`（保留原樣） |
| `見海刊十八卷九期` | `見《海潮音》第18卷第9期` |

- **本项目所有中文产出统一采用繁体**，与 CBETA 原文一致，不做繁简转换
- 民国纪年 → 公元（＋1911）
- 讲说时间地点：`——…——` → `（…）`，日期与地点间加中文逗号
- 刊载来源：`見海刊X卷Y期` → `見《海潮音》第X卷第Y期`
- 记录者 + 刊载信息用空格连接：`（碧松記）見《海潮音》第18卷第11期`

**MD 输出：** 题注放在篇名之下、目录树之前，单独一行。
**JSON 输出：** 放在 `byline` 字段中，无则 `null`。

## Known Pitfalls

1. **章名被误列为独立文章** — 网页版常见错误。如《中国佛学》下的「佛學大綱」「悟心成佛禪」等是章名，非独立文章。
2. **绪言歧义** — 「緒言」可以是 level‑3 部名（《佛學概論》），也可以是 level‑4 节名（《中國佛學》第三章第一節）。
3. **结论层级不等** — 在《佛學概論》中「結論」为 level‑3 部，其下直接是 level‑4 节（无章层）。
4. **level 号不作语义标签** — 不要假设 level="4" 一定是「章」或一定是「节」。
5. **纲要（目次/大纲）须去掉** — 有些文章开头有「綱要」或「目次」，它只是文章結構的預覽列表，不是獨立章節，在目錄樹中應去掉。
6. **前言保留** — 綱要之後如有「前言」，前言是文章的有用開場，應保留。在目錄樹中可將前言列於綱要原本所在的位置，或在備註中說明。
7. **简体搜索须转换为繁体** — 搜索时注意做简繁转换（CBETA 为繁体，用户输入可能为简体）。
8. **TX 文件的 `<cb:mulu>` 在 body 中，不在 TEI header 中** — 在 CBETA TEI P5 的 TX（太虚全书）文件中，目录标记不在 `teiHeader` 内，而是以嵌套 `<cb:div>` 结构承载于 `<text>` body 中。提取目录时应在 body 中 walk `<cb:div>` 树，而非搜索 header 中的 `<cb:mulu>`。
9. **MD 缩进格式：使用 `- ` 嵌套列表而非纯空格** — 纯空格缩进在 Obsidian 等 Markdown 渲染器的阅读模式下不可见。应采用 `- ` 嵌套列表格式：
   ```
   - 文章名
       - 章
           - 节
   ```
10. **ElementTree 无 parent 指针** — Python 标准库 `xml.etree.ElementTree` 不支持 `lxml` 的 `iterancestors()`。需手动构建 `parent_map = {child: parent for parent in root.iter() for child in parent}`。见实现备忘 A。
11. **卷 div ≠ 文章 div** — 从 `<cb:mulu level="2">` 向上爬两级 div 得到的是整卷的容器 div（如 TX01n0001 全文），非单篇文章专属容器。不得对该 div 直接提取，而应以相邻 level=2 条目为边界切分。见实现备忘 B。

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


## Reference Files

- `references/xml_structure.md` — TEI P5 XML structure, key elements, tag meanings
- `references/level_guide.md` — Detailed level hierarchy with real CBETA examples
- `references/taixu_catalog.md` — Full 太虚全书 20编 catalog with IDs

## Scripts

- `scripts/cbeta-xml-reader/scripts/extract_bian_catalog.py` — 提取编级篇名目录 (level 1-2)，含字节偏移扫描与增强 JSON 输出
- `scripts/cbeta-xml-reader/scripts/extract_mulu.py` — 提取单篇文章的完整 `<cb:mulu>` 层级结构
**⚠️ CX 限制：Python 环境可用但受限。** 在 Codex 沙箱中以下能力受影响：
- `pip install` 可能因网络限制失败，优先使用本地已安装的库（xml.etree.ElementTree、json、re 均为标准库无需安装）
- 大批量文件 I/O 应在项目工作区 `_data/cbeta/TX/` 和 `_research/` 内完成
- XML 文件在 UTF-8 编码下操作，字节偏移按原始字节流计算（`open(xml_path, 'rb')`）
