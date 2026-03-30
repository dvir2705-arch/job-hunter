# Session State

## Last Session (2026-03-30)
**Completed:** Search Strategy Redesign — full build order steps 1-6. Commits: c8bdc02, e26e28d, a7f0887.

1. `search_strategy.py`: SearchConfig dataclass, Haiku query generation with fallback, cached queries in profile, enabled_scrapers derived from company watchlist, configurable max_workers (default 3).
2. `scan_cache.py`: per-source JSON cache with configurable TTL (90 min default), atomic writes, corruption recovery.
3. `scraper.py`: parallel_scan() with ThreadPoolExecutor, 0.5s stagger, cache integration, per-source error handling, progress callbacks. Existing scan()/company_scan() preserved.
4. `cli.py`: jobs scan default path uses build_search_config + parallel_scan with progressive output. --query bypasses to legacy path. --fresh clears cache. --no-companies/--companies-all still work. Added jobs refresh-queries command.
5. `relevance_filter.py`: seniority_reject configurable from SearchConfig (student: full list, experienced: reduced). Backward compatible default.
6. 77 new tests across 4 test files, all passing.

## Current Status
Priority 1-4: all done
Session A (profile redesign + docx parser): done
Search Strategy Redesign (steps 1-6): done

Phase 2 — New User Onboarding (approved plan in CLAUDE.md):
- Step 1: Schema + migration (experience_level, watchlist) — next
- Step 2: Watchlist-driven company loading
- Step 3: `jobs init` wizard (minimal)
- Step 4: Company suggestions via Haiku
- Step 5: Relevance filter update (derive from target_positions + skills)
- Step 6: Profile CLI (show/edit/validate, --profile-path)
- Step 7: Company CLI (list/add/remove/suggest)
- Step 8: Integration tests

Priority 5 (remaining):
- Cross-platform browser/clipboard, retry logic, cover letter critique loop, job analytics, Hebrew cover letter

## Next Session
**Goal:** Phase 2 Step 1 — Add `experience_level` + `watchlist` to UserProfile, update `search_strategy.py` to use `experience_level`, migrate Dvir's profile (copy priority companies to watchlist), tests.
**Start message:** "Working on job-hunter at C:\Users\dvir2\job-hunter. Read CLAUDE.md."

## Session End Checklist
- [x] Update "Last Session" section with what was done + commit hashes
- [x] Advance "Next Session" goal to next priority item
- [x] Check off completed items in CLAUDE.md roadmap
- [x] Commit: `git add knowladge/SESSION.md CLAUDE.md && git commit -m "session: [what was done]" && git push origin master`
