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

DEFAULT_MAX_WORKERS = 3


@dataclass
class SearchConfig:
    """Everything the scanner needs to run a profile-tailored search."""

    queries: List[str]
    location: str = "Israel"
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
    location = profile.location or "Israel"

    # --- Level / seniority -------------------------------------------------
    if profile.is_student:
        level_keywords = ["student", "intern"]
        seniority_reject = list(SENIORITY_REJECT_FULL)
    elif not profile.work_experience:
        level_keywords = ["junior", "entry level"]
        seniority_reject = list(SENIORITY_REJECT_FULL)
    else:
        level_keywords = []
        seniority_reject = list(SENIORITY_REJECT_EXPERIENCED)

    # --- Companies ---------------------------------------------------------
    companies, priority_companies = _load_companies()

    # --- Enabled scrapers --------------------------------------------------
    enabled = list(ALWAYS_ENABLED_SCRAPERS)
    company_names_lower = {c.lower() for c in companies}
    for company_name, scraper_name in COMPANY_SCRAPER_MAP.items():
        if company_name.lower() in company_names_lower:
            enabled.append(scraper_name)
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

    # Determine level descriptor
    if profile.is_student:
        level = "student"
        level_word = "student"
    elif not profile.work_experience:
        level = "junior / entry-level"
        level_word = "junior"
    else:
        level = "experienced"
        level_word = ""

    prompt = _QUERY_GENERATION_PROMPT.format(
        count=count,
        cv_title=profile.cv_title or "job seeker",
        skills=", ".join(profile.skills) if profile.skills else "not specified",
        target_positions=", ".join(profile.target_positions) if profile.target_positions else "general",
        level=level,
        level_word=level_word,
        location=profile.location or "Israel",
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
    if profile.is_student:
        suffix = "student"
    elif not profile.work_experience:
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

def _load_companies() -> tuple:
    """Load (all_companies, priority_companies) from companies.json.

    Returns ([], []) if the file doesn't exist or is malformed.
    """
    companies_file = Config.DATA_DIR / "jobs" / "companies.json"
    try:
        with open(companies_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = data.get("companies", [])
        all_names = [c["name"] for c in entries if c.get("name")]
        priority = [c["name"] for c in entries if c.get("name") and c.get("priority")]
        return all_names, priority
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.warning("Could not load companies.json: %s", e)
        return [], []
