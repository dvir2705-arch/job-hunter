import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    HUNTER_API_KEY: str = os.getenv("HUNTER_API_KEY", "")
    TEMPLATES_DIR: Path = Path("./templates")

    # Base directories (root data dir, never changes — used for shared files)
    _BASE_DATA_DIR: Path = Path(os.getenv("DATA_DIR", "./data"))
    # Active data dir (may be overridden by set_user)
    DATA_DIR: Path = _BASE_DATA_DIR
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "./output"))

    # Derived data paths
    CV_DIR: Path = DATA_DIR / "cv"
    APPLICATIONS_FILE: Path = DATA_DIR / "applications" / "applications.json"
    JOBS_DIR: Path = DATA_DIR / "jobs"
    COMPANIES_FILE: Path = DATA_DIR / "jobs" / "companies.json"
    DISCOVERED_COMPANIES_FILE: Path = DATA_DIR / "jobs" / "discovered_companies.json"
    SCAN_HISTORY_FILE: Path = DATA_DIR / "jobs" / "scan_history.json"
    SCAN_CACHE_FILE: Path = DATA_DIR / "jobs" / "scan_cache.json"
    COVER_LETTER_DATA_DIR: Path = DATA_DIR / "cover_letters"
    COVER_LETTER_HISTORY_FILE: Path = DATA_DIR / "cover_letters" / "history.json"
    RECRUITERS_FILE: Path = DATA_DIR / "recruiters" / "recruiters.json"
    LOG_DIR: Path = DATA_DIR / "logs"

    # Derived output paths
    CV_OUTPUT_DIR: Path = OUTPUT_DIR / "adapted_cv"
    COVER_LETTER_OUTPUT_DIR: Path = OUTPUT_DIR / "cover_letters"

    # Legacy alias
    COVER_LETTER_DIR: Path = COVER_LETTER_OUTPUT_DIR

    # Active user (None = single-user mode, backward compatible)
    _active_user: str = None

    @classmethod
    def set_user(cls, user_id: str) -> None:
        """Switch to per-user data isolation.

        Rebases DATA_DIR to data/users/<user_id>/ and recalculates all
        derived paths. Shared registries (companies.json, templates/) stay
        at the root data/ level. Also invalidates the cached profile.
        """
        cls._active_user = user_id
        cls.DATA_DIR = cls._BASE_DATA_DIR / "users" / user_id
        cls._recalculate_paths()
        # Invalidate cached profile so next load reads from new DATA_DIR
        from job_hunter.profile import set_profile_path
        set_profile_path(None)

    @classmethod
    def _recalculate_paths(cls) -> None:
        """Recalculate all derived paths from current DATA_DIR / OUTPUT_DIR."""
        cls.CV_DIR = cls.DATA_DIR / "cv"
        cls.APPLICATIONS_FILE = cls.DATA_DIR / "applications" / "applications.json"
        cls.JOBS_DIR = cls.DATA_DIR / "jobs"
        cls.DISCOVERED_COMPANIES_FILE = cls.DATA_DIR / "jobs" / "discovered_companies.json"
        cls.SCAN_HISTORY_FILE = cls.DATA_DIR / "jobs" / "scan_history.json"
        cls.SCAN_CACHE_FILE = cls.DATA_DIR / "jobs" / "scan_cache.json"
        cls.COVER_LETTER_DATA_DIR = cls.DATA_DIR / "cover_letters"
        cls.COVER_LETTER_HISTORY_FILE = cls.DATA_DIR / "cover_letters" / "history.json"
        cls.RECRUITERS_FILE = cls.DATA_DIR / "recruiters" / "recruiters.json"
        cls.LOG_DIR = cls.DATA_DIR / "logs"
        cls.CV_OUTPUT_DIR = cls.OUTPUT_DIR / "adapted_cv"
        cls.COVER_LETTER_OUTPUT_DIR = cls.OUTPUT_DIR / "cover_letters"
        cls.COVER_LETTER_DIR = cls.COVER_LETTER_OUTPUT_DIR

    @classmethod
    def companies_file(cls) -> Path:
        """Return companies.json path — shared registry, always at root data/."""
        return cls._BASE_DATA_DIR / "jobs" / "companies.json"

    @classmethod
    def validate(cls) -> None:
        if not cls.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")

    @classmethod
    def ensure_dirs(cls) -> None:
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.CV_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.CV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.COVER_LETTER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.COVER_LETTER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.APPLICATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        cls.JOBS_DIR.mkdir(parents=True, exist_ok=True)
        cls.RECRUITERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
