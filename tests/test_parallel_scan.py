"""Tests for JobScanner.parallel_scan() — orchestration with mocked scrapers.

No real HTTP calls. All scrapers are mocked to return controlled data.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from job_hunter.jobs.scraper import JobScanner, JobListing
from job_hunter.jobs.scan_cache import ScanCache
from job_hunter.jobs.search_strategy import SearchConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jobs(prefix: str, n: int = 2) -> list:
    return [
        JobListing(
            title=f"{prefix} Job {i}",
            company=f"{prefix} Corp",
            location="Israel",
            url=f"https://example.com/{prefix.lower()}/{i}",
            posted="2026-03-29",
        )
        for i in range(n)
    ]


def _make_config(**overrides) -> SearchConfig:
    defaults = dict(
        queries=["test query"],
        location="Israel",
        level_keywords=["student"],
        seniority_reject=["senior"],
        companies=["FakeCo", "AnotherCo"],
        priority_companies=["FakeCo"],
        enabled_scrapers=["MockScraperA", "MockScraperB"],
        max_workers=3,
    )
    defaults.update(overrides)
    return SearchConfig(**defaults)


def _mock_scraper(name: str, jobs: list) -> MagicMock:
    """Create a mock scraper that returns the given jobs from .search()."""
    scraper = MagicMock()
    scraper.COMPANY_NAME = name
    scraper.search.return_value = jobs
    return scraper


@pytest.fixture
def cache(tmp_path):
    return ScanCache(path=tmp_path / "test_cache.json")


@pytest.fixture
def scanner():
    return JobScanner()


# ---------------------------------------------------------------------------
# Basic parallel dispatch
# ---------------------------------------------------------------------------

class TestParallelDispatch:
    def test_runs_all_enabled_scrapers(self, scanner, cache):
        mock_a = _mock_scraper("A", _make_jobs("A", 2))
        mock_b = _mock_scraper("B", _make_jobs("B", 3))
        scanner.SCRAPER_REGISTRY = {
            "MockScraperA": mock_a,
            "MockScraperB": mock_b,
        }

        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["MockScraperA", "MockScraperB"],
        )
        results = scanner.parallel_scan(
            config, cache, include_companies=False,
        )
        assert mock_a.search.called
        assert mock_b.search.called
        assert len(results) == 5  # 2 + 3, no duplicates

    def test_runs_each_query_per_scraper(self, scanner, cache):
        mock_a = _mock_scraper("A", [])
        mock_a.search.return_value = _make_jobs("A", 1)
        scanner.SCRAPER_REGISTRY = {"MockScraperA": mock_a}

        config = _make_config(
            queries=["q1", "q2", "q3"],
            enabled_scrapers=["MockScraperA"],
        )
        scanner.parallel_scan(config, cache, include_companies=False)
        # Should be called once per query
        assert mock_a.search.call_count == 3

    def test_skips_unknown_scrapers(self, scanner, cache):
        scanner.SCRAPER_REGISTRY = {}
        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["NonexistentScraper"],
        )
        results = scanner.parallel_scan(
            config, cache, include_companies=False,
        )
        assert results == []


# ---------------------------------------------------------------------------
# Company scan integration
# ---------------------------------------------------------------------------

class TestCompanyScan:
    def test_company_tasks_submitted(self, scanner, cache):
        scanner.SCRAPER_REGISTRY = {}
        config = _make_config(
            queries=["student"],
            enabled_scrapers=[],
            priority_companies=["TestCo"],
        )

        with patch.object(
            scanner, "_run_source",
            return_value=_make_jobs("TestCo", 2),
        ) as mock_run:
            results = scanner.parallel_scan(
                config, cache, include_companies=True,
                only_priority=True,
            )
        # At least the company task should have been submitted
        called_keys = [call.args[0] for call in mock_run.call_args_list]
        assert any("company:TestCo" in k for k in called_keys)

    def test_company_scan_disabled(self, scanner, cache):
        mock_a = _mock_scraper("A", _make_jobs("A", 1))
        scanner.SCRAPER_REGISTRY = {"MockScraperA": mock_a}

        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["MockScraperA"],
            priority_companies=["ShouldNotRun"],
        )
        results = scanner.parallel_scan(
            config, cache, include_companies=False,
        )
        # Only scraper results, no company results
        assert len(results) == 1

    def test_only_priority_vs_all(self, scanner, cache):
        scanner.SCRAPER_REGISTRY = {}

        config = _make_config(
            queries=["student"],
            enabled_scrapers=[],
            companies=["Co1", "Co2", "Co3"],
            priority_companies=["Co1"],
        )

        # only_priority=True → 1 company task
        with patch.object(scanner, "_run_source", return_value=[]):
            scanner.parallel_scan(
                config, cache, include_companies=True, only_priority=True,
            )
            # Clear cache for next run
            cache.clear()

        with patch.object(scanner, "_run_source", return_value=[]) as mock_run:
            scanner.parallel_scan(
                config, cache, include_companies=True, only_priority=False,
            )
            company_keys = [
                call.args[0] for call in mock_run.call_args_list
                if call.args[0].startswith("company:")
            ]
            assert len(company_keys) == 3


# ---------------------------------------------------------------------------
# Dedup across sources
# ---------------------------------------------------------------------------

class TestDedup:
    def test_dedup_across_scrapers(self, scanner, cache):
        """Same job from two scrapers is deduplicated."""
        shared_job = JobListing(
            title="Shared Job", company="Corp",
            location="Israel", url="https://example.com/shared",
        )
        mock_a = _mock_scraper("A", [shared_job])
        mock_b = _mock_scraper("B", [shared_job])
        scanner.SCRAPER_REGISTRY = {
            "MockScraperA": mock_a,
            "MockScraperB": mock_b,
        }
        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["MockScraperA", "MockScraperB"],
        )
        results = scanner.parallel_scan(
            config, cache, include_companies=False,
        )
        assert len(results) == 1

    def test_dedup_by_title_company(self, scanner, cache):
        """Same title+company but different URL is still deduped."""
        job1 = JobListing(
            title="Engineer", company="Corp",
            location="Israel", url="https://a.com/1",
        )
        job2 = JobListing(
            title="Engineer", company="Corp",
            location="Israel", url="https://b.com/2",
        )
        mock_a = _mock_scraper("A", [job1])
        mock_b = _mock_scraper("B", [job2])
        scanner.SCRAPER_REGISTRY = {
            "MockScraperA": mock_a,
            "MockScraperB": mock_b,
        }
        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["MockScraperA", "MockScraperB"],
        )
        results = scanner.parallel_scan(
            config, cache, include_companies=False,
        )
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Cache integration
# ---------------------------------------------------------------------------

class TestCacheIntegration:
    def test_skips_fresh_sources(self, scanner, cache):
        """If a source is in cache and fresh, the scraper is NOT called."""
        mock_a = _mock_scraper("A", _make_jobs("A", 2))
        scanner.SCRAPER_REGISTRY = {"MockScraperA": mock_a}

        # Pre-populate cache
        cache.put("scraper:MockScraperA:q1", _make_jobs("cached", 3))

        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["MockScraperA"],
        )
        results = scanner.parallel_scan(
            config, cache, include_companies=False, ttl_minutes=90,
        )
        # Scraper should NOT have been called — result served from cache
        mock_a.search.assert_not_called()
        assert len(results) == 3  # cached jobs

    def test_saves_results_after_scrape(self, scanner, cache):
        mock_a = _mock_scraper("A", _make_jobs("A", 2))
        scanner.SCRAPER_REGISTRY = {"MockScraperA": mock_a}

        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["MockScraperA"],
        )
        scanner.parallel_scan(
            config, cache, include_companies=False,
        )
        # Cache should now have the result
        cached = cache.get("scraper:MockScraperA:q1")
        assert cached is not None
        assert len(cached[0]) == 2

    def test_stale_cache_triggers_rescrape(self, scanner, cache, tmp_path):
        """If cache is stale, the scraper IS called."""
        import json
        from datetime import datetime, timedelta

        mock_a = _mock_scraper("A", _make_jobs("fresh", 1))
        scanner.SCRAPER_REGISTRY = {"MockScraperA": mock_a}

        # Pre-populate cache with old timestamp
        cache.put("scraper:MockScraperA:q1", _make_jobs("old", 5))
        # Backdate to 2 hours ago
        data = json.loads(cache.path.read_text(encoding="utf-8"))
        past = (datetime.now() - timedelta(minutes=120)).isoformat()
        data["scraper:MockScraperA:q1"]["last_scan"] = past
        cache.path.write_text(json.dumps(data), encoding="utf-8")

        # Force cache reload
        fresh_cache = ScanCache(path=cache.path)

        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["MockScraperA"],
        )
        results = scanner.parallel_scan(
            config, fresh_cache, include_companies=False, ttl_minutes=90,
        )
        # Scraper should have been called since cache is stale
        mock_a.search.assert_called_once()
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Error handling — one source fails, others continue
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_failing_scraper_doesnt_kill_scan(self, scanner, cache):
        mock_a = _mock_scraper("A", _make_jobs("A", 2))
        mock_b = _mock_scraper("B", [])
        mock_b.search.side_effect = RuntimeError("network error")
        scanner.SCRAPER_REGISTRY = {
            "MockScraperA": mock_a,
            "MockScraperB": mock_b,
        }

        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["MockScraperA", "MockScraperB"],
        )
        results = scanner.parallel_scan(
            config, cache, include_companies=False,
        )
        # A's results should still be returned
        assert len(results) == 2

    def test_all_scrapers_fail_returns_empty(self, scanner, cache):
        mock_a = _mock_scraper("A", [])
        mock_a.search.side_effect = Exception("fail")
        mock_b = _mock_scraper("B", [])
        mock_b.search.side_effect = Exception("fail")
        scanner.SCRAPER_REGISTRY = {
            "MockScraperA": mock_a,
            "MockScraperB": mock_b,
        }

        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["MockScraperA", "MockScraperB"],
        )
        results = scanner.parallel_scan(
            config, cache, include_companies=False,
        )
        assert results == []


# ---------------------------------------------------------------------------
# Progress callback
# ---------------------------------------------------------------------------

class TestProgressCallback:
    def test_callback_fires_per_source(self, scanner, cache):
        mock_a = _mock_scraper("A", _make_jobs("A", 2))
        mock_b = _mock_scraper("B", _make_jobs("B", 3))
        scanner.SCRAPER_REGISTRY = {
            "MockScraperA": mock_a,
            "MockScraperB": mock_b,
        }

        calls = []

        def on_progress(source, jobs_found, new_count, cached_age):
            calls.append((source, jobs_found, new_count, cached_age))

        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["MockScraperA", "MockScraperB"],
        )
        scanner.parallel_scan(
            config, cache, include_companies=False,
            progress_callback=on_progress,
        )
        assert len(calls) == 2
        sources = {c[0] for c in calls}
        assert "scraper:MockScraperA:q1" in sources
        assert "scraper:MockScraperB:q1" in sources

    def test_callback_shows_cached_age(self, scanner, cache):
        mock_a = _mock_scraper("A", _make_jobs("A", 2))
        scanner.SCRAPER_REGISTRY = {"MockScraperA": mock_a}

        # Pre-populate cache
        cache.put("scraper:MockScraperA:q1", _make_jobs("cached", 1))

        calls = []

        def on_progress(source, jobs_found, new_count, cached_age):
            calls.append((source, jobs_found, new_count, cached_age))

        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["MockScraperA"],
        )
        scanner.parallel_scan(
            config, cache, include_companies=False,
            progress_callback=on_progress,
        )
        assert len(calls) == 1
        assert calls[0][3] is not None  # cached_age should be an int
        assert calls[0][3] >= 0

    def test_callback_shows_none_age_for_live(self, scanner, cache):
        mock_a = _mock_scraper("A", _make_jobs("A", 2))
        scanner.SCRAPER_REGISTRY = {"MockScraperA": mock_a}

        calls = []

        def on_progress(source, jobs_found, new_count, cached_age):
            calls.append((source, jobs_found, new_count, cached_age))

        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["MockScraperA"],
        )
        scanner.parallel_scan(
            config, cache, include_companies=False,
            progress_callback=on_progress,
        )
        assert len(calls) == 1
        assert calls[0][3] is None  # live scrape, not cached

    def test_callback_on_failure(self, scanner, cache):
        mock_a = _mock_scraper("A", [])
        mock_a.search.side_effect = Exception("boom")
        scanner.SCRAPER_REGISTRY = {"MockScraperA": mock_a}

        calls = []

        def on_progress(source, jobs_found, new_count, cached_age):
            calls.append((source, jobs_found, new_count, cached_age))

        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["MockScraperA"],
        )
        scanner.parallel_scan(
            config, cache, include_companies=False,
            progress_callback=on_progress,
        )
        assert len(calls) == 1
        assert calls[0][1] == 0  # jobs_found = 0 on failure


# ---------------------------------------------------------------------------
# Stagger delay
# ---------------------------------------------------------------------------

class TestStagger:
    def test_stagger_delay_present(self, scanner, cache):
        """Verify submissions are staggered by at least 0.4s between them."""
        mock_a = _mock_scraper("A", _make_jobs("A", 1))
        mock_b = _mock_scraper("B", _make_jobs("B", 1))
        scanner.SCRAPER_REGISTRY = {
            "MockScraperA": mock_a,
            "MockScraperB": mock_b,
        }

        config = _make_config(
            queries=["q1"],
            enabled_scrapers=["MockScraperA", "MockScraperB"],
        )

        start = time.monotonic()
        scanner.parallel_scan(
            config, cache, include_companies=False,
        )
        elapsed = time.monotonic() - start
        # 2 tasks with 0.5s stagger → at least ~0.9s total
        # Use 0.8s threshold to account for timing variance
        assert elapsed >= 0.8, f"Expected >= 0.8s stagger, got {elapsed:.2f}s"
