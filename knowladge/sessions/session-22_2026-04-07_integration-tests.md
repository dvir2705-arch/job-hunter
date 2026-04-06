# Session 22 — Integration Tests + API Key Validation
**Date:** 2026-04-07

## Goal
Phase 2 Step 8 (integration tests) + B2 (API key validation).

## What was done

### B2: API key validation
Added `Config.validate()` at the start of 3 commands that use Claude:
- `jobs scan` — validates before scraping starts
- `jobs refresh-queries` — validates before query generation
- `jobs discover` — validates before discovery

Prevents "scan for 2 minutes then crash" experience.

### Step 8: Integration tests
Created `tests/test_integration.py` with 27 tests across 4 user profiles:
- **CS student** (Yael) — no experience, 2nd year CS at TAU, domains=[]
- **Backend developer** (Amit) — 3-7 years, Python/Node, Docker/AWS
- **Data scientist** (Noa) — 1-3 years, TensorFlow/PyTorch
- **Dvir** — existing profile, EE student

Test coverage:
- Profile save/load round-trip (4 profiles)
- Validation passes for all profiles (4 profiles)
- Search config build with correct seniority/scrapers (4 profiles + 4 specific)
- Relevance filter keyword derivation (5 tests including empty profile)
- API key validation (3 commands)
- Cross-profile consistency (is_student, watchlist→companies)

## Tests
- 27 new tests in `test_integration.py`
- All 246 tests pass

## Files changed
- `job_hunter/cli.py` — added Config.validate() to scan/refresh-queries/discover
- `tests/test_integration.py` — new integration test file
- `CLAUDE.md` — checked off Step 8
