"""Tests for B3 — per-user data isolation via Config.set_user()."""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

from job_hunter.config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_original_config():
    """Snapshot Config class attributes before a test."""
    return {
        "_BASE_DATA_DIR": Config._BASE_DATA_DIR,
        "DATA_DIR": Config.DATA_DIR,
        "OUTPUT_DIR": Config.OUTPUT_DIR,
        "CV_DIR": Config.CV_DIR,
        "APPLICATIONS_FILE": Config.APPLICATIONS_FILE,
        "JOBS_DIR": Config.JOBS_DIR,
        "COMPANIES_FILE": Config.COMPANIES_FILE,
        "DISCOVERED_COMPANIES_FILE": Config.DISCOVERED_COMPANIES_FILE,
        "SCAN_HISTORY_FILE": Config.SCAN_HISTORY_FILE,
        "SCAN_CACHE_FILE": Config.SCAN_CACHE_FILE,
        "COVER_LETTER_DATA_DIR": Config.COVER_LETTER_DATA_DIR,
        "COVER_LETTER_HISTORY_FILE": Config.COVER_LETTER_HISTORY_FILE,
        "RECRUITERS_FILE": Config.RECRUITERS_FILE,
        "LOG_DIR": Config.LOG_DIR,
        "CV_OUTPUT_DIR": Config.CV_OUTPUT_DIR,
        "COVER_LETTER_OUTPUT_DIR": Config.COVER_LETTER_OUTPUT_DIR,
        "_active_user": Config._active_user,
    }


def _restore_config(snapshot):
    """Restore Config class attributes after a test."""
    for key, value in snapshot.items():
        setattr(Config, key, value)


@pytest.fixture(autouse=True)
def reset_config():
    """Reset Config to default state after every test."""
    snapshot = _save_original_config()
    yield
    _restore_config(snapshot)


# ---------------------------------------------------------------------------
# Config.set_user() path recalculation
# ---------------------------------------------------------------------------

class TestSetUser:
    def test_set_user_rebases_data_dir(self):
        Config.set_user("alice")
        assert Config.DATA_DIR == Path("./data/users/alice")

    def test_set_user_recalculates_cv_dir(self):
        Config.set_user("alice")
        assert Config.CV_DIR == Path("./data/users/alice/cv")

    def test_set_user_recalculates_applications_file(self):
        Config.set_user("bob")
        assert Config.APPLICATIONS_FILE == Path("./data/users/bob/applications/applications.json")

    def test_set_user_recalculates_jobs_dir(self):
        Config.set_user("bob")
        assert Config.JOBS_DIR == Path("./data/users/bob/jobs")

    def test_set_user_recalculates_scan_files(self):
        Config.set_user("carol")
        assert Config.SCAN_HISTORY_FILE == Path("./data/users/carol/jobs/scan_history.json")
        assert Config.SCAN_CACHE_FILE == Path("./data/users/carol/jobs/scan_cache.json")
        assert Config.DISCOVERED_COMPANIES_FILE == Path("./data/users/carol/jobs/discovered_companies.json")

    def test_set_user_recalculates_cover_letter_paths(self):
        Config.set_user("dave")
        assert Config.COVER_LETTER_DATA_DIR == Path("./data/users/dave/cover_letters")
        assert Config.COVER_LETTER_HISTORY_FILE == Path("./data/users/dave/cover_letters/history.json")

    def test_set_user_recalculates_recruiters(self):
        Config.set_user("eve")
        assert Config.RECRUITERS_FILE == Path("./data/users/eve/recruiters/recruiters.json")

    def test_set_user_recalculates_log_dir(self):
        Config.set_user("frank")
        assert Config.LOG_DIR == Path("./data/users/frank/logs")

    def test_set_user_stores_active_user(self):
        Config.set_user("alice")
        assert Config._active_user == "alice"

    def test_companies_file_stays_at_root(self):
        """companies.json is a shared registry — never moves into user dir."""
        Config.set_user("alice")
        assert Config.companies_file() == Path("./data/jobs/companies.json")

    def test_output_dir_unchanged_by_set_user(self):
        """Output stays global (PDFs/letters are ephemeral)."""
        original_output = Config.OUTPUT_DIR
        Config.set_user("alice")
        assert Config.OUTPUT_DIR == original_output


# ---------------------------------------------------------------------------
# Backward compatibility — no user = single-user mode
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_default_data_dir(self):
        assert Config.DATA_DIR == Path("./data")

    def test_default_no_active_user(self):
        assert Config._active_user is None

    def test_default_cv_dir(self):
        assert Config.CV_DIR == Path("./data/cv")

    def test_default_applications_file(self):
        assert Config.APPLICATIONS_FILE == Path("./data/applications/applications.json")


# ---------------------------------------------------------------------------
# Modules use Config paths (not hardcoded)
# ---------------------------------------------------------------------------

class TestModulesUseConfig:
    def test_cover_letter_history_uses_config(self, tmp_path):
        Config.COVER_LETTER_DATA_DIR = tmp_path / "cl_data"
        Config.COVER_LETTER_OUTPUT_DIR = tmp_path / "cl_output"
        from job_hunter.cover_letter.history import CoverLetterHistory
        history = CoverLetterHistory()
        assert history.data_dir == tmp_path / "cl_data"
        assert history.output_dir == tmp_path / "cl_output"

    def test_job_history_uses_config(self, tmp_path):
        Config.SCAN_HISTORY_FILE = tmp_path / "jobs" / "scan_history.json"
        from job_hunter.jobs.history import JobHistory
        history = JobHistory()
        assert history.history_file == tmp_path / "jobs" / "scan_history.json"

    def test_recruiter_manager_uses_config(self, tmp_path):
        Config.RECRUITERS_FILE = tmp_path / "recruiters" / "recruiters.json"
        from job_hunter.recruiters.manager import RecruiterManager
        mgr = RecruiterManager()
        assert mgr.file == tmp_path / "recruiters" / "recruiters.json"

    def test_discovery_uses_config(self, tmp_path):
        Config.DISCOVERED_COMPANIES_FILE = tmp_path / "jobs" / "discovered.json"
        from job_hunter.jobs.discovery import CompanyDiscovery
        disc = CompanyDiscovery()
        assert disc.discovered_file == tmp_path / "jobs" / "discovered.json"

    def test_scan_cache_uses_config(self, tmp_path):
        Config.SCAN_CACHE_FILE = tmp_path / "jobs" / "scan_cache.json"
        from job_hunter.jobs.scan_cache import ScanCache
        cache = ScanCache()
        assert cache.path == tmp_path / "jobs" / "scan_cache.json"

    def test_tracker_uses_config(self, tmp_path):
        Config.APPLICATIONS_FILE = tmp_path / "apps" / "applications.json"
        (tmp_path / "apps").mkdir()
        from job_hunter.applications.tracker import ApplicationTracker
        tracker = ApplicationTracker()
        assert tracker.filepath == tmp_path / "apps" / "applications.json"

    def test_cv_manager_uses_config(self, tmp_path):
        Config.CV_DIR = tmp_path / "cv"
        from job_hunter.cv.manager import CVManager
        mgr = CVManager()
        assert mgr.cv_dir == tmp_path / "cv"


# ---------------------------------------------------------------------------
# ensure_dirs creates per-user directories
# ---------------------------------------------------------------------------

class TestEnsureDirs:
    def test_ensure_dirs_creates_user_directories(self, tmp_path):
        Config.DATA_DIR = tmp_path / "data" / "users" / "test"
        Config._recalculate_paths()
        Config.OUTPUT_DIR = tmp_path / "output"
        Config.CV_OUTPUT_DIR = Config.OUTPUT_DIR / "adapted_cv"
        Config.COVER_LETTER_OUTPUT_DIR = Config.OUTPUT_DIR / "cover_letters"
        Config.COVER_LETTER_DIR = Config.COVER_LETTER_OUTPUT_DIR
        Config.ensure_dirs()

        assert Config.DATA_DIR.exists()
        assert Config.CV_DIR.exists()
        assert Config.JOBS_DIR.exists()
        assert Config.COVER_LETTER_DATA_DIR.exists()
        assert Config.LOG_DIR.exists()
        assert Config.RECRUITERS_FILE.parent.exists()
        assert Config.APPLICATIONS_FILE.parent.exists()


# ---------------------------------------------------------------------------
# End-to-end: set_user + module isolation
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_two_users_get_separate_tracker_files(self, tmp_path):
        """Two users writing applications don't share application data."""
        with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
            from job_hunter.applications.tracker import ApplicationTracker
            from job_hunter.applications.models import Application

            # User 1
            Config._BASE_DATA_DIR = tmp_path
            Config.set_user("user1")
            Config.ensure_dirs()
            t1 = ApplicationTracker()
            t1.add(Application(job_title="Engineer", company="Acme"))

            # User 2
            Config.set_user("user2")
            Config.ensure_dirs()
            t2 = ApplicationTracker()
            t2.add(Application(job_title="Analyst", company="Globex"))

            # Verify isolation
            assert len(t1.applications) == 1
            assert t1.applications[0].company == "Acme"
            assert len(t2.applications) == 1
            assert t2.applications[0].company == "Globex"

            # Files are in separate dirs
            assert "user1" in str(t1.filepath)
            assert "user2" in str(t2.filepath)
