"""Tests for search_strategy.py — SearchConfig generation from profiles."""

import pytest
from unittest.mock import patch, MagicMock

from job_hunter.profile import UserProfile
from job_hunter.jobs.search_strategy import (
    build_search_config,
    generate_queries,
    _fallback_queries,
    _get_cached_queries,
    _load_companies,
    SearchConfig,
    SENIORITY_REJECT_FULL,
    SENIORITY_REJECT_EXPERIENCED,
    DEFAULT_MAX_WORKERS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _student_profile(**overrides) -> UserProfile:
    defaults = dict(
        name="Test Student", email="test@test.com", phone="050-1234567",
        skills=["Python", "MATLAB"],
        target_positions=["software", "DSP", "chip design"],
        domains=["software", "electrical", "chip"],
        location="Israel",
        education={"university": "BGU", "degree": "B.Sc. EE", "year": "3rd"},
        search_config={},
    )
    defaults.update(overrides)
    return UserProfile(**defaults)


def _experienced_profile(**overrides) -> UserProfile:
    defaults = dict(
        name="Test Experienced", email="exp@test.com", phone="050-9999999",
        skills=["Python", "React", "AWS"],
        target_positions=["fullstack", "backend"],
        domains=["software", "web", "cloud"],
        location="Tel Aviv",
        work_experience=[{"title": "Software Engineer", "company": "Startup"}],
        search_config={},
    )
    defaults.update(overrides)
    return UserProfile(**defaults)


def _junior_profile(**overrides) -> UserProfile:
    """No education.year, no work_experience."""
    defaults = dict(
        name="Test Junior", email="jr@test.com", phone="050-5555555",
        skills=["Python"],
        target_positions=["data analyst", "software"],
        domains=["data", "software"],
        search_config={},
    )
    defaults.update(overrides)
    return UserProfile(**defaults)


# ---------------------------------------------------------------------------
# Level / seniority detection
# ---------------------------------------------------------------------------

class TestLevelDetection:
    def test_student_level_keywords(self):
        config = build_search_config(_student_profile(
            search_config={"queries": ["test query"]},
        ))
        assert config.level_keywords == ["student", "intern"]

    def test_student_seniority_reject_full(self):
        config = build_search_config(_student_profile(
            search_config={"queries": ["test query"]},
        ))
        assert config.seniority_reject == list(SENIORITY_REJECT_FULL)
        assert "senior" in config.seniority_reject

    def test_experienced_no_level_keywords(self):
        config = build_search_config(_experienced_profile(
            search_config={"queries": ["test query"]},
        ))
        assert config.level_keywords == []

    def test_experienced_reduced_seniority_reject(self):
        config = build_search_config(_experienced_profile(
            search_config={"queries": ["test query"]},
        ))
        assert config.seniority_reject == list(SENIORITY_REJECT_EXPERIENCED)
        assert "senior" not in config.seniority_reject
        assert "director" in config.seniority_reject

    def test_junior_level_keywords(self):
        config = build_search_config(_junior_profile(
            search_config={"queries": ["test query"]},
        ))
        assert config.level_keywords == ["junior", "entry level"]

    def test_junior_full_seniority_reject(self):
        config = build_search_config(_junior_profile(
            search_config={"queries": ["test query"]},
        ))
        assert config.seniority_reject == list(SENIORITY_REJECT_FULL)


# ---------------------------------------------------------------------------
# Cached queries
# ---------------------------------------------------------------------------

class TestCachedQueries:
    def test_reads_cached_queries(self):
        cached = ["chip design student", "software intern"]
        config = build_search_config(_student_profile(
            search_config={"queries": cached, "generated_at": "2026-03-29T14:00:00"},
        ))
        assert config.queries == cached

    def test_empty_search_config_triggers_generation(self):
        """When search_config is empty, fallback queries are generated (Haiku mocked to fail)."""
        with patch("job_hunter.jobs.search_strategy.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value.messages.create.side_effect = Exception("no API")
            config = build_search_config(_student_profile(search_config={}))
        # Should fall back to rule-based queries
        assert len(config.queries) > 0
        assert any("student" in q for q in config.queries)

    def test_missing_search_config_field(self):
        """Profile with no search_config at all should not crash."""
        p = _student_profile()
        p.search_config = {}
        cached = _get_cached_queries(p)
        assert cached is None


# ---------------------------------------------------------------------------
# Fallback queries
# ---------------------------------------------------------------------------

class TestFallbackQueries:
    def test_student_fallback_includes_suffix(self):
        queries = _fallback_queries(_student_profile())
        assert all("student" in q for q in queries)

    def test_experienced_fallback_no_suffix(self):
        queries = _fallback_queries(_experienced_profile())
        assert all("student" not in q and "junior" not in q for q in queries)

    def test_junior_fallback_includes_junior(self):
        queries = _fallback_queries(_junior_profile())
        assert any("junior" in q for q in queries)

    def test_fallback_caps_at_5_positions(self):
        p = _student_profile(target_positions=["a", "b", "c", "d", "e", "f", "g"])
        queries = _fallback_queries(p)
        # 5 from positions + maybe 1 generic "student"
        assert len(queries) <= 7

    def test_empty_positions_uses_engineer(self):
        p = _student_profile(target_positions=[])
        queries = _fallback_queries(p)
        assert any("engineer" in q for q in queries)


# ---------------------------------------------------------------------------
# Enabled scrapers
# ---------------------------------------------------------------------------

class TestEnabledScrapers:
    def test_always_includes_linkedin_and_jobspy(self):
        config = build_search_config(_student_profile(
            search_config={"queries": ["test"]},
        ))
        assert "LinkedInScraper" in config.enabled_scrapers
        assert "JobSpyScraper" in config.enabled_scrapers

    def test_intel_enabled_when_in_company_list(self):
        """Intel is in companies.json so IntelScraper should be enabled."""
        config = build_search_config(_student_profile(
            search_config={"queries": ["test"]},
        ))
        assert "IntelScraper" in config.enabled_scrapers

    def test_no_duplicate_scrapers(self):
        config = build_search_config(_student_profile(
            search_config={"queries": ["test"]},
        ))
        assert len(config.enabled_scrapers) == len(set(config.enabled_scrapers))


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

class TestLocation:
    def test_uses_profile_location(self):
        config = build_search_config(_student_profile(
            location="Haifa",
            search_config={"queries": ["test"]},
        ))
        assert config.location == "Haifa"

    def test_defaults_to_israel(self):
        config = build_search_config(_student_profile(
            location="",
            search_config={"queries": ["test"]},
        ))
        assert config.location == "Israel"


# ---------------------------------------------------------------------------
# Max workers
# ---------------------------------------------------------------------------

class TestMaxWorkers:
    def test_default_max_workers(self):
        config = build_search_config(_student_profile(
            search_config={"queries": ["test"]},
        ))
        assert config.max_workers == DEFAULT_MAX_WORKERS
        assert config.max_workers == 5
