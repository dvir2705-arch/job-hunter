#!/usr/bin/env python3
"""Record a real job-hunter scan and export an SVG terminal screenshot.

Usage:
    python scripts/record_demo.py          # saves docs/demo.svg
    python scripts/record_demo.py --fresh  # clears cache first

Requires a valid ANTHROPIC_API_KEY in .env and network access.
"""

import logging
import os
import sys
from pathlib import Path

# Suppress noisy third-party loggers (jobspy, urllib3, etc.)
logging.disable(logging.CRITICAL)

# Ensure project root is importable and is the working directory
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
os.chdir(_project_root)

from rich.console import Console
from rich.table import Table

from job_hunter.config import Config
from job_hunter.profile import get_profile


def main():
    fresh = "--fresh" in sys.argv

    # Validate environment
    try:
        Config.validate()
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Activate the user profile (same as CLI startup)
    from job_hunter.profile_manager import get_active_profile

    active = get_active_profile()
    if active:
        Config.set_user(active)
    Config.ensure_dirs()

    profile = get_profile()
    if not profile:
        print("ERROR: No profile found. Run 'job-hunter init' first.")
        sys.exit(1)

    # Set up recorded console (width matches a typical GitHub README render)
    console = Console(record=True, width=100)

    # Print header
    console.print("[bold]$ job-hunter jobs scan[/bold]\n")

    # Build search config
    from job_hunter.jobs.scan_cache import ScanCache
    from job_hunter.jobs.search_strategy import build_search_config

    config = build_search_config(profile)

    query_list = ", ".join(f'"{q}"' for q in config.queries)
    company_count = len(config.priority_companies)
    console.print(
        f"Scanning {len(config.queries)} queries + {company_count} priority companies "
        f"in {config.location}...\n"
    )
    console.print(f"[dim]Queries: {query_list}[/dim]\n")

    cache = ScanCache()
    if fresh:
        cache.clear()

    # Run parallel scan with progress output
    from job_hunter.jobs.scraper import JobScanner

    scanner = JobScanner()

    def progress_callback(source_key, jobs_found, new_count, cached_age):
        parts = source_key.split(":", 2)
        if parts[0] == "scraper" and len(parts) >= 3:
            scraper_name = parts[1].replace("Scraper", "")
            display = f'{scraper_name}: "{parts[2]}"'
        elif parts[0] == "company" and len(parts) >= 2:
            display = f"{parts[1]} (company)"
        else:
            display = source_key

        if cached_age is not None:
            status = f"[dim](cached {cached_age} min ago)[/dim]"
        else:
            status = ""

        if jobs_found == 0:
            console.print(f"  [dim]  {display}: 0 jobs {status}[/dim]")
        else:
            console.print(
                f"  [green]>[/green] {display}: "
                f"{jobs_found} job{'s' if jobs_found != 1 else ''} "
                f"{status}"
            )

    listings = scanner.parallel_scan(
        config=config,
        cache=cache,
        max_per_source=20,
        progress_callback=progress_callback,
        include_companies=True,
        only_priority=True,
    )
    console.print(f"\n[bold]Total: {len(listings)} jobs found[/bold]")

    # Apply relevance filter
    from job_hunter.jobs.relevance_filter import filter_relevant_jobs

    filtered, removed = filter_relevant_jobs(
        listings, seniority_reject=config.seniority_reject
    )
    if removed:
        console.print(
            f"[dim]Filtered out {len(removed)} irrelevant jobs "
            f"(use --all to see everything)[/dim]"
        )

    if not filtered:
        console.print("[yellow]No relevant jobs found.[/yellow]")
    else:
        # Build results table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("Title")
        table.add_column("Company", style="cyan")
        table.add_column("Location", style="dim")

        for i, job in enumerate(filtered[:15], 1):  # Cap at 15 rows for readability
            table.add_row(str(i), job.title, job.company, job.location)

        console.print(f"\n[green]Found {len(filtered)} relevant jobs:[/green]")
        console.print(table)

        if len(filtered) > 15:
            console.print(f"[dim]  ... and {len(filtered) - 15} more[/dim]")

    # Export SVG
    output_path = Path(__file__).resolve().parent.parent / "docs" / "demo.svg"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    svg = console.export_svg(title="job-hunter jobs scan")
    output_path.write_text(svg, encoding="utf-8")
    print(f"\nSVG saved to {output_path}")


if __name__ == "__main__":
    main()
