# Session 23 — B3: Per-User Data Isolation
**Date:** 2026-04-08

## Goal
Multi-user readiness B3 — centralize all data paths and add per-user directory support.

## What was done

### Centralized all paths in Config
Added 9 new path constants to `Config`:
- `JOBS_DIR`, `COMPANIES_FILE`, `DISCOVERED_COMPANIES_FILE`
- `SCAN_HISTORY_FILE`, `SCAN_CACHE_FILE`
- `COVER_LETTER_DATA_DIR`, `COVER_LETTER_HISTORY_FILE`
- `RECRUITERS_FILE`, `LOG_DIR`
- `_BASE_DATA_DIR` — root data dir, used for shared registries

### Fixed 8 hardcoded paths across 6 modules
| Module | Was | Now |
|--------|-----|-----|
| `cover_letter/history.py` | `Path("data/cover_letters")` | `Config.COVER_LETTER_DATA_DIR` |
| `cover_letter/history.py` | `Path("output/cover_letters")` | `Config.COVER_LETTER_OUTPUT_DIR` |
| `jobs/discovery.py` | `Path("data/jobs/discovered_companies.json")` | `Config.DISCOVERED_COMPANIES_FILE` |
| `jobs/discovery.py` | `Path("data/jobs/companies.json")` | `Config.companies_file()` |
| `jobs/history.py` | `Path("data/jobs/scan_history.json")` | `Config.SCAN_HISTORY_FILE` |
| `jobs/scan_cache.py` | `Config.DATA_DIR / "jobs" / "scan_cache.json"` | `Config.SCAN_CACHE_FILE` |
| `jobs/scraper.py` | `Config.DATA_DIR / "jobs" / "companies.json"` | `Config.companies_file()` |
| `jobs/search_strategy.py` | `Config.DATA_DIR / "jobs" / "companies.json"` | `Config.companies_file()` |
| `recruiters/manager.py` | `Path("data/recruiters/recruiters.json")` | `Config.RECRUITERS_FILE` |
| `logger.py` | `os.getenv("DATA_DIR") / "logs"` | `Config.LOG_DIR` |
| `cli.py:1161` | `Path("data/jobs/companies.json")` | `Config.companies_file()` |

### Added per-user isolation support
- `Config.set_user(user_id)` — rebases `DATA_DIR` to `data/users/<id>/`, recalculates all derived paths
- `Config.companies_file()` — always returns shared registry path from `_BASE_DATA_DIR`
- `--user` CLI flag + `JOB_HUNTER_USER` env var
- Backward compatible: no `--user` = single-user mode (unchanged behavior)

### Tests
- 24 new tests in `test_data_isolation.py`:
  - `TestSetUser` (11): path recalculation, active user tracking, shared registry stays global
  - `TestBackwardCompat` (4): default paths unchanged
  - `TestModulesUseConfig` (7): every module reads from Config, not hardcoded
  - `TestEnsureDirs` (1): user directory creation
  - `TestEndToEnd` (1): two users get separate tracker files
- Updated 4 existing test fixtures to patch `_BASE_DATA_DIR`
- All 270 tests pass

## Files changed
- `job_hunter/config.py` — new path constants, `set_user()`, `_recalculate_paths()`, `companies_file()`
- `job_hunter/cli.py` — `--user` flag, fixed hardcoded path
- `job_hunter/cover_letter/history.py` — use Config paths
- `job_hunter/jobs/discovery.py` — use Config paths
- `job_hunter/jobs/history.py` — use Config paths
- `job_hunter/jobs/scan_cache.py` — use Config constant
- `job_hunter/jobs/scraper.py` — use `Config.companies_file()`
- `job_hunter/jobs/search_strategy.py` — use `Config.companies_file()`
- `job_hunter/logger.py` — use Config paths
- `job_hunter/recruiters/manager.py` — use Config paths
- `tests/test_data_isolation.py` — new (24 tests)
- `tests/test_companies_cli.py` — patch `_BASE_DATA_DIR`
- `tests/test_integration.py` — patch `_BASE_DATA_DIR`
- `tests/test_onboarding.py` — patch `_BASE_DATA_DIR`
- `tests/test_profile_cli.py` — patch `_BASE_DATA_DIR`
