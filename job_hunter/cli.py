import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from job_hunter.applications.models import ApplicationStatus
from job_hunter.applications.tracker import ApplicationTracker
from job_hunter.config import Config
from job_hunter.cv.manager import CVManager

console = Console()


@click.group()
@click.version_option(package_name="job-hunter")
def cli():
    """Job Hunter — personal career bot powered by Claude AI."""
    Config.ensure_dirs()


# ---------------------------------------------------------------------------
# CV commands
# ---------------------------------------------------------------------------

@cli.group()
def cv():
    """Manage and adapt your CV."""


@cv.command("init")
def cv_init():
    """Initialize a default base CV."""
    manager = CVManager()
    path = manager.init_base()
    console.print(f"[green]Base CV created at {path}[/green]")
    console.print("Edit it with: [bold]job-hunter cv edit[/bold]")


@cv.command("show")
@click.option("--version", "-v", default=None, help="CV version filename to show (default: base CV)")
def cv_show(version):
    """Display the current base CV."""
    manager = CVManager()
    data = manager.load_version(version) if version else manager.load_base()
    import json
    console.print_json(json.dumps(data))


@cv.command("adapt")
@click.option("--job-desc", "-j", required=True, help="Path to a file containing the job description.")
@click.option("--job-title", "-t", default="", help="Job title.")
@click.option("--label", "-l", default="adapted", help="Label for the saved CV version.")
@click.option("--pdf", is_flag=True, help="Also render a PDF.")
@click.option("--cover-letter", is_flag=True, help="Also generate a cover letter.")
@click.option("--company", "-c", default="", help="Company name (used in cover letter).")
def cv_adapt(job_desc, job_title, label, pdf, cover_letter, company):
    """Adapt your CV for a specific job using Claude AI."""
    from job_hunter.cv.adapter import CVAdapter
    from job_hunter.cv.renderer import CVRenderer

    job_desc_path = Path(job_desc)
    if not job_desc_path.exists():
        console.print(f"[red]File not found: {job_desc}[/red]")
        sys.exit(1)

    job_description = job_desc_path.read_text(encoding="utf-8")
    manager = CVManager()
    base_cv = manager.load_base()

    with console.status("Adapting CV with Claude..."):
        adapter = CVAdapter()
        adapted = adapter.adapt(base_cv, job_description, job_title)

    version_path = manager.save_version(adapted, label)
    console.print(f"[green]Adapted CV saved to {version_path}[/green]")

    if pdf:
        renderer = CVRenderer()
        pdf_path = Config.OUTPUT_DIR / f"{version_path.stem}.pdf"
        renderer.render_pdf(adapted, pdf_path)
        console.print(f"[green]PDF saved to {pdf_path}[/green]")

    if cover_letter:
        with console.status("Generating cover letter..."):
            letter = adapter.generate_cover_letter(adapted, job_description, company, job_title)
        letter_path = Config.OUTPUT_DIR / f"cover_letter_{label}.txt"
        letter_path.write_text(letter, encoding="utf-8")
        console.print(f"[green]Cover letter saved to {letter_path}[/green]")


@cv.command("render")
@click.option("--version", "-v", default=None, help="CV version filename (default: base CV).")
@click.option("--output", "-o", default=None, help="Output PDF path.")
@click.option("--template", "-t", default="cv/modern.html", help="Template to use.")
def cv_render(version, output, template):
    """Render a CV version to PDF."""
    from job_hunter.cv.renderer import CVRenderer

    manager = CVManager()
    data = manager.load_version(version) if version else manager.load_base()
    renderer = CVRenderer()

    name = data.get("name", "cv").replace(" ", "_").lower()
    out_path = Path(output) if output else Config.OUTPUT_DIR / f"{name}_cv.pdf"

    renderer.render_pdf(data, out_path, template)
    console.print(f"[green]PDF saved to {out_path}[/green]")


@cv.command("list")
def cv_list():
    """List all saved CV versions."""
    manager = CVManager()
    versions = manager.list_versions()
    if not versions:
        console.print("No CV versions found.")
        return
    table = Table(title="CV Versions")
    table.add_column("File", style="cyan")
    table.add_column("Modified", style="dim")
    for v in versions:
        import datetime
        mtime = datetime.datetime.fromtimestamp(v.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(v.name, mtime)
    console.print(table)


# ---------------------------------------------------------------------------
# Application commands
# ---------------------------------------------------------------------------

@cli.group()
def apps():
    """Track job applications."""


@apps.command("add")
@click.option("--company", "-c", required=True)
@click.option("--position", "-p", required=True)
@click.option("--url", "-u", required=True)
@click.option("--salary", "-s", default=None)
@click.option("--notes", "-n", default="")
def apps_add(company, position, url, salary, notes):
    """Add a new job application."""
    tracker = ApplicationTracker()
    app = tracker.add(company=company, position=position, url=url, salary_range=salary, notes=notes)
    console.print(f"[green]Application added (ID: {app.id})[/green]")
    console.print(f"  {company} — {position}")


@apps.command("list")
@click.option("--status", "-s", default=None, type=click.Choice([s.value for s in ApplicationStatus]))
def apps_list(status):
    """List all applications."""
    tracker = ApplicationTracker()
    filter_status = ApplicationStatus(status) if status else None
    applications = tracker.list(filter_status)

    if not applications:
        console.print("No applications found.")
        return

    table = Table(title="Job Applications")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Company", style="cyan")
    table.add_column("Position")
    table.add_column("Status", style="bold")
    table.add_column("Date", style="dim")

    status_colors = {
        "applied": "blue", "screening": "yellow", "interview": "magenta",
        "offer": "green", "rejected": "red", "withdrawn": "dim",
    }

    for app in applications:
        color = status_colors.get(app.status.value, "white")
        table.add_row(
            app.id, app.company, app.position,
            f"[{color}]{app.status.value}[/{color}]",
            app.applied_date,
        )
    console.print(table)


@apps.command("update")
@click.argument("app_id")
@click.option("--status", "-s", required=True, type=click.Choice([s.value for s in ApplicationStatus]))
@click.option("--notes", "-n", default="")
def apps_update(app_id, status, notes):
    """Update the status of an application."""
    tracker = ApplicationTracker()
    app = tracker.update_status(app_id, ApplicationStatus(status), notes)
    console.print(f"[green]Updated {app.company} — {app.position} → {app.status.value}[/green]")


@apps.command("stats")
def apps_stats():
    """Show application statistics."""
    tracker = ApplicationTracker()
    stats = tracker.stats()
    console.print(f"[bold]Total applications:[/bold] {stats['total']}")
    for status, count in stats["by_status"].items():
        console.print(f"  {status}: {count}")


# ---------------------------------------------------------------------------
# Jobs commands
# ---------------------------------------------------------------------------

@cli.group()
def jobs():
    """Search and collect job listings."""


@jobs.command("search")
@click.option("--query", "-q", default="student electrical engineering", show_default=True, help="Search query.")
@click.option("--location", "-l", default="Israel", show_default=True, help="Location filter.")
@click.option("--max", "-n", "max_results", default=10, show_default=True, help="Max results to return.")
@click.option("--source", "-s", default="intel", type=click.Choice(["intel", "glassdoor", "indeed"]), show_default=True, help="Job board to search.")
def jobs_search(query, location, max_results, source):
    """Search job boards for listings."""
    from job_hunter.jobs.scraper import IndeedScraper, GlassdoorScraper, IntelScraper

    if source == "intel":
        scraper = IntelScraper()
    elif source == "glassdoor":
        scraper = GlassdoorScraper()
    else:
        scraper = IndeedScraper()
    console.print(f"Searching {source.capitalize()} for: [bold]{query}[/bold] in {location}...\n")

    try:
        with console.status("Fetching results..."):
            listings = scraper.search(query, location, max_results=max_results)
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    if not listings:
        console.print("[yellow]No jobs found. Indeed may be blocking the request, or no results match.[/yellow]")
        return

    console.print(f"[green]Found {len(listings)} jobs:[/green]\n")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Title")
    table.add_column("Company", style="cyan")
    table.add_column("Location", style="dim")
    table.add_column("URL", style="blue")

    for i, job in enumerate(listings, 1):
        table.add_row(str(i), job.title, job.company, job.location, job.url)

    console.print(table)


@jobs.command("scan")
@click.option("--query", "-q", default="student", show_default=True, help="Search query.")
@click.option("--location", "-l", default="Israel", show_default=True, help="Location filter.")
@click.option("--max", "-n", "max_per_company", default=20, show_default=True, help="Max results per company.")
def jobs_scan(query, location, max_per_company):
    """Scan all supported company career pages and show interactive menu."""
    from job_hunter.jobs.scraper import JobScanner

    scanner = JobScanner()
    console.print(f"Scanning all companies for: [bold]{query}[/bold] in {location}...\n")

    with console.status("Fetching from Intel, NVIDIA, Marvell, Amazon..."):
        listings = scanner.scan(query=query, location=location, max_per_company=max_per_company)

    if not listings:
        console.print("[yellow]No jobs found across all sources.[/yellow]")
        return

    _print_jobs_table(listings)

    # Interactive selection loop
    while True:
        console.print()
        choice = click.prompt(
            "Enter job number to explore (or [bold]q[/bold] to quit)",
            default="q",
            show_default=False,
        )
        if choice.strip().lower() == "q":
            break

        if not choice.strip().isdigit() or not (1 <= int(choice) <= len(listings)):
            console.print(f"[red]Please enter a number between 1 and {len(listings)}.[/red]")
            continue

        job = listings[int(choice) - 1]
        _job_action_menu(job)

        # Re-print table so user can pick another
        console.print()
        _print_jobs_table(listings)


def _print_jobs_table(listings) -> None:
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Title")
    table.add_column("Company", style="cyan")
    table.add_column("Location", style="dim")
    table.add_column("Posted", style="dim")
    for i, job in enumerate(listings, 1):
        table.add_row(str(i), job.title, job.company, job.location, "")
    console.print(f"[green]Found {len(listings)} jobs:[/green]")
    console.print(table)


def _job_action_menu(job) -> None:
    import webbrowser
    from job_hunter.applications.tracker import ApplicationTracker
    from job_hunter.applications.models import ApplicationStatus

    while True:
        console.print(f"\n[bold cyan]{job.title}[/bold cyan] — {job.company}, {job.location}")
        console.print(f"[dim]{job.url}[/dim]\n")
        console.print("  [bold][1][/bold] Show full details")
        console.print("  [bold][2][/bold] Adapt CV for this job  [dim](coming soon)[/dim]")
        console.print("  [bold][3][/bold] Generate cover letter  [dim](coming soon)[/dim]")
        console.print("  [bold][4][/bold] Open in browser")
        console.print("  [bold][5][/bold] Track application")
        console.print("  [bold][6][/bold] Back to list")

        action = click.prompt("\nChoose", default="6", show_default=False)

        if action == "1":
            panel_text = (
                f"[bold]Title:[/bold]    {job.title}\n"
                f"[bold]Company:[/bold]  {job.company}\n"
                f"[bold]Location:[/bold] {job.location}\n"
                f"[bold]URL:[/bold]      {job.url}"
            )
            from rich.panel import Panel
            console.print(Panel(panel_text, title="Job Details", border_style="cyan"))

        elif action == "4":
            webbrowser.open(job.url)
            console.print(f"[green]Opened in browser.[/green]")

        elif action == "5":
            tracker = ApplicationTracker()
            existing = [a for a in tracker.list() if a.url == job.url]
            if existing:
                console.print(f"[yellow]Already tracked (ID: {existing[0].id}, status: {existing[0].status.value})[/yellow]")
            else:
                notes = click.prompt("Notes (optional)", default="", show_default=False)
                app = tracker.add(
                    company=job.company,
                    position=job.title,
                    url=job.url,
                    notes=notes,
                )
                console.print(f"[green]Tracked! Application ID: {app.id}[/green]")

        elif action == "6":
            break

        else:
            console.print("[red]Invalid option.[/red]")


if __name__ == "__main__":
    cli()
