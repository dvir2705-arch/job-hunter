"""Tests for Priority 4 — onboarding flow (init command, CV pre-fill, profile guard)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from job_hunter.cli import cli
from job_hunter.profile import UserProfile, profile_exists


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Patch Config.DATA_DIR to a temp directory for isolation."""
    empty_suggestions = {"registry": [], "additional": []}
    with patch("job_hunter.config.Config.DATA_DIR", tmp_path), \
         patch("job_hunter.profile.Config.DATA_DIR", tmp_path), \
         patch("job_hunter.jobs.search_strategy.suggest_companies",
               return_value=empty_suggestions):
        yield tmp_path


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# UserProfile.save tests
# ---------------------------------------------------------------------------

class TestUserProfileSave:
    def test_save_creates_file(self, tmp_data_dir):
        profile = UserProfile(name="Test User", email="test@example.com", phone="123")
        path = profile.save(tmp_data_dir / "user_profile.json")
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["name"] == "Test User"
        assert data["email"] == "test@example.com"

    def test_save_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "profile.json"
        profile = UserProfile(name="A", email="a@b.com", phone="1")
        profile.save(nested)
        assert nested.exists()

    def test_save_roundtrip(self, tmp_data_dir):
        original = UserProfile(
            name="Dvir", email="d@g.com", phone="053",
            education={"university": "BGU", "degree": "B.Sc. EE"},
            domains=["software", "dsp"], skills=["Python"],
        )
        path = original.save(tmp_data_dir / "user_profile.json")
        loaded = UserProfile.load(path)
        assert loaded.name == original.name
        assert loaded.domains == original.domains
        assert loaded.skills == original.skills
        assert loaded.university == "BGU"


# ---------------------------------------------------------------------------
# profile_exists tests
# ---------------------------------------------------------------------------

class TestProfileExists:
    def test_returns_false_when_missing(self, tmp_data_dir):
        assert profile_exists() is False

    def test_returns_true_when_present(self, tmp_data_dir):
        profile = UserProfile(name="X", email="x@x.com", phone="1")
        profile.save(tmp_data_dir / "user_profile.json")
        assert profile_exists() is True


# ---------------------------------------------------------------------------
# `job-hunter init` command tests
# ---------------------------------------------------------------------------

class TestInitCommand:
    def test_init_creates_profile_student(self, runner, tmp_data_dir):
        # Prompts: name, email, phone, target_roles, skills,
        #          experience(none), country, cities, studying?(y), degree, university
        inputs = (
            "Alice\nalice@example.com\n555\n"
            "software, ml\nPython\n"
            "none\nIsrael\n\n"
            "y\nB.Sc. CS\nMIT\n"
        )
        result = runner.invoke(cli, ["init"], input=inputs)
        assert result.exit_code == 0
        assert "Profile saved" in result.output
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert data["name"] == "Alice"
        assert data["email"] == "alice@example.com"
        assert data["target_positions"] == ["software", "ml"]
        assert data["education"]["degree"] == "B.Sc. CS"
        assert data["education"]["university"] == "MIT"
        assert data["experience_level"] == "none"
        assert data["location"]["country"] == "Israel"

    def test_init_creates_profile_experienced(self, runner, tmp_data_dir):
        # Prompts: name, email, phone, target_roles, skills,
        #          experience(3-7), country, cities, radius
        inputs = (
            "Bob\nb@b.com\n111\n"
            "backend, fullstack\nPython, React\n"
            "3-7\nIsrael\nTel Aviv, Haifa\n25\n"
        )
        result = runner.invoke(cli, ["init"], input=inputs)
        assert result.exit_code == 0
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert data["name"] == "Bob"
        assert data["experience_level"] == "3-7"
        assert data["location"]["cities"] == ["Tel Aviv", "Haifa"]
        assert data["location"]["radius_km"] == 25

    def test_init_domains_derived_from_targets_and_skills(self, runner, tmp_data_dir):
        inputs = (
            "Carol\nc@c.com\n222\n"
            "software developer\nPython, MATLAB\n"
            "none\nIsrael\n\n"
            "n\n"  # not studying
        )
        result = runner.invoke(cli, ["init"], input=inputs)
        assert result.exit_code == 0
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        # Domains auto-derived from target_positions + skills
        assert "python" in data["domains"]
        assert "software" in data["domains"]

    def test_init_aborts_if_exists_and_user_declines(self, runner, tmp_data_dir):
        UserProfile(name="Old", email="o@o.com", phone="0").save(
            tmp_data_dir / "user_profile.json"
        )
        result = runner.invoke(cli, ["init"], input="n\n")
        assert result.exit_code == 0
        assert "Aborted" in result.output
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert data["name"] == "Old"

    def test_init_overwrites_if_confirmed(self, runner, tmp_data_dir):
        UserProfile(name="Old", email="o@o.com", phone="0").save(
            tmp_data_dir / "user_profile.json"
        )
        # y(overwrite), name, email, phone, targets, skills, exp, country, cities, studying(n)
        inputs = "y\nNew\nnew@n.com\n222\nsoftware\nPython\nnone\nIsrael\n\nn\n"
        result = runner.invoke(cli, ["init"], input=inputs)
        assert result.exit_code == 0
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert data["name"] == "New"


# ---------------------------------------------------------------------------
# CV pre-fill tests
# ---------------------------------------------------------------------------

class TestCVPreFill:
    def test_init_from_cv_prefills_flat_skills(self, runner, tmp_data_dir, tmp_path):
        cv_json = {
            "name": "CV Person",
            "email": "cv@example.com",
            "phone": "999",
            "education": [{"institution": "Stanford", "degree": "M.Sc. AI"}],
            "skills": ["Python", "TensorFlow"],
        }
        cv_path = tmp_path / "cv.json"
        cv_path.write_text(json.dumps(cv_json), encoding="utf-8")

        # Prompts: name(enter), email(enter), phone(enter), targets, skills(enter=prefilled),
        #          experience(none), country, cities, studying(y), degree(enter=prefilled), university(enter=prefilled)
        result = runner.invoke(cli, ["init", "--from-cv", str(cv_path)],
                               input="\n\n\nsoftware\n\nnone\nIsrael\n\ny\n\n\n")
        assert result.exit_code == 0
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert data["name"] == "CV Person"
        assert data["education"]["university"] == "Stanford"
        assert "Python" in data["skills"]

    def test_init_from_cv_prefills_categorized_skills(self, runner, tmp_data_dir, tmp_path):
        """base_cv.json uses dict format: {"programming": [...], "technical": [...]}."""
        cv_json = {
            "name": "Dvir",
            "email": "d@g.com",
            "phone": "053",
            "education": [{"institution": "BGU", "degree": "B.Sc. EE"}],
            "skills": {
                "programming": ["Python", "Assembly", "MATLAB"],
                "technical": ["Machine Learning", "Signal Processing"],
                "tools": ["Git"],
            },
            "projects": [
                {"name": "Job Hunter", "technologies": ["REST APIs", "Web Scraping"]},
            ],
        }
        cv_path = tmp_path / "cv.json"
        cv_path.write_text(json.dumps(cv_json), encoding="utf-8")

        result = runner.invoke(cli, ["init", "--from-cv", str(cv_path)],
                               input="\n\n\nsoftware\n\nnone\nIsrael\n\ny\n\n\n")
        assert result.exit_code == 0
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        # All categorized skills extracted
        assert "Python" in data["skills"]
        assert "Machine Learning" in data["skills"]
        assert "Signal Processing" in data["skills"]
        assert "Git" in data["skills"]
        # Project technologies extracted
        assert "REST APIs" in data["skills"]
        assert "Web Scraping" in data["skills"]
        # No duplicates
        assert len(data["skills"]) == len(set(data["skills"]))


# ---------------------------------------------------------------------------
# require_profile guard tests
# ---------------------------------------------------------------------------

class TestRequireProfileGuard:
    def test_cv_adapt_blocked_without_profile(self, runner, tmp_data_dir):
        result = runner.invoke(cli, ["cv", "adapt", "-u", "https://fake.example.com"])
        assert result.exit_code != 0
        assert "Profile not found" in result.output
        assert "job-hunter init" in result.output

    def test_jobs_search_blocked_without_profile(self, runner, tmp_data_dir):
        result = runner.invoke(cli, ["jobs", "search", "-q", "python"])
        assert result.exit_code != 0
        assert "Profile not found" in result.output

    def test_jobs_scan_blocked_without_profile(self, runner, tmp_data_dir):
        result = runner.invoke(cli, ["jobs", "scan"])
        assert result.exit_code != 0
        assert "Profile not found" in result.output

    def test_jobs_discover_blocked_without_profile(self, runner, tmp_data_dir):
        result = runner.invoke(cli, ["jobs", "discover"])
        assert result.exit_code != 0
        assert "Profile not found" in result.output


# ---------------------------------------------------------------------------
# Phase 2: experience_level + watchlist
# ---------------------------------------------------------------------------

class TestExperienceLevelField:
    def test_save_and_load_experience_level(self, tmp_data_dir):
        p = UserProfile(name="A", email="a@b.com", phone="1", experience_level="3-7")
        path = p.save(tmp_data_dir / "user_profile.json")
        loaded = UserProfile.load(path)
        assert loaded.experience_level == "3-7"

    def test_save_and_load_watchlist(self, tmp_data_dir):
        p = UserProfile(
            name="A", email="a@b.com", phone="1",
            watchlist=["Intel", "Google"],
        )
        path = p.save(tmp_data_dir / "user_profile.json")
        loaded = UserProfile.load(path)
        assert loaded.watchlist == ["Intel", "Google"]

    def test_validate_invalid_experience_level(self):
        p = UserProfile(name="A", email="a@b.com", phone="1", experience_level="20+")
        issues = p.validate()
        assert any("experience_level" in i for i in issues)

    def test_validate_valid_experience_levels(self):
        for level in ("", "none", "1-3", "3-7", "7+"):
            p = UserProfile(name="A", email="a@b.com", phone="1", experience_level=level)
            issues = p.validate()
            assert not any("experience_level" in i for i in issues)

    def test_migration_student_gets_none(self, tmp_data_dir):
        """Profile with education.year but no experience_level → migrates to 'none'."""
        data = {
            "name": "A", "email": "a@b.com", "phone": "1",
            "education": {"university": "BGU", "year": "3rd"},
        }
        path = tmp_data_dir / "user_profile.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = UserProfile.load(path)
        assert loaded.experience_level == "none"

    def test_migration_experienced_gets_1_3(self, tmp_data_dir):
        """Profile with work_experience but no experience_level → migrates to '1-3'."""
        data = {
            "name": "A", "email": "a@b.com", "phone": "1",
            "work_experience": [{"title": "SWE", "company": "X"}],
        }
        path = tmp_data_dir / "user_profile.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = UserProfile.load(path)
        assert loaded.experience_level == "1-3"

    def test_migration_no_exp_no_edu_gets_none(self, tmp_data_dir):
        """Profile with nothing → migrates to 'none'."""
        data = {"name": "A", "email": "a@b.com", "phone": "1"}
        path = tmp_data_dir / "user_profile.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = UserProfile.load(path)
        assert loaded.experience_level == "none"

    def test_existing_experience_level_not_overwritten(self, tmp_data_dir):
        """Profile with explicit experience_level keeps it."""
        data = {
            "name": "A", "email": "a@b.com", "phone": "1",
            "experience_level": "7+",
        }
        path = tmp_data_dir / "user_profile.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = UserProfile.load(path)
        assert loaded.experience_level == "7+"

    def test_default_watchlist_empty(self):
        p = UserProfile(name="A", email="a@b.com", phone="1")
        assert p.watchlist == []


# ---------------------------------------------------------------------------
# Profile enrich command
# ---------------------------------------------------------------------------

class TestProfileEnrich:
    def test_enrich_adds_cv_skills(self, runner, tmp_data_dir):
        """Enrich pulls missing skills from CV into profile."""
        # Create profile with 2 skills
        UserProfile(
            name="A", email="a@b.com", phone="1",
            skills=["Python", "MATLAB"],
        ).save(tmp_data_dir / "user_profile.json")

        # Create CV with more skills
        cv_dir = tmp_data_dir / "cv"
        cv_dir.mkdir(exist_ok=True)
        cv_data = {
            "skills": {
                "programming": ["Python", "Assembly", "MATLAB"],
                "technical": ["Machine Learning", "Signal Processing"],
            },
            "projects": [{"name": "P", "technologies": ["REST APIs"]}],
        }
        (cv_dir / "base_cv.json").write_text(json.dumps(cv_data), encoding="utf-8")

        with patch("job_hunter.config.Config.CV_DIR", cv_dir):
            result = runner.invoke(cli, ["profile", "enrich"], input="y\n")

        assert result.exit_code == 0
        data = json.loads((tmp_data_dir / "user_profile.json").read_text(encoding="utf-8"))
        assert "Machine Learning" in data["skills"]
        assert "Signal Processing" in data["skills"]
        assert "Assembly" in data["skills"]
        assert "REST APIs" in data["skills"]
        # Original skills preserved
        assert "Python" in data["skills"]
        assert "MATLAB" in data["skills"]

    def test_enrich_no_duplicates(self, runner, tmp_data_dir):
        """Skills already in profile are not added again."""
        UserProfile(
            name="A", email="a@b.com", phone="1",
            skills=["Python", "Machine Learning"],
        ).save(tmp_data_dir / "user_profile.json")

        cv_dir = tmp_data_dir / "cv"
        cv_dir.mkdir(exist_ok=True)
        cv_data = {"skills": {"programming": ["Python"], "technical": ["Machine Learning"]}}
        (cv_dir / "base_cv.json").write_text(json.dumps(cv_data), encoding="utf-8")

        with patch("job_hunter.config.Config.CV_DIR", cv_dir):
            result = runner.invoke(cli, ["profile", "enrich"])

        assert "already has all CV skills" in result.output

    def test_enrich_no_cv_shows_error(self, runner, tmp_data_dir):
        """Enrich without a CV shows helpful error."""
        UserProfile(name="A", email="a@b.com", phone="1").save(
            tmp_data_dir / "user_profile.json"
        )

        cv_dir = tmp_data_dir / "cv"
        cv_dir.mkdir(exist_ok=True)
        with patch("job_hunter.config.Config.CV_DIR", cv_dir):
            result = runner.invoke(cli, ["profile", "enrich"])

        assert "No CV found" in result.output
