# Session State

## Last Session (2026-03-28)
**Completed:** Company-targeted JobSpy search. Added Microsoft, Google, Meta to companies.json (now 30 companies). Added `priority` field (12 priority companies). Default `jobs scan` now runs regular sources + priority company search combined and deduplicated. `--no-companies` for fast scan, `--companies-all` for all 30. Fixed Unicode crash on Windows cp1255 console.
**Commits:** a189fd3, ac6e0bd, 5307902, e009f4a

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
