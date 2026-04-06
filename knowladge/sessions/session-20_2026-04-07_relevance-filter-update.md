# Session 20 — Relevance Filter Update (2026-04-07)

## Goal
Phase 2 Step 5: When `domains` is empty, derive filter keywords from `target_positions + skills`.

## Changes

### `job_hunter/jobs/relevance_filter.py`
- `_get_irrelevant_keywords()`: Now uses `_get_relevant_keywords()` (which includes domains + target_positions + skills + synonyms) instead of only `domains` to exclude professional fields. This means a user with "marketing" in target_positions won't have marketing jobs incorrectly rejected.
- `_get_irrelevant_companies()`: Same fix — uses full relevant keywords set instead of only domains.

### `job_hunter/profile.py`
- Validation: Changed "No domain keywords" warning to only trigger when ALL of domains, target_positions, and skills are empty. Previously warned whenever domains was empty even if target_positions/skills compensated.

### `tests/test_relevance_filter.py`
- Fixed 2 pre-existing failing tests (`test_accept_rf_engineer`, `test_accept_machine_learning_researcher`) — they relied on the live profile having RF/ML keywords. Now use monkeypatched profiles.
- Added `TestEmptyDomains` class with 5 tests:
  - Accept by target_position keyword
  - Accept by skill keyword
  - Accept by synonym expansion
  - Reject unrelated title
  - Professional field not excluded when in target_positions

### `tests/test_profile_cli.py`
- Updated `test_validate_warns_missing_domains` to match new validation logic (must clear all three fields to trigger warning).

## Test Results
202 passed, 0 failed.
