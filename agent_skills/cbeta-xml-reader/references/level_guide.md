# CBETA Level Hierarchy Guide

Detailed analysis of the `<cb:mulu level="N">` hierarchy with real examples from 太虚大师全书.

## Core Principle

**The level number is relative to the parent node, NOT a fixed semantic label.**

The same semantic level (e.g., 章 / chapter) can appear at different `level` numbers depending on whether higher levels (部) exist in the article's structure.

---

## Example 1: 《佛學概論》— Full hierarchy with 部

Source: `TX01n0001`

```
子目类别 (level 1): 概論
  └── 篇 (level 2): 佛學概論
        ├── 部 (level 3): 緒言                          (无编号)
        ├── 部 (level 3): 學史                          (无编号)
        │     ├── 章 (level 4): 第一章 釋尊略傳
        │     │     ├── 節 (level 5): 第一節 釋尊出於印度之背景
        │     │     ├── 節 (level 5): 第二節 未成正覺前之釋尊
        │     │     └── 節 (level 5): 第三節 成正覺後之釋尊
        │     ├── 章 (level 4): 第二章 印度佛學略史
        │     ├── 章 (level 4): 第三章 中國佛學歷史
        │     └── 章 (level 4): 第四章 各地之佛學略史
        ├── 部 (level 3): 學理                          (无编号)
        │     ├── 章 (level 4): 第一章 因緣所生法——五乘共學
        │     │     ├── 節 (level 5): 第一節 總論
        │     │     ├── 節 (level 5): 第二節 無始流轉
        │     │     │     ├── 小節 (level 6): 一 心之分析
        │     │     │     ├── 小節 (level 6): 二 煩惱業生
        │     │     │     ├── 小節 (level 6): 三 有情本死中生
        │     │     │     └── 小節 (level 6): 四 器界成住壞空
        │     │     ├── 節 (level 5): 第三節 業與界趣
        │     │     ├── 節 (level 5): 第四節 異生與聖
        │     │     ├── 節 (level 5): 第五節 成聖之道
        │     │     └── 節 (level 5): 第六節 再論業與界趣之流轉
        │     ├── 章 (level 4): 第二章 三法印——出世三乘共學
        │     ├── 章 (level 4): 第三章 一實相印——大乘不共學
        │     └── 章 (level 4): 第四章 約略指廣            (无下级)
        └── 部 (level 3): 結論                          (无编号)
              ├── 節 (level 4): 第一節 解釋對於佛學之誤會    (无「章」层)
              ├── 節 (level 4): 第二節 佛學的本質
              ├── 節 (level 4): 第三節 佛學的方法
              ├── 節 (level 4): 第四節 佛學的應用
              └── 節 (level 4): 第五節 怎樣研究佛學
```

**Key observations:**
- 「部」at level 3 has no numbering (緒言、學史、學理、結論)
- Under 「部」, 章 starts at level 4
- Under 章, 節 starts at level 5
- Under 節, 小節 starts at level 6 (numbered 一、二、三…)
- 「結論」部 has NO 章 layer — 節 directly at level 4

---

## Example 2: 《中國佛學》— No 部 layer

Source: `TX02n0001`

```
子目类别 (level 1): 源流
  └── 篇 (level 2): 中國佛學
        ├── 章 (level 3): 第一章 佛學大綱                  (无下级)
        ├── 章 (level 3): 第二章 中國佛學特質在禪
        │     ├── 節 (level 4): 第一節 略敘因緣
        │     ├── 節 (level 4): 第二節 依教修心禪
        │     │     ├── 小節 (level 5): 一 安般禪
        │     │     ├── 小節 (level 5): 二 五門禪
        │     │     ├── 小節 (level 5): 三 念佛禪
        │     │     └── 小節 (level 5): 四 實相禪
        │     └── ... (節 三至六)
        ├── 章 (level 3): 第三章 禪觀行演為台賢教
        │     ├── 節 (level 4): 第一節 緒言                ← 注意：此处「緒言」是节！
        │     ├── 節 (level 4): 第二節 實相禪布為天台教
        │     │     ├── 小節 (level 5): 一 天台學之根據
        │     │     ├── 小節 (level 5): 二 天台學之先河
        │     │     ├── 小節 (level 5): 三 天台學之成立
        │     │     │     ├── 小小節 (level 6): 甲 慧文慧思之創發
        │     │     │     └── 小小節 (level 6): 乙 智者之完成
        │     │     └── ...
        │     └── ...
        ├── 章 (level 3): 第四章 禪台賢流歸淨土行
        └── 章 (level 3): 第五章 中國佛學之重建
```

**Key observations:**
- No 「部」 layer → 章 directly at level 3
- Without 部, 節 shifts up to level 4
- Without 章 under 節, 小節 shifts up to level 5
- 「小小節」(甲、乙、丙) at level 6 with 甲/乙/丙 numbering
- **绪言 pitfall**: 第三章第一節 is named 「緒言」— it's a 節 at level 4, NOT a 部 at level 3 as in 佛學概論

---

## Level Shift Table

| If parent has... | Then current level maps to... |
|------------------|-------------------------------|
| (level 1) 子目类别 | level 2 → 篇 |
| (level 2) 篇 | level 3 → 部 (if unnumbered) or 章 (if 第X章) |
| (level 3) 部 | level 4 → 章 (if 第X章) or 節 (if 第一節) |
| (level 3) 章 | level 4 → 節 |
| (level 4) 章 | level 5 → 節 |
| (level 4) 節 | level 5 → 小節 |
| (level 5) 節 | level 6 → 小節 |
| (level 5) 小節 | level 6 → 小小節 |

## Detection Algorithm

```
For each <cb:mulu> element:
  1. Get level attribute value
  2. Get text content
  3. If text matches /^第[一二三四五六七八九十百]+章/ → 章
  4. If text matches /^第[一二三四五六七八九十百]+節/ → 節
  5. If text matches /^[一二三四五六七八九十]、/ → 小節
  6. If text matches /^[甲乙丙丁戊己庚辛壬癸]、/ → 小小節 (also 子丑寅卯...)
  7. If no pattern match → check parent:
     a. Parent is 篇 (level 2) → 部
     b. Parent is 部 (level 3) → 章 or 節 (check siblings)
     c. Parent is 章 → 節
     d. Otherwise → need human verification
  8. Cross-check: if level decreases, a new subtree has started upward
```

## Counting Statistics for 《佛學概論》

| Level | Semantic | Count |
|:-----:|----------|:-----:|
| 2 | 篇 | 1 |
| 3 | 部 | 4 |
| 4 | 章 or 節 | 12 章 + 5 節 |
| 5 | 節 or 小節 | 30 節 |
| 6 | 小節 | 10 |
