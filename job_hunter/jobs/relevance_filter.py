"""Filter jobs based on user profile relevance."""

import json
from typing import List, Optional, Tuple

import anthropic

from job_hunter.config import Config
from job_hunter.logger import get_logger
from job_hunter.profile import get_profile
from .scraper import JobListing, fetch_job_description


def _get_relevant_keywords() -> List[str]:
    """Load domain keywords from user profile."""
    return get_profile().domains

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
    """Build irrelevant keywords, excluding fields that overlap with the user's domains."""
    try:
        domains = {d.lower() for d in get_profile().domains}
    except (FileNotFoundError, ValueError):
        domains = set()

    field_irrelevant = [kw for kw in PROFESSIONAL_FIELDS if kw not in domains]
    return ALWAYS_IRRELEVANT + field_irrelevant

_IRRELEVANT_COMPANIES_ALL = [
    "teva", "pharmaceutical", "pharma", "law firm", "bank", "insurance",
]


def _get_irrelevant_companies() -> List[str]:
    """Build irrelevant company keywords, excluding those in user's domains."""
    try:
        domains = {d.lower() for d in get_profile().domains}
    except (FileNotFoundError, ValueError):
        domains = set()
    return [kw for kw in _IRRELEVANT_COMPANIES_ALL if kw not in domains]

SENIORITY_KEYWORDS = [
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


def filter_relevant_jobs(
    jobs: List[JobListing],
) -> Tuple[List[JobListing], List[JobListing]]:
    """Filter jobs in two layers.

    Layer 1: Fast title-based filtering.
    Layer 2: Always AI-score uncertain jobs (Haiku) for accurate filtering.

    Returns (accepted, rejected).
    """
    accepted = []
    rejected = []
    uncertain = []

    for job in jobs:
        title_lower = job.title.lower()
        company_lower = job.company.lower()

        # Company blacklist
        if any(kw in company_lower for kw in _get_irrelevant_companies()):
            rejected.append(job)
            continue

        # Seniority mismatch — reject roles clearly above student level
        if any(kw in title_lower for kw in SENIORITY_KEYWORDS):
            rejected.append(job)
            continue

        # Irrelevant keyword in title — reject even if "student" is present
        if any(kw in title_lower for kw in _get_irrelevant_keywords()):
            rejected.append(job)
            continue

        # Relevant keyword in title — accept immediately
        if any(kw in title_lower for kw in _get_relevant_keywords()):
            accepted.append(job)
            continue

        # Has "student"/"intern" but no clear signal — needs AI check
        if "student" in title_lower or "intern" in title_lower:
            uncertain.append(job)
        else:
            rejected.append(job)

    # Layer 2: Always AI-score uncertain jobs using Haiku
    if uncertain:
        logger = get_logger("relevance_filter")

        deep_accepted = 0
        deep_rejected = 0
        FIT_THRESHOLD = 55

        for job in uncertain:
            try:
                description = fetch_job_description(job)
                if not description:
                    logger.warning(
                        "No description for %s at %s — accepting (benefit of doubt)",
                        job.title, job.company,
                    )
                    accepted.append(job)
                    deep_accepted += 1
                    continue

                result = score_job_fit(job.title, job.company, description)

                if result is None:
                    logger.warning(
                        "AI scoring failed for %s at %s — accepting (benefit of doubt)",
                        job.title, job.company,
                    )
                    accepted.append(job)
                    deep_accepted += 1
                    continue

                score, reason = result
                if score >= FIT_THRESHOLD:
                    logger.info(
                        "Fit score %d (accepted): %s at %s — %s",
                        score, job.title, job.company, reason,
                    )
                    accepted.append(job)
                    deep_accepted += 1
                else:
                    logger.info(
                        "Fit score %d (rejected): %s at %s — %s",
                        score, job.title, job.company, reason,
                    )
                    rejected.append(job)
                    deep_rejected += 1

            except Exception as e:
                logger.warning(
                    "Deep-check error for %s at %s: %s — accepting (benefit of doubt)",
                    job.title, job.company, e,
                )
                accepted.append(job)
                deep_accepted += 1

        if deep_accepted + deep_rejected > 0:
            print(
                f"AI-checked {deep_accepted + deep_rejected} uncertain jobs "
                f"({deep_accepted} accepted, {deep_rejected} rejected)"
            )

    return accepted, rejected
