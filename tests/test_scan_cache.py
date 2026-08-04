"""Tests for scan_cache.py — per-source result caching."""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from job_hunter.jobs.scan_cache import (
    DEFAULT_TTL_MINUTES,
    ZERO_STREAK_THRESHOLD,
    ScanCache,
)
from job_hunter.jobs.scraper import JobListing

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def cache_path(tmp_path):
    return tmp_path / "scan_cache.json"


@pytest.fixture
def cache(cache_path):
    return ScanCache(path=cache_path)


def _make_jobs(n: int = 3) -> list:
    return [
        JobListing(
            title=f"Job {i}",
            company=f"Company {i}",
            location="Israel",
            url=f"https://example.com/job/{i}",
            posted="2026-03-29",
        )
        for i in range(n)
    ]


def _backdate_entry(cache_path: Path, source: str, minutes_ago: int):
    """Manually set a cache entry's last_scan to N minutes in the past."""
    with open(cache_path, encoding="utf-8") as f:
        data = json.load(f)
    past = datetime.now() - timedelta(minutes=minutes_ago)
    data[source]["last_scan"] = past.isoformat()
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# Key format
# ---------------------------------------------------------------------------


class TestKeyFormat:
    def test_company_key(self, cache):
        jobs = _make_jobs(2)
        cache.put("company:Intel", jobs)
        result = cache.get("company:Intel")
        assert result is not None
        assert len(result[0]) == 2

    def test_query_key(self, cache):
        jobs = _make_jobs(1)
        cache.put("query:chip design student", jobs)
        result = cache.get("query:chip design student")
        assert result is not None
        assert len(result[0]) == 1

    def test_scraper_key(self, cache):
        jobs = _make_jobs(3)
        cache.put("scraper:IntelScraper", jobs)
        result = cache.get("scraper:IntelScraper")
        assert result is not None
        assert len(result[0]) == 3


# ---------------------------------------------------------------------------
# Put / Get round-trip — returns JobListing objects
# ---------------------------------------------------------------------------


class TestPutGet:
    def test_roundtrip_returns_job_listings(self, cache):
        jobs = _make_jobs(2)
        cache.put("company:NVIDIA", jobs)
        result = cache.get("company:NVIDIA")
        assert result is not None
        returned_jobs, age = result
        assert len(returned_jobs) == 2
        assert all(isinstance(j, JobListing) for j in returned_jobs)

    def test_roundtrip_preserves_fields(self, cache):
        job = JobListing(
            title="DSP Engineer",
            company="Qualcomm",
            location="Haifa",
            url="https://example.com/dsp",
            posted="2026-03-28",
        )
        cache.put("company:Qualcomm", [job])
        returned_jobs, _ = cache.get("company:Qualcomm")
        r = returned_jobs[0]
        assert r.title == "DSP Engineer"
        assert r.company == "Qualcomm"
        assert r.location == "Haifa"
        assert r.url == "https://example.com/dsp"
        assert r.posted == "2026-03-28"

    def test_age_is_zero_or_near_zero(self, cache):
        cache.put("query:test", _make_jobs(1))
        _, age = cache.get("query:test")
        assert age <= 1

    def test_get_missing_source_returns_none(self, cache):
        assert cache.get("company:Nonexistent") is None


# ---------------------------------------------------------------------------
# Freshness / TTL boundary
# ---------------------------------------------------------------------------


class TestFreshness:
    def test_fresh_at_89_minutes(self, cache, cache_path):
        cache.put("scraper:IntelScraper", _make_jobs(1))
        _backdate_entry(cache_path, "scraper:IntelScraper", 89)
        # Force reload from disk
        fresh_cache = ScanCache(path=cache_path)
        assert fresh_cache.is_fresh("scraper:IntelScraper", ttl_minutes=90) is True

    def test_stale_at_91_minutes(self, cache, cache_path):
        cache.put("scraper:IntelScraper", _make_jobs(1))
        _backdate_entry(cache_path, "scraper:IntelScraper", 91)
        fresh_cache = ScanCache(path=cache_path)
        assert fresh_cache.is_fresh("scraper:IntelScraper", ttl_minutes=90) is False

    def test_get_returns_none_when_stale(self, cache, cache_path):
        cache.put("query:test", _make_jobs(1))
        _backdate_entry(cache_path, "query:test", 91)
        stale_cache = ScanCache(path=cache_path)
        assert stale_cache.get("query:test", ttl_minutes=90) is None

    def test_get_returns_data_when_fresh(self, cache, cache_path):
        cache.put("query:test", _make_jobs(2))
        _backdate_entry(cache_path, "query:test", 89)
        fresh_cache = ScanCache(path=cache_path)
        result = fresh_cache.get("query:test", ttl_minutes=90)
        assert result is not None
        assert len(result[0]) == 2

    def test_custom_ttl(self, cache, cache_path):
        cache.put("company:Intel", _make_jobs(1))
        _backdate_entry(cache_path, "company:Intel", 31)
        fresh_cache = ScanCache(path=cache_path)
        assert fresh_cache.is_fresh("company:Intel", ttl_minutes=30) is False
        assert fresh_cache.is_fresh("company:Intel", ttl_minutes=60) is True

    def test_is_fresh_missing_source(self, cache):
        assert cache.is_fresh("company:Nonexistent") is False

    def test_age_minutes_returns_value(self, cache, cache_path):
        cache.put("query:test", _make_jobs(1))
        _backdate_entry(cache_path, "query:test", 45)
        fresh_cache = ScanCache(path=cache_path)
        age = fresh_cache.age_minutes("query:test")
        assert age is not None
        assert 44 <= age <= 46

    def test_age_minutes_missing_source(self, cache):
        assert cache.age_minutes("query:missing") is None

    def test_default_ttl_is_90(self):
        assert DEFAULT_TTL_MINUTES == 90

    def test_zero_streak_extends_ttl(self, cache, cache_path):
        """Source with zero_streak >= 3 uses 24h TTL instead of 90min."""
        # Build up a zero streak of 3
        for _ in range(ZERO_STREAK_THRESHOLD):
            cache.put("scraper:MarvellScraper:student", [])
        assert (
            cache.zero_streak("scraper:MarvellScraper:student") == ZERO_STREAK_THRESHOLD
        )

        # Backdate to 2 hours ago — stale under 90min, fresh under 24h
        _backdate_entry(cache_path, "scraper:MarvellScraper:student", 120)
        fresh_cache = ScanCache(path=cache_path)
        # Normal TTL would say stale, but zero_streak extends it
        result = fresh_cache.get("scraper:MarvellScraper:student", ttl_minutes=90)
        assert result is not None  # still fresh because of extended TTL

    def test_zero_streak_resets_on_results(self, cache):
        """Getting >0 results resets zero_streak back to 0."""
        for _ in range(ZERO_STREAK_THRESHOLD):
            cache.put("company:Intel", [])
        assert cache.zero_streak("company:Intel") == ZERO_STREAK_THRESHOLD

        cache.put("company:Intel", _make_jobs(2))
        assert cache.zero_streak("company:Intel") == 0

    def test_zero_streak_below_threshold_uses_normal_ttl(self, cache, cache_path):
        """Source with streak < 3 still uses normal TTL."""
        cache.put("company:Intel", [])
        cache.put("company:Intel", [])
        assert cache.zero_streak("company:Intel") == 2

        _backdate_entry(cache_path, "company:Intel", 91)
        stale_cache = ScanCache(path=cache_path)
        assert stale_cache.get("company:Intel", ttl_minutes=90) is None

    def test_zero_streak_increments(self, cache):
        """Each empty put increments the streak."""
        cache.put("query:test", [])
        assert cache.zero_streak("query:test") == 1
        cache.put("query:test", [])
        assert cache.zero_streak("query:test") == 2
        cache.put("query:test", [])
        assert cache.zero_streak("query:test") == 3

    def test_zero_streak_missing_source_is_zero(self, cache):
        assert cache.zero_streak("company:Nonexistent") == 0


# ---------------------------------------------------------------------------
# Empty cache
# ---------------------------------------------------------------------------


class TestEmptyCache:
    def test_get_on_new_cache(self, cache):
        assert cache.get("query:anything") is None

    def test_is_fresh_on_new_cache(self, cache):
        assert cache.is_fresh("query:anything") is False

    def test_clear_on_new_cache_no_crash(self, cache):
        cache.clear()  # should not raise

    def test_put_creates_file(self, cache, cache_path):
        assert not cache_path.exists()
        cache.put("query:test", _make_jobs(1))
        assert cache_path.exists()


# ---------------------------------------------------------------------------
# Corrupted / malformed JSON
# ---------------------------------------------------------------------------


class TestCorruptedCache:
    def test_corrupted_json_recovers(self, cache_path):
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text("{{not valid json!!!", encoding="utf-8")
        cache = ScanCache(path=cache_path)
        # Should not crash — recovers with empty cache
        assert cache.get("query:test") is None
        # Should be able to write new data after recovery
        cache.put("query:test", _make_jobs(1))
        result = cache.get("query:test")
        assert result is not None

    def test_empty_file_recovers(self, cache_path):
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text("", encoding="utf-8")
        cache = ScanCache(path=cache_path)
        assert cache.get("query:test") is None
        cache.put("query:test", _make_jobs(1))
        assert cache.get("query:test") is not None

    def test_non_dict_root_recovers(self, cache_path):
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text('["not", "a", "dict"]', encoding="utf-8")
        cache = ScanCache(path=cache_path)
        assert cache.get("query:test") is None

    def test_missing_last_scan_treated_as_not_cached(self, cache_path):
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"query:test": {"jobs": []}}
        cache_path.write_text(json.dumps(data), encoding="utf-8")
        cache = ScanCache(path=cache_path)
        assert cache.get("query:test") is None
        assert cache.is_fresh("query:test") is False

    def test_malformed_job_entries_skipped(self, cache, cache_path):
        """Bad job entries are silently skipped, good ones are kept."""
        cache.put("query:test", _make_jobs(2))
        # Inject a bad entry
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        data["query:test"]["jobs"].append("not a dict")
        data["query:test"]["jobs"].append(42)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        fresh_cache = ScanCache(path=cache_path)
        result = fresh_cache.get("query:test")
        assert result is not None
        jobs, _ = result
        assert len(jobs) == 2  # bad entries skipped


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------


class TestClear:
    def test_clear_removes_file(self, cache, cache_path):
        cache.put("query:test", _make_jobs(1))
        assert cache_path.exists()
        cache.clear()
        assert not cache_path.exists()

    def test_clear_resets_memory(self, cache):
        cache.put("query:test", _make_jobs(1))
        assert cache.get("query:test") is not None
        cache.clear()
        assert cache.get("query:test") is None


# ---------------------------------------------------------------------------
# Concurrent read/write safety
# ---------------------------------------------------------------------------


class TestConcurrency:
    def test_parallel_writes_no_crash(self, cache_path):
        """Multiple threads writing simultaneously should not corrupt or crash."""
        errors = []

        def worker(source_id):
            try:
                c = ScanCache(path=cache_path)
                jobs = _make_jobs(2)
                c.put(f"query:worker-{source_id}", jobs)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        # Verify file is valid JSON after concurrent writes
        final_cache = ScanCache(path=cache_path)
        data = final_cache._load()
        assert isinstance(data, dict)

    def test_read_during_write_no_crash(self, cache_path):
        """Reading while another thread writes should not crash."""
        cache = ScanCache(path=cache_path)
        cache.put("query:seed", _make_jobs(1))
        errors = []

        def writer():
            try:
                c = ScanCache(path=cache_path)
                for i in range(10):
                    c.put(f"query:w-{i}", _make_jobs(1))
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                c = ScanCache(path=cache_path)
                for _ in range(10):
                    c.get("query:seed")
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0
