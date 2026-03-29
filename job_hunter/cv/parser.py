"""Parse a CV file (docx/json) into structured JSON using Claude AI."""

import json
from pathlib import Path

import anthropic

from job_hunter.config import Config
from job_hunter.logger import get_logger
from .docx_parser import parse_docx, extract_all_text

logger = get_logger(__name__)


def parse_cv_file(path: Path) -> dict:
    """Parse a CV file into structured JSON, preserving the user's sections.

    Supports: .docx (via python-docx + Claude), .json (direct load).
    Returns a dict suitable for saving as base_cv.json.
    """
    suffix = path.suffix.lower()

    if suffix == ".json":
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    if suffix == ".docx":
        doc, section_map = parse_docx(path)
        section_texts = extract_all_text(doc, section_map)
        section_names = [s.name for s in section_map.sections]
        raw_text = "\n\n".join(
            f"[{name}]\n{text}" for name, text in section_texts.items()
        )
        return _structure_cv_with_claude(raw_text, section_names)

    raise ValueError(f"Unsupported CV file format: {suffix}. Use .docx or .json")


def _structure_cv_with_claude(raw_text: str, detected_sections: list[str]) -> dict:
    """Send CV text to Claude and get back structured JSON."""
    Config.validate()
    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    sections_list = ", ".join(detected_sections) if detected_sections else "auto-detect"

    prompt = f"""Extract this CV into structured JSON.

DETECTED SECTIONS: {sections_list}

MANDATORY top-level fields (always include, use empty string if not found):
- "name": string
- "title": string (the person's professional title or student status)
- "contact": {{"email": "", "phone": "", "linkedin": "", "github": "", "location": ""}}
- "summary": string (or empty)

FOR EACH DETECTED SECTION, create a snake_case key. Rules:
- Experience/education/projects/military/volunteering → array of objects with relevant fields
- Skills → object with subcategories as keys, each mapping to a list of strings
- Languages → array of strings
- Preserve ALL sections from the CV — do not drop, merge, or invent sections
- Use the section names as they appear (converted to snake_case)
- Do NOT add sections that don't exist in the CV

Return ONLY valid JSON. No commentary.

CV TEXT:
{raw_text}
"""

    try:
        response = client.messages.create(
            model=Config.CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as e:
        logger.error("Claude API error in CV structuring: %s", e)
        return None

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Claude response as JSON: %s", e)
        return None
