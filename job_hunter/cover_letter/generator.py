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

    # --- Adaptive opening line based on profile type -------------------------
    if p.is_student:
        opening = f"I'm a [YEAR]-year {p.cv_title} at {p.university}, [FOCUS AREA]."
    elif p.education:
        # Graduate — has education but no current year
        opening = f"I hold a {p.degree} from {p.university}, [FOCUS AREA]."
    elif p.work_experience:
        # Professional — no education, has work experience
        top_skills = ", ".join(p.skills[:3]) if p.skills else "various technologies"
        opening = f"I'm a {p.cv_title} with experience in {top_skills}, [FOCUS AREA]."
    else:
        opening = f"I'm a {p.cv_title}, [FOCUS AREA]."

    # --- Focus area instructions ---------------------------------------------
    spec = p.specialization or p.degree
    skills_csv = ", ".join(p.skills) if p.skills else "see CV"
    focus_rules = f"""[FOCUS AREA] — pick the best focus phrase for this job:
- The candidate\'s background: "{spec or skills_csv}"
- The candidate\'s skills are: {skills_csv}
- Choose the ONE skill or area most relevant to THIS job
- Format as: "specializing in [X]" or "with hands-on experience in [X]"
- If no clear match, default to: "specializing in {spec or skills_csv}"
"""

    # --- Banned words from hard_rules ----------------------------------------
    banned_words = p.hard_rules.get("banned_words", [])
    banned_words_rule = ""
    if banned_words:
        quoted = ", ".join(f'"{w}"' for w in banned_words)
        banned_words_rule = f"- Do NOT say {quoted}"

    # --- No-mention topics from hard_rules -----------------------------------
    no_mention = p.hard_rules.get("no_mention_in_cover_letter", [])
    no_mention_rule = ""
    if no_mention:
        topics = ", ".join(no_mention)
        no_mention_rule = f"""- NEVER reference {topics} or hint at them with phrases like:
  "high-pressure environments", "leadership roles in demanding settings",
  "proven ability under pressure"
  These details are in the CV. The cover letter must not mention them at all."""

    # --- Skills the candidate does NOT have ----------------------------------
    skills_not_rule = ""
    if p.skills_not:
        skills_not_rule = f'- Do NOT claim skills the candidate doesn\'t have ({", ".join(f"no {s}" for s in p.skills_not)})'

    return f'''You fill in a cover letter template. Follow the structure exactly.

TEMPLATE (follow this exactly):

---
Dear [Company] Hiring Team,

{opening} I'm reaching out about the [EXACT JOB TITLE] position [in LOCATION if known].

[ONE SENTENCE connecting your relevant background to what the role requires]. I also have [ONE OTHER RELEVANT SKILL OR EXPERIENCE].

My CV is attached. I'm available and happy to discuss further.

{p.signature_block()}
---

RULES FOR FILLING THE TEMPLATE:

{focus_rules}
[ONE SENTENCE connecting background to role] — mention ONE relevant experience:
- Match from the candidate\'s skills ({skills_csv}) to what the job needs
- Pick the SINGLE best match. Do NOT list multiple things.

[ONE ADDITIONAL SKILL] — must be DIFFERENT from what you just said:
- Pick from the candidate\'s remaining skills
- NEVER repeat the same skill or technology in both sentences
- Keep sentence 2 short: "I also have [something different]."

HARD RULES:
- Total body: 50-80 words. Not more.
- Do NOT add extra paragraphs
- Do NOT list grades (they are in the CV)
- Do NOT add flattery about the company
{banned_words_rule}
{skills_not_rule}
- Do NOT write "grade sheet attached" or "grades attached" — only CV is attached
- Do NOT say coursework "aligns directly with" or "maps directly to" a role
- Coursework gives FOUNDATION and BACKGROUND, not job-task expertise
- Use honest phrasing: "gave me a foundation relevant to..." or "covers fundamentals useful for..."
- Do NOT use jargon from the job description that the candidate hasn\'t actually studied
- Only mention specific technical terms if they were part of the candidate\'s actual experience
- When unsure, use general terms
- Do NOT change the template structure — only fill in the brackets
- If recruiter_name is provided, use "Dear [Name] from the [Company] team," instead
- NEVER use the word "strong" in any form ("strong background", "strong skills", "strong foundation", etc.)
{no_mention_rule}
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
        """Return academic year from profile (e.g. '3rd'), fallback to CV computation."""
        profile_year = get_profile().year
        if profile_year:
            return profile_year

        # Fallback: compute from CV education start year
        ordinals = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}
        try:
            edu = cv.get("education", [])
            if not edu:
                return ""
            year_field = edu[0].get("year", "")
            start_year = int(year_field.split("-")[0].strip())
            current_year = datetime.now().year
            if datetime.now().month < 10:
                current_year -= 1
            year_num = current_year - start_year + 1
            return ordinals.get(year_num, f"{year_num}th")
        except (ValueError, IndexError, AttributeError):
            return ""

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
- Academic year: **{academic_year + " year" if academic_year else "omit year from letter"}** (use this exactly — do not guess)

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
