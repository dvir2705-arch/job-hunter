# Session 10 — 2026-03-28 — Improved Filter & Company-Targeted Search

## What was done
- Improved relevance filter: expanded irrelevant keywords, uncertain jobs always deep-checked via Haiku, accept on API failure
- Company-targeted JobSpy search: 30 companies in companies.json, 12 priority
- Default scan includes priority companies; added `--no-companies` and `--companies-all` flags
- Fixed Unicode crash in `cli.py` for Windows cp1255 console

## Key commits
- `bb272bf` session: improved relevance filter
- `a189fd3` Add --companies flag for company-targeted JobSpy search
- `ac6e0bd` Fix Unicode crash in job table on Windows cp1255 console
- `caf8f10` session: company-targeted JobSpy search with priority filtering
