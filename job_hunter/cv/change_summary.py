"""Generate a side-by-side HTML comparison of the original and adapted CV."""

import html
import re
from datetime import datetime
from pathlib import Path

from job_hunter.cv.renderer import CVRenderer


def generate_change_summary(
    base_cv: dict,
    adapted_cv: dict,
    job_title: str,
    company: str,
    output_path: Path | None = None,
) -> Path:
    """Render both CVs side by side using the actual CV template.

    Returns the path to the written .html file.
    """
    if output_path is None:
        from job_hunter.config import Config

        slug = re.sub(r"[^\w]+", "_", f"{company}_{job_title}").lower()[:40]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Config.OUTPUT_DIR / f"cv_diff_{slug}_{ts}.html"

    renderer = CVRenderer()
    base_html = renderer.render_html(base_cv)
    adapted_html = renderer.render_html(adapted_cv)

    # Escape for embedding in srcdoc attribute
    base_srcdoc = html.escape(base_html)
    adapted_srcdoc = html.escape(adapted_html)

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    title_esc = html.escape(job_title)
    company_esc = html.escape(company)

    wrapper = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CV Comparison — {title_esc} at {company_esc}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Arial, sans-serif; background: #f5f5f5; color: #333; height: 100vh; display: flex; flex-direction: column; }}
  .header {{ text-align: center; padding: 16px 24px 12px; background: #fff; border-bottom: 1px solid #ddd; }}
  .header h1 {{ font-size: 18pt; color: #1a1a2e; margin-bottom: 4px; }}
  .header .subtitle {{ color: #666; font-size: 14px; }}
  .header .meta {{ color: #aaa; font-size: 11px; margin-top: 4px; }}
  .diff-container {{ display: flex; flex: 1; gap: 0; min-height: 0; }}
  .column {{ flex: 1; display: flex; flex-direction: column; min-width: 0; }}
  .column-header {{ font-size: 14px; font-weight: bold; padding: 8px 16px; text-align: center; flex-shrink: 0; }}
  .original .column-header {{ background: #e8e8e8; color: #555; }}
  .adapted .column-header {{ background: #d4edda; color: #155724; }}
  .divider {{ width: 2px; background: #ccc; flex-shrink: 0; }}
  iframe {{ flex: 1; border: none; width: 100%; }}
</style>
</head>
<body>
<div class="header">
  <h1>CV Comparison</h1>
  <div class="subtitle">{title_esc} at {company_esc}</div>
  <div class="meta">Generated {generated}</div>
</div>
<div class="diff-container">
  <div class="column original">
    <div class="column-header">Original CV</div>
    <iframe srcdoc="{base_srcdoc}"></iframe>
  </div>
  <div class="divider"></div>
  <div class="column adapted">
    <div class="column-header">Adapted CV</div>
    <iframe srcdoc="{adapted_srcdoc}"></iframe>
  </div>
</div>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(wrapper, encoding="utf-8")
    return output_path
