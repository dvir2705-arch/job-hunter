# Session 21 — Company CLI (Phase 2 Step 7)
**Date:** 2026-04-07

## Goal
Implement `jobs companies` command group: list, add, remove, suggest.

## What was done
1. Added `companies` CLI group to `cli.py` with 4 subcommands:
   - `companies list` — shows watchlist with registry info (domains, scraper availability)
   - `companies add <names...>` — adds companies to watchlist, deduplication by case-insensitive match
   - `companies remove <names...>` — removes companies, case-insensitive matching
   - `companies suggest` — calls `suggest_companies()` via Haiku, shows results, confirms additions, allows removals
2. All commands use `@require_profile` guard
3. Created `tests/test_companies_cli.py` with 17 tests covering all commands

## Also done in this session
- Created multi-session plan for Phase 2 completion + multi-user readiness (see `.claude/plans/`)
- Explored all blockers for new user onboarding

## Tests
- 17 new tests in `test_companies_cli.py`
- All 219 tests pass

## Files changed
- `job_hunter/cli.py` — added companies group (list/add/remove/suggest)
- `tests/test_companies_cli.py` — new test file
- `CLAUDE.md` — checked off Company CLI in roadmap
