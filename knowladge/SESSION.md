# Session State

## Last Session (2026-03-26)
**Completed:** requirements.txt fixed (requests, bs4, python-jobspy added; weasyprint removed); Chrome PDF confirmed; irrelevant keyword list expanded; JobSpy results set to 50; LinkedIn+JobSpy scrapers both enabled
**Commits:** 788273b, 614f03e, bd64518, b29ae63, 2258dcb, 1bf2edd, 266f454

## Current Status
Priority 1 bugs remaining:
- [ ] `tracker.py:43` — replace silent `pass` with error log on malformed records
- [ ] `scraper.py` `JobSpyScraper.search()` — honor `max_results` param (currently hardcoded 50)
- [ ] `hunter.py` — add `HUNTER_API_KEY` to `.env.example`
- [ ] `logger.py` — use `Config.DATA_DIR` instead of hardcoded `"data/logs"`

Priority 2 (next after bugs):
- 10 unit tests across relevance_filter, models, tracker, scraper, cv/adapter

## Next Session
**Goal:** Priority 1 remaining bugs (4 small fixes across 4 files)
**Start message:** "Working on job-hunter. Read `knowladge/SESSION.md`. Tell me: last completed, current status, next task."

## Session End Checklist
- [ ] Update "Last Session" section with what was done + commit hashes
- [ ] Advance "Next Session" goal to next priority item
- [ ] Check off completed items in CLAUDE.md roadmap
- [ ] Commit: `git add knowladge/SESSION.md CLAUDE.md && git commit -m "session: [what was done]" && git push origin master`
