import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from job_hunter.config import Config

SECTION_TITLES = {
    "en": {
        "summary": "Summary",
        "experience": "Experience",
        "projects": "Projects",
        "education": "Education",
        "skills": "Skills",
        "military": "Military Service",
        "volunteering": "Volunteering",
        "languages": "Languages",
    },
    "he": {
        "summary": "תקציר",
        "experience": "ניסיון תעסוקתי",
        "projects": "פרויקטים",
        "education": "השכלה",
        "skills": "כישורים",
        "military": "שירות צבאי",
        "volunteering": "התנדבות",
        "languages": "שפות",
    },
}


def _find_chrome() -> str:
    """Find Chrome/Chromium executable across Windows, macOS, and Linux."""
    system = platform.system()
    candidates: list[Path] = []

    if system == "Windows":
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        ]
    elif system == "Darwin":
        candidates = [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
    else:  # Linux
        candidates = [
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/google-chrome-stable"),
            Path("/usr/bin/chromium"),
            Path("/usr/bin/chromium-browser"),
            Path("/snap/bin/chromium"),
        ]

    for p in candidates:
        if p.exists():
            return str(p)

    # Fallback: check PATH
    for name in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]:
        path = shutil.which(name)
        if path:
            return path

    raise RuntimeError("Chrome/Chromium not found. Install Google Chrome to generate PDFs.")


class CVRenderer:
    def __init__(self, templates_dir: Path = None):
        self.templates_dir = templates_dir or Config.TEMPLATES_DIR
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=True,
        )

    def render_html(self, cv_data: dict, template_name: str = "cv/modern.html",
                    lang: str = "en") -> str:
        template = self.env.get_template(template_name)
        titles = SECTION_TITLES.get(lang, SECTION_TITLES["en"])
        return template.render(**cv_data, lang=lang, titles=titles)

    def render_pdf(self, cv_data: dict, output_path: Path, template_name: str = "cv/modern.html",
                   lang: str = "en") -> Path:
        """Render CV to PDF using Chrome headless."""
        html_content = self.render_html(cv_data, template_name, lang=lang)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_html = f.name

        try:
            subprocess.run([
                _find_chrome(),
                '--headless=new',
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

    def render_cover_letter_pdf(self, letter_text: str, output_path: Path,
                                sender_name: str, sender_email: str,
                                sender_phone: str = "", sender_linkedin: str = "",
                                company: str = "", recruiter_name: str = None,
                                lang: str = "en") -> Path:
        """Render a cover letter to PDF using Chrome headless."""
        from datetime import date

        paragraphs = [p.strip() for p in letter_text.strip().split("\n\n") if p.strip()]

        template = self.env.get_template("cover_letter/cover_letter.html")
        html_content = template.render(
            sender_name=sender_name,
            sender_email=sender_email,
            sender_phone=sender_phone,
            sender_linkedin=sender_linkedin,
            company=company,
            recruiter_name=recruiter_name,
            paragraphs=paragraphs,
            date=date.today().strftime("%B %d, %Y") if lang != "he" else date.today().strftime("%d/%m/%Y"),
            lang=lang,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_html = f.name

        try:
            subprocess.run([
                _find_chrome(),
                '--headless=new',
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

    def render_html_file(self, cv_data: dict, output_path: Path, template_name: str = "cv/modern.html",
                         lang: str = "en") -> Path:
        html_content = self.render_html(cv_data, template_name, lang=lang)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding="utf-8")
        return output_path
