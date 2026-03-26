"""Tests for filter_relevant_jobs() — title-based accept/reject logic.

We use deep_check=False to avoid any API/network calls.
"""

import pytest
from job_hunter.jobs.scraper import JobListing
from job_hunter.jobs.relevance_filter import filter_relevant_jobs


def make_job(title: str, company: str = "Acme") -> JobListing:
    return JobListing(title=title, company=company, location="Israel", url="http://example.com")


# ---------------------------------------------------------------------------
# Accept cases
# ---------------------------------------------------------------------------

def test_accept_python_developer():
    accepted, rejected = filter_relevant_jobs([make_job("Python Developer")], deep_check=False)
    assert len(accepted) == 1
    assert len(rejected) == 0


def test_accept_rf_engineer():
    accepted, rejected = filter_relevant_jobs([make_job("RF Engineer")], deep_check=False)
    assert len(accepted) == 1
    assert len(rejected) == 0


def test_accept_machine_learning_researcher():
    accepted, rejected = filter_relevant_jobs([make_job("Machine Learning Researcher")], deep_check=False)
    assert len(accepted) == 1
    assert len(rejected) == 0


def test_accept_embedded_software_engineer():
    accepted, rejected = filter_relevant_jobs([make_job("Embedded Software Engineer")], deep_check=False)
    assert len(accepted) == 1
    assert len(rejected) == 0


def test_accept_dsp_algorithm_engineer():
    accepted, rejected = filter_relevant_jobs([make_job("DSP Algorithm Engineer")], deep_check=False)
    assert len(accepted) == 1
    assert len(rejected) == 0


# ---------------------------------------------------------------------------
# Reject cases
# ---------------------------------------------------------------------------

def test_reject_marketing_manager():
    accepted, rejected = filter_relevant_jobs([make_job("Marketing Manager")], deep_check=False)
    assert len(accepted) == 0
    assert len(rejected) == 1


def test_reject_accountant():
    accepted, rejected = filter_relevant_jobs([make_job("Accountant")], deep_check=False)
    assert len(accepted) == 0
    assert len(rejected) == 1


def test_reject_mechanical_engineer():
    accepted, rejected = filter_relevant_jobs([make_job("Mechanical Engineer")], deep_check=False)
    assert len(accepted) == 0
    assert len(rejected) == 1


def test_reject_unrelated_title():
    """Title with no relevant or irrelevant keyword — falls through to reject."""
    accepted, rejected = filter_relevant_jobs([make_job("Chef")], deep_check=False)
    assert len(accepted) == 0
    assert len(rejected) == 1


def test_reject_blacklisted_company():
    """Company name in IRRELEVANT_COMPANIES — rejected regardless of title."""
    accepted, rejected = filter_relevant_jobs(
        [make_job("Software Engineer", company="Teva")], deep_check=False
    )
    assert len(accepted) == 0
    assert len(rejected) == 1
