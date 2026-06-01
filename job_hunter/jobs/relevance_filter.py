"""Filter jobs based on user profile relevance."""

import json
import re
from typing import List, Optional, Tuple

import anthropic

from job_hunter.config import Config
from job_hunter.logger import get_logger
from job_hunter.profile import get_profile
from .scraper import JobListing


# Maps profile terms → common job title synonyms (generic, not user-specific)
# When a profile contains a key, all its synonyms are added to the accept list.
TITLE_SYNONYMS = {
    "software": ["sw", "swe", "r&d"],
    "hardware": ["hw", "board design"],
    "embedded": ["firmware", "rt embedded"],
    "chip design": ["vlsi", "rtl", "asic", "verification", "hardware",
                    "post si", "post-silicon"],
    "machine learning": ["ml", "deep learning", "ai"],
    "data science": ["data scientist"],
    "data engineer": ["data engineering"],
    "data": ["data engineer", "data engineering"],
    "rf": ["radio frequency", "rfic", "phy", "wireless"],
    "dsp": ["signal processing", "algorithm", "algorithms", "phy"],
    "verification": ["dv", "formal verification"],
    "algorithm": ["algorithms"],
    "fpga": [],
    "devops": ["sre", "site reliability"],
    "frontend": ["front-end", "react", "angular"],
    "backend": ["back-end"],
    "fullstack": ["full-stack", "full stack"],
    "cyber": ["cybersecurity", "security"],
    "cloud": ["aws", "azure", "gcp"],
    "mobile": ["android", "ios"],
    "electrical": ["emc", "firmware", "hardware", "hw", "embedded",
                   "power", "laser", "camera"],
}


def _get_relevant_keywords() -> List[str]:
    """Build accept keywords from profile: domains + target_positions + skills + synonyms."""
    try:
        p = get_profile()
    except (FileNotFoundError, ValueError):
        return []

    keywords = set()

    # Add domains (existing behavior)
    for d in p.domains:
        keywords.add(d.lower())

    # Add target_positions as full phrases.
    # Only split into individual words when domains is empty (new user fallback).
    for pos in p.target_positions:
        pos_lower = pos.lower()
        keywords.add(pos_lower)
    if not p.domains:
        # Fallback for users who only filled target_positions — split into words
        for pos in p.target_positions:
            for word in pos.lower().split():
                if len(word) > 2:
                    keywords.add(word)

    # Add skills
    for skill in p.skills:
        keywords.add(skill.lower())

    # Expand with synonyms
    expanded = set()
    for kw in keywords:
        if kw in TITLE_SYNONYMS:
            expanded.update(TITLE_SYNONYMS[kw])
    keywords.update(expanded)

    return list(keywords)

# Operational/facilities roles — irrelevant for any job-seeker using this tool
ALWAYS_IRRELEVANT = [
    "catering", "leasing", "facilities", "food", "kitchen",
    "receptionist", "warehouse", "driver", "delivery", "cafeteria",
    "maintenance", "cleaning", "security guard", "personal assistant",
    "night operator", "night shift", "assembly team",
    "intralogistics", "operator student",
]

# Professional fields — only irrelevant if NOT in the user's domain keywords
PROFESSIONAL_FIELDS = [
    "legal", "lawyer", "attorney", "law",
    "mechanical", "mechanic",
    "civil", "construction", "building",
    "chemical", "chemistry", "pharmaceutical", "pharma", "lab technician",
    "biomedical", "biology", "biotech", "medical device",
    "accounting", "accountant", "finance", "financial", "tax",
    "human resources", "recruitment", "recruiter", "talent acquisition",
    "marketing", "sales", "business development",
    "customer success", "customer support",
    "graphic design", "ui designer", "ux designer",
    "content writer", "copywriter", "social media",
    "writer", "writing", "editor", "editorial",
    "translator", "translation", "proofreader", "journalist",
    "public relations",
    "supply chain", "logistics", "procurement",
    "office manager", "administrative", "secretary",
    "manual testing", "qa manual",
    "support engineer", "technical writer",
    "technical support", "manual qa",
    "documentation student", "composites manufacturing",
    "network operations center",
    "solution designer",
    "quality engineering", "quality assurance",
    "event", "hospitality", "retail", "fashion",
    "interior design", "agriculture", "veterinary",
    "nursing", "pharmacy", "dental",
    "physiotherapy", "occupational therapy",
    "teaching", "teacher", "tutor",
]


def _get_irrelevant_keywords() -> List[str]:
    """Build irrelevant keywords, excluding fields that overlap with the user's profile."""
    relevant = set(_get_relevant_keywords())
    field_irrelevant = [kw for kw in PROFESSIONAL_FIELDS if kw not in relevant]
    return ALWAYS_IRRELEVANT + field_irrelevant

_IRRELEVANT_COMPANIES_ALL = [
    "teva", "pharmaceutical", "pharma", "law firm", "bank", "insurance",
]


def _get_irrelevant_companies() -> List[str]:
    """Build irrelevant company keywords, excluding those in user's profile."""
    relevant = set(_get_relevant_keywords())
    return [kw for kw in _IRRELEVANT_COMPANIES_ALL if kw not in relevant]

DEFAULT_SENIORITY_KEYWORDS = [
    "senior", "manager", "director", "principal", "vp", "vice president",
    "head of", "chief",
]


def _build_fit_score_prompt() -> str:
    """Build the fit-score system prompt from user profile."""
    p = get_profile()
    skills_str = ", ".join(p.skills)
    skills_not_str = ", ".join(p.skills_not) if p.skills_not else "N/A"
    targets_str = ", ".join(p.target_positions)

    # Adaptive identity line
    if p.is_student:
        identity = f"{p.cv_title}, {p.year}-year student at {p.university}"
        level_desc = "student/entry-level"
    elif p.education:
        identity = f"{p.cv_title}, {p.degree} from {p.university}"
        level_desc = "entry to mid-level"
    elif p.work_experience:
        latest = p.work_experience[0]
        identity = f"{p.cv_title}, previously {latest.get('title', '')} at {latest.get('company', '')}"
        level_desc = "experienced"
    else:
        identity = p.cv_title or "job seeker"
        level_desc = "entry-level"

    return f"""\
You are a job-fit evaluator. Score how well a job fits this candidate:

**Candidate profile:**
- {identity}
- Skills: {skills_str}
- Looking for: positions in {targets_str}
- NOT experienced in: {skills_not_str}

**Scoring guide:**
- 80-100: Strong fit — domain matches ({targets_str}), {level_desc} appropriate, uses candidate's skills
- 60-79: Decent fit — related field, some skill overlap, reasonable for this candidate
- 40-59: Weak fit — tangential field or requires significant skills the candidate lacks
- 20-39: Poor fit — different field, heavy experience requirements, or unrelated skills
- 0-19: No fit — completely unrelated field or clearly mismatched seniority

Return ONLY valid JSON:
{{"score": <0-100>, "reason": "<one sentence explaining the score>"}}
"""


HAIKU_MODEL = "claude-haiku-4-5-20251001"


def score_job_fit(
    title: str, company: str, description: str,
) -> Optional[Tuple[int, str]]:
    """Ask Claude Haiku to score how well a job fits the user profile.

    Returns (score, reason) or None on failure.
    """
    try:
        Config.validate()
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=150,
            system=_build_fit_score_prompt(),
            messages=[{
                "role": "user",
                "content": f"Job: {title} at {company}\n\nDescription:\n{description}",
            }],
        )
    except anthropic.APIError:
        return None

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    try:
        data = json.loads(raw)
        return (int(data["score"]), data.get("reason", ""))
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _keyword_matches(keyword: str, text: str) -> bool:
    """Check if keyword appears in text.

    Short keywords (<=3 chars) use word-boundary matching to avoid false
    positives like "c" matching any title containing the letter 'c'.
    Longer keywords use substring matching (existing behaviour).
    """
    if len(keyword) <= 3:
        return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text))
    return keyword in text


def filter_relevant_jobs(
    jobs: List[JobListing],
    seniority_reject: Optional[List[str]] = None,
) -> Tuple[List[JobListing], List[JobListing]]:
    """Filter jobs in two layers.

    Layer 1: Fast title-based filtering.
    Layer 2: Always AI-score uncertain jobs (Haiku) for accurate filtering.

    Args:
        jobs: List of job listings to filter.
        seniority_reject: Seniority keywords to reject. If None, uses the
            default full list (rejects senior, manager, director, etc.).
            Pass a reduced list for experienced users.

    Returns (accepted, rejected).
    """
    active_seniority = seniority_reject if seniority_reject is not None else DEFAULT_SENIORITY_KEYWORDS

    # Cache keyword lists (avoid regenerating per job)
    irrelevant_kws = _get_irrelevant_keywords()
    relevant_kws = _get_relevant_keywords()
    irrelevant_companies = _get_irrelevant_companies()

    accepted = []
    rejected = []
    uncertain = []

    for job in jobs:
        title_lower = job.title.lower()
        company_lower = job.company.lower()

        # Company blacklist
        if any(_keyword_matches(kw, company_lower) for kw in irrelevant_companies):
            rejected.append(job)
            continue

        # Seniority mismatch — reject roles above the user's level
        if any(kw in title_lower for kw in active_seniority):
            rejected.append(job)
            continue

        has_irrelevant = any(_keyword_matches(kw, title_lower) for kw in irrelevant_kws)
        has_relevant = any(_keyword_matches(kw, title_lower) for kw in relevant_kws)

        if has_irrelevant and has_relevant:
            # Both signals — let AI decide instead of blanket reject
            uncertain.append(job)
        elif has_irrelevant:
            rejected.append(job)
        elif has_relevant:
            accepted.append(job)
        elif "student" in title_lower or "intern" in title_lower:
            # Has "student"/"intern" but no clear signal — needs AI check
            uncertain.append(job)
        else:
            rejected.append(job)

    # Layer 2: Batch Haiku filter for uncertain jobs (title-only, no description fetch)
    if uncertain:
        logger = get_logger("relevance_filter")
        batch_accepted, batch_rejected = _batch_haiku_filter(uncertain)
        accepted.extend(batch_accepted)
        rejected.extend(batch_rejected)

        if batch_accepted or batch_rejected:
            print(
                f"AI-checked {len(batch_accepted) + len(batch_rejected)} uncertain jobs "
                f"({len(batch_accepted)} accepted, {len(batch_rejected)} rejected)"
            )

    return accepted, rejected


# ---------------------------------------------------------------------------
# Batch Haiku filter — single API call for all uncertain titles
# ---------------------------------------------------------------------------

BATCH_SIZE = 15  # Max jobs per Haiku call to keep response quality high


def _batch_haiku_filter(
    jobs: List[JobListing],
) -> Tuple[List[JobListing], List[JobListing]]:
    """Filter uncertain jobs via batch Haiku call (title + company only).

    Sends all uncertain titles in one prompt, asks for accept/reject per job.
    Falls back to accepting all on any failure (benefit of doubt).
    Splits into batches of BATCH_SIZE if needed.
    """
    logger = get_logger("relevance_filter")

    if not jobs:
        return [], []

    accepted = []
    rejected = []

    # Split into batches
    batches = [jobs[i:i + BATCH_SIZE] for i in range(0, len(jobs), BATCH_SIZE)]

    for batch in batches:
        decisions = _haiku_batch_call(batch)
        if decisions is None:
            # Haiku failed — accept all (benefit of doubt)
            logger.warning("Batch Haiku filter failed — accepting all %d uncertain jobs", len(batch))
            accepted.extend(batch)
            continue

        for i, job in enumerate(batch):
            decision = decisions.get(str(i + 1), "accept").lower().strip()
            if decision == "reject":
                logger.info("Batch rejected: %s at %s", job.title, job.company)
                rejected.append(job)
            else:
                logger.info("Batch accepted: %s at %s", job.title, job.company)
                accepted.append(job)

    return accepted, rejected


def _haiku_batch_call(jobs: List[JobListing]) -> Optional[dict]:
    """Send a single Haiku call to classify a batch of job titles.

    Returns dict like {"1": "accept", "2": "reject", ...} or None on failure.
    """
    try:
        p = get_profile()
    except (FileNotFoundError, ValueError):
        return None

    targets = ", ".join(p.target_positions) if p.target_positions else "general"
    skills = ", ".join(p.skills) if p.skills else "not specified"
    domains = ", ".join(p.domains) if p.domains else "not specified"

    # Build identity
    if p.is_student:
        level = f"student ({p.year} year, {p.degree} at {p.university})"
    elif p.education:
        level = f"graduate ({p.degree} from {p.university})"
    elif p.work_experience:
        level = "experienced professional"
    else:
        level = "entry-level"

    job_lines = []
    for i, job in enumerate(jobs, 1):
        loc = job.location.split(",")[0].strip() if job.location else ""
        job_lines.append(f'{i}. "{job.title}" at {job.company}, {loc}')

    prompt = f"""\
You are a job relevance filter for a job seeker.

Profile:
- Looking for: {targets}
- Skills: {skills}
- Domains: {domains}
- Level: {level}

For each job below, respond ACCEPT or REJECT.
ACCEPT if the role is potentially relevant to this candidate's field or skills.
REJECT only if the role is clearly in an unrelated field.
When uncertain, lean toward ACCEPT — don't miss opportunities.

{chr(10).join(job_lines)}

Return ONLY a JSON object: {{"1": "accept", "2": "reject", ...}}"""

    try:
        Config.validate()
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        return None

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    return None
