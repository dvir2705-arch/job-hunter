# Job Hunter - Project Context

## Session Protocol

### Rules
- One session = one feature or task. Never spread work across multiple features in one session.
- Never start coding without a confirmed session goal.
- Follow the roadmap priority order — don't jump ahead unless explicitly told to.
- Build in layers: data model → logic → CLI. Test each layer before moving on.
- If the task is unclear, ask one focused question before starting — don't assume.

### Session Start
1. Read `knowladge/SESSION.md`
2. Report in 3 bullets: last completed / current status / next task
3. Wait for Dvir to confirm the goal before writing any code

### Session End
1. Update `knowladge/SESSION.md`: last session summary, advance next task, add any blockers
2. Check off completed items in the roadmap below
3. Commit: `git add knowladge/SESSION.md CLAUDE.md && git commit -m "session: [what was done]" && git push origin master`

## About the Developer
- Name: Dvir Salomon
- Background: 3rd year Electrical Engineering student at Ben-Gurion University
- Specialization: Signals and Communications
- GPA: 83 (Math scores: Linear Algebra 100, 99; Calculus 97)
- Looking for: Software development, DSP, ML/AI positions

## Project Goals
1. Near-term: Help me find a job through automated CV adaptation and application tracking
2. Long-term: Turn this into a product others can use

## Planned Modules
- CV Management (done)
- Job Analysis (planned) - analyze job descriptions to find skill gaps
- Interview Prep (planned) - prepare for interviews based on actual interviews received
- Networking Tools (planned) - manage recruiter contacts and outreach

## Code Style
- Language: Python 3.11+
- Use type hints
- Write docstrings for functions
- Variable names: snake_case
- Classes: PascalCase
- Comments: English
- Keep code modular and testable

## Tech Stack
- Claude API for AI features
- Jinja2 for templates
- Chrome (via subprocess) for PDF generation
- Click for CLI
- JSON for data storage (no database yet)

## Token Efficiency Rules
- Don't read files unless I tell you which files to change
- Keep responses short — no lengthy explanations unless asked
- Combine related changes into one commit
- Don't re-read files you already read in this session

## Git Rules
- Always commit and push at the end of every task
- Never leave modified files uncommitted
- Use: git add [files] && git commit -m "message" && git push origin master
- Do NOT commit output files (PDFs, HTMLs, cover letters) — they are in .gitignore
- Keep repository structure clean — no duplicate files
- Never commit output files, logs, or personal data
- Before every push, verify with: git status

---

## Roadmap (from full project audit, 2026-03-26)

### Priority 1 — Bugs & broken things
- [x] `requirements.txt`: add `requests`, `beautifulsoup4`, `python-jobspy`
- [x] `tracker.py:43`: replace silent `pass` with error log on malformed records
- [x] `scraper.py` `JobSpyScraper.search()`: honor `max_results` param (currently hardcoded 50)
- [x] `hunter.py`: add `HUNTER_API_KEY` to `.env.example`
- [x] `logger.py`: use `Config.DATA_DIR` instead of hardcoded `"data/logs"`

### Priority 2 — Tests
- [x] `tests/test_relevance_filter.py` — 5 accept / 5 reject title cases
- [x] `tests/test_application_models.py` — status transition validation
- [x] `tests/test_tracker.py` — load/save, malformed JSON recovery, follow-up detection
- [x] `tests/test_scraper.py` — JobSpyScraper returns `List[JobListing]`
- [x] `tests/test_cv_adapter.py` — JSON fence stripping, None on API failure

### Priority 3 — Centralize user data (multi-user prep)
- [x] Create `data/user_profile.json` + `job_hunter/profile.py` (`UserProfile` dataclass)
- [x] Refactor `cover_letter/generator.py`: inject name/email/phone/degree from `UserProfile`
- [x] Refactor `cv/adapter.py`: derive title rule from `UserProfile.degree`
- [x] Refactor `cli.py:_send_email_to_recruiter()`: read contact info from `UserProfile`
- [x] Refactor `relevance_filter.py`: load domain keywords from `UserProfile.domains`

### Priority 4 — Onboarding flow
- [x] `job-hunter init` command: 6-question setup → writes `data/user_profile.json`
- [x] CV upload path: parse uploaded JSON → pre-fill profile fields
- [x] Guard all commands: helpful error if profile not initialized

### Priority 5 — New features
- [ ] Cross-platform browser/clipboard (replace Windows-only `clip`/`explorer` with `pyperclip`/`webbrowser`)
- [ ] Retry logic in scrapers (exponential backoff on 429/503)
- [x] Unify `RELEVANT_KEYWORDS` between `relevance_filter.py` and `discovery.py`
- [ ] Cover letter critique loop (Claude scores and suggests improvements after generation)
- [ ] Job analytics: applications per week, response rate trend
- [ ] Hebrew cover letter option for Israeli companies

### Done on 2026-03-29 (not in original roadmap)
- [x] Relevance filter: expanded irrelevant keywords + uncertain jobs always deep-checked via Haiku + accept on API failure
- [x] Company-targeted search: 30 companies in `companies.json`, 12 priority, default scan includes priority companies, `--no-companies` and `--companies-all` flags
- [x] Unicode fix in `cli.py` for Windows cp1255
- [x] CV template CSS optimization for one-page fit (spacing/margins, `--headless=new`, skills as inline text)
- [x] CV content rules: "3rd year" hard rule, "debugging" banned, one-page hard rule in adapter prompts
- [x] `base_cv.json` updated: "3rd year" in education, Job Hunter project in problem/solution/result format

### Known hardcoded personal data (to fix in Priority 3)
| File | What's hardcoded |
|------|-----------------|
| `cover_letter/generator.py:32–33` | Name, email, phone, university, degree in AI prompt |
| `cli.py:1077–1078` | Name, email, phone in email compose |
| `cv/adapter.py:24–39` | Title rule: "Electrical Engineering Student" |
| `jobs/relevance_filter.py:6–48` | EE-specific keyword lists |
| `change_summary.py:298–318` | EE/Python interview prep tips |
| `recruiters/hunter.py:11–46` | Israel company→domain map |

---

## Approved Plan — Phase 2: New User Onboarding

### Decisions (don't revisit)
1. Empty watchlist = no company scan. New users add companies during init or manually later.
2. Drop `domains` from init. Relevance filter derives keywords from `target_positions + skills` when `domains` is empty.
3. Profile path override only: `--profile-path <file>` flag for testing. No directory restructure.
4. Dvir's migration: copy priority companies from companies.json into profile's `watchlist` field automatically.
5. `experience_level` replaces `is_student` as primary. Values: "none", "1-3", "3-7", "7+". `is_student` property still exists (checks education.year) but is secondary.

### New Schema Fields
```python
experience_level: str = ""        # "none", "1-3", "3-7", "7+"
watchlist: List[str] = field(default_factory=list)  # company names to watch
```

### Init Flow (7 required + 1 conditional)
```
jobs init
1. Name? >
2. Email? >
3. Phone? >
4. Target roles? (comma-separated) >
5. Key skills? (comma-separated) >
6. Experience level? (none / 1-3 / 3-7 / 7+)
7. Location? >
→ If "none": Are you studying? → If yes: What and where?
→ Auto: generate queries via Haiku → show → confirm
→ Auto: suggest companies via Haiku → show → confirm/edit
→ Save profile. Offer first scan.
```

### Build Order
1. **Schema + migration** — Add `experience_level` + `watchlist` to UserProfile. Update `search_strategy.py` to use `experience_level`. Migration for existing profiles. Tests.
2. **Watchlist-driven company loading** — `_load_companies()` reads `profile.watchlist`, cross-refs companies.json registry for scraper metadata. Empty watchlist = no company scan. Tests.
3. **`jobs init` wizard (minimal)** — Rich prompts, 7 questions + conditional, create profile, generate queries via Haiku, show to user. NO company suggestions yet. Tests.
4. **Company suggestions via Haiku** — `suggest_companies(profile) -> List[str]`. Plug into init wizard. Save to `profile.watchlist`. Tests.
5. **Relevance filter update** — When `domains` is empty, derive filter keywords from `target_positions + skills`. Tests.
6. **Profile CLI** — `jobs profile show/edit/validate`, `--profile-path` flag on all commands.
7. **Company CLI** — `jobs companies list/add/remove/suggest`.
8. **Integration tests** — 3 test profiles (CS student, backend dev, data scientist). Verify Dvir's profile still works.

### Still Pending (not in current plan)
- Programmatic CV page-count safety net (render → check → retry)
- Quick CV adapt via URL without scanning
- Interview prep module
- Profile import from file + free-text input
- Docx-native CV adaptation

---

## Completed Plan — Search Strategy Redesign (done 2026-03-30)
Parallel profile-driven scanning with ThreadPoolExecutor, Haiku query generation, per-source cache (90min TTL), progressive CLI output. All backward compatible. 77 tests passing.

---

## CV Rules
- Title is always "Electrical Engineering Student" — never changes
- Never claim skills Dvir doesn't have (no Linux, no C++, no FPGA)
- "strong" allowed only near math grades (100, 99, 97)
- Grades not repeated in cover letter — they're in the CV
- Education must say "3rd year" — never "second year"
- CV must fit one page — adapter prompts enforce this as a hard rule
- "debugging" is banned as a skill (too generic)
- Skills listed as inline text, not bullet lists, to save space

## Cover Letter Rules
- 80-120 words, 3 paragraphs, strict template
- Focus area adapts by job type: RF→signals, software→Python, chip→digital systems
- Banned words: "passionate", "genuinely", "solid", "excited", "caught my attention"
- No "aligns directly with" or "maps directly to" — use "gave me a foundation relevant to"
- No vague filler phrases — every sentence must say something specific
- No military references or "high-pressure environments"
- Job Hunter project not mentioned; military not mentioned

## Past Mistakes — Never Repeat
- Deleted Siemens application instead of resetting → never delete user data without explicit permission
- Cover letter claimed "comfortable with Linux" → never claim skills Dvir doesn't have
- CV title changed to "Embedded Systems" → title is fixed: "Electrical Engineering Student"
- Wrote "second year" instead of "third year" → Dvir is in third year (2026)
- Listed "debugging" as a skill → too generic, never include it
- Auto-accepted uncertain jobs without checking → uncertain jobs must always be deep-checked via Haiku
