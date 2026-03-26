"""User profile management — centralizes personal data for all modules."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from job_hunter.config import Config


@dataclass
class UserProfile:
    """Candidate profile loaded from data/user_profile.json."""

    name: str
    email: str
    phone: str
    linkedin: str = ""
    github: str = ""
    location: str = ""
    university: str = ""
    degree: str = ""
    specialization: str = ""
    cv_title: str = ""
    skills: List[str] = field(default_factory=list)
    skills_not: List[str] = field(default_factory=list)
    target_positions: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path = None) -> "UserProfile":
        """Load profile from JSON file.

        Args:
            path: Optional override; defaults to data/user_profile.json.

        Raises:
            FileNotFoundError: If profile file doesn't exist.
            ValueError: If required fields are missing.
        """
        if path is None:
            path = Config.DATA_DIR / "user_profile.json"

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for required in ("name", "email", "phone"):
            if not data.get(required):
                raise ValueError(f"Missing required profile field: {required}")

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def signature_block(self) -> str:
        """Return formatted name + contact for email/letter sign-off."""
        return f"{self.name}\n{self.email} | {self.phone}"


# Module-level cached instance
_profile: UserProfile = None


def get_profile(path: Path = None) -> UserProfile:
    """Return cached UserProfile, loading on first call."""
    global _profile
    if _profile is None:
        _profile = UserProfile.load(path)
    return _profile
