"""Job requirements analyzer — extracts structured requirements from job descriptions."""

import json
from dataclasses import dataclass
from typing import List, Optional

import anthropic

from job_hunter.config import Config
from job_hunter.logger import get_logger

logger = get_logger(__name__)


@dataclass
class JobRequirements:
    """Structured requirements extracted from a job description."""

    # What they're looking for
    required_skills: List[str]    # e.g. ["Python", "C++", "MATLAB"]
    preferred_skills: List[str]   # nice-to-have skills
    education: str                # e.g. "BSc Electrical Engineering"
    experience_level: str         # "student", "junior", "mid", "senior"

    # What the role involves
    role_summary: str             # 1 sentence: what you'd actually do
    key_technologies: List[str]   # main tools/technologies used
    domain: str                   # "software", "chip_design", "rf", "embedded", "ai_ml", "other"

    # Metadata
    company: str
    title: str
    location: str


class JobAnalyzer:
    """Analyzes job descriptions using Claude AI."""

    SYSTEM_PROMPT = """You extract structured job requirements from job descriptions.

Return ONLY valid JSON with these exact fields:
{
    "required_skills": ["skill1", "skill2"],
    "preferred_skills": ["skill1"],
    "education": "degree requirement as stated",
    "experience_level": "student" or "junior" or "mid" or "senior",
    "role_summary": "one sentence describing what the person will actually do",
    "key_technologies": ["tech1", "tech2"],
    "domain": "software" or "chip_design" or "rf" or "embedded" or "ai_ml" or "other"
}

Rules:
- Only include skills EXPLICITLY mentioned in the description
- Do NOT invent or assume requirements
- role_summary should be simple and concrete, not marketing language
- If something is unclear, use "unspecified"
- Return ONLY JSON, no explanation
"""

    def __init__(self):
        Config.validate()
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = Config.CLAUDE_MODEL

    def analyze(
        self,
        job_title: str,
        company: str,
        location: str,
        description: str,
    ) -> Optional[JobRequirements]:
        """Parse a job description into structured requirements."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=self.SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"Job: {job_title} at {company}\n\nDescription:\n{description}",
                }],
            )
        except anthropic.APIError as e:
            logger.error("Claude API error in JobAnalyzer.analyze: %s", e)
            return None

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("JSON parse error in JobAnalyzer.analyze: %s\nRaw: %s", e, raw)
            return None

        return JobRequirements(
            required_skills=data.get("required_skills", []),
            preferred_skills=data.get("preferred_skills", []),
            education=data.get("education", "unspecified"),
            experience_level=data.get("experience_level", "unspecified"),
            role_summary=data.get("role_summary", ""),
            key_technologies=data.get("key_technologies", []),
            domain=data.get("domain", "other"),
            company=company,
            title=job_title,
            location=location,
        )
