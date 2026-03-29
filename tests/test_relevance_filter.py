"""Tests for filter_relevant_jobs() — title-based accept/reject logic.

Layer 1 tests use monkeypatching to skip the AI deep-check for uncertain jobs.
"""

import pytest
from unittest.mock import patch
from job_hunter.jobs.scraper import JobListing
from job_hunter.jobs.relevance_filter import (
    filter_relevant_jobs,
    DEFAULT_SENIORITY_KEYWORDS,
)
from job_hunter.jobs.search_strategy import SENIORITY_REJECT_FULL, SENIORITY_REJECT_EXPERIENCED


def make_job(title: str, company: str = "Acme") -> JobListing:
    return JobListing(title=title, company=company, location="Israel", url="http://example.com")


# ---------------------------------------------------------------------------
# Accept cases
# ---------------------------------------------------------------------------

def test_accept_python_developer():
    accepted, rejected = filter_relevant_jobs([make_job("Python Developer")])
    assert len(accepted) == 1
    assert len(rejected) == 0


def test_accept_rf_engineer():
    accepted, rejected = filter_relevant_jobs([make_job("RF Engineer")])
    assert len(accepted) == 1
    assert len(rejected) == 0


def test_accept_machine_learning_researcher():
    accepted, rejected = filter_relevant_jobs([make_job("Machine Learning Researcher")])
    assert len(accepted) == 1
    assert len(rejected) == 0


def test_accept_embedded_software_engineer():
    accepted, rejected = filter_relevant_jobs([make_job("Embedded Software Engineer")])
    assert len(accepted) == 1
    assert len(rejected) == 0


def test_accept_dsp_algorithm_engineer():
    accepted, rejected = filter_relevant_jobs([make_job("DSP Algorithm Engineer")])
    assert len(accepted) == 1
    assert len(rejected) == 0


# ---------------------------------------------------------------------------
# Reject cases
# ---------------------------------------------------------------------------

def test_reject_marketing_manager():
    accepted, rejected = filter_relevant_jobs([make_job("Marketing Manager")])
    assert len(accepted) == 0
    assert len(rejected) == 1


def test_reject_accountant():
    accepted, rejected = filter_relevant_jobs([make_job("Accountant")])
    assert len(accepted) == 0
    assert len(rejected) == 1


def test_reject_mechanical_engineer():
    accepted, rejected = filter_relevant_jobs([make_job("Mechanical Engineer")])
    assert len(accepted) == 0
    assert len(rejected) == 1


def test_reject_unrelated_title():
    """Title with no relevant or irrelevant keyword — falls through to reject."""
    accepted, rejected = filter_relevant_jobs([make_job("Chef")])
    assert len(accepted) == 0
    assert len(rejected) == 1


def test_reject_blacklisted_company():
    """Company name in IRRELEVANT_COMPANIES — rejected regardless of title."""
    accepted, rejected = filter_relevant_jobs(
        [make_job("Software Engineer", company="Teva")]
    )
    assert len(accepted) == 0
    assert len(rejected) == 1


def test_reject_writing_intern():
    """'Writing Intern' should be caught by expanded PROFESSIONAL_FIELDS."""
    accepted, rejected = filter_relevant_jobs([make_job("Writing Intern – Hebrew")])
    assert len(accepted) == 0
    assert len(rejected) == 1


def test_reject_editor_intern():
    """'Editor Intern' should be caught by PROFESSIONAL_FIELDS."""
    accepted, rejected = filter_relevant_jobs([make_job("Editor Intern")])
    assert len(accepted) == 0
    assert len(rejected) == 1


def test_reject_teaching_assistant():
    """'Teaching Assistant' should be caught by PROFESSIONAL_FIELDS."""
    accepted, rejected = filter_relevant_jobs([make_job("Teaching Assistant")])
    assert len(accepted) == 0
    assert len(rejected) == 1


# ---------------------------------------------------------------------------
# Uncertain jobs — AI deep-check with mocked API
# ---------------------------------------------------------------------------

def test_uncertain_job_accepted_by_ai():
    """Job with 'intern' but no keyword signal → AI scores high → accepted."""
    job = make_job("Operations Intern")
    with patch("job_hunter.jobs.relevance_filter.fetch_job_description", return_value="Some description"), \
         patch("job_hunter.jobs.relevance_filter.score_job_fit", return_value=(70, "related field")):
        accepted, rejected = filter_relevant_jobs([job])
    assert len(accepted) == 1
    assert len(rejected) == 0


def test_uncertain_job_rejected_by_ai():
    """Job with 'intern' but no keyword signal → AI scores low → rejected."""
    job = make_job("Operations Intern")
    with patch("job_hunter.jobs.relevance_filter.fetch_job_description", return_value="Some description"), \
         patch("job_hunter.jobs.relevance_filter.score_job_fit", return_value=(20, "unrelated field")):
        accepted, rejected = filter_relevant_jobs([job])
    assert len(accepted) == 0
    assert len(rejected) == 1


def test_uncertain_job_accepted_on_api_failure():
    """AI scoring fails → benefit of doubt → accepted with warning."""
    job = make_job("Operations Intern")
    with patch("job_hunter.jobs.relevance_filter.fetch_job_description", return_value="Some description"), \
         patch("job_hunter.jobs.relevance_filter.score_job_fit", return_value=None):
        accepted, rejected = filter_relevant_jobs([job])
    assert len(accepted) == 1
    assert len(rejected) == 0


def test_uncertain_job_accepted_on_no_description():
    """No description fetched → benefit of doubt → accepted with warning."""
    job = make_job("Operations Intern")
    with patch("job_hunter.jobs.relevance_filter.fetch_job_description", return_value=None):
        accepted, rejected = filter_relevant_jobs([job])
    assert len(accepted) == 1
    assert len(rejected) == 0


# ---------------------------------------------------------------------------
# Seniority reject — configurable via SearchConfig
# ---------------------------------------------------------------------------

class TestSeniorityReject:
    """Test that seniority_reject param controls which titles are rejected."""

    def test_no_param_uses_default_full_list(self):
        """No seniority_reject passed → uses DEFAULT_SENIORITY_KEYWORDS (rejects senior)."""
        job = make_job("Senior Software Engineer Student")
        accepted, rejected = filter_relevant_jobs([job])
        assert len(rejected) == 1
        assert len(accepted) == 0

    def test_student_config_rejects_senior(self):
        """Student config (full list) rejects 'Senior' titles."""
        job = make_job("Senior Software Engineer Student")
        accepted, rejected = filter_relevant_jobs(
            [job], seniority_reject=list(SENIORITY_REJECT_FULL),
        )
        assert len(rejected) == 1

    def test_student_config_rejects_director(self):
        """Student config rejects 'Director' titles."""
        job = make_job("Director of Engineering")
        accepted, rejected = filter_relevant_jobs(
            [job], seniority_reject=list(SENIORITY_REJECT_FULL),
        )
        assert len(rejected) == 1

    def test_student_config_rejects_vp(self):
        """Student config rejects 'VP' titles."""
        job = make_job("VP Engineering")
        accepted, rejected = filter_relevant_jobs(
            [job], seniority_reject=list(SENIORITY_REJECT_FULL),
        )
        assert len(rejected) == 1

    def test_experienced_config_allows_senior(self):
        """Experienced config (reduced list) does NOT reject 'Senior'."""
        job = make_job("Senior Software Engineer Student")
        accepted, rejected = filter_relevant_jobs(
            [job], seniority_reject=list(SENIORITY_REJECT_EXPERIENCED),
        )
        # "senior" is not in the experienced reject list, so it should NOT
        # be rejected by seniority. It may still be accepted/rejected by
        # other rules (keyword match, etc.)
        seniority_rejected = any(
            "senior" in r.title.lower() for r in rejected
            if not any(kw in r.title.lower() for kw in ["marketing", "mechanical"])
        )
        assert not seniority_rejected

    def test_experienced_config_rejects_director(self):
        """Experienced config still rejects 'Director'."""
        job = make_job("Director of Engineering")
        accepted, rejected = filter_relevant_jobs(
            [job], seniority_reject=list(SENIORITY_REJECT_EXPERIENCED),
        )
        assert len(rejected) == 1

    def test_experienced_config_rejects_vp(self):
        """Experienced config still rejects 'VP'."""
        job = make_job("VP Engineering")
        accepted, rejected = filter_relevant_jobs(
            [job], seniority_reject=list(SENIORITY_REJECT_EXPERIENCED),
        )
        assert len(rejected) == 1

    def test_experienced_config_rejects_chief(self):
        """Experienced config still rejects 'Chief'."""
        job = make_job("Chief Technology Officer")
        accepted, rejected = filter_relevant_jobs(
            [job], seniority_reject=list(SENIORITY_REJECT_EXPERIENCED),
        )
        assert len(rejected) == 1

    def test_empty_seniority_reject_allows_all(self):
        """Empty seniority_reject list → no seniority filtering at all."""
        jobs = [
            make_job("Senior Software Engineer Student"),
            make_job("Director of Engineering"),
            make_job("VP Engineering"),
        ]
        accepted, rejected = filter_relevant_jobs(jobs, seniority_reject=[])
        # None should be rejected by seniority (though they may be rejected
        # by other rules like missing keywords)
        senior_titles = {"senior software engineer student", "director of engineering", "vp engineering"}
        # At minimum, the senior one has "software" + "student" which matches keywords
        senior_job_accepted = any(
            "senior software" in j.title.lower() for j in accepted
        )
        assert senior_job_accepted

    def test_default_constant_matches_search_strategy_full(self):
        """DEFAULT_SENIORITY_KEYWORDS should match SENIORITY_REJECT_FULL."""
        assert DEFAULT_SENIORITY_KEYWORDS == list(SENIORITY_REJECT_FULL)
