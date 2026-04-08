# Session 25 — Remove hardcoded Dvir data (2026-04-08)

## Goal
Multi-user readiness B5 — Remove all hardcoded personal data from generic code.

## What was done

### 1. Restored Dvir's real profile
- `data/user_profile.json` had been overwritten with test data ("Test Student") during session 24 testing
- Restored real data from git history (commit `bcc12ad`) and merged with current schema format
- Fields restored: name, email, phone, linkedin, github, skills, skills_not, domains, watchlist (12 companies), experience_level, hard_rules (cv_title, must_include, banned_words)

### 2. Moved COMPANY_DOMAINS from hunter.py to companies.json
- Removed hardcoded `COMPANY_DOMAINS` dict (35 entries) from `job_hunter/recruiters/hunter.py`
- Added `email_domain` field to every company entry in `data/jobs/companies.json`
- `get_domain_for_company()` now loads domains dynamically from `companies.json` via `Config.companies_file()`
- Fallback unchanged: unknown companies still get `firstword.com`

### 3. Updated CLAUDE.md
- Updated "Known hardcoded personal data" table — all 6 items now resolved
- Marked B5 as DONE in SESSION.md

## Audit: All hardcoded data now resolved
| File | Resolution |
|------|-----------|
| `cover_letter/generator.py` | Reads from profile (done in Priority 3) |
| `cli.py` email compose | Uses `get_profile().signature_block()` (done in Priority 3) |
| `cv/adapter.py` title rule | Uses `profile.cv_title` (done in Priority 3) |
| `relevance_filter.py` keywords | Uses profile domains/positions/skills (done in Priority 3) |
| `change_summary.py` | File removed |
| `recruiters/hunter.py` domains | Now reads from `companies.json` `email_domain` field |

## Tests
280 tests pass.

## Known issue discovered
Tests overwrite `data/user_profile.json` with test data. A test is leaking — not using temp directory properly. Not fixed in this session (separate issue).

## Files changed
- `data/user_profile.json` — restored real Dvir profile
- `data/jobs/companies.json` — added `email_domain` to all 30 company entries
- `job_hunter/recruiters/hunter.py` — replaced hardcoded dict with `companies.json` lookup
- `CLAUDE.md` — updated hardcoded data table
- `knowladge/SESSION.md` — marked B5 done
