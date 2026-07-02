---
book: {book_name}
---

# {book_name} · 概览仪表盘

```dataview
TABLE word_count AS "千字", choice(create_m, create_y + "-" + create_m, create_y) AS "年代", location AS "地点", publication AS "刊载"
FROM "{out_dir}"
WHERE book AND sequence
SORT sequence ASC
```

> 点击表头可排序。`concepts`（概念）、`domains`（领域）、`functions`（功能）、`bearings`（方位）列留待以后填充。
