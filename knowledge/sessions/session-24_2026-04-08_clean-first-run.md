# Session 24 — Clean First-Run Experience (B4)
**Date:** 2026-04-08
**Goal:** Make the first-run experience clean for new users

## What was done
1. **Input validation in init wizard** — Name, email, target roles now required (retry on empty). Phone labeled as optional.
2. **Profile summary before saving** — Rich Panel shows all fields; user confirms before save. Abort returns cleanly.
3. **API key warning** — If ANTHROPIC_API_KEY missing during init, yellow warning explains why company suggestions are skipped. Also fixed vague cv init error message.
4. **Post-init guidance** — Replaced single-line "try cv init" with 3-step checklist (cv init, profile show, jobs scan). API key tip shown if missing. Also improved post-cv-init guidance.
5. **B3 test fix** — Fixed pre-existing test_two_users_get_separate_tracker_files: was setting Config.DATA_DIR instead of Config._BASE_DATA_DIR.

## Files changed
- `job_hunter/cli.py` — init command: validation, summary panel, API key check, guidance
- `tests/test_onboarding.py` — 10 new tests (38 total), 6 existing updated for save confirm
- `tests/test_data_isolation.py` — 1-line fix for _BASE_DATA_DIR
- `CLAUDE.md` — Added Priority 6 (CLI test coverage gaps)

## Tests
- 280 total, 280 passing
- New: TestInitValidation (4), TestInitSummary (2), TestInitApiKeyWarning (2), TestInitGuidance (2)

## Also done (pre-session)
- CLI command audit: 28 commands across 7 groups, identified 3 groups without CLI tests (cv, apps, recruiters)
- Added Priority 6 test coverage gaps to CLAUDE.md roadmap
- Added Job Analysis module to "Still Pending"
