# 🎯 Job Hunter

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![Claude AI](https://img.shields.io/badge/Claude-AI%20Powered-orange?logo=anthropic)
![License](https://img.shields.io/badge/License-MIT-green)

**AI-powered career management system that adapts your CV to job descriptions using Claude AI — so every application puts your best foot forward.**

---

## ✨ Key Features

- 🤖 **Smart CV Adaptation** — Claude AI rewrites your CV to match each job description, highlighting the most relevant skills and experience
- 📄 **Professional PDF Generation** — Renders polished, print-ready CVs from customizable HTML/CSS templates using WeasyPrint
- ✉️ **Cover Letter Generation** — Auto-generates tailored cover letters for each application in seconds
- 📊 **Application Tracker** — Track every application with status updates, notes, and analytics
- 🗂️ **CV Version Control** — Every adapted CV is saved and versioned, so you always know which CV you sent where

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| AI Engine | Claude API (Anthropic) |
| Templating | Jinja2 |
| PDF Rendering | WeasyPrint |
| CLI Framework | Click + Rich |
| Data Storage | JSON |

---

## 🚀 Quick Start

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

**3. Add your CV**
```bash
# Edit data/cv/base_cv.json with your real information
job-hunter cv show
```

---

## 📖 Usage

### CV Management

```bash
# Adapt your CV to a job description
job-hunter cv adapt --job-desc path/to/job.txt --job-title "Backend Engineer" --label google

# Generate PDF + cover letter in one command
job-hunter cv adapt -j job.txt -t "Backend Engineer" -l google --pdf --cover-letter -c "Google"

# Render any saved CV version to PDF
job-hunter cv render --version cv_google_20240323_120000.json

# List all saved CV versions
job-hunter cv list
```

### Application Tracking

```bash
# Add a new application
job-hunter apps add -c "Google" -p "Backend Engineer" -u "https://careers.google.com/jobs/123"

# View all applications
job-hunter apps list

# Filter by status
job-hunter apps list --status interview

# Update application status
job-hunter apps update <app-id> --status interview --notes "Phone screen Thursday 3pm"

# View stats dashboard
job-hunter apps stats
```

### Application Status Flow

```
applied → screening → interview → offer
                              ↘ rejected / withdrawn
```

---

## 📸 Demo

> Screenshots and demo GIF coming soon.

---

## 🗺️ Roadmap

- [x] CV adaptation with Claude AI
- [x] PDF generation with custom templates
- [x] Cover letter generation
- [x] Application tracker with status management
- [ ] **Job Analysis** — Parse job postings and extract key requirements automatically
- [ ] **Interview Prep** — AI-generated interview questions tailored to the job description
- [ ] **Networking Tools** — Draft cold outreach messages to recruiters and hiring managers
- [ ] **Dashboard** — Visual analytics: application funnel, response rates, timeline
- [ ] **Multi-template support** — Switch between CV styles per industry

---

## 📁 Project Structure

```
job-hunter/
├── job_hunter/
│   ├── cli.py              # CLI entry point (Click)
│   ├── config.py           # Configuration & env vars
│   ├── cv/
│   │   ├── manager.py      # Load/save/version CV data
│   │   ├── adapter.py      # Claude AI CV adaptation
│   │   └── renderer.py     # Jinja2 + WeasyPrint → PDF
│   └── applications/
│       ├── tracker.py      # Application CRUD + stats
│       └── models.py       # Data models & status enum
├── templates/cv/           # HTML/CSS CV templates
├── data/                   # JSON data storage
├── output/                 # Generated PDFs & cover letters
└── tests/                  # Unit tests (pytest)
```

---

## 👨‍💻 About the Developer

**Dvir Salomon** — 3rd year Electrical Engineering student at **Ben-Gurion University of the Negev**, specializing in Signals & Communications.

Combines strong mathematical foundations (Linear Algebra 100, Vector Calculus 97) with a passion for software development and AI. Built this tool to solve a real problem: making every job application count.

- 🔗 [LinkedIn](https://linkedin.com/in/dvir-solomon-6b87493a2)
- 🐙 [GitHub](https://github.com/dvir2705-arch)
- 📧 Dvir2705@gmail.com

---

## 🤝 Contributing

Contributions are welcome! If you have ideas for new features or improvements:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push and open a Pull Request

---

## 📄 License

MIT License — feel free to use and adapt this project.
