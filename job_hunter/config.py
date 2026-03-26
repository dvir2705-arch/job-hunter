import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", "./data"))
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "./output"))
    CV_DIR: Path = DATA_DIR / "cv"
    APPLICATIONS_FILE: Path = DATA_DIR / "applications" / "applications.json"
    TEMPLATES_DIR: Path = Path("./templates")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    HUNTER_API_KEY: str = os.getenv("HUNTER_API_KEY", "")

    @classmethod
    def validate(cls) -> None:
        if not cls.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")

    @classmethod
    def ensure_dirs(cls) -> None:
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.CV_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.APPLICATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
