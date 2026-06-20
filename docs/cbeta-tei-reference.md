<!-- 提示：用 VSCode 按 Cmd+K V（或 Obsidian 阅读模式）查看，自动渲染折叠等效果 -->

# CBETA TEI P5 XML 结构参考手册

> 本文档提炼自太虚大师全书（TX）CBETA XML 读取实践中积累的结构知识。内容聚焦 CBETA TEI P5 XML 本身的格式、标签和层级体系，不绑定特定典籍或项目。

---

## 1. 概述

### 1.1 CBETA TEI P5 XML 是什么

CBETA（中華電子佛典協會）使用 TEI P5（Text Encoding Initiative）标准对汉文佛典进行电子化编码。每部典籍对应一个 XML 文件，其中：

- **TEI 层**：提供文档框架（标题、作者、版本、修订记录等元数据），命名空间 `http://www.tei-c.org/ns/1.0`
- **CBETA 层**：提供佛典特有的目录结构、文本分块、行号、注解等，命名空间 `http://www.cbeta.org/ns/1.0`

### 1.2 命名空间声明

```xml
<TEI xmlns="http://www.tei-c.org/ns/1.0"
     xmlns:cb="http://www.cbeta.org/ns/1.0"
     xml:id="TX01n0001">
```

两种命名空间同时作用于同一文档。解析时必须正确处理命名空间前缀。

### 1.3 文档整体骨架

```
<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="...cbeta-p5.rnc" ...?>
<TEI xmlns="..." xmlns:cb="...">
  <teiHeader>   <!-- 元数据区 -->
    <fileDesc>...</fileDesc>
    <encodingDesc>...</encodingDesc>
    <profileDesc>...</profileDesc>
    <revisionDesc>...</revisionDesc>
  </teiHeader>
  <text>         <!-- 正文区 -->
    <front>...</front>
    <body>...</body>
    <back>...</back>
  </text>
</TEI>
```

### 1.4 编码和字符集

- 文件编码：UTF-8
- 部分罕用汉字落在 Unicode PUA（Private Use Area）区域，需通过 `<charDecl>` 中的映射表还原。例如：

```xml
<charDecl>
  <char xml:id="CB00145">
    <charName>CBETA CHARACTER CB00145</charName>
    <charProp>
      <localName>composition</localName>
      <value>[少/兔]</value>
    </charProp>
    <mapping type="unicode">U+3779</mapping>
    <mapping cb:dec="983185" type="PUA">U+F0091</mapping>
  </char>
</charDecl>
```

- `<charProp><localName>composition</localName>` 用 IDS（表意文字描述序列）描述字的构成
- `<mapping type="unicode">` 给出标准 Unicode 码位
- `<mapping type="PUA">` 给出 CBETA 暂用 PUA 码位

---

## 2. 文档结构

### 2.1 teiHeader — 元数据区

#### fileDesc（文件描述）

```xml
<fileDesc>
  <titleStmt>
    <title level="s">太虛大師全書</title>                <!-- 丛书级 -->
    <title level="m" xml:lang="zh-Hant">太虛大師全書．第一編</title>  <!-- 专著级 -->
    <author>民國 釋太虛著</author>
    <respStmt>
      <resp>Electronic Version by</resp>
      <name>CBETA</name>
    </respStmt>
  </titleStmt>
  <editionStmt>
    <edition>XML TEI P5</edition>
  </editionStmt>
  <extent>26卷</extent>
  <publicationStmt>
    <idno type="CBETA">
      <idno type="canon">TX</idno>.<idno type="vol">1</idno>.<idno type="no">1</idno>
    </idno>
    <distributor>
      <name>財團法人佛教電子佛典基金會 (CBETA)</name>
    </distributor>
    <availability>
      <p>Available for non-commercial use when distributed with this header intact.</p>
    </availability>
  </publicationStmt>
  <sourceDesc>
    <bibl>太虛大師全書</bibl>
  </sourceDesc>
</fileDesc>
```

关键字段：

| 元素 | 含义 |
|------|------|
| `<title level="s">` | 丛书级标题 |
| `<title level="m">` | 专著级标题 |
| `<author>` | 作者 |
| `<extent>` | 卷数 |
| `<idno type="canon">` | 藏经缩写（T=大正藏，X=卍续藏，TX=太虚全书等） |
| `<idno type="vol">` | 册号 |
| `<idno type="no">` | 编/经号 |
| `<sourceDesc>` | 底本来源 |

#### encodingDesc（编码描述）

记录字元声明（`<charDecl>`）、校勘标记体系（`<tagsDecl>`）、标点来源（`<editorialDecl>`）等。

#### profileDesc / revisionDesc

- `<profileDesc>`：语言声明（`<langUsage>`）
- `<revisionDesc>`：修订历史（`<change>` 含 `when` 时间戳）

### 2.2 text — 正文区

```
<text>
  <front>             <!-- 前附件：封面、目录预览 -->
    <cb:titlePage>
      <cb:mulu>...</cb:mulu>
    </cb:titlePage>
  </front>
  <body>               <!-- 正文主体 -->
    <cb:div>...</cb:div>
  </body>
  <back>               <!-- 后附件：校注、篇末注释 -->
    <cb:div type="apparatus">...</cb:div>
    <cb:div type="taixu-notes">...</cb:div>
  </back>
</text>
```

**重要**：在许多 CBETA 文件中（如 TX 太虚全书），`<cb:mulu>` 目录标记不在 `<front>` 内，而是以嵌套 `<cb:div>` 结构部署在 `<body>` 中，与正文交错出现。

---

## 3. 核心标签参考

> 每个标签均附真实 XML 片段。为简洁起见，示例中省略命名空间前缀的完整写法，实际解析时需处理 `{http://www.example.org/ns/1.0}` 格式的命名空间。

### 3.1 cb:mulu — 目录条目

`<cb:mulu>` 是 CBETA 最重要的结构标签，标记文档层级树中的每个节点。

```xml
<cb:mulu type="其他" level="1">概論</cb:mulu>
<cb:mulu type="其他" level="2">佛學概論</cb:mulu>
<cb:mulu type="其他" level="3">緒言</cb:mulu>
<cb:mulu type="其他" level="4">第一章 釋尊略傳</cb:mulu>
```

属性：

| 属性 | 含义 | 示例 |
|------|------|------|
| `level` | 当前节点的层级深度（相对于父节点） | `"1"` `"2"` `"3"` ... `"6"` |
| `n` | 文件内顺序编号，用于锚定 | `"001"` `"001a"` `"001b"` |
| `type` | 目录类型 | `"其他"` `"卷"` |
| `ref` | 指向 body 中对应 `xml:id` 的引用（可选） | — |

**核心原则：`level` 是相对编号，不是固定语义标签。** 详见第 4 章。

### 3.2 cb:div — 文本分块

`<cb:div>` 是 CBETA 扩展的 div 元素，用于逻辑分块，嵌套使用。

```xml
<cb:div type="other">
  <cb:mulu type="其他" level="3">緒言</cb:mulu>
  <head>緒　言</head>
  <p>「佛教」，平常都以寺菴中之僧尼為代表...</p>
</cb:div>
```

`type` 属性取值：

| type | 含义 |
|------|------|
| `"other"` | 通用内容块（最常见） |
| `"orig"` | 经论原文（解经类文章中使用，对应 `margin-left:0em`） |
| `"commentary"` | 讲义注解（解经类文章中使用，对应 `margin-left:1em`） |
| `"apparatus"` | 校勘装置（在 `<back>` 中） |
| `"taixu-notes"` | 太虚全书校注（在 `<back>` 中） |

### 3.3 head — 标题

出现在 `<cb:div>` 内部，标记该分块的标题。

```xml
<head>佛學概論</head>
<head type="sub">第一章 釋尊略傳</head>
```

**注意**：`<head>` 与 `<cb:mulu>` 通常包含相同或相似的文本，但 `<head>` 用于正文渲染，`<cb:mulu>` 用于目录结构。两者可能格式略有差异（如全角空格保留与否）。

### 3.4 p — 段落

```xml
<p xml:id="pTX01p0005a0201" style="margin-left:0em;text-indent:2em">
「佛教」，平常都以寺菴中之僧尼為代表...
</p>
<p cb:type="pre" xml:id="pTX01p0001a0501">
　　　　緒　言……………………………………………………五
</p>
```

属性：

| 属性 | 含义 |
|------|------|
| `xml:id` | 段落的唯一标识符（格式：`p{文件ID}p{行号}{序号}`） |
| `style` | 排版样式（`margin-left`、`text-indent`） |
| `cb:type` | CBETA 段落类型：`"pre"` 表示预格式化（如目录预览） |

### 3.5 byline — 题下注释

记录讲说时间、地点、记录者等信息，位于 `<head>` 之后、正文之前。

```xml
<head>佛學概論</head>
<byline cb:type="other">——十九年一月在閩南佛學院編述——</byline>
```

```xml
<head>佛法導言</head>
<byline>（碧松記）</byline>
```

常见格式：

| 格式 | 含义 |
|------|------|
| `——…——` | 讲说时间地点 |
| `（…記）` | 记录者 |
| `（…合記）` | 合记 |

**陷阱**：`<byline>` 内部可能嵌有 `<lb/>` 换行标记，提取文本时需压缩全部空白。

### 3.6 note — 注释

CBETA 中有两种注释模式：

**（1）行内注释**

```xml
<note place="inline">見海刊十八卷九期</note>
```

**（2）篇末注释（通过 anchor 引用）**

在 `<back>` 区域的 `<cb:div type="taixu-notes">` 中：

```xml
<back>
  <cb:div type="taixu-notes">
    <head>太虛大師全書 校注</head>
    <p>
      <note n="0001001" resp="#resp2" place="foot text"
            type="orig" target="#nkr_note_orig_0001001">
        本論略本，民國十五年八月，在北平佛學研究會講...
      </note>
    </p>
  </cb:div>
</back>
```

属性：

| 属性 | 含义 |
|------|------|
| `place` | 注释位置：`"inline"`（行内）、`"foot text"`（脚注/篇末） |
| `n` | 注释编号 |
| `target` | 锚点引用（`#nkr_note_orig_N`） |
| `resp` | 注释责任者（`#resp2` = TaiXu） |
| `type` | `"orig"` 表示原始注释 |

### 3.7 anchor — 锚点

在正文中标记注释引用位置：

```xml
<head>佛學概論<anchor xml:id="nkr_note_orig_0001001" n="0001001"/></head>
```

`xml:id` 与 `<back>` 中 `<note target="...">` 的 `target` 属性一一对应。`n` 属性值用于排序。

### 3.8 lb / pb — 行分隔 / 页分隔

```xml
<pb ed="TX" xml:id="TX01.0001.0005a" n="0005a"/>
<lb ed="TX" n="0005a01"/>
```

属性：

| 元素 | 属性 | 含义 |
|------|------|------|
| `<pb>` | `n` | 页码（4 位数字 + a/b 栏位） |
| `<pb>` | `xml:id` | 页唯一 ID（格式：`{canon}.{vol}.{page}`） |
| `<lb>` | `n` | 行号（页码 + 栏位 + 2 位行号，如 `0005a01`） |
| 两者 | `ed` | 版本标识（如 `"TX"`） |

`<pb>` 和 `<lb>` 是空元素（自闭合）。它们在 XML 树中作为里程碑节点，本身不含文本——其后的文本继承该行/页号。

### 3.9 cb:juan — 卷分隔

```xml
<milestone unit="juan" n="1"/>
<milestone unit="juan" n="27"/>
```

CBETA 用 TEI 标准的 `<milestone>` 元素标记卷边界，`unit="juan"` 表示以卷为单位。在多卷 XML 文件中，`<milestone>` 是划分各卷正文起点的关键标记。

### 3.10 app / lem / rdg — 校勘信息

记录不同来源（底本 vs CBETA 编辑）之间的文字差异：

```xml
<app from="#beg0140a1201" to="#end0140a1201">
  <lem wit="#wit.orig">歛</lem>
  <rdg resp="#resp3" type="cbetaRemark">斂</rdg>
</app>
```

| 元素 | 含义 |
|------|------|
| `<app>` | 校勘条目，`from`/`to` 指向正文中对应文字的 ID 区间 |
| `<lem>` | 底本用字（`wit="#wit.orig"` = 太虚原书） |
| `<rdg>` | 校订后的用字（`type="cbetaRemark"` = CBETA 校注） |

校勘装置通常位于 `<back>` 区域的 `<cb:div type="apparatus">` 中。

### 3.11 supplied / unclear — 编辑标记

TEI 标准元素，用于标记编辑者的干预：

| 元素 | 含义 |
|------|------|
| `<supplied>` | 编辑者补充的文字 |
| `<unclear>` | 底本模糊不确定的文字 |

### 3.12 标签总览表

| 标签 | 命名空间 | 类型 | 用途 |
|------|:------:|:----:|------|
| `<TEI>` | tei | 根 | 文档根元素 |
| `<teiHeader>` | tei | 容器 | 元数据 |
| `<text>` | tei | 容器 | 正文 |
| `<front>` | tei | 容器 | 前附件 |
| `<body>` | tei | 容器 | 正文主体 |
| `<back>` | tei | 容器 | 后附件 |
| `<cb:mulu>` | cb | 结构 | 目录条目 |
| `<cb:div>` | cb | 容器 | 文本分块 |
| `<head>` | tei | 内容 | 标题 |
| `<p>` | tei | 内容 | 段落 |
| `<byline>` | tei | 内容 | 题下注释 |
| `<note>` | tei | 内容 | 注释 |
| `<anchor>` | tei | 空元素 | 锚点 |
| `<pb>` | tei | 空元素 | 页分隔 |
| `<lb>` | tei | 空元素 | 行分隔 |
| `<milestone>` | tei | 空元素 | 卷分隔 |
| `<app>` | tei | 容器 | 校勘条目 |
| `<lem>` | tei | 内容 | 校勘-底本 |
| `<rdg>` | tei | 内容 | 校勘-校订 |
| `<supplied>` | tei | 内容 | 编辑补充 |
| `<unclear>` | tei | 内容 | 底本模糊 |

---

## 4. `<cb:mulu>` 层级系统

### 4.1 核心原则

**`level` 是相对于父节点的深度编号，不是固定语义标签。**

同一个语义层级（如「章」）在不同文章中可能出现在 `level="3"` 或 `level="4"`，取决于整篇文章是否存在更上层的结构（如「部」）。必须根据上文语境而非孤立的 `level` 数值来判断语义。

### 4.2 标准层级映射（当所有层级都存在时）

| Level | 语义 | 编号模式 | 示例 |
|:-----:|------|----------|------|
| 1 | 子目类别 | — | 概論 / 判攝 / 源流 |
| 2 | 篇（文章名） | — | 佛學概論 / 中國佛學 |
| 3 | 部 或 章 | 无编号，或 第X章 | 緒言 / 學史，或 第一章 佛學大綱 |
| 4 | 章 或 節 | 第X章，或 第一節 | 第一章 釋尊略傳 |
| 5 | 節 或 小節 | 第一節，或 一、二、三 | 第一節 總論，或 一 心之分析 |
| 6 | 小節 或 小小節 | 一、二、三，或 甲、乙、丙 | 一 安般禪，或 甲 慧文慧思之創發 |

### 4.3 Shift Rule（层级偏移规则）

层级会随上层结构的有无而发生偏移：

- **有「部」的文章**（如《佛學概論》：緒言/學史/學理/結論）→ level 3 = 部、level 4 = 章、level 5 = 節
- **无「部」的文章**（如《中國佛學》）→ level 3 = 章、level 4 = 節
- **无「章」仅有「節」的段落**（如結論下的節）→ 節直接从 level 4 开始（跳过章层）

#### 实例：《佛學概論》层级树（有「部」层）

```
├─ level 1: 概論                         子目类别
│  └─ level 2: 佛學概論                  篇
│     ├─ level 3: 緒言                   部（无编号）
│     ├─ level 3: 學史                   部（无编号）
│     │  ├─ level 4: 第一章 釋尊略傳      章
│     │  │  ├─ level 5: 第一節 ...        節
│     │  │  ├─ level 5: 第二節 ...        節
│     │  │  └─ level 5: 第三節 ...        節
│     │  ├─ level 4: 第二章 印度佛學略史  章
│     │  ├─ level 4: 第三章 中國佛學歷史  章
│     │  └─ level 4: 第四章 各地之佛學略史 章
│     ├─ level 3: 學理                   部（无编号）
│     │  ├─ level 4: 第一章 因緣所生法... 章
│     │  │  ├─ level 5: 第一節 總論       節
│     │  │  ├─ level 5: 第二節 無始流轉   節
│     │  │  │  ├─ level 6: 一 心之分析    小節
│     │  │  │  ├─ level 6: 二 煩惱業生    小節
│     │  │  │  └─ ...                    小節
│     │  │  └─ ...
│     │  └─ ...
│     └─ level 3: 結論                   部（无编号）
│        ├─ level 4: 第一節 解釋...       節 ← 无「章」层，節直接在 level 4
│        ├─ level 4: 第二節 佛學的本質    節
│        └─ ...
```

#### 对比实例：《中國佛學》层级树（无「部」层）

```
├─ level 1: 源流                         子目类别
│  └─ level 2: 中國佛學                   篇
│     ├─ level 3: 第一章 佛學大綱          章 ← 无「部」层，章直接在 level 3
│     ├─ level 3: 第二章 中國佛學特質在禪  章
│     │  ├─ level 4: 第一節 略敘因緣       節
│     │  ├─ level 4: 第二節 依教修心禪     節
│     │  │  ├─ level 5: 一 安般禪         小節
│     │  │  ├─ level 5: 二 五門禪         小節
│     │  │  └─ ...
│     │  └─ ...
│     ├─ level 3: 第三章 禪觀行演為台賢教  章
│     │  ├─ level 4: 第一節 緒言           節 ← 「緒言」在此是節，不是部！
│     │  ├─ level 4: 第二節 實相禪布為天台教 節
│     │  │  ├─ level 5: 一 天台學之根據    小節
│     │  │  ├─ level 5: 二 天台學之先河    小節
│     │  │  ├─ level 5: 三 天台學之成立    小節
│     │  │  │  ├─ level 6: 甲 慧文慧思之創發 小小節
│     │  │  │  └─ level 6: 乙 智者之完成    小小節
│     │  │  └─ ...
│     │  └─ ...
│     ├─ level 3: 第四章 禪台賢流歸淨土行  章
│     └─ level 3: 第五章 中國佛學之重建    章
```

**关键差异**：《佛學概論》的「緒言」是 level-3 部名；《中國佛學》第三章第一節的「緒言」是 level-4 节名。同一文本，不同角色。

### 4.4 Level Shift 对照表

| 父节点 | 当前 level 映射 |
|--------|-----------------|
| level 1（子目类别） | level 2 → 篇 |
| level 2（篇） | level 3 → 部（无编号）或 章（有「第X章」） |
| level 3（部） | level 4 → 章（有「第X章」）或 節（有「第一節」） |
| level 3（章） | level 4 → 節 |
| level 4（章） | level 5 → 節 |
| level 4（節） | level 5 → 小節 |
| level 5（節） | level 6 → 小節 |
| level 5（小節） | level 6 → 小小節 |

### 4.5 语义检测算法

对每个 `<cb:mulu>` 元素的文本内容进行模式匹配：

```
1. 若文本匹配 /^第[一二三四五六七八九十百]+章/ → 章（chapter）
2. 若文本匹配 /^第[一二三四五六七八九十百]+節/ → 節（section）
3. 若文本匹配 /^[一二三四五六七八九十]、/      → 小節（subsection）
4. 若文本匹配 /^[甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥]、/ → 小小節
5. 若无匹配 → 检查父节点：
   a. 父节点为「篇」(level 2) → 部
   b. 父节点为「部」(level 3) → 章或節（检查同级兄弟）
   c. 父节点为「章」→ 節
   d. 其他 → 需人工核实
6. 交叉检验：若 level 数值下降，表示向上开启了新的子树
```

**天干序列**：CBETA 使用中国传统天干（甲乙丙丁戊己庚辛壬癸）和地支（子丑寅卯辰巳午未申酉戌亥）标记深层嵌套。

---

## 5. 常见文档模式

### 5.1 科判解经模式（orig + commentary 兄弟 div）

解经类文章（对佛经逐句解读）采用特殊的 div 结构：标题 div（`type="other"`）与正文 div（`type="orig"`/`type="commentary"`）是兄弟节点关系。

```xml
<cb:div>
  <cb:div type="other">
    <cb:mulu type="其他" level="4">甲一　總起分</cb:mulu>
    <head>甲一　總起分</head>
  </cb:div>
  <cb:div type="orig">
    <p style="margin-left:0em;text-indent:2em">
      世尊成道已，作是思惟：離欲寂靜是最為勝...
    </p>
  </cb:div>
  <cb:div type="commentary">
    <p style="margin-left:1em;text-indent:2em">
      佛經例分三大部分：一、序分，二、正宗分，三、流通分...
    </p>
  </cb:div>
</cb:div>
```

处理要点：

1. `type="orig"` 和 `type="commentary"` 的 div **没有** `<cb:mulu>` 也没有 `<head>`，`get_heading_text()` 无法从中获取标题。
2. 解析时，遇到空标题不要跳过，应照常提取 `<p>` 并递归子节点。
3. **格式区分**：`type="orig"`（经论原文）对应 `margin-left:0em`——通常以块引用形式呈现；`type="commentary"`（讲义注解）对应 `margin-left:1em`——通常以普通段落形式呈现。

### 5.2 附录文章模式

CBETA 有时将附录文章标为独立的 level-2 条目，篇名以「（附）」开头。在纸本目录中这些附录附属于前一篇文章，不应独立成篇。

```xml
<cb:mulu type="其他" level="2">（附）答生命研究之疑問</cb:mulu>
```

处理方式：

- 将附录合并入前一篇（前一篇的 `byte_end` 延伸到附录的 `byte_end`）
- 从篇目链表中移除附录条目，重连链表
- 在前一篇的备註中标注「含附錄：（附）…」

### 5.3 纲目预览模式（目次 / 綱要 / 科分）

部分文章开头有「目次」「綱要」或「科分」条目，它们只是文章结构的预览列表，不是独立的章节，在构建目录树时应过滤掉。

```xml
<cb:div type="other">
  <cb:mulu type="其他" level="3">目次</cb:mulu>
  <p cb:type="pre">
    　　　　緒　言……………………………………………………五
    　　　　學　史……………………………………………………一〇
    　　　　　第一章　釋尊略傳……………………………………一〇
    ...
  </p>
</cb:div>
```

**过滤关键词完整列表**：`目次`、`綱要`、`目錄`、`目録`、`科分`。

判断标准：若条目标签匹配上述任一关键词，且其内容为全文结构概览、非实质论述，则跳过。

**注意**：「前言」（foreword）不在过滤之列——前言是文章的有用开篇，应保留在目录树中。

### 5.4 题注模式

文章标题之下、正文之前常见题注，记录讲说信息。XML 中有两种常见组合：

**模式 A：byline + inline note**

```xml
<head>佛學概論</head>
<byline cb:type="other">——十九年一月在閩南佛學院編述——</byline>
```

**模式 B：byline 含记录者**

```xml
<head>佛法導言</head>
<byline>（碧松記）</byline>
```

**模式 C：byline 内嵌 `<lb/>`（罕见）**

```xml
<byline>（李了<lb/>空、胡法智合記）</byline>
```

提取 byline 文本时需用 `"".join(text.split())` 压缩所有空白，否则 `<lb/>` 的换行残留会破坏输出格式。

---

## 6. 已知陷阱与注意事项

### 6.1 level 编号不作语义标签

**陷阱**：写解析代码时，不要硬编码「level="4" 一定是 章」或「level="4" 一定是 節」。level 值纯粹是相对于直接父节点的深度偏移量，在不同文章结构下映射到不同语义层级。

**解法**：始终结合父节点类型 + 文本编号模式来确定语义，参见 §4.5 算法。

### 6.2 「緒言」的歧义

同一文本「緒言」在不同文章中可作不同角色：

- 《佛學概論》中 → level 3，**部**名（与 學史、學理、結論 并列）
- 《中國佛學》第三章第一節标题 → level 4，**節**名

不能仅凭标签文本内容判断语义，必须结合其在层级树中的位置。

### 6.3 纲目/目次/科分需过滤

参见 §5.3。关键：不要因为 `<cb:mulu>` 存在 level 值就自动将其视为一个有效章节——需检查文本内容是否匹配过滤关键词。

### 6.4 ElementTree 无 parent 指针

Python 标准库 `xml.etree.ElementTree` 不支持 `lxml` 的 `iterancestors()` 或 `.parent` 属性。向上导航需手动构建映射：

```python
parent_map = {}
for parent in root.iter():
    for child in parent:
        parent_map[child] = parent
```

之后用 `parent_map[elem]` 获取父节点。

### 6.5 卷 div ≠ 文章 div

从 `<cb:mulu level="2">` 向上爬两级 div 得到的并非该文章的专属容器，而是整个 CBETA 卷的容器 div（包含该卷内所有文章的全部 `<cb:mulu>` 条目）。

**正确做法**：先收集整个卷 div 内所有 `<cb:mulu>` 条目，再以相邻 `level="2"` 条目的位置为边界切分出目标文章的范围：

```python
art_start = # 首个 level=2 且 label 匹配的文章条目索引
art_end   = # 下一个 level=2 条目的索引（若为最后一篇则取 len(all_mulu)）
article_entries = all_mulu[art_start:art_end]
```

### 6.6 附录文章合并

参见 §5.2。关键特征：篇名以「（附）」开头、紧跟前一篇之后、其间无 level-1（子目分隔）。

### 6.7 标题编号与正文间的空格

CBETA 中章节编号（前缀）与标题正文之间通常是粘在一起的（如 `第一章釋尊略傳`）。在规范化输出时，应在前缀与正文间插入一个全角空格（`第一章　釋尊略傳`）。

六种前缀模式及处理：

| 前缀类型 | 输入 | 输出 |
|---------|------|------|
| CJK 裸数字+数字 | `二三法印` | `二　三法印` |
| 第X章/节/篇 | `第一章釋尊略傳` | `第一章　釋尊略傳` |
| CJK 裸数字 | `一契理與應機` | `一　契理與應機` |
| 天干（非数字后） | `甲契理之實義` | `甲　契理之實義` |
| 天干+数字组合 | `甲一證信` | `甲一　證信` |
| 全角数字 | `１十善業為…` | `１　十善業為…` |

### 6.8 `<lb/>` 在 byline 中的换行残留

部分 `<byline>` 内部嵌有 `<lb/>` 换行标记。`itertext()` 在拼接时会把 `<lb/>` 的 tail 文本前的换行符也带入，导致输出断成多行。修复方式：对 byline 文本做 `"".join(text.split())` 压缩全部空白，而非仅 `.strip()`。

### 6.9 `<note>` 嵌套在 `<byline>` 内的情形

部分 CBETA 文件中，篇末刊载来源 `<note place="inline">` 嵌套在 `<byline>` 元素内部（而非平级关系）。解析时需使用 `re.DOTALL` 匹配跨行文本，确保嵌套 note 也被正确提取。

### 6.10 子目内篇号独立编号

在一个子目（如「概論」）内部，文章编号从 1 起编；切换到下一个子目（如「判攝」）时，编号从 1 重新开始——而不是跨子目连续编号。解析时需为每个子目独立维护计数器。

### 6.11 文末 byline/note 的直接子元素

文章 div 末尾的记载人 `<byline>` 和刊载来源 `<note place="inline">` 是文章 div 的直接子元素（而非嵌套在 `<cb:div>` 内）。如果解析代码只遍历 `<cb:div>` 子元素，这些文末附注会被整段跳过。应在处理完所有子 `<cb:div>` 之后，额外对文章 div 本身提取一遍段落级元素。

---

## 7. CBETA ID 体系

### 7.1 ID 格式

```
{prefix}{vol}n{no}
```

- `{prefix}`：藏经缩写（见 §7.2）
- `{vol}`：实体书册号（1-2 位数字，如 `01`）
- `n`：固定字符 `n`
- `{no}`：编/经的逻辑编号

示例：`TX01n0001` = 太虚全书 · 第 1 册 · 第 1 编

### 7.2 常见前缀

| 前缀 | 全称 | 说明 |
|:----:|------|------|
| `T` | 大正新脩大藏經 | 日本大正一切经刊行会编，100 卷 |
| `X` | 卍新纂續藏經 | 续藏 |
| `TX` | 太虛大師全書 | 太虚全书专藏（CBETA 专门编目） |
| `J` | 嘉興藏 | 明版嘉兴藏 |
| `K` | 高麗大藏經 | 高丽藏 |

### 7.3 文件命名规则

CBETA ID 直接用作文件名：`{id}.xml`（如 `TX01n0001.xml`）。文件存放于按册号分组的子目录下（如 `TX01/TX01n0001.xml`）。

### 7.4 idno 对应关系

文件命名信息同样出现在 `<teiHeader>` 的 `<publicationStmt>` 中：

```xml
<idno type="CBETA">
  <idno type="canon">TX</idno>.<idno type="vol">1</idno>.<idno type="no">1</idno>
</idno>
```

| `<idno type="...">` | 对应 ID 部分 | 示例值 |
|---------------------|-------------|--------|
| `canon` | prefix | `TX` |
| `vol` | vol | `1` |
| `no` | no | `1` |

---

## 8. 解析工具与技巧

### 8.1 Python xml.etree.ElementTree 基础用法

```python
import xml.etree.ElementTree as ET

tree = ET.parse('_data/cbeta/TX/TX01/TX01n0001.xml')
root = tree.getroot()
```

### 8.2 命名空间处理

CBETA XML 使用两个命名空间。ElementTree 内部会将命名空间 URI 拼接为 `{uri}` 前缀：

```python
CBETA_NS = '{http://www.cbeta.org/ns/1.0}'
TEI_NS = '{http://www.tei-c.org/ns/1.0}'

# 搜索所有 cb:mulu 元素
mulu_elems = root.findall(f'.//{CBETA_NS}mulu')

# 在 body 中搜索
body = root.find(f'.//{TEI_NS}text/{TEI_NS}body')
```

**技巧**：如果解析的是从文件中截取的 XML 片段（而非完整文档），需要先将其包装在一个带有命名空间声明的根元素中，否则 ElementTree 无法解析：

```python
wrap = f'<root xmlns:cb="{CBETA_NS[1:-1]}" xmlns:tei="{TEI_NS[1:-1]}">' \
     + chunk.decode('utf-8') + '</root>'
el = ET.fromstring(wrap)
```

### 8.3 字节偏移定位读取

处理大文件时（单个 TX 文件可达 500KB–900KB），应通过字节偏移只读取目标片段，而非加载整个 XML 树：

```python
with open('_data/cbeta/TX/TX01/TX01n0001.xml', 'rb') as f:
    f.seek(byte_start)
    chunk = f.read(byte_end - byte_start)
```

前提：需要预先建立文章 → 字节偏移的索引（可通过一次全文件扫描完成）。

### 8.4 itertext() 与手动遍历

提取纯文本时，`itertext()` 是最简洁的方式：

```python
all_text = ''.join(el.itertext())
```

但它不保留任何结构边界（段落、标题、注释之间的分界会丢失）。当需要保留结构时（如区分标题 vs 段落 vs 注释），应手动遍历子节点。

需要注意的是 `itertext()` 会拼接 `<lb/>` 标记之间的 tail 文本，可能在行间断处产生额外的空白符——这在 byline 提取中尤为常见（见 §6.8）。

### 8.5 手动构建 parent_map

参见 §6.4。因为 ElementTree 无 parent 指针，任何需要向上导航的操作（如从 `<cb:mulu>` 向上找到所属 `<cb:div>` 或计算祖先层级）都依赖 `parent_map`。

---

## 附录

### 参考来源

本文档知识来自：

- CBETA TEI P5 XML 官方 schema：[cbeta-p5.rnc](https://github.com/cbeta-org/xml-p5)
- 太虚大师全书 TX XML 文件（共 40 卷）的解析实践
- TEI P5 Guidelines：[https://tei-c.org/guidelines/p5/](https://tei-c.org/guidelines/p5/)

### 版本记录

| 日期 | 版本 | 说明 |
|------|:----:|------|
| 2026-06-20 | v1.0 | 初始版本，提炼自太虚全书 CBETA 解析实践中积累的结构知识 |
