---
name: keyword-extractor
description: "太虚大师全书关键词提取流水线。Use when Codex needs to: (1) extract keywords from a single article (Phase A programmatic matching + Phase B LLM annotation), (2) apply four-dimensional annotations (knowledge domains, functional purposes, spiritual directions, content keywords) to article frontmatter, (3) update or query the standard vocabulary, (4) record and review gap terms for vocabulary expansion. This skill consolidates all keyword extraction work — method, scripts, vocabulary, prompts, logs, candidates, and documentation — into a single self-contained folder."
metadata:
  version: "0.2.0"
  last_updated: "2026-06-24"
  status: active
  task_type: open-ended
---

> **用户要求**：见 [requirements.md](requirements.md)。当用户说「更新 skill」时：先分析本次新经验涉及需求变更还是纯实现改进。若纯实现改进，不改 requirements.md。仅当需求确有新增或变更时才修改 requirements.md。

# 太虚文章关键词提取 — 完整技能文档

## 一句话

从太虚大师全书的 MD 文章中自动提取四维标注（知识域 / 功能取向 / 精神指向 / 内容关键词），写入 YAML frontmatter，并通过标准术语表确保跨文章术语一致性。

## 快速上手

```bash
# 从 skill 根目录运行（scripts/keyword-extractor/）

# Phase A：生成候选 JSON
python3 scripts/extract_keywords.py \
  --article ../../_research/01_佛法總學/01_概論/03_佛法導言.md

# Phase A+B 一体：构建完整 prompt（一次性填入全文+候选+领域体系）
python3 scripts/extract_keywords.py --build-prompt \
  ../../_research/01_佛法總學/01_概論/03_佛法導言.md > /tmp/prompt.md

# Phase B：LLM 精判 + 写入 frontmatter（四维标注）
python3 scripts/extract_keywords.py \
  --apply ../../_research/01_佛法總學/01_概論/03_佛法導言.md \
  --keywords '["菩提心","大慈悲","涅槃","四諦","十二因緣"]' \
  --knowledge-domains '["基礎教義","修行次第","佛法體系"]' \
  --functional-purposes '["入门导引","纲要约论","修行次第"]' \
  --spiritual-directions '["解脱道","菩薩道","圆融会通"]'
```

> **重要**：Phase B 的判断和分析由 Codex（LLM）完成，不通过脚本。Codex 读取文章全文 + 候选 JSON + prompt 模板，生成四维标签后，调用 `--apply` 写入。

---

## 一、全程叙事：我们怎么走到今天的

### 1.1 需求定义（2026-06-22）

见 [requirements.md](requirements.md)。核心需求摘要：

- 为全书每篇文章自动生成 `keywords` 字段，写入 YAML frontmatter
- 关键词分两类：**文中词**（文章实际讨论的术语）+ **义理维度词**（概括性判断如 `判教`、`通論`）
- 扁平列表，不嵌套，不做章节级
- 双轨标注：`標準詞（原文詞）` — 标准词来自标准术语表
- 数量对数式缩放：5K 字 5-8 个，30K+ 字 12-18 个
- 先建标准术语表（阶段一），再写提取脚本（阶段二）

### 1.2 标准术语表的建造（2026-06-22 至 2026-06-24）

这是整个工程的地基。设计原则：术语表不从外部灌输，而是从全书实际内容中归纳生长。

详见 [references/keyword_vocabulary_task.md](references/keyword_vocabulary_task.md)。

#### 四个建造阶段

| 阶段 | 输出 | 大小 | 方法 |
|:--:|------|:--:|------|
| **种子 + 全量匹配** | `keyword_vocabulary.json` (v1) | 146KB | DILA 佛学词典（丁福保、南山律學、翻譯名義大集、Soothill-Hodous）提取头术语做种子 → 在全书 1,358 篇文章中做字符串匹配 → CBETA API 查全藏频次做通用词过滤 |
| **LLM 策展** | `keyword_vocabulary_v2_draft.json` | 146KB | 按编分批送入 LLM 审阅 → 归并异名确立标准形式 → 分配 domain/subdomain 分类 |
| **义理维度词补充** | `keyword_vocabulary_v3_draft.json` | 194KB | 从 54 篇太虚研究论文中提取义理维度术语（判教、通論、入門、人間佛教等）→ 并入词表 |
| **手动缺口填补 → v4** | `keyword_vocabulary_v4.json` | 284KB | 首轮验证（佛學概論、佛理要略）发现缺失 → 补入三法印、一實相印、佛學、結集、因緣生、諸法無我、向上增進心、出離流轉心、普度成佛心等 → 添加 variant 映射和标题命中加权 |

#### v4 词表结构

每条术语的结构：
```json
{
  "standard": "唯識",
  "variants": ["法相唯識", "瑜伽行派"],
  "domain": "教理",
  "subdomain": "大乘有宗",
  "source": "batch_01,v3_draft",
  "note": ""
}
```

当前词表：1,371 条术语，涵盖 8 个 domain（教理/行持/历史/制度/社会文化/义理维度/方法論/社会），约 80 个子域。

### 1.3 提取方法的演进

#### 方法 0：直接 LLM 提取（first_pass，已废弃）

简单粗暴——每篇文章全文发给 LLM，LLM 直接返回关键词列表。

**问题**：不同文章之间术语不一致（同一概念不同文章用了不同的词）；LLM 对术语的颗粒度判断漂移；无法区分核心讨论和顺带提及。

**遗留物**：`_research/_first_pass_input.json`（2.2MB）、`_research/_batch_*.json`

#### 方法 1：Phase A/B 流水线（当前基础框架）

```
Phase A (程序化)            Phase B (LLM 精判)
┌─────────────────┐        ┌─────────────────────┐
│ 标准术语表匹配    │  →    │ LLM 读全文 + 候选集    │
│ → 候选 JSON      │        │ → 筛选/补充/双轨标注   │
│ (零成本，~400条)  │        │ → 写入 frontmatter    │
└─────────────────┘        └─────────────────────┘
```

Phase A 由 `extract_keywords.py` 完成：
- 加载标准术语表 → 建立 variant→entry 映射
- 按 CJK 字数排序逐条匹配文章正文
- 去重 + 标注 domain/subdomain + 统计频次 + 标题命中加权
- 输出候选 JSON（含 domain 分布摘要和高频术语列表）

Phase B 由 Codex（LLM）完成：
- 读取文章全文 + 候选 JSON 摘要
- 按候选排序逐条审阅：核心讨论 → 提名；顺带提及 → 跳过；字面误中 → 跳过
- 补充自由关键词（≤5 个/篇）
- 双轨标注：标准词与原文一致 → 直接写；不一致 → `標準詞（原文詞）`

#### 方法 2（v2，当前）：四维标注

在 Phase A/B 基础上，将 Phase B 的输出从单一关键词列表扩展为四个维度。详见 [references/_keyword_method.md](references/_keyword_method.md)。

| 维度 | 字段 | 数量 | 说明 |
|------|------|:--:|------|
| 知识域 | `knowledge_domains` | 1-3 | 文章所属佛学领域（如 基礎教義、唯識學、僧制） |
| 功能取向 | `functional_purposes` | 1-3 | 写作意图（如 入门导引、体系建构、批判辨析） |
| 精神指向 | `spiritual_directions` | 1-3 | 终极关怀（如 解脱道、菩薩道、人间佛教） |
| 内容概念 | `keywords` | 5-10 | 文章重点展开的具体术语 |

**演进说明**：原始需求（[requirements.md](requirements.md) §二）规定文中词与义理维度词合并在单一 `keywords` 字段中。v2 将义理维度词拆分为 `knowledge_domains` / `functional_purposes` / `spiritual_directions` 三个独立维度，`keywords` 回归为纯粹的内容概念。这不是需求偏离，而是对「义理维度词」概念的深化——原始需求中「义理维度词」的定义（判教、通論、入門等）正好对应了 v2 的三个判断性维度。拆分后的好处：①标注更结构化，避免扁平列表里术语和判断混杂；②每个维度的值域可以独立标准化（参见 §1.4 值域标准化成果）；③未来可以按维度独立检索和统计。


Phase B prompt 模板：[prompts/_keyword_prompt_v2.md](prompts/_keyword_prompt_v2.md)

### 1.4 交叉验证（2026-06-24）

详见 [references/_keyword_v2_validation_manual.md](references/_keyword_v2_validation_manual.md) 和 [references/_keyword_v2_validation_report.md](references/_keyword_v2_validation_report.md)。

**验证范围**：7 篇文章 × 7 编 × 5 文体 × 5 知识域（从 1.2K 超短讲演到 54K 超长制度论）。

**结论**：v2 方法在通论、经解、学论、律释文体上表现优良；座谈体和超短文略有挑战但可接受；制度论超长文通过 TOC + 候选摘要方式可行。

**值域标准化成果**：
- 功能取向：9 个标准标签，无需合并
- 精神指向：7 个标准标签（`菩萨道` → `菩薩道` 简繁已统一）
- 已回写至 [prompts/_keyword_prompt_v2.md](prompts/_keyword_prompt_v2.md)

**缺口日志**：15 个术语表外概念已记录于 [logs/_keyword_gap_log.jsonl](logs/_keyword_gap_log.jsonl)

---

## 二、当前方法（v2）详细流程

### Phase A：程序化粗筛

```bash
python3 scripts/extract_keywords.py --article <MD_PATH>
```

产出：`candidates/<article_hash>_candidates.json`

**便捷模式**：`--build-prompt` 一次性完成 Phase A + 填入 prompt 模板，输出完整可用的 Phase B prompt：

```bash
python3 scripts/extract_keywords.py --build-prompt <MD_PATH> > /tmp/prompt.md
```

其中自动填入：①文章全文 ②候选术语上下文（表格格式，top 30）③domain/subdomain 分类体系 ④推荐关键词数量。Codex 可直接读取该 prompt 做 Phase B 标注。

候选 JSON 结构：
```json
{
  "summary": {
    "total_candidates": 281,
    "unique_standards": 281,
    "high_frequency_terms": ["大乘","小乘","涅槃",...],
    "heading_weighted": true
  },
  "article": { "path": "...", "title": "...", "cjk_chars": 7033, "recommended_count": "8-12" },
  "candidates": [
    {
      "matched": "大乘", "standard": "大乘",
      "occurrences": 39,
      "domain": "教理", "subdomain": "大乘通義",
      "in_heading": true, "_heading_hits": 2,
      "_positions": [...]
    }
  ]
}
```

关键机制：
- **标题命中加权**：出现在章节标题中的术语 +3 分排序优先，帮助 Codex 快速定位核心概念
- **CJK 字数精确计算**：用于自动推荐关键词数量范围

### Phase B：LLM 四维标注

**推荐方式**：先用 `--build-prompt` 生成完整 prompt（自动填入全文、候选术语表格、领域分类树、推荐关键词数量），Codex 直接基于 prompt 做四维标注：

```bash
# 第一步：生成完整 prompt
python3 scripts/extract_keywords.py --build-prompt <MD_PATH> > /tmp/prompt.md

# 第二步：Codex 读取 /tmp/prompt.md，按模板做四维分析，输出 JSON
# 第三步：写入 frontmatter
python3 scripts/extract_keywords.py --apply <MD_PATH> \
  --keywords '["..."]' --knowledge-domains '["..."]' \
  --functional-purposes '["..."]' --spiritual-directions '["..."]'
```

**手动方式**（仅调试或特殊场景）：

1. 读取文章全文（跳过 YAML frontmatter 和目录）
2. 读取 Phase A 候选 JSON 的 summary 和排序靠前的候选
3. 按 [prompts/_keyword_prompt_v2.md](prompts/_keyword_prompt_v2.md) 模板做四维分析（需自行填入 `{article_body}`、`{candidate_context}`、`{domain_taxonomy}`）
4. 输出 JSON，调用 `--apply` 写入 frontmatter

### --apply 写入

```bash
python3 scripts/extract_keywords.py \
  --apply <MD_PATH> \
  --keywords '["KW1","KW2",...]' \
  --knowledge-domains '["D1","D2"]' \
  --functional-purposes '["F1","F2"]' \
  --spiritual-directions '["S1","S2"]'
```

写入后的 frontmatter 示例：
```yaml
keywords:
  - 菩提心
  - 涅槃
  - 四諦
knowledge_domains:
  - 基礎教義
  - 修行次第
functional_purposes:
  - 入门导引
  - 纲要约论
spiritual_directions:
  - 解脱道
  - 菩薩道
```

`--apply` 自动将四个维度中不在标准值域内的标签记录到 [logs/_keyword_gap_log.jsonl](logs/_keyword_gap_log.jsonl)（按 `keywords` / `knowledge_domains` / `functional_purposes` / `spiritual_directions` 分字段存储）。

---

## 三、文件清单

```
scripts/keyword-extractor/
├── SKILL.md                                   ← 本文件
├── requirements.md                             ← 用户需求文档
├── scripts/
│   ├── extract_keywords.py                     ← 主流水线脚本（Phase A + --apply）
│   └── _kw_utils.py                            ← 共享工具（路径解析、CJK计算、词表加载等）
├── vocabulary/
│   └── keyword_vocabulary_v4.json              ← 标准术语表（1,371条，当前版本）
├── prompts/
│   └── _keyword_prompt_v2.md                   ← Phase B LLM prompt 模板（含标准化值域）
├── logs/
│   └── _keyword_gap_log.jsonl                  ← 术语表缺口日志（append-only）
├── candidates/                                 ← Phase A 候选 JSON 输出目录
│   └── *_candidates.json
└── references/                                 ← 参考文档
    ├── _keyword_method.md                       ← 当前方法详述
    ├── _keyword_v2_validation_manual.md         ← 交叉验证工作手册
    ├── _keyword_v2_validation_report.md         ← 交叉验证报告
    ├── keyword_vocabulary_task.md              ← 术语表建造任务设计
```

### 不在 skill 文件夹内的遗留文件

这些文件保留在项目各处，不再使用但保留为历史记录：

| 位置 | 文件 | 说明 |
|------|------|------|
| `scripts/` | `build_phaseA_output.py` 等 12 个 | 早期批量处理脚本 |
| `_research/` | `keyword_vocabulary.json` (v1) | 历史版本 |
| `_research/` | `keyword_vocabulary_v2_draft.json` | 历史版本 |
| `_research/` | `keyword_vocabulary_v3_draft.json` | 历史版本 |
| `_research/` | `_batch_*.json`, `_first_pass_*.json` | 中间批量数据 |
| `_research/` | `_phase2_batch/`, `_phase3_batch/` | 批量处理产物 |
| `_research/` | `keyword_vocabulary_v4_readable.md` | v4 可读版本 |
| `_research/` | `keyword_vocabulary_status.md` | 状态跟踪 |
| `_research/` | `keyword_vocabulary.md` | 术语表说明 |
| `_research/` | `keyword_vocabulary_v3_draft_revision.md` | v3 修订记录 |

---

## 四、如何更新

### 更新术语表

1. 累积约 20 篇文章后，检查 [logs/_keyword_gap_log.jsonl](logs/_keyword_gap_log.jsonl)，筛选 `keywords` 维度
2. 筛选出现频次 ≥ 2 的自由关键词
3. 手动判断是否补入 [vocabulary/keyword_vocabulary_v4.json](vocabulary/keyword_vocabulary_v4.json)
4. 补入时同步更新 variant 映射和 domain/subdomain 分类
5. 可考虑升级版本号至 v5

### 更新 prompt

1. 累积约 20 篇文章后，检查 [logs/_keyword_gap_log.jsonl](logs/_keyword_gap_log.jsonl)，筛选 `functional_purposes` 和 `spiritual_directions` 维度
2. 如果出现频次 ≥ 2 的新标签类型，手动评审是否加入 [prompts/_keyword_prompt_v2.md](prompts/_keyword_prompt_v2.md) 的参考列表
3. 同时检查 `knowledge_domains` 维度，若出现不在 8 大域中的新域，考虑扩充术语表 domain 分类
4. 注意区分：是真正的"新类型"还是已有标签的同义变体（后者应收敛到标准标签）

### 调用方式

当其他 skill（如文章提取 skill）需要同时提取关键词时，调用本 skill 的流程：

```
用 keyword-extractor skill 的 v2 方法处理 <文章路径>
```

Codex 将自动执行 Phase A（`--article`）→ 读全文 + 候选 JSON → Phase B 分析 → `--apply` 写入。

### 已知限制

- 诗存（第 20 编）不适用，韵律文体需要单独设计策略
- 座谈体（第 17 编）术语密度低，Phase B 需放宽关键词选择自由度
- 超长文（>50K 字）全文通读成本过高，当前使用 TOC + 候选摘要近似方法
- `修行次第` 在知识域和功能取向两维度下均可能出现（属合理现象，已在 prompt 中说明）
- `functional_purposes` 和 `spiritual_directions` 的标准标签列表集中在 [vocabulary/labels.json](vocabulary/labels.json) 中维护，`--build-prompt` 和 `--apply` 均从此文件读取，无需手动同步。

---

*最后更新：2026-06-24*
