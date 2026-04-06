"""Tests for companies CLI commands: list, add, remove, suggest."""

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
        "education": {},
        "location": {"country": "Israel", "cities": [], "radius_km": 25},
        "watchlist": [],
    }
    data.update(overrides)
    profile_path = path / "user_profile.json"
    profile_path.write_text(json.dumps(data), encoding="utf-8")
    return profile_path


def _write_registry(path: Path) -> Path:
    """Write a small companies.json registry."""
    registry = {
        "companies": [
            {
                "name": "Intel",
                "domain": ["chip_design", "ai_ml"],
                "scraper": "IntelScraper",
                "priority": True,
            },
            {
                "name": "NVIDIA",
                "domain": ["chip_design", "ai_ml"],
                "scraper": "NVIDIAScraper",
                "priority": True,
            },
            {
                "name": "Mobileye",
                "domain": ["autonomous_driving"],
                "scraper": None,
                "priority": False,
            },
        ]
    }
    jobs_dir = path / "jobs"
    jobs_dir.mkdir(exist_ok=True)
    registry_path = jobs_dir / "companies.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    return registry_path


# ---------------------------------------------------------------------------
# companies list
# ---------------------------------------------------------------------------

class TestCompaniesList:
    def test_empty_watchlist(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=[])
        result = runner.invoke(cli, ["companies", "list"])
        assert result.exit_code == 0
        assert "empty" in result.output.lower()

    def test_shows_watchlist(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=["Intel", "Google"])
        _write_registry(tmp_data_dir)
        result = runner.invoke(cli, ["companies", "list"])
        assert result.exit_code == 0
        assert "Intel" in result.output
        assert "Google" in result.output
        assert "2 companies" in result.output

    def test_shows_scraper_info(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=["Intel", "Mobileye"])
        _write_registry(tmp_data_dir)
        result = runner.invoke(cli, ["companies", "list"])
        assert result.exit_code == 0
        assert "dedicated" in result.output
        assert "general only" in result.output

    def test_no_profile_error(self, runner, tmp_data_dir):
        result = runner.invoke(cli, ["companies", "list"])
        assert result.exit_code != 0 or "profile" in result.output.lower()


# ---------------------------------------------------------------------------
# companies add
# ---------------------------------------------------------------------------

class TestCompaniesAdd:
    def test_add_single(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=[])
        result = runner.invoke(cli, ["companies", "add", "Google"])
        assert result.exit_code == 0
        assert "Added" in result.output
        assert "Google" in result.output
        # Verify persisted
        profile = UserProfile.load(tmp_data_dir / "user_profile.json")
        assert "Google" in profile.watchlist

    def test_add_multiple(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=[])
        result = runner.invoke(cli, ["companies", "add", "Google", "Microsoft"])
        assert result.exit_code == 0
        assert "Google" in result.output
        profile = UserProfile.load(tmp_data_dir / "user_profile.json")
        assert "Google" in profile.watchlist
        assert "Microsoft" in profile.watchlist

    def test_add_duplicate(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=["Google"])
        result = runner.invoke(cli, ["companies", "add", "Google"])
        assert result.exit_code == 0
        assert "Already in watchlist" in result.output
        profile = UserProfile.load(tmp_data_dir / "user_profile.json")
        assert profile.watchlist.count("Google") == 1

    def test_add_mixed(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=["Google"])
        result = runner.invoke(cli, ["companies", "add", "Google", "Meta"])
        assert result.exit_code == 0
        assert "Added" in result.output
        assert "Meta" in result.output
        assert "Already in watchlist" in result.output


# ---------------------------------------------------------------------------
# companies remove
# ---------------------------------------------------------------------------

class TestCompaniesRemove:
    def test_remove_single(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=["Google", "Intel"])
        result = runner.invoke(cli, ["companies", "remove", "Google"])
        assert result.exit_code == 0
        assert "Removed" in result.output
        profile = UserProfile.load(tmp_data_dir / "user_profile.json")
        assert "Google" not in profile.watchlist
        assert "Intel" in profile.watchlist

    def test_remove_not_found(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=["Google"])
        result = runner.invoke(cli, ["companies", "remove", "Meta"])
        assert result.exit_code == 0
        assert "Not in watchlist" in result.output

    def test_remove_case_insensitive(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=["Google"])
        result = runner.invoke(cli, ["companies", "remove", "google"])
        assert result.exit_code == 0
        assert "Removed" in result.output
        profile = UserProfile.load(tmp_data_dir / "user_profile.json")
        assert len(profile.watchlist) == 0

    def test_remove_multiple(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=["Google", "Intel", "Meta"])
        result = runner.invoke(cli, ["companies", "remove", "Google", "Meta"])
        assert result.exit_code == 0
        assert "Removed" in result.output
        profile = UserProfile.load(tmp_data_dir / "user_profile.json")
        assert profile.watchlist == ["Intel"]


# ---------------------------------------------------------------------------
# companies suggest
# ---------------------------------------------------------------------------

class TestCompaniesSuggest:
    def test_suggest_adds_to_watchlist(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=[])
        _write_registry(tmp_data_dir)

        mock_result = {"registry": ["Intel", "NVIDIA"], "additional": ["Qualcomm"]}
        with patch("job_hunter.jobs.search_strategy.suggest_companies", return_value=mock_result):
            result = runner.invoke(cli, ["companies", "suggest"], input="y\n\n")
        assert result.exit_code == 0
        assert "Intel" in result.output
        assert "NVIDIA" in result.output
        assert "Qualcomm" in result.output
        profile = UserProfile.load(tmp_data_dir / "user_profile.json")
        assert "Intel" in profile.watchlist
        assert "Qualcomm" in profile.watchlist

    def test_suggest_skips_existing(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=["Intel"])
        _write_registry(tmp_data_dir)

        mock_result = {"registry": ["Intel", "NVIDIA"], "additional": []}
        with patch("job_hunter.jobs.search_strategy.suggest_companies", return_value=mock_result):
            result = runner.invoke(cli, ["companies", "suggest"], input="y\n\n")
        assert result.exit_code == 0
        assert "already in watchlist" in result.output
        profile = UserProfile.load(tmp_data_dir / "user_profile.json")
        # Intel should not be duplicated
        assert profile.watchlist.count("Intel") == 1

    def test_suggest_no_results(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=[])

        mock_result = {"registry": [], "additional": []}
        with patch("job_hunter.jobs.search_strategy.suggest_companies", return_value=mock_result):
            result = runner.invoke(cli, ["companies", "suggest"])
        assert result.exit_code == 0
        assert "No suggestions" in result.output

    def test_suggest_decline(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=[])

        mock_result = {"registry": ["Intel"], "additional": []}
        with patch("job_hunter.jobs.search_strategy.suggest_companies", return_value=mock_result):
            result = runner.invoke(cli, ["companies", "suggest"], input="n\n")
        assert result.exit_code == 0
        assert "No changes" in result.output
        profile = UserProfile.load(tmp_data_dir / "user_profile.json")
        assert len(profile.watchlist) == 0

    def test_suggest_all_already_in_watchlist(self, runner, tmp_data_dir):
        _write_profile(tmp_data_dir, watchlist=["Intel", "NVIDIA"])
        _write_registry(tmp_data_dir)

        mock_result = {"registry": ["Intel", "NVIDIA"], "additional": []}
        with patch("job_hunter.jobs.search_strategy.suggest_companies", return_value=mock_result):
            result = runner.invoke(cli, ["companies", "suggest"])
        assert result.exit_code == 0
        assert "already in your watchlist" in result.output
