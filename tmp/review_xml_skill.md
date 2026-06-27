

当前处于git 的 `claude-code-review` 分支。
你已经帮我审查了本项目中，负责 “读取 CBETA XML 文件、构建编目录并提取文章正文” 的这个 skill 模块（文件夹路径：`scripts/cbeta-xml-reader`）。
以下是审查报告。

## 一、结构鲁棒性

**1. `bool(element)` 真值陷阱（潜在崩溃/静默丢标题）— 中高危** 代码里大量使用 `A.find(...) or B.find(...)` 这一惯用法：

- `get_heading_text` 第 123 行：`head = div.find(f"{{{TEI_NS}}}head") or div.find("head")`
- 第 127、274、379、538 行同样模式

`xml.etree.ElementTree` 的 `Element.__bool__` 返回的是"子元素个数是否为 0"。一个 `<head>第一章</head>`（只有文字、无子元素）求值为 **False**。于是 `命名空间find（拿到真实元素）or 非命名空间find` 会因为前者"假"而落到后者。目前之所以没出事，是因为 `extract_article_fulltext` 走的是**字节片段 + 无命名空间解析**路径（`parse_article_chunk` 包裹的片段里 `<head>` 是裸标签），命名空间 `find` 返回 `None`，恰好让 `or` fallback 生效。但这是"靠巧合工作"：一旦有人把这些 helper 用在 `ET.parse` 的整树（带默认 `xmlns`，如 `extract_book_catalog`）上，文字型 `<head>`/`<note>` 会被判为假而丢失。建议统一改成 `x = a.find(...); if x is None: x = b.find(...)`，杜绝真值判断。

**2. 字节偏移扫描的脆弱假设（`scan_byte_offsets`，catalog 脚本第 45–106 行）**

- 向后只搜 200 字节找 `<cb:div`（第 64 行）。若 `<cb:div ...>` 开标签到其 `<cb:mulu level="2">` 之间超过 200 字节，`last_div == -1`，`div_start` 退化为 mulu 自身位置，得到一个错误范围；随后 `find_div_end` 从错位点深度追踪，可能整篇越界。
- 该脚本用**正则数 `level="2"`** 来定位文章，又用 **ElementTree 数 `level==2`** 来生成条目（第 146–170 行），两套独立解析靠 `article_count` 严格对齐索引 `byte_ranges[article_count]`。任何一方多/少一个（属性单引号、属性顺序、`level="2"` 出现在意外上下文）就会 `IndexError` 或全篇偏移错位。这是隐性的强耦合。

**3. 空输入直接崩** `extract_book_catalog.py` 第 308 行无条件访问 `entries[0]`/`entries[-1]`；若某编没有任何 level-2 条目（或 XML 解析异常导致空），直接 `IndexError`。`extract_article` 第 744 行找不到 level-2 div 时 `raise RuntimeError`，单篇模式（非 batch）未捕获，直接抛栈。

**4. 片段解析无容错** `parse_article_chunk` 第 119 行 `ET.fromstring(wrap)`，一旦字节范围切歪（见上）导致标签不闭合，抛 `ParseError`，单篇模式无 try/except。批量模式有兜底（第 1240 行），单篇没有——体验不一致。

## 二、清洗彻底性

**5. `''.join(text.split())` 会吞掉所有有意义空格（`render_paragraph` 第 240 行）** 对纯中文无害，但混排的拉丁词、年份、英文术语会被压成连写（"Master Taixu" → "MasterTaixu"）。对太虚文本通常 OK，但属于"过度清洗"，建议只压缩中文间空白或改用更克制的规整。

**6. CBETA 缺字标记 `<g>`（gaiji）未处理** 正文走 catch-all `''.join(child.itertext())`（第 228 行）。CBETA 用 `<g ref="#CBxxxxx"/>` 表示罕用字，这类元素无 text，`itertext()` 直接产出空——会**静默丢字**。律释/法相部分缺字较多，值得专门映射。

**7. 韵文/表格结构被拍平** `<lg>/<l>`（偈颂）、`<table>/<row>/<cell>` 都落到 catch-all，换行与列结构丢失，偈颂会连成一行。`<p cb:type="pre">` 有专门处理（很好），但其它结构化元素没有。

**8. `<note>` 一律包 `（…）` 内联（第 209–211 行）** 夹注、校勘注不区分，且嵌套 note 可能双重包裹。属轻度问题。

## 三、内存与性能

**9. 全文件被重复整读 + 整篇正则扫描（`extract_article_notes`，第 315–357 行）— 主要瓶颈** 每提取一篇文章都：①按字节读片段；②`f.read()` 把**整个 900KB 文件**再读一遍；③对全文跑 `<back>.*?</back>` 的 DOTALL 正则。批量模式提取同一文件的 N 篇时，这步是 **O(N × 文件大小)**，且每篇重读重扫，无任何缓存。应当：每个文件只读一次 `<back>`，构建 `{anchor_id: note}` 映射缓存，按文件复用。

**10. byline 提取每篇重开文件（catalog 脚本第 30 行）** `extract_article_byline` 对每篇 `open()` 一次读 5000 字节；而 `scan_byte_offsets` 已把整文件读进内存（`read_bytes`）。可以复用同一个 `raw` 缓冲，省掉 N 次 open。

**11. 解析策略总体评价** "先查 JSON 偏移 → 只解析片段"的设计本身很好，避免了整树加载，对当前文件规模（<1MB）合理。**不需要**为这些文件换 `lxml` 或 `iterparse`——收益不抵复杂度。真正该优化的是上面 #9/#10 的重复 I/O，而非解析库。若未来要处理远大于内存的 XML，才考虑 `iterparse` + 事件流。

## 四、目录构建逻辑

**12. 两套 TOC 生成路径并存，易漂移** `walk_div_tree`（全文模式产 `toc_entries`）与 `build_toc_json_tree`（toc-only 产 JSON 树）各自实现了一遍"跳纲要 / level-1 透传 / 附录 offset / shift rule"逻辑（第 446–525 与 646–708 行）。两者必须手工保持同步，任何一边改了规则另一边就静默不一致。建议合并为"先建一棵语义树，再分别渲染 MD / JSON"，单一真相源。

**13. 链表用 `篇名` 字符串做校验** `prev`/`next` 存的是篇名（catalog 脚本第 235–238 行）。若同编出现重名文章，名称校验会歧义。`prev_index`/`next_index` 已经够用，名称仅作展示即可。

**14. `regenerate_catalog_md` 的 `zi_mu_map[zm]` 可能 KeyError（第 953 行）** 遍历的是 `子目` 数组里的名称，但若某子目在 `篇目鏈表` 中暂无文章（实验阶段很常见），`zi_mu_map[zm]` 直接 KeyError。应改 `zi_mu_map.get(zm, [])`。

## 五、其它漏洞与不健康项

**15. `--prefix` 触发 `NameError`（catalog 脚本，确定性 bug）** 第 284–299 行：`basename` 只在 `if args.prefix is None:` 分支里赋值，但第 299 行 `dashboard_path = out_dir / f'_{basename}_仪表盘.md'` 无条件使用它。用户一旦显式传 `--prefix`，`basename` 未定义 → `NameError` 崩溃。应在 if 外先 `basename = out_dir.name`。

**16. `Path.walk()` 需要 Python 3.12+（fulltext 第 1220、1357 行）** SKILL 明说 CX 沙箱"Python 受限"。`Path.walk()` 是 3.12 新增，旧环境 `AttributeError`。`os.walk` 更稳妥兼容。

**17. `parse_byline_fields` 在两个文件中重复且不一致** `extract_article_fulltext.py` 第 1076 行无月份时 `date = f"{year}-01"`；`add_frontmatter_to_existing.py` 第 41 行同情形 `date = year`。结果：新提取的文章 frontmatter 是 `date: 1930-01`，而迁移脚本补的是 `date: 1930`——同一批数据两套格式，Dataview 排序/筛选会不一致。应抽进 `_utils.py` 共用。

**18. 死代码 / 未用参数** `make_anchor_id`（第 94 行）按 SKILL 说明已不再生成锚点，整函数无人调用；`note_backrefs`、`heading_anchor` 参数层层透传却从未实质使用。建议清理，降低维护噪音。

**19. `extract_mulu.py` 与主管线割裂** 它用纯正则解析 `<cb:mulu>`（第 20–32 行），与主管线的 ET 解析两套实现；且 `e['text']` 不剥离内部标签，可能混入 `<lb/>`。作为独立调试工具尚可，但与项目"统一用 ET"的取向不符，容易给后来者错误示范。

**20. 异常处理只在 batch，单篇裸奔** batch 模式对每篇 try/except 并继续（第 1240 行），单篇/`--file` 模式完全没有保护。建议把单篇也包一层，至少给出可读错误而非栈回溯。

---

## 优先级建议

确定性 bug，应先修：**#15（`--prefix` NameError）**、**#14（KeyError）**、**#17（date 格式不一致）**。 鲁棒性投入产出最高：**#1（统一 `is None` 判定）**、**#2（字节扫描兜底 + 两套解析对齐校验）**。 性能：**#9（`<back>` 注释按文件缓存）** 是唯一真正的瓶颈，值得改;解析库无需更换。 可维护性：**#12（合并两套 TOC 逻辑）**、**#18（清死代码）**。 清洗完整性：**#6（`<g>` 缺字）** 若涉及律释/法相编需重视，**#5/#7** 视实际文本酌情。

---

以上是审查报告，请根据优先级，修复代码。