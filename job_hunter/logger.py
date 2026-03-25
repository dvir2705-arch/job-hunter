import logging
from pathlib import Path

LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(LOG_DIR / "job_hunter.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(fh)
        logger.addHandler(ch)
    return logger
