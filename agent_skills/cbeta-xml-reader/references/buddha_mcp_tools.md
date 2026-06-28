# Buddha MCP Tool Reference

> **注意**：此文件仅供历史参考。本项目已硬性规定不使用 buddha MCP，全部 CBETA 数据通过本地 `_data/cbeta/TX/` XML 文件和 Python + ElementTree 解析。保留此文件仅为记录早期探索时使用的 MCP 工具接口。

Complete reference for using the buddha MCP tools to access CBETA data.

## Tool Overview

All tools use the prefix `mcp__buddha__`.

| Tool | Purpose | Required |
|------|---------|----------|
| `fetch` | Retrieve text by ID | `id`, `source` (for TX IDs) |
| `search` | Full-text regex search | `source`, `query` |
| `pipeline` | Search + auto-fetch | `source`, `query` |
| `title_search` | Title-based search | `source`, `query` |
| `resolve` | Resolve query to IDs | `query` |

## `fetch` — Primary Text Retrieval

```
mcp__buddha__fetch({
  source: "cbeta",
  id: "TX01n0001",
  maxChars: 5000,
  format: "plain",
  full: false
})
```

### Parameters

| Param | Type | Description |
|-------|------|-------------|
| `id` | string | CBETA ID (required) |
| `source` | string | Must be `"cbeta"` for TX IDs (TX not auto-detected) |
| `maxChars` | number | Max characters to return (optional, omit for full) |
| `format` | string | `"plain"` for readable text without TEI markup |
| `full` | boolean | Return full text without slicing |
| `headIndex` | number | Filter by `<head>` index (0-based) |
| `headQuery` | string | Filter by `<head>` substring match |
| `part` | string | CBETA juan/part number (e.g., `"001"`) |
| `lineNumber` | number | Target line for context extraction |
| `contextBefore` | number | Lines before target |
| `contextAfter` | number | Lines after target |
| `highlight` | string | Highlight string or regex |
| `includeNotes` | boolean | Include footnotes/annotations |

### Important Notes

- **TX IDs require explicit `source: "cbeta"`** — they are NOT auto-detected.
- Use `format: "plain"` for readable text; omit for TEI P5 XML.
- For very long texts, use `part` parameter to fetch one juan at a time.
- The `headQuery` param is useful for finding a specific section by title.

## `search` — Full-Text Search

```
mcp__buddha__search({
  source: "cbeta",
  query: "如來藏",
  exact: true,
  maxResults: 10
})
```

Returns `_meta.fetchSuggestions` for direct fetching of matches.

### Parameters

| Param | Type | Description |
|-------|------|-------------|
| `source` | string | `"cbeta"` for 太虚全书 |
| `query` | string | Search term or regex |
| `exact` | boolean | Phrase search (default: true) |
| `maxResults` | number | Max results (default: 20) |
| `maxMatchesPerFile` | number | Max matches per file (default: 5) |

## `pipeline` — Search + Auto-Fetch

```
mcp__buddha__pipeline({
  source: "cbeta",
  query: "佛學",
  autoFetch: false
})
```

Set `autoFetch: false` to get summary only; `true` to auto-fetch top matches.

## `title_search` — Title Lookup

```
mcp__buddha__title_search({
  source: "cbeta",
  query: "佛法導言"
})
```

## Common Patterns

### Pattern 1: Fetch full text for directory extraction

```
mcp__buddha__fetch({source: "cbeta", id: "TX01n0001", maxChars: 50000})
```
Then parse `<cb:mulu>` elements in the TEI header.

### Pattern 2: Search for a specific article

```
mcp__buddha__search({source: "cbeta", query: "佛學概論", exact: true})
```
Use `_meta.fetchSuggestions` to locate the file.

### Pattern 3: Get a specific section by heading

```
mcp__buddha__fetch({
  source: "cbeta", id: "TX02n0001",
  headQuery: "中國佛學特質在禪",
  format: "plain"
})
```

### Pattern 4: Fetch by juan number

```
mcp__buddha__fetch({source: "cbeta", id: "TX01n0001", part: "001"})
```
Fetches only juan 1 of a multi-juan file.

## TX ID Auto-Detection Issue

The buddha MCP auto-detects source for standard Taisho IDs (T0262, X0001) but NOT for 太虚全书 TX IDs. Always include `source: "cbeta"` explicitly when using TX-prefixed IDs.
