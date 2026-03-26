"""Filter jobs based on user profile relevance."""

import json
from typing import List, Optional, Tuple

import anthropic

from job_hunter.config import Config
from .scraper import JobListing

RELEVANT_KEYWORDS = [
    # Electrical Engineering
    "electrical", "electronic", "electronics", "ee", "e&e",
    # Software / Programming
    "software", "developer", "programming", "python", "code", "coding",
    # Chip Design / Hardware
    "chip", "asic", "fpga", "rtl", "verilog", "vhdl", "verification",
    "digital design", "analog", "hardware", "silicon", "semiconductor",
    "processor", "architecture", "vlsi", "dsp",
    # AI / ML
    "ai", "ml", "machine learning", "deep learning", "neural", "data science",
    "computer vision", "nlp",
    # Embedded / Firmware
    "embedded", "firmware", "rtos", "microcontroller", "arm", "drivers",
    # RF / Signals
    "rf", "radio", "signal", "communication", "wireless", "antenna", "radar",
    "modem", "5g", "lte",
    # General tech
    "algorithm", "devops", "cloud", "backend", "frontend",
    "full stack", "fullstack", "api", "automation",
]

IRRELEVANT_KEYWORDS = [
    # Completely different fields
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
    "supply chain", "logistics", "procurement",
    "office manager", "administrative", "secretary",
    "manual testing", "qa manual",
    "support engineer", "technical writer",
    # Facilities / operations
    "catering", "leasing", "facilities", "food", "kitchen",
    "receptionist", "warehouse", "driver", "delivery", "cafeteria",
    "maintenance", "cleaning", "security guard", "personal assistant",
    "night operator", "night shift",
    "technical support", "manual qa",
    "documentation student", "composites manufacturing",
    "network operations center", "assembly team",
    "solution designer", "intralogistics", "operator student",
    "quality engineering", "quality assurance",
]

IRRELEVANT_COMPANIES = [
    "teva", "pharmaceutical", "pharma", "law firm", "bank", "insurance",
]

SENIORITY_KEYWORDS = [
    "senior", "manager", "director", "principal", "vp", "vice president",
    "head of", "chief",
]


FIT_SCORE_PROMPT = """\
You are a job-fit evaluator. Score how well a job fits this candidate:

**Candidate profile:**
- 3rd-year Electrical Engineering student (BSc), Ben-Gurion University
- Skills: Python, MATLAB, Assembly, signal processing, digital systems, ML basics
- Looking for: student/internship positions in software, DSP, chip design, RF, embedded, AI/ML
- NOT experienced in: Linux administration, C++, FPGA hands-on, DevOps

**Scoring guide:**
- 80-100: Strong fit — domain matches (software/DSP/RF/embedded/AI), student-level, uses candidate's skills
- 60-79: Decent fit — related field, some skill overlap, reasonable for a student to apply
- 40-59: Weak fit — tangential field or requires significant skills the candidate lacks
- 20-39: Poor fit — different field, heavy experience requirements, or unrelated skills
- 0-19: No fit — completely unrelated field or clearly senior role

Return ONLY valid JSON:
{"score": <0-100>, "reason": "<one sentence explaining the score>"}
"""


def score_job_fit(
    title: str, company: str, description: str,
) -> Optional[Tuple[int, str]]:
    """Ask Claude to score how well a job fits the user profile.

    Returns (score, reason) or None on failure.
    """
    try:
        Config.validate()
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=Config.CLAUDE_MODEL,
            max_tokens=150,
            system=FIT_SCORE_PROMPT,
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
    deep_check: bool = True,
) -> Tuple[List[JobListing], List[JobListing]]:
    """Filter jobs in two layers.

    Layer 1: Fast title-based filtering.
    Layer 2: If deep_check=True, fetch description for uncertain jobs.

    Returns (accepted, rejected).
    """
    accepted = []
    rejected = []
    uncertain = []

    for job in jobs:
        title_lower = job.title.lower()
        company_lower = job.company.lower()

        # Company blacklist
        if any(kw in company_lower for kw in IRRELEVANT_COMPANIES):
            rejected.append(job)
            continue

        # Seniority mismatch — reject roles clearly above student level
        if any(kw in title_lower for kw in SENIORITY_KEYWORDS):
            rejected.append(job)
            continue

        # Irrelevant keyword in title — reject even if "student" is present
        if any(kw in title_lower for kw in IRRELEVANT_KEYWORDS):
            rejected.append(job)
            continue

        # Relevant keyword in title — accept immediately
        if any(kw in title_lower for kw in RELEVANT_KEYWORDS):
            accepted.append(job)
            continue

        # Has "student"/"intern" but no clear signal — needs description check
        if "student" in title_lower or "intern" in title_lower:
            uncertain.append(job)
        else:
            rejected.append(job)

    # Layer 2: AI fit-score check for uncertain jobs
    if deep_check and uncertain:
        from job_hunter.jobs.scraper import fetch_job_description
        from job_hunter.logger import get_logger
        logger = get_logger("relevance_filter")

        deep_accepted = 0
        deep_rejected = 0
        FIT_THRESHOLD = 55

        for job in uncertain:
            try:
                description = fetch_job_description(job)
                if not description:
                    accepted.append(job)
                    deep_accepted += 1
                    continue

                result = score_job_fit(job.title, job.company, description)

                if result is None:
                    # Scoring failed — benefit of doubt
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
                logger.warning("Could not deep-check %s: %s", job.title, e)
                accepted.append(job)
                deep_accepted += 1

        if deep_accepted + deep_rejected > 0:
            print(
                f"Deep-checked {deep_accepted + deep_rejected} uncertain jobs "
                f"({deep_accepted} accepted, {deep_rejected} rejected)"
            )

    elif uncertain:
        # deep_check disabled — give benefit of doubt
        accepted.extend(uncertain)

    return accepted, rejected
