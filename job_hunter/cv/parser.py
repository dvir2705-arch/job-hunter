"""Parse a CV file (docx/json/pdf) into structured JSON using Claude AI."""

import copy
import json
from pathlib import Path

import anthropic

from job_hunter.config import Config
from job_hunter.logger import get_logger

from .docx_parser import extract_all_text, parse_docx

logger = get_logger(__name__)

# Canonical field names expected by templates/cv/modern.html
_EXPERIENCE_ALIASES = {
    "title": "position",
    "job_title": "position",
    "role": "position",
    "start_date": "start",
    "end_date": "end",
    "description": "highlights",
}

_EDUCATION_ALIASES = {
    "school": "institution",
    "university": "institution",
    "start_date": "_start_date",
    "end_date": "_end_date",
}

_MILITARY_ALIASES = {
    "title": "role",
    "position": "role",
    "name": "unit",
    "company": "unit",
    "start_date": "_start_date",
    "end_date": "_end_date",
    "description": "highlights",
}

_VOLUNTEERING_ALIASES = {
    "company": "organization",
    "name": "organization",
    "title": "role",
    "position": "role",
    "start_date": "_start_date",
    "end_date": "_end_date",
}


def _rename_keys(entry: dict, aliases: dict) -> dict:
    """Rename keys in a dict according to an alias map. Skip if target already exists in original."""
    # Collect all target keys that already exist in the entry
    existing_targets = set(entry.keys())
    result = {}
    for key, value in entry.items():
        target = aliases.get(key, key)
        if target is None:
            continue
        # Don't rename if the canonical key already exists as a separate entry
        if key in aliases and target in existing_targets and target != key:
            continue  # skip the alias, the canonical key will be kept
        if target in result:
            continue
        result[target] = value
    return result


def _ensure_highlights(entry: dict) -> dict:
    """Convert a string 'highlights' to a single-item list."""
    if "highlights" in entry and isinstance(entry["highlights"], str):
        text = entry["highlights"].strip()
        if text:
            entry["highlights"] = [text]
        else:
            entry["highlights"] = []
    return entry


def _build_period(entry: dict) -> dict:
    """Build a 'period' field from _start_date/_end_date if period is missing."""
    if "period" not in entry:
        start = entry.pop("_start_date", "")
        end = entry.pop("_end_date", "")
        if start or end:
            entry["period"] = f"{start} – {end}".strip(" –")
    else:
        entry.pop("_start_date", None)
        entry.pop("_end_date", None)
    return entry


def _build_year(entry: dict) -> dict:
    """Build a 'year' field from _start_date/_end_date if year is missing."""
    if not entry.get("year"):
        start = entry.pop("_start_date", "")
        end = entry.pop("_end_date", "")
        if start and end:
            entry["year"] = f"{start} – {end}".strip(" –")
        elif start:
            entry["year"] = start
        elif end:
            entry["year"] = end
    else:
        entry.pop("_start_date", None)
        entry.pop("_end_date", None)
    return entry


def normalize_cv_schema(cv_data: dict) -> dict:
    """Normalize CV JSON to use canonical field names expected by the template.

    Idempotent — a CV already using canonical names passes through unchanged.
    """
    data = copy.deepcopy(cv_data)

    # --- Experience ---
    if "experience" in data and isinstance(data["experience"], list):
        normalized = []
        for entry in data["experience"]:
            entry = _rename_keys(entry, _EXPERIENCE_ALIASES)
            entry = _ensure_highlights(entry)
            normalized.append(entry)
        data["experience"] = normalized

    # --- Education ---
    if "education" in data and isinstance(data["education"], list):
        normalized = []
        for entry in data["education"]:
            entry = _rename_keys(entry, _EDUCATION_ALIASES)
            entry = _build_year(entry)
            normalized.append(entry)
        data["education"] = normalized

    # --- Military ---
    if "military" in data and isinstance(data["military"], list):
        normalized = []
        for entry in data["military"]:
            entry = _rename_keys(entry, _MILITARY_ALIASES)
            entry = _build_period(entry)
            entry = _ensure_highlights(entry)
            normalized.append(entry)
        data["military"] = normalized

    # --- Volunteering ---
    if "volunteering" in data and isinstance(data["volunteering"], list):
        normalized = []
        for entry in data["volunteering"]:
            entry = _rename_keys(entry, _VOLUNTEERING_ALIASES)
            entry = _build_period(entry)
            normalized.append(entry)
        data["volunteering"] = normalized

    return data


def parse_pdf_text(path: Path) -> str:
    """Extract all text from a PDF file using pdfplumber."""
    import pdfplumber

    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


def parse_cv_file(path: Path) -> dict:
    """Parse a CV file into structured JSON, preserving the user's sections.

    Supports: .docx (via python-docx + Claude), .pdf (via pdfplumber + Claude),
    .json (direct load).
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

    if suffix == ".pdf":
        raw_text = parse_pdf_text(path)
        if not raw_text.strip():
            raise ValueError(
                "Could not extract text from PDF. The file may be image-based — try a .docx instead."
            )
        return _structure_cv_with_claude(raw_text, [])

    raise ValueError(f"Unsupported CV file format: {suffix}. Use .docx, .pdf, or .json")


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
- Experience → array of objects: "position", "company", "start", "end", "highlights" (array of strings)
- Education → array of objects: "institution", "degree", "year", "gpa", "highlights" (array of strings)
- Projects → array of objects: "name", "technologies" (array), "highlights" (array), "url"
- Military → array of objects: "unit", "role", "period", "highlights" (array of strings)
- Volunteering → array of objects: "organization", "role", "period", "description"
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
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Claude response as JSON: %s", e)
        return None
    return normalize_cv_schema(parsed)
