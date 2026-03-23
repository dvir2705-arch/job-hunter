import pytest
from job_hunter.applications.tracker import ApplicationTracker
from job_hunter.applications.models import ApplicationStatus


@pytest.fixture
def tracker(tmp_path):
    return ApplicationTracker(filepath=tmp_path / "applications.json")


def test_add_application(tracker):
    app = tracker.add(company="Google", position="SWE", url="https://google.com/jobs/1")
    assert app.id is not None
    assert app.company == "Google"
    assert app.status == ApplicationStatus.APPLIED


def test_list_all(tracker):
    tracker.add("Google", "SWE", "https://g.com")
    tracker.add("Meta", "SWE", "https://m.com")
    assert len(tracker.list()) == 2


def test_list_by_status(tracker):
    tracker.add("Google", "SWE", "https://g.com")
    app = tracker.add("Meta", "SWE", "https://m.com")
    tracker.update_status(app.id, ApplicationStatus.INTERVIEW)
    assert len(tracker.list(ApplicationStatus.INTERVIEW)) == 1
    assert len(tracker.list(ApplicationStatus.APPLIED)) == 1


def test_update_status(tracker):
    app = tracker.add("Google", "SWE", "https://g.com")
    updated = tracker.update_status(app.id, ApplicationStatus.OFFER)
    assert updated.status == ApplicationStatus.OFFER


def test_stats(tracker):
    tracker.add("Google", "SWE", "https://g.com")
    tracker.add("Meta", "SWE", "https://m.com")
    stats = tracker.stats()
    assert stats["total"] == 2
    assert stats["by_status"]["applied"] == 2


def test_delete(tracker):
    app = tracker.add("Google", "SWE", "https://g.com")
    tracker.delete(app.id)
    assert tracker.list() == []


def test_persistence(tmp_path):
    t1 = ApplicationTracker(filepath=tmp_path / "apps.json")
    t1.add("Google", "SWE", "https://g.com")
    t2 = ApplicationTracker(filepath=tmp_path / "apps.json")
    assert len(t2.list()) == 1
