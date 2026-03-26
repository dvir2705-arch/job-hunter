"""Tests for Application model — auto-init, status transitions, follow-up logic."""

from job_hunter.applications.models import Application, VALID_TRANSITIONS


def make_app(**kwargs) -> Application:
    defaults = dict(job_title="Software Engineer", company="Acme")
    defaults.update(kwargs)
    return Application(**defaults)


# ---------------------------------------------------------------------------
# Auto-init
# ---------------------------------------------------------------------------

def test_auto_id_assigned():
    app = make_app()
    assert app.id != ""
    assert len(app.id) == 8


def test_auto_dates_assigned():
    app = make_app()
    assert app.applied_date != ""
    assert app.last_updated == app.applied_date
    assert app.follow_up_date != ""


def test_history_seeded_on_creation():
    app = make_app()
    assert len(app.history) == 1
    assert app.history[0]["action"] == "applied"


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------

def test_update_status_changes_status():
    app = make_app()
    app.update_status("interview")
    assert app.status == "interview"


def test_update_status_appends_to_history():
    app = make_app()
    app.update_status("screening", note="HR call scheduled")
    assert len(app.history) == 2
    assert app.history[-1]["action"] == "screening"
    assert app.history[-1]["note"] == "HR call scheduled"


# ---------------------------------------------------------------------------
# reset_status
# ---------------------------------------------------------------------------

def test_reset_status_sets_applied():
    app = make_app()
    app.update_status("interview")
    app.reset_status()
    assert app.status == "applied"


def test_reset_status_appends_reset_event():
    app = make_app()
    app.update_status("interview")
    app.reset_status()
    assert app.history[-1]["action"] == "reset"


# ---------------------------------------------------------------------------
# needs_follow_up
# ---------------------------------------------------------------------------

def test_needs_follow_up_false_for_terminal_statuses():
    for status in ("rejected", "withdrawn", "offer"):
        app = make_app()
        app.status = status
        assert app.needs_follow_up() is False, f"Expected False for status={status}"


def test_needs_follow_up_true_when_overdue():
    app = make_app()
    app.follow_up_date = "2020-01-01"  # far in the past
    app.status = "applied"
    assert app.needs_follow_up() is True


# ---------------------------------------------------------------------------
# VALID_TRANSITIONS
# ---------------------------------------------------------------------------

def test_valid_transition_applied_to_interview():
    assert "interview" in VALID_TRANSITIONS["applied"]


def test_invalid_transition_rejected_to_offer():
    assert "offer" not in VALID_TRANSITIONS["rejected"]


# ---------------------------------------------------------------------------
# Round-trip serialization
# ---------------------------------------------------------------------------

def test_to_dict_from_dict_roundtrip():
    app = make_app(job_title="DSP Engineer", company="Intel", location="Haifa")
    app.update_status("screening")
    data = app.to_dict()
    restored = Application.from_dict(data)
    assert restored.job_title == app.job_title
    assert restored.company == app.company
    assert restored.status == app.status
    assert restored.id == app.id
    assert restored.history == app.history
