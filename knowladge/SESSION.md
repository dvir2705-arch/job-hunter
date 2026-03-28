# Session State

## Last Session (2026-03-28)
**Completed:** Improved relevance filter to block irrelevant jobs. Added 24 new keywords to PROFESSIONAL_FIELDS (writer, writing, editor, teaching, nursing, retail, etc.). Changed uncertain jobs to always AI-score with Haiku instead of auto-accepting. Removed --deep flag (now automatic). On AI failure → accept with warning. All 66 tests passing.
**Commits:** (see git log)

## Current Status
Priority 1 bugs: all done ✓
Priority 2 tests: all done ✓
Relevance filter: AI-enhanced + expanded keywords ✓
Priority 3 centralize user data: all done ✓
Priority 4 onboarding flow: all done ✓
Multi-profile generalization: done ✓

Priority 5 (remaining):
- Cross-platform browser/clipboard, retry logic, cover letter critique loop, job analytics, Hebrew cover letter

## Next Session
**Goal:** Priority 5 — new features (start with cross-platform browser/clipboard: replace Windows-only `clip`/`explorer` with `pyperclip`/`webbrowser`)
**Start message:** "Working on job-hunter at C:\Users\dvir2\job-hunter. Read CLAUDE.md."

## Session End Checklist
- [ ] Update "Last Session" section with what was done + commit hashes
- [ ] Advance "Next Session" goal to next priority item
- [ ] Check off completed items in CLAUDE.md roadmap
- [ ] Commit: `git add knowladge/SESSION.md CLAUDE.md && git commit -m "session: [what was done]" && git push origin master`
