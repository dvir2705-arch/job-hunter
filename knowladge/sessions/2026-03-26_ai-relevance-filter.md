# Session: 2026-03-26 — AI-enhanced relevance filter

## What was done
- Added seniority guard to Layer 1 (rejects senior, manager, director, principal, VP, head of, chief)
- Removed "lead", "staff", "architect" from seniority list per Dvir's feedback (they don't guarantee non-fit)
- Created `score_job_fit()` function — sends job to Claude with candidate profile + scoring rubric, returns 0-100 score + reason
- Replaced Layer 2's old rule-based logic (domain check + skill overlap) with AI fit scoring
- Threshold set to 55 (decent fit boundary)
- Tested Layer 1 with 21 job titles — all classified correctly
- Tested Layer 2 AI scoring with 5 real descriptions — all scored correctly (e.g., R&D Student at Intel = 88, HR Student at Elbit = 5)
- Updated session-end skill to auto-save session summaries to `knowladge/sessions/`
- Updated session-end skill so Claude writes the summary instead of asking Dvir

## Files changed
- `job_hunter/jobs/relevance_filter.py` — seniority guard + AI fit scoring
- `.claude/commands/session-end.md` — auto-save session logs + auto-summarize

## Commits
- (to be committed this session)

## Key decisions
- Option A chosen (conservative): keep Layer 1 keyword-based, enhance Layer 2 with AI scoring. Option B (AI-only) and C (batch API) deferred.
- Threshold 55 chosen — sits at boundary between "weak fit" (40-59) and "decent fit" (60-79), slightly generous
- Benefit-of-doubt preserved on all failure paths (API error, bad JSON, no description)
- JobAnalyzer class left untouched — still available for other uses

## Notes
- FIT_SCORE_PROMPT has hardcoded candidate profile — will become dynamic after Priority 3 (UserProfile)
- Keyword lists still hardcoded — also a Priority 3 item
- Could evolve to Option C (batch scoring) later for cost efficiency
