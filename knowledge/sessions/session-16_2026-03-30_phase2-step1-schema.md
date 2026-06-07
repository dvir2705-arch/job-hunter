# Session 16 — 2026-03-30 — Phase 2 Step 1: Schema + Migration

## What was done
- Added `experience_level` field to UserProfile ("none", "1-3", "3-7", "7+")
- Added `watchlist` field to UserProfile (List[str] of company names to watch)
- Updated search_strategy.py to use experience_level
- Migration for existing profiles
- 141 tests passing (3 pre-existing failures: RF Engineer, ML Researcher, `-j` flag)

## Key commits
- `e2ff213` phase2-step1: add experience_level + watchlist to UserProfile
- `3d859ee` session: phase2 step 1 done
