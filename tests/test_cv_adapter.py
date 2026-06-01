"""Tests for CVAdapter.adapt() — JSON fence stripping and API failure handling."""

import json
import pytest
from unittest.mock import MagicMock, patch
import anthropic


SAMPLE_CV = {"name": "Dvir Salomon", "title": "Electrical Engineering Student"}
SAMPLE_JOB = "We are looking for a Python developer with signal processing experience."

_FAKE_PROFILE = MagicMock(
    cv_title="Electrical Engineering Student",
    hard_rules={}, university="BGU",
    must_include_facts=[], banned_skills=[],
    is_student=True, education={"year": "3rd"},
)


@pytest.fixture(autouse=True)
def _mock_get_profile():
    """Mock get_profile for all tests so no real profile file is needed."""
    with patch("job_hunter.cv.adapter.get_profile", return_value=_FAKE_PROFILE):
        yield


def make_adapter():
    """Build a CVAdapter with all external dependencies mocked out."""
    with patch("job_hunter.cv.adapter.Config.validate"), \
         patch("job_hunter.cv.adapter.anthropic.Anthropic"):
        from job_hunter.cv.adapter import CVAdapter
        adapter = CVAdapter()
        adapter.client = MagicMock()
        return adapter


def make_response(text: str):
    """Build a fake anthropic message response with the given text."""
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


# ---------------------------------------------------------------------------
# JSON fence stripping
# ---------------------------------------------------------------------------

def test_clean_json_no_fences():
    adapter = make_adapter()
    payload = {"title": "Electrical Engineering Student", "skills": ["Python"]}
    adapter.client.messages.create.return_value = make_response(json.dumps(payload))

    result = adapter.adapt(SAMPLE_CV, SAMPLE_JOB)

    assert result == payload


def test_strips_json_code_fence():
    adapter = make_adapter()
    payload = {"title": "Electrical Engineering Student", "skills": ["Python"]}
    fenced = f"```json\n{json.dumps(payload)}\n```"
    adapter.client.messages.create.return_value = make_response(fenced)

    result = adapter.adapt(SAMPLE_CV, SAMPLE_JOB)

    assert result == payload


def test_strips_plain_code_fence():
    adapter = make_adapter()
    payload = {"title": "Electrical Engineering Student", "skills": ["MATLAB"]}
    fenced = f"```\n{json.dumps(payload)}\n```"
    adapter.client.messages.create.return_value = make_response(fenced)

    result = adapter.adapt(SAMPLE_CV, SAMPLE_JOB)

    assert result == payload


# ---------------------------------------------------------------------------
# API failure → None
# ---------------------------------------------------------------------------

def test_api_error_returns_none():
    adapter = make_adapter()
    adapter.client.messages.create.side_effect = anthropic.APIError(
        message="rate limit", request=MagicMock(), body={}
    )

    result = adapter.adapt(SAMPLE_CV, SAMPLE_JOB)

    assert result is None


# ---------------------------------------------------------------------------
# Empty/invalid response → None
# ---------------------------------------------------------------------------

def test_empty_content_returns_none():
    adapter = make_adapter()
    msg = MagicMock()
    msg.content = []
    adapter.client.messages.create.return_value = msg

    assert adapter.adapt(SAMPLE_CV, SAMPLE_JOB) is None


def test_invalid_json_response_returns_none():
    adapter = make_adapter()
    adapter.client.messages.create.return_value = make_response("not valid json at all")

    assert adapter.adapt(SAMPLE_CV, SAMPLE_JOB) is None


def test_empty_content_in_adapt_with_requirements_returns_none():
    adapter = make_adapter()
    msg = MagicMock()
    msg.content = []
    adapter.client.messages.create.return_value = msg

    from job_hunter.jobs.analyzer import JobRequirements
    reqs = JobRequirements(
        title="Python Dev", company="Acme", domain="software",
        role_summary="Build stuff", required_skills=["Python"],
        preferred_skills=[], key_technologies=[], education="BSc",
        experience_level="junior", location="Israel"
    )

    with patch("job_hunter.cv.adapter.get_profile") as mock_profile:
        mock_profile.return_value = MagicMock(
            cv_title="Electrical Engineering Student",
            hard_rules={}, university="BGU",
        )
        assert adapter.adapt_with_requirements(SAMPLE_CV, reqs) is None


def test_empty_content_in_generate_cover_letter_returns_none():
    adapter = make_adapter()
    msg = MagicMock()
    msg.content = []
    adapter.client.messages.create.return_value = msg

    assert adapter.generate_cover_letter(SAMPLE_CV, SAMPLE_JOB, "Acme") is None
