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
            education={"university": "BGU", "degree": "B.Sc. EE"},
            domains=["software", "dsp"], skills=["Python"],
        )
        path = original.save(tmp_data_dir / "user_profile.json")
        loaded = UserProfile.load(path)
        assert loaded.name == original.name
        assert loaded.domains == original.domains
        assert loaded.skills == original.skills
        assert loaded.university == "BGU"


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
        # Prompts: name, email, phone, university, degree, specialization,
        #          cv_title, target_positions, skills, skills_not, domains
        inputs = "Alice\nalice@example.com\n555\nMIT\nB.Sc. CS\nAI\n\nsoftware, ml\nPython\n\nml, python, software\n"
        result = runner.invoke(cli, ["init"], input=inputs)
        assert result.exit_code == 0
        assert "Profile saved" in result.output
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert data["name"] == "Alice"
        assert data["email"] == "alice@example.com"
        assert data["education"]["specialization"] == "AI"
        assert data["target_positions"] == ["software", "ml"]
        assert data["domains"] == ["ml", "python", "software"]

    def test_init_custom_domains(self, runner, tmp_data_dir):
        inputs = "Bob\nb@b.com\n111\nUni\nBSc\n\n\n\n\n\nml, python, rust\n"
        result = runner.invoke(cli, ["init"], input=inputs)
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
        inputs = "y\nNew\nnew@n.com\n222\nUni\nBSc\n\n\n\n\n\n\n"
        result = runner.invoke(cli, ["init"], input=inputs)
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
        # Prompts: name, email, phone, university, degree, specialization,
        #          cv_title, target_positions, skills, skills_not, domains
        result = runner.invoke(cli, ["init", "--from-cv", str(cv_path)],
                               input="\n\n\n\n\n\n\n\n\n\n\n")
        assert result.exit_code == 0
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert data["name"] == "CV Person"
        assert data["education"]["university"] == "Stanford"
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


# ---------------------------------------------------------------------------
# Phase 2: experience_level + watchlist
# ---------------------------------------------------------------------------

class TestExperienceLevelField:
    def test_save_and_load_experience_level(self, tmp_data_dir):
        p = UserProfile(name="A", email="a@b.com", phone="1", experience_level="3-7")
        path = p.save(tmp_data_dir / "user_profile.json")
        loaded = UserProfile.load(path)
        assert loaded.experience_level == "3-7"

    def test_save_and_load_watchlist(self, tmp_data_dir):
        p = UserProfile(
            name="A", email="a@b.com", phone="1",
            watchlist=["Intel", "Google"],
        )
        path = p.save(tmp_data_dir / "user_profile.json")
        loaded = UserProfile.load(path)
        assert loaded.watchlist == ["Intel", "Google"]

    def test_validate_invalid_experience_level(self):
        p = UserProfile(name="A", email="a@b.com", phone="1", experience_level="20+")
        issues = p.validate()
        assert any("experience_level" in i for i in issues)

    def test_validate_valid_experience_levels(self):
        for level in ("", "none", "1-3", "3-7", "7+"):
            p = UserProfile(name="A", email="a@b.com", phone="1", experience_level=level)
            issues = p.validate()
            assert not any("experience_level" in i for i in issues)

    def test_migration_student_gets_none(self, tmp_data_dir):
        """Profile with education.year but no experience_level → migrates to 'none'."""
        data = {
            "name": "A", "email": "a@b.com", "phone": "1",
            "education": {"university": "BGU", "year": "3rd"},
        }
        path = tmp_data_dir / "user_profile.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = UserProfile.load(path)
        assert loaded.experience_level == "none"

    def test_migration_experienced_gets_1_3(self, tmp_data_dir):
        """Profile with work_experience but no experience_level → migrates to '1-3'."""
        data = {
            "name": "A", "email": "a@b.com", "phone": "1",
            "work_experience": [{"title": "SWE", "company": "X"}],
        }
        path = tmp_data_dir / "user_profile.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = UserProfile.load(path)
        assert loaded.experience_level == "1-3"

    def test_migration_no_exp_no_edu_gets_none(self, tmp_data_dir):
        """Profile with nothing → migrates to 'none'."""
        data = {"name": "A", "email": "a@b.com", "phone": "1"}
        path = tmp_data_dir / "user_profile.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = UserProfile.load(path)
        assert loaded.experience_level == "none"

    def test_existing_experience_level_not_overwritten(self, tmp_data_dir):
        """Profile with explicit experience_level keeps it."""
        data = {
            "name": "A", "email": "a@b.com", "phone": "1",
            "experience_level": "7+",
        }
        path = tmp_data_dir / "user_profile.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = UserProfile.load(path)
        assert loaded.experience_level == "7+"

    def test_default_watchlist_empty(self):
        p = UserProfile(name="A", email="a@b.com", phone="1")
        assert p.watchlist == []
