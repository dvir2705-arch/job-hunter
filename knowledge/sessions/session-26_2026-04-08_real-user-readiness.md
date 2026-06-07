# Session 26 — Real-User Testing Readiness

**Date:** 2026-04-08
**Goal:** Fix all crash paths and platform assumptions that would break for a non-Dvir user

## What was done

### N1. Cross-Platform Chrome Detection
- `cv/renderer.py`: Replaced Windows-only `_CHROME_PATHS` with platform-aware `_find_chrome()` that checks Windows, macOS, and Linux paths + `shutil.which()` fallback
- `cli.py`: Simplified `open_in_chrome()` to reuse `_find_chrome()` from renderer, eliminating duplicated Chrome detection logic

### N2. Cross-Platform Clipboard & File Explorer
- `cli.py:2091`: Replaced `subprocess.run(['clip'])` with `pyperclip.copy()` (already used elsewhere in same file)
- `cli.py:2097`: Replaced `subprocess.run(['explorer', ...])` with platform-aware open: `explorer` (Windows), `open -R` (macOS), `xdg-open` (Linux)
- Both wrapped in try/except with graceful fallback (prints path instead of crashing)

### N3. JSON Parse Crash Guard in CV Adapter
- `cv/adapter.py`: Added empty `message.content` guard + `json.JSONDecodeError` try/except in all 3 methods:
  - `adapt()` — returns None on empty content or invalid JSON
  - `adapt_with_requirements()` — same
  - `generate_cover_letter()` — returns None on empty content
- Added 4 new tests in `test_cv_adapter.py`: empty content (all 3 methods) + invalid JSON

### N4. Missing `@require_profile` Guards
- Added `@require_profile` decorator to 13 commands that were missing it:
  - CV: `cv_show`, `cv_list`
  - Apps: `apps_list`, `apps_update`, `apps_reset`, `apps_stats`, `apps_dashboard`
  - Recruiters: `recruiters_add`, `recruiters_list`, `recruiters_remove`, `recruiters_search`, `recruiters_find_emails`, `recruiters_scan_all`

### N5. README & .env.example Updates
- README: Added Prerequisites section (Python 3.11+, Chrome/Chromium), updated Quick Start to include `job-hunter init` step and docx import
- `.env.example`: Added commented `JOB_HUNTER_USER=` with explanation

## Files changed
- `job_hunter/cv/adapter.py` — empty content + JSON parse guards
- `job_hunter/cv/renderer.py` — cross-platform Chrome detection
- `job_hunter/cli.py` — cross-platform clipboard/explorer, @require_profile on 13 commands, simplified open_in_chrome
- `tests/test_cv_adapter.py` — 4 new tests
- `.env.example` — JOB_HUNTER_USER documentation
- `README.md` — Prerequisites + updated Quick Start
- `CLAUDE.md` — checked off cross-platform item

## Tests
284 passed (was 280, added 4 new)

## Roadmap updated
- [x] Cross-platform browser/clipboard (Priority 5)
