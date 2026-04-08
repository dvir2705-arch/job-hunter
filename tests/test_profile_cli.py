"""Tests for profile CLI commands: show, validate, edit, and --profile-path flag."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from job_hunter.cli import cli
from job_hunter.profile import UserProfile


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Patch Config.DATA_DIR to a temp directory for isolation."""
    with patch("job_hunter.config.Config.DATA_DIR", tmp_path), \
         patch("job_hunter.config.Config._BASE_DATA_DIR", tmp_path), \
         patch("job_hunter.profile.Config.DATA_DIR", tmp_path):
        yield tmp_path


@pytest.fixture(autouse=True)
def reset_profile_cache():
    """Reset cached profile between tests."""
    import job_hunter.profile as pm
    pm._profile = None
    pm._profile_path_override = None
    yield
    pm._profile = None
    pm._profile_path_override = None


@pytest.fixture
def runner():
    return CliRunner()


def _write_profile(path: Path, **overrides) -> Path:
    """Write a minimal valid profile and return its path."""
    data = {
        "name": "Test User",
        "email": "test@example.com",
        "phone": "050-1234567",
        "skills": ["Python", "SQL"],
        "target_positions": ["Backend Developer"],
        "domains": ["software"],
        "experience_level": "1-3",
        "education": {"university": "BGU", "degree": "B.Sc. EE", "year": "3rd"},
        "location": {"country": "Israel", "cities": ["Tel Aviv"], "radius_km": 25},
        "watchlist": ["Google", "Microsoft"],
        "hard_rules": {"cv_title": "EE Student"},
    }
    data.update(overrides)
    profile_path = path / "user_profile.json"
    profile_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return profile_path


# ---------------------------------------------------------------------------
# profile show
# ---------------------------------------------------------------------------

class TestProfileShow:
    def test_show_displays_contact(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir)
        result = runner.invoke(cli, ["profile", "show"])
        assert result.exit_code == 0
        assert "Test User" in result.output
        assert "test@example.com" in result.output
        assert "050-1234567" in result.output

    def test_show_displays_skills(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir)
        result = runner.invoke(cli, ["profile", "show"])
        assert "Python" in result.output
        assert "SQL" in result.output

    def test_show_displays_education(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir)
        result = runner.invoke(cli, ["profile", "show"])
        assert "BGU" in result.output
        assert "B.Sc. EE" in result.output

    def test_show_displays_watchlist(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir)
        result = runner.invoke(cli, ["profile", "show"])
        assert "Google" in result.output
        assert "Microsoft" in result.output

    def test_show_skips_empty_sections(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, education={}, watchlist=[], domains=[])
        result = runner.invoke(cli, ["profile", "show"])
        assert result.exit_code == 0
        assert "Education" not in result.output
        assert "Watchlist" not in result.output
        assert "Domains" not in result.output

    def test_show_no_profile_exits(self, runner, tmp_data_dir):
        result = runner.invoke(cli, ["profile", "show"])
        assert result.exit_code != 0
        assert "Profile not found" in result.output


# ---------------------------------------------------------------------------
# profile validate
# ---------------------------------------------------------------------------

class TestProfileValidate:
    def test_validate_clean_profile(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir)
        result = runner.invoke(cli, ["profile", "validate"])
        assert result.exit_code == 0
        assert "no issues" in result.output.lower()

    def test_validate_warns_missing_skills(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, skills=[])
        result = runner.invoke(cli, ["profile", "validate"])
        assert "No skills listed" in result.output

    def test_validate_warns_missing_domains(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, domains=[], target_positions=[], skills=[])
        result = runner.invoke(cli, ["profile", "validate"])
        assert "job matching" in result.output

    def test_validate_error_bad_experience(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, experience_level="invalid")
        result = runner.invoke(cli, ["profile", "validate"])
        assert result.exit_code == 1
        assert "Invalid experience_level" in result.output

    def test_validate_warns_skill_overlap(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, skills=["Python"], skills_not=["python"])
        result = runner.invoke(cli, ["profile", "validate"])
        assert "overlap" in result.output.lower()


# ---------------------------------------------------------------------------
# profile edit
# ---------------------------------------------------------------------------

class TestProfileEdit:
    def test_edit_name(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir)
        result = runner.invoke(cli, ["profile", "edit"], input="1\nNew Name\n0\n")
        assert result.exit_code == 0
        assert "Saved" in result.output
        # Verify persisted
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert data["name"] == "New Name"

    def test_edit_skills_list(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir)
        result = runner.invoke(cli, ["profile", "edit"], input="5\nGo, Rust, C\n0\n")
        assert result.exit_code == 0
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert data["skills"] == ["Go", "Rust", "C"]

    def test_edit_exit_immediately(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir)
        result = runner.invoke(cli, ["profile", "edit"], input="0\n")
        assert result.exit_code == 0
        assert "Done editing" in result.output

    def test_edit_invalid_choice(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir)
        result = runner.invoke(cli, ["profile", "edit"], input="99\n0\n")
        assert "Invalid choice" in result.output


# ---------------------------------------------------------------------------
# --profile-path flag
# ---------------------------------------------------------------------------

class TestProfilePathFlag:
    def test_show_with_custom_path(self, runner, tmp_path):
        profile_path = tmp_path / "custom_profile.json"
        data = {
            "name": "Custom User",
            "email": "custom@test.com",
            "phone": "999",
            "skills": ["Java"],
            "target_positions": ["SRE"],
            "domains": ["cloud"],
            "experience_level": "3-7",
        }
        profile_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        result = runner.invoke(cli, ["--profile-path", str(profile_path), "profile", "show"])
        assert result.exit_code == 0
        assert "Custom User" in result.output

    def test_validate_with_custom_path(self, runner, tmp_path):
        profile_path = tmp_path / "custom_profile.json"
        data = {
            "name": "V",
            "email": "v@t.com",
            "phone": "1",
            "experience_level": "bad",
        }
        profile_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        result = runner.invoke(cli, ["--profile-path", str(profile_path), "profile", "validate"])
        assert result.exit_code == 1
        assert "Invalid experience_level" in result.output
