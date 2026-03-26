"""Cover Letter Generator using Claude AI."""

import anthropic
from datetime import datetime
from typing import Optional

from job_hunter.config import Config
from job_hunter.jobs.scraper import JobListing
from job_hunter.logger import get_logger
from job_hunter.profile import get_profile
from .templates import LETTER_STRUCTURE, get_company_tone, TONE_INSTRUCTIONS
from .history import CoverLetterHistory

logger = get_logger(__name__)


def _build_system_prompt() -> str:
    """Build the cover letter system prompt from user profile."""
    p = get_profile()
    return f'''You fill in a cover letter template. Follow the structure exactly.

TEMPLATE (follow this exactly):

---
Dear [Company] Hiring Team,

I'm a [YEAR]-year {p.cv_title} at {p.university}, [FOCUS AREA]. I'm reaching out about the [EXACT JOB TITLE] position [in LOCATION if known].

[ONE SENTENCE connecting your relevant background to what the role requires]. I also have [ONE OTHER RELEVANT SKILL OR EXPERIENCE].

My CV is attached. I'm available for [internship/position] and happy to discuss further.

{p.signature_block()}
---

RULES FOR FILLING THE TEMPLATE:

[FOCUS AREA] — adapt based on job type:
- RF/Communications/DSP role → "specializing in Signals and Communications"
- Software/Python role → "with hands-on experience in Python development"
- Chip Design/Verification role → "specializing in digital systems and signal processing"
- AI/ML role → "with experience in Python and machine learning fundamentals"
- General/unclear → "specializing in Signals and Communications"

[ONE SENTENCE connecting background to role] — mention ONE relevant experience:
- If the role mentions signal processing → mention signal processing coursework
- If the role mentions Python → mention Python project experience
- If the role mentions digital design → mention Digital Systems coursework
- Do NOT list multiple things. Pick ONE that fits best.

[ONE ADDITIONAL SKILL] — must be DIFFERENT from what you just said. Examples:
- If sentence 1 mentions Python → sentence 2 can mention MATLAB or math background
- If sentence 1 mentions signal processing → sentence 2 can mention Python
- NEVER repeat the same skill or technology in both sentences
- Keep sentence 2 short: "I also have [something different]."

HARD RULES:
- Total body: 50-80 words. Not more.
- Do NOT add extra paragraphs
- Do NOT list grades (they are in the CV)
- Do NOT add flattery about the company
- Do NOT say "passionate", "genuinely", "solid", "excited", "caught my attention"
- Do NOT claim skills the candidate doesn\'t have (no Linux, no C++, no FPGA)
- Do NOT write "grade sheet attached" or "grades attached" — only CV is attached
- Do NOT say coursework "aligns directly with" or "maps directly to" a role
- Coursework gives FOUNDATION and BACKGROUND, not job-task expertise
- Use honest phrasing: "gave me a foundation relevant to..." or "covers fundamentals useful for..."
- Do NOT use jargon from the job description that the candidate hasn\'t actually studied
- Only mention specific technical terms (e.g. PHY-layer, beamforming) if they were part of the candidate\'s courses
- When unsure, use general terms: "signal processing" not "PHY-layer optimization"
- Do NOT change the template structure — only fill in the brackets
- If recruiter_name is provided, use "Dear [Name] from the [Company] team," instead
- NEVER use the word "strong" in any form ("strong background", "strong skills", "strong foundation", etc.)
- NEVER reference military service, army, combat, or hint at it with phrases like:
  "high-pressure environments", "leadership roles in demanding settings",
  "cross-functional collaboration developed through military", "proven ability under pressure"
  Military details are in the CV. The cover letter must not mention them at all.
- NEVER mention the job-hunter project, Claude API, job search automation, or any tool the candidate built for finding jobs — even if the CV contains it, ignore it completely
- NEVER use vague filler phrases. Every sentence must say something specific.
  BAD (ban these): "gave me a foundation in building functional, real-world applications",
  "developed skills through team-based projects", "cross-functional collaboration skills",
  "technical problem-solving capabilities"
  GOOD (specific): "I built a Python CLI tool that processes data from multiple APIs",
  "My coursework covered digital signal processing and communication systems",
  "I have practical experience with Python and MATLAB"

The letter should read like a short professional email, not a formal document.
'''

class CoverLetterGenerator:
    """Generates personalized cover letters using Claude AI."""

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
        profile = get_profile()
        personal_info = {
            "name":     profile.name,
            "email":    profile.email,
            "phone":    profile.phone,
            "linkedin": profile.linkedin,
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
                system=_build_system_prompt(),
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
- Body must be 50-80 words. Count them. Cut if over.
- Use this exact greeting: {greeting}
Follow the structure and rules in the system prompt exactly.
"""


def generate_cover_letter(job: JobListing, cv: dict, **kwargs) -> str:
    """Convenience function for one-shot generation."""
    return CoverLetterGenerator().generate(job, cv, **kwargs)
