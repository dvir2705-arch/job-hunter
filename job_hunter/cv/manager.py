import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from job_hunter.config import Config


class CVManager:
    BASE_CV_FILE = "base_cv.json"

    def __init__(self, cv_dir: Path = None):
        self.cv_dir = cv_dir or Config.CV_DIR
        self.cv_dir.mkdir(parents=True, exist_ok=True)

    def load_base(self) -> dict:
        path = self.cv_dir / self.BASE_CV_FILE
        if not path.exists():
            raise FileNotFoundError(f"Base CV not found at {path}. Run 'job-hunter cv init' first.")
        with open(path, "r") as f:
            return json.load(f)

    def save_base(self, data: dict) -> Path:
        path = self.cv_dir / self.BASE_CV_FILE
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path

    def save_version(self, data: dict, label: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cv_{label}_{timestamp}.json"
        path = self.cv_dir / filename
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path

    def list_versions(self) -> List[Path]:
        return sorted(self.cv_dir.glob("cv_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    def load_version(self, filename: str) -> dict:
        path = self.cv_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"CV version '{filename}' not found.")
        with open(path, "r") as f:
            return json.load(f)

    def init_base(self, data: Optional[dict] = None) -> Path:
        if data is None:
            data = self._default_cv()
        return self.save_base(data)

    @staticmethod
    def _default_cv() -> dict:
        return {
            "name": "Your Name",
            "title": "Software Engineer",
            "contact": {
                "email": "you@example.com",
                "phone": "+1 234 567 8900",
                "linkedin": "linkedin.com/in/yourprofile",
                "github": "github.com/yourhandle",
                "location": "City, Country",
            },
            "summary": "Experienced software engineer with a passion for building scalable systems.",
            "experience": [
                {
                    "company": "Acme Corp",
                    "position": "Senior Software Engineer",
                    "start": "2022-01",
                    "end": "Present",
                    "highlights": [
                        "Led migration of monolith to microservices, reducing latency by 40%.",
                        "Mentored 3 junior engineers.",
                    ],
                }
            ],
            "education": [
                {
                    "institution": "State University",
                    "degree": "B.Sc. Computer Science",
                    "year": "2018",
                }
            ],
            "skills": ["Python", "Docker", "Kubernetes", "PostgreSQL", "REST APIs"],
        }
