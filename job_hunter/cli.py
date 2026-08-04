import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from job_hunter.applications.tracker import ApplicationTracker
from job_hunter.config import Config
from job_hunter.cv.manager import CVManager
from job_hunter.profile import (
    UserProfile,
    get_profile,
    profile_exists,
    set_profile_path,
)

console = Console()


def open_in_chrome(url: str) -> None:
    """Open a URL in Google Chrome, falling back to the default browser."""
    import subprocess
    import webbrowser

    try:
        from job_hunter.cv.renderer import _find_chrome

        chrome = _find_chrome()
        subprocess.Popen([chrome, url])
    except (RuntimeError, FileNotFoundError):
        webbrowser.open(url)


@click.group()
@click.version_option(package_name="job-hunter")
@click.option(
    "--profile-path",
    type=click.Path(exists=True),
    default=None,
    help="Path to a custom user_profile.json file.",
)
@click.option(
    "--user",
    default=None,
    envvar="JOB_HUNTER_USER",
    help="User ID for per-user data isolation (env: JOB_HUNTER_USER).",
)
def cli(profile_path, user):
    """Job Hunter — personal career bot powered by Claude AI."""
    from job_hunter.profile_manager import (
        get_active_profile,
        has_legacy_profile,
        migrate_legacy_profile,
    )

    if user:
        Config.set_user(user)
    elif not profile_path:
        # Auto-activate: .active_profile > legacy migration > single-user
        active = get_active_profile()
        if active:
            Config.set_user(active)
        elif has_legacy_profile():
            slug = migrate_legacy_profile("default")
            Config.set_user(slug)
            console.print(
                f"[dim]Migrated profile to multi-user mode (profile: {slug})[/dim]"
            )
    Config.ensure_dirs()
    if profile_path:
        set_profile_path(Path(profile_path))


def require_profile(f):
    """Decorator that aborts with a helpful message if profile is missing."""
    import functools

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not profile_exists():
            console.print(
                "[red]Profile not found.[/red] "
                "Run [bold]job-hunter init[/bold] to get started."
            )
            sys.exit(1)
        return f(*args, **kwargs)

    return wrapper


@cli.command()
@click.option(
    "--from-cv",
    type=click.Path(exists=True),
    default=None,
    help="Path to existing CV JSON to pre-fill profile fields.",
)
@click.option(
    "--name",
    "profile_name",
    default=None,
    help="Profile name (slug). Prompted if not given.",
)
def init(from_cv, profile_name):
    """Set up your profile — required before using other commands."""
    import json as _json

    from job_hunter.profile_manager import (
        list_profiles,
        set_active_profile,
        slugify,
    )
    from job_hunter.profile_manager import (
        profile_exists as pm_profile_exists,
    )

    # Show existing profiles if any
    existing = list_profiles()
    if existing:
        console.print("[bold]Existing profiles:[/bold]")
        for p in existing:
            marker = " [green](active)[/green]" if p["active"] else ""
            console.print(f"  • {p['slug']} — {p['name']}{marker}")
        console.print()

    prefill = {}
    if from_cv:
        with open(from_cv, encoding="utf-8") as f:
            cv_data = _json.load(f)
        prefill["name"] = cv_data.get("name", "")
        prefill["email"] = cv_data.get("email", "")
        prefill["phone"] = cv_data.get("phone", "")
        prefill["university"] = cv_data.get("education", [{}])[0].get("institution", "")
        prefill["degree"] = cv_data.get("education", [{}])[0].get("degree", "")
        skills_data = cv_data.get("skills", [])
        if isinstance(skills_data, dict):
            # Categorized: {"programming": [...], "technical": [...], "tools": [...]}
            prefill["skills"] = [
                s for cat in skills_data.values() for s in cat if isinstance(s, str)
            ]
        elif isinstance(skills_data, list) and skills_data:
            if isinstance(skills_data[0], dict):
                prefill["skills"] = [s.get("name", str(s)) for s in skills_data]
            else:
                prefill["skills"] = skills_data
        # Also extract project technologies
        for proj in cv_data.get("projects", []):
            prefill.setdefault("skills", []).extend(proj.get("technologies", []))
        # Deduplicate while preserving order
        if prefill.get("skills"):
            prefill["skills"] = list(dict.fromkeys(prefill["skills"]))
        if prefill.get("name"):
            console.print(f"[green]Pre-filled from CV:[/green] {prefill['name']}")

    console.print("[bold]Welcome to Job Hunter![/bold] Let's set up your profile.")
    console.print(
        "[dim]Type 'back' at any prompt to return to the previous question.[/dim]\n"
    )

    class GoBack(Exception):
        """Raised when user types 'back' to return to previous step."""

    def _check_back(value: str) -> str:
        """Raise GoBack if the user typed 'back'."""
        if value.strip().lower() == "back":
            raise GoBack()
        return value

    def _prompt_required(label: str, default: str = "") -> str:
        """Prompt until a non-empty value is given. Raises GoBack on 'back'."""
        while True:
            value = _check_back(click.prompt(label, default=default)).strip()
            if value:
                return value
            console.print("[yellow]This field is required.[/yellow]")

    # Collect answers in a dict so steps can read/write them
    answers = {
        "name": prefill.get("name", ""),
        "email": prefill.get("email", ""),
        "phone": prefill.get("phone", ""),
        "target_positions": [],
        "skills": prefill.get("skills", []),
        "exp_level": "none",
        "country": "Israel",
        "cities": [],
        "radius_km": 25,
        "education": {},
    }

    def step_name():
        answers["name"] = _prompt_required("1. Full name", default=answers["name"])

    def step_email():
        answers["email"] = _prompt_required("2. Email", default=answers["email"])

    def step_phone():
        val = _check_back(
            click.prompt(
                "3. Phone number (optional, Enter to skip)",
                default=answers["phone"],
            )
        )
        answers["phone"] = val

    def step_target_roles():
        while True:
            val = _check_back(
                click.prompt(
                    "4. Target roles (comma-separated, e.g. software developer, DSP engineer)",
                    default=(
                        ", ".join(answers["target_positions"])
                        if answers["target_positions"]
                        else ""
                    ),
                )
            )
            positions = [t.strip() for t in val.split(",") if t.strip()]
            if positions:
                answers["target_positions"] = positions
                return
            console.print("[yellow]At least one target role is required.[/yellow]")

    def step_skills():
        val = _check_back(
            click.prompt(
                "5. Key skills (comma-separated, e.g. Python, MATLAB, SolidWorks)",
                default=", ".join(answers["skills"]),
            )
        )
        answers["skills"] = [s.strip() for s in val.split(",") if s.strip()]

    def step_experience():
        val = _check_back(
            click.prompt(
                "6. Experience level (none / 1-3 / 3-7 / 7+)",
                default=answers["exp_level"],
            )
        )
        val = val.strip().lower()
        if val not in ("none", "1-3", "3-7", "7+"):
            console.print("[yellow]Please enter one of: none, 1-3, 3-7, 7+[/yellow]")
            step_experience()  # retry same step (GoBack still propagates)
            return
        answers["exp_level"] = val

    def step_country():
        val = _check_back(click.prompt("7. Country", default=answers["country"]))
        answers["country"] = val.strip() or "Israel"

    def step_cities():
        val = _check_back(
            click.prompt(
                "8. Cities to search around (comma-separated, or Enter for country-wide)",
                default=", ".join(answers["cities"]) if answers["cities"] else "",
            )
        )
        answers["cities"] = [c.strip() for c in val.split(",") if c.strip()]

    def step_radius():
        # Only ask if cities were given; otherwise skip silently
        if not answers["cities"]:
            answers["radius_km"] = 25
            return
        val = _check_back(
            click.prompt(
                "9. Search radius around cities (km, 10/25/50)",
                default=str(answers["radius_km"]),
            )
        )
        val = val.strip()
        if val not in ("10", "25", "50"):
            console.print("[yellow]Please enter 10, 25, or 50.[/yellow]")
            step_radius()
            return
        answers["radius_km"] = int(val)

    def step_education():
        if answers["exp_level"] != "none":
            answers["education"] = {}
            return
        val = (
            _check_back(
                click.prompt(
                    "Are you currently studying? (y/n)",
                    default="y",
                )
            )
            .strip()
            .lower()
        )
        if val in ("y", "yes"):
            degree = _check_back(
                click.prompt(
                    "Degree (e.g. B.Sc. Electrical Engineering)",
                    default=answers.get("education", {}).get(
                        "degree", prefill.get("degree", "")
                    ),
                )
            )
            university = _check_back(
                click.prompt(
                    "University",
                    default=answers.get("education", {}).get(
                        "university", prefill.get("university", "")
                    ),
                )
            )
            year = _check_back(
                click.prompt(
                    "Year of study (1st / 2nd / 3rd / 4th)",
                    default=answers.get("education", {}).get(
                        "year", prefill.get("year", "")
                    ),
                )
            ).strip()
            answers["education"] = {
                "university": university,
                "degree": degree,
                "year": year,
            }
        else:
            answers["education"] = {}

    steps = [
        step_name,
        step_email,
        step_phone,
        step_target_roles,
        step_skills,
        step_experience,
        step_country,
        step_cities,
        step_radius,
        step_education,
    ]

    i = 0
    while i < len(steps):
        try:
            steps[i]()
            i += 1
        except GoBack:
            if i > 0:
                i -= 1
                console.print("[dim]<< Going back...[/dim]")
            else:
                console.print("[dim]Already at the first question.[/dim]")

    location = {
        "country": answers["country"],
        "cities": answers["cities"],
        "radius_km": answers["radius_km"],
    }
    education = answers["education"]

    # --- Derive domains from target_positions + skills -----------------------
    target_positions = answers["target_positions"]
    skills = answers["skills"]
    domains = list(
        {
            token.lower()
            for item in target_positions + skills
            for token in item.split()
            if len(token) > 2
        }
    )

    profile = UserProfile(
        name=answers["name"],
        email=answers["email"],
        phone=answers["phone"],
        target_positions=target_positions,
        skills=skills,
        experience_level=answers["exp_level"],
        location=location,
        education=education,
        domains=domains,
    )

    # --- Summary + confirmation ---------------------------------------------
    from rich.panel import Panel

    summary_lines = [
        f"[bold]Name:[/bold]       {profile.name}",
        f"[bold]Email:[/bold]      {profile.email}",
        f"[bold]Phone:[/bold]      {profile.phone or '(not set)'}",
        f"[bold]Roles:[/bold]      {', '.join(profile.target_positions)}",
        f"[bold]Skills:[/bold]     {', '.join(profile.skills) or '(none)'}",
        f"[bold]Experience:[/bold] {profile.experience_level}",
        f"[bold]Location:[/bold]   {location.get('country', '')}",
    ]
    if education:
        summary_lines.append(
            f"[bold]Education:[/bold]  {education.get('degree', '')} @ {education.get('university', '')}"
        )
    console.print(
        Panel("\n".join(summary_lines), title="Profile Summary", border_style="blue")
    )

    if not click.confirm("Save this profile?", default=True):
        console.print("Aborted — run [bold]job-hunter init[/bold] again to start over.")
        return

    # --- Profile name (slug) -------------------------------------------------
    default_slug = slugify(answers["name"])
    if not profile_name:
        profile_name = click.prompt(
            "Profile name (used to switch between profiles)",
            default=default_slug,
        )
    slug = slugify(profile_name)
    if slug != profile_name.lower().strip():
        console.print(f"[dim]Using slug: {slug}[/dim]")

    if pm_profile_exists(slug):
        if not click.confirm(
            f"Profile '{slug}' already exists. Overwrite?", default=False
        ):
            console.print("Aborted.")
            return

    # Switch Config to the new profile directory and save
    Config.set_user(slug)
    Config.ensure_dirs()
    profile_path = Config.DATA_DIR / "user_profile.json"
    profile.save(profile_path)
    set_active_profile(slug)

    # --- Company suggestions via Haiku ------------------------------------
    if not Config.ANTHROPIC_API_KEY:
        console.print(
            "\n[yellow]No API key found.[/yellow] Company suggestions require "
            "ANTHROPIC_API_KEY in your .env file.\n"
            "[dim]You can add companies later with "
            "[bold]job-hunter companies add[/bold][/dim]"
        )
        suggestions = {"registry": [], "additional": []}
    else:
        console.print("\n[dim]Finding relevant companies to watch...[/dim]")
        try:
            from job_hunter.jobs.search_strategy import suggest_companies

            suggestions = suggest_companies(profile)
        except Exception:
            suggestions = {"registry": [], "additional": []}

    has_suggestions = suggestions["registry"] or suggestions["additional"]
    if has_suggestions:
        if suggestions["registry"]:
            console.print("\n[bold]Companies we can scan for you:[/bold]")
            for name in suggestions["registry"]:
                console.print(f"  [green]\u2713[/green] {name}")

        if suggestions["additional"]:
            console.print("\n[bold]Also relevant (general search only):[/bold]")
            for name in suggestions["additional"]:
                console.print(f"  [blue]+[/blue] {name}")

        if click.confirm("\nAdd these to your watchlist?", default=True):
            profile.watchlist = suggestions["registry"] + suggestions["additional"]
            remove_input = click.prompt(
                "Remove any? (comma-separated names, or Enter to keep all)",
                default="",
            )
            if remove_input.strip():
                to_remove = {r.strip().lower() for r in remove_input.split(",")}
                profile.watchlist = [
                    c for c in profile.watchlist if c.lower() not in to_remove
                ]
            profile.save(profile_path)
            console.print(
                f"[green]Watchlist saved: {len(profile.watchlist)} companies[/green]"
            )
        else:
            console.print(
                "[dim]Skipped — you can add companies later with "
                "[bold]jobs companies add[/bold][/dim]"
            )
    else:
        console.print(
            "[dim]No company suggestions available — you can add "
            "companies later with [bold]jobs companies add[/bold][/dim]"
        )

    console.print(f"\n[green]Profile '{slug}' saved to {profile_path}[/green]")

    # --- CV import (optional) -----------------------------------------------
    cv_imported = False
    if from_cv:
        # --from-cv provided a JSON used for pre-fill; offer to save as base CV
        if click.confirm("\nSave the provided CV JSON as your base CV?", default=True):
            from job_hunter.cv.manager import CVManager

            manager = CVManager()
            cv_path = manager.save_base(cv_data)
            console.print(f"[green]Base CV saved to {cv_path}[/green]")
            cv_imported = True

    if not cv_imported:
        if click.confirm(
            "\nDo you have a CV to import? (docx, pdf, or json)", default=False
        ):
            while True:
                cv_file_input = (
                    click.prompt("Path to your CV file").strip().strip('"').strip("'")
                )
                cv_file_path = Path(cv_file_input)
                if not cv_file_path.exists():
                    console.print(
                        "[yellow]File not found. Please check the path.[/yellow]"
                    )
                    continue
                if cv_file_path.suffix.lower() not in (".docx", ".pdf", ".json"):
                    console.print(
                        "[yellow]Unsupported format. Use .docx, .pdf, or .json[/yellow]"
                    )
                    continue
                break

            suffix = cv_file_path.suffix.lower()
            needs_api = suffix in (".docx", ".pdf")

            if needs_api and not Config.ANTHROPIC_API_KEY:
                console.print(
                    "[yellow]CV structuring requires ANTHROPIC_API_KEY.[/yellow]\n"
                    "Set it in your .env file, then run: "
                    "[bold]job-hunter cv init --from-file "
                    + str(cv_file_path)
                    + "[/bold]"
                )
            else:
                console.print(f"[dim]Importing {cv_file_path.name}...[/dim]")
                try:
                    from job_hunter.cv.manager import CVManager
                    from job_hunter.cv.parser import parse_cv_file

                    structured = parse_cv_file(cv_file_path)
                    if structured is None:
                        console.print("[red]Failed to parse CV.[/red]")
                    else:
                        manager = CVManager()
                        saved_path = manager.save_base(structured)
                        console.print(f"[green]Base CV saved to {saved_path}[/green]")
                        # Copy original file as template
                        if suffix == ".docx":
                            import shutil as _shutil

                            template_path = Config.CV_DIR / "base_cv.docx"
                            template_path.parent.mkdir(parents=True, exist_ok=True)
                            _shutil.copy2(str(cv_file_path), str(template_path))
                            console.print(
                                f"[green]Original docx saved as template: {template_path}[/green]"
                            )
                        elif suffix == ".pdf":
                            import shutil as _shutil

                            template_path = Config.CV_DIR / "base_cv.pdf"
                            template_path.parent.mkdir(parents=True, exist_ok=True)
                            _shutil.copy2(str(cv_file_path), str(template_path))
                            console.print(
                                f"[green]Original PDF saved as reference: {template_path}[/green]"
                            )
                        cv_imported = True
                except Exception as e:
                    console.print(f"[red]CV import failed: {e}[/red]")
                    console.print(
                        "[dim]You can import later with: [bold]job-hunter cv init --from-file <cv>[/bold][/dim]"
                    )

    console.print()
    console.print("[bold]What to do next:[/bold]")
    if not cv_imported:
        console.print(
            "  1. [bold]job-hunter cv init --from-file <cv>[/bold]  — Upload your CV (docx or JSON)"
        )
    console.print(
        f"  {'1' if cv_imported else '2'}. [bold]job-hunter profile show[/bold]              — Review your profile"
    )
    console.print(
        f"  {'2' if cv_imported else '3'}. [bold]job-hunter jobs scan[/bold]                 — Find matching jobs"
    )
    console.print(
        "\n[dim]To switch profiles later: [bold]job-hunter profile switch <name>[/bold][/dim]"
    )
    if not Config.ANTHROPIC_API_KEY:
        console.print()
        console.print(
            "[yellow]Tip:[/yellow] Set ANTHROPIC_API_KEY in your .env file to enable "
            "AI features (CV adaptation, job matching)."
        )


# ---------------------------------------------------------------------------
# Profile commands
# ---------------------------------------------------------------------------


@cli.group()
def profile():
    """View and manage your profile."""


@profile.command("enrich")
@require_profile
def profile_enrich():
    """Pull skills from your CV into the profile for better job matching."""
    import json as _json

    cv_path = Config.CV_DIR / "base_cv.json"
    if not cv_path.exists():
        console.print(
            "[red]No CV found.[/red] Run [bold]job-hunter cv init[/bold] first."
        )
        return

    with open(cv_path, encoding="utf-8") as f:
        cv_data = _json.load(f)

    # Extract skills from CV (categorized dict + flat list + project techs)
    cv_skills = []
    skills_data = cv_data.get("skills", [])
    if isinstance(skills_data, dict):
        cv_skills = [
            s for cat in skills_data.values() for s in cat if isinstance(s, str)
        ]
    elif isinstance(skills_data, list) and skills_data:
        if isinstance(skills_data[0], dict):
            cv_skills = [s.get("name", str(s)) for s in skills_data]
        else:
            cv_skills = list(skills_data)

    for proj in cv_data.get("projects", []):
        cv_skills.extend(proj.get("technologies", []))

    # Deduplicate
    cv_skills = list(dict.fromkeys(cv_skills))

    prof = get_profile()
    current_lower = {s.lower() for s in prof.skills}
    new_skills = [s for s in cv_skills if s.lower() not in current_lower]

    if not new_skills:
        console.print("[green]Profile already has all CV skills.[/green]")
        return

    console.print(f"[bold]Current profile skills:[/bold] {', '.join(prof.skills)}")
    console.print(f"[bold]New from CV:[/bold] {', '.join(new_skills)}")

    if not click.confirm(f"Add {len(new_skills)} skills to profile?", default=True):
        console.print("Skipped.")
        return

    prof.skills.extend(new_skills)
    # Clear cached queries so they regenerate with richer skills
    prof.search_config = {}
    prof.save()
    # Reset cached profile so next get_profile() reloads
    import job_hunter.profile as _prof_mod

    _prof_mod._profile = None

    console.print(f"[green]Profile updated with {len(new_skills)} new skills.[/green]")
    console.print("[dim]Search queries will regenerate on next scan.[/dim]")


@profile.command("show")
@require_profile
def profile_show():
    """Display your current profile."""
    from rich.panel import Panel

    prof = get_profile()

    lines = []

    # Contact
    lines.append("[bold underline]Contact[/bold underline]")
    lines.append(f"  Name:     {prof.name}")
    lines.append(f"  Email:    {prof.email}")
    lines.append(f"  Phone:    {prof.phone}")
    if prof.linkedin:
        lines.append(f"  LinkedIn: {prof.linkedin}")
    if prof.github:
        lines.append(f"  GitHub:   {prof.github}")
    if prof.country or prof.cities:
        loc_parts = []
        if prof.cities:
            loc_parts.append(", ".join(prof.cities))
        if prof.country:
            loc_parts.append(prof.country)
        lines.append(f"  Location: {' — '.join(loc_parts)}")

    # Education
    if prof.education and any(prof.education.values()):
        lines.append("")
        lines.append("[bold underline]Education[/bold underline]")
        if prof.degree:
            lines.append(f"  Degree:  {prof.degree}")
        if prof.specialization:
            lines.append(f"  Major:   {prof.specialization}")
        if prof.university:
            lines.append(f"  School:  {prof.university}")
        if prof.year:
            lines.append(f"  Year:    {prof.year}")

    # Experience level
    if prof.experience_level:
        lines.append("")
        lines.append("[bold underline]Experience Level[/bold underline]")
        lines.append(f"  {prof.experience_level} years")

    # Skills
    if prof.skills:
        lines.append("")
        lines.append("[bold underline]Skills[/bold underline]")
        lines.append(f"  {', '.join(prof.skills)}")
    if prof.skills_not:
        lines.append(f"  [dim]Excluded: {', '.join(prof.skills_not)}[/dim]")

    # Target positions & domains
    if prof.target_positions:
        lines.append("")
        lines.append("[bold underline]Target Positions[/bold underline]")
        lines.append(f"  {', '.join(prof.target_positions)}")
    if prof.domains:
        lines.append("")
        lines.append("[bold underline]Domains[/bold underline]")
        lines.append(f"  {', '.join(prof.domains)}")

    # Watchlist
    if prof.watchlist:
        lines.append("")
        lines.append("[bold underline]Watchlist[/bold underline]")
        lines.append(f"  {', '.join(prof.watchlist)}")

    # Hard rules
    if prof.hard_rules:
        lines.append("")
        lines.append("[bold underline]Hard Rules[/bold underline]")
        for k, v in prof.hard_rules.items():
            lines.append(f"  {k}: {v}")

    console.print(Panel("\n".join(lines), title="Your Profile", border_style="blue"))


@profile.command("validate")
@require_profile
def profile_validate():
    """Check your profile for errors and warnings."""
    prof = get_profile()
    issues = prof.validate()

    if not issues:
        console.print("[green]Profile is valid — no issues found.[/green]")
        return

    for issue in issues:
        if issue.startswith("[ERROR]"):
            console.print(f"[red]{issue}[/red]")
        else:
            console.print(f"[yellow]{issue}[/yellow]")

    if any(i.startswith("[ERROR]") for i in issues):
        sys.exit(1)


@profile.command("edit")
@require_profile
def profile_edit():
    """Interactively edit profile fields."""
    import job_hunter.profile as _prof_mod

    prof = get_profile()

    EDITABLE = [
        ("name", "Name", "str"),
        ("email", "Email", "str"),
        ("phone", "Phone", "str"),
        ("target_positions", "Target positions", "list"),
        ("skills", "Skills", "list"),
        ("skills_not", "Excluded skills", "list"),
        ("domains", "Domains", "list"),
        ("experience_level", "Experience level (none/1-3/3-7/7+)", "str"),
        ("watchlist", "Watchlist (companies)", "list"),
        ("linkedin", "LinkedIn", "str"),
        ("github", "GitHub", "str"),
    ]

    while True:
        console.print("\n[bold]Which field to edit?[/bold]")
        for i, (_, label, kind) in enumerate(EDITABLE, 1):
            field_name = EDITABLE[i - 1][0]
            current = getattr(prof, field_name)
            if isinstance(current, list):
                display = ", ".join(current) if current else "[dim]empty[/dim]"
            else:
                display = current or "[dim]empty[/dim]"
            console.print(f"  {i}. {label}: {display}")
        console.print("  0. Done")

        choice = click.prompt("Choice", type=int, default=0)
        if choice == 0:
            break
        if choice < 1 or choice > len(EDITABLE):
            console.print("[red]Invalid choice.[/red]")
            continue

        field_name, label, kind = EDITABLE[choice - 1]
        current = getattr(prof, field_name)

        if kind == "list":
            console.print(f"  Current: {', '.join(current) if current else '(empty)'}")
            raw = click.prompt(
                f"  New {label} (comma-separated, empty to clear)", default=""
            )
            new_val = [s.strip() for s in raw.split(",") if s.strip()] if raw else []
            setattr(prof, field_name, new_val)
        else:
            new_val = click.prompt(f"  New {label}", default=current or "")
            setattr(prof, field_name, new_val)

        prof.save()
        _prof_mod._profile = None  # invalidate cache
        prof = get_profile()
        console.print("[green]Saved.[/green]")

    console.print("[green]Done editing profile.[/green]")


@profile.command("list")
def profile_list():
    """List all profiles."""
    from job_hunter.profile_manager import list_profiles as pm_list

    profiles = pm_list()
    if not profiles:
        console.print(
            "[dim]No profiles found. Run [bold]job-hunter init[/bold] to create one.[/dim]"
        )
        return

    table = Table(title="Profiles")
    table.add_column("", style="green", width=3)
    table.add_column("Slug", style="bold")
    table.add_column("Name")
    table.add_column("Email")
    table.add_column("Target Roles")

    for p in profiles:
        marker = "*" if p["active"] else ""
        roles = ", ".join(p["target_positions"][:3])
        table.add_row(marker, p["slug"], p["name"], p["email"], roles)

    console.print(table)
    console.print("[dim]* = active profile[/dim]")


@profile.command("current")
def profile_current():
    """Show the active profile name."""
    from job_hunter.profile_manager import get_active_profile

    active = get_active_profile()
    if active:
        console.print(f"Active profile: [bold]{active}[/bold]")
    else:
        console.print(
            "[dim]No active profile. Run [bold]job-hunter init[/bold] to create one.[/dim]"
        )


@profile.command("switch")
@click.argument("name")
def profile_switch(name):
    """Switch to a different profile."""
    from job_hunter.profile_manager import (
        get_active_profile,
        set_active_profile,
    )
    from job_hunter.profile_manager import (
        profile_exists as pm_exists,
    )

    if not pm_exists(name):
        console.print(f"[red]Profile '{name}' not found.[/red]")
        console.print(
            "[dim]Run [bold]job-hunter profile list[/bold] to see available profiles.[/dim]"
        )
        return

    current = get_active_profile()
    if current == name:
        console.print(f"[dim]Already on profile '{name}'.[/dim]")
        return

    set_active_profile(name)
    console.print(f"[green]Switched to profile '{name}'.[/green]")


@profile.command("delete")
@click.argument("name")
def profile_delete(name):
    """Delete a profile and all its data."""
    from job_hunter.profile_manager import delete_profile as pm_delete
    from job_hunter.profile_manager import get_active_profile

    active = get_active_profile()
    if name == active:
        console.print(
            f"[red]Cannot delete the active profile '{name}'.[/red] "
            "Switch to another profile first."
        )
        return

    if not click.confirm(
        f"Delete profile '{name}' and ALL its data? This cannot be undone",
        default=False,
    ):
        console.print("Aborted.")
        return

    try:
        pm_delete(name)
        console.print(f"[green]Profile '{name}' deleted.[/green]")
    except FileNotFoundError:
        console.print(f"[red]Profile '{name}' not found.[/red]")


# ---------------------------------------------------------------------------
# CV commands
# ---------------------------------------------------------------------------


@cli.group()
def cv():
    """Manage and adapt your CV."""


@cv.command("init")
@click.option(
    "--from-file",
    "from_file",
    type=click.Path(exists=True),
    default=None,
    help="Path to existing CV file (.docx, .pdf, or .json) to import.",
)
def cv_init(from_file):
    """Initialize a base CV — from scratch or by importing a docx/pdf/json file."""
    import shutil

    manager = CVManager()

    if not from_file:
        path = manager.init_base()
        console.print(f"[green]Base CV created at {path}[/green]")
        console.print("Edit it with: [bold]job-hunter cv edit[/bold]")
        return

    from_path = Path(from_file)
    suffix = from_path.suffix.lower()

    if suffix == ".docx":
        # Step 1: Parse docx and detect sections
        from job_hunter.cv.docx_parser import extract_section_text, parse_docx

        console.print(f"Parsing [bold]{from_path.name}[/bold]...")
        doc, section_map = parse_docx(from_path)

        # Step 2: Show detected sections
        console.print("\n[bold]Detected sections in your CV:[/bold]")
        idx = 1
        if section_map.header:
            header_text = extract_section_text(doc, section_map.header)
            preview = header_text[:80].replace("\n", " ")
            console.print(f"  {idx}. [cyan][header][/cyan] — {preview}")
            idx += 1
        if section_map.contact:
            contact_text = extract_section_text(doc, section_map.contact)
            preview = contact_text[:80].replace("\n", " | ")
            console.print(f"  {idx}. [cyan][contact][/cyan] — {preview}")
            idx += 1
        for s in section_map.sections:
            text = extract_section_text(doc, s)
            line_count = len(text.splitlines())
            console.print(
                f'  {idx}. [cyan][{s.semantic_type}][/cyan] "{s.name}" '
                f"— {line_count} lines"
            )
            idx += 1

        if section_map.unmapped_paras:
            console.print(
                f"  [yellow]{len(section_map.unmapped_paras)} unmapped paragraphs[/yellow]"
            )

        # Step 3: User confirms
        if not click.confirm("\nSections look correct?", default=True):
            console.print(
                "[yellow]Aborted.[/yellow] Fix your docx headings and try again."
            )
            return

        # Step 4: Send to Claude for JSON structuring
        console.print("\nStructuring CV with Claude...")
        from job_hunter.cv.parser import parse_cv_file

        structured = parse_cv_file(from_path)
        if structured is None:
            console.print(
                "[red]Failed to structure CV.[/red] Make sure ANTHROPIC_API_KEY is set in your .env file."
            )
            return

        # Step 5: Save structured JSON as base_cv.json
        cv_path = manager.save_base(structured)
        console.print(f"[green]Base CV saved to {cv_path}[/green]")

        # Step 6: Copy original docx as template for Track 2
        template_path = Config.CV_DIR / "base_cv.docx"
        template_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(from_path), str(template_path))
        console.print(
            f"[green]Original docx saved as template: {template_path}[/green]"
        )

    elif suffix == ".pdf":
        from job_hunter.cv.parser import parse_cv_file, parse_pdf_text

        console.print(f"Extracting text from [bold]{from_path.name}[/bold]...")
        try:
            raw_text = parse_pdf_text(from_path)
        except Exception as e:
            console.print(f"[red]Failed to read PDF: {e}[/red]")
            return

        if not raw_text.strip():
            console.print(
                "[red]Could not extract text from PDF.[/red] The file may be image-based — try a .docx instead."
            )
            return

        # Show preview of extracted text
        preview_lines = raw_text.splitlines()[:15]
        console.print("\n[bold]Extracted text preview:[/bold]")
        for line in preview_lines:
            console.print(f"  {line}")
        if len(raw_text.splitlines()) > 15:
            console.print(
                f"  [dim]... ({len(raw_text.splitlines())} lines total)[/dim]"
            )

        if not click.confirm("\nText extracted correctly?", default=True):
            console.print(
                "[yellow]Aborted.[/yellow] Try converting your PDF to .docx for better results."
            )
            return

        console.print("\nStructuring CV with Claude...")
        structured = parse_cv_file(from_path)
        if structured is None:
            console.print(
                "[red]Failed to structure CV.[/red] Make sure ANTHROPIC_API_KEY is set in your .env file."
            )
            return

        cv_path = manager.save_base(structured)
        console.print(f"[green]Base CV saved to {cv_path}[/green]")

        # Save original PDF for reference
        template_path = Config.CV_DIR / "base_cv.pdf"
        template_path.parent.mkdir(parents=True, exist_ok=True)
        import shutil as _shutil

        _shutil.copy2(str(from_path), str(template_path))
        console.print(
            f"[green]Original PDF saved as reference: {template_path}[/green]"
        )

    elif suffix == ".json":
        from job_hunter.cv.parser import parse_cv_file

        structured = parse_cv_file(from_path)
        if structured is None:
            console.print("[red]Failed to parse CV JSON.[/red]")
            return
        cv_path = manager.save_base(structured)
        console.print(f"[green]Base CV saved to {cv_path}[/green]")

    else:
        console.print(
            f"[red]Unsupported file format: {suffix}. Use .docx, .pdf, or .json[/red]"
        )
        return

    console.print()
    console.print("[bold]What to do next:[/bold]")
    console.print(
        "  [bold]job-hunter cv adapt -u <job-url>[/bold]  — Adapt CV for a specific job"
    )
    console.print(
        "  [bold]job-hunter cv show[/bold]                — Preview your base CV"
    )


@cv.command("show")
@click.option(
    "--version",
    "-v",
    default=None,
    help="CV version filename to show (default: base CV)",
)
@require_profile
def cv_show(version):
    """Display the current base CV."""
    manager = CVManager()
    data = manager.load_version(version) if version else manager.load_base()
    import json

    console.print_json(json.dumps(data))


@cv.command("adapt")
@click.option(
    "--url",
    "-u",
    default=None,
    help="Job listing URL (fetches description automatically).",
)
@click.option(
    "--desc", "-d", default=None, help="Path to a file containing the job description."
)
@click.option("--job-title", "-t", default="", help="Job title.")
@click.option("--company", "-c", default="", help="Company name.")
@click.option("--label", "-l", default="", help="Label for the saved CV version.")
@click.option(
    "--lang",
    default=None,
    type=click.Choice(["en", "he"]),
    help="Output language (default: auto-detect from base CV).",
)
@require_profile
def cv_adapt(url, desc, job_title, company, label, lang, **_kwargs):
    """Adapt your CV for a specific job using Claude AI."""
    import re

    from job_hunter.cv.adapter import CVAdapter
    from job_hunter.cv.change_summary import generate_change_summary
    from job_hunter.cv.renderer import CVRenderer
    from job_hunter.jobs.analyzer import JobAnalyzer

    # --- 1. Get job description ---
    if url and desc:
        console.print("[red]Use --url or --desc, not both.[/red]")
        sys.exit(1)
    if not url and not desc:
        console.print("[red]Provide --url <job-url> or --desc <file>.[/red]")
        sys.exit(1)

    if url:
        from job_hunter.jobs.scraper import JobListing, fetch_job_description

        stub = JobListing(
            title=job_title or "Unknown",
            company=company or "Unknown",
            location="",
            url=url,
        )
        with console.status("Fetching job description..."):
            job_description = fetch_job_description(stub)
        if not job_description:
            console.print(
                "[red]Could not fetch job description from URL.[/red]\n"
                "[yellow]Tip: copy the text manually and use --desc <file> instead.[/yellow]"
            )
            sys.exit(1)
        console.print(f"[dim]Fetched {len(job_description)} characters.[/dim]")
    else:
        desc_path = Path(desc)
        if not desc_path.exists():
            console.print(f"[red]File not found: {desc}[/red]")
            sys.exit(1)
        job_description = desc_path.read_text(encoding="utf-8")

    # --- 2. Analyze job requirements ---
    requirements = None
    with console.status("Analyzing job requirements..."):
        analyzer = JobAnalyzer()
        requirements = analyzer.analyze(
            job_title=job_title,
            company=company,
            location="",
            description=job_description,
        )

    if requirements:
        req_skills = (
            ", ".join(requirements.required_skills)
            if requirements.required_skills
            else "none listed"
        )
        console.print(
            f"[dim]Detected: [bold]{requirements.domain}[/bold] role requiring {req_skills}.[/dim]"
        )
        if not job_title:
            job_title = requirements.title
        if not company:
            company = requirements.company

    # --- 3. Adapt CV ---
    manager = CVManager()
    base_cv = manager.load_base()

    # Auto-detect language from base CV if not specified
    if lang is None:
        from job_hunter.cv.adapter import detect_cv_language

        lang = detect_cv_language(base_cv)
        console.print(f"[dim]Auto-detected CV language: {lang}[/dim]")

    with console.status("Adapting CV with Claude..."):
        adapter = CVAdapter()
        if requirements:
            adapted = adapter.adapt_with_requirements(base_cv, requirements, lang=lang)
        else:
            adapted = adapter.adapt(base_cv, job_description, job_title, lang=lang)

    if not adapted:
        console.print("[red]CV adaptation failed (API error).[/red]")
        sys.exit(1)

    # --- 4. Save JSON + render PDF + generate diff ---
    if not label:
        company_slug = (
            re.sub(r"[^\w]+", "_", company).lower()[:20] if company else "job"
        )
        title_slug = (
            re.sub(r"[^\w]+", "_", job_title).lower()[:25] if job_title else "adapted"
        )
        label = f"{company_slug}_{title_slug}"

    json_path = manager.save_version(adapted, label)

    renderer = CVRenderer()
    pdf_path = Config.CV_OUTPUT_DIR / f"{json_path.stem}.pdf"
    with console.status("Rendering PDF..."):
        renderer.render_pdf(adapted, pdf_path, lang=lang)

    diff_path = generate_change_summary(
        base_cv=base_cv,
        adapted_cv=adapted,
        job_title=job_title,
        company=company,
    )

    # --- 5. Show results ---
    from rich.panel import Panel

    console.print(
        Panel(
            f"[bold]Title:[/bold]    {adapted.get('title', '')}\n"
            f"[bold]JSON:[/bold]     {json_path}\n"
            f"[bold]PDF:[/bold]      {pdf_path}\n"
            f"[bold]Changes:[/bold]  {diff_path}",
            title="[green]CV Adapted[/green]",
            border_style="green",
        )
    )

    open_in_chrome(str(Path(pdf_path).absolute()))


@cv.command("render")
@click.option(
    "--version", "-v", default=None, help="CV version filename (default: base CV)."
)
@click.option("--output", "-o", default=None, help="Output PDF path.")
@click.option("--template", "-t", default="cv/modern.html", help="Template to use.")
@click.option(
    "--lang",
    default=None,
    type=click.Choice(["en", "he"]),
    help="Output language (default: auto-detect from CV data).",
)
@require_profile
def cv_render(version, output, template, lang):
    """Render a CV version to PDF."""
    from job_hunter.cv.adapter import detect_cv_language
    from job_hunter.cv.renderer import CVRenderer

    manager = CVManager()
    data = manager.load_version(version) if version else manager.load_base()

    if lang is None:
        lang = detect_cv_language(data)

    renderer = CVRenderer()

    name = data.get("name", "cv").replace(" ", "_").lower()
    out_path = Path(output) if output else Config.CV_OUTPUT_DIR / f"{name}_cv.pdf"

    renderer.render_pdf(data, out_path, template, lang=lang)
    console.print(f"[green]PDF saved to {out_path}[/green]")


@cv.command("list")
@require_profile
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

        mtime = datetime.datetime.fromtimestamp(v.stat().st_mtime).strftime(
            "%Y-%m-%d %H:%M"
        )
        table.add_row(v.name, mtime)
    console.print(table)


# ---------------------------------------------------------------------------
# Application commands
# ---------------------------------------------------------------------------


@cli.group()
def apps():
    """Track job applications."""


_STATUS_ICONS = {
    "applied": "[yellow]applied[/yellow]",
    "screening": "[blue]screening[/blue]",
    "interview": "[green]interview[/green]",
    "offer": "[bold green]OFFER[/bold green]",
    "rejected": "[red]rejected[/red]",
    "withdrawn": "[dim]withdrawn[/dim]",
}

_STATUS_CHOICES = [
    "applied",
    "screening",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
]


@apps.command("list")
@click.option("--status", "-s", default=None, type=click.Choice(_STATUS_CHOICES))
@click.option("--company", "-c", default=None)
@click.option(
    "--follow-up",
    "follow_up",
    is_flag=True,
    help="Show only applications needing follow-up",
)
@require_profile
def apps_list(status, company, follow_up):
    """List job applications."""
    from datetime import datetime

    tracker = ApplicationTracker()

    if follow_up:
        applications = tracker.get_needing_follow_up()
    elif status:
        applications = tracker.get_by_status(status)
    elif company:
        applications = tracker.get_by_company(company)
    else:
        applications = tracker.get_all()

    if not applications:
        console.print("No applications found.")
        return

    today = datetime.now().strftime("%Y-%m-%d")

    table = Table(title=f"Job Applications ({len(applications)})")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Position")
    table.add_column("Company", style="cyan")
    table.add_column("Status", width=16)
    table.add_column("Applied", style="dim")
    table.add_column("Follow-up")

    for app in applications:
        icon = _STATUS_ICONS.get(app.status, "")
        # Applied date: "Mar 23" format
        try:
            applied_fmt = datetime.strptime(app.applied_date, "%Y-%m-%d").strftime(
                "%b %d"
            )
        except ValueError:
            applied_fmt = app.applied_date

        # Follow-up column
        if app.status in ("rejected", "withdrawn", "offer"):
            fu_cell = "[dim]-[/dim]"
        elif app.follow_up_date and today > app.follow_up_date:
            from datetime import datetime as dt

            days_over = (
                dt.strptime(today, "%Y-%m-%d")
                - dt.strptime(app.follow_up_date, "%Y-%m-%d")
            ).days
            fu_cell = f"[red]! overdue ({days_over}d)[/red]"
        else:
            fu_cell = app.follow_up_date

        table.add_row(
            app.id[:8],
            app.job_title[:40],
            app.company[:25],
            icon,
            applied_fmt,
            fu_cell,
        )

    console.print(table)


@apps.command("update")
@click.argument("app_id")
@click.option("--status", "-s", required=True, type=click.Choice(_STATUS_CHOICES))
@click.option("--notes", "-n", default="")
@require_profile
def apps_update(app_id, status, notes):
    """Update the status of an application."""
    from job_hunter.applications.models import VALID_TRANSITIONS

    tracker = ApplicationTracker()

    app = tracker.get_by_id(app_id)
    if not app:
        console.print(f"[red]Application '{app_id}' not found.[/red]")
        return

    old_status = app.status
    try:
        tracker.update_status(app_id, status, notes)
    except ValueError:
        allowed = VALID_TRANSITIONS.get(old_status, [])
        allowed_str = ", ".join(allowed) if allowed else "(none)"
        console.print(f"[red]Cannot change from '{old_status}' to '{status}'[/red]")
        console.print(f"   Valid transitions from '{old_status}': {allowed_str}")
        return

    console.print(f"[green]Updated: {app.company} - {app.job_title}[/green]")
    console.print(f"   Status: {old_status} -> {status}")
    if notes:
        console.print(f"   Note: {notes}")


@apps.command("reset")
@click.argument("app_id")
@click.option("--notes", "-n", default="")
@require_profile
def apps_reset(app_id, notes):
    """Reset an application status back to 'applied'."""
    tracker = ApplicationTracker()
    app = tracker.reset_status(app_id, notes)
    if not app:
        console.print(f"[red]Application '{app_id}' not found.[/red]")
        return
    console.print(f"[green]Reset: {app.company} - {app.job_title} -> applied[/green]")


@apps.command("stats")
@require_profile
def apps_stats():
    """Show application statistics."""
    tracker = ApplicationTracker()
    stats = tracker.get_stats()
    console.print(f"[bold]Total applications:[/bold] {stats['total']}")
    console.print(f"[bold]Response rate:[/bold] {stats['response_rate']}%")
    console.print(f"[bold]Needs follow-up:[/bold] {stats['needs_follow_up']}")
    for status, count in stats["by_status"].items():
        console.print(f"  {status}: {count}")


@apps.command("dashboard")
@require_profile
def apps_dashboard():
    """Show a full application dashboard with stats, follow-ups, and recent activity."""
    from datetime import datetime

    from rich.panel import Panel

    tracker = ApplicationTracker()
    apps = tracker.get_all()

    if not apps:
        console.print(
            Panel(
                "[dim]No applications tracked yet.\nUse: jobs scan -> select job -> [5] Track[/dim]",
                title="[cyan]Application Dashboard[/cyan]",
                border_style="cyan",
            )
        )
        return

    stats = tracker.get_stats()
    total = stats["total"]
    by_status = stats["by_status"]

    _ICONS = {
        "applied": "[yellow]~[/yellow]",
        "screening": "[blue]>[/blue]",
        "interview": "[green]+[/green]",
        "offer": "[bold green]$[/bold green]",
        "rejected": "[red]x[/red]",
        "withdrawn": "[dim]-[/dim]",
    }

    # --- Status breakdown with bar ---
    max_count = max(by_status.values(), default=1)
    status_lines = []
    for s, icon in _ICONS.items():
        count = by_status.get(s, 0)
        if count == 0:
            continue
        bar = "#" * max(1, round(count / max_count * 8))
        status_lines.append(f"  {icon} {s:<10} {count:>2}  [cyan]{bar}[/cyan]")

    # --- Follow-up warnings ---
    overdue = tracker.get_needing_follow_up()
    today = datetime.now().strftime("%Y-%m-%d")
    fu_lines = []
    for app in overdue:
        try:
            days_ago = (
                datetime.strptime(today, "%Y-%m-%d")
                - datetime.strptime(app.follow_up_date, "%Y-%m-%d")
            ).days
            fu_lines.append(
                f"  • {app.company} — {app.job_title[:35]} ({days_ago}d overdue)"
            )
        except ValueError:
            fu_lines.append(f"  • {app.company} — {app.job_title[:35]}")

    # --- Recent activity (last 5 events across all apps) ---
    events = []
    for app in apps:
        for event in app.history:
            events.append(
                (
                    event.get("date", ""),
                    app.company,
                    event.get("action", ""),
                    event.get("note", ""),
                )
            )
    events.sort(key=lambda e: e[0], reverse=True)
    recent_lines = []
    for date, company, action, note in events[:5]:
        try:
            date_fmt = datetime.strptime(date, "%Y-%m-%d").strftime("%b %d")
        except ValueError:
            date_fmt = date
        note_part = f" - {note}" if note and note != "Initial application" else ""
        recent_lines.append(f"  {date_fmt}  {action:<12} {company}{note_part}")

    # --- Company breakdown ---
    company_table = Table(box=None, show_header=False, padding=(0, 1))
    company_table.add_column(style="cyan")
    company_table.add_column(justify="right", style="dim")
    for company, count in sorted(stats["by_company"].items(), key=lambda x: -x[1])[:8]:
        company_table.add_row(company, str(count))

    # --- Assemble output ---
    console.print()
    console.print(
        Panel(
            "\n".join(
                [
                    f"[bold]Total:[/bold] {total} application{'s' if total != 1 else ''}",
                    f"[bold]Response rate:[/bold] {stats['response_rate']}%",
                    "",
                    "[bold]By status:[/bold]",
                    *status_lines,
                ]
            ),
            title="[cyan]Application Dashboard[/cyan]",
            border_style="cyan",
        )
    )

    if fu_lines:
        console.print(
            Panel(
                "\n".join(fu_lines),
                title="[yellow]! Needs Follow-up[/yellow]",
                border_style="yellow",
            )
        )

    if recent_lines:
        console.print(
            Panel(
                "\n".join(recent_lines),
                title="[blue]Recent Activity[/blue]",
                border_style="blue",
            )
        )

    console.print(
        Panel(
            company_table,
            title="[dim]By Company[/dim]",
            border_style="dim",
        )
    )


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
@require_profile
def recruiters_add(company, name, email, linkedin, role, notes):
    """Add a recruiter contact for a company."""
    from job_hunter.recruiters.manager import RecruiterManager

    mgr = RecruiterManager()
    rec = mgr.add(
        company=company,
        name=name,
        email=email,
        linkedin=linkedin,
        role=role,
        notes=notes,
    )
    console.print(f"[green]Saved:[/green] {rec.name} @ {rec.company} ({rec.email})")


@recruiters.command("list")
@click.option("--company", "-c", default=None, help="Filter by company name (fuzzy).")
@require_profile
def recruiters_list(company):
    """List saved recruiter contacts."""
    from rich.table import Table

    from job_hunter.recruiters.manager import RecruiterManager

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
    console.print(
        f"[dim]Total: {stats['total_recruiters']} recruiters across "
        f"{stats['companies_with_recruiters']} companies[/dim]"
    )


@recruiters.command("remove")
@click.option("--company", "-c", required=True)
@click.option("--email", "-e", required=True)
@require_profile
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
@require_profile
def recruiters_search(company):
    """Open LinkedIn and Google searches to find recruiters for a company."""
    import time
    import urllib.parse

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

    console.print("\n[green]Searches opened in Chrome.[/green]")
    console.print("\n[dim]When you find a recruiter, save them with:[/dim]")
    console.print(
        f'[bold]job-hunter recruiters add -c "{company}" -n "Name" -e "email@company.com"[/bold]'
    )


@recruiters.command("find-emails")
@click.argument("domain")
@click.option("--limit", "-l", default=5, show_default=True, help="Max results.")
@require_profile
def recruiters_find_emails(domain, limit):
    """Search Hunter.io for emails at a company domain."""
    from rich.table import Table

    from job_hunter.recruiters.hunter import HunterAPI

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
        console.print(
            f"\n[dim]Quota: {quota['used']} used / {quota['available']} available[/dim]"
        )


@recruiters.command("scan-all")
@click.option(
    "--limit",
    "-l",
    default=2,
    show_default=True,
    help="Max HR contacts to save per company.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would happen without saving or using quota.",
)
@require_profile
def recruiters_scan_all(limit, dry_run):
    """Scan all companies from companies.json and find recruiter emails via Hunter.io."""
    import json

    from rich.table import Table

    from job_hunter.recruiters.hunter import HunterAPI, get_domain_for_company
    from job_hunter.recruiters.manager import RecruiterManager

    companies_file = Config.companies_file()
    with open(companies_file, encoding="utf-8") as f:
        companies = json.load(f).get("companies", [])

    try:
        hunter = HunterAPI()
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return

    quota = hunter.get_quota()
    available = quota.get("available", 0)
    console.print(
        f"[cyan]Quota:[/cyan] {quota.get('used', 0)} used / {available} available"
    )

    if not dry_run and available < len(companies):
        console.print(
            f"[yellow]Warning: {available} searches for {len(companies)} companies.[/yellow]"
        )
        if not click.confirm("Continue anyway?"):
            return

    if dry_run:
        console.print(
            "[yellow]Dry-run mode — no searches will be made, no data saved.[/yellow]"
        )

    console.print(f"\n[bold]Scanning {len(companies)} companies...[/bold]\n")

    manager = RecruiterManager()
    hr_keywords = [
        "recruit",
        "talent",
        "hr",
        "human resource",
        "people",
        "staffing",
        "hiring",
    ]

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
            e
            for e in result.get("emails", [])
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
    console.print(
        f"\n[bold]Summary:[/bold] {len(companies)} companies scanned | "
        f"{total_found} HR contacts found | "
        f"[green]{total_saved} saved[/green]"
    )

    if not dry_run:
        new_quota = hunter.get_quota()
        console.print(
            f"[dim]Quota after scan: {new_quota.get('used','?')} used / "
            f"{new_quota.get('available','?')} available[/dim]"
        )
        if total_saved:
            console.print(
                "\n[green]View saved recruiters:[/green] [bold]job-hunter recruiters list[/bold]"
            )


# ---------------------------------------------------------------------------
# Companies commands
# ---------------------------------------------------------------------------


@cli.group()
def companies():
    """Manage your company watchlist."""


@companies.command("list")
@require_profile
def companies_list():
    """Show your current watchlist and registry info."""

    profile = get_profile()

    if not profile.watchlist:
        console.print("[dim]Your watchlist is empty.[/dim]")
        console.print(
            "Run [bold]job-hunter companies suggest[/bold] to get recommendations,"
        )
        console.print(
            "or [bold]job-hunter companies add <name>[/bold] to add manually."
        )
        return

    # Load registry for extra info
    from job_hunter.jobs.search_strategy import _load_company_registry

    registry = _load_company_registry()

    table = Table(title=f"Watchlist ({len(profile.watchlist)} companies)")
    table.add_column("Company", style="cyan")
    table.add_column("Domains", style="dim")
    table.add_column("Scraper", style="green")

    for name in sorted(profile.watchlist):
        entry = registry.get(name.lower(), {})
        domains = ", ".join(entry.get("domain", []))
        scraper = "✓ dedicated" if entry.get("scraper") else "general only"
        table.add_row(name, domains or "—", scraper)

    console.print(table)


@companies.command("add")
@click.argument("names", nargs=-1, required=True)
@require_profile
def companies_add(names):
    """Add companies to your watchlist.

    Examples:
        job-hunter companies add Google
        job-hunter companies add "Check Point" Microsoft
    """
    profile = get_profile()

    added = []
    already = []
    existing_lower = {c.lower() for c in profile.watchlist}

    for name in names:
        if name.lower() in existing_lower:
            already.append(name)
        else:
            profile.watchlist.append(name)
            existing_lower.add(name.lower())
            added.append(name)

    if added:
        profile.save()
        console.print(f"[green]Added:[/green] {', '.join(added)}")
    if already:
        console.print(f"[dim]Already in watchlist:[/dim] {', '.join(already)}")

    console.print(f"[dim]Watchlist now has {len(profile.watchlist)} companies.[/dim]")


@companies.command("remove")
@click.argument("names", nargs=-1, required=True)
@require_profile
def companies_remove(names):
    """Remove companies from your watchlist.

    Examples:
        job-hunter companies remove Google
        job-hunter companies remove "Check Point" Microsoft
    """
    profile = get_profile()

    removed = []
    names_lower = {n.lower() for n in names}

    new_watchlist = []
    for c in profile.watchlist:
        if c.lower() in names_lower:
            removed.append(c)
        else:
            new_watchlist.append(c)

    if not removed:
        console.print(f"[yellow]Not in watchlist:[/yellow] {', '.join(names)}")
        return

    profile.watchlist = new_watchlist
    profile.save()
    console.print(f"[green]Removed:[/green] {', '.join(removed)}")
    console.print(f"[dim]Watchlist now has {len(profile.watchlist)} companies.[/dim]")


@companies.command("suggest")
@require_profile
def companies_suggest():
    """Get AI-powered company suggestions based on your profile."""
    from job_hunter.jobs.search_strategy import suggest_companies

    profile = get_profile()

    console.print("[dim]Analyzing your profile for relevant companies...[/dim]")
    suggestions = suggest_companies(profile)

    has_suggestions = suggestions["registry"] or suggestions["additional"]
    if not has_suggestions:
        console.print(
            "[yellow]No suggestions available.[/yellow] "
            "Try adding more skills or target positions to your profile."
        )
        return

    if suggestions["registry"]:
        console.print("\n[bold]Companies with dedicated scrapers:[/bold]")
        for name in suggestions["registry"]:
            in_wl = name.lower() in {c.lower() for c in profile.watchlist}
            marker = " [dim](already in watchlist)[/dim]" if in_wl else ""
            console.print(f"  [green]✓[/green] {name}{marker}")

    if suggestions["additional"]:
        console.print("\n[bold]Also relevant (general search only):[/bold]")
        for name in suggestions["additional"]:
            in_wl = name.lower() in {c.lower() for c in profile.watchlist}
            marker = " [dim](already in watchlist)[/dim]" if in_wl else ""
            console.print(f"  [blue]+[/blue] {name}{marker}")

    # Collect new suggestions not already in watchlist
    existing_lower = {c.lower() for c in profile.watchlist}
    new_names = [
        n
        for n in suggestions["registry"] + suggestions["additional"]
        if n.lower() not in existing_lower
    ]

    if not new_names:
        console.print("\n[dim]All suggestions are already in your watchlist.[/dim]")
        return

    if click.confirm(
        f"\nAdd {len(new_names)} new companies to your watchlist?", default=True
    ):
        profile.watchlist.extend(new_names)

        remove_input = click.prompt(
            "Remove any? (comma-separated names, or Enter to keep all)",
            default="",
        )
        if remove_input.strip():
            to_remove = {r.strip().lower() for r in remove_input.split(",")}
            profile.watchlist = [
                c for c in profile.watchlist if c.lower() not in to_remove
            ]

        profile.save()
        console.print(
            f"[green]Watchlist updated: {len(profile.watchlist)} companies[/green]"
        )
    else:
        console.print("[dim]No changes made.[/dim]")


# ---------------------------------------------------------------------------
# Jobs commands
# ---------------------------------------------------------------------------


@cli.group()
def jobs():
    """Search and collect job listings."""


@jobs.command("search")
@click.option(
    "--query",
    "-q",
    default="student electrical engineering",
    show_default=True,
    help="Search query.",
)
@click.option(
    "--location", "-l", default="Israel", show_default=True, help="Location filter."
)
@click.option(
    "--max",
    "-n",
    "max_results",
    default=10,
    show_default=True,
    help="Max results to return.",
)
@click.option(
    "--source",
    "-s",
    default="intel",
    type=click.Choice(["intel", "glassdoor", "indeed"]),
    show_default=True,
    help="Job board to search.",
)
@require_profile
def jobs_search(query, location, max_results, source):
    """Search job boards for listings."""
    from job_hunter.jobs.scraper import GlassdoorScraper, IndeedScraper, IntelScraper

    if source == "intel":
        scraper = IntelScraper()
    elif source == "glassdoor":
        scraper = GlassdoorScraper()
    else:
        scraper = IndeedScraper()
    console.print(
        f"Searching {source.capitalize()} for: [bold]{query}[/bold] in {location}...\n"
    )

    try:
        with console.status("Fetching results..."):
            listings = scraper.search(query, location, max_results=max_results)
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    if not listings:
        console.print(
            "[yellow]No jobs found. Indeed may be blocking the request, or no results match.[/yellow]"
        )
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
@click.option(
    "--query",
    "-q",
    default=None,
    help="Manual override query (bypasses profile-generated queries).",
)
@click.option(
    "--location", "-l", default=None, help="Location filter (default: from profile)."
)
@click.option(
    "--max",
    "-n",
    "max_per_company",
    default=20,
    show_default=True,
    help="Max results per source.",
)
@click.option(
    "--new-only",
    is_flag=True,
    default=False,
    help="Show only jobs seen for the first time in the last 24 hours.",
)
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    default=False,
    help="Show all jobs including irrelevant ones (disables profile filter).",
)
@click.option(
    "--no-companies",
    is_flag=True,
    default=False,
    help="Skip company-targeted JobSpy search (faster scan).",
)
@click.option(
    "--companies-all",
    is_flag=True,
    default=False,
    help="Search ALL companies in companies.json instead of priority only.",
)
@click.option(
    "--fresh", is_flag=True, default=False, help="Ignore cache and rescan everything."
)
@require_profile
def jobs_scan(
    query,
    location,
    max_per_company,
    new_only,
    show_all,
    no_companies,
    companies_all,
    fresh,
):
    """Scan all supported company career pages and show interactive menu."""
    try:
        Config.validate()
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return

    from job_hunter.jobs.history import JobHistory
    from job_hunter.jobs.relevance_filter import filter_relevant_jobs
    from job_hunter.jobs.scraper import JobScanner

    scanner = JobScanner()
    seniority_reject = None  # None = use default list in relevance_filter

    if query:
        # --- Legacy path: manual --query override ----------------------------
        profile = get_profile()
        default_location = (profile.country if profile else None) or "Israel"
        effective_location = location or default_location
        console.print(
            f"Scanning for: [bold]{query}[/bold] in {effective_location}...\n"
        )
        with console.status("Fetching from Intel, NVIDIA, Marvell, Amazon..."):
            listings = scanner.scan(
                query=query,
                location=effective_location,
                max_per_company=max_per_company,
            )

        if not no_companies:
            only_priority = not companies_all
            label = "priority" if only_priority else "all"
            console.print(
                f"\nCompany-targeted scan ({label} companies) via JobSpy...\n"
            )

            def _progress(name, current, total):
                console.print(
                    f"  [{current}/{total}] Searching: {name}...", style="dim"
                )

            company_listings = scanner.company_scan(
                query=query,
                location=effective_location,
                max_per_company=max_per_company,
                only_priority=only_priority,
                progress_callback=_progress,
            )
            listings = scanner._deduplicate(listings + company_listings)
    else:
        # --- New default path: profile-driven parallel scan ------------------
        from job_hunter.jobs.scan_cache import ScanCache
        from job_hunter.jobs.search_strategy import build_search_config

        profile = get_profile()
        config = build_search_config(profile)
        seniority_reject = config.seniority_reject

        # Override location if --location flag was passed
        if location:
            config.location = location

        # First-run: if queries were just generated, let the user know
        cached_queries = (
            profile.search_config.get("queries") if profile.search_config else None
        )
        if not cached_queries:
            console.print("[dim]Generating search queries from your profile...[/dim]")
            # build_search_config already triggered generation, config.queries is populated

        # Show what we're scanning
        query_list = ", ".join(f'"{q}"' for q in config.queries)
        company_count = len(
            config.priority_companies if not companies_all else config.companies
        )
        company_label = ""
        if not no_companies:
            label = "priority" if not companies_all else "all"
            company_label = f" + {company_count} {label} companies"
        console.print(
            f"Scanning {len(config.queries)} queries{company_label} "
            f"in {config.location}...\n"
        )
        console.print(f"[dim]Queries: {query_list}[/dim]\n")

        cache = ScanCache()
        if fresh:
            cache.clear()
            console.print("[dim]Cache cleared — rescanning everything[/dim]\n")

        # Apply --no-companies / --companies-all overrides
        include_companies = not no_companies
        only_priority = not companies_all

        # Progress callback — prints each source as it completes
        def _parallel_progress(source_key, jobs_found, new_count, cached_age):
            # Parse source key for display: "scraper:IntelScraper:query" → "Intel: query"
            # "company:Google" → "Google (company)"
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
            max_per_source=max_per_company,
            progress_callback=_parallel_progress,
            include_companies=include_companies,
            only_priority=only_priority,
        )
        console.print(f"\n[bold]Total: {len(listings)} jobs found[/bold]")

    if not listings:
        console.print("[yellow]No jobs found across all sources.[/yellow]")
        return

    # Apply relevance filter unless --all is passed
    if not show_all:
        listings, removed = filter_relevant_jobs(
            listings, seniority_reject=seniority_reject
        )
        if removed:
            console.print(
                f"[dim]Filtered out {len(removed)} irrelevant jobs "
                f"(use --all to see everything)[/dim]"
            )
        if not listings:
            console.print(
                "[yellow]No relevant jobs found. Run with --all to see all results.[/yellow]"
            )
            return

    jobs_with_flags = JobHistory().update_and_mark_new(listings)
    new_count = sum(1 for _, is_new in jobs_with_flags if is_new)

    from job_hunter.jobs.discovery import CompanyDiscovery

    disc_stats = CompanyDiscovery().process_jobs(listings)
    if disc_stats["new"] > 0:
        console.print(
            f"[dim]Discovered {disc_stats['new']} new companies — run [bold]job-hunter jobs discover[/bold] to review[/dim]"
        )

    if new_only:
        jobs_with_flags = [(job, is_new) for job, is_new in jobs_with_flags if is_new]
        if not jobs_with_flags:
            console.print("[yellow]No new jobs since last scan.[/yellow]")
            return
        console.print(
            f"[bold green]Showing {len(jobs_with_flags)} new jobs[/bold green] [dim](last 24 hours)[/dim]\n"
        )
    else:
        if new_count:
            console.print(
                f"[bold green]{new_count} new[/bold green] [dim]since last scan[/dim]"
            )

    _print_jobs_table(jobs_with_flags)

    # listings for index lookup must match the displayed table
    displayed_listings = [job for job, _ in jobs_with_flags]

    # Interactive selection loop
    while True:
        console.print()
        try:
            choice = click.prompt(
                "Enter job number to explore (or q to quit)",
                type=str,
            )
        except (click.Abort, EOFError):
            break
        if not choice.strip() or choice.strip().lower() == "q":
            break

        if not choice.strip().isdigit() or not (
            1 <= int(choice) <= len(displayed_listings)
        ):
            console.print(
                f"[red]Please enter a number between 1 and {len(displayed_listings)}.[/red]"
            )
            continue

        job = displayed_listings[int(choice) - 1]
        _job_action_menu(job)

        # Re-print table so user can pick another
        console.print()
        _print_jobs_table(jobs_with_flags)


@jobs.command("refresh-queries")
@require_profile
def jobs_refresh_queries():
    """Regenerate search queries from your profile using AI."""
    try:
        Config.validate()
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return

    from job_hunter.jobs.search_strategy import _get_cached_queries, refresh_queries

    profile = get_profile()

    # Show old queries
    old_queries = _get_cached_queries(profile)
    if old_queries:
        console.print("[bold]Current queries:[/bold]")
        for q in old_queries:
            console.print(f"  [dim]{q}[/dim]")
        console.print()

    console.print("[dim]Generating new queries from your profile...[/dim]")
    new_queries = refresh_queries(profile)

    console.print("\n[bold]New queries:[/bold]")
    for q in new_queries:
        console.print(f"  [green]{q}[/green]")

    if old_queries:
        added = set(new_queries) - set(old_queries)
        removed = set(old_queries) - set(new_queries)
        if added:
            console.print(f"\n[green]+ Added:[/green] {', '.join(added)}")
        if removed:
            console.print(f"[red]- Removed:[/red] {', '.join(removed)}")

    console.print("\n[dim]Saved to profile. Next scan will use these queries.[/dim]")


@jobs.command("discover")
@click.option(
    "--relevance",
    "-r",
    default=None,
    type=click.Choice(["high", "medium", "unknown", "low"]),
    help="Filter by relevance level.",
)
@require_profile
def jobs_discover(relevance):
    """Review companies discovered during scans that aren't in companies.json."""
    try:
        Config.validate()
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return

    from job_hunter.jobs.discovery import CompanyDiscovery

    discovery = CompanyDiscovery()
    stats = discovery.get_stats()

    console.print(
        f"\n[bold]Company Discovery[/bold]  "
        f"total={stats['total_discovered']}  "
        f"pending={stats['pending_review']}  "
        f"[green]high={stats['high_relevance']}[/green]  "
        f"added={stats['added_to_main']}  "
        f"ignored={stats['ignored']}\n"
    )

    pending = discovery.get_pending(relevance=relevance)
    if not pending:
        msg = "No pending companies to review."
        if relevance:
            msg += f" (filter: {relevance})"
        console.print(f"[yellow]{msg}[/yellow]")
        return

    for i, company in enumerate(pending, 1):
        relevance_color = {
            "high": "green",
            "medium": "yellow",
            "unknown": "dim",
            "low": "red",
        }.get(company["relevance_score"], "dim")
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
                console.print(
                    f"[red]Number must be between 1 and {len(pending)}.[/red]"
                )
                continue
            company_name = pending[idx]["name"]
            if parts[0] == "i":
                discovery.mark_ignored(company_name)
                console.print(f"[dim]Ignored: {company_name}[/dim]")
                pending.pop(idx)
            else:
                ok = discovery.add_to_companies_json(company_name)
                if ok:
                    console.print(
                        f"[green]Added to companies.json: {company_name}[/green]"
                    )
                    console.print(
                        f"[dim]Edit {Config.companies_file()} to fill in career_url and scraper.[/dim]"
                    )
                else:
                    console.print(
                        f"[yellow]{company_name} is already in companies.json.[/yellow]"
                    )
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

    def _safe(text: str) -> str:
        """Replace problematic Unicode chars that crash Windows cp1255 console."""
        return (
            text.replace("\u2011", "-")
            .replace("\u2013", "-")
            .replace("\u2014", "-")
            .replace("\u2192", "->")
        )

    for i, (job, is_new) in enumerate(pairs, 1):
        safe_title = _safe(job.title)
        title = f"[bold green][NEW][/bold green] {safe_title}" if is_new else safe_title
        table.add_row(
            str(i), title, _safe(job.company), _safe(job.location), job.posted or ""
        )

    console.print(f"[green]Found {len(pairs)} jobs:[/green]")
    console.print(table)


def _job_action_menu(job) -> None:
    from job_hunter.recruiters.manager import RecruiterManager

    while True:
        from datetime import datetime as _dt

        recruiter_mgr = RecruiterManager()
        recruiters = recruiter_mgr.find_by_company_fuzzy(job.company)
        recruiter = recruiters[0] if recruiters else None

        tracked = next(
            (a for a in ApplicationTracker().get_all() if a.job_url == job.url), None
        )

        console.print(
            f"\n[bold cyan]{job.title}[/bold cyan] - {job.company}, {job.location}"
        )
        console.print(f"[dim]{job.url}[/dim]")

        if tracked:
            try:
                date_fmt = _dt.strptime(tracked.applied_date, "%Y-%m-%d").strftime(
                    "%b %d"
                )
            except ValueError:
                date_fmt = tracked.applied_date
            console.print(
                f"  [dim]Tracked: {tracked.status} ({date_fmt}) - ID: {tracked.id}[/dim]"
            )

        console.print()
        console.print("  [bold][1][/bold] Show full details")
        console.print("  [bold][2][/bold] Adapt CV for this job")
        console.print("  [bold][3][/bold] Generate cover letter")
        console.print("  [bold][4][/bold] Open in browser")
        console.print("  [bold][5][/bold] Track application")
        if recruiter:
            console.print(
                f"  [bold][6][/bold] Send email to recruiter ([cyan]{recruiter['email']}[/cyan])"
            )
        else:
            console.print(
                "  [bold][6][/bold] Send email to recruiter [dim](no recruiter saved)[/dim]"
            )
        console.print("  [bold][7][/bold] Back to list")
        if tracked and tracked.status != "applied":
            console.print("  [bold][8][/bold] Reset application status")

        action = click.prompt("\nChoose", default="7", show_default=False)

        if action == "1":
            from rich.panel import Panel

            from job_hunter.jobs.scraper import fetch_job_description

            panel_text = (
                f"[bold]Title:[/bold]    {job.title}\n"
                f"[bold]Company:[/bold]  {job.company}\n"
                f"[bold]Location:[/bold] {job.location}\n"
                f"[bold]URL:[/bold]      {job.url}"
            )
            console.print(Panel(panel_text, title="Job Details", border_style="cyan"))

            console.print("[dim]Fetching description...[/dim]")
            desc = fetch_job_description(job)
            if desc:
                # Trim to reasonable length for display
                if len(desc) > 2000:
                    desc = desc[:2000] + "\n..."
                console.print(Panel(desc, title="Description", border_style="dim"))
            else:
                console.print(
                    "[yellow]Could not fetch description. Open in browser to view.[/yellow]"
                )

        elif action == "2":
            _adapt_cv_for_job(job)

        elif action == "3":
            _generate_cover_letter_for_job(job)

        elif action == "4":
            open_in_chrome(job.url)
            console.print("[green]Opened in Chrome.[/green]")

        elif action == "5":
            _track_application(job, recruiter)

        elif action == "6":
            if not recruiter:
                console.print("[yellow]No recruiter saved for this company.[/yellow]")
            else:
                _send_email_to_recruiter(job, recruiter)

        elif action == "7":
            break

        elif action == "8":
            if not tracked:
                console.print("[red]Invalid option.[/red]")
            else:
                note = click.prompt("Note (optional)", default="", show_default=False)
                ApplicationTracker().reset_status(tracked.id, note)
                console.print(
                    f"[green]Reset to applied: {tracked.company} - {tracked.job_title}[/green]"
                )

        else:
            console.print("[red]Invalid option.[/red]")


def _track_application(job, recruiter) -> None:
    """Auto-detect context and save application to tracker."""
    from rich.panel import Panel

    from job_hunter.applications.models import Application
    from job_hunter.applications.tracker import ApplicationTracker

    # --- Auto-detect CV ---
    company_clean = job.company.lower().replace(" ", "_")
    cv_dir = Config.CV_OUTPUT_DIR
    cv_files = list(cv_dir.glob(f"cv_{company_clean}*.pdf")) if cv_dir.exists() else []
    if not cv_files:
        cv_files = (
            [f for f in cv_dir.glob("cv_*.pdf") if company_clean in f.name.lower()]
            if cv_dir.exists()
            else []
        )
    cv_file = str(max(cv_files, key=lambda p: p.stat().st_mtime)) if cv_files else ""

    # --- Auto-detect cover letter ---
    cl_dir = Config.COVER_LETTER_DIR
    cl_files = (
        list(cl_dir.glob(f"cover_letter_{company_clean}*.txt"))
        if cl_dir.exists()
        else []
    )
    if not cl_files:
        cl_files = (
            [
                f
                for f in cl_dir.glob("cover_letter_*.txt")
                if company_clean in f.name.lower()
            ]
            if cl_dir.exists()
            else []
        )
    cl_file = str(max(cl_files, key=lambda p: p.stat().st_mtime)) if cl_files else ""

    # --- Recruiter info ---
    recruiter_name = recruiter["name"] if recruiter else ""
    recruiter_email = recruiter["email"] if recruiter else ""

    # --- Check if already tracked ---
    tracker = ApplicationTracker()
    existing = [a for a in tracker.get_all() if a.job_url == job.url]
    if existing:
        a = existing[0]
        console.print(
            f"[yellow]Already tracked — ID: {a.id}, status: {a.status}[/yellow]"
        )
        return

    # --- Show summary panel ---
    from datetime import datetime, timedelta

    follow_up = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    cv_line = (
        f"[green]{Path(cv_file).name} ✅[/green]"
        if cv_file
        else "[red]Not found ❌[/red]"
    )
    cl_line = (
        f"[green]{Path(cl_file).name} ✅[/green]"
        if cl_file
        else "[red]Not found ❌[/red]"
    )
    rec_line = (
        f"[green]{recruiter_name} ({recruiter_email}) ✅[/green]"
        if recruiter_name
        else "[red]Not saved ❌[/red]"
    )

    console.print(
        Panel(
            f"[bold]Job:[/bold]          {job.title}\n"
            f"[bold]Company:[/bold]      {job.company}\n"
            f"[bold]Location:[/bold]     {job.location}\n"
            f"[bold]CV:[/bold]           {cv_line}\n"
            f"[bold]Cover letter:[/bold] {cl_line}\n"
            f"[bold]Recruiter:[/bold]    {rec_line}\n"
            f"[bold]Follow-up:[/bold]    {follow_up}",
            title="[cyan]Track Application[/cyan]",
            border_style="cyan",
        )
    )

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

    console.print(
        Panel(
            f"[bold]ID:[/bold]          {app.id}\n"
            f"[bold]Status:[/bold]      {app.status}\n"
            f"[bold]Follow-up:[/bold]   {app.follow_up_date}",
            title="[green]Application Tracked ✅[/green]",
            border_style="green",
        )
    )


def _send_email_to_recruiter(job, recruiter) -> None:
    """Open Gmail compose in Chrome with pre-filled email, and prepare CV for attachment."""
    import subprocess
    import urllib.parse
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
            f"{get_profile().signature_block()}"
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
            cv_files = [
                f for f in cv_dir.glob("cv_*.pdf") if company_clean in f.name.lower()
            ]

        if cv_files:
            # Get most recent
            latest_cv = max(cv_files, key=lambda p: p.stat().st_mtime)

            # Copy path to clipboard
            try:
                import pyperclip

                pyperclip.copy(str(latest_cv.absolute()))
                console.print(
                    f"[cyan]CV path copied to clipboard:[/cyan] {latest_cv.name}"
                )
            except Exception:
                console.print(f"[cyan]CV path:[/cyan] {latest_cv.absolute()}")

            # Open folder with CV selected
            try:
                import platform as _plat

                _sys = _plat.system()
                if _sys == "Windows":
                    subprocess.run(["explorer", "/select,", str(latest_cv.absolute())])
                elif _sys == "Darwin":
                    subprocess.run(["open", "-R", str(latest_cv.absolute())])
                else:
                    subprocess.Popen(["xdg-open", str(latest_cv.parent.absolute())])
                console.print(
                    "[cyan]Opened CV folder — drag file to Gmail to attach[/cyan]"
                )
            except Exception:
                console.print(f"[cyan]CV folder:[/cyan] {latest_cv.parent.absolute()}")
        else:
            console.print(
                "[yellow]No adapted CV found. Run [2] Adapt CV first.[/yellow]"
            )
    else:
        console.print("[yellow]No CV folder found.[/yellow]")


def _prompt_paste_description(job_url: str) -> str:
    """Prompt the user to paste a job description inline in the terminal.

    Falls back to a text editor if the user prefers.
    Returns the trimmed description, or empty string if the user provided nothing.
    """
    console.print(
        "[dim]Paste the job description below. "
        "When done, type [bold]END[/bold] on a new line by itself.[/dim]"
    )
    lines = []
    try:
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
    except EOFError:
        pass
    text = "\n".join(lines).strip()

    if not text:
        # Nothing pasted — offer editor as fallback
        if click.confirm("Nothing pasted. Open a text editor instead?", default=True):
            template = (
                f"# Paste the job description below this line, then save and close.\n"
                f"# Job URL: {job_url}\n"
                f"# Lines starting with '#' will be ignored.\n\n"
            )
            try:
                edited = click.edit(template)
            except click.UsageError:
                edited = None
            if edited:
                text = "\n".join(
                    ln for ln in edited.splitlines() if not ln.lstrip().startswith("#")
                ).strip()
        return text

    return text


def _adapt_cv_for_job(job) -> None:
    import re

    from job_hunter.config import Config
    from job_hunter.cv.adapter import CVAdapter
    from job_hunter.cv.manager import CVManager
    from job_hunter.cv.renderer import CVRenderer
    from job_hunter.jobs.scraper import fetch_job_description

    # 0. Check for existing CV
    company_clean = re.sub(r"[^\w]+", "_", job.company).lower()[:20]
    existing_cvs = sorted(
        Config.OUTPUT_DIR.glob(f"cv_*{company_clean}*.pdf"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if existing_cvs:
        existing = existing_cvs[0]
        console.print(
            f"\n  Found existing CV for {job.company}: [cyan]{existing.name}[/cyan]"
        )
        console.print("  [bold][1][/bold] Open existing CV")
        console.print("  [bold][2][/bold] View changes (diff comparison)")
        console.print("  [bold][3][/bold] Generate new adapted CV")
        console.print("  [bold][4][/bold] Back")
        reuse = click.prompt("\nChoose", default="1", show_default=False)
        if reuse == "1":
            open_in_chrome(str(existing.absolute()))
            console.print(f"[green]Opened {existing.name}[/green]")
            return
        elif reuse == "2":
            diff_files = sorted(
                Config.OUTPUT_DIR.glob(f"cv_diff_*{company_clean}*.html"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if diff_files:
                open_in_chrome(str(diff_files[0].absolute()))
                console.print(f"[green]Opened {diff_files[0].name}[/green]")
            else:
                # Diff missing (old CV) — regenerate from adapted JSON + base CV
                from job_hunter.cv.change_summary import generate_change_summary

                cv_manager = CVManager()
                json_path = Config.CV_DIR / f"{existing.stem}.json"
                if json_path.exists():
                    try:
                        base_cv = cv_manager.load_base()
                        adapted_cv = cv_manager.load_version(json_path.name)
                        with console.status("Regenerating diff..."):
                            diff_path = generate_change_summary(
                                base_cv=base_cv,
                                adapted_cv=adapted_cv,
                                job_title=job.title,
                                company=job.company,
                            )
                        open_in_chrome(str(diff_path.absolute()))
                        console.print(
                            f"[green]Regenerated and opened {diff_path.name}[/green]"
                        )
                    except Exception as e:
                        console.print(f"[red]Could not regenerate diff: {e}[/red]")
                else:
                    console.print(
                        "[yellow]No adapted CV JSON found — cannot regenerate diff. Generate a new CV.[/yellow]"
                    )
            return
        elif reuse == "4":
            return
        # reuse == "3": fall through to generate

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
            "[yellow]Job description not available automatically "
            "(site blocked us or page is JavaScript-rendered).[/yellow]"
        )
        if click.confirm("Paste the job description manually?", default=True):
            description = _prompt_paste_description(job.url)
        if not description:
            console.print(
                "[yellow]No description provided — aborting CV adapt.[/yellow]"
            )
            return

    console.print(
        f"[dim]Fetched {len(description)} characters of job description.[/dim]"
    )

    # 2. Analyze job description into structured requirements
    from job_hunter.jobs.analyzer import JobAnalyzer

    requirements = None
    with console.status("Analyzing job requirements..."):
        analyzer = JobAnalyzer()
        requirements = analyzer.analyze(
            job_title=job.title,
            company=job.company,
            location=getattr(job, "location", ""),
            description=description,
        )

    if requirements:
        req_skills = (
            ", ".join(requirements.required_skills)
            if requirements.required_skills
            else "none listed"
        )
        console.print(
            f"[dim]Detected: [bold]{requirements.domain}[/bold] role requiring {req_skills}. "
            f"Adapting CV...[/dim]"
        )

    # 3. Load base CV and adapt
    cv_manager = CVManager()
    base_cv = cv_manager.load_base()

    from job_hunter.cv.adapter import detect_cv_language

    cv_lang = detect_cv_language(base_cv)

    with console.status("Adapting CV with Claude..."):
        adapter = CVAdapter()
        if requirements:
            adapted = adapter.adapt_with_requirements(
                base_cv, requirements, lang=cv_lang
            )
        else:
            adapted = adapter.adapt(
                base_cv, description, job_title=job.title, lang=cv_lang
            )

    # 4. Save adapted CV JSON
    company_slug = job.company.lower().replace(" ", "_").replace("/", "_")[:20]
    title_slug = job.title.lower().replace(" ", "_").replace("/", "_")[:25]
    label = f"{company_slug}_{title_slug}"
    json_path = cv_manager.save_version(adapted, label)

    # 5. Render PDF
    renderer = CVRenderer()
    pdf_path = Config.CV_OUTPUT_DIR / f"{json_path.stem}.pdf"
    with console.status("Rendering PDF..."):
        renderer.render_pdf(adapted, pdf_path, lang=cv_lang)

    # 6. Generate change summary
    from job_hunter.cv.change_summary import generate_change_summary

    changes_path = generate_change_summary(
        base_cv=base_cv,
        adapted_cv=adapted,
        job_title=job.title,
        company=job.company,
    )

    # 7. Show result
    from rich.panel import Panel

    console.print(
        Panel(
            f"[bold]Title:[/bold]    {adapted.get('title', '')}\n"
            f"[bold]JSON:[/bold]     {json_path}\n"
            f"[bold]PDF:[/bold]      {pdf_path}\n"
            f"[bold]Changes:[/bold]  {changes_path}",
            title="[green]CV Adapted[/green]",
            border_style="green",
        )
    )

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
    import re

    import pyperclip
    from rich.panel import Panel

    from job_hunter.config import Config
    from job_hunter.cover_letter import CoverLetterGenerator
    from job_hunter.cv.manager import CVManager
    from job_hunter.jobs.scraper import fetch_job_description

    # 0. Check for existing cover letter
    company_clean = re.sub(r"[^\w]+", "_", job.company).lower()[:20]
    existing_letters = sorted(
        Config.COVER_LETTER_DIR.glob(f"cover_letter_*{company_clean}*.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if existing_letters:
        existing = existing_letters[0]
        console.print(
            f"\n  Found existing cover letter for {job.company}: [cyan]{existing.name}[/cyan]"
        )
        console.print("  [bold][1][/bold] Open existing letter")
        console.print("  [bold][2][/bold] Generate new cover letter")
        console.print("  [bold][3][/bold] Back")
        reuse = click.prompt("\nChoose", default="1", show_default=False)
        if reuse == "1":
            click.launch(str(existing.absolute()))
            console.print(f"[green]Opened {existing.name}[/green]")
            return
        elif reuse == "3":
            return
        # reuse == "2": fall through to generate

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
        recruiter_raw = click.prompt(
            "Recruiter name (Enter to skip)", default="", show_default=False
        )
    recruiter_name = (
        None if recruiter_raw.strip() in ("", "-") else recruiter_raw.strip()
    )

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
    console.print(
        Panel(
            letter,
            title=f"[green]Cover Letter — {job.company}[/green]",
            border_style="green",
        )
    )

    # 7. Auto-save TXT + PDF
    slug = re.sub(r"[^\w]+", "_", f"{job.company}_{job.title}").lower()[:40]
    txt_path = Config.COVER_LETTER_DIR / f"cover_letter_{slug}.txt"
    pdf_path = Config.COVER_LETTER_DIR / f"cover_letter_{slug}.pdf"

    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(letter, encoding="utf-8")
    console.print(f"[green]Saved TXT: {txt_path}[/green]")

    try:
        from job_hunter.cv.renderer import CVRenderer
        from job_hunter.profile import get_profile

        profile = get_profile()
        renderer = CVRenderer()
        with console.status("Rendering cover letter PDF..."):
            renderer.render_cover_letter_pdf(
                letter_text=letter,
                output_path=pdf_path,
                sender_name=profile.name,
                sender_email=profile.email,
                sender_phone=profile.phone,
                sender_linkedin=profile.linkedin,
                company=job.company,
                recruiter_name=recruiter_name,
                lang=lang_choice,
            )
        console.print(f"[green]Saved PDF: {pdf_path}[/green]")
    except Exception as e:
        console.print(f"[yellow]PDF generation failed: {e}[/yellow]")

    # 8. Extra options
    console.print("\n  [bold][1][/bold] Copy to clipboard")
    console.print("  [bold][2][/bold] Open PDF")
    console.print("  [bold][3][/bold] Done")

    post = click.prompt("Choose", default="3", show_default=False)

    if post == "1":
        try:
            pyperclip.copy(letter)
            console.print("[green]Copied to clipboard.[/green]")
        except Exception:
            console.print(
                "[yellow]Could not copy to clipboard (pyperclip may not be installed).[/yellow]"
            )
    elif post == "2":
        if pdf_path.exists():
            click.launch(str(pdf_path.absolute()))
        else:
            console.print("[yellow]PDF not available.[/yellow]")


if __name__ == "__main__":
    cli()
