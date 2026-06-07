# Session 27: 2026-04-09 — Multi-Profile System

## What was done
- Created `profile_manager.py` module with all multi-profile operations: slugify, list_profiles, get/set_active_profile, profile_exists, delete_profile, has_legacy_profile, migrate_legacy_profile
- Updated `config.py`: `set_user()` now invalidates cached profile to prevent stale data after switching
- Updated CLI startup (`cli()` group): auto-reads `.active_profile` on startup, triggers legacy migration if needed. Priority: `--user` flag > `JOB_HUNTER_USER` env > `.active_profile` > legacy single-user
- Updated `init` command: asks for profile name (slug), saves under `data/users/<slug>/`, sets as active. Shows existing profiles. `--name` flag to skip prompt.
- Added 4 new profile management CLI commands: `profile list`, `profile current`, `profile switch <name>`, `profile delete <name>`
- Updated existing test fixtures (onboarding, profile_cli, companies_cli) to prevent auto-migration in isolated tests
- 334 total tests passing (50 new tests added)

## Files changed
- `job_hunter/profile_manager.py` — NEW: multi-profile management module
- `job_hunter/config.py` — set_user() cache invalidation
- `job_hunter/cli.py` — auto-activate, init profile name, 4 new commands
- `tests/test_profile_manager.py` — NEW: 32 unit tests
- `tests/test_multi_profile_cli.py` — NEW: 18 CLI tests
- `tests/test_onboarding.py` — updated for new init flow
- `tests/test_profile_cli.py` — updated fixture
- `tests/test_companies_cli.py` — updated fixture

## Commits
- (pending — will be committed at session end)

## Key decisions
- Profiles = users: a profile maps 1:1 to Config.set_user() user ID, reusing existing B3 isolation infrastructure
- Active profile stored in `data/.active_profile` (single-line text file)
- Legacy migration: existing `data/user_profile.json` auto-migrates to `data/users/default/` on first CLI run
- Profile names slugified: lowercase, hyphens, `[a-z0-9-]` only
- `companies.json` stays shared at root `data/jobs/` level (not per-user)
- `--name` CLI flag on init to skip interactive profile name prompt

## Notes
- Dvir's existing data will auto-migrate on next CLI run — no manual action needed
- Output dir (PDFs) remains global — could be per-user later if needed
- The `--profile-path` flag from the original roadmap is superseded by the `--user` flag + profile system
