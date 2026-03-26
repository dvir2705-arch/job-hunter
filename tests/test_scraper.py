"""Tests for JobSpyScraper — verifies List[JobListing] output, filtering, and error handling.

All tests mock jobspy.scrape_jobs to avoid real network calls.
"""

from unittest.mock import patch, MagicMock
import pandas as pd
import pytest

from job_hunter.jobs.scraper import JobSpyScraper, JobListing


def make_df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal DataFrame that scrape_jobs would return."""
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Normal result
# ---------------------------------------------------------------------------

def test_returns_list_of_job_listings():
    df = make_df([
        {"title": "Python Developer", "company": "Acme", "location": "Israel",
         "job_url": "https://example.com/1", "date_posted": "2026-03-01"},
        {"title": "RF Engineer", "company": "Intel", "location": "Haifa",
         "job_url": "https://example.com/2", "date_posted": "2026-03-02"},
    ])
    with patch("jobspy.scrape_jobs", return_value=df):
        results = JobSpyScraper().search("student", max_results=10)

    assert isinstance(results, list)
    assert len(results) == 2
    assert all(isinstance(j, JobListing) for j in results)
    assert results[0].title == "Python Developer"
    assert results[0].company == "Acme"
    assert results[1].url == "https://example.com/2"


# ---------------------------------------------------------------------------
# Row filtering — missing title or url
# ---------------------------------------------------------------------------

def test_rows_missing_title_are_dropped():
    df = make_df([
        {"title": None, "company": "Acme", "location": "Israel",
         "job_url": "https://example.com/1", "date_posted": ""},
        {"title": "DSP Engineer", "company": "NVIDIA", "location": "Israel",
         "job_url": "https://example.com/2", "date_posted": ""},
    ])
    with patch("jobspy.scrape_jobs", return_value=df):
        results = JobSpyScraper().search("student")

    assert len(results) == 1
    assert results[0].title == "DSP Engineer"


def test_rows_missing_url_are_dropped():
    df = make_df([
        {"title": "Software Engineer", "company": "Acme", "location": "Israel",
         "job_url": None, "date_posted": ""},
        {"title": "Embedded Engineer", "company": "Marvell", "location": "Israel",
         "job_url": "https://example.com/2", "date_posted": ""},
    ])
    with patch("jobspy.scrape_jobs", return_value=df):
        results = JobSpyScraper().search("student")

    assert len(results) == 1
    assert results[0].title == "Embedded Engineer"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_scrape_exception_returns_empty():
    with patch("jobspy.scrape_jobs", side_effect=Exception("network error")):
        results = JobSpyScraper().search("student")
    assert results == []


def test_import_error_returns_empty():
    """Simulates python-jobspy not being installed."""
    with patch.dict("sys.modules", {"jobspy": None}):
        results = JobSpyScraper().search("student")
    assert results == []


# ---------------------------------------------------------------------------
# max_results respected
# ---------------------------------------------------------------------------

def test_max_results_passed_to_library():
    """max_results is forwarded to scrape_jobs as results_wanted — the library limits the count."""
    df = make_df([
        {"title": "Job 0", "company": "Acme", "location": "Israel",
         "job_url": "https://example.com/0", "date_posted": ""}
    ])
    with patch("jobspy.scrape_jobs", return_value=df) as mock_scrape:
        JobSpyScraper().search("student", max_results=3)

    mock_scrape.assert_called_once()
    _, kwargs = mock_scrape.call_args
    assert kwargs["results_wanted"] == 3
