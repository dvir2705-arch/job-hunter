import json

import anthropic

from job_hunter.config import Config


SYSTEM_PROMPT = """\
You are an expert CV writer and career coach. You will receive a candidate's CV in JSON format \
and a job description. Your task is to adapt the CV to best match the job requirements while \
keeping all information truthful. You may:
- Reorder or emphasize relevant skills
- Rewrite bullet points to use keywords from the job description
- Adjust the summary to align with the role
- Remove less relevant experience details

TITLE RULES (CRITICAL — NEVER VIOLATE):
1. The title MUST stay exactly as "Electrical Engineering Student" — this is the only accurate title.
2. Do NOT append specializations: no "| Embedded Systems", "| Software Development", "| AI/ML", etc.
3. Do NOT add focus areas, aspirations, or job targets to the title field.
4. The title field is for ACTUAL STATUS only.
5. If you want to show a focus area, put it in the SUMMARY — never in the title.

ALLOWED:  "Electrical Engineering Student"
          "Electrical Engineering Student | BGU"  (university is a fact)
NOT ALLOWED: anything with a pipe + skill/domain/focus (e.g. "| Embedded Systems", "| Software Development", "| AI/ML Focus")
NOT ALLOWED: "Embedded Software Engineer", "Junior Engineer", or any employed role title.

Keep language confident but modest. Avoid superlatives like "exceptional", "outstanding", \
"remarkable", "unparalleled". Instead of "exceptional mathematical abilities", write \
"strong mathematical background" or let the grades speak for themselves. The CV should be \
professional and confident, not boastful.

Return ONLY valid JSON in the exact same schema as the input CV. Do not add commentary outside the JSON.
"""


class CVAdapter:
    def __init__(self, model: str = None):
        Config.validate()
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = model or Config.CLAUDE_MODEL

    def adapt(self, cv_data: dict, job_description: str, job_title: str = "") -> dict:
        user_message = (
            f"Job Title: {job_title}\n\n"
            f"Job Description:\n{job_description}\n\n"
            f"Candidate CV (JSON):\n{json.dumps(cv_data, indent=2)}"
        )

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = message.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        adapted = json.loads(raw)
        return adapted

    def generate_cover_letter(self, cv_data: dict, job_description: str, company: str, job_title: str = "") -> str:
        user_message = (
            f"Company: {company}\n"
            f"Job Title: {job_title}\n\n"
            f"Job Description:\n{job_description}\n\n"
            f"Candidate CV (JSON):\n{json.dumps(cv_data, indent=2)}\n\n"
            "Write a concise, professional cover letter (3-4 paragraphs) for this candidate."
        )

        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": user_message}],
        )

        return message.content[0].text.strip()
