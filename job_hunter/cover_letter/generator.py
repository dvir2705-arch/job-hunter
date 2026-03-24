"""Cover Letter Generator using Claude AI."""

import anthropic
from typing import Optional

from job_hunter.config import Config
from job_hunter.jobs.scraper import JobListing
from .templates import LETTER_STRUCTURE, get_company_tone, TONE_INSTRUCTIONS
from .history import CoverLetterHistory


class CoverLetterGenerator:
    """Generates personalized cover letters using Claude AI."""

    SYSTEM_PROMPT = '''You are a professional cover letter writer.

Write cover letters that are:
- Professional but personable
- Specific to the job and company
- Highlighting relevant skills and experience
- Concise and impactful

CRITICAL TONE RULES for mentioning the job-hunter project:
- Use BALANCED tone - not arrogant, not self-deprecating
- Just state facts: "I built a job search automation tool in Python"
- Do NOT use: "advanced", "sophisticated", "cutting-edge", "powerful"
- Do NOT use: "small", "little", "simple", "basic"
- Let the facts speak: Python, APIs, 24 companies, AI integration

When mentioning job discovery through the tool, phrase it naturally:
- EN: "I discovered this position through a job search automation tool I built..."
- HE: "את המשרה מצאתי דרך כלי אוטומציה לחיפוש משרות שבניתי..."
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

        prompt = self._build_prompt(
            job=job,
            cv=cv,
            job_description=job_description,
            language=language,
            tone_instruction=tone_instruction,
            mention_project=should_mention,
            personal_info=personal_info,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

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
    ) -> str:
        """Build the prompt for cover letter generation."""
        import json

        lang_instruction = "Write in English." if language == "en" else "כתוב בעברית."

        project_instruction = ""
        if mention_project:
            project_instruction = (
                "\nINCLUDE THIS: Naturally mention that the candidate discovered this position "
                "through a job search automation tool they built in Python. Keep it to 1-2 sentences. "
                "Use balanced tone — just state the facts, no superlatives, no self-deprecation.\n"
            )

        template = LETTER_STRUCTURE.get(language, LETTER_STRUCTURE["en"])
        closing = template["closing"].format(company=job.company)

        return f"""Write a cover letter for this job application.

## Job Details:
- Title: {job.title}
- Company: {job.company}
- Location: {job.location}

## Job Description:
{job_description or "Not available - infer from job title and company"}

## Candidate CV (JSON):
{json.dumps(cv, indent=2, ensure_ascii=False)}

## Candidate Contact Info:
- Name: {personal_info['name']}
- Email: {personal_info['email']}
- Phone: {personal_info['phone']}
- LinkedIn: {personal_info['linkedin']}

## Instructions:
- {lang_instruction}
- Tone: {tone_instruction}
- Length: 3-4 paragraphs (not too long)
- End with: {closing}
- Include name and contact info in the signature
{project_instruction}
Write a compelling cover letter that connects the candidate's background to this role.
"""


def generate_cover_letter(job: JobListing, cv: dict, **kwargs) -> str:
    """Convenience function for one-shot generation."""
    return CoverLetterGenerator().generate(job, cv, **kwargs)
