from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class ApplicationStatus(Enum):
    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


@dataclass
class Application:
    id: str
    company: str
    position: str
    url: str
    status: ApplicationStatus = ApplicationStatus.APPLIED
    applied_date: str = field(default_factory=lambda: date.today().isoformat())
    notes: str = ""
    cv_version: Optional[str] = None
    salary_range: Optional[str] = None
    contact: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company": self.company,
            "position": self.position,
            "url": self.url,
            "status": self.status.value,
            "applied_date": self.applied_date,
            "notes": self.notes,
            "cv_version": self.cv_version,
            "salary_range": self.salary_range,
            "contact": self.contact,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Application":
        data = data.copy()
        data["status"] = ApplicationStatus(data.get("status", "applied"))
        return cls(**data)
