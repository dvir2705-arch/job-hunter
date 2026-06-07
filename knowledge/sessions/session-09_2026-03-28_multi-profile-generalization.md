# Session 9 — 2026-03-28 — Multi-Profile Generalization

## What was done
- Generalized cover letter generator: replaced hardcoded EE focus areas with profile-driven fields
- Generalized interview tips: replaced EE-specific mappings with profile-driven tips
- Generalized relevance filter: split IRRELEVANT_KEYWORDS into ALWAYS_IRRELEVANT + PROFESSIONAL_FIELDS (excluded only if NOT in user's domains)
- Made IRRELEVANT_COMPANIES profile-aware
- Replaced hardcoded discovery keywords with profile.domains loading
- Expanded init command: added prompts for specialization, cv_title, target_positions, skills, skills_not
- Updated onboarding tests; all 59 tests passing

## Key decisions
- ALWAYS_IRRELEVANT vs PROFESSIONAL_FIELDS split for context-aware filtering
- Removed DEFAULT_DOMAINS entirely — require user input
- Interview tips: hybrid approach (generic + profile-derived) to avoid extra API calls

## Key commits
- `36e0d61` session: Multi-profile generalization — system now works for any user profile
