# Session 17 — Profile Enrich + CV Skill Parsing (2026-04-06)

## Goal
Continue cut session: profile enrich command + fix CV skill parsing for categorized format.

## What was done
1. **Categorized CV skill parsing** — `init --from-cv` now handles `base_cv.json` format where skills are a dict (`{"programming": [...], "technical": [...]}`) instead of a flat list. Also extracts project technologies and deduplicates.
2. **`profile enrich` command** — New `job-hunter profile enrich` command that pulls missing skills from `base_cv.json` into the user profile. Clears cached search queries so they regenerate with the richer skill set.
3. **Test fix** — Fixed `test_cv_adapt_blocked_without_profile` which used removed `-j` flag (now `-u`).
4. **Tests added** — `test_init_from_cv_prefills_categorized_skills`, `TestProfileEnrich` (3 tests: adds skills, no duplicates, no CV error).

## Tests
28/28 passing in `test_onboarding.py`.

## Commits
- `33fd18e` profile: enrich command + categorized CV skill parsing

## Next
Phase 2 Step 6 continued — `profile show/edit/validate`, `--profile-path` flag on all commands.
