"""Tests for JobSpyScraper — verifies List[JobListing] output, filtering, and error handling.

All tests mock jobspy.scrape_jobs to avoid real network calls.
"""

from unittest.mock import MagicMock, patch

import pandas as pd

from job_hunter.jobs.scraper import JobListing, JobSpyScraper


def make_df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal DataFrame that scrape_jobs would return."""
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Normal result
# ---------------------------------------------------------------------------


def test_returns_list_of_job_listings():
    df = make_df(
        [
            {
                "title": "Python Developer",
                "company": "Acme",
                "location": "Israel",
                "job_url": "https://example.com/1",
                "date_posted": "2026-03-01",
            },
            {
                "title": "RF Engineer",
                "company": "Intel",
                "location": "Haifa, Israel",
                "job_url": "https://example.com/2",
                "date_posted": "2026-03-02",
            },
        ]
    )
    with patch("jobspy.scrape_jobs", return_value=df):
        results = JobSpyScraper().search("student", max_results=10)

    assert isinstance(results, list)
    assert len(results) == 2
    assert all(isinstance(j, JobListing) for j in results)
    assert results[0].title == "Python Developer"
    assert results[0].company == "Acme"
    assert results[1].url == "https://example.com/2"


# ---------------------------------------------------------------------------
# Location filtering — off-country jobs must be dropped
# ---------------------------------------------------------------------------


def test_off_country_jobs_are_filtered_out():
    """JobSpy often returns US/remote results even when location='Israel'.
    The scraper must drop anything whose location doesn't match the country.
    """
    df = make_df(
        [
            {
                "title": "SW Engineer",
                "company": "Acme",
                "location": "Tel Aviv, Israel",
                "job_url": "https://example.com/1",
                "date_posted": "",
            },
            {
                "title": "SW Engineer",
                "company": "Acme",
                "location": "San Francisco, CA",
                "job_url": "https://example.com/2",
                "date_posted": "",
            },
            {
                "title": "SW Engineer",
                "company": "Acme",
                "location": "Remote",
                "job_url": "https://example.com/3",
                "date_posted": "",
            },
            {
                "title": "SW Engineer",
                "company": "Acme",
                "location": "",
                "job_url": "https://example.com/4",
                "date_posted": "",
            },
        ]
    )
    with patch("jobspy.scrape_jobs", return_value=df):
        results = JobSpyScraper().search("student", location="Israel")

    assert len(results) == 1
    assert results[0].location == "Tel Aviv, Israel"


def test_israeli_cities_without_country_suffix_are_kept():
    """LinkedIn/Indeed often return Israeli jobs as just 'Tel Aviv' or 'IL, Haifa'
    without the word 'Israel'. The country-aware matcher must keep these.
    """
    df = make_df(
        [
            {
                "title": "Backend",
                "company": "Startup A",
                "location": "Tel Aviv",
                "job_url": "https://example.com/1",
                "date_posted": "",
            },
            {
                "title": "Backend",
                "company": "Startup B",
                "location": "Herzliya",
                "job_url": "https://example.com/2",
                "date_posted": "",
            },
            {
                "title": "Backend",
                "company": "Amazon",
                "location": "IL, Haifa",
                "job_url": "https://example.com/3",
                "date_posted": "",
            },
            {
                "title": "Backend",
                "company": "Startup C",
                "location": "Ra'anana",
                "job_url": "https://example.com/4",
                "date_posted": "",
            },
            {
                "title": "Backend",
                "company": "US Co",
                "location": "Austin, TX",
                "job_url": "https://example.com/5",
                "date_posted": "",
            },
        ]
    )
    with patch("jobspy.scrape_jobs", return_value=df):
        results = JobSpyScraper().search("student", location="Israel")

    locations = [j.location for j in results]
    assert "Tel Aviv" in locations
    assert "Herzliya" in locations
    assert "IL, Haifa" in locations  # matched via "haifa" alias
    assert "Ra'anana" in locations
    assert "Austin, TX" not in locations


def test_empty_location_but_city_in_title_is_kept():
    """Regression: JobSpy sometimes returns Israeli postings with an empty
    location field — the city appears only in the title (e.g. Apple's
    'Verification Student- Jerusalem'). These must not be rejected.
    """
    df = make_df(
        [
            {
                "title": "Verification Student- Jerusalem",
                "company": "Apple",
                "location": "",
                "job_url": "https://example.com/apple-jlm",
                "date_posted": "",
            },
            {
                "title": "Intern Opportunities at Apple (international students)",
                "company": "Apple",
                "location": "",
                "job_url": "https://example.com/apple-global",
                "date_posted": "",
            },
            {
                "title": "Software Engineering Intern",
                "company": "Apple",
                "location": "Shanghai, China",
                "job_url": "https://example.com/apple-sh",
                "date_posted": "",
            },
        ]
    )
    with patch("jobspy.scrape_jobs", return_value=df):
        results = JobSpyScraper().search("Apple student", location="Israel")

    titles = [j.title for j in results]
    assert "Verification Student- Jerusalem" in titles
    assert "Intern Opportunities at Apple (international students)" not in titles
    assert "Software Engineering Intern" not in titles


def test_illinois_state_code_is_not_matched_as_israel():
    """Regression: 'Chicago, IL' must NOT match Israel — 'IL' is the US state
    code for Illinois and we previously accepted it as the Israel country code.
    """
    df = make_df(
        [
            {
                "title": "SWE Intern",
                "company": "US Hedge Fund",
                "location": "Chicago, IL",
                "job_url": "https://example.com/chicago",
                "date_posted": "",
            },
            {
                "title": "SWE Intern",
                "company": "Israeli Startup",
                "location": "Tel Aviv, Israel",
                "job_url": "https://example.com/tlv",
                "date_posted": "",
            },
        ]
    )
    with patch("jobspy.scrape_jobs", return_value=df):
        results = JobSpyScraper().search("student", location="Israel")

    locations = [j.location for j in results]
    assert "Tel Aviv, Israel" in locations
    assert "Chicago, IL" not in locations


def test_empty_location_disables_filter():
    """Passing location='' should behave like the old (unfiltered) scraper."""
    df = make_df(
        [
            {
                "title": "SW",
                "company": "A",
                "location": "Tel Aviv, Israel",
                "job_url": "https://example.com/1",
                "date_posted": "",
            },
            {
                "title": "SW",
                "company": "A",
                "location": "San Francisco, CA",
                "job_url": "https://example.com/2",
                "date_posted": "",
            },
        ]
    )
    with patch("jobspy.scrape_jobs", return_value=df):
        results = JobSpyScraper().search("student", location="")

    assert len(results) == 2


# ---------------------------------------------------------------------------
# Row filtering — missing title or url
# ---------------------------------------------------------------------------


def test_rows_missing_title_are_dropped():
    df = make_df(
        [
            {
                "title": None,
                "company": "Acme",
                "location": "Israel",
                "job_url": "https://example.com/1",
                "date_posted": "",
            },
            {
                "title": "DSP Engineer",
                "company": "NVIDIA",
                "location": "Israel",
                "job_url": "https://example.com/2",
                "date_posted": "",
            },
        ]
    )
    with patch("jobspy.scrape_jobs", return_value=df):
        results = JobSpyScraper().search("student")

    assert len(results) == 1
    assert results[0].title == "DSP Engineer"


def test_rows_missing_url_are_dropped():
    df = make_df(
        [
            {
                "title": "Software Engineer",
                "company": "Acme",
                "location": "Israel",
                "job_url": None,
                "date_posted": "",
            },
            {
                "title": "Embedded Engineer",
                "company": "Marvell",
                "location": "Israel",
                "job_url": "https://example.com/2",
                "date_posted": "",
            },
        ]
    )
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
    df = make_df(
        [
            {
                "title": "Job 0",
                "company": "Acme",
                "location": "Israel",
                "job_url": "https://example.com/0",
                "date_posted": "",
            }
        ]
    )
    with patch("jobspy.scrape_jobs", return_value=df) as mock_scrape:
        JobSpyScraper().search("student", max_results=3)

    mock_scrape.assert_called_once()
    _, kwargs = mock_scrape.call_args
    assert kwargs["results_wanted"] == 3


def test_jobspy_sends_country_indeed_for_israel():
    """Indeed's country_indeed param is what actually restricts results to a country.
    Without it, Indeed returns worldwide results even with location='Israel'.
    """
    df = make_df([])
    with patch("jobspy.scrape_jobs", return_value=df) as mock_scrape:
        JobSpyScraper().search("student", location="Israel")

    _, kwargs = mock_scrape.call_args
    assert kwargs.get("country_indeed") == "israel"


def test_jobspy_country_indeed_absent_for_unknown_country():
    """Unknown country strings must not override jobspy's default country_indeed."""
    df = make_df([])
    with patch("jobspy.scrape_jobs", return_value=df) as mock_scrape:
        JobSpyScraper().search("student", location="Madagascar")

    _, kwargs = mock_scrape.call_args
    assert "country_indeed" not in kwargs


def test_jobspy_extracts_country_from_city_suffix():
    """When location is 'Tel Aviv, Israel' (per-city scan), extract 'israel' as country."""
    df = make_df([])
    with patch("jobspy.scrape_jobs", return_value=df) as mock_scrape:
        JobSpyScraper().search("student", location="Tel Aviv, Israel")

    _, kwargs = mock_scrape.call_args
    assert kwargs.get("country_indeed") == "israel"


def test_linkedin_attaches_geoid_for_israel():
    """LinkedInScraper must pass the Israel geoId (101620260) when location is Israel.
    Without geoId, LinkedIn's guest search returns worldwide top 25.
    """
    from job_hunter.jobs.scraper import LinkedInScraper

    captured = {}

    class _FakeResponse:
        url = "https://www.linkedin.com/jobs/search/"
        text = "<html><body></body></html>"
        status_code = 200

        def raise_for_status(self):
            pass

    with patch(
        "requests.request",
        side_effect=lambda method, url, **kw: (
            captured.update({"params": kw.get("params")}),
            _FakeResponse(),
        )[1],
    ):
        try:
            LinkedInScraper().search("student", location="Israel")
        except RuntimeError:
            # No job cards in fake HTML — raises, but we only care about params
            pass

    assert captured["params"]["geoId"] == "101620260"
    assert captured["params"]["location"] == "Israel"
    assert captured["params"]["keywords"] == "student"


def test_indeed_rows_are_trusted_when_country_indeed_set():
    """When country_indeed='israel' is passed, Indeed's server-side filter
    guarantees Israeli results. Indeed returns Hebrew location strings
    ('חיפה, HA, IL') that our alias list doesn't recognize, so we must NOT
    re-filter those rows client-side. LinkedIn rows still get filtered.
    """
    df = make_df(
        [
            {
                "title": "Israeli Job (Hebrew loc)",
                "company": "Intel",
                "site": "indeed",
                "location": "חיפה, HA, IL",
                "job_url": "https://example.com/indeed-he",
                "date_posted": "",
            },
            {
                "title": "Israeli Job (country code)",
                "company": "Gov.il",
                "site": "indeed",
                "location": "IL",
                "job_url": "https://example.com/indeed-il",
                "date_posted": "",
            },
            {
                "title": "US Job from LinkedIn",
                "company": "US Co",
                "site": "linkedin",
                "location": "San Francisco, CA",
                "job_url": "https://example.com/sf",
                "date_posted": "",
            },
            {
                "title": "Israeli Job from LinkedIn",
                "company": "Wix",
                "site": "linkedin",
                "location": "Tel Aviv, Israel",
                "job_url": "https://example.com/tlv-li",
                "date_posted": "",
            },
        ]
    )
    with patch("jobspy.scrape_jobs", return_value=df):
        results = JobSpyScraper().search("student", location="Israel")

    titles = [j.title for j in results]
    # Indeed rows trusted even with non-matching Hebrew/bare-IL locations
    assert "Israeli Job (Hebrew loc)" in titles
    assert "Israeli Job (country code)" in titles
    # LinkedIn rows still filtered
    assert "Israeli Job from LinkedIn" in titles
    assert "US Job from LinkedIn" not in titles


def test_indeed_rows_are_filtered_when_no_country_indeed():
    """Unknown country → country_indeed not set → don't trust Indeed either."""
    df = make_df(
        [
            {
                "title": "Hebrew Loc Job",
                "company": "Intel",
                "site": "indeed",
                "location": "חיפה, HA, IL",
                "job_url": "https://example.com/1",
                "date_posted": "",
            },
        ]
    )
    with patch("jobspy.scrape_jobs", return_value=df):
        results = JobSpyScraper().search("student", location="Madagascar")

    # Without country_indeed, we can't trust the site — Hebrew loc doesn't
    # match "Madagascar" so it should be filtered out.
    assert len(results) == 0


def test_linkedin_no_geoid_for_unknown_country():
    """Unknown country → geoId not sent (LinkedIn falls back to keyword search)."""
    captured = {}

    class _FakeResponse:
        url = "https://www.linkedin.com/jobs/search/"
        text = "<html><body></body></html>"
        status_code = 200

        def raise_for_status(self):
            pass

    from job_hunter.jobs.scraper import LinkedInScraper

    with patch(
        "requests.request",
        side_effect=lambda method, url, **kw: (
            captured.update({"params": kw.get("params")}),
            _FakeResponse(),
        )[1],
    ):
        try:
            LinkedInScraper().search("student", location="Madagascar")
        except RuntimeError:
            pass

    assert "geoId" not in captured["params"]


# ---------------------------------------------------------------------------
# Exponential backoff with jitter
# ---------------------------------------------------------------------------


def test_backoff_retries_on_429():
    """_request_with_backoff retries on 429 and succeeds when server recovers."""
    from job_hunter.jobs.scraper import _request_with_backoff

    call_count = 0

    def fake_request(method, url, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        resp.status_code = 429 if call_count < 3 else 200
        return resp

    with patch("requests.request", side_effect=fake_request), patch("time.sleep"):
        result = _request_with_backoff("get", "https://example.com", max_retries=3)

    assert result.status_code == 200
    assert call_count == 3


def test_backoff_retries_on_503():
    """_request_with_backoff retries on 503."""
    from job_hunter.jobs.scraper import _request_with_backoff

    call_count = 0

    def fake_request(method, url, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        resp.status_code = 503 if call_count == 1 else 200
        return resp

    with patch("requests.request", side_effect=fake_request), patch("time.sleep"):
        result = _request_with_backoff("get", "https://example.com")

    assert result.status_code == 200
    assert call_count == 2


def test_backoff_gives_up_after_max_retries():
    """After max_retries, the last 429/503 response is returned."""
    from job_hunter.jobs.scraper import _request_with_backoff

    def fake_request(method, url, **kwargs):
        resp = MagicMock()
        resp.status_code = 429
        return resp

    with patch("requests.request", side_effect=fake_request), patch("time.sleep"):
        result = _request_with_backoff("get", "https://example.com", max_retries=2)

    assert result.status_code == 429


def test_backoff_no_retry_on_success():
    """200 responses are returned immediately without retrying."""
    from job_hunter.jobs.scraper import _request_with_backoff

    def fake_request(method, url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        return resp

    with patch("requests.request", side_effect=fake_request) as mock_req:
        result = _request_with_backoff("get", "https://example.com")

    assert result.status_code == 200
    assert mock_req.call_count == 1


def test_backoff_no_retry_on_client_error():
    """Non-retryable errors like 404 are returned immediately."""
    from job_hunter.jobs.scraper import _request_with_backoff

    def fake_request(method, url, **kwargs):
        resp = MagicMock()
        resp.status_code = 404
        return resp

    with patch("requests.request", side_effect=fake_request) as mock_req:
        result = _request_with_backoff("get", "https://example.com")

    assert result.status_code == 404
    assert mock_req.call_count == 1
