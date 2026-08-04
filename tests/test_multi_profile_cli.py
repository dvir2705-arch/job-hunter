"""CLI tests for multi-profile features: list, switch, delete, current, init with profile name."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from job_hunter.cli import cli
from job_hunter.config import Config


@pytest.fixture(autouse=True)
def isolate(tmp_path):
    """Point Config at a temp directory and reset profile cache."""
    import job_hunter.profile as pm

    original = {
        "_BASE_DATA_DIR": Config._BASE_DATA_DIR,
        "DATA_DIR": Config.DATA_DIR,
        "_active_user": Config._active_user,
    }
    Config._BASE_DATA_DIR = tmp_path
    Config.DATA_DIR = tmp_path
    Config._active_user = None
    pm._profile = None
    pm._profile_path_override = None

    yield tmp_path

    for key, value in original.items():
        setattr(Config, key, value)
    Config._recalculate_paths()
    pm._profile = None
    pm._profile_path_override = None


@pytest.fixture
def runner():
    return CliRunner()


def _create_profile(
    base: Path, slug: str, name: str = "Test User", email: str = "test@example.com"
):
    """Create a profile under users/<slug>/ and return the directory."""
    d = base / "users" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "user_profile.json").write_text(
        json.dumps(
            {
                "name": name,
                "email": email,
                "phone": "050-0000000",
                "skills": ["Python"],
                "target_positions": ["Developer"],
                "domains": ["software"],
                "experience_level": "1-3",
                "location": {"country": "Israel", "cities": [], "radius_km": 25},
            }
        ),
        encoding="utf-8",
    )
    return d


def _set_active(base: Path, slug: str):
    (base / ".active_profile").write_text(slug + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# profile list
# ---------------------------------------------------------------------------


class TestProfileList:
    def test_no_profiles(self, runner, isolate):
        result = runner.invoke(cli, ["profile", "list"])
        assert result.exit_code == 0
        assert "No profiles found" in result.output

    def test_one_profile(self, runner, isolate):
        _create_profile(isolate, "alice", name="Alice Smith")
        _set_active(isolate, "alice")
        result = runner.invoke(cli, ["profile", "list"])
        assert result.exit_code == 0
        assert "alice" in result.output
        assert "Alice Smith" in result.output

    def test_multiple_profiles(self, runner, isolate):
        _create_profile(isolate, "alice", name="Alice")
        _create_profile(isolate, "bob", name="Bob")
        _set_active(isolate, "bob")
        result = runner.invoke(cli, ["profile", "list"])
        assert result.exit_code == 0
        assert "alice" in result.output
        assert "bob" in result.output


# ---------------------------------------------------------------------------
# profile current
# ---------------------------------------------------------------------------


class TestProfileCurrent:
    def test_no_active(self, runner, isolate):
        result = runner.invoke(cli, ["profile", "current"])
        assert result.exit_code == 0
        assert "No active profile" in result.output

    def test_has_active(self, runner, isolate):
        _create_profile(isolate, "dvir")
        _set_active(isolate, "dvir")
        result = runner.invoke(cli, ["profile", "current"])
        assert result.exit_code == 0
        assert "dvir" in result.output


# ---------------------------------------------------------------------------
# profile switch
# ---------------------------------------------------------------------------


class TestProfileSwitch:
    def test_switch_success(self, runner, isolate):
        _create_profile(isolate, "alice")
        _create_profile(isolate, "bob")
        _set_active(isolate, "alice")
        result = runner.invoke(cli, ["profile", "switch", "bob"])
        assert result.exit_code == 0
        assert "Switched to profile 'bob'" in result.output
        # Verify .active_profile changed
        active = (isolate / ".active_profile").read_text(encoding="utf-8").strip()
        assert active == "bob"

    def test_switch_nonexistent(self, runner, isolate):
        result = runner.invoke(cli, ["profile", "switch", "ghost"])
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_switch_already_active(self, runner, isolate):
        _create_profile(isolate, "alice")
        _set_active(isolate, "alice")
        result = runner.invoke(cli, ["profile", "switch", "alice"])
        assert result.exit_code == 0
        assert "Already on" in result.output


# ---------------------------------------------------------------------------
# profile delete
# ---------------------------------------------------------------------------


class TestProfileDelete:
    def test_delete_success(self, runner, isolate):
        _create_profile(isolate, "alice")
        _create_profile(isolate, "bob")
        _set_active(isolate, "bob")
        result = runner.invoke(cli, ["profile", "delete", "alice"], input="y\n")
        assert result.exit_code == 0
        assert "deleted" in result.output
        assert not (isolate / "users" / "alice").exists()

    def test_delete_active_blocked(self, runner, isolate):
        _create_profile(isolate, "alice")
        _set_active(isolate, "alice")
        result = runner.invoke(cli, ["profile", "delete", "alice"])
        assert result.exit_code == 0
        assert "Cannot delete" in result.output
        assert (isolate / "users" / "alice").exists()

    def test_delete_aborted(self, runner, isolate):
        _create_profile(isolate, "alice")
        _set_active(isolate, "bob")
        result = runner.invoke(cli, ["profile", "delete", "alice"], input="n\n")
        assert result.exit_code == 0
        assert "Aborted" in result.output
        assert (isolate / "users" / "alice").exists()

    def test_delete_nonexistent(self, runner, isolate):
        _set_active(isolate, "bob")
        result = runner.invoke(cli, ["profile", "delete", "ghost"], input="y\n")
        assert result.exit_code == 0
        assert "not found" in result.output


# ---------------------------------------------------------------------------
# Auto-activate on startup
# ---------------------------------------------------------------------------


class TestAutoActivate:
    def test_reads_active_profile(self, runner, isolate):
        _create_profile(isolate, "dvir", name="Dvir")
        _set_active(isolate, "dvir")
        result = runner.invoke(cli, ["profile", "current"])
        assert result.exit_code == 0
        assert "dvir" in result.output

    def test_user_flag_overrides(self, runner, isolate):
        _create_profile(isolate, "alice")
        _create_profile(isolate, "bob")
        _set_active(isolate, "alice")
        # --user bob should override active
        result = runner.invoke(cli, ["--user", "bob", "profile", "current"])
        assert result.exit_code == 0
        # The current command reads from .active_profile, but Config is set to bob
        # Just verify it doesn't crash
        assert result.exit_code == 0

    def test_legacy_migration_on_startup(self, runner, isolate):
        # Create legacy profile at root
        (isolate / "user_profile.json").write_text(
            json.dumps(
                {
                    "name": "Legacy User",
                    "email": "legacy@test.com",
                    "phone": "050",
                    "skills": [],
                    "target_positions": ["Dev"],
                    "domains": [],
                    "experience_level": "none",
                    "location": {"country": "IL", "cities": [], "radius_km": 25},
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(cli, ["profile", "current"])
        assert result.exit_code == 0
        # Should have migrated
        assert "Migrated" in result.output or "default" in result.output


# ---------------------------------------------------------------------------
# init with profile name
# ---------------------------------------------------------------------------


class TestInitMultiProfile:
    @patch("job_hunter.config.Config.ANTHROPIC_API_KEY", "")
    def test_init_creates_named_profile(self, runner, isolate):
        result = runner.invoke(
            cli,
            ["init", "--name", "test-user"],
            input=(
                "Alice Smith\n"  # name
                "alice@test.com\n"  # email
                "050-111\n"  # phone
                "Developer\n"  # target roles
                "Python\n"  # skills
                "none\n"  # experience
                "Israel\n"  # country
                "\n"  # cities (empty)
                "n\n"  # studying? no
                "y\n"  # save?
                "n\n"  # CV import? no
            ),
        )
        assert result.exit_code == 0, f"Output: {result.output}"
        # Profile saved under users/test-user/
        assert (isolate / "users" / "test-user" / "user_profile.json").exists()
        # Active set
        active = (isolate / ".active_profile").read_text(encoding="utf-8").strip()
        assert active == "test-user"

    @patch("job_hunter.config.Config.ANTHROPIC_API_KEY", "")
    def test_init_prompts_for_name(self, runner, isolate):
        result = runner.invoke(
            cli,
            ["init"],
            input=(
                "Bob Jones\n"  # name
                "bob@test.com\n"  # email
                "050-222\n"  # phone
                "Analyst\n"  # target roles
                "SQL\n"  # skills
                "1-3\n"  # experience
                "Israel\n"  # country
                "\n"  # cities
                "y\n"  # save?
                "bob-jones\n"  # profile name
                "n\n"  # CV import? no
            ),
        )
        assert result.exit_code == 0, f"Output: {result.output}"
        assert (isolate / "users" / "bob-jones" / "user_profile.json").exists()

    @patch("job_hunter.config.Config.ANTHROPIC_API_KEY", "")
    def test_init_shows_existing_profiles(self, runner, isolate):
        _create_profile(isolate, "alice", name="Alice")
        _set_active(isolate, "alice")
        result = runner.invoke(
            cli,
            ["init", "--name", "bob"],
            input=(
                "Bob\n"
                "bob@t.com\n"
                "050\n"
                "Dev\n"
                "Python\n"
                "none\n"
                "Israel\n"
                "\n"
                "n\n"  # studying
                "y\n"  # save
                "n\n"  # CV import? no
            ),
        )
        assert result.exit_code == 0
        assert "alice" in result.output  # shows existing profiles
