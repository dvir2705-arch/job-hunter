"""Multi-profile management — create, list, switch, and migrate profiles."""

import json
import re
import shutil
from pathlib import Path

from job_hunter.config import Config

# Directories that belong to a user profile (moved during migration)
_USER_DATA_DIRS = ("applications", "cv", "cover_letters", "jobs", "logs", "recruiters")
_USER_DATA_FILES = ("user_profile.json",)


def slugify(name: str) -> str:
    """Convert a profile name to a filesystem-safe slug.

    Lowercases, replaces spaces/underscores with hyphens,
    strips non-alphanumeric characters (except hyphens).
    """
    slug = name.lower().strip()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")
    return slug or "default"


def _active_profile_file() -> Path:
    """Return path to the .active_profile state file."""
    return Config._BASE_DATA_DIR / ".active_profile"


def get_active_profile() -> str | None:
    """Read the currently active profile name, or None if not set."""
    path = _active_profile_file()
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def set_active_profile(name: str) -> None:
    """Write the active profile name to the state file."""
    path = _active_profile_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(name + "\n", encoding="utf-8")


def profile_dir(name: str) -> Path:
    """Return the data directory for a named profile."""
    return Config._BASE_DATA_DIR / "users" / name


def list_profiles() -> list[dict]:
    """List all profiles with basic metadata.

    Returns a list of dicts with keys: slug, name, email, target_positions.
    """
    users_dir = Config._BASE_DATA_DIR / "users"
    if not users_dir.exists():
        return []

    active = get_active_profile()
    profiles = []
    for d in sorted(users_dir.iterdir()):
        profile_file = d / "user_profile.json"
        if d.is_dir() and profile_file.exists():
            try:
                with open(profile_file, encoding="utf-8") as f:
                    data = json.load(f)
                profiles.append(
                    {
                        "slug": d.name,
                        "name": data.get("name", ""),
                        "email": data.get("email", ""),
                        "target_positions": data.get("target_positions", []),
                        "active": d.name == active,
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue
    return profiles


def profile_exists(name: str) -> bool:
    """Check whether a named profile has a user_profile.json."""
    return (profile_dir(name) / "user_profile.json").exists()


def delete_profile(name: str) -> None:
    """Delete a profile directory. Raises ValueError if it's the active profile."""
    active = get_active_profile()
    if name == active:
        raise ValueError(
            f"Cannot delete the active profile '{name}'. "
            "Switch to another profile first."
        )
    d = profile_dir(name)
    if not d.exists():
        raise FileNotFoundError(f"Profile '{name}' not found.")
    shutil.rmtree(d)


def has_legacy_profile() -> bool:
    """Check if there's a legacy single-user profile at data/user_profile.json."""
    legacy = Config._BASE_DATA_DIR / "user_profile.json"
    active_file = _active_profile_file()
    return legacy.exists() and not active_file.exists()


def migrate_legacy_profile(target_slug: str = "default") -> str:
    """Migrate legacy single-user data into data/users/<target_slug>/.

    Moves user_profile.json and all user data directories.
    Shared files (companies.json) stay at the root level.
    Sets the migrated profile as active.

    Returns the slug used.
    """
    base = Config._BASE_DATA_DIR
    dest = base / "users" / target_slug
    dest.mkdir(parents=True, exist_ok=True)

    # Move user data directories
    for dirname in _USER_DATA_DIRS:
        src = base / dirname
        dst = dest / dirname
        if src.exists() and src.is_dir():
            # Skip if destination already exists (e.g., from partial migration)
            if dst.exists():
                continue
            # For jobs/, copy only user-specific files, keep shared ones
            if dirname == "jobs":
                dst.mkdir(parents=True, exist_ok=True)
                for item in src.iterdir():
                    # companies.json is shared — don't move it
                    if item.name == "companies.json":
                        continue
                    shutil.move(str(item), str(dst / item.name))
            else:
                shutil.move(str(src), str(dst))

    # Move user_profile.json
    for fname in _USER_DATA_FILES:
        src = base / fname
        dst = dest / fname
        if src.exists() and not dst.exists():
            shutil.move(str(src), str(dst))

    set_active_profile(target_slug)
    return target_slug
