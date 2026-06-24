import pathlib
import sys

p = pathlib.Path("/Users/xin/.codex/memories/MEMORY.md")
content = p.read_text(encoding="utf-8")

# EDIT 1: Add Task 12 and Task 13 after Task 11
old = "- get_byline_text, byline, 题注, 篇末附注, TX01n0001, 性释, end-of-article annotation, Python inline replacement

## User preferences"

new = """- get_byline_text, byline, 题注, 篇末附注, TX01n0001, 性释, end-of-article annotation, Python inline replacement

## Task 12: Fix heading level cap (### should not exceed H6)

### rollout_summary_files

- <rollout_summaries/2026-06-22T00-30-32-SaOk-fix_cbeta_heading_level_cap.md> (cwd=/Users/xin/Documents/Road_Of_Taixu, updated_at=2026-06-22T00:36:46+00:00, thread_id=019eecbc-6e64-7360-ad57-002338418e98, fixed walk_div_tree heading_level to cap at ######)

### keywords

- heading_level, walk_div_tree, mulu_lv, H6, extract_article_fulltext.py, ######, #######, apply_patch format, --out-dir

## Task 13: Batch extract first 8 articles using --batch mode (概述 articles via catalog range)

### rollout_summary_files

- <rollout_summaries/2026-06-22T01-59-16-jIW1-cbeta_xml_reader_batch_extract_first_8_articles.md> (cwd=/Users/xin/Documents/Road_Of_Taixu, updated_at=2026-06-22T02:00:28+00:00, thread_id=019eed0d-aa12-7601-9063-527d73a82b55, batch extracted 概述 #1-8)

### keywords

- --batch, 概述, --from, --to, TX01n0001, batch mode, first 8 articles, 佛法总学 概述

## User preferences"""

assert old in content, "EDIT 1 failed"
content = content.replace(old, new)

# EDIT 2: Add user pref for Task 12, 13
old2 = "investigate root cause before editing code [Task 11]"
new2 = old2 + """ [Task 11]
- when the user found non-standard headings (#######), they said: "找一找原因" before requesting a fix -> when observing unexpected output, first diagnose and explain root cause, then propose fix [Task 12]
- when the user gave instructions with skill reference syntax "[skill-name](SKILL.md)" and "提取第一编，第一到第八篇文章" -> the user expects direct execution using the project existing toolchain, no preliminary discussion or solution design [Task 13]"""
assert old2 in content, "EDIT 2 failed"
content = content.replace(old2, new2)

# EDIT 3: Add reusable knowledge
old3 = "- Byline placement rule in get_byline_text(): if a <p> is found before any <byline> among direct children of <div>, the byline is an end-of-article annotation (leave for extract_paragraphs()), not a title annotation. Only bylines before all <p> children should be treated as 题注 [Task 11]"
new3 = old3 + """
- Heading level cap in walk_div_tree(): use min(6, max(floor, effective_lv)) to cap at H6. Location: extract_article_fulltext.py line 480 (after fix). Verify with rg -n of caret followed by 6 hashes (should return empty) [Task 12]
- Batch extraction command pattern: python3 extract_article_fulltext.py --batch --catalog <catalog.json> --zi_mu <zi_mu_name> --from <N> --to <M> --data-dir <data_dir> [Task 10][Task 13]
- Output directory for extracted articles: _research/<bian_subdir>/<zi_mu_num:02d>_<zi_mu>/ with files named number_name.md. The script auto-updates catalog JSON word counts and Markdown catalog. First 8 articles are all in file TX01n0001.xml under zi_mu 概述 [Task 13]"""
assert old3 in content, "EDIT 3 failed"
content = content.replace(old3, new3)

# EDIT 4: Add failure shields
old4 = "- apply_patch failures due to context line mismatch: when patching Python files, prefer inline Python replacement (open() + write()) over apply_patch or sed to avoid encoding and context-line issues [Task 11]"
new4 = old4 + """
- apply_patch format: must start with "*** Begin Patch", end with "*** End Patch", use -/+ for deleted/added lines, context lines must match exactly (including whitespace). For simple template text replacements (s/str1/str2/g), prefer sed or Python string replace over apply_patch [Task 2][Task 12]
- extract_article_fulltext.py uses --out-dir not --output. Always check --help before guessing parameter names when running a script for the first time [Task 12]"""
assert old4 in content, "EDIT 4 failed"
content = content.replace(old4, new4)

# EDIT 5: Add Task 2b in cbeta-toolchain-extraction
old5 = "- KeyError, bian_name, book_name, template variable, rename, sed, template naming consistency

## Task 3: Skill health check and documentation fix (second round)"
new5 = """- KeyError, bian_name, book_name, template variable, rename, sed, template naming consistency

## Task 2b: Unify --bian to --book parameter naming and rename script file

### rollout_summary_files

- <rollout_summaries/2026-06-21T21-48-26-Za3g-cbeta_book_catalog_unify_bian_to_book_parameter_naming.md> (cwd=/Users/xin/Documents/Road_Of_Taixu, updated_at=2026-06-21T21:57:30+00:00, thread_id=019eec28-05ab-7501-bcff-e7716e1493ca, unified --bian/--bian-num to --book/--book-num in script and renamed extract_bian_catalog.py to extract_book_catalog.py)

### keywords

- --bian, --book, parameter naming, extract_bian_catalog, extract_book_catalog, script rename, naming consistency, content.replace, Python replacement workaround

## Task 3: Skill health check and documentation fix (second round)"""
assert old5 in content, "EDIT 5 failed"
content = content.replace(old5, new5)

# EDIT 6: Add user pref for Task 2b
old6 = "- when the user said: "模板名中的 bian 也改成 book 吧" -> naming consistency: use the English term "book" (not the Chinese transliteration "bian") for file names referring to 编 [Task 2]"
new6 = old6 + """
- when the agent first updated SKILL.md to match the script --bian parameter, then the user said: "统一一下吧，skill 和脚本里，都讲 bian 统一成 book 吧" -> the user prefers Chinese-meaningful English argument names (book for 编) over pinyin transliteration (bian), and wants all documentation and code to use consistent naming [Task 2b]
- when the agent asked whether to rename the script file too, the user said: "文件名也改吧" -> the user wants complete consistency: file names, parameter names, and all inline references should use the same naming convention [Task 2b]"""
assert old6 in content, "EDIT 6 failed"
content = content.replace(old6, new6)

# EDIT 7: Add reusable knowledge for Task 2b (prepend to existing Template file path convention line)
old7 = "- Template file path convention: scripts/cbeta-xml-reader/templates/bian_dashboard.md (now book_dashboard.md). Script locates via Path(__file__).parent.parent / 'templates' / 'book_dashboard.md' [Task 1][Task 2]"
new7 = "- User prefers --book/--book-num over --bian/--bian-num. The script at scripts/cbeta-xml-reader/scripts/extract_book_catalog.py uses --book and --book-num. SKILL.md has 4 reference occurrences (lines ~242, 246, 618, 726). _utils.py has one comment reference [Task 2b]
- " + old7[2:]
assert old7 in content, "EDIT 7 failed"
content = content.replace(old7, new7)

# EDIT 8: Update health check finding to note historical context
old8 = "- Health check cross-check findings: SKILL.md referenced extract_book_catalog.py (wrong name -- actual file is extract_bian_catalog.py); SKILL.md progress table was stale; requirements.md R7b contradicted actual implementation [Task 3]"
new8 = "- Health check cross-check findings (historical context, before script was renamed): SKILL.md referenced extract_book_catalog.py (wrong name at the time -- actual file was extract_bian_catalog.py); SKILL.md progress table was stale; requirements.md R7b contradicted actual implementation [Task 3]"
if old8 in content:
    content = content.replace(old8, new8)
    print("EDIT 8 applied")
else:
    print("EDIT 8: not found")

# EDIT 9: Fix stale --bian references in reusable knowledge sections
# Task 6 line
old9a = "- First bian catalog extraction command: python3 extract_bian_catalog.py <xml1> <xml2> --bian "<编名>" --bian-num <N> [Task 6]"
# The actual content might be slightly different
for line in content.split(chr(10)):
    if "extract_bian_catalog.py" in line and "extraction command" in line:
        print(f"Found stale ref: [{line}]")

# Write file
p.write_text(content, encoding="utf-8")
print("All edits done")
