"""Generate a human-readable markdown diff between base CV and an adapted CV."""

from datetime import datetime
from pathlib import Path
from typing import Optional


def generate_change_summary(
    base_cv: dict,
    adapted_cv: dict,
    job_title: str,
    company: str,
    output_path: Optional[Path] = None,
) -> Path:
    """Compare base and adapted CVs and write a markdown change summary.

    Returns the path to the written .md file.
    """
    if output_path is None:
        from job_hunter.config import Config
        import re
        slug = re.sub(r"[^\w]+", "_", f"{company}_{job_title}").lower()[:40]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Config.OUTPUT_DIR / f"cv_changes_{slug}_{ts}.md"

    lines = [
        f"# CV Change Summary",
        f"**Job:** {job_title} @ {company}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    # --- Title ---
    base_title = base_cv.get("title", "")
    adapted_title = adapted_cv.get("title", "")
    lines += ["## Title", ""]
    if base_title == adapted_title:
        lines += [f"Unchanged: `{base_title}`", ""]
    else:
        lines += [
            f"- **Before:** {base_title}",
            f"- **After:**  {adapted_title}",
            "",
        ]

    # --- Summary ---
    lines += ["## Summary", ""]
    base_summary = base_cv.get("summary", "").strip()
    adapted_summary = adapted_cv.get("summary", "").strip()
    if base_summary == adapted_summary:
        lines += ["Unchanged.", ""]
    else:
        lines += [
            "**Before:**",
            f"> {base_summary}",
            "",
            "**After:**",
            f"> {adapted_summary}",
            "",
        ]

    # --- Skills ---
    lines += ["## Skills", ""]
    base_skills = _flatten_skills(base_cv.get("skills", {}))
    adapted_skills = _flatten_skills(adapted_cv.get("skills", {}))

    added = [s for s in adapted_skills if s not in base_skills]
    removed = [s for s in base_skills if s not in adapted_skills]
    reordered = base_skills != adapted_skills and not added and not removed

    if not added and not removed and not reordered:
        lines += ["Unchanged.", ""]
    else:
        if added:
            lines += ["**Added / promoted:**"] + [f"- {s}" for s in added] + [""]
        if removed:
            lines += ["**Removed / demoted:**"] + [f"- {s}" for s in removed] + [""]
        if reordered:
            lines += ["**Reordered** (same skills, different emphasis).", ""]

    # --- Projects ---
    lines += ["## Projects", ""]
    base_projects = {p["name"]: p for p in base_cv.get("projects", [])}
    adapted_projects = {p["name"]: p for p in adapted_cv.get("projects", [])}

    for name, proj in adapted_projects.items():
        base_proj = base_projects.get(name)
        if base_proj is None:
            lines += [f"### {name} *(new)*", ""]
            continue

        # Compare highlights
        base_hl = base_proj.get("highlights", [])
        adapted_hl = proj.get("highlights", [])
        base_desc = base_proj.get("description", "")
        adapted_desc = proj.get("description", "")

        changed = base_hl != adapted_hl or base_desc != adapted_desc
        if not changed:
            lines += [f"### {name}", "No changes.", ""]
            continue

        lines += [f"### {name}", ""]
        if base_desc != adapted_desc:
            lines += [
                f"**Description changed:**",
                f"- Before: {base_desc}",
                f"- After:  {adapted_desc}",
                "",
            ]
        if base_hl != adapted_hl:
            added_hl = [h for h in adapted_hl if h not in base_hl]
            removed_hl = [h for h in base_hl if h not in adapted_hl]
            if added_hl:
                lines += ["**Highlights added:**"] + [f"- {h}" for h in added_hl] + [""]
            if removed_hl:
                lines += ["**Highlights removed:**"] + [f"- {h}" for h in removed_hl] + [""]
            if not added_hl and not removed_hl:
                lines += ["**Highlights reordered.**", ""]

    for name in base_projects:
        if name not in adapted_projects:
            lines += [f"### {name} *(removed)*", ""]

    # --- Interview prep tips ---
    lines += ["---", "## Interview Prep Tips", ""]
    tips = _generate_tips(base_cv, adapted_cv, job_title, company)
    lines += [f"- {t}" for t in tips]
    lines += [""]

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _flatten_skills(skills_section) -> list:
    """Return a flat list of skill strings regardless of CV schema shape."""
    if not skills_section:
        return []
    # Schema: dict of {category: [skill, ...]}  (actual base_cv.json format)
    if isinstance(skills_section, dict):
        flat = []
        for items in skills_section.values():
            if isinstance(items, list):
                flat.extend(items)
        return flat
    # List of {category, items} dicts
    if isinstance(skills_section[0], dict):
        flat = []
        for group in skills_section:
            flat.extend(group.get("items", []))
        return flat
    # Already a flat list of strings
    return list(skills_section)


def _generate_tips(base_cv: dict, adapted_cv: dict, job_title: str, company: str) -> list:
    """Return a short list of interview prep tips based on the diff."""
    tips = []
    job_lower = job_title.lower()
    adapted_summary = adapted_cv.get("summary", "").lower()

    # Tips based on job domain keywords
    keyword_tips = {
        "embedded": "Review embedded systems concepts: RTOS, memory-mapped I/O, interrupt handling.",
        "firmware": "Be ready to discuss bare-metal vs. RTOS trade-offs and debugging techniques.",
        "chip design": "Brush up on digital design flow: RTL → synthesis → P&R. Know your VHDL/Verilog basics.",
        "verification": "Review UVM/SystemVerilog fundamentals and constrained-random verification methodology.",
        "signal": "Refresh DSP: FFT, filtering, sampling theorem — likely to come up in a signals role.",
        "algorithm": "Practice coding interview problems: arrays, dynamic programming, graph traversal.",
        "software": "Prepare for system design questions; be ready to walk through your Python projects.",
        "ml": "Know the basics of your ML stack; be ready to explain model evaluation and trade-offs.",
        "python": "Walk through your job-hunter project in detail — it's your strongest Python example.",
    }
    for kw, tip in keyword_tips.items():
        if kw in job_lower or kw in adapted_summary:
            tips.append(tip)

    # Always include these
    tips += [
        f"Research {company}'s recent products and tech stack before the interview.",
        "Be ready to explain the job-hunter automation project end-to-end — it shows initiative.",
        "Prepare 1–2 examples from your military service that demonstrate pressure / teamwork.",
    ]

    return tips[:6]  # cap at 6 tips
