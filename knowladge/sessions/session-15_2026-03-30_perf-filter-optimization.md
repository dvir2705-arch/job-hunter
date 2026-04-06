# Session 15 — 2026-03-30 — Performance & Filter Optimization

## What was done
- Removed stagger delay, added 429 retry with exponential backoff
- Bumped max_workers to 5
- Zero_streak cache logic (24h TTL after 3 empty results)
- Fixed company search query
- Replaced 42 individual Haiku+description calls with 1-2 batch title-only calls
- Expanded keyword accept list from profile (target_positions + skills + TITLE_SYNONYMS)
- On-demand description fetch in job menu
- Filter time: 172s -> 6s, uncertain: 42 -> ~15
- Tests updated for batch Haiku flow

## Key commits
- `e55b680` perf: parallel scraping + filtering, zero_streak cache, company search fix
- `8130d09` filter: batch Haiku + profile-driven keywords, on-demand description fetch
- `9bc26ae` session: perf + filter optimization
