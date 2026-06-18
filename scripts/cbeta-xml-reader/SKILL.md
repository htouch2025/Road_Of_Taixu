---
name: cbeta-xml-reader
description: "Read CBETA TEI P5 XML files for the 太虚大师全书 (Collected Works of Master Taixu). Use when Codex needs to: (1) read or navigate CBETA XML source texts via the buddha MCP (fetch/pipeline/search), (2) extract article catalogs and document hierarchy (编/篇/部/章/节/小节) from CBETA structured data, (3) interpret cb:mulu level attributes and disambiguate semantic levels like 章 vs 节 vs 部, (4) cross-reference CBETA content against the paper edition table of contents, (5) process legacy DOC/HTML editions and compare them with the authoritative CBETA TEI version."
metadata:
  version: "0.1.0"
  last_updated: "2026-06-18"
  status: active
  task_type: open-ended
---

# CBETA XML Reader — 太虚大师全书

Read and navigate CBETA TEI P5 XML files for the 太虚大师全书 via the buddha MCP tools. This skill consolidates knowledge gained from analyzing the CBETA catalog, loading XML source files, and interpreting the TEI markup for directory structure extraction.

## Quick Start

To fetch a 太虚全书 text by its CBETA ID:

```
mcp__buddha__fetch({source: "cbeta", id: "TX01n0001", maxChars: 5000})
```

- `source` must always be `"cbeta"` for 太虚全书 — the TX ID format is not auto-detected.
- `maxChars` controls output size; omit it for the full file.
- Use `format: "plain"` for readable output instead of TEI markup.

For full-text search across the corpus:

```
mcp__buddha__search({source: "cbeta", query: "佛學概論"})
```

Or use the pipeline for search + auto-fetch:

```
mcp__buddha__pipeline({source: "cbeta", query: "緣起", autoFetch: false})
```

See `references/buddha_mcp_tools.md` for complete tool reference.

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

### 1. 提取篇名目录树（用于生成编目文件）

1. Fetch the file via `mcp__buddha__fetch({source: "cbeta", id: "TX...", maxChars: ...})`
2. Locate `<cb:mulu>` elements in the TEI header
3. Parse levels 1 (子目类别) and 2 (篇名) only — do not include level 3+ in a 篇名目录
4. Run `scripts/extract_mulu.py` to automate extraction

### 2. 提取单篇文章完整目录树

1. Fetch the file containing the target article
2. Locate `<cb:mulu>` elements with `level="2"` matching the article name
3. Parse all subsequent `<cb:mulu>` elements until next `level="2"` sibling
4. Apply the shift rule to assign semantic labels (部/章/节/小节)
5. Build a tree from level 2 down to the deepest level

### 3. 跨来源校对

- CBETA is authoritative (以 CBETA 为准)
- HTML/网页版目录 is a secondary reference with known errors (混淆层级)
- 纸质书总目录 (user holds) is the final arbiter
- When in doubt: ask the user to verify against the paper edition

## Known Pitfalls

1. **章名被误列为独立文章** — 网页版常见错误。如《中国佛学》下的「佛學大綱」「悟心成佛禪」等是章名，非独立文章。
2. **绪言歧义** — 「緒言」可以是 level‑3 部名（《佛學概論》），也可以是 level‑4 节名（《中國佛學》第三章第一節）。
3. **结论层级不等** — 在《佛學概論》中「結論」为 level‑3 部，其下直接是 level‑4 节（无章层）。
4. **level 号不作语义标签** — 不要假设 level="4" 一定是「章」或一定是「节」。
5. **TX ID 不自动识别** — `mcp__buddha__fetch` 对 TX IDs 不自动识别 source，必须显式传递 `source: "cbeta"`。

## Reference Files

- `references/xml_structure.md` — TEI P5 XML structure, key elements, tag meanings
- `references/level_guide.md` — Detailed level hierarchy with real CBETA examples
- `references/taixu_catalog.md` — Full 太虚全书 20编 catalog with IDs
- `references/buddha_mcp_tools.md` — Complete buddha MCP tool reference

## Scripts

- `scripts/extract_mulu.py` — Extract `<cb:mulu>` directory structure from CBETA XML
