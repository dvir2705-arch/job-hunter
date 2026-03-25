import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from job_hunter.applications.tracker import ApplicationTracker
from job_hunter.config import Config
from job_hunter.cv.manager import CVManager

console = Console()


def open_in_chrome(url: str) -> None:
    """Open a URL in Google Chrome, falling back to the default browser."""
    import webbrowser
    import subprocess
    import platform
    import os

    system = platform.system()
    try:
        if system == "Windows":
            chrome_candidates = [
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]
            chrome_path = next((p for p in chrome_candidates if os.path.exists(p)), None)
            if chrome_path:
                subprocess.Popen([chrome_path, url])
            else:
                raise FileNotFoundError("Chrome not found")
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", "Google Chrome", url])
        else:
            subprocess.Popen(["google-chrome", url])
    except FileNotFoundError:
        webbrowser.open(url)


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


@apps.command("list")
@click.option("--status", "-s", default=None,
              type=click.Choice(["applied", "screening", "interview", "offer", "rejected", "withdrawn"]))
def apps_list(status):
    """List all applications."""
    from job_hunter.applications.models import VALID_STATUSES
    tracker = ApplicationTracker()
    applications = tracker.get_by_status(status) if status else tracker.get_all()

    if not applications:
        console.print("No applications found.")
        return

    table = Table(title="Job Applications")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Company", style="cyan")
    table.add_column("Position")
    table.add_column("Status", style="bold")
    table.add_column("Date", style="dim")
    table.add_column("Follow-up", style="dim")

    status_colors = {
        "applied": "blue", "screening": "yellow", "interview": "magenta",
        "offer": "green", "rejected": "red", "withdrawn": "dim",
    }

    for app in applications:
        color = status_colors.get(app.status, "white")
        fu_flag = " ⚠" if app.needs_follow_up() else ""
        table.add_row(
            app.id, app.company, app.job_title,
            f"[{color}]{app.status}[/{color}]",
            app.applied_date,
            f"{app.follow_up_date}{fu_flag}",
        )
    console.print(table)


@apps.command("update")
@click.argument("app_id")
@click.option("--status", "-s", required=True,
              type=click.Choice(["applied", "screening", "interview", "offer", "rejected", "withdrawn"]))
@click.option("--notes", "-n", default="")
def apps_update(app_id, status, notes):
    """Update the status of an application."""
    tracker = ApplicationTracker()
    try:
        app = tracker.update_status(app_id, status, notes)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return
    if not app:
        console.print(f"[red]Application '{app_id}' not found.[/red]")
        return
    console.print(f"[green]Updated {app.company} — {app.job_title} → {app.status}[/green]")


@apps.command("stats")
def apps_stats():
    """Show application statistics."""
    tracker = ApplicationTracker()
    stats = tracker.get_stats()
    console.print(f"[bold]Total applications:[/bold] {stats['total']}")
    console.print(f"[bold]Response rate:[/bold] {stats['response_rate']}%")
    console.print(f"[bold]Needs follow-up:[/bold] {stats['needs_follow_up']}")
    for status, count in stats["by_status"].items():
        console.print(f"  {status}: {count}")


# ---------------------------------------------------------------------------
# Recruiter commands
# ---------------------------------------------------------------------------

@cli.group()
def recruiters():
    """Manage recruiter contacts."""


@recruiters.command("add")
@click.option("--company", "-c", required=True, help="Company name.")
@click.option("--name", "-n", required=True, help="Recruiter full name.")
@click.option("--email", "-e", required=True, help="Recruiter email.")
@click.option("--linkedin", "-l", default="", help="LinkedIn profile URL.")
@click.option("--role", "-r", default="", help="Recruiter role/title.")
@click.option("--notes", default="", help="Free-text notes.")
def recruiters_add(company, name, email, linkedin, role, notes):
    """Add a recruiter contact for a company."""
    from job_hunter.recruiters.manager import RecruiterManager
    mgr = RecruiterManager()
    rec = mgr.add(company=company, name=name, email=email,
                  linkedin=linkedin, role=role, notes=notes)
    console.print(f"[green]Saved:[/green] {rec.name} @ {rec.company} ({rec.email})")


@recruiters.command("list")
@click.option("--company", "-c", default=None, help="Filter by company name (fuzzy).")
def recruiters_list(company):
    """List saved recruiter contacts."""
    from job_hunter.recruiters.manager import RecruiterManager
    from rich.table import Table

    mgr = RecruiterManager()

    if company:
        rows = mgr.find_by_company_fuzzy(company)
        if not rows:
            console.print(f"[yellow]No recruiters found for '{company}'.[/yellow]")
            return
    else:
        rows = [
            {"company": comp, **r}
            for comp, recs in mgr.list_all().items()
            for r in recs
        ]
        if not rows:
            console.print("[yellow]No recruiters saved yet.[/yellow]")
            return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Company", style="cyan")
    table.add_column("Name")
    table.add_column("Email", style="dim")
    table.add_column("Role", style="dim")
    table.add_column("Notes", style="dim")
    table.add_column("Added", style="dim")

    for r in rows:
        table.add_row(
            r.get("company", ""),
            r.get("name", ""),
            r.get("email", ""),
            r.get("role", ""),
            r.get("notes", "")[:40],
            r.get("added_at", ""),
        )
    console.print(table)

    stats = mgr.get_stats()
    console.print(f"[dim]Total: {stats['total_recruiters']} recruiters across "
                  f"{stats['companies_with_recruiters']} companies[/dim]")


@recruiters.command("remove")
@click.option("--company", "-c", required=True)
@click.option("--email", "-e", required=True)
def recruiters_remove(company, email):
    """Remove a recruiter by email."""
    from job_hunter.recruiters.manager import RecruiterManager
    mgr = RecruiterManager()
    if mgr.remove(company, email):
        console.print(f"[green]Removed {email} from {company}.[/green]")
    else:
        console.print(f"[yellow]Not found: {email} @ {company}[/yellow]")


@recruiters.command("search")
@click.argument("company")
def recruiters_search(company):
    """Open LinkedIn and Google searches to find recruiters for a company."""
    import urllib.parse
    import time

    linkedin_query = f"{company} Israel recruiter talent acquisition HR"
    google_query = f"{company} Israel recruiter email HR contact"

    linkedin_url = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(linkedin_query)}"
    google_url = f"https://www.google.com/search?q={urllib.parse.quote(google_query)}"

    console.print(f"[bold]Searching for recruiters at {company}...[/bold]\n")
    console.print("[cyan]Opening LinkedIn search...[/cyan]")
    open_in_chrome(linkedin_url)
    time.sleep(1)
    console.print("[cyan]Opening Google search...[/cyan]")
    open_in_chrome(google_url)

    console.print(f"\n[green]Searches opened in Chrome.[/green]")
    console.print(f"\n[dim]When you find a recruiter, save them with:[/dim]")
    console.print(f'[bold]job-hunter recruiters add -c "{company}" -n "Name" -e "email@company.com"[/bold]')


@recruiters.command("find-emails")
@click.argument("domain")
@click.option("--limit", "-l", default=5, show_default=True, help="Max results.")
def recruiters_find_emails(domain, limit):
    """Search Hunter.io for emails at a company domain."""
    from job_hunter.recruiters.hunter import HunterAPI
    from rich.table import Table

    try:
        hunter = HunterAPI()
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return

    console.print(f"[bold]Searching Hunter.io for {domain}...[/bold]\n")
    result = hunter.domain_search(domain, limit=limit)

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        return

    if result.get("pattern"):
        console.print(f"[cyan]Email pattern:[/cyan] {result['pattern']}@{domain}\n")

    emails = result.get("emails", [])
    if not emails:
        console.print("[yellow]No emails found for this domain.[/yellow]")
        return

    hr_keywords = ["recruit", "talent", "hr", "human", "people"]

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name")
    table.add_column("Email")
    table.add_column("Position")
    table.add_column("Confidence", justify="right")

    for e in emails:
        is_hr = any(kw in e.get("position", "").lower() for kw in hr_keywords)
        name = f"[bold green]{e['name']}[/bold green]" if is_hr else e["name"]
        table.add_row(name, e["email"], e["position"][:35], f"{e['confidence']}%")

    console.print(table)

    quota = hunter.get_quota()
    if "error" not in quota:
        console.print(f"\n[dim]Quota: {quota['used']} used / {quota['available']} available[/dim]")


@recruiters.command("scan-all")
@click.option("--limit", "-l", default=2, show_default=True,
              help="Max HR contacts to save per company.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would happen without saving or using quota.")
def recruiters_scan_all(limit, dry_run):
    """Scan all companies from companies.json and find recruiter emails via Hunter.io."""
    import json
    from pathlib import Path
    from job_hunter.recruiters.hunter import HunterAPI, get_domain_for_company
    from job_hunter.recruiters.manager import RecruiterManager
    from rich.table import Table

    companies_file = Path("data/jobs/companies.json")
    with open(companies_file, "r", encoding="utf-8") as f:
        companies = json.load(f).get("companies", [])

    try:
        hunter = HunterAPI()
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return

    quota = hunter.get_quota()
    available = quota.get("available", 0)
    console.print(f"[cyan]Quota:[/cyan] {quota.get('used', 0)} used / {available} available")

    if not dry_run and available < len(companies):
        console.print(f"[yellow]Warning: {available} searches for {len(companies)} companies.[/yellow]")
        if not click.confirm("Continue anyway?"):
            return

    if dry_run:
        console.print("[yellow]Dry-run mode — no searches will be made, no data saved.[/yellow]")

    console.print(f"\n[bold]Scanning {len(companies)} companies...[/bold]\n")

    manager = RecruiterManager()
    hr_keywords = ["recruit", "talent", "hr", "human resource", "people", "staffing", "hiring"]

    table = Table(title="Scan Results", show_header=True, header_style="bold cyan")
    table.add_column("Company")
    table.add_column("Domain")
    table.add_column("Pattern")
    table.add_column("HR found", justify="right")
    table.add_column("Saved", justify="right")

    total_found = total_saved = 0

    for company in companies:
        name = company.get("name", "")
        domain = get_domain_for_company(name)

        if dry_run:
            table.add_row(name, domain, "—", "—", "[dim]dry-run[/dim]")
            continue

        console.print(f"[dim]  {name} ({domain})...[/dim]")
        result = hunter.domain_search(domain, limit=limit + 5)

        if "error" in result:
            table.add_row(name, domain, "—", "[red]error[/red]", "0")
            continue

        pattern = result.get("pattern", "")
        hr_contacts = [
            e for e in result.get("emails", [])
            if any(kw in (e.get("position") or "").lower() for kw in hr_keywords)
        ][:limit]

        total_found += len(hr_contacts)
        saved = 0
        for contact in hr_contacts:
            if contact.get("email") and contact.get("name"):
                manager.add(
                    company=name,
                    name=contact["name"],
                    email=contact["email"],
                    role=contact.get("position", ""),
                    notes=f"Hunter.io (confidence: {contact.get('confidence', 0)}%)",
                )
                saved += 1
        total_saved += saved
        table.add_row(name, domain, pattern or "?", str(len(hr_contacts)), str(saved))

    console.print()
    console.print(table)
    console.print(f"\n[bold]Summary:[/bold] {len(companies)} companies scanned | "
                  f"{total_found} HR contacts found | "
                  f"[green]{total_saved} saved[/green]")

    if not dry_run:
        new_quota = hunter.get_quota()
        console.print(f"[dim]Quota after scan: {new_quota.get('used','?')} used / "
                      f"{new_quota.get('available','?')} available[/dim]")
        if total_saved:
            console.print("\n[green]View saved recruiters:[/green] [bold]job-hunter recruiters list[/bold]")


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
@click.option("--new-only", is_flag=True, default=False, help="Show only jobs seen for the first time in the last 24 hours.")
@click.option("--all", "show_all", is_flag=True, default=False, help="Show all jobs including irrelevant ones (disables profile filter).")
def jobs_scan(query, location, max_per_company, new_only, show_all):
    """Scan all supported company career pages and show interactive menu."""
    from job_hunter.jobs.scraper import JobScanner
    from job_hunter.jobs.history import JobHistory
    from job_hunter.jobs.relevance_filter import filter_relevant_jobs

    scanner = JobScanner()
    console.print(f"Scanning all companies for: [bold]{query}[/bold] in {location}...\n")

    with console.status("Fetching from Intel, NVIDIA, Marvell, Amazon..."):
        listings = scanner.scan(query=query, location=location, max_per_company=max_per_company)

    if not listings:
        console.print("[yellow]No jobs found across all sources.[/yellow]")
        return

    # Apply relevance filter unless --all is passed
    if not show_all:
        listings, removed = filter_relevant_jobs(listings)
        if removed:
            console.print(f"[dim]Filtered out {len(removed)} irrelevant jobs "
                          f"(use --all to see everything)[/dim]")
        if not listings:
            console.print("[yellow]No relevant jobs found. Run with --all to see all results.[/yellow]")
            return

    jobs_with_flags = JobHistory().update_and_mark_new(listings)
    new_count = sum(1 for _, is_new in jobs_with_flags if is_new)

    from job_hunter.jobs.discovery import CompanyDiscovery
    disc_stats = CompanyDiscovery().process_jobs(listings)
    if disc_stats["new"] > 0:
        console.print(f"[dim]Discovered {disc_stats['new']} new companies — run [bold]job-hunter jobs discover[/bold] to review[/dim]")

    if new_only:
        jobs_with_flags = [(job, is_new) for job, is_new in jobs_with_flags if is_new]
        if not jobs_with_flags:
            console.print("[yellow]No new jobs since last scan.[/yellow]")
            return
        console.print(f"[bold green]Showing {len(jobs_with_flags)} new jobs[/bold green] [dim](last 24 hours)[/dim]\n")
    else:
        if new_count:
            console.print(f"[bold green]{new_count} new[/bold green] [dim]since last scan[/dim]")

    _print_jobs_table(jobs_with_flags)

    # listings for index lookup must match the displayed table
    displayed_listings = [job for job, _ in jobs_with_flags]

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

        if not choice.strip().isdigit() or not (1 <= int(choice) <= len(displayed_listings)):
            console.print(f"[red]Please enter a number between 1 and {len(displayed_listings)}.[/red]")
            continue

        job = displayed_listings[int(choice) - 1]
        _job_action_menu(job)

        # Re-print table so user can pick another
        console.print()
        _print_jobs_table(jobs_with_flags)


@jobs.command("discover")
@click.option("--relevance", "-r", default=None,
              type=click.Choice(["high", "medium", "unknown", "low"]),
              help="Filter by relevance level.")
def jobs_discover(relevance):
    """Review companies discovered during scans that aren't in companies.json."""
    from job_hunter.jobs.discovery import CompanyDiscovery
    from rich.panel import Panel

    discovery = CompanyDiscovery()
    stats = discovery.get_stats()

    console.print(f"\n[bold]Company Discovery[/bold]  "
                  f"total={stats['total_discovered']}  "
                  f"pending={stats['pending_review']}  "
                  f"[green]high={stats['high_relevance']}[/green]  "
                  f"added={stats['added_to_main']}  "
                  f"ignored={stats['ignored']}\n")

    pending = discovery.get_pending(relevance=relevance)
    if not pending:
        msg = "No pending companies to review."
        if relevance:
            msg += f" (filter: {relevance})"
        console.print(f"[yellow]{msg}[/yellow]")
        return

    for i, company in enumerate(pending, 1):
        relevance_color = {"high": "green", "medium": "yellow", "unknown": "dim", "low": "red"}.get(
            company["relevance_score"], "dim"
        )
        titles_preview = ", ".join(company["job_titles"][:3])
        if len(company["job_titles"]) > 3:
            titles_preview += f" (+{len(company['job_titles']) - 3} more)"

        panel_text = (
            f"[bold]{company['name']}[/bold]  "
            f"[{relevance_color}]{company['relevance_score']}[/{relevance_color}]  "
            f"seen {company['times_seen']}x  "
            f"source: {company['source']}\n"
            f"[dim]Roles:[/dim] {titles_preview}\n"
            f"[dim]Locations:[/dim] {', '.join(company['locations'])}"
        )
        console.print(f"[dim]{i}.[/dim] {panel_text}\n")

    console.print("  [bold][a <N>][/bold] Mark as added to companies.json")
    console.print("  [bold][i <N>][/bold] Ignore company")
    console.print("  [bold][q][/bold]     Done\n")

    while True:
        action = click.prompt("Action", default="q", show_default=False).strip().lower()
        if action == "q":
            break

        parts = action.split()
        if len(parts) == 2 and parts[0] in ("a", "i") and parts[1].isdigit():
            idx = int(parts[1]) - 1
            if not (0 <= idx < len(pending)):
                console.print(f"[red]Number must be between 1 and {len(pending)}.[/red]")
                continue
            company_name = pending[idx]["name"]
            if parts[0] == "i":
                discovery.mark_ignored(company_name)
                console.print(f"[dim]Ignored: {company_name}[/dim]")
                pending.pop(idx)
            else:
                ok = discovery.add_to_companies_json(company_name)
                if ok:
                    console.print(f"[green]Added to companies.json: {company_name}[/green]")
                    console.print(f"[dim]Edit data/jobs/companies.json to fill in career_url and scraper.[/dim]")
                else:
                    console.print(f"[yellow]{company_name} is already in companies.json.[/yellow]")
                    discovery.mark_added(company_name)
                pending.pop(idx)
        else:
            console.print("[red]Usage: a <N> or i <N> or q[/red]")


def _print_jobs_table(jobs_with_flags) -> None:
    """Print jobs table. Accepts either List[JobListing] or List[(JobListing, bool)]."""
    # Normalise: accept plain list or list-of-tuples
    if jobs_with_flags and isinstance(jobs_with_flags[0], tuple):
        pairs = jobs_with_flags
    else:
        pairs = [(j, False) for j in jobs_with_flags]

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Title")
    table.add_column("Company", style="cyan")
    table.add_column("Location", style="dim")
    table.add_column("Posted", style="dim")

    for i, (job, is_new) in enumerate(pairs, 1):
        title = f"[bold green][NEW][/bold green] {job.title}" if is_new else job.title
        table.add_row(str(i), title, job.company, job.location, job.posted or "")

    console.print(f"[green]Found {len(pairs)} jobs:[/green]")
    console.print(table)


def _job_action_menu(job) -> None:
    from job_hunter.recruiters.manager import RecruiterManager

    while True:
        recruiter_mgr = RecruiterManager()
        recruiters = recruiter_mgr.find_by_company_fuzzy(job.company)
        recruiter = recruiters[0] if recruiters else None

        console.print(f"\n[bold cyan]{job.title}[/bold cyan] — {job.company}, {job.location}")
        console.print(f"[dim]{job.url}[/dim]\n")
        console.print("  [bold][1][/bold] Show full details")
        console.print("  [bold][2][/bold] Adapt CV for this job")
        console.print("  [bold][3][/bold] Generate cover letter")
        console.print("  [bold][4][/bold] Open in browser")
        console.print("  [bold][5][/bold] Track application")
        if recruiter:
            console.print(f"  [bold][6][/bold] Send email to recruiter ([cyan]{recruiter['email']}[/cyan])")
        else:
            console.print("  [bold][6][/bold] Send email to recruiter [dim](no recruiter saved)[/dim]")
        console.print("  [bold][7][/bold] Back to list")

        action = click.prompt("\nChoose", default="7", show_default=False)

        if action == "1":
            panel_text = (
                f"[bold]Title:[/bold]    {job.title}\n"
                f"[bold]Company:[/bold]  {job.company}\n"
                f"[bold]Location:[/bold] {job.location}\n"
                f"[bold]URL:[/bold]      {job.url}"
            )
            from rich.panel import Panel
            console.print(Panel(panel_text, title="Job Details", border_style="cyan"))

        elif action == "2":
            _adapt_cv_for_job(job)

        elif action == "3":
            _generate_cover_letter_for_job(job)

        elif action == "4":
            open_in_chrome(job.url)
            console.print(f"[green]Opened in Chrome.[/green]")

        elif action == "5":
            _track_application(job, recruiter)

        elif action == "6":
            if not recruiter:
                console.print("[yellow]No recruiter saved for this company.[/yellow]")
            else:
                _send_email_to_recruiter(job, recruiter)

        elif action == "7":
            break

        else:
            console.print("[red]Invalid option.[/red]")


def _track_application(job, recruiter) -> None:
    """Auto-detect context and save application to tracker."""
    import json
    from rich.panel import Panel
    from job_hunter.applications.models import Application
    from job_hunter.applications.tracker import ApplicationTracker

    # --- Auto-detect CV ---
    output_dir = Path("output")
    company_clean = job.company.lower().replace(" ", "_")
    cv_files = list(output_dir.glob(f"cv_{company_clean}*.pdf")) if output_dir.exists() else []
    if not cv_files:
        cv_files = [f for f in output_dir.glob("cv_*.pdf") if company_clean in f.name.lower()] if output_dir.exists() else []
    cv_file = str(max(cv_files, key=lambda p: p.stat().st_mtime)) if cv_files else ""

    # --- Auto-detect cover letter ---
    cl_dir = output_dir / "cover_letters"
    cl_files = list(cl_dir.glob(f"cover_letter_{company_clean}*.txt")) if cl_dir.exists() else []
    if not cl_files:
        cl_files = [f for f in cl_dir.glob("cover_letter_*.txt") if company_clean in f.name.lower()] if cl_dir.exists() else []
    cl_file = str(max(cl_files, key=lambda p: p.stat().st_mtime)) if cl_files else ""

    # --- Recruiter info ---
    recruiter_name = recruiter["name"] if recruiter else ""
    recruiter_email = recruiter["email"] if recruiter else ""

    # --- Check if already tracked ---
    tracker = ApplicationTracker()
    existing = [a for a in tracker.get_all() if a.job_url == job.url]
    if existing:
        a = existing[0]
        console.print(f"[yellow]Already tracked — ID: {a.id}, status: {a.status}[/yellow]")
        return

    # --- Show summary panel ---
    from datetime import datetime, timedelta
    follow_up = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    cv_line = f"[green]{Path(cv_file).name} ✅[/green]" if cv_file else "[red]Not found ❌[/red]"
    cl_line = f"[green]{Path(cl_file).name} ✅[/green]" if cl_file else "[red]Not found ❌[/red]"
    rec_line = f"[green]{recruiter_name} ({recruiter_email}) ✅[/green]" if recruiter_name else "[red]Not saved ❌[/red]"

    console.print(Panel(
        f"[bold]Job:[/bold]          {job.title}\n"
        f"[bold]Company:[/bold]      {job.company}\n"
        f"[bold]Location:[/bold]     {job.location}\n"
        f"[bold]CV:[/bold]           {cv_line}\n"
        f"[bold]Cover letter:[/bold] {cl_line}\n"
        f"[bold]Recruiter:[/bold]    {rec_line}\n"
        f"[bold]Follow-up:[/bold]    {follow_up}",
        title="[cyan]Track Application[/cyan]",
        border_style="cyan",
    ))

    notes = click.prompt("Notes (optional)", default="", show_default=False)

    app = Application(
        job_title=job.title,
        company=job.company,
        location=getattr(job, "location", ""),
        job_url=job.url,
        source=getattr(job, "source", ""),
        cv_file=cv_file,
        cover_letter_file=cl_file,
        recruiter_name=recruiter_name,
        recruiter_email=recruiter_email,
        notes=notes,
    )
    tracker.add(app)

    console.print(Panel(
        f"[bold]ID:[/bold]          {app.id}\n"
        f"[bold]Status:[/bold]      {app.status}\n"
        f"[bold]Follow-up:[/bold]   {app.follow_up_date}",
        title="[green]Application Tracked ✅[/green]",
        border_style="green",
    ))


def _send_email_to_recruiter(job, recruiter) -> None:
    """Open Gmail compose in Chrome with pre-filled email, and prepare CV for attachment."""
    import urllib.parse
    import subprocess
    from pathlib import Path
    from job_hunter.cover_letter.history import CoverLetterHistory

    subject = f"Application for {job.title} position"

    # Use most recent cover letter for this company if available
    history = CoverLetterHistory()
    letters = history.get_by_company(job.company)
    if letters:
        latest = sorted(letters, key=lambda r: r.created_at, reverse=True)[0]
        body = latest.content
    else:
        body = (
            f"Dear {recruiter['name'].split()[0]},\n\n"
            f"I am writing to express my interest in the {job.title} position at {job.company}.\n\n"
            f"Please find my CV attached.\n\n"
            f"Best regards,\n"
            f"Dvir Salomon\n"
            f"Dvir2705@gmail.com | 053-3401466"
        )

    # Open Gmail compose in Chrome
    gmail_url = (
        f"https://mail.google.com/mail/u/0/?view=cm&fs=1"
        f"&to={recruiter['email']}"
        f"&su={urllib.parse.quote(subject)}"
        f"&body={urllib.parse.quote(body)}"
    )
    open_in_chrome(gmail_url)
    console.print(f"[green]Opened Gmail in Chrome — To: {recruiter['email']}[/green]")

    # Find adapted CV for this company
    cv_dir = Path("output")
    if cv_dir.exists():
        # Match CV files: cv_mobileye_*.pdf
        company_clean = job.company.lower().replace(" ", "_")
        cv_files = list(cv_dir.glob(f"cv_{company_clean}*.pdf"))

        if not cv_files:
            # Try partial match
            cv_files = [f for f in cv_dir.glob("cv_*.pdf") if company_clean in f.name.lower()]

        if cv_files:
            # Get most recent
            latest_cv = max(cv_files, key=lambda p: p.stat().st_mtime)

            # Copy path to clipboard
            try:
                subprocess.run(['clip'], input=str(latest_cv.absolute()).encode(), check=True)
                console.print(f"[cyan]CV path copied to clipboard:[/cyan] {latest_cv.name}")
            except Exception:
                pass

            # Open folder with CV selected
            subprocess.run(['explorer', '/select,', str(latest_cv.absolute())])
            console.print(f"[cyan]Opened CV folder — drag file to Gmail to attach[/cyan]")
        else:
            console.print("[yellow]No adapted CV found. Run [2] Adapt CV first.[/yellow]")
    else:
        console.print("[yellow]No CV folder found.[/yellow]")


def _adapt_cv_for_job(job) -> None:
    from job_hunter.jobs.scraper import fetch_job_description
    from job_hunter.cv.adapter import CVAdapter
    from job_hunter.cv.manager import CVManager
    from job_hunter.cv.renderer import CVRenderer
    from job_hunter.config import Config

    # 1. Fetch job description
    console.print(f"\n[dim]Fetching job description from {job.url}...[/dim]")
    try:
        with console.status("Fetching job description..."):
            description = fetch_job_description(job)
    except RuntimeError as e:
        console.print(f"[red]Could not fetch job page: {e}[/red]")
        return

    if not description:
        console.print(
            "[yellow]Job description not available for this source "
            "(page is JavaScript-rendered).\n"
            "Tip: copy the job description text and use [bold]job-hunter cv adapt[/bold] with a file.[/yellow]"
        )
        return

    console.print(f"[dim]Fetched {len(description)} characters of job description.[/dim]")

    # 2. Load base CV and adapt
    cv_manager = CVManager()
    base_cv = cv_manager.load_base()

    with console.status("Adapting CV with Claude..."):
        adapter = CVAdapter()
        adapted = adapter.adapt(base_cv, description, job_title=job.title)

    # 3. Save adapted CV JSON
    company_slug = job.company.lower().replace(" ", "_").replace("/", "_")[:20]
    title_slug = job.title.lower().replace(" ", "_").replace("/", "_")[:25]
    label = f"{company_slug}_{title_slug}"
    json_path = cv_manager.save_version(adapted, label)

    # 4. Render PDF
    renderer = CVRenderer()
    pdf_path = Config.OUTPUT_DIR / f"{json_path.stem}.pdf"
    with console.status("Rendering PDF..."):
        renderer.render_pdf(adapted, pdf_path)

    # 5. Generate change summary
    from job_hunter.cv.change_summary import generate_change_summary
    changes_path = generate_change_summary(
        base_cv=base_cv,
        adapted_cv=adapted,
        job_title=job.title,
        company=job.company,
    )

    # 6. Show result
    from rich.panel import Panel
    console.print(Panel(
        f"[bold]Title:[/bold]    {adapted.get('title', '')}\n"
        f"[bold]JSON:[/bold]     {json_path}\n"
        f"[bold]PDF:[/bold]      {pdf_path}\n"
        f"[bold]Changes:[/bold]  {changes_path}",
        title="[green]CV Adapted[/green]",
        border_style="green",
    ))

    while True:
        console.print("\n[bold cyan]CV adapted! What would you like to do?[/bold cyan]")
        console.print("  [bold][1][/bold] View adapted CV (PDF)")
        console.print("  [bold][2][/bold] View changes summary (what was modified)")
        console.print("  [bold][3][/bold] Back to job menu")

        view_choice = click.prompt("\nChoose", default="3", show_default=False)

        if view_choice == "1":
            if pdf_path and Path(pdf_path).exists():
                open_in_chrome(str(Path(pdf_path).absolute()))
                console.print(f"[green]Opened CV: {pdf_path}[/green]")
            else:
                console.print("[yellow]PDF not found[/yellow]")

        elif view_choice == "2":
            if changes_path and Path(changes_path).exists():
                open_in_chrome(str(Path(changes_path).absolute()))
                console.print(f"[green]Opened changes summary: {changes_path}[/green]")
            else:
                console.print("[yellow]Changes file not found[/yellow]")

        elif view_choice == "3":
            break

        else:
            console.print("[red]Invalid option[/red]")


def _generate_cover_letter_for_job(job) -> None:
    from job_hunter.jobs.scraper import fetch_job_description
    from job_hunter.cv.manager import CVManager
    from job_hunter.cover_letter import CoverLetterGenerator
    from rich.panel import Panel
    import pyperclip

    # 1. Fetch job description
    console.print(f"\n[dim]Fetching job description from {job.url}...[/dim]")
    try:
        with console.status("Fetching job description..."):
            description = fetch_job_description(job)
    except RuntimeError as e:
        console.print(f"[red]Could not fetch job page: {e}[/red]")
        description = None

    if not description:
        console.print(
            "[yellow]Job description unavailable (JS-rendered page). "
            "Generating based on job title and company only.[/yellow]"
        )

    # 2. Load base CV
    cv_manager = CVManager()
    base_cv = cv_manager.load_base()

    # 3. Ask language
    lang_choice = click.prompt(
        "Language",
        type=click.Choice(["en", "he"]),
        default="en",
        show_default=True,
    )

    # 4. Ask recruiter name — pre-fill if we have one saved
    from job_hunter.recruiters.manager import RecruiterManager
    saved_recruiters = RecruiterManager().find_by_company_fuzzy(job.company)
    if saved_recruiters:
        saved_name = saved_recruiters[0]["name"]
        console.print(f"[dim]Found saved recruiter: {saved_name}[/dim]")
        recruiter_raw = click.prompt(
            "Recruiter name (Enter to use saved, type new name, or '-' to skip)",
            default=saved_name,
            show_default=True,
        )
    else:
        recruiter_raw = click.prompt("Recruiter name (Enter to skip)", default="", show_default=False)
    recruiter_name = None if recruiter_raw.strip() in ("", "-") else recruiter_raw.strip()

    # 5. Generate
    with console.status("Generating cover letter with Claude..."):
        generator = CoverLetterGenerator()
        letter = generator.generate(
            job=job,
            cv=base_cv,
            job_description=description,
            language=lang_choice,
            recruiter_name=recruiter_name,
        )

    # 6. Display
    console.print(Panel(letter, title=f"[green]Cover Letter — {job.company}[/green]", border_style="green"))

    # 7. Save / copy options
    console.print("\n  [bold][1][/bold] Save to file")
    console.print("  [bold][2][/bold] Copy to clipboard")
    console.print("  [bold][3][/bold] Both")
    console.print("  [bold][4][/bold] Done")

    post = click.prompt("Choose", default="4", show_default=False)

    if post in ("1", "3"):
        from pathlib import Path
        from job_hunter.config import Config
        import re
        slug = re.sub(r"[^\w]+", "_", f"{job.company}_{job.title}").lower()[:40]
        out_path = Config.OUTPUT_DIR / f"cover_letter_{slug}.txt"
        out_path.write_text(letter, encoding="utf-8")
        console.print(f"[green]Saved to {out_path}[/green]")

    if post in ("2", "3"):
        try:
            pyperclip.copy(letter)
            console.print("[green]Copied to clipboard.[/green]")
        except Exception:
            console.print("[yellow]Could not copy to clipboard (pyperclip may not be installed).[/yellow]")


if __name__ == "__main__":
    cli()
