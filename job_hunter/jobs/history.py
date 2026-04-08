"""Track job history to identify new listings."""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Tuple

from .scraper import JobListing

from job_hunter.config import Config


class JobHistory:
    """Persists seen jobs so new ones can be flagged on subsequent scans."""

    def __init__(self):
        self.history_file = Config.SCAN_HISTORY_FILE
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        if self.history_file.exists():
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.last_scan = data.get("last_scan")
            self.known_jobs: dict = data.get("known_jobs", {})
        else:
            self.last_scan = None
            self.known_jobs = {}

    def _save(self):
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(
                {"last_scan": self.last_scan, "known_jobs": self.known_jobs},
                f,
                indent=2,
                ensure_ascii=False,
            )

    def update_and_mark_new(self, jobs: List[JobListing]) -> List[Tuple[JobListing, bool]]:
        """Update history and return (job, is_new) pairs.

        A job is "new" if it has never been seen before, OR if it was first
        seen within the last 24 hours (so it stays highlighted for a full day).
        """
        now = datetime.now()
        cutoff = now - timedelta(hours=24)
        now_iso = now.isoformat()

        results = []
        for job in jobs:
            url = job.url
            if url not in self.known_jobs:
                self.known_jobs[url] = {
                    "title": job.title,
                    "company": job.company,
                    "first_seen": now_iso,
                }
                is_new = True
            else:
                first_seen = datetime.fromisoformat(self.known_jobs[url]["first_seen"])
                is_new = first_seen > cutoff

            results.append((job, is_new))

        self.last_scan = now_iso
        self._save()
        return results

    def new_count(self, jobs_with_flags: List[Tuple[JobListing, bool]]) -> int:
        return sum(1 for _, is_new in jobs_with_flags if is_new)
