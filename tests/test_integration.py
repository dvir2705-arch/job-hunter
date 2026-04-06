"""Integration tests — Phase 2 Step 8.

Tests 3 user profiles end-to-end through the pipeline:
  1. CS student (no experience, studying at Tel Aviv University)
  2. Backend developer (3-7 years, Python/Node)
  3. Data scientist (1-3 years, Python/ML)

Each profile verifies: save → load → search config build → relevance filter keywords.
Also verifies Dvir's existing profile still works.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from job_hunter.profile import UserProfile
from job_hunter.config import Config


# ---------------------------------------------------------------------------
# Test profiles
# ---------------------------------------------------------------------------

CS_STUDENT = {
    "name": "Yael Cohen",
    "email": "yael@example.com",
    "phone": "054-1234567",
    "skills": ["Python", "Java", "SQL", "Git"],
    "target_positions": ["software developer", "backend engineer", "QA engineer"],
    "domains": [],
    "experience_level": "none",
    "education": {
        "university": "Tel Aviv University",
        "degree": "B.Sc. Computer Science",
        "year": "2nd",
    },
    "location": {"country": "Israel", "cities": ["Tel Aviv", "Ramat Gan"], "radius_km": 15},
    "watchlist": ["Intel", "Google"],
}

BACKEND_DEV = {
    "name": "Amit Levi",
    "email": "amit@example.com",
    "phone": "052-9876543",
    "skills": ["Python", "Node.js", "PostgreSQL", "Docker", "AWS", "Kubernetes"],
    "target_positions": ["backend developer", "full stack developer", "DevOps engineer"],
    "domains": ["software"],
    "experience_level": "3-7",
    "education": {
        "university": "Technion",
        "degree": "B.Sc. Computer Science",
    },
    "work_experience": [
        {"company": "Wix", "role": "Backend Developer", "years": "2020-2024"},
    ],
    "location": {"country": "Israel", "cities": ["Haifa", "Tel Aviv"], "radius_km": 30},
    "watchlist": ["NVIDIA", "Intel", "Amazon"],
}

DATA_SCIENTIST = {
    "name": "Noa Shapira",
    "email": "noa@example.com",
    "phone": "050-5555555",
    "skills": ["Python", "TensorFlow", "PyTorch", "pandas", "SQL", "Spark"],
    "target_positions": ["data scientist", "ML engineer", "AI researcher"],
    "domains": ["ai_ml"],
    "experience_level": "1-3",
    "education": {
        "university": "Hebrew University",
        "degree": "M.Sc. Computer Science",
    },
    "work_experience": [
        {"company": "Mobileye", "role": "Data Scientist Intern", "years": "2024-2025"},
    ],
    "location": {"country": "Israel", "cities": ["Jerusalem", "Tel Aviv"], "radius_km": 25},
    "watchlist": ["Mobileye", "NVIDIA"],
}

DVIR_PROFILE = {
    "name": "Dvir Salomon",
    "email": "dvir@example.com",
    "phone": "053-3401466",
    "skills": ["Python", "MATLAB", "C"],
    "target_positions": ["software", "DSP", "chip design"],
    "domains": ["software", "electrical", "chip"],
    "experience_level": "none",
    "education": {
        "university": "Ben-Gurion University of the Negev",
        "degree": "B.Sc. Electrical Engineering",
        "year": "3rd",
    },
    "location": {"country": "Israel", "cities": [], "radius_km": 25},
    "watchlist": ["Intel", "NVIDIA", "Marvell"],
    "hard_rules": {"cv_title": "Electrical Engineering Student"},
}


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Patch Config.DATA_DIR to a temp directory with companies.json."""
    # Create companies.json registry
    registry = {
        "companies": [
            {"name": "Intel", "domain": ["chip_design", "ai_ml"],
             "scraper": "IntelScraper", "priority": True},
            {"name": "NVIDIA", "domain": ["chip_design", "ai_ml"],
             "scraper": "NVIDIAScraper", "priority": True},
            {"name": "Marvell", "domain": ["chip_design", "communications"],
             "scraper": "MarvellScraper", "priority": True},
            {"name": "Amazon", "domain": ["cloud", "software"],
             "scraper": "AmazonScraper", "priority": True},
            {"name": "Mobileye", "domain": ["autonomous_driving", "ai_ml"],
             "scraper": None, "priority": False},
        ]
    }
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    (jobs_dir / "companies.json").write_text(json.dumps(registry), encoding="utf-8")

    with patch("job_hunter.config.Config.DATA_DIR", tmp_path), \
         patch("job_hunter.profile.Config.DATA_DIR", tmp_path):
        yield tmp_path


@pytest.fixture(autouse=True)
def reset_profile_cache():
    """Reset cached profile between tests."""
    import job_hunter.profile as pm
    pm._profile = None
    pm._profile_path_override = None
    yield
    pm._profile = None
    pm._profile_path_override = None


def _save_profile(data: dict, tmp_dir: Path) -> UserProfile:
    """Save profile dict and return loaded UserProfile."""
    path = tmp_dir / "user_profile.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return UserProfile.load(path)


# ---------------------------------------------------------------------------
# Profile save/load round-trip
# ---------------------------------------------------------------------------

class TestProfileRoundTrip:
    @pytest.mark.parametrize("label,data", [
        ("cs_student", CS_STUDENT),
        ("backend_dev", BACKEND_DEV),
        ("data_scientist", DATA_SCIENTIST),
        ("dvir", DVIR_PROFILE),
    ])
    def test_save_and_reload(self, tmp_data_dir, label, data):
        path = tmp_data_dir / "user_profile.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        profile = UserProfile.load(path)

        # Required fields preserved
        assert profile.name == data["name"]
        assert profile.email == data["email"]
        assert profile.skills == data["skills"]
        assert profile.target_positions == data["target_positions"]
        assert profile.experience_level == data["experience_level"]

        # Save and reload again
        profile.save(path)
        reloaded = UserProfile.load(path)
        assert reloaded.name == profile.name
        assert reloaded.watchlist == profile.watchlist

    @pytest.mark.parametrize("label,data", [
        ("cs_student", CS_STUDENT),
        ("backend_dev", BACKEND_DEV),
        ("data_scientist", DATA_SCIENTIST),
        ("dvir", DVIR_PROFILE),
    ])
    def test_validation_passes(self, tmp_data_dir, label, data):
        profile = _save_profile(data, tmp_data_dir)
        issues = profile.validate()
        errors = [i for i in issues if i.startswith("[ERROR]")]
        assert errors == [], f"{label} has validation errors: {errors}"


# ---------------------------------------------------------------------------
# Search config build
# ---------------------------------------------------------------------------

class TestSearchConfigBuild:
    @pytest.mark.parametrize("label,data", [
        ("cs_student", CS_STUDENT),
        ("backend_dev", BACKEND_DEV),
        ("data_scientist", DATA_SCIENTIST),
        ("dvir", DVIR_PROFILE),
    ])
    def test_build_search_config(self, tmp_data_dir, label, data):
        profile = _save_profile(data, tmp_data_dir)

        from job_hunter.jobs.search_strategy import build_search_config
        # Mock Haiku query generation to avoid API calls
        mock_queries = ["test query 1", "test query 2"]
        with patch("job_hunter.jobs.search_strategy.generate_queries", return_value=mock_queries):
            config = build_search_config(profile)

        # Queries present
        assert len(config.queries) >= 1

        # Location matches profile
        assert config.location == profile.country

        # Companies from watchlist
        assert set(config.companies) == set(profile.watchlist)

    def test_cs_student_seniority(self, tmp_data_dir):
        """CS student (experience=none, is_student=True) should reject senior roles."""
        profile = _save_profile(CS_STUDENT, tmp_data_dir)

        from job_hunter.jobs.search_strategy import build_search_config
        with patch("job_hunter.jobs.search_strategy.generate_queries", return_value=["q"]):
            config = build_search_config(profile)

        assert "student" in config.level_keywords or "intern" in config.level_keywords
        assert "senior" in config.seniority_reject

    def test_backend_dev_seniority(self, tmp_data_dir):
        """Backend dev (experience=3-7) should NOT reject senior roles aggressively."""
        profile = _save_profile(BACKEND_DEV, tmp_data_dir)

        from job_hunter.jobs.search_strategy import build_search_config
        with patch("job_hunter.jobs.search_strategy.generate_queries", return_value=["q"]):
            config = build_search_config(profile)

        # 3-7 years: should use SENIORITY_REJECT_EXPERIENCED (only VP/director/etc)
        assert "senior" not in config.seniority_reject
        assert config.level_keywords == []

    def test_data_scientist_seniority(self, tmp_data_dir):
        """Data scientist (experience=1-3) should reject senior roles."""
        profile = _save_profile(DATA_SCIENTIST, tmp_data_dir)

        from job_hunter.jobs.search_strategy import build_search_config
        with patch("job_hunter.jobs.search_strategy.generate_queries", return_value=["q"]):
            config = build_search_config(profile)

        assert "senior" in config.seniority_reject

    def test_watchlist_enables_scrapers(self, tmp_data_dir):
        """Watchlist companies with dedicated scrapers should be enabled."""
        profile = _save_profile(DVIR_PROFILE, tmp_data_dir)

        from job_hunter.jobs.search_strategy import build_search_config
        with patch("job_hunter.jobs.search_strategy.generate_queries", return_value=["q"]):
            config = build_search_config(profile)

        assert "IntelScraper" in config.enabled_scrapers
        assert "NVIDIAScraper" in config.enabled_scrapers


# ---------------------------------------------------------------------------
# Relevance filter keywords
# ---------------------------------------------------------------------------

class TestRelevanceFilterKeywords:
    def test_cs_student_keywords(self, tmp_data_dir):
        """CS student keywords derived from target_positions + skills (no domains)."""
        _save_profile(CS_STUDENT, tmp_data_dir)

        from job_hunter.jobs.relevance_filter import _get_relevant_keywords
        keywords = _get_relevant_keywords()

        # From skills
        assert "python" in keywords
        assert "java" in keywords
        assert "sql" in keywords

        # From target_positions
        assert "software" in keywords
        assert "backend" in keywords
        assert "engineer" in keywords

    def test_backend_dev_keywords(self, tmp_data_dir):
        """Backend dev has domains + target_positions + skills."""
        _save_profile(BACKEND_DEV, tmp_data_dir)

        from job_hunter.jobs.relevance_filter import _get_relevant_keywords
        keywords = _get_relevant_keywords()

        # From domains
        assert "software" in keywords
        # From skills
        assert "python" in keywords
        assert "docker" in keywords
        # From target_positions
        assert "backend" in keywords
        assert "devops" in keywords

    def test_data_scientist_keywords(self, tmp_data_dir):
        """Data scientist has ML-specific keywords."""
        _save_profile(DATA_SCIENTIST, tmp_data_dir)

        from job_hunter.jobs.relevance_filter import _get_relevant_keywords
        keywords = _get_relevant_keywords()

        assert "python" in keywords
        assert "tensorflow" in keywords
        assert "data" in keywords
        assert "scientist" in keywords

    def test_dvir_keywords(self, tmp_data_dir):
        """Dvir's profile should produce EE-relevant keywords."""
        _save_profile(DVIR_PROFILE, tmp_data_dir)

        from job_hunter.jobs.relevance_filter import _get_relevant_keywords
        keywords = _get_relevant_keywords()

        assert "python" in keywords
        assert "matlab" in keywords
        assert "software" in keywords
        assert "chip" in keywords
        assert "electrical" in keywords

    def test_no_profile_returns_empty(self, tmp_data_dir):
        """No profile file → empty keywords (graceful fallback)."""
        from job_hunter.jobs.relevance_filter import _get_relevant_keywords
        keywords = _get_relevant_keywords()
        assert keywords == []


# ---------------------------------------------------------------------------
# API key validation (B2)
# ---------------------------------------------------------------------------

class TestAPIKeyValidation:
    def test_scan_rejects_missing_key(self, tmp_data_dir):
        """jobs scan should fail immediately if ANTHROPIC_API_KEY is missing."""
        from click.testing import CliRunner
        from job_hunter.cli import cli

        _save_profile(CS_STUDENT, tmp_data_dir)
        runner = CliRunner()

        with patch("job_hunter.config.Config.ANTHROPIC_API_KEY", ""):
            result = runner.invoke(cli, ["jobs", "scan"])

        assert "ANTHROPIC_API_KEY" in result.output

    def test_refresh_rejects_missing_key(self, tmp_data_dir):
        """jobs refresh-queries should fail immediately if key is missing."""
        from click.testing import CliRunner
        from job_hunter.cli import cli

        _save_profile(CS_STUDENT, tmp_data_dir)
        runner = CliRunner()

        with patch("job_hunter.config.Config.ANTHROPIC_API_KEY", ""):
            result = runner.invoke(cli, ["jobs", "refresh-queries"])

        assert "ANTHROPIC_API_KEY" in result.output

    def test_discover_rejects_missing_key(self, tmp_data_dir):
        """jobs discover should fail immediately if key is missing."""
        from click.testing import CliRunner
        from job_hunter.cli import cli

        _save_profile(CS_STUDENT, tmp_data_dir)
        runner = CliRunner()

        with patch("job_hunter.config.Config.ANTHROPIC_API_KEY", ""):
            result = runner.invoke(cli, ["jobs", "discover"])

        assert "ANTHROPIC_API_KEY" in result.output


# ---------------------------------------------------------------------------
# Cross-profile consistency
# ---------------------------------------------------------------------------

class TestCrossProfileConsistency:
    def test_student_is_student_property(self, tmp_data_dir):
        """Profiles with education.year should have is_student=True."""
        cs = _save_profile(CS_STUDENT, tmp_data_dir)
        assert cs.is_student is True

        dvir = _save_profile(DVIR_PROFILE, tmp_data_dir)
        assert dvir.is_student is True

    def test_non_student_property(self, tmp_data_dir):
        """Profiles without education.year should have is_student=False."""
        backend = _save_profile(BACKEND_DEV, tmp_data_dir)
        assert backend.is_student is False

        ds = _save_profile(DATA_SCIENTIST, tmp_data_dir)
        assert ds.is_student is False

    def test_watchlist_drives_companies(self, tmp_data_dir):
        """Each profile's watchlist should determine which companies are scanned."""
        from job_hunter.jobs.search_strategy import _load_companies

        for label, data in [("cs", CS_STUDENT), ("backend", BACKEND_DEV),
                            ("ds", DATA_SCIENTIST), ("dvir", DVIR_PROFILE)]:
            profile = _save_profile(data, tmp_data_dir)
            companies, priority = _load_companies(profile)
            assert set(companies) == set(data["watchlist"]), \
                f"{label}: expected {data['watchlist']}, got {companies}"
