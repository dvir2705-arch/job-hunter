# Session State

## Last Session (2026-03-26)
**Completed:** AI-enhanced relevance filter — added seniority guard to Layer 1, replaced Layer 2 rule-based logic with AI fit scoring (score_job_fit, 0-100 scale, threshold 55). Updated session-end skill to auto-save summaries.
**Commits:** (this session's commit)

## Current Status
Priority 1 bugs: all done ✓
Priority 2 tests: all done ✓
Relevance filter: AI-enhanced (seniority guard + fit scoring) ✓

Priority 3 (next):
- Centralize user data: UserProfile dataclass + refactor hardcoded personal data out of 5 files

## Next Session
**Goal:** Priority 3 — create UserProfile dataclass and refactor hardcoded personal data (cover_letter/generator.py, cv/adapter.py, cli.py, relevance_filter.py, fit score prompt)
**Start message:** "Working on job-hunter. Read `knowladge/SESSION.md`. Tell me: last completed, current status, next task."

## Session End Checklist
- [ ] Update "Last Session" section with what was done + commit hashes
- [ ] Advance "Next Session" goal to next priority item
- [ ] Check off completed items in CLAUDE.md roadmap
- [ ] Commit: `git add knowladge/SESSION.md CLAUDE.md && git commit -m "session: [what was done]" && git push origin master`
