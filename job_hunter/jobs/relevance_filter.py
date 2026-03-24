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
]

IRRELEVANT_COMPANIES = [
    "teva", "pharmaceutical", "pharma", "law firm", "bank", "insurance",
]


def filter_relevant_jobs(jobs: List[JobListing]) -> Tuple[List[JobListing], List[JobListing]]:
    """Split jobs into (relevant, removed) based on profile keywords.

    Keep a job if:
      - It has a RELEVANT keyword in the title, OR
      - It contains 'student' or 'intern' AND has no IRRELEVANT keyword
    Drop a job if:
      - Its company matches IRRELEVANT_COMPANIES, OR
      - Its title contains an IRRELEVANT keyword
    """
    relevant = []
    removed = []

    for job in jobs:
        title_lower = job.title.lower()
        company_lower = job.company.lower()

        if any(kw in company_lower for kw in IRRELEVANT_COMPANIES):
            removed.append(job)
            continue

        if any(kw in title_lower for kw in IRRELEVANT_KEYWORDS):
            removed.append(job)
            continue

        has_relevant = any(kw in title_lower for kw in RELEVANT_KEYWORDS)
        is_student_intern = "student" in title_lower or "intern" in title_lower

        if has_relevant or is_student_intern:
            relevant.append(job)
        else:
            removed.append(job)

    return relevant, removed
