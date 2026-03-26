"""Filter jobs based on user profile relevance."""

from typing import List, Tuple
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
    # Facilities / operations
    "catering", "leasing", "facilities", "food", "kitchen",
    "receptionist", "warehouse", "driver", "delivery", "cafeteria",
    "maintenance", "cleaning", "security guard", "personal assistant",
]

IRRELEVANT_COMPANIES = [
    "teva", "pharmaceutical", "pharma", "law firm", "bank", "insurance",
]


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

    # Layer 2: JobAnalyzer-based check for uncertain jobs
    if deep_check and uncertain:
        from job_hunter.jobs.scraper import fetch_job_description
        from job_hunter.jobs.analyzer import JobAnalyzer
        from job_hunter.logger import get_logger
        logger = get_logger("relevance_filter")

        RELEVANT_DOMAINS = {"software", "chip_design", "rf", "embedded", "ai_ml"}
        DVIR_SKILLS = {"python", "matlab", "assembly", "signal processing", "digital systems", "machine learning"}

        analyzer = JobAnalyzer()
        deep_accepted = 0
        deep_rejected = 0

        for job in uncertain:
            try:
                description = fetch_job_description(job)
                if not description:
                    # Can't fetch — benefit of doubt
                    accepted.append(job)
                    deep_accepted += 1
                    continue

                requirements = analyzer.analyze(
                    job_title=job.title,
                    company=job.company,
                    location=getattr(job, "location", ""),
                    description=description,
                )

                if requirements is None:
                    # Analyzer failed — benefit of doubt
                    accepted.append(job)
                    deep_accepted += 1
                    continue

                if requirements.domain in RELEVANT_DOMAINS:
                    accepted.append(job)
                    deep_accepted += 1
                else:
                    # domain is "other" — check for skill overlap
                    job_skills = {s.lower() for s in requirements.required_skills}
                    if job_skills & DVIR_SKILLS:
                        accepted.append(job)
                        deep_accepted += 1
                    else:
                        logger.info(
                            "Deep-filtered (domain=%s, no skill overlap): %s at %s",
                            requirements.domain, job.title, job.company,
                        )
                        rejected.append(job)
                        deep_rejected += 1

            except Exception as e:
                logger.warning("Could not deep-check %s: %s", job.title, e)
                accepted.append(job)  # benefit of doubt
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
