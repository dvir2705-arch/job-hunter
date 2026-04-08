"""Cover letter history management for comparison and learning."""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, asdict

from job_hunter.config import Config


@dataclass
class CoverLetterRecord:
    """A stored cover letter with metadata."""
    id: str
    job_title: str
    company: str
    language: str
    content: str
    job_description: str
    created_at: str
    file_path: str
    critique: Optional[str] = None
    score: Optional[int] = None


class CoverLetterHistory:
    """Manages cover letter history for comparison and improvement."""

    def __init__(self):
        self.data_dir = Config.COVER_LETTER_DATA_DIR
        self.output_dir = Config.COVER_LETTER_OUTPUT_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.data_dir / "history.json"
        self._load_history()

    def _load_history(self):
        """Load history from JSON file."""
        if self.history_file.exists():
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.records = [
                    CoverLetterRecord(**{k: v for k, v in r.items() if k != "mentioned_job_hunter"})
                    for r in data.get("records", [])
                ]
        else:
            self.records = []

    def _save_history(self):
        """Save history to JSON file."""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump({"records": [asdict(r) for r in self.records]}, f, indent=2, ensure_ascii=False)

    def save(self,
             job_title: str,
             company: str,
             language: str,
             content: str,
             job_description: str) -> CoverLetterRecord:
        """Save a new cover letter to history."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        company_slug = company.lower().replace(" ", "_").replace("/", "_")[:20]
        title_slug = job_title.lower().replace(" ", "_").replace("/", "_")[:25]

        record_id = f"{company_slug}_{title_slug}_{timestamp}"
        filename = f"cover_letter_{record_id}.txt"
        file_path = self.output_dir / filename

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        record = CoverLetterRecord(
            id=record_id,
            job_title=job_title,
            company=company,
            language=language,
            content=content,
            job_description=job_description,
            created_at=datetime.now().isoformat(),
            file_path=str(file_path),
        )

        self.records.append(record)
        self._save_history()

        return record

    def get_recent(self, limit: int = 5) -> List[CoverLetterRecord]:
        """Get the most recent cover letters."""
        return sorted(self.records, key=lambda r: r.created_at, reverse=True)[:limit]

    def get_by_company(self, company: str) -> List[CoverLetterRecord]:
        """Get all cover letters for a specific company."""
        return [r for r in self.records if company.lower() in r.company.lower()]

    def get_by_id(self, record_id: str) -> Optional[CoverLetterRecord]:
        """Get a specific cover letter by ID."""
        for r in self.records:
            if r.id == record_id:
                return r
        return None

    def get_all(self) -> List[CoverLetterRecord]:
        """Get all cover letters."""
        return self.records

    def update_critique(self, record_id: str, critique: str, score: int = None) -> bool:
        """Update a record with critique feedback."""
        for r in self.records:
            if r.id == record_id:
                r.critique = critique
                if score:
                    r.score = score
                self._save_history()
                return True
        return False
