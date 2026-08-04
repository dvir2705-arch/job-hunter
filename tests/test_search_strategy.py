"""Tests for search_strategy.py — SearchConfig generation from profiles."""

from unittest.mock import patch

import pytest

from job_hunter.profile import UserProfile


@pytest.fixture(autouse=True)
def isolate_profile_save(tmp_path):
    """Prevent tests from writing to the real user_profile.json."""
    with patch("job_hunter.jobs.search_strategy._save_cached_queries"):
        yield


from job_hunter.jobs.search_strategy import (
    DEFAULT_MAX_WORKERS,
    SENIORITY_REJECT_EXPERIENCED,
    SENIORITY_REJECT_FULL,
    SearchConfig,
    _fallback_queries,
    _get_cached_queries,
    build_search_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _student_profile(**overrides) -> UserProfile:
    defaults = dict(
        name="Test Student",
        email="test@test.com",
        phone="050-1234567",
        skills=["Python", "MATLAB"],
        target_positions=["software", "DSP", "chip design"],
        domains=["software", "electrical", "chip"],
        location={"country": "Israel", "cities": [], "radius_km": 25},
        education={"university": "BGU", "degree": "B.Sc. EE", "year": "3rd"},
        search_config={},
    )
    defaults.update(overrides)
    return UserProfile(**defaults)


def _experienced_profile(**overrides) -> UserProfile:
    defaults = dict(
        name="Test Experienced",
        email="exp@test.com",
        phone="050-9999999",
        skills=["Python", "React", "AWS"],
        target_positions=["fullstack", "backend"],
        domains=["software", "web", "cloud"],
        location={"country": "Israel", "cities": ["Tel Aviv"], "radius_km": 25},
        experience_level="3-7",
        work_experience=[{"title": "Software Engineer", "company": "Startup"}],
        search_config={},
    )
    defaults.update(overrides)
    return UserProfile(**defaults)


def _junior_profile(**overrides) -> UserProfile:
    """No education.year, no work_experience."""
    defaults = dict(
        name="Test Junior",
        email="jr@test.com",
        phone="050-5555555",
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
        config = build_search_config(
            _student_profile(
                search_config={"queries": ["test query"]},
            )
        )
        assert config.level_keywords == ["student", "intern"]

    def test_student_seniority_reject_full(self):
        config = build_search_config(
            _student_profile(
                search_config={"queries": ["test query"]},
            )
        )
        assert config.seniority_reject == list(SENIORITY_REJECT_FULL)
        assert "senior" in config.seniority_reject

    def test_experienced_no_level_keywords(self):
        config = build_search_config(
            _experienced_profile(
                search_config={"queries": ["test query"]},
            )
        )
        assert config.level_keywords == []

    def test_experienced_reduced_seniority_reject(self):
        config = build_search_config(
            _experienced_profile(
                search_config={"queries": ["test query"]},
            )
        )
        assert config.seniority_reject == list(SENIORITY_REJECT_EXPERIENCED)
        assert "senior" not in config.seniority_reject
        assert "director" in config.seniority_reject

    def test_junior_level_keywords(self):
        config = build_search_config(
            _junior_profile(
                search_config={"queries": ["test query"]},
            )
        )
        assert config.level_keywords == ["junior", "entry level"]

    def test_junior_full_seniority_reject(self):
        config = build_search_config(
            _junior_profile(
                search_config={"queries": ["test query"]},
            )
        )
        assert config.seniority_reject == list(SENIORITY_REJECT_FULL)


# ---------------------------------------------------------------------------
# Cached queries
# ---------------------------------------------------------------------------


class TestCachedQueries:
    def test_reads_cached_queries(self):
        cached = ["chip design student", "software intern"]
        config = build_search_config(
            _student_profile(
                search_config={
                    "queries": cached,
                    "generated_at": "2026-03-29T14:00:00",
                },
            )
        )
        assert config.queries == cached

    def test_empty_search_config_triggers_generation(self):
        """When search_config is empty, fallback queries are generated (Haiku mocked to fail)."""
        with patch("job_hunter.jobs.search_strategy.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value.messages.create.side_effect = (
                Exception("no API")
            )
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
        config = build_search_config(
            _student_profile(
                search_config={"queries": ["test"]},
            )
        )
        assert "LinkedInScraper" in config.enabled_scrapers
        assert "JobSpyScraper" in config.enabled_scrapers

    def test_intel_enabled_when_in_watchlist(self):
        """Intel in watchlist + companies.json registry → IntelScraper enabled."""
        config = build_search_config(
            _student_profile(
                watchlist=["Intel"],
                search_config={"queries": ["test"]},
            )
        )
        assert "IntelScraper" in config.enabled_scrapers

    def test_no_duplicate_scrapers(self):
        config = build_search_config(
            _student_profile(
                watchlist=["Intel", "NVIDIA"],
                search_config={"queries": ["test"]},
            )
        )
        assert len(config.enabled_scrapers) == len(set(config.enabled_scrapers))


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


class TestLocation:
    def test_uses_profile_country(self):
        config = build_search_config(
            _student_profile(
                location={"country": "Germany", "cities": ["Berlin"], "radius_km": 50},
                search_config={"queries": ["test"]},
            )
        )
        assert config.location == "Germany"

    def test_defaults_to_israel(self):
        config = build_search_config(
            _student_profile(
                location={"country": "", "cities": [], "radius_km": 25},
                search_config={"queries": ["test"]},
            )
        )
        assert config.location == "Israel"

    def test_empty_location_dict_defaults(self):
        config = build_search_config(
            _student_profile(
                location={},
                search_config={"queries": ["test"]},
            )
        )
        assert config.location == "Israel"


# ---------------------------------------------------------------------------
# Max workers
# ---------------------------------------------------------------------------


class TestMaxWorkers:
    def test_default_max_workers(self):
        config = build_search_config(
            _student_profile(
                search_config={"queries": ["test"]},
            )
        )
        assert config.max_workers == DEFAULT_MAX_WORKERS
        assert config.max_workers == 5


# ---------------------------------------------------------------------------
# Experience level
# ---------------------------------------------------------------------------


class TestExperienceLevel:
    def test_none_student_gets_student_keywords(self):
        config = build_search_config(
            _student_profile(
                experience_level="none",
                search_config={"queries": ["test"]},
            )
        )
        assert config.level_keywords == ["student", "intern"]
        assert config.seniority_reject == list(SENIORITY_REJECT_FULL)

    def test_none_non_student_gets_junior_keywords(self):
        config = build_search_config(
            _junior_profile(
                experience_level="none",
                search_config={"queries": ["test"]},
            )
        )
        assert config.level_keywords == ["junior", "entry level"]
        assert config.seniority_reject == list(SENIORITY_REJECT_FULL)

    def test_1_3_gets_junior(self):
        config = build_search_config(
            _experienced_profile(
                experience_level="1-3",
                search_config={"queries": ["test"]},
            )
        )
        assert config.level_keywords == ["junior"]
        assert config.seniority_reject == list(SENIORITY_REJECT_FULL)

    def test_3_7_gets_experienced(self):
        config = build_search_config(
            _experienced_profile(
                experience_level="3-7",
                search_config={"queries": ["test"]},
            )
        )
        assert config.level_keywords == []
        assert config.seniority_reject == list(SENIORITY_REJECT_EXPERIENCED)

    def test_7_plus_gets_no_restrictions(self):
        config = build_search_config(
            _experienced_profile(
                experience_level="7+",
                search_config={"queries": ["test"]},
            )
        )
        assert config.level_keywords == []
        assert config.seniority_reject == []

    def test_empty_experience_falls_back_to_is_student(self):
        """Empty experience_level with education.year → student behavior."""
        config = build_search_config(
            _student_profile(
                experience_level="",
                search_config={"queries": ["test"]},
            )
        )
        assert config.level_keywords == ["student", "intern"]

    def test_empty_experience_with_work_exp_falls_back(self):
        """Empty experience_level with work_experience → 1-3 behavior."""
        config = build_search_config(
            _experienced_profile(
                experience_level="",
                search_config={"queries": ["test"]},
            )
        )
        assert config.level_keywords == ["junior"]


# ---------------------------------------------------------------------------
# Watchlist-driven companies
# ---------------------------------------------------------------------------


class TestWatchlist:
    def test_watchlist_overrides_companies_json(self):
        p = _student_profile(
            watchlist=["CompanyA", "CompanyB"],
            search_config={"queries": ["test"]},
        )
        config = build_search_config(p)
        assert config.companies == ["CompanyA", "CompanyB"]
        assert config.priority_companies == ["CompanyA", "CompanyB"]

    def test_empty_watchlist_means_no_company_scans(self):
        """Empty watchlist → no companies, no company scan tasks."""
        p = _student_profile(
            watchlist=[],
            search_config={"queries": ["test"]},
        )
        config = build_search_config(p)
        assert config.companies == []
        assert config.priority_companies == []

    def test_watchlist_enables_matching_scrapers(self):
        p = _student_profile(
            watchlist=["Intel", "SomeOtherCo"],
            search_config={"queries": ["test"]},
        )
        config = build_search_config(p)
        assert "IntelScraper" in config.enabled_scrapers
        assert "LinkedInScraper" in config.enabled_scrapers

    def test_watchlist_cross_refs_registry(self):
        """Watchlist with 3 companies: 2 in companies.json, 1 unknown.
        All 3 returned as companies. Known ones get scrapers enabled."""
        p = _student_profile(
            watchlist=["Intel", "NVIDIA", "UnknownStartup"],
            search_config={"queries": ["test"]},
        )
        config = build_search_config(p)
        # All 3 in companies list
        assert config.companies == ["Intel", "NVIDIA", "UnknownStartup"]
        assert config.priority_companies == ["Intel", "NVIDIA", "UnknownStartup"]
        # Known scrapers enabled from registry
        assert "IntelScraper" in config.enabled_scrapers
        assert "NVIDIAScraper" in config.enabled_scrapers
        # Unknown company doesn't add a scraper (searched via JobSpy)
        scraper_names = [
            s
            for s in config.enabled_scrapers
            if s not in ("LinkedInScraper", "JobSpyScraper")
        ]
        assert "UnknownStartupScraper" not in scraper_names

    def test_empty_watchlist_no_company_tasks_in_parallel_scan(self):
        """Integration: empty watchlist → parallel_scan gets no company tasks."""
        import pathlib
        import tempfile

        from job_hunter.jobs.scan_cache import ScanCache
        from job_hunter.jobs.scraper import JobScanner

        scanner = JobScanner()
        scanner.SCRAPER_REGISTRY = {}

        with tempfile.TemporaryDirectory() as tmp:
            cache = ScanCache(path=pathlib.Path(tmp) / "cache.json")
            config = SearchConfig(
                queries=["test"],
                companies=[],
                priority_companies=[],
                enabled_scrapers=[],
            )
            with patch.object(scanner, "_run_source", return_value=[]) as mock_run:
                scanner.parallel_scan(config, cache, include_companies=True)
                # No company tasks should have been submitted
                company_keys = [
                    call.args[0]
                    for call in mock_run.call_args_list
                    if call.args[0].startswith("company:")
                ]
                assert company_keys == []
