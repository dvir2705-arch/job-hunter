# Session 28 — Bilingual CV Adaptation (English + Hebrew)

**Date:** 2026-04-09
**Status:** Completed

## What was done

Fixed two root causes that made adapted CVs broken/sparse for non-Dvir users (specifically Ben's Hebrew CV):

### 1. Schema Normalization (`parser.py`, `manager.py`)
- Added `normalize_cv_schema()` function that maps field aliases to canonical names expected by the template
- Experience: `title`→`position`, `start_date`→`start`, `end_date`→`end`, `description`(string)→`highlights`(list)
- Education: builds `year` from `start_date`/`end_date` if missing
- Military: `title`→`role`, `company`→`unit`, builds `period` from dates
- Volunteering: similar alias mapping
- Called at parse time (new CVs) and at load time in `manager.py` (fixes existing CVs without re-import)
- Idempotent — Dvir's CV passes through unchanged
- Updated Claude prompt in `_structure_cv_with_claude()` to request canonical field names

### 2. Adapter Language Support (`adapter.py`)
- Added `lang` parameter to `adapt()`, `adapt_with_requirements()`, and `_build_system_prompt()`
- Language instruction blocks: English tells Claude to translate from Hebrew if needed, Hebrew tells Claude to write all values in Hebrew
- Added `detect_cv_language()` helper — checks Hebrew character ratio in summary+name
- `ensure_ascii=False` in JSON dumps so Hebrew text is readable in prompts

### 3. Template RTL + Hebrew Section Titles (`modern.html`, `renderer.py`)
- Template now supports `lang` variable: `<html lang="{{ lang }}" dir="{{ dir }}">`
- RTL direction and right-aligned text for Hebrew
- Hebrew section titles (תקציר, ניסיון תעסוקתי, השכלה, כישורים, etc.)
- `SECTION_TITLES` dict defined in `renderer.py`
- Added `lang` parameter to `render_html()`, `render_pdf()`, `render_html_file()`
- Hebrew font fallback ('David') added to font-family

### 4. CLI `--lang` Option (`cli.py`)
- Added `--lang en|he` to `cv adapt` and `cv render` commands
- Auto-detects language from base CV if not specified
- Also updated the `jobs apply` CV adapt flow to auto-detect language

## Tests
- 25 new tests in `tests/test_cv_bilingual.py`
- Schema normalization: 15 tests (including Ben's actual schema, idempotency, edge cases)
- Language detection: 4 tests
- Adapter prompt: 2 tests
- Template rendering: 4 tests (LTR/RTL, section titles, defaults)
- Full suite: 281+ 25 = 306 passing (11 pre-existing failures unrelated to this session)

## Files Modified
- `job_hunter/cv/parser.py` — `normalize_cv_schema()` + helper functions + prompt update
- `job_hunter/cv/manager.py` — normalize on `load_base()`
- `job_hunter/cv/adapter.py` — `lang` param + `detect_cv_language()` + language prompts
- `job_hunter/cv/renderer.py` — `lang` param + `SECTION_TITLES`
- `templates/cv/modern.html` — RTL + dynamic section titles + font fallback
- `job_hunter/cli.py` — `--lang` option on `cv adapt` and `cv render`
- `tests/test_cv_bilingual.py` — 25 new tests
