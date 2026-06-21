---
book: {bian_name}
---

# {bian_name} · 概览仪表盘

```dataview
TABLE word_count AS "千字", date AS "年代", location AS "地点"
FROM "{out_dir}"
WHERE book AND sequence
SORT sequence ASC
```

> 点击表头可排序。未来可扩展 `keywords`（关键字）和 `themes`（核心思想）列。
