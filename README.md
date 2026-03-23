# Job Hunter

Personal career bot that manages your CV, adapts it for job positions using Claude AI, and tracks applications.

## Setup

```bash
pip install -e .
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## Usage

### CV Management

```bash
# Create your base CV (edit data/cv/base_cv.json afterward)
job-hunter cv init

# Show base CV
job-hunter cv show

# Adapt CV for a job (reads job description from a file)
job-hunter cv adapt --job-desc path/to/job.txt --job-title "Backend Engineer" --label google

# Also generate PDF and cover letter
job-hunter cv adapt -j job.txt -t "Backend Engineer" -l google --pdf --cover-letter -c "Google"

# Render any CV version to PDF
job-hunter cv render --version cv_google_20240101_120000.json

# List all saved CV versions
job-hunter cv list
```

### Application Tracking

```bash
# Add a new application
job-hunter apps add -c "Google" -p "Backend Engineer" -u "https://careers.google.com/jobs/123"

# List all applications
job-hunter apps list

# Filter by status
job-hunter apps list --status interview

# Update status
job-hunter apps update <app-id> --status interview --notes "Phone screen scheduled"

# View stats
job-hunter apps stats
```

## Application Statuses

`applied` → `screening` → `interview` → `offer` / `rejected` / `withdrawn`

## Project Structure

```
job_hunter/
├── cli.py              # CLI entry point
├── config.py           # Configuration
├── cv/
│   ├── manager.py      # Load/save CV versions
│   ├── adapter.py      # Claude AI CV adaptation
│   └── renderer.py     # Jinja2 + WeasyPrint PDF
└── applications/
    ├── tracker.py      # Application CRUD
    └── models.py       # Data models

templates/cv/           # HTML/CSS CV templates
data/                   # JSON data storage
output/                 # Generated PDFs
```

## Running Tests

```bash
pytest
```
