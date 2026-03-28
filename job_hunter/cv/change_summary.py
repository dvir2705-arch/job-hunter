"""Generate a visual HTML diff between base CV and an adapted CV."""

import html
import re
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
    """Compare base and adapted CVs and write a visual HTML diff.

    Returns the path to the written .html file.
    """
    if output_path is None:
        from job_hunter.config import Config
        slug = re.sub(r"[^\w]+", "_", f"{company}_{job_title}").lower()[:40]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Config.OUTPUT_DIR / f"cv_diff_{slug}_{ts}.html"

    sections = _compare_sections(base_cv, adapted_cv, job_title, company)
    html_content = _build_html(job_title, company, sections)
    output_path.write_text(html_content, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def _compare_sections(base_cv: dict, adapted_cv: dict, job_title: str, company: str) -> list:
    sections = []

    # Title
    base_title = base_cv.get("title", "")
    adapted_title = adapted_cv.get("title", "")
    sections.append({
        "name": "Title",
        "base_html": _e(base_title),
        "adapted_html": _e(adapted_title),
        "changed": base_title != adapted_title,
    })

    # Summary
    base_summary = base_cv.get("summary", "").strip()
    adapted_summary = adapted_cv.get("summary", "").strip()
    sections.append({
        "name": "Summary",
        "base_html": _e(base_summary),
        "adapted_html": _e(adapted_summary),
        "changed": base_summary != adapted_summary,
    })

    # Skills
    base_skills = _flatten_skills(base_cv.get("skills", {}))
    adapted_skills = _flatten_skills(adapted_cv.get("skills", {}))
    added = [s for s in adapted_skills if s not in base_skills]
    removed = [s for s in base_skills if s not in adapted_skills]
    reordered = base_skills != adapted_skills and not added and not removed
    skills_changed = bool(added or removed or reordered)

    sections.append({
        "name": "Skills",
        "base_html": _render_skills_html(base_skills, highlight=[]),
        "adapted_html": _render_skills_html(adapted_skills, highlight=added, strikethrough=removed),
        "changed": skills_changed,
        "skills_meta": {"added": added, "removed": removed, "reordered": reordered},
    })

    # Projects
    base_projects = {p["name"]: p for p in base_cv.get("projects", [])}
    adapted_projects = {p["name"]: p for p in adapted_cv.get("projects", [])}
    projects_changed = base_cv.get("projects") != adapted_cv.get("projects")

    base_proj_html = _render_projects_html(base_projects, adapted_projects, side="base")
    adapted_proj_html = _render_projects_html(base_projects, adapted_projects, side="adapted")
    sections.append({
        "name": "Projects",
        "base_html": base_proj_html,
        "adapted_html": adapted_proj_html,
        "changed": projects_changed,
    })

    # Interview prep tips
    tips = _generate_tips(base_cv, adapted_cv, job_title, company)
    tips_html = "<ul>" + "".join(f"<li>{_e(t)}</li>" for t in tips) + "</ul>"
    sections.append({
        "name": "Interview Prep Tips",
        "base_html": "<span class='muted'>N/A</span>",
        "adapted_html": tips_html,
        "changed": True,
        "full_width_right": True,
    })

    return sections


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def _e(text: str) -> str:
    """HTML-escape a string."""
    return html.escape(str(text))


def _render_skills_html(skills: list, highlight: list, strikethrough: list = None) -> str:
    strikethrough = strikethrough or []
    tags = []
    for s in skills:
        escaped = _e(s)
        if s in highlight:
            tags.append(f'<span class="skill-tag highlight">{escaped}</span>')
        elif s in strikethrough:
            tags.append(f'<span class="skill-tag removed">{escaped}</span>')
        else:
            tags.append(f'<span class="skill-tag">{escaped}</span>')
    return '<div class="skill-list">' + "".join(tags) + "</div>" if tags else "<em>None</em>"


def _render_projects_html(base_projects: dict, adapted_projects: dict, side: str) -> str:
    parts = []
    all_names = list(adapted_projects.keys()) + [n for n in base_projects if n not in adapted_projects]

    for name in all_names:
        base_proj = base_projects.get(name)
        adapted_proj = adapted_projects.get(name)

        if side == "base":
            proj = base_proj
            is_new = proj is None
            is_removed = adapted_proj is None
        else:
            proj = adapted_proj
            is_new = base_proj is None
            is_removed = proj is None

        if proj is None:
            label = "(removed)" if side == "base" else "(new)"
            parts.append(f'<div class="project"><strong class="muted">{_e(name)} {label}</strong></div>')
            continue

        desc = proj.get("description", "")
        highlights = proj.get("highlights", [])

        # Determine if this project changed
        changed = (base_proj != adapted_proj) if (base_proj and adapted_proj) else False
        new_badge = ' <span class="badge-new">new</span>' if (side == "adapted" and base_proj is None) else ""

        desc_html = _e(desc)
        if side == "adapted" and changed and base_proj and desc != base_proj.get("description", ""):
            desc_html = f'<span class="highlight">{_e(desc)}</span>'

        hl_items = []
        base_hl = base_proj.get("highlights", []) if base_proj else []
        for h in highlights:
            escaped = _e(h)
            if side == "adapted" and changed and h not in base_hl:
                hl_items.append(f'<li><span class="highlight">{escaped}</span></li>')
            else:
                hl_items.append(f'<li>{escaped}</li>')

        hl_html = f'<ul>{"".join(hl_items)}</ul>' if hl_items else ""
        parts.append(
            f'<div class="project">'
            f'<strong>{_e(name)}{new_badge}</strong>'
            f'<p>{desc_html}</p>'
            f'{hl_html}'
            f'</div>'
        )

    return "".join(parts) if parts else "<em>No projects</em>"


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

def _build_html(job_title: str, company: str, sections: list) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    original_cols = []
    adapted_cols = []

    for sec in sections:
        name_escaped = _e(sec["name"])
        changed = sec.get("changed", False)
        full_right = sec.get("full_width_right", False)

        # Original column
        if full_right:
            original_cols.append(
                f'<div class="section"><div class="section-title">{name_escaped}</div>'
                f'<div class="content muted">—</div></div>'
            )
        else:
            original_cols.append(
                f'<div class="section"><div class="section-title">{name_escaped}</div>'
                f'<div class="content">{sec["base_html"]}</div></div>'
            )

        # Adapted column
        adapted_cols.append(
            f'<div class="section"><div class="section-title">{name_escaped}</div>'
            f'<div class="content">{sec["adapted_html"]}</div></div>'
        )

    original_html = "\n".join(original_cols)
    adapted_html = "\n".join(adapted_cols)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CV Diff — {_e(job_title)} at {_e(company)}</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 24px; background: #f5f5f5; color: #333; }}
  h1 {{ text-align: center; color: #1a1a2e; margin-bottom: 4px; }}
  .subtitle {{ text-align: center; color: #666; margin-bottom: 6px; font-size: 15px; }}
  .meta {{ text-align: center; color: #aaa; font-size: 12px; margin-bottom: 20px; }}
  .legend {{ text-align: center; margin-bottom: 24px; font-size: 13px; color: #666; }}
  .legend .swatch {{ background: #fff3cd; padding: 2px 10px; border-radius: 3px; border: 1px solid #ffc107; }}
  .diff-container {{ display: flex; gap: 20px; max-width: 1400px; margin: 0 auto; }}
  .column {{ flex: 1; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }}
  .column-header {{ font-size: 16px; font-weight: bold; padding: 8px 12px; border-radius: 4px; margin-bottom: 16px; text-align: center; }}
  .original .column-header {{ background: #e8e8e8; color: #555; }}
  .adapted .column-header {{ background: #d4edda; color: #155724; }}
  .section {{ margin-bottom: 22px; border-bottom: 1px solid #f0f0f0; padding-bottom: 16px; }}
  .section:last-child {{ border-bottom: none; }}
  .section-title {{ font-weight: bold; font-size: 12px; text-transform: uppercase; letter-spacing: 0.8px; color: #888; margin-bottom: 8px; }}
  .content {{ font-size: 13.5px; line-height: 1.65; }}
  .highlight {{ background: #fff3cd; padding: 1px 3px; border-radius: 3px; border: 1px solid #ffc107; }}
  .muted {{ color: #aaa; font-style: italic; }}
  .skill-list {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .skill-tag {{ background: #f0f0f5; border-radius: 4px; padding: 2px 9px; font-size: 12px; }}
  .skill-tag.highlight {{ background: #fff3cd; border: 1px solid #ffc107; }}
  .skill-tag.removed {{ background: #fde8e8; text-decoration: line-through; color: #aaa; }}
  .project {{ margin-bottom: 14px; }}
  .project strong {{ font-size: 13.5px; }}
  .project p {{ margin: 4px 0 6px; color: #555; font-size: 13px; }}
  .project ul {{ padding-left: 18px; margin: 0; }}
  .project ul li {{ margin-bottom: 3px; font-size: 13px; color: #444; }}
  .badge-new {{ background: #d4edda; color: #155724; font-size: 10px; padding: 1px 6px; border-radius: 10px; font-weight: normal; vertical-align: middle; }}
</style>
</head>
<body>
<h1>CV Adaptation Diff</h1>
<div class="subtitle">{_e(job_title)} at {_e(company)}</div>
<div class="meta">Generated {generated}</div>
<div class="legend"><span class="swatch">Yellow highlight</span> = changed from original</div>
<div class="diff-container">
  <div class="column original">
    <div class="column-header">Original CV</div>
    {original_html}
  </div>
  <div class="column adapted">
    <div class="column-header">Adapted CV ✓</div>
    {adapted_html}
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Helpers (unchanged logic)
# ---------------------------------------------------------------------------

def _flatten_skills(skills_section) -> list:
    """Return a flat list of skill strings regardless of CV schema shape."""
    if not skills_section:
        return []
    if isinstance(skills_section, dict):
        flat = []
        for items in skills_section.values():
            if isinstance(items, list):
                flat.extend(items)
        return flat
    if isinstance(skills_section[0], dict):
        flat = []
        for group in skills_section:
            flat.extend(group.get("items", []))
        return flat
    return list(skills_section)


def _generate_tips(base_cv: dict, adapted_cv: dict, job_title: str, company: str) -> list:
    """Return a short list of interview prep tips based on the diff."""
    from job_hunter.profile import get_profile

    tips = []
    job_lower = job_title.lower()
    adapted_summary = adapted_cv.get("summary", "").lower()

    try:
        p = get_profile()
        # Generate tips from profile: if a target position keyword appears in the job,
        # suggest reviewing related skills
        for target in p.target_positions:
            if target.lower() in job_lower or target.lower() in adapted_summary:
                matching_skills = [s for s in p.skills if s.lower() != target.lower()]
                if matching_skills:
                    tips.append(
                        f"Review your {target} knowledge — be ready to discuss "
                        f"your experience with {matching_skills[0]}."
                    )
    except (FileNotFoundError, ValueError):
        pass

    tips.append(f"Research {company}'s recent products and tech stack before the interview.")
    tips.append("Prepare 1-2 examples of projects or coursework you can walk through end-to-end.")
    tips.append("Have a concise answer ready for 'Why this role?' tied to your background.")

    return tips[:6]
