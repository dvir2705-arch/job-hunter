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

    SYSTEM_PROMPT = '''You are a professional cover letter writer. Write SHORT, honest cover letters.

TARGET LENGTH: 100-150 words maximum (body only, not counting greeting/signature).
If you exceed 150 words, you have failed. Cut ruthlessly.

STRUCTURE — exactly 3 parts:
1. PARAGRAPH 1 (2 sentences): Who the candidate is + what position they are applying for.
2. PARAGRAPH 2 (2-3 sentences): ONE differentiating point relevant to this specific role.
   - Software/Python/automation role → mention the job-hunter project (facts only: Python, REST APIs, dozens of company career pages)
   - Chip/hardware/verification role → mention relevant coursework or the math grades
   - Pick ONE. Do NOT list multiple selling points.
3. CLOSING (1 sentence): "My CV is attached. I'm available 2-3 days per week and would welcome the opportunity to discuss."

GREETING:
- If recruiter_name is provided: "Dear [Name],"
- Otherwise: "Dear [Company] Hiring Team,"

SIGNATURE (always exactly):
[Name]
[Email] | [Phone]

TONE — strictly enforced:
- Write plainly. Do NOT use: "passionate", "excited", "strong aptitude for", "genuine drive",
  "rigorous", "when it matters most", "I engage seriously", "truly", "deeply"
- No superlatives: not "exceptional", "outstanding", "remarkable"
- No self-deprecation: not "small project", "just a student"
- State facts. Let them speak.

NEVER include:
- Full list of grades (they are in the CV — the recruiter will read it)
- Detailed military description (it is in the CV)
- Claims about Linux, C++, or any skill not clearly in the CV
- More than one differentiating point in paragraph 2
- Filler sentences that add no information

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
        mention_job_hunter: bool = True,
        save_to_history: bool = True,
        recruiter_name: Optional[str] = None,
    ) -> str:
        """Generate a cover letter for a specific job."""
        # Extract personal info from CV schema (top-level name + contact sub-dict)
        contact = cv.get("contact", {})
        personal_info = {
            "name":     cv.get("name", ""),
            "email":    contact.get("email", ""),
            "phone":    contact.get("phone", ""),
            "linkedin": contact.get("linkedin", ""),
        }

        company_tone = get_company_tone(job.company)
        tone_instruction = TONE_INSTRUCTIONS.get(company_tone, TONE_INSTRUCTIONS["balanced"])
        should_mention = mention_job_hunter and self._is_project_relevant(job, job_description)

        academic_year = self._get_academic_year(cv)

        prompt = self._build_prompt(
            job=job,
            cv=cv,
            job_description=job_description,
            language=language,
            tone_instruction=tone_instruction,
            mention_project=should_mention,
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
                mentioned_job_hunter=should_mention,
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

    def _is_project_relevant(self, job: JobListing, job_description: Optional[str]) -> bool:
        """Return True if mentioning the job-hunter project fits this role."""
        relevant_keywords = ["python", "automation", "scripting", "api", "software", "programming"]
        hardware_only = ["vlsi", "layout", "physical design", "dft"]

        text = f"{job.title} {job_description or ''}".lower()

        if any(kw in text for kw in hardware_only):
            if not any(kw in text for kw in relevant_keywords):
                return False
        return True

    def _build_prompt(
        self,
        job: JobListing,
        cv: dict,
        job_description: Optional[str],
        language: str,
        tone_instruction: str,
        mention_project: bool,
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

        project_hint = ""
        if mention_project:
            project_hint = (
                "- For paragraph 2, use the job-hunter project as the differentiating point "
                "(Python, REST APIs, scraping dozens of company career pages, Claude AI integration).\n"
            )

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
{project_hint}Follow the structure and rules in the system prompt exactly.
"""


def generate_cover_letter(job: JobListing, cv: dict, **kwargs) -> str:
    """Convenience function for one-shot generation."""
    return CoverLetterGenerator().generate(job, cv, **kwargs)
