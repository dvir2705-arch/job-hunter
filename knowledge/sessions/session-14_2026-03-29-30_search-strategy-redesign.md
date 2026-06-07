# Session 14 — 2026-03-29/30 — Search Strategy Redesign

## What was done
- Profile-driven search strategy: generates queries from UserProfile fields
- Parallel scanning with ThreadPoolExecutor (max_workers=5)
- Haiku-generated search queries from profile
- Per-source cache with 90min TTL
- Progressive CLI output during scan
- Wired parallel_scan into `jobs scan`
- Made seniority_reject configurable from SearchConfig
- All backward compatible; 77 tests passing

## Key commits
- `c8bdc02` search: add profile-driven search strategy, scan cache, and parallel execution
- `e26e28d` cli: wire parallel_scan into jobs scan with progressive output
- `a7f0887` filter: make seniority_reject configurable from SearchConfig
- `0172c8d` session: search strategy redesign (steps 1-6 complete)
