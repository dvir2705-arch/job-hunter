# Session State

## Last Session (2026-03-26)
**Completed:** Analysis only — deep dive into relevance_filter.py: explained Layer 1 (title/company keyword filtering, uncertain bucket) and Layer 2 (description fetch + JobAnalyzer/Claude API, domain + skill overlap checks, benefit-of-doubt logic). No code written.
**Commits:** (none this session)

## Current Status
Priority 1 bugs: all done ✓
Priority 2 tests: all done ✓

Priority 3 (next):
- Centralize user data: UserProfile dataclass + refactor hardcoded personal data out of 5 files

## Next Session
**Goal:** Priority 3 — create UserProfile dataclass and refactor hardcoded personal data (cover_letter/generator.py, cv/adapter.py, cli.py, relevance_filter.py)
**Start message:** "Working on job-hunter. Read `knowladge/SESSION.md`. Tell me: last completed, current status, next task."

## Session End Checklist
- [ ] Update "Last Session" section with what was done + commit hashes
- [ ] Advance "Next Session" goal to next priority item
- [ ] Check off completed items in CLAUDE.md roadmap
- [ ] Commit: `git add knowladge/SESSION.md CLAUDE.md && git commit -m "session: [what was done]" && git push origin master`
