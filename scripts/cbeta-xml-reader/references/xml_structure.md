# CBETA TEI P5 XML Structure

Reference for the TEI P5 XML structure used by CBETA for the 太虚大师全书.

## Document Structure

```
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    ...
  </teiHeader>
  <text>
    <front>
      <cb:titlePage>
        <cb:mulu>...mulu entries...</cb:mulu>
      </cb:titlePage>
    </front>
    <body>...</body>
  </text>
</TEI>
```

## Key Elements

### `cb:mulu` — Directory Entry

The central element for directory extraction.

```xml
<cb:mulu n="001" level="1">概論</cb:mulu>
<cb:mulu n="001a" level="2">佛學概論</cb:mulu>
<cb:mulu n="001b" level="3">緒言</cb:mulu>
<cb:mulu n="001c" level="4">第一章 釋尊略傳</cb:mulu>
```

Attributes:
- `n`: Sequential ID within the file, used for anchoring
- `level`: Relative depth from parent (1 = top)
- Often has `ref` attribute pointing to an XML ID in `<body>`

### `cb:juan` — Volume

```xml
<cb:juan n="001" fun="open">
  <cb:mulu type="卷">...</cb:mulu>
</cb:juan>
```

### `head` — Heading

```xml
<head type="sub">第一章 釋尊略傳</head>
```

Used in both `<front>` (in titlePage/mulu) and `<body>` (for inline headings).

### `lb` — Line Break

```xml
<lb n="0001a01" ed="CBETA"/>
```

- `n`: Line number (4-digit page + column + 2-digit line)
- Used for precise citation and cross-reference

### `pb` — Page Break

```xml
<pb n="0001a" ed="CBETA"/>
```

### `note` — Annotation

```xml
<note place="inline">（编按：...）</note>
```

## Name Pattern Detection

When parsing `<cb:mulu>` text content, detect the semantic level:

| Pattern | Chinese | Semantic |
|---------|:-------:|----------|
| 第X章 | ✓ | 章 (chapter) |
| 第X節 | ✓ | 節 (section) |
| 一、二、三… | ✓ | 小節 (subsection) |
| 甲、乙、丙… | ✓ | 小小節 (sub-subsection) |
| (no numbering) | — | need depth check |

For unnumbered entries, judgment relies on:
1. Position in the cb:mulu tree (how many levels above)
2. Whether parent has numbering
3. Comparison with other siblings

## CBETA-Specific Elements

- `cb:docNumber` — Abbreviation: TX.{volume}.{juan}
- `cb:tt` — CBETA internal markup
- `<supplied>` — Editor-inserted text
- `<unclear>` — Uncertain text

## TEI Header Metadata

Key fields in `<fileDesc>`:

| Element | Content |
|---------|---------|
| `<title>` | 太虚大师全书 |
| `<author>` | 釋太虛 |
| `<respStmt>` | CBETA electronic editors |
| `<extent>` | Volume count (e.g., 26卷) |
| `<publisher>` | 財團法人佛教電子佛典基金會 |
