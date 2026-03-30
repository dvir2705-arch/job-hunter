# Session State

## Last Session (2026-03-30)
**Completed:** Performance optimization + filter optimization (Changes B+D). Commits: e55b680, 8130d09.

1. **Perf fixes (e55b680):** Removed stagger delay, added 429 retry with backoff, bumped max_workers to 5, zero_streak cache logic (24h TTL after 3 empty results), fixed company search query.
2. **Filter optimization (8130d09):** Replaced 42 individual Haiku+description calls with 1-2 batch title-only calls. Expanded keyword accept list from profile (target_positions + skills + TITLE_SYNONYMS). On-demand description fetch in job menu. Filter time: 172s → 6s, uncertain: 42 → ~15. Tests updated for batch Haiku flow.
3. 141 tests passing (3 pre-existing failures: RF Engineer, ML Researcher, `-j` flag).

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
