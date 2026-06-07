# Session 2 — 2026-03-24 — Job Scanning System

## What was done
- Built jobs module with target companies and job boards
- Implemented Workday API scrapers for company career pages
- Added AmazonScraper, LinkedInScraper (public guest search), GreenhouseScraper base
- Created interactive job menu in `jobs scan` command with CV adaptation option
- Added new-job detection with 24h badge highlighting
- Built automatic company discovery from job listings
- Added cover letter module: generator (Claude AI), history storage/retrieval, CLI wiring
- Added CV change summary generation
- Expanded companies database from 10 to 24+ (Wix, Base44, Imagen)
- Fixed Workday scraper dropping Israel jobs, CV adapter false specializations, cover letter year accuracy

## Key commits
- `8658d2c` Add job scanning system with Workday API scrapers
- `08edbbf` Add AmazonScraper and expand job scanning to 4 companies
- `1effab3` Add interactive job menu to jobs scan command
- `a703761` Add LinkedInScraper using public guest search page
- `92cc2c7` Implement cover letter generator with Claude AI integration
- `8b705d9` Prevent job-hunter project from appearing in cover letters
