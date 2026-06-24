import pathlib
p = pathlib.Path("/Users/xin/.codex/memories/MEMORY.md")
content = p.read_text(encoding="utf-8")

# Add Task 12 and 13 after Task 11
old = "- get_byline_text, byline, 題注, 篇末附注, TX01n0001, 性釋, end-of-article annotation, Python inline replacement

## User preferences"

new_task12 = """- get_byline_text, byline, 題注, 篇末附注, TX01n0001, 性釋, end-of-article annotation, Python inline replacement

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
content = content.replace(old, new_task12)
p.write_text(content, encoding="utf-8")
print("EDIT 1: Tasks 12 and 13 added")