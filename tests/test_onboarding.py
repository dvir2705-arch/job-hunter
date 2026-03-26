"""Tests for Priority 4 — onboarding flow (init command, CV pre-fill, profile guard)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from job_hunter.cli import cli
from job_hunter.profile import UserProfile, profile_exists


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Patch Config.DATA_DIR to a temp directory for isolation."""
    with patch("job_hunter.config.Config.DATA_DIR", tmp_path), \
         patch("job_hunter.profile.Config.DATA_DIR", tmp_path):
        yield tmp_path


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# UserProfile.save tests
# ---------------------------------------------------------------------------

class TestUserProfileSave:
    def test_save_creates_file(self, tmp_data_dir):
        profile = UserProfile(name="Test User", email="test@example.com", phone="123")
        path = profile.save(tmp_data_dir / "user_profile.json")
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["name"] == "Test User"
        assert data["email"] == "test@example.com"

    def test_save_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "profile.json"
        profile = UserProfile(name="A", email="a@b.com", phone="1")
        profile.save(nested)
        assert nested.exists()

    def test_save_roundtrip(self, tmp_data_dir):
        original = UserProfile(
            name="Dvir", email="d@g.com", phone="053",
            university="BGU", degree="B.Sc. EE",
            domains=["software", "dsp"], skills=["Python"],
        )
        path = original.save(tmp_data_dir / "user_profile.json")
        loaded = UserProfile.load(path)
        assert loaded.name == original.name
        assert loaded.domains == original.domains
        assert loaded.skills == original.skills


# ---------------------------------------------------------------------------
# profile_exists tests
# ---------------------------------------------------------------------------

class TestProfileExists:
    def test_returns_false_when_missing(self, tmp_data_dir):
        assert profile_exists() is False

    def test_returns_true_when_present(self, tmp_data_dir):
        profile = UserProfile(name="X", email="x@x.com", phone="1")
        profile.save(tmp_data_dir / "user_profile.json")
        assert profile_exists() is True


# ---------------------------------------------------------------------------
# `job-hunter init` command tests
# ---------------------------------------------------------------------------

class TestInitCommand:
    def test_init_creates_profile(self, runner, tmp_data_dir):
        result = runner.invoke(cli, ["init"], input="Alice\nalice@example.com\n555\nMIT\nB.Sc. CS\n\n")
        assert result.exit_code == 0
        assert "Profile saved" in result.output
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert data["name"] == "Alice"
        assert data["email"] == "alice@example.com"
        assert len(data["domains"]) > 0  # defaults applied

    def test_init_custom_domains(self, runner, tmp_data_dir):
        result = runner.invoke(cli, ["init"], input="Bob\nb@b.com\n111\nUni\nBSc\nml, python, rust\n")
        assert result.exit_code == 0
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert data["domains"] == ["ml", "python", "rust"]

    def test_init_aborts_if_exists_and_user_declines(self, runner, tmp_data_dir):
        # Create existing profile
        UserProfile(name="Old", email="o@o.com", phone="0").save(
            tmp_data_dir / "user_profile.json"
        )
        result = runner.invoke(cli, ["init"], input="n\n")
        assert result.exit_code == 0
        assert "Aborted" in result.output
        # Profile unchanged
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert data["name"] == "Old"

    def test_init_overwrites_if_confirmed(self, runner, tmp_data_dir):
        UserProfile(name="Old", email="o@o.com", phone="0").save(
            tmp_data_dir / "user_profile.json"
        )
        result = runner.invoke(cli, ["init"], input="y\nNew\nnew@n.com\n222\nUni\nBSc\n\n")
        assert result.exit_code == 0
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert data["name"] == "New"


# ---------------------------------------------------------------------------
# CV pre-fill tests
# ---------------------------------------------------------------------------

class TestCVPreFill:
    def test_init_from_cv_prefills_fields(self, runner, tmp_data_dir, tmp_path):
        cv_json = {
            "name": "CV Person",
            "email": "cv@example.com",
            "phone": "999",
            "education": [{"institution": "Stanford", "degree": "M.Sc. AI"}],
            "skills": ["Python", "TensorFlow"],
        }
        cv_path = tmp_path / "cv.json"
        cv_path.write_text(json.dumps(cv_json), encoding="utf-8")

        # Press Enter for each prompt to accept pre-filled defaults
        result = runner.invoke(cli, ["init", "--from-cv", str(cv_path)],
                               input="\n\n\n\n\n\n")
        assert result.exit_code == 0
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert data["name"] == "CV Person"
        assert data["university"] == "Stanford"
        assert "Python" in data["skills"]


# ---------------------------------------------------------------------------
# require_profile guard tests
# ---------------------------------------------------------------------------

class TestRequireProfileGuard:
    def test_cv_adapt_blocked_without_profile(self, runner, tmp_data_dir):
        result = runner.invoke(cli, ["cv", "adapt", "-j", "fake.txt"])
        assert result.exit_code != 0
        assert "Profile not found" in result.output
        assert "job-hunter init" in result.output

    def test_jobs_search_blocked_without_profile(self, runner, tmp_data_dir):
        result = runner.invoke(cli, ["jobs", "search", "-q", "python"])
        assert result.exit_code != 0
        assert "Profile not found" in result.output

    def test_jobs_scan_blocked_without_profile(self, runner, tmp_data_dir):
        result = runner.invoke(cli, ["jobs", "scan"])
        assert result.exit_code != 0
        assert "Profile not found" in result.output

    def test_jobs_discover_blocked_without_profile(self, runner, tmp_data_dir):
        result = runner.invoke(cli, ["jobs", "discover"])
        assert result.exit_code != 0
        assert "Profile not found" in result.output
