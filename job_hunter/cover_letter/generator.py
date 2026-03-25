"""Cover Letter Generator using Claude AI."""

import anthropic
from datetime import datetime
from typing import Optional

from job_hunter.config import Config
from job_hunter.jobs.scraper import JobListing
from job_hunter.logger import get_logger
from .templates import LETTER_STRUCTURE, get_company_tone, TONE_INSTRUCTIONS
from .history import CoverLetterHistory

logger = get_logger(__name__)


class CoverLetterGenerator:
    """Generates personalized cover letters using Claude AI."""

    SYSTEM_PROMPT = '''You write short cover letters that sound like a real person wrote them.

HARD RULES:
- 80-120 words maximum (excluding signature)
- 3 short paragraphs only
- Do NOT list grades or GPA — they are in the attached CV
- Do NOT repeat information that appears in the CV (courses, military service, skills list)
- Do NOT use the word "genuinely", "solid", "strong", "passionate", "excited"
- Do NOT use "caught my attention" or "I am writing to express"
- Do NOT describe what the job posting says — the reader already knows

WHAT THE LETTER SHOULD DO:
The cover letter answers ONE question: "Why should we talk to this person?"
It should say something the CV cannot say:
- A specific reason you want THIS company (not generic praise)
- What you would bring that other candidates probably don't
- Something personal that connects you to the role

PARAGRAPH 1 (2 sentences max):
Who you are + why this specific company/role interests you.
Be specific — mention something about the company that you actually know or care about.

PARAGRAPH 2 (2 sentences max):
ONE thing that makes you different. Not a list of skills.
Something like: "I built X which taught me Y" or "My background in Z gives me a perspective that..."
Do NOT list grades. Do NOT list courses. The CV handles that.

PARAGRAPH 3 (1 sentence):
CV attached + availability. Nothing more.

GREETING:
- If recruiter_name is provided: "Dear [Name],"
- Otherwise: "Dear [Company] Hiring Team,"

SIGNATURE:
[Name]
[Email] | [Phone]

ACADEMIC YEAR — CRITICAL:
- The prompt states the candidate's year explicitly. Use it exactly as given.
'''

    def __init__(self):
        Config.validate()
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = Config.CLAUDE_MODEL
        self.history = CoverLetterHistory()

    def generate(
        self,
        job: JobListing,
        cv: dict,
        job_description: Optional[str] = None,
        language: str = "en",
        save_to_history: bool = True,
        recruiter_name: Optional[str] = None,
    ) -> str:
        """Generate a cover letter for a specific job."""
        contact = cv.get("contact", {})
        personal_info = {
            "name":     cv.get("name", ""),
            "email":    contact.get("email", ""),
            "phone":    contact.get("phone", ""),
            "linkedin": contact.get("linkedin", ""),
        }

        company_tone = get_company_tone(job.company)
        tone_instruction = TONE_INSTRUCTIONS.get(company_tone, TONE_INSTRUCTIONS["balanced"])
        academic_year = self._get_academic_year(cv)

        prompt = self._build_prompt(
            job=job,
            cv=cv,
            job_description=job_description,
            language=language,
            tone_instruction=tone_instruction,
            personal_info=personal_info,
            academic_year=academic_year,
            recruiter_name=recruiter_name,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=600,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as e:
            logger.error("Claude API error in CoverLetterGenerator.generate: %s", e)
            return None

        content = response.content[0].text.strip()

        if save_to_history:
            self.history.save(
                job_title=job.title,
                company=job.company,
                language=language,
                content=content,
                job_description=job_description or "",
            )

        return content

    def _get_academic_year(self, cv: dict) -> str:
        """Compute current academic year (e.g. '3rd') from education start year."""
        ordinals = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}
        try:
            edu = cv.get("education", [])
            if not edu:
                return "third"
            year_field = edu[0].get("year", "")
            start_year = int(year_field.split("-")[0].strip())
            current_year = datetime.now().year
            # Academic year starts in October; before October we're still in the same year
            if datetime.now().month < 10:
                current_year -= 1
            year_num = current_year - start_year + 1
            return ordinals.get(year_num, f"{year_num}th")
        except (ValueError, IndexError, AttributeError):
            return "third"

    def _build_prompt(
        self,
        job: JobListing,
        cv: dict,
        job_description: Optional[str],
        language: str,
        tone_instruction: str,
        personal_info: dict,
        academic_year: str = "third",
        recruiter_name: Optional[str] = None,
    ) -> str:
        """Build the prompt for cover letter generation."""
        import json

        lang_instruction = "Write in English." if language == "en" else "כתוב בעברית."

        if recruiter_name:
            greeting = f"Dear {recruiter_name} from the HR team at {job.company},"
        else:
            greeting = f"Dear {job.company} Hiring Team,"

        return f"""Write a SHORT cover letter (100-150 words body) for this application.

## Job:
- Title: {job.title}
- Company: {job.company}
- Location: {job.location}

## Job Description:
{job_description or "Not available — infer from title and company"}

## Candidate CV (JSON):
{json.dumps(cv, indent=2, ensure_ascii=False)}

## Candidate:
- Name: {personal_info['name']}
- Email: {personal_info['email']}
- Phone: {personal_info['phone']}
- Academic year: **{academic_year} year** (use this exactly — do not guess)

## Instructions:
- Language: {lang_instruction}
- Tone: {tone_instruction}
- Body must be 100-150 words. Count them. Cut if over.
- Use this exact greeting: {greeting}
Follow the structure and rules in the system prompt exactly.
"""


def generate_cover_letter(job: JobListing, cv: dict, **kwargs) -> str:
    """Convenience function for one-shot generation."""
    return CoverLetterGenerator().generate(job, cv, **kwargs)
