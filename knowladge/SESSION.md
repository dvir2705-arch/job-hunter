# Session State

## Last Session (2026-03-28)
**Completed:** CV template & adapt pipeline improvements. (1) Updated base_cv.json education to "3rd year". (2) Added one-page hard rule to CV adapter system prompt (both methods). (3) Optimized modern.html CSS for one-page fit: @page margins, tighter spacing, inline skills. (4) Fixed Chrome headless to use `--headless=new` so @page rules work. (5) Upgraded `cv adapt` CLI command: added `--url` and `--desc` flags, integrated JobAnalyzer (smart path), auto PDF render + diff generation. Removed old `--job-desc`/`--pdf`/`--cover-letter` flags.

## Current Status
Priority 1 bugs: all done ✓
Priority 2 tests: all done ✓
Relevance filter: AI-enhanced + expanded keywords ✓
Priority 3 centralize user data: all done ✓
Priority 4 onboarding flow: all done ✓
Multi-profile generalization: done ✓
Company-targeted search: done ✓

Priority 5 (remaining):
- Cross-platform browser/clipboard, retry logic, cover letter critique loop, job analytics, Hebrew cover letter

## Next Session
**Goal:** Priority 5 — new features (start with cross-platform browser/clipboard: replace Windows-only `clip`/`explorer` with `pyperclip`/`webbrowser`)
**Start message:** "Working on job-hunter at C:\Users\dvir2\job-hunter. Read CLAUDE.md."

## Session End Checklist
- [x] Update "Last Session" section with what was done + commit hashes
- [x] Advance "Next Session" goal to next priority item
- [x] Check off completed items in CLAUDE.md roadmap
- [x] Commit: `git add knowladge/SESSION.md CLAUDE.md && git commit -m "session: [what was done]" && git push origin master`
