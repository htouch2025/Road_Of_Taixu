---
name: keyword-extractor
description: "太虚大师全书要义提取流水线。Use when Codex needs to: (1) extract concepts from a single article (Phase A programmatic matching + Phase B LLM annotation), (2) apply four-dimensional annotations (domains, functions, bearings, concepts) to article frontmatter, (3) update or query the standard vocabulary, (4) record and review gap terms for vocabulary expansion. This skill consolidates all concept extraction work — method, scripts, vocabulary, prompts, logs, candidates, and documentation — into a single self-contained folder."
metadata:
  version: "0.2.0"
  last_updated: "2026-06-27"
  status: active
  task_type: open-ended
---

> **用户要求**：见 [requirements.md](requirements.md)。当用户说「更新 skill」时：先分析本次新经验涉及需求变更还是纯实现改进。若纯实现改进，不改 requirements.md。仅当需求确有新增或变更时才修改 requirements.md。

# 太虚文章关键词提取 — 完整技能文档

## 一句话

从太虚大师全书的 MD 文章中自动提取四维标注（论域 / 论用 / 旨归 / 要义），写入 YAML frontmatter，并通过标准术语表确保跨文章术语一致性。

## 快速上手

```bash
# 从 skill 根目录运行（agent_skills/keyword-extractor/）

# Phase A：生成候选 JSON
python3 scripts/extract_keywords.py \
  --article ../../_research/01_佛法總學/01_概論/03_佛法導言.md

# Phase A+B 一体：构建完整 prompt（一次性填入全文+候选+领域体系）
python3 scripts/extract_keywords.py --build-prompt \
  ../../_research/01_佛法總學/01_概論/03_佛法導言.md > /tmp/prompt.md

# Phase B：LLM 精判 + 写入 frontmatter（四维标注）
python3 scripts/extract_keywords.py \
  --apply ../../_research/01_佛法總學/01_概論/03_佛法導言.md \
  --concepts '["菩提心","大慈悲","涅槃","四諦","十二因緣"]' \
  --domains '["基礎教義","修行次第","佛法體系"]' \
  --functions '["入门导引","纲要约论","修行次第"]' \
  --bearings '["解脱道","菩薩道","圆融会通"]'
```

> **重要**：Phase B 的判断和分析由 Codex（LLM）完成，不通过脚本。Codex 读取文章全文 + 候选 JSON + prompt 模板，生成四维标签后，调用 `--apply` 写入。

---

## 一、当前方法（v2）详细流程

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
  --concepts '["..."]' --domains '["..."]' \
  --functions '["..."]' --bearings '["..."]'
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
  --concepts '["KW1","KW2",...]' \
  --domains '["D1","D2"]' \
  --functions '["F1","F2"]' \
  --bearings '["S1","S2"]'
```

写入后的 frontmatter 示例：
```yaml
concepts:
  - 菩提心
  - 涅槃
  - 四諦
domains:
  - 基礎教義
  - 修行次第
functions:
  - 入门导引
  - 纲要约论
bearings:
  - 解脱道
  - 菩薩道
```

`--apply` 自动将四个维度中不在标准值域内的标签记录到 [logs/_keyword_gap_log.jsonl](logs/_keyword_gap_log.jsonl)（按 `concepts` / `domains` / `functions` / `bearings` 分字段存储）。

---

## 二、文件清单

```
scripts/keyword-extractor/
├── SKILL.md                                   ← 本文件
├── requirements.md                             ← 用户需求文档
├── scripts/
│   ├── extract_keywords.py                     ← 主流水线脚本（Phase A + --apply）
│   └── _kw_utils.py                            ← 共享工具（路径解析、CJK计算、词表加载等）
├── vocabulary/
│   └── keyword_vocabulary_v4.json              ← 标准术语表（1,391条，v4.2）
├── prompts/
│   └── _keyword_prompt_v2.md                   ← Phase B LLM prompt 模板（含标准化值域）
├── logs/
│   └── _keyword_gap_log.jsonl                  ← 术语表缺口日志（append-only）
│   └── _kw_counter.json                        ← 已处理文章计数（自动维护）
├── candidates/                                 ← Phase A 候选 JSON 输出目录
│   └── *_candidates.json
└── references/                                 ← 参考文档
    ├── _keyword_method.md                       ← 当前方法详述
    ├── _keyword_v2_validation_manual.md         ← 交叉验证工作手册
    ├── _keyword_v2_validation_report.md         ← 交叉验证报告
    ├── keyword_vocabulary_task.md              ← 术语表建造任务设计
```

## 三、如何更新

### 自动化缺口审查（推荐）

```bash
# 仅审查报告（只读）
python3 scripts/extract_keywords.py --review-gaps

# 审查 + 自动补入（频次≥2 的缺口直接写入词表/labels）
python3 scripts/extract_keywords.py --review-gaps-apply
```

自动化规则：
- 先对比当前词表和 labels.json，剔除所有假阳性
- concepts 频次 ≥2 → 自动补入词表，通篇文章其他已存术语推断 domain/subdomain
- domains / functions / bearings 频次 ≥2 → 自动补入 labels.json
- 频次 =1 的缺口保留在日志中，等待累积
- 处理后缺口日志自动回写（假阳性条目被移除）

每次 `--apply` 成功后，`_kw_counter.json` 自动 +1（按文章路径去重），并在终端输出「已處理文章數: N，距下次評審還差 M 篇」。

当计数达到 5/10/15 …的倍数时，自动触发词表过滤 + 缺口补入（频次≥2 的自动写入，假阳性自动清理）。整个过程无需人工干预。

### 更新术语表

1. 当 `_kw_counter.json` 显示 ≥ 5 篇时，检查 [logs/_keyword_gap_log.jsonl](logs/_keyword_gap_log.jsonl)，筛选 `concepts` 维度
2. 筛选出现频次 ≥ 2 的自由关键词
3. 手动判断是否补入 [vocabulary/keyword_vocabulary_v4.json](vocabulary/keyword_vocabulary_v4.json)
4. 补入时同步更新 variant 映射和 domain/subdomain 分类
5. 可考虑升级版本号至 v5

> **自动化已覆盖**：以上手动步骤已由 `--review-gaps-apply` 自动化。仅在判定有争议或需人工介入时手动操作。

### 更新 prompt

1. 当 `_kw_counter.json` 显示 ≥ 5 篇时，检查 [logs/_keyword_gap_log.jsonl](logs/_keyword_gap_log.jsonl)，筛选 `functions` 和 `bearings` 维度
2. 如果出现频次 ≥ 2 的新标签类型，手动评审是否加入 [prompts/_keyword_prompt_v2.md](prompts/_keyword_prompt_v2.md) 的参考列表
3. 同时检查 `domains` 维度，若出现不在 8 大域中的新域，考虑扩充术语表 domain 分类
4. 注意区分：是真正的"新类型"还是已有标签的同义变体（后者应收敛到标准标签）

> **自动化已覆盖**：functions / bearings 的新标签类型由 `--review-gaps-apply` 自动补入 labels.json。

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
- `修行次第` 在论域和论用两维度下均可能出现（属合理现象，已在 prompt 中说明）
- `functions` 和 `bearings` 的标准标签列表集中在 [vocabulary/labels.json](vocabulary/labels.json) 中维护，`--build-prompt` 和 `--apply` 均从此文件读取，无需手动同步。

## 四、缺口审查自动化设计

### 脚本入口

`extract_keywords.py` 新增两个 flag：

| flag | 作用 |
|------|------|
| `--review-gaps` | 读缺口日志 → 过滤假阳性 → 打印频次报告（只读） |
| `--review-gaps-apply` | 同上 + 自动补入频次≥2 的缺口 + 清理日志 |

### 触发时机

- 自动：`print_review_report()` 在文章计数达到 5 的倍数时调用，已内建词表过滤
- 手动：`python3 scripts/extract_keywords.py --review-gaps-apply`

### 状态追踪

- `logs/_keyword_gap_log.jsonl` — 缺口日志（`--review-gaps-apply` 自动清理假阳性）
- `logs/_kw_counter.json` — 已处理文章计数，达到 5 的倍数时打印评審报告
- `vocabulary/labels.json` — 标准值域（现有 `domains` / `functions` / `bearings` 三个维度）

---

*最后更新：2026-06-27*
