# Session State

## Last Session (2026-03-26)
**Completed:** Priority 3 — centralized user data. Created `data/user_profile.json` + `job_hunter/profile.py` (UserProfile dataclass). Refactored hardcoded personal data out of 5 files: cover_letter/generator.py, cv/adapter.py, cli.py, relevance_filter.py (keywords + fit score prompt). All 45 tests passing.
**Commits:** (this session's commit)

## Current Status
Priority 1 bugs: all done ✓
Priority 2 tests: all done ✓
Relevance filter: AI-enhanced ✓
Priority 3 centralize user data: all done ✓

Priority 4 (next):
- Onboarding flow: `job-hunter init` command, CV upload path, guard all commands

## Next Session
**Goal:** Priority 4 — onboarding flow (`job-hunter init` command: 6-question setup → writes user_profile.json, CV upload path, guard commands if profile not initialized)
**Start message:** "Working on job-hunter. Read `knowladge/SESSION.md`. Tell me: last completed, current status, next task."

## Session End Checklist
- [ ] Update "Last Session" section with what was done + commit hashes
- [ ] Advance "Next Session" goal to next priority item
- [ ] Check off completed items in CLAUDE.md roadmap
- [ ] Commit: `git add knowladge/SESSION.md CLAUDE.md && git commit -m "session: [what was done]" && git push origin master`
