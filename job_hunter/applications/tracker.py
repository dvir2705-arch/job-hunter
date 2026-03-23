import json
import uuid
from collections import Counter
from pathlib import Path
from typing import List, Optional

from job_hunter.applications.models import Application, ApplicationStatus
from job_hunter.config import Config


class ApplicationTracker:
    def __init__(self, filepath: Path = None):
        self.filepath = filepath or Config.APPLICATIONS_FILE
        self._applications: List[Application] = []
        self._load()

    def _load(self) -> None:
        if self.filepath.exists():
            with open(self.filepath, "r") as f:
                data = json.load(f)
            self._applications = [Application.from_dict(d) for d in data]
        else:
            self._applications = []

    def _save(self) -> None:
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, "w") as f:
            json.dump([a.to_dict() for a in self._applications], f, indent=2)

    def add(self, company: str, position: str, url: str, **kwargs) -> Application:
        app = Application(
            id=str(uuid.uuid4())[:8],
            company=company,
            position=position,
            url=url,
            **kwargs,
        )
        self._applications.append(app)
        self._save()
        return app

    def get(self, app_id: str) -> Optional[Application]:
        return next((a for a in self._applications if a.id == app_id), None)

    def update_status(self, app_id: str, status: ApplicationStatus, notes: str = "") -> Application:
        app = self.get(app_id)
        if not app:
            raise ValueError(f"Application {app_id} not found.")
        app.status = status
        if notes:
            app.notes = notes
        self._save()
        return app

    def list(self, status: Optional[ApplicationStatus] = None) -> List[Application]:
        if status:
            return [a for a in self._applications if a.status == status]
        return list(self._applications)

    def stats(self) -> dict:
        counts = Counter(a.status.value for a in self._applications)
        return {
            "total": len(self._applications),
            "by_status": dict(counts),
        }

    def delete(self, app_id: str) -> None:
        app = self.get(app_id)
        if not app:
            raise ValueError(f"Application {app_id} not found.")
        self._applications.remove(app)
        self._save()
