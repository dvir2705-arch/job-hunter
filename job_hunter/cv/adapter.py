import json
from typing import TYPE_CHECKING

import anthropic

from job_hunter.config import Config
from job_hunter.logger import get_logger
from job_hunter.profile import get_profile

if TYPE_CHECKING:
    from job_hunter.jobs.analyzer import JobRequirements

logger = get_logger(__name__)


def detect_cv_language(cv_data: dict) -> str:
    """Detect base CV language by checking for Hebrew characters."""
    text = cv_data.get("summary", "") + cv_data.get("name", "")
    if not text:
        return "en"
    hebrew_chars = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
    return "he" if hebrew_chars > len(text) * 0.3 else "en"


def _build_language_rules(lang: str) -> str:
    """Build language instruction block for the system prompt."""
    if lang == "he":
        return """
LANGUAGE (CRITICAL):
- Write ALL CV content values in Hebrew (עברית).
- JSON keys MUST remain in English (snake_case) — only values should be in Hebrew.
- If the input CV is in English, translate content to professional Hebrew.
- Keep technology names (Python, Git, Docker, etc.) and proper nouns in their original language.
- Keep company names in their original language.
"""
    return """
LANGUAGE:
- Write all CV content in professional English.
- If the input CV is in Hebrew or another language, translate all content to English.
- Keep technology names and proper nouns as-is.
"""


def _build_system_prompt(lang: str = "en") -> str:
    """Build the CV adapter system prompt from user profile."""
    p = get_profile()

    # --- Title rules (always present) ----------------------------------------
    title_rules = ""
    if p.cv_title:
        uni_example = f'"{p.cv_title} | {p.university}"  (university is a fact)' if p.university else ""
        title_rules = f"""
TITLE RULES (CRITICAL — NEVER VIOLATE):
1. The title MUST stay exactly as "{p.cv_title}" — this is the only accurate title.
2. Do NOT append specializations: no "| Embedded Systems", "| Software Development", "| AI/ML", etc.
3. Do NOT add focus areas, aspirations, or job targets to the title field.
4. The title field is for ACTUAL STATUS only.
5. If you want to show a focus area, put it in the SUMMARY — never in the title.

ALLOWED:  "{p.cv_title}"
          {uni_example}
NOT ALLOWED: anything with a pipe + skill/domain/focus (e.g. "| Embedded Systems", "| Software Development", "| AI/ML Focus")
NOT ALLOWED: "Embedded Software Engineer", "Junior Engineer", or any employed role title.
"""

    # --- Must-include facts (from hard_rules) --------------------------------
    must_include = p.hard_rules.get("must_include", [])
    must_include_rules = ""
    if must_include:
        fact_lines = "\n".join(
            f'- The CV MUST say "{fact}". This is a fact — never remove or change it.'
            for fact in must_include
        )
        must_include_rules = f"""
MUST-INCLUDE FACTS (CRITICAL — NEVER VIOLATE):
{fact_lines}
"""

    # --- Education rules (only if education section exists) -------------------
    education_rules = ""
    if p.education:
        education_rules = """
EDUCATION RULES:
If the original CV contains education details, preserve them exactly. \
Do not alter degree names, years, or GPA values.
"""

    # --- Banned skills (from hard_rules) -------------------------------------
    banned_skills = p.hard_rules.get("banned_skills", [])
    banned_skills_rules = ""
    if banned_skills:
        skills_list = ", ".join(f'"{s}"' for s in banned_skills)
        banned_skills_rules = f"""
BANNED SKILLS (CRITICAL):
Never list these as skills in the summary or skills section — they are too generic: {skills_list}. \
If the job mentions them, emphasize relevant technical skills instead.
"""

    return f"""\
You are an expert CV writer and career coach. You will receive a candidate's CV in JSON format \
and a job description. Your task is to make subtle, proportional adjustments so the CV \
highlights relevant experience — while keeping the candidate's authentic profile front and center. \
The CV should still read as THIS person's CV, not as a mirror of the job description.

BALANCE (CRITICAL):
- The CV must remain ~80% the candidate's original content and voice. Only ~20% should shift to \
emphasize job-relevant aspects.
- Do NOT rewrite bullet points just to insert job-description keywords. Only adjust phrasing \
when the candidate genuinely has that experience.
- Do NOT reshape the summary into a copy of the job requirements. Keep the candidate's identity \
and background as the foundation, with a subtle nod toward the role.
- Keyword stuffing is forbidden — if a skill or keyword doesn't reflect real experience, leave it out.

You may:
- Reorder skills to put job-relevant ones first (if the candidate has them)
- Slightly adjust phrasing of bullet points to surface relevant aspects of real experience
- Adjust the summary emphasis toward the role's domain — but keep the candidate's story
- Remove less relevant experience details to fit one page
{title_rules}{must_include_rules}{education_rules}\
PAGE LENGTH (CRITICAL):
The adapted CV MUST fit on exactly one page. Never add new content or skills. \
Only reorder and rephrase existing items. Remove less relevant items if needed to fit one page.
{banned_skills_rules}\
Keep language confident but modest. Avoid superlatives like "exceptional", "outstanding", \
"remarkable", "unparalleled". Let concrete facts (grades, projects, technologies) speak for \
themselves. The CV should be professional and factual, not boastful or salesy.
{_build_language_rules(lang)}\
Return ONLY valid JSON in the exact same schema as the input CV. Do not add commentary outside the JSON.
"""


class CVAdapter:
    def __init__(self, model: str = None):
        Config.validate()
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = model or Config.CLAUDE_MODEL

    def adapt(self, cv_data: dict, job_description: str, job_title: str = "",
              lang: str = "en") -> dict:
        user_message = (
            f"Job Title: {job_title}\n\n"
            f"Job Description:\n{job_description}\n\n"
            f"Candidate CV (JSON):\n{json.dumps(cv_data, indent=2, ensure_ascii=False)}"
        )

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=_build_system_prompt(lang=lang),
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APIError as e:
            logger.error("Claude API error in CVAdapter.adapt: %s", e)
            return None

        if not message.content:
            logger.error("Claude returned empty content in CVAdapter.adapt")
            return None

        raw = message.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        try:
            adapted = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Claude response as JSON in adapt: %s", e)
            return None
        return adapted

    def adapt_with_requirements(self, cv_data: dict, requirements: "JobRequirements",
                                lang: str = "en") -> dict:
        """Adapt CV using structured job requirements instead of raw description."""
        p = get_profile()

        # Build dynamic rules from hard_rules
        title_rule = f'4. TITLE: Keep exactly as "{p.cv_title}" — never change this.' if p.cv_title else ""

        banned = p.hard_rules.get("banned_skills", [])
        banned_rule = ""
        if banned:
            banned_list = ", ".join(f'"{s}"' for s in banned)
            banned_rule = f"7. BANNED SKILLS: Never list these as skills — they are too generic: {banned_list}. Emphasize relevant technical skills instead."

        must_include = p.hard_rules.get("must_include", [])
        must_include_rule = ""
        if must_include:
            facts = "; ".join(f'"{f}"' for f in must_include)
            must_include_rule = f"8. MUST-INCLUDE FACTS: The CV MUST preserve these exactly: {facts}. Never remove or change them."

        prompt = f"""Make subtle, proportional adjustments to this CV for the following role. \
The CV should still read as THIS candidate's authentic profile — not a mirror of the job posting.

ROLE: {requirements.title} at {requirements.company}
DOMAIN: {requirements.domain}
WHAT THE PERSON WILL DO: {requirements.role_summary}

REQUIRED SKILLS: {', '.join(requirements.required_skills)}
PREFERRED SKILLS: {', '.join(requirements.preferred_skills)}
KEY TECHNOLOGIES: {', '.join(requirements.key_technologies)}
EDUCATION REQUIRED: {requirements.education}

ADAPTATION RULES:
0. BALANCE: Keep ~80% of the CV as-is. Only ~20% should shift emphasis. Do NOT rewrite the CV around the job description. No keyword stuffing — if a skill isn't real, leave it out.
1. SKILLS ORDERING: If the candidate HAS a required skill, move it to the top of the skills section. Do NOT add skills the candidate doesn't have.
2. SUMMARY: Keep the candidate's identity and story as the foundation. Add a subtle nod toward {requirements.domain} — but don't turn the summary into a job-description echo.
3. PROJECTS: Keep project descriptions authentic. You may slightly emphasize aspects relevant to {requirements.domain}, but don't rewrite what the project does.
{title_rule}
5. HONESTY: Do not add, invent, or exaggerate anything. Only reorder and re-emphasize existing content.
6. ONE PAGE: The adapted CV MUST fit on exactly one page. Never add new content or skills. Only reorder and rephrase existing items. Remove less relevant items if needed to fit one page.
{banned_rule}
{must_include_rule}

CV DATA:
{json.dumps(cv_data, indent=2, ensure_ascii=False)}

Return ONLY valid JSON in the exact same schema as the input CV."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=_build_system_prompt(lang=lang),
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as e:
            logger.error("Claude API error in CVAdapter.adapt_with_requirements: %s", e)
            return None

        if not message.content:
            logger.error("Claude returned empty content in CVAdapter.adapt_with_requirements")
            return None

        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Claude response as JSON in adapt_with_requirements: %s", e)
            return None

    def generate_cover_letter(self, cv_data: dict, job_description: str, company: str, job_title: str = "") -> str:
        user_message = (
            f"Company: {company}\n"
            f"Job Title: {job_title}\n\n"
            f"Job Description:\n{job_description}\n\n"
            f"Candidate CV (JSON):\n{json.dumps(cv_data, indent=2)}\n\n"
            "Write a concise, professional cover letter (3-4 paragraphs) for this candidate."
        )

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APIError as e:
            logger.error("Claude API error in CVAdapter.generate_cover_letter: %s", e)
            return None

        if not message.content:
            logger.error("Claude returned empty content in CVAdapter.generate_cover_letter")
            return None

        return message.content[0].text.strip()
