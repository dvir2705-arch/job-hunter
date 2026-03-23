from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from job_hunter.config import Config


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
        try:
            from weasyprint import HTML
        except ImportError:
            raise ImportError("weasyprint is required for PDF rendering. Install it with: pip install weasyprint")

        html_content = self.render_html(cv_data, template_name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        HTML(string=html_content, base_url=str(self.templates_dir)).write_pdf(str(output_path))
        return output_path

    def render_html_file(self, cv_data: dict, output_path: Path, template_name: str = "cv/modern.html") -> Path:
        html_content = self.render_html(cv_data, template_name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding="utf-8")
        return output_path
