# Job Hunter

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![Claude AI](https://img.shields.io/badge/Claude-AI%20Powered-orange?logo=anthropic)
![License](https://img.shields.io/badge/License-MIT-green)
![Tests](https://img.shields.io/badge/Tests-374-brightgreen)

**AI-powered career management CLI that adapts your CV to job descriptions using Claude AI, scrapes jobs from multiple sources, tracks applications, and generates cover letters — so every application puts your best foot forward.**

---

## Key Features

- **Smart CV Adaptation** — Claude AI rewrites your CV to match each job description, highlighting the most relevant skills and experience
- **Multi-Source Job Scraping** — Parallel scraping from LinkedIn, Indeed, Glassdoor, and company career pages (Intel, NVIDIA, Amazon, etc.)
- **Intelligent Filtering** — Two-layer relevance filter: fast keyword matching + AI deep-check for borderline jobs
- **Professional PDF Generation** — Renders polished, print-ready CVs from customizable HTML/CSS templates
- **Bilingual Support** — Generate CVs in English or Hebrew (with full RTL support)
- **Cover Letter Generation** — Auto-generates tailored cover letters for each application
- **Application Tracker** — Track every application with status management, notes, and analytics dashboard
- **Multi-Profile System** — Isolated data per user with profile switching
- **Recruiter Management** — Store contacts, search LinkedIn, find emails via Hunter.io
- **Company Watchlist** — AI-suggested companies based on your profile

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| AI Engine | Claude API (Anthropic) |
| CLI Framework | Click + Rich |
| Templating | Jinja2 |
| PDF Rendering | Chrome (headless) + Jinja2 HTML templates |
| Job Scraping | python-jobspy, requests, BeautifulSoup |
| Parallelism | concurrent.futures (ThreadPoolExecutor) |
| Data Storage | JSON (file-based, per-user isolation) |

---

## Data Structures & Algorithms

This project applies several core CS concepts in a real-world context:

| Concept | Where | How It's Used |
|---------|-------|---------------|
| **Finite State Machine** | [`applications/models.py`](job_hunter/applications/models.py) | Application status transitions modeled as a directed graph (adjacency list). `VALID_TRANSITIONS` dict enforces legal state changes (e.g., `applied -> screening -> interview -> offer`), preventing invalid paths like `rejected -> interview`. |
| **TTL Cache with Adaptive Expiration** | [`jobs/scan_cache.py`](job_hunter/jobs/scan_cache.py) | Key-value store with 90-minute default TTL. When a source returns 0 results for 3+ consecutive scans, TTL extends to 24 hours. Uses atomic file writes (`os.replace`) to prevent corruption. |
| **Two-Layer Filtering Pipeline** | [`jobs/relevance_filter.py`](job_hunter/jobs/relevance_filter.py) | Layer 1: O(n*k) keyword matching with word-boundary regex for short terms. Layer 2: uncertain jobs sent to Claude Haiku in batches of 15 for AI classification. Optimizes expensive API calls by pre-filtering locally. |
| **Thread Pool (Producer-Consumer)** | [`jobs/scraper.py`](job_hunter/jobs/scraper.py) | Multiple job scrapers run concurrently via `ThreadPoolExecutor`. Results collected with `as_completed()` for progressive CLI output. |
| **Dataclass ADTs** | [`profile.py`](job_hunter/profile.py), [`models.py`](job_hunter/applications/models.py) | Structured records with validation, `to_dict()`/`from_dict()` serialization, computed properties, and auto-generated UUIDs. |
| **Schema Migration** | [`profile.py`](job_hunter/profile.py) | Backward-compatible data transformation: flat fields migrate to nested structures, missing fields get sensible defaults. Handles 4+ schema versions transparently. |
| **Tree-Structured Data Isolation** | [`config.py`](job_hunter/config.py), [`profile_manager.py`](job_hunter/profile_manager.py) | Per-user data stored in isolated directory subtrees. `Config.set_user()` rebases all path references to the active user's subtree while sharing global resources. |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Google Chrome or Chromium (for PDF generation)
- Anthropic API key 

**1. Clone & install**
```bash
git clone https://github.com/dvir2705-arch/job-hunter.git
cd job-hunter
pip install -e .
```

**2. Configure your API key**
```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

**3. Initialize your profile**
```bash
job-hunter init
```

**4. Add your CV**
```bash
# Import from a Word document:
job-hunter cv init --from-file my_cv.docx
# Or edit the base CV JSON directly
job-hunter cv show
```

---

## Usage

### Job Discovery
```bash
# Scan all sources (LinkedIn, Indeed, company pages) with AI relevance filtering
job-hunter jobs scan

# Search with specific query
job-hunter jobs search --query "backend engineer" --location "Tel Aviv"

# Refresh AI-generated search queries based on your profile
job-hunter jobs refresh-queries
```

### CV Management
```bash
# Adapt your CV to a job description
job-hunter cv adapt --job-desc job.txt --job-title "Backend Engineer" --label google

# Generate PDF + cover letter in one command
job-hunter cv adapt -j job.txt -t "Backend Engineer" -l google --pdf --cover-letter -c "Google"

# Render a Hebrew CV
job-hunter cv adapt -j job.txt -t "Software Engineer" -l intel --lang he

# List all saved CV versions
job-hunter cv list
```

### Application Tracking
```bash
# View all applications
job-hunter apps list

# Filter by status or company
job-hunter apps list --status interview
job-hunter apps list --company Google

# Update application status
job-hunter apps update <app-id> --status interview --notes "Phone screen Thursday 3pm"

# View analytics dashboard
job-hunter apps dashboard
```

### Application Status Flow
```
applied -> screening -> interview -> offer
    \          \            \
     `-> rejected    `-> rejected    `-> withdrawn
```

### Profile & Companies
```bash
# View/edit profile
job-hunter profile show
job-hunter profile edit

# Switch between profiles
job-hunter profile list
job-hunter profile switch <name>

# Manage company watchlist
job-hunter companies list
job-hunter companies add "Intel" "NVIDIA" "Apple"
job-hunter companies suggest   # AI-powered suggestions
```

### Recruiter Tools
```bash
# Add and manage recruiter contacts
job-hunter recruiters add --company Intel --name "Jane Doe" --email jane@intel.com
job-hunter recruiters list
job-hunter recruiters find-emails --domain intel.com
```

---

## Project Structure

```
job-hunter/
├── job_hunter/
│   ├── cli.py                  # CLI entry point — 7 command groups
│   ├── config.py               # Configuration, paths, env vars
│   ├── profile.py              # UserProfile dataclass + schema migration
│   ├── profile_manager.py      # Multi-profile management + switching
│   ├── logger.py               # Logging configuration
│   ├── cv/
│   │   ├── adapter.py          # Claude AI CV adaptation
│   │   ├── renderer.py         # Jinja2 + WeasyPrint PDF rendering
│   │   ├── manager.py          # CV load/save/version control
│   │   ├── docx_parser.py      # Word document import
│   │   ├── parser.py           # CV format parsing
│   │   └── change_summary.py   # Diff summary after adaptation
│   ├── applications/
│   │   ├── tracker.py          # Application CRUD + analytics
│   │   └── models.py           # FSM status transitions + data models
│   ├── jobs/
│   │   ├── scraper.py          # Multi-source parallel scraping
│   │   ├── relevance_filter.py # Two-layer keyword + AI filtering
│   │   ├── search_strategy.py  # Profile-driven query generation
│   │   ├── scan_cache.py       # TTL cache with adaptive expiration
│   │   ├── discovery.py        # Job discovery orchestration
│   │   ├── analyzer.py         # Job requirement extraction
│   │   └── history.py          # Scan history tracking
│   ├── cover_letter/
│   │   ├── generator.py        # Claude AI cover letter generation
│   │   ├── critic.py           # Cover letter quality scoring
│   │   ├── templates.py        # Letter templates
│   │   └── history.py          # Generation history
│   └── recruiters/
│       ├── manager.py          # Recruiter contact management
│       └── hunter.py           # Hunter.io email finder integration
├── templates/cv/               # HTML/CSS CV templates (EN + HE/RTL)
├── data/                       # JSON data storage (per-user)
├── tests/                      # 18 test files, 374 tests (pytest)
└── output/                     # Generated PDFs & cover letters
```

---

## Testing

374 tests across 18 test files, covering:

- **Unit tests** — Data models, status transitions, schema validation, CV adaptation, filtering logic
- **CLI integration tests** — Full command testing via Click's CliRunner (init, profile, companies, jobs)
- **Edge cases** — Corrupted JSON recovery, API failures, malformed data, multi-profile isolation

```bash
pytest                    # Run all tests
pytest -x                 # Stop on first failure
pytest tests/test_onboarding.py  # Run specific test file
```

---

## Roadmap

- [x] CV adaptation with Claude AI
- [x] PDF generation with custom templates
- [x] Cover letter generation
- [x] Application tracker with status management
- [x] Multi-source job scraping with parallel execution
- [x] Intelligent relevance filtering (keyword + AI)
- [x] Multi-profile system with data isolation
- [x] Bilingual CV support (English + Hebrew/RTL)
- [x] Company watchlist with AI suggestions
- [x] Recruiter management + email finder


---

## About the Developer

**Dvir Salomon** — 3rd year Electrical Engineering student at **Ben-Gurion University of the Negev**.

Built this tool to solve a real problem: making every job application count.

- [LinkedIn](https://linkedin.com/in/dvir-solomon-6b87493a2)
- [GitHub](https://github.com/dvir2705-arch)
- Dvir2705@gmail.com

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
