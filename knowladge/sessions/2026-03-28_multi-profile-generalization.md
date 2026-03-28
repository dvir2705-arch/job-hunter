# Session: 2026-03-28 — Multi-profile generalization

## What was done
- Generalized cover letter generator: replaced hardcoded EE focus areas, skill examples, and banned skills with profile-driven fields (specialization, skills, skills_not)
- Generalized interview tips: replaced EE-specific keyword-to-tip mapping and personal references (military, job-hunter project) with profile-driven tips from target_positions + skills
- Generalized relevance filter: split IRRELEVANT_KEYWORDS into ALWAYS_IRRELEVANT (operational roles) and PROFESSIONAL_FIELDS (excluded only if NOT in user's domains) — a lawyer won't have "legal" filtered out
- Made IRRELEVANT_COMPANIES profile-aware (e.g., "pharma" not filtered for biotech users)
- Replaced hardcoded discovery keywords with profile.domains loading
- Expanded init command: added prompts for specialization, cv_title, target_positions, skills, skills_not; removed EE-specific DEFAULT_DOMAINS
- Updated onboarding tests for new init prompts; all 59 tests passing

## Files changed
- `job_hunter/cover_letter/generator.py` — profile-driven focus areas, skills_not, academic year fallback
- `job_hunter/cv/change_summary.py` — profile-driven interview tips, removed personal references
- `job_hunter/jobs/relevance_filter.py` — split irrelevant keywords, profile-aware filtering
- `job_hunter/jobs/discovery.py` — load relevant keywords from profile.domains
- `job_hunter/cli.py` — expanded init with 6 new prompts, removed DEFAULT_DOMAINS
- `tests/test_onboarding.py` — updated test inputs for new init flow

## Commits
- (pending — will be committed at session close)

## Key decisions
- ALWAYS_IRRELEVANT vs PROFESSIONAL_FIELDS split: operational roles (catering, warehouse, etc.) are always irrelevant; professional fields (legal, mechanical, etc.) are only irrelevant if NOT in user's domains
- Removed DEFAULT_DOMAINS entirely rather than generating smart defaults from degree — requiring user input is simpler and more accurate
- Interview tips: hybrid approach (generic tips + profile-derived) rather than fully AI-generated — avoids extra API calls
- Company data (hunter.py, companies.json, COMPANY_TONES) left as-is — Israel-specific but harmless (falls back gracefully)
- Academic year defaults to empty string instead of "third" — letter omits year if can't compute

## Notes
- Dvir's existing user_profile.json still works identically — no migration needed
- Priority 5 "Unify RELEVANT_KEYWORDS" is now effectively done (discovery.py loads from profile.domains)
- Next: Priority 5 — cross-platform browser/clipboard
