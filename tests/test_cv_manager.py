import pytest

from job_hunter.cv.manager import CVManager


@pytest.fixture
def tmp_cv_manager(tmp_path):
    return CVManager(cv_dir=tmp_path)


def test_init_base_creates_file(tmp_cv_manager, tmp_path):
    path = tmp_cv_manager.init_base()
    assert path.exists()
    assert path.name == "base_cv.json"


def test_load_base_returns_dict(tmp_cv_manager):
    tmp_cv_manager.init_base()
    data = tmp_cv_manager.load_base()
    assert isinstance(data, dict)
    assert "name" in data
    assert "experience" in data


def test_save_and_load_base(tmp_cv_manager):
    sample = {"name": "Jane Doe", "title": "Engineer", "skills": ["Python"]}
    tmp_cv_manager.save_base(sample)
    loaded = tmp_cv_manager.load_base()
    assert loaded["name"] == "Jane Doe"


def test_save_version(tmp_cv_manager, tmp_path):
    data = {"name": "Jane Doe", "title": "Engineer"}
    path = tmp_cv_manager.save_version(data, label="google")
    assert path.exists()
    assert "google" in path.name


def test_list_versions(tmp_cv_manager):
    tmp_cv_manager.save_version({"name": "A"}, "v1")
    tmp_cv_manager.save_version({"name": "B"}, "v2")
    versions = tmp_cv_manager.list_versions()
    assert len(versions) == 2


def test_load_base_raises_if_missing(tmp_cv_manager):
    with pytest.raises(FileNotFoundError):
        tmp_cv_manager.load_base()
