# Session 6 — 2026-03-26 — AI-Enhanced Relevance Filter

## What was done
- Added seniority guard to Layer 1 (rejects senior, manager, director, principal, VP, head of, chief)
- Removed "lead", "staff", "architect" from seniority list per Dvir's feedback
- Created `score_job_fit()` function — sends job to Claude with scoring rubric, returns 0-100 score + reason
- Replaced Layer 2's old rule-based logic with AI fit scoring (threshold: 55)
- Tested Layer 1 with 21 job titles, Layer 2 with 5 real descriptions — all correct

## Key decisions
- Conservative approach: keep Layer 1 keyword-based, enhance Layer 2 with AI scoring
- Threshold 55 — slightly generous, benefit-of-doubt on all failure paths

## Key commits
- `26fe34c` session: AI-enhanced relevance filter — seniority guard + fit scoring in Layer 2
