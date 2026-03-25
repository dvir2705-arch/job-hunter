from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime, timedelta
import uuid


@dataclass
class ApplicationEvent:
    """Single event in application history."""
    date: str
    action: str  # applied, screening, interview, offer, rejected, withdrawn, follow_up, note
    note: str = ""


@dataclass
class Application:
    """Full application record with context."""
    # Job info
    job_title: str
    company: str
    location: str = ""
    job_url: str = ""
    source: str = ""  # workday, linkedin, amazon, manual

    # Status
    status: str = "applied"  # applied | screening | interview | offer | rejected | withdrawn
    applied_date: str = ""
    last_updated: str = ""
    follow_up_date: str = ""

    # Linked files
    cv_file: str = ""
    cover_letter_file: str = ""

    # Recruiter
    recruiter_name: str = ""
    recruiter_email: str = ""

    # Metadata
    id: str = ""
    notes: str = ""
    history: List[dict] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = uuid.uuid4().hex[:8]
        if not self.applied_date:
            self.applied_date = datetime.now().strftime("%Y-%m-%d")
        if not self.last_updated:
            self.last_updated = self.applied_date
        if not self.follow_up_date:
            follow_up = datetime.now() + timedelta(days=7)
            self.follow_up_date = follow_up.strftime("%Y-%m-%d")
        if not self.history:
            self.history = [{"date": self.applied_date, "action": "applied", "note": "Initial application"}]

    def reset_status(self, note: str = "") -> None:
        """Reset application back to 'applied' status. Used for corrections only."""
        self.status = "applied"
        self.last_updated = datetime.now().strftime("%Y-%m-%d")
        self.history.append({
            "date": self.last_updated,
            "action": "reset",
            "note": note or "Status reset to applied"
        })

    def update_status(self, new_status: str, note: str = "") -> None:
        """Update status and add to history."""
        self.status = new_status
        self.last_updated = datetime.now().strftime("%Y-%m-%d")
        self.history.append({
            "date": self.last_updated,
            "action": new_status,
            "note": note
        })

    def needs_follow_up(self) -> bool:
        """Check if follow-up is overdue."""
        if self.status in ("rejected", "withdrawn", "offer"):
            return False
        today = datetime.now().strftime("%Y-%m-%d")
        return today >= self.follow_up_date

    def days_since_applied(self) -> int:
        """Days since application was submitted."""
        applied = datetime.strptime(self.applied_date, "%Y-%m-%d")
        return (datetime.now() - applied).days

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Application":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


VALID_STATUSES = ["applied", "screening", "interview", "offer", "rejected", "withdrawn"]

VALID_TRANSITIONS = {
    "applied": ["screening", "interview", "rejected", "withdrawn"],
    "screening": ["interview", "rejected", "withdrawn"],
    "interview": ["offer", "rejected", "withdrawn"],
    "offer": ["withdrawn"],
    "rejected": [],
    "withdrawn": [],
}
