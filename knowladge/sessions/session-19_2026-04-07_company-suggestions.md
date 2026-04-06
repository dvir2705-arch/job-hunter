# Session 19 — Company Suggestions via Haiku

**Date:** 2026-04-07
**Goal:** Phase 2 Step 4 — Company suggestions via Haiku

## What was done
- Added `suggest_companies(profile)` to `search_strategy.py`
  - Sends user profile + full companies.json registry (with domain tags) to Haiku
  - Two-tier response: registry picks (scrapeable) + additional companies (general search)
  - Validates registry names against companies.json (drops hallucinated names)
  - Fallback on API failure: returns all priority companies from registry
- Integrated into `jobs init` wizard (cli.py)
  - Shows two tiers after profile creation: "Companies we can scan" and "Also relevant"
  - User confirms with y/n, can remove specific companies by name
  - Saves to `profile.watchlist`
- Created `tests/test_company_suggestions.py` (5 tests)
  - Valid response parsing, invalid name filtering, markdown fence handling, API failure fallback, empty profile
- Fixed `tests/test_onboarding.py` — mocked `suggest_companies` in `tmp_data_dir` fixture

## Files changed
- `job_hunter/jobs/search_strategy.py` — `suggest_companies()`, `_fallback_company_suggestions()`, `_COMPANY_SUGGESTION_PROMPT`
- `job_hunter/cli.py` — company suggestion flow in `init` command
- `tests/test_company_suggestions.py` — new file, 5 tests
- `tests/test_onboarding.py` — mock added to fixture

## Tests
- 5/5 new tests pass
- 170/170 total tests pass (excluding pre-existing relevance filter failures)

## Commit
`aa8ca71` — company suggestions: Haiku-driven two-tier company suggestions in init wizard
