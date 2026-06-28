<!--
太虚文章关键词提取 v2 — 交叉验证工作手册

用途：在新对话中按此手册执行跨编多文体验证，完成后整理标准化值域。
前置条件：extract_keywords.py 已升级到 v2（支持多维标注写入），_keyword_prompt_v2.md 已存在。
-->

# 太虚文章关键词提取 v2 — 交叉验证工作手册

## 背景

v2 方法已用《佛理要略》（编01 概論·通论体，基礎教義+修行次第）完成首轮验证。现需跨编、跨文体、跨知识域扩展验证 5-7 篇文章，然后整理标准化功能取向和精神指向的值域。

**v2 方法总结：** Phase A 词表粗筛（产出候选 JSON 含 domain 分布）→ Phase B LLM 通读全文四维度标注（知识域 / 功能取向 / 精神指向 / 内容概念）→ `--apply` 写入 frontmatter。

## 一、验证样本（7 篇，跨 7 编 × 5 文体 × 5 知识域）

| 序号 | 文章 | 路径 | 字数 | 编·文体 | 预期知识域特征 |
|:--:|------|------|:--:|------|------|
| 1 | 佛法導言 | `_research/01_佛法總學/01_概論/03_佛法導言.md` | 7K | 01·通论 | 基礎教義+修行次第（与佛理要略同编同体，应产出类似结构） |
| 2 | 金剛般若波羅蜜經義脈 | `_research/05_法性空慧學/01_教釋/01_金剛般若波羅蜜經義脈.md` | 5.8K | 05·经解 | 中觀學+經典註釋，理论密度中等 |
| 3 | 法相唯識學概論 | `_research/06_法相唯識學/02_義繹/19_法相唯識學概論.md` | 22K | 06·学论 | 唯識學，理论密度高，长文 |
| 4 | 懸論 | `_research/08_律釋/01_優婆塞戒經講錄/02_懸論.md` | 5.3K | 08·律释讲录 | 戒律行持+經典註釋，制度实践领域 |
| 5 | 整理僧伽制度論 | `_research/09_制議/01_僧制/01_整理僧伽制度論.md` | 54K | 09·制度论 | 僧制+佛教組織，非教理的制度领域，超长文 |
| 6 | 佛法能否改善現實社會 | `_research/17_酬對/04_座談/278_佛法能否改善現實社會.md` | 6.5K | 17·座谈 | 对话体，佛教與社會，短段落快节奏 |
| 7 | 佛教與吾人之關係 | `_research/18_講演/01_我之佛教觀/01_佛教與吾人之關係.md` | 1.2K | 18·讲演 | 讲演体，短篇，口语化 |

**特别说明：**
- 第 5 篇（54K 字）是全集中最长的文章之一，Phase B 可能需要分段处理或选取代表性章节
- 第 6 篇是座谈会记录，短段落快节奏对话，与书面论文体完全不同
- 第 7 篇仅 1.2K 字，测试方法在超短文上的表现

## 二、执行步骤

### 对每篇文章（在新对话中逐篇或批量执行）：

```
用 v2 方法提取「文章路径」的关键词
```

例如：
```
用 v2 方法提取 _research/01_佛法總學/01_概論/03_佛法導言.md 的关键词
```

Codex 会自动完成：
1. `python scripts/extract_keywords.py --article <path>` — Phase A 粗筛
2. 读取候选 JSON（含 domain 分布摘要）
3. 按 `_keyword_prompt_v2.md` 模板做四维度分析
4. `python scripts/extract_keywords.py --apply <path> --keywords '[...]' --knowledge-domains '[...]' --functional-purposes '[...]' --spiritual-directions '[...]'` — 写入 frontmatter
5. 展示新旧对比

### 批量方式（如果对话上下文充足）：

```
用 v2 方法依次处理以下文章：
1. _research/01_佛法總學/01_概論/03_佛法導言.md
2. _research/05_法性空慧學/01_教釋/01_金剛般若波羅蜜經義脈.md
3. _research/06_法相唯識學/02_義繹/19_法相唯識學概論.md
4. _research/08_律釋/01_優婆塞戒經講錄/02_懸論.md
5. _research/09_制議/01_僧制/01_整理僧伽制度論.md
6. _research/17_酬對/04_座談/278_佛法能否改善現實社會.md
7. _research/18_講演/01_我之佛教觀/01_佛教與吾人之關係.md

全部处理完后，做值域标准化整理。
```

## 三、验证指标

每篇文章完成后，记录以下内容：

| 指标 | 说明 |
|------|------|
| 候选总数 / 去重后 | Phase A 命中的术语数 |
| 前 3 domain | 文章知识域分布 |
| 前 5 subdomain | 文章子域分布 |
| 知识域标签 | Phase B 产出的知识域（是否与词表 domain 体系一致） |
| 功能取向标签 | Phase B 产出的功能取向（类型是否在预期范围内） |
| 精神指向标签 | Phase B 产出的精神指向（类型是否在预期范围内） |
| 内容概念数 | 是否在 5-10 范围内 |
| 缺口术语 | `_keyword_gap_log.jsonl` 中记录的新术语 |
| 备注 | 方法在该文体/知识域上的表现评价 |

## 四、值域标准化整理

全部 7 篇文章处理完后，汇总所有产出的功能取向和精神指向标签，做一次标准化。

### 4.1 收集标签

用以下命令导出所有文章的维度标签：

```bash
cd /Users/xin/Documents/Road_Of_Taixu
python3 << 'PYEOF'
import yaml, glob, json
from collections import Counter

kd, fp, sd = Counter(), Counter(), Counter()
for md in glob.glob("_research/**/*.md", recursive=True):
    if md.startswith("_research/_"): continue
    with open(md) as f:
        raw = f.read()
    parts = raw.split("---")
    if len(parts) < 3: continue
    fm = yaml.safe_load(parts[1])
    if not fm: continue
    for tag in fm.get("knowledge_domains", []): kd[tag] += 1
    for tag in fm.get("functional_purposes", []): fp[tag] += 1
    for tag in fm.get("spiritual_directions", []): sd[tag] += 1

print("=== knowledge_domains ===")
for t, c in kd.most_common(): print(f"  {t}: {c}")
print("\n=== functional_purposes ===")
for t, c in fp.most_common(): print(f"  {t}: {c}")
print("\n=== spiritual_directions ===")
for t, c in sd.most_common(): print(f"  {t}: {c}")
PYEOF
```

### 4.2 标准化合并

检查以下问题并手动合并/修正：

1. **同义异名**：例如「綱要概述」和「提綱挈領」是否指向同一含义 → 统一为一个标准标签
2. **粒度不一**：例如「實修指引」vs「修行次第」是否该合并 → 确定合理的标签粒度
3. **频次过低**：出现仅 1 次的标签 → 判断是否保留还是合并到上位标签
4. **语义漂移**：同一标签在不同文章中是否含义一致 → 如果不一致则需要拆分

### 4.3 回写 Prompt

将标准化后的值域更新到 `_research/_keyword_prompt_v2.md` 的维度说明部分，替换原有的「常见类型参考」列表，使后续的 Phase B 产出更一致。

### 4.4 最终产出

1. 标准化的功能取向值域列表（建议控制在 15-20 个以内）
2. 标准化的精神指向值域列表（建议控制在 10-15 个以内）
3. 更新后的 `_keyword_prompt_v2.md`
4. 验证报告（对每篇文章的评价 + 整体结论）

## 五、已知限制

- 讲演（第 18 编）和酬對（第 17 编）的 MD 文件多为短篇子文章（300-1500 字），v2 方法在此文体上的关键词数量控制可能需要调整（较短文章应允许 3-5 个内容概念）
- 诗存（第 20 编）暂不包含在当前验证范围（韵律文体需要不同的分析策略）
- 《整理僧伽制度論》（54K 字）篇幅极大，Phase B 可能需要首先读取文章结构和目录，然后分段分析
