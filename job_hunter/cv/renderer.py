import os
import subprocess
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from job_hunter.config import Config

_CHROME_PATHS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
]


def _find_chrome() -> str:
    for p in _CHROME_PATHS:
        if p.exists():
            return str(p)
    raise RuntimeError("Chrome not found. Install Google Chrome to generate PDFs.")


class CVRenderer:
    def __init__(self, templates_dir: Path = None):
        self.templates_dir = templates_dir or Config.TEMPLATES_DIR
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=True,
        )

    def render_html(self, cv_data: dict, template_name: str = "cv/modern.html") -> str:
        template = self.env.get_template(template_name)
        return template.render(**cv_data)

    def render_pdf(self, cv_data: dict, output_path: Path, template_name: str = "cv/modern.html") -> Path:
        """Render CV to PDF using Chrome headless."""
        html_content = self.render_html(cv_data, template_name)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_html = f.name

        try:
            subprocess.run([
                _find_chrome(),
                '--headless',
                '--disable-gpu',
                '--no-sandbox',
                '--print-to-pdf-no-header',
                '--no-pdf-header-footer',
                f'--print-to-pdf={output_path.absolute()}',
                temp_html,
            ], check=True, capture_output=True)
        finally:
            os.unlink(temp_html)

        return output_path

    def render_html_file(self, cv_data: dict, output_path: Path, template_name: str = "cv/modern.html") -> Path:
        html_content = self.render_html(cv_data, template_name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding="utf-8")
        return output_path
