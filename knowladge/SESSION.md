# Session State

## Last Session (2026-03-29)
**Completed:** Profile system redesign + docx CV parser (Session A of profile plan). Commit: d551fbb.

1. **Profile redesign:** Replaced flat `UserProfile` with role-agnostic system — nested `education` dict, `hard_rules` dict (`cv_title`, `must_include`, `banned_skills`, `banned_words`), helper properties (`is_student`, `cv_title`, `university`). Backward-compat migration in `load()`.
2. **Module updates:** `adapter.py`, `generator.py`, `relevance_filter.py` now read from `hard_rules` — zero hardcoded personal data. Adaptive cover letter opening (student/graduate/professional).
3. **Docx parser:** New `docx_parser.py` with 3-signal section detection (style, formatting, content). Tested on actual CV — all 6 sections detected correctly.
4. **CV import CLI:** `cv init --from-file resume.docx` parses docx, shows detected sections, user confirms, Claude structures to JSON, saves JSON + original docx as template.
5. **Data migration:** `user_profile.json` migrated to nested format with education, hard_rules, military, languages, projects.

## Current Status
Priority 1-4: all done ✓
Profile system redesign (Session A): done ✓
Docx section detection (Step 7A): done ✓

Remaining from profile plan:
- Session B: Profile CLI commands (show/edit/validate)
- Session C: Profile import from file, free-text input
- Session D: Profile system tests
- Session E: Docx-native adaptation (Step 7B — after 7A verified)

Priority 5 (remaining):
- Cross-platform browser/clipboard, retry logic, cover letter critique loop, job analytics, Hebrew cover letter

## Next Session
**Goal:** Session B — Profile CLI commands (`profile show`, `profile edit`, `profile edit --field`, `profile validate`)
**Start message:** "Working on job-hunter at C:\Users\dvir2\job-hunter. Read CLAUDE.md."

## Session End Checklist
- [x] Update "Last Session" section with what was done + commit hashes
- [x] Advance "Next Session" goal to next priority item
- [x] Check off completed items in CLAUDE.md roadmap
- [x] Commit: `git add knowladge/SESSION.md CLAUDE.md && git commit -m "session: [what was done]" && git push origin master`
