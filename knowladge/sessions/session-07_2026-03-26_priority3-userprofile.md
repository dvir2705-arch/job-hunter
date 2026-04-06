# Session 7 — 2026-03-26 — Priority 3: UserProfile & Centralized Data

## What was done
- Created `data/user_profile.json` + `job_hunter/profile.py` (UserProfile dataclass)
- Refactored cover_letter/generator.py: inject name/email/phone/degree from UserProfile
- Refactored cv/adapter.py: derive title rule from UserProfile.degree
- Refactored cli.py:_send_email_to_recruiter(): read contact info from UserProfile
- Refactored relevance_filter.py: load domain keywords from UserProfile.domains

## Key commits
- `bcc12ad` session: Priority 3 done — UserProfile dataclass, centralized personal data out of 5 files
