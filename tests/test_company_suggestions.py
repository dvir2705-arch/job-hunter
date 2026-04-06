"""Tests for suggest_companies() — Haiku-driven company suggestions."""

import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from tempfile import NamedTemporaryFile

from job_hunter.profile import UserProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(**overrides) -> UserProfile:
    """Build a minimal UserProfile with sensible defaults."""
    defaults = dict(
        name="Test User",
        email="test@example.com",
        phone="0500000000",
        target_positions=["software developer"],
        skills=["Python", "C"],
        experience_level="none",
        location={"country": "Israel"},
    )
    defaults.update(overrides)
    return UserProfile(**defaults)


def _make_response(text: str):
    """Build a fake anthropic message response."""
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def _write_registry(companies: list) -> str:
    """Write a temporary companies.json and return its path."""
    f = NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"companies": companies}, f)
    f.close()
    return f.name


SAMPLE_REGISTRY = [
    {"name": "Intel", "domain": ["chip_design", "ai_ml"], "priority": True},
    {"name": "NVIDIA", "domain": ["chip_design", "ai_ml"], "priority": True},
    {"name": "Wix", "domain": ["web_dev"], "priority": False},
    {"name": "Mobileye", "domain": ["autonomous_driving", "ai_ml"], "priority": True},
    {"name": "Elbit", "domain": ["defense", "communications"], "priority": False},
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSuggestCompanies:
    """Tests for suggest_companies()."""

    @patch("job_hunter.jobs.search_strategy.Config.validate")
    @patch("job_hunter.jobs.search_strategy.anthropic.Anthropic")
    def test_returns_registry_and_additional(self, mock_anthropic_cls, mock_validate):
        """Haiku response with both tiers is parsed correctly."""
        from job_hunter.jobs.search_strategy import suggest_companies

        haiku_response = json.dumps({
            "registry": ["Intel", "NVIDIA"],
            "additional": ["Google", "Microsoft"],
        })
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_response(haiku_response)
        mock_anthropic_cls.return_value = mock_client

        registry_path = _write_registry(SAMPLE_REGISTRY)
        profile = _make_profile()

        result = suggest_companies(profile, registry_path=registry_path)

        assert result["registry"] == ["Intel", "NVIDIA"]
        assert result["additional"] == ["Google", "Microsoft"]

    @patch("job_hunter.jobs.search_strategy.Config.validate")
    @patch("job_hunter.jobs.search_strategy.anthropic.Anthropic")
    def test_filters_invalid_registry_names(self, mock_anthropic_cls, mock_validate):
        """Registry names not in companies.json are dropped."""
        from job_hunter.jobs.search_strategy import suggest_companies

        haiku_response = json.dumps({
            "registry": ["Intel", "FakeCompany", "NVIDIA"],
            "additional": [],
        })
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_response(haiku_response)
        mock_anthropic_cls.return_value = mock_client

        registry_path = _write_registry(SAMPLE_REGISTRY)
        profile = _make_profile()

        result = suggest_companies(profile, registry_path=registry_path)

        assert "FakeCompany" not in result["registry"]
        assert result["registry"] == ["Intel", "NVIDIA"]

    @patch("job_hunter.jobs.search_strategy.Config.validate")
    @patch("job_hunter.jobs.search_strategy.anthropic.Anthropic")
    def test_handles_markdown_fences(self, mock_anthropic_cls, mock_validate):
        """JSON wrapped in markdown code fences is parsed correctly."""
        from job_hunter.jobs.search_strategy import suggest_companies

        haiku_response = '```json\n{"registry": ["Intel"], "additional": ["Google"]}\n```'
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_response(haiku_response)
        mock_anthropic_cls.return_value = mock_client

        registry_path = _write_registry(SAMPLE_REGISTRY)
        profile = _make_profile()

        result = suggest_companies(profile, registry_path=registry_path)

        assert result["registry"] == ["Intel"]
        assert result["additional"] == ["Google"]

    @patch("job_hunter.jobs.search_strategy.Config.validate")
    @patch("job_hunter.jobs.search_strategy.anthropic.Anthropic")
    def test_fallback_on_api_failure(self, mock_anthropic_cls, mock_validate):
        """On API failure, returns all priority companies from registry."""
        from job_hunter.jobs.search_strategy import suggest_companies

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")
        mock_anthropic_cls.return_value = mock_client

        registry_path = _write_registry(SAMPLE_REGISTRY)
        profile = _make_profile()

        result = suggest_companies(profile, registry_path=registry_path)

        # Should return priority companies as fallback
        assert "Intel" in result["registry"]
        assert "NVIDIA" in result["registry"]
        assert "Mobileye" in result["registry"]
        # Non-priority should not be included
        assert "Wix" not in result["registry"]
        assert result["additional"] == []

    @patch("job_hunter.jobs.search_strategy.Config.validate")
    @patch("job_hunter.jobs.search_strategy.anthropic.Anthropic")
    def test_empty_profile_still_works(self, mock_anthropic_cls, mock_validate):
        """Minimal profile with no skills/positions still produces a valid call."""
        from job_hunter.jobs.search_strategy import suggest_companies

        haiku_response = json.dumps({
            "registry": ["Intel"],
            "additional": [],
        })
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_response(haiku_response)
        mock_anthropic_cls.return_value = mock_client

        registry_path = _write_registry(SAMPLE_REGISTRY)
        profile = _make_profile(target_positions=[], skills=[])

        result = suggest_companies(profile, registry_path=registry_path)

        assert result["registry"] == ["Intel"]
        # Verify the API was actually called (not fallback)
        mock_client.messages.create.assert_called_once()
