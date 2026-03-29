# Session State

## Last Session (2026-03-29)
**Completed:** Cover letter auto-PDF + output folder reorganization. (1) Created `templates/cover_letter/cover_letter.html` — clean letter template with sender info, date, paragraphs, closing; supports Hebrew RTL. (2) Added `render_cover_letter_pdf()` to `CVRenderer`. (3) Updated `_generate_cover_letter_for_job()` to auto-save TXT + PDF immediately after generation. (4) Reorganized output into `output/adapted_cv/` and `output/cover_letters/` subdirectories — updated all save paths, auto-detect in tracker, and .gitignore. Commits: 5a32f7a, 9abd137.

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
**Goal:** Priority 5 — new features (cross-platform browser/clipboard: replace Windows-only `clip`/`explorer` with `pyperclip`/`webbrowser`)
**Start message:** "Working on job-hunter at C:\Users\dvir2\job-hunter. Read CLAUDE.md."

## Session End Checklist
- [x] Update "Last Session" section with what was done + commit hashes
- [x] Advance "Next Session" goal to next priority item
- [x] Check off completed items in CLAUDE.md roadmap
- [x] Commit: `git add knowladge/SESSION.md CLAUDE.md && git commit -m "session: [what was done]" && git push origin master`
