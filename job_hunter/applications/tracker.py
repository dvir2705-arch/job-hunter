import json
from pathlib import Path
from typing import Dict, List, Optional

from job_hunter.applications.models import Application, VALID_TRANSITIONS
from job_hunter.config import Config
from job_hunter.logger import get_logger

logger = get_logger(__name__)


class ApplicationTracker:
    def __init__(self, filepath: Path = None):
        self.filepath = filepath or Config.APPLICATIONS_FILE
        self.applications: List[Application] = []
        self._load()

    def _load(self) -> None:
        if not self.filepath.exists():
            self.applications = []
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Corrupted applications file %s: %s", self.filepath, e)
            self.applications = []
            return
        except PermissionError as e:
            logger.error("Cannot read applications file %s: %s", self.filepath, e)
            self.applications = []
            return

        # Support both old list format and new {"applications": [...]} format
        records = data.get("applications", data) if isinstance(data, dict) else data

        self.applications = []
        for record in records:
            try:
                self.applications.append(self._migrate(record))
            except Exception:
                pass  # Skip malformed records

    def _migrate(self, record: dict) -> Application:
        """Migrate old-format records to new Application model."""
        # Map old field names to new ones
        migrated = dict(record)
        if "position" in migrated and "job_title" not in migrated:
            migrated["job_title"] = migrated.pop("position")
        if "url" in migrated and "job_url" not in migrated:
            migrated["job_url"] = migrated.pop("url")
        if "cv_version" in migrated:
            migrated.setdefault("cv_file", migrated.pop("cv_version") or "")
        # Strip old fields not in the new model
        for old_key in ("salary_range", "contact"):
            migrated.pop(old_key, None)
        # Flatten status enum string if needed
        if isinstance(migrated.get("status"), dict):
            migrated["status"] = migrated["status"].get("value", "applied")
        return Application.from_dict(migrated)

    def _save(self) -> None:
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"applications": [a.to_dict() for a in self.applications]}, f, indent=2)
        except PermissionError as e:
            logger.error("Cannot write applications file %s: %s", self.filepath, e)

    # --- CRUD ---

    def add(self, app: Application) -> Application:
        self.applications.append(app)
        self._save()
        return app

    def get_by_id(self, partial_id: str) -> Optional[Application]:
        """Find application by full or partial ID."""
        for app in self.applications:
            if app.id.startswith(partial_id):
                return app
        return None

    def reset_status(self, app_id: str, note: str = "") -> Optional[Application]:
        """Reset application status to 'applied'. For corrections only."""
        app = self.get_by_id(app_id)
        if not app:
            return None
        app.reset_status(note)
        self._save()
        return app

    def update_status(self, app_id: str, new_status: str, note: str = "") -> Optional[Application]:
        """Update status with transition validation."""
        app = self.get_by_id(app_id)
        if not app:
            return None

        allowed = VALID_TRANSITIONS.get(app.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {app.status} → {new_status}. "
                f"Allowed: {allowed or 'none'}"
            )

        app.update_status(new_status, note)
        self._save()
        return app

    # --- Queries ---

    def get_all(self) -> List[Application]:
        return list(self.applications)

    def get_by_status(self, status: str) -> List[Application]:
        return [a for a in self.applications if a.status == status]

    def get_by_company(self, company: str) -> List[Application]:
        return [a for a in self.applications if a.company.lower() == company.lower()]

    def get_needing_follow_up(self) -> List[Application]:
        return [a for a in self.applications if a.needs_follow_up()]

    # --- Stats ---

    def get_stats(self) -> Dict:
        apps = self.applications
        total = len(apps)

        by_status: Dict[str, int] = {}
        by_company: Dict[str, int] = {}
        for a in apps:
            by_status[a.status] = by_status.get(a.status, 0) + 1
            by_company[a.company] = by_company.get(a.company, 0) + 1

        responded = sum(
            1 for a in apps if a.status in ("screening", "interview", "offer", "rejected")
        )
        response_rate = round(responded / total * 100, 1) if total else 0.0

        return {
            "total": total,
            "by_status": by_status,
            "by_company": by_company,
            "response_rate": response_rate,
            "needs_follow_up": len(self.get_needing_follow_up()),
        }
