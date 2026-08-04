"""Tests for multi-profile management (profile_manager.py)."""

import json
from pathlib import Path

import pytest

from job_hunter.config import Config
from job_hunter.profile_manager import (
    delete_profile,
    get_active_profile,
    has_legacy_profile,
    list_profiles,
    migrate_legacy_profile,
    profile_exists,
    set_active_profile,
    slugify,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolate_config(tmp_path):
    """Point Config at a temp directory for every test."""
    original = {
        "_BASE_DATA_DIR": Config._BASE_DATA_DIR,
        "DATA_DIR": Config.DATA_DIR,
        "_active_user": Config._active_user,
    }
    Config._BASE_DATA_DIR = tmp_path
    Config.DATA_DIR = tmp_path
    Config._active_user = None
    yield tmp_path
    for key, value in original.items():
        setattr(Config, key, value)
    Config._recalculate_paths()


def _create_profile(
    base: Path, slug: str, name: str = "Test User", email: str = "test@example.com"
) -> Path:
    """Helper: create a minimal profile under users/<slug>/."""
    d = base / "users" / slug
    d.mkdir(parents=True, exist_ok=True)
    profile_file = d / "user_profile.json"
    profile_file.write_text(
        json.dumps(
            {
                "name": name,
                "email": email,
                "phone": "050-0000000",
                "target_positions": ["Developer"],
            }
        ),
        encoding="utf-8",
    )
    return d


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_basic_name(self):
        assert slugify("Dvir Salomon") == "dvir-salomon"

    def test_uppercase(self):
        assert slugify("ALICE BOB") == "alice-bob"

    def test_special_characters(self):
        assert slugify("user@123!") == "user123"

    def test_underscores_become_hyphens(self):
        assert slugify("my_profile") == "my-profile"

    def test_multiple_spaces(self):
        assert slugify("a   b") == "a-b"

    def test_empty_string(self):
        assert slugify("") == "default"

    def test_only_special_chars(self):
        assert slugify("@#$%") == "default"

    def test_leading_trailing_hyphens(self):
        assert slugify("-hello-") == "hello"

    def test_hebrew_falls_back(self):
        assert slugify("דביר") == "default"


# ---------------------------------------------------------------------------
# Active profile read/write
# ---------------------------------------------------------------------------


class TestActiveProfile:
    def test_no_active_profile_returns_none(self, isolate_config):
        assert get_active_profile() is None

    def test_set_and_get(self, isolate_config):
        set_active_profile("dvir")
        assert get_active_profile() == "dvir"

    def test_overwrite(self, isolate_config):
        set_active_profile("alice")
        set_active_profile("bob")
        assert get_active_profile() == "bob"

    def test_empty_file_returns_none(self, isolate_config):
        path = isolate_config / ".active_profile"
        path.write_text("", encoding="utf-8")
        assert get_active_profile() is None


# ---------------------------------------------------------------------------
# list_profiles
# ---------------------------------------------------------------------------


class TestListProfiles:
    def test_empty_no_users_dir(self, isolate_config):
        assert list_profiles() == []

    def test_empty_users_dir(self, isolate_config):
        (isolate_config / "users").mkdir()
        assert list_profiles() == []

    def test_one_profile(self, isolate_config):
        _create_profile(isolate_config, "dvir", name="Dvir Salomon")
        profiles = list_profiles()
        assert len(profiles) == 1
        assert profiles[0]["slug"] == "dvir"
        assert profiles[0]["name"] == "Dvir Salomon"
        assert profiles[0]["active"] is False

    def test_active_marker(self, isolate_config):
        _create_profile(isolate_config, "dvir")
        set_active_profile("dvir")
        profiles = list_profiles()
        assert profiles[0]["active"] is True

    def test_multiple_profiles(self, isolate_config):
        _create_profile(isolate_config, "alice", name="Alice")
        _create_profile(isolate_config, "bob", name="Bob")
        set_active_profile("bob")
        profiles = list_profiles()
        assert len(profiles) == 2
        slugs = {p["slug"] for p in profiles}
        assert slugs == {"alice", "bob"}
        active_ones = [p for p in profiles if p["active"]]
        assert len(active_ones) == 1
        assert active_ones[0]["slug"] == "bob"

    def test_skips_dirs_without_profile(self, isolate_config):
        (isolate_config / "users" / "empty_dir").mkdir(parents=True)
        _create_profile(isolate_config, "valid")
        profiles = list_profiles()
        assert len(profiles) == 1

    def test_skips_corrupt_json(self, isolate_config):
        d = isolate_config / "users" / "corrupt"
        d.mkdir(parents=True)
        (d / "user_profile.json").write_text("{bad json", encoding="utf-8")
        _create_profile(isolate_config, "valid")
        profiles = list_profiles()
        assert len(profiles) == 1


# ---------------------------------------------------------------------------
# profile_exists / profile_dir
# ---------------------------------------------------------------------------


class TestProfileExists:
    def test_exists(self, isolate_config):
        _create_profile(isolate_config, "alice")
        assert profile_exists("alice") is True

    def test_not_exists(self, isolate_config):
        assert profile_exists("nobody") is False


# ---------------------------------------------------------------------------
# delete_profile
# ---------------------------------------------------------------------------


class TestDeleteProfile:
    def test_delete(self, isolate_config):
        _create_profile(isolate_config, "alice")
        set_active_profile("bob")
        delete_profile("alice")
        assert not (isolate_config / "users" / "alice").exists()

    def test_delete_active_raises(self, isolate_config):
        _create_profile(isolate_config, "alice")
        set_active_profile("alice")
        with pytest.raises(ValueError, match="active profile"):
            delete_profile("alice")

    def test_delete_nonexistent_raises(self, isolate_config):
        with pytest.raises(FileNotFoundError, match="not found"):
            delete_profile("ghost")


# ---------------------------------------------------------------------------
# Legacy migration
# ---------------------------------------------------------------------------


class TestLegacyMigration:
    def test_has_legacy_true(self, isolate_config):
        (isolate_config / "user_profile.json").write_text(
            '{"name":"x"}', encoding="utf-8"
        )
        assert has_legacy_profile() is True

    def test_has_legacy_false_no_file(self, isolate_config):
        assert has_legacy_profile() is False

    def test_has_legacy_false_already_migrated(self, isolate_config):
        (isolate_config / "user_profile.json").write_text(
            '{"name":"x"}', encoding="utf-8"
        )
        set_active_profile("default")
        assert has_legacy_profile() is False

    def test_migrate_moves_profile(self, isolate_config):
        (isolate_config / "user_profile.json").write_text(
            json.dumps({"name": "Dvir", "email": "d@e.com", "phone": "050"}),
            encoding="utf-8",
        )
        migrate_legacy_profile("dvir")

        # Profile moved
        assert not (isolate_config / "user_profile.json").exists()
        assert (isolate_config / "users" / "dvir" / "user_profile.json").exists()
        # Active set
        assert get_active_profile() == "dvir"

    def test_migrate_moves_data_dirs(self, isolate_config):
        # Create legacy structure
        (isolate_config / "user_profile.json").write_text("{}", encoding="utf-8")
        (isolate_config / "applications").mkdir()
        (isolate_config / "applications" / "applications.json").write_text(
            "[]", encoding="utf-8"
        )
        (isolate_config / "cv").mkdir()
        (isolate_config / "cv" / "base_cv.json").write_text("{}", encoding="utf-8")

        migrate_legacy_profile("default")

        assert not (isolate_config / "applications").exists()
        assert (
            isolate_config / "users" / "default" / "applications" / "applications.json"
        ).exists()
        assert (isolate_config / "users" / "default" / "cv" / "base_cv.json").exists()

    def test_migrate_keeps_companies_json(self, isolate_config):
        (isolate_config / "user_profile.json").write_text("{}", encoding="utf-8")
        jobs_dir = isolate_config / "jobs"
        jobs_dir.mkdir()
        (jobs_dir / "companies.json").write_text("[]", encoding="utf-8")
        (jobs_dir / "scan_history.json").write_text("[]", encoding="utf-8")

        migrate_legacy_profile("default")

        # companies.json stays at root
        assert (isolate_config / "jobs" / "companies.json").exists()
        # scan_history moved
        assert (
            isolate_config / "users" / "default" / "jobs" / "scan_history.json"
        ).exists()

    def test_migrate_custom_slug(self, isolate_config):
        (isolate_config / "user_profile.json").write_text("{}", encoding="utf-8")
        slug = migrate_legacy_profile("my-profile")
        assert slug == "my-profile"
        assert get_active_profile() == "my-profile"
