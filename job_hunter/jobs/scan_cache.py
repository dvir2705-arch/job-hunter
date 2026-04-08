"""Per-source scan result cache.

Stores job listings keyed by source (company, query, or scraper) with
timestamps so repeated scans can skip sources that were recently checked.

Tracks zero_streak per source: when a source returns 0 results for 3+
consecutive scans, its TTL extends to 24 hours instead of 90 minutes.
A single >0 result resets the streak back to normal TTL.

Cache file: data/jobs/scan_cache.json
Key format: "company:Intel", "query:chip design student", "scraper:IntelScraper"
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from job_hunter.config import Config
from job_hunter.logger import get_logger
from .scraper import JobListing

logger = get_logger(__name__)

DEFAULT_TTL_MINUTES = 90
ZERO_STREAK_THRESHOLD = 3
ZERO_STREAK_TTL_MINUTES = 24 * 60  # 24 hours


class ScanCache:
    """Simple JSON file cache for scan results, keyed by source."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or Config.SCAN_CACHE_FILE
        self._data: Optional[dict] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, source: str, ttl_minutes: int = DEFAULT_TTL_MINUTES) -> Optional[Tuple[List[JobListing], int]]:
        """Return (jobs, age_minutes) if source is cached and fresh, else None.

        Uses extended TTL (24h) for sources with zero_streak >= 3.
        Jobs are returned as deserialized JobListing objects.
        """
        data = self._load()
        entry = data.get(source)
        if not entry:
            return None

        age = self._age_minutes(entry)
        if age is None:
            return None

        effective_ttl = self._effective_ttl(entry, ttl_minutes)
        if age > effective_ttl:
            return None

        raw_jobs = entry.get("jobs", [])
        jobs = self._deserialize_jobs(raw_jobs)
        return jobs, age

    def put(self, source: str, jobs: List[JobListing]) -> None:
        """Save results for a source with the current timestamp.

        Updates zero_streak: incremented when jobs is empty, reset to 0
        when jobs has results.
        """
        data = self._load()
        old_entry = data.get(source, {})
        old_streak = old_entry.get("zero_streak", 0)

        if len(jobs) == 0:
            new_streak = old_streak + 1
        else:
            new_streak = 0

        data[source] = {
            "last_scan": datetime.now().isoformat(),
            "jobs": [self._serialize_job(j) for j in jobs],
            "zero_streak": new_streak,
        }
        self._save(data)

    def is_fresh(self, source: str, ttl_minutes: int = DEFAULT_TTL_MINUTES) -> bool:
        """True if source was scanned within its effective TTL."""
        data = self._load()
        entry = data.get(source)
        if not entry:
            return False

        age = self._age_minutes(entry)
        if age is None:
            return False

        effective_ttl = self._effective_ttl(entry, ttl_minutes)
        return age <= effective_ttl

    def zero_streak(self, source: str) -> int:
        """Return the zero_streak count for a source (0 if not cached)."""
        data = self._load()
        entry = data.get(source)
        if not entry:
            return 0
        return entry.get("zero_streak", 0)

    def age_minutes(self, source: str) -> Optional[int]:
        """Return age in minutes for a source, or None if not cached."""
        data = self._load()
        entry = data.get(source)
        if not entry:
            return None
        return self._age_minutes(entry)

    def clear(self) -> None:
        """Delete the cache file and reset in-memory state."""
        self._data = None
        try:
            self.path.unlink(missing_ok=True)
        except OSError as e:
            logger.warning("Could not delete cache file: %s", e)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_job(job: JobListing) -> dict:
        return {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "posted": job.posted,
        }

    @staticmethod
    def _deserialize_jobs(raw: list) -> List[JobListing]:
        jobs = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                jobs.append(JobListing(
                    title=item.get("title", ""),
                    company=item.get("company", ""),
                    location=item.get("location", ""),
                    url=item.get("url", ""),
                    posted=item.get("posted", ""),
                ))
            except Exception:
                continue
        return jobs

    # ------------------------------------------------------------------
    # File I/O — atomic writes, graceful corruption recovery
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        """Load cache from disk. Returns empty dict on any error."""
        if self._data is not None:
            return self._data

        if not self.path.exists():
            self._data = {}
            return self._data

        try:
            raw = self.path.read_text(encoding="utf-8")
            if not raw.strip():
                raise ValueError("empty file")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("root is not a dict")
            self._data = data
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.warning("Corrupted cache file (%s) — deleting and starting fresh", e)
            self._delete_corrupt()
            self._data = {}

        return self._data

    def _save(self, data: dict) -> None:
        """Atomic write: write to temp file then rename to avoid partial writes."""
        self._data = data
        self.path.parent.mkdir(parents=True, exist_ok=True)

        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self.path.parent),
                suffix=".tmp",
                prefix="scan_cache_",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                # On Windows, target must not exist for os.replace to work
                # os.replace handles this atomically on both platforms
                os.replace(tmp_path, str(self.path))
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as e:
            logger.error("Failed to write cache: %s", e)

    def _delete_corrupt(self) -> None:
        """Remove a corrupted cache file."""
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _effective_ttl(entry: dict, base_ttl: int) -> int:
        """Return the TTL to use: extended if zero_streak >= threshold."""
        streak = entry.get("zero_streak", 0)
        if streak >= ZERO_STREAK_THRESHOLD:
            return ZERO_STREAK_TTL_MINUTES
        return base_ttl

    @staticmethod
    def _age_minutes(entry: dict) -> Optional[int]:
        """Parse last_scan timestamp and return age in minutes."""
        ts = entry.get("last_scan")
        if not ts:
            return None
        try:
            scanned_at = datetime.fromisoformat(ts)
            delta = datetime.now() - scanned_at
            return int(delta.total_seconds() / 60)
        except (ValueError, TypeError):
            return None
