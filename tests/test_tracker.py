"""Tests for ApplicationTracker — load/save, malformed JSON recovery, status transitions."""

import json

import pytest

from job_hunter.applications.models import Application
from job_hunter.applications.tracker import ApplicationTracker


def make_app(**kwargs) -> Application:
    defaults = dict(job_title="Software Engineer", company="Acme")
    defaults.update(kwargs)
    return Application(**defaults)


# ---------------------------------------------------------------------------
# Load / save round-trip
# ---------------------------------------------------------------------------


def test_load_save_roundtrip(tmp_path):
    filepath = tmp_path / "apps.json"
    tracker = ApplicationTracker(filepath=filepath)
    app = make_app(job_title="DSP Engineer", company="Intel")
    tracker.add(app)

    tracker2 = ApplicationTracker(filepath=filepath)
    assert len(tracker2.applications) == 1
    assert tracker2.applications[0].job_title == "DSP Engineer"
    assert tracker2.applications[0].company == "Intel"
    assert tracker2.applications[0].id == app.id


def test_load_missing_file_returns_empty(tmp_path):
    filepath = tmp_path / "nonexistent.json"
    tracker = ApplicationTracker(filepath=filepath)
    assert tracker.applications == []


# ---------------------------------------------------------------------------
# Malformed JSON recovery
# ---------------------------------------------------------------------------


def test_corrupted_json_returns_empty(tmp_path):
    filepath = tmp_path / "apps.json"
    filepath.write_text("{ not valid json }", encoding="utf-8")

    tracker = ApplicationTracker(filepath=filepath)
    assert tracker.applications == []


def test_malformed_record_is_skipped(tmp_path):
    """One bad record in the list — it's skipped, the valid record still loads."""
    filepath = tmp_path / "apps.json"
    good = make_app(job_title="RF Engineer", company="NVIDIA").to_dict()
    bad = {"broken": True}  # missing required fields
    filepath.write_text(
        json.dumps({"applications": [bad, good]}),
        encoding="utf-8",
    )

    tracker = ApplicationTracker(filepath=filepath)
    assert len(tracker.applications) == 1
    assert tracker.applications[0].job_title == "RF Engineer"


# ---------------------------------------------------------------------------
# update_status — valid and invalid transitions
# ---------------------------------------------------------------------------


def test_update_status_valid_transition(tmp_path):
    filepath = tmp_path / "apps.json"
    tracker = ApplicationTracker(filepath=filepath)
    app = make_app()
    tracker.add(app)

    updated = tracker.update_status(app.id, "screening")
    assert updated.status == "screening"


def test_update_status_invalid_transition_raises(tmp_path):
    filepath = tmp_path / "apps.json"
    tracker = ApplicationTracker(filepath=filepath)
    app = make_app()
    tracker.add(app)
    tracker.update_status(app.id, "rejected")  # valid: applied → rejected

    with pytest.raises(ValueError):
        tracker.update_status(app.id, "offer")  # invalid: rejected → offer


# ---------------------------------------------------------------------------
# get_needing_follow_up
# ---------------------------------------------------------------------------


def test_get_needing_follow_up(tmp_path):
    filepath = tmp_path / "apps.json"
    tracker = ApplicationTracker(filepath=filepath)

    overdue = make_app(job_title="Overdue Job")
    overdue.follow_up_date = "2020-01-01"
    tracker.add(overdue)

    not_due = make_app(job_title="Not Due Job")
    not_due.follow_up_date = "2099-01-01"
    tracker.add(not_due)

    needs = tracker.get_needing_follow_up()
    assert len(needs) == 1
    assert needs[0].job_title == "Overdue Job"
