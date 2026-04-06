# Session 18 — Profile CLI (show/edit/validate + --profile-path)

**Date:** 2026-04-07
**Goal:** Phase 2 Step 6 continued — `profile show/edit/validate`, `--profile-path` flag on all commands

## What was done

### --profile-path flag
- Added `--profile-path` option to top-level `cli()` group
- Added `set_profile_path()` + `_resolve_path()` in `profile.py` for module-level override
- All commands automatically use the override when set

### profile show
- Rich Panel with sections: Contact, Education, Experience Level, Skills, Target Positions, Domains, Watchlist, Hard Rules
- Empty sections are skipped

### profile validate
- Runs existing `UserProfile.validate()`
- Errors printed red, warnings yellow
- Exit code 1 on errors, 0 otherwise

### profile edit
- Interactive numbered menu for 11 editable fields
- Supports string and list (comma-separated) fields
- Saves after each edit, offers to edit another field

### Tests
- 17 new tests in `tests/test_profile_cli.py`
- Covers show (6), validate (5), edit (4), --profile-path (2)
- All pass; full suite 190/192 (2 pre-existing failures in relevance_filter)

## Files changed
- `job_hunter/cli.py` — profile show/edit/validate commands + --profile-path
- `job_hunter/profile.py` — set_profile_path, _resolve_path helpers
- `tests/test_profile_cli.py` — new test file (17 tests)

## Phase 2 status after this session
- Steps 1-3, 6: DONE
- Steps 4, 5, 7, 8: TODO
