"""Profile-driven search configuration.

Derives search queries, enabled scrapers, company lists, and seniority
filters from the user profile — so the scan adapts to any user, not just
one hardcoded persona.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import anthropic

from job_hunter.config import Config
from job_hunter.logger import get_logger
from job_hunter.profile import UserProfile, get_profile

logger = get_logger(__name__)

# Maps company names in companies.json → scraper class names in scraper.py.
# Only companies with a working direct scraper are listed here.
# Companies not in this map are searched via JobSpy company_scan instead.
COMPANY_SCRAPER_MAP = {
    "Intel": "IntelScraper",
    "NVIDIA": "NVIDIAScraper",
    "Marvell": "MarvellScraper",
    "Amazon Annapurna": "AmazonScraper",
}

# Scrapers that always run regardless of company watchlist.
ALWAYS_ENABLED_SCRAPERS = ["LinkedInScraper", "JobSpyScraper"]

# Seniority keywords to reject — full list for students/entry-level.
SENIORITY_REJECT_FULL = [
    "senior", "manager", "director", "principal", "vp", "vice president",
    "head of", "chief",
]

# Reduced list for experienced users — only C-level / director+.
SENIORITY_REJECT_EXPERIENCED = [
    "director", "vp", "vice president", "head of", "chief",
]

HAIKU_MODEL = "claude-haiku-4-5-20251001"

DEFAULT_MAX_WORKERS = 5


def _level_from_profile(profile: UserProfile) -> tuple:
    """Derive (level_keywords, seniority_reject) from experience_level.

    Falls back to is_student / work_experience if experience_level is empty.
    """
    exp = profile.experience_level

    if exp == "none" or (not exp and (profile.is_student or not profile.work_experience)):
        # Student or no experience
        if profile.is_student:
            return ["student", "intern"], list(SENIORITY_REJECT_FULL)
        return ["junior", "entry level"], list(SENIORITY_REJECT_FULL)

    if exp == "1-3" or (not exp and profile.work_experience):
        return ["junior"], list(SENIORITY_REJECT_FULL)

    if exp == "3-7":
        return [], list(SENIORITY_REJECT_EXPERIENCED)

    if exp == "7+":
        return [], []

    # Fallback
    return ["junior", "entry level"], list(SENIORITY_REJECT_FULL)


@dataclass
class SearchConfig:
    """Everything the scanner needs to run a profile-tailored search."""

    queries: List[str]
    location: str = "Israel"
    cities: List[str] = field(default_factory=list)
    radius_km: int = 25
    level_keywords: List[str] = field(default_factory=lambda: ["student", "intern"])
    seniority_reject: List[str] = field(default_factory=lambda: list(SENIORITY_REJECT_FULL))
    companies: List[str] = field(default_factory=list)
    priority_companies: List[str] = field(default_factory=list)
    enabled_scrapers: List[str] = field(default_factory=list)
    max_workers: int = DEFAULT_MAX_WORKERS


def build_search_config(profile: Optional[UserProfile] = None) -> SearchConfig:
    """Build a SearchConfig from the user profile.

    - Reads cached queries from profile.search_config if available,
      otherwise generates them via Haiku and caches.
    - Derives enabled_scrapers from the company watchlist.
    - Adjusts seniority rejection based on experience level.
    """
    if profile is None:
        profile = get_profile()

    # --- Queries -----------------------------------------------------------
    cached = _get_cached_queries(profile)
    if cached:
        queries = cached
    else:
        queries = generate_queries(profile)

    # --- Location ----------------------------------------------------------
    location = profile.country or "Israel"

    # --- Level / seniority -------------------------------------------------
    level_keywords, seniority_reject = _level_from_profile(profile)

    # --- Companies ---------------------------------------------------------
    companies, priority_companies = _load_companies(profile)

    # --- Enabled scrapers --------------------------------------------------
    enabled = list(ALWAYS_ENABLED_SCRAPERS)
    registry = _load_company_registry()
    for company_name in companies:
        entry = registry.get(company_name.lower(), {})
        scraper = entry.get("scraper", "")
        # Only enable scrapers that exist in COMPANY_SCRAPER_MAP values
        # (filters out "blocked_422", "not_tested", etc.)
        if scraper in COMPANY_SCRAPER_MAP.values():
            enabled.append(scraper)
    # Deduplicate while preserving order
    seen = set()
    enabled_deduped = []
    for s in enabled:
        if s not in seen:
            seen.add(s)
            enabled_deduped.append(s)

    return SearchConfig(
        queries=queries,
        location=location,
        cities=profile.cities,
        radius_km=profile.radius_km,
        level_keywords=level_keywords,
        seniority_reject=seniority_reject,
        companies=companies,
        priority_companies=priority_companies,
        enabled_scrapers=enabled_deduped,
        max_workers=DEFAULT_MAX_WORKERS,
    )


# ---------------------------------------------------------------------------
# Query generation via Haiku
# ---------------------------------------------------------------------------

_QUERY_GENERATION_PROMPT = """\
Generate {count} job search queries for LinkedIn/Indeed job boards.

Candidate profile:
- Title: {cv_title}
- Skills: {skills}
- Looking for: {target_positions}
- Level: {level}
- Location: {location}

Rules:
- Each query should be 2-4 words, optimized for job board keyword search.
- Include the level word ({level_word}) in most queries.
- Mix domain-specific terms (e.g. "VLSI intern") with broader terms (e.g. "software student").
- Don't include location in the query — it's passed separately.
- Return ONLY a JSON array of strings, no explanation.
"""


def generate_queries(
    profile: Optional[UserProfile] = None,
    count: int = 5,
    save: bool = True,
) -> List[str]:
    """Generate search queries via Haiku and optionally cache them in the profile.

    Returns a list of query strings. On API failure, returns a sensible
    rule-based fallback so the scan can still run.
    """
    if profile is None:
        profile = get_profile()

    # Determine level descriptor from experience_level
    exp = profile.experience_level
    if exp == "none" or (not exp and not profile.work_experience):
        if profile.is_student:
            level, level_word = "student", "student"
        else:
            level, level_word = "junior / entry-level", "junior"
    elif exp == "1-3":
        level, level_word = "junior", "junior"
    elif exp in ("3-7", "7+"):
        level, level_word = "experienced", ""
    else:
        level, level_word = "junior / entry-level", "junior"

    prompt = _QUERY_GENERATION_PROMPT.format(
        count=count,
        cv_title=profile.cv_title or "job seeker",
        skills=", ".join(profile.skills) if profile.skills else "not specified",
        target_positions=", ".join(profile.target_positions) if profile.target_positions else "general",
        level=level,
        level_word=level_word,
        location=profile.country or "Israel",
    )

    try:
        Config.validate()
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        queries = json.loads(raw)
        if not isinstance(queries, list) or not queries:
            raise ValueError("Expected non-empty JSON array")
        queries = [str(q).strip() for q in queries if str(q).strip()]

    except Exception as e:
        logger.warning("Haiku query generation failed (%s) — using fallback", e)
        queries = _fallback_queries(profile)

    if save:
        _save_cached_queries(profile, queries)

    return queries


def refresh_queries(profile: Optional[UserProfile] = None) -> List[str]:
    """Regenerate queries (ignores cache) and save to profile."""
    if profile is None:
        profile = get_profile()
    return generate_queries(profile, save=True)


# ---------------------------------------------------------------------------
# Fallback: rule-based queries when Haiku is unavailable
# ---------------------------------------------------------------------------

def _fallback_queries(profile: UserProfile) -> List[str]:
    """Build simple queries from target_positions + level keyword."""
    exp = profile.experience_level
    if exp == "none" or (not exp and not profile.work_experience):
        suffix = "student" if profile.is_student else "junior"
    elif exp == "1-3":
        suffix = "junior"
    else:
        suffix = ""

    positions = profile.target_positions or ["engineer"]
    queries = []
    for pos in positions[:5]:
        q = f"{pos} {suffix}".strip()
        queries.append(q)

    # Always include a generic one
    if suffix and suffix not in queries:
        queries.append(suffix)

    return queries


# ---------------------------------------------------------------------------
# Cache helpers — store queries in profile's search_config field
# ---------------------------------------------------------------------------

def _get_cached_queries(profile: UserProfile) -> Optional[List[str]]:
    """Read cached queries from profile. Returns None if not cached."""
    sc = getattr(profile, "search_config", None)
    if not sc or not isinstance(sc, dict):
        return None
    queries = sc.get("queries")
    if queries and isinstance(queries, list) and len(queries) > 0:
        return [str(q) for q in queries]
    return None


def _save_cached_queries(profile: UserProfile, queries: List[str]) -> None:
    """Save generated queries into the profile and write to disk."""
    sc = getattr(profile, "search_config", None)
    if not isinstance(sc, dict):
        sc = {}

    sc["queries"] = queries
    sc["generated_at"] = datetime.now().isoformat()
    profile.search_config = sc
    profile.save()
    logger.info("Saved %d search queries to profile", len(queries))


# ---------------------------------------------------------------------------
# Company list loader
# ---------------------------------------------------------------------------

_COMPANY_SUGGESTION_PROMPT = """\
Suggest companies for a job seeker to watch.

Candidate profile:
- Target roles: {target_positions}
- Skills: {skills}
- Experience level: {experience_level}
- Location: {country}
{education_line}
Available companies in our database (name — domains):
{registry_list}

Instructions:
1. Pick companies from the database above that are relevant to this candidate. \
Include companies where the candidate could realistically contribute, even if \
the domain is not a perfect match. Skip only companies in clearly unrelated fields.
2. Suggest up to 5 additional well-known companies NOT in the database above \
that hire for these roles in {country}.

Return ONLY a JSON object, no explanation:
{{"registry": ["Company1", "Company2"], "additional": ["Company3", "Company4"]}}
"""


def suggest_companies(
    profile: Optional[UserProfile] = None,
    registry_path=None,
) -> dict:
    """Ask Haiku to suggest companies from registry + free-form.

    Returns {"registry": [...], "additional": [...]}.
    On API failure, returns all priority companies from registry.
    """
    if profile is None:
        profile = get_profile()

    registry = _load_company_registry(registry_path)
    registry_names = {entry["name"]: entry for entry in registry.values()}

    # Build numbered registry list for the prompt
    lines = []
    for i, (name, entry) in enumerate(registry_names.items(), 1):
        domains = ", ".join(entry.get("domain", []))
        lines.append(f"{i}. {name} — {domains}")
    registry_list = "\n".join(lines)

    # Education line (only if set)
    education_line = ""
    if profile.degree and profile.university:
        education_line = f"- Education: {profile.degree} at {profile.university}\n"

    prompt = _COMPANY_SUGGESTION_PROMPT.format(
        target_positions=", ".join(profile.target_positions) if profile.target_positions else "general",
        skills=", ".join(profile.skills) if profile.skills else "not specified",
        experience_level=profile.experience_level or "not specified",
        country=profile.country or "Israel",
        education_line=education_line,
        registry_list=registry_list,
    )

    try:
        Config.validate()
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("Expected JSON object")

        # Validate registry names — only keep exact matches
        valid_registry = [
            name for name in result.get("registry", [])
            if name in registry_names
        ]
        additional = [
            str(name).strip() for name in result.get("additional", [])
            if str(name).strip()
        ]

        return {"registry": valid_registry, "additional": additional}

    except Exception as e:
        logger.warning("Haiku company suggestion failed (%s) — using fallback", e)
        return _fallback_company_suggestions(registry_names)


def _fallback_company_suggestions(registry_names: dict) -> dict:
    """Return all priority companies when Haiku is unavailable."""
    priority = [
        name for name, entry in registry_names.items()
        if entry.get("priority")
    ]
    return {"registry": priority, "additional": []}


def _load_company_registry(registry_path=None) -> dict:
    """Load companies.json as a lookup dict keyed by lowercase company name.

    Returns {name_lower: {full entry dict}} or {} on failure.
    """
    companies_file = registry_path or Config.companies_file()
    try:
        with open(companies_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            c["name"].lower(): c
            for c in data.get("companies", [])
            if c.get("name")
        }
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.warning("Could not load companies.json: %s", e)
        return {}


def _load_companies(profile: Optional[UserProfile] = None) -> tuple:
    """Load (all_companies, priority_companies).

    - Non-empty watchlist → use it (all are priority). Cross-refs with
      companies.json for scraper metadata; unknown companies still included.
    - Empty watchlist → ([], []) — no company scans.
    - No profile → fall back to companies.json registry.
    """
    if profile is None:
        try:
            profile = get_profile()
        except (FileNotFoundError, ValueError):
            profile = None

    if profile is not None:
        # Watchlist drives company scanning
        if profile.watchlist:
            return list(profile.watchlist), list(profile.watchlist)
        # Empty watchlist = no company scans
        return [], []

    # No profile at all — fall back to companies.json
    registry = _load_company_registry()
    all_names = [entry["name"] for entry in registry.values()]
    priority = [entry["name"] for entry in registry.values() if entry.get("priority")]
    return all_names, priority
