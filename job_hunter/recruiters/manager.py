"""Manage recruiter contacts database."""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

from job_hunter.config import Config


@dataclass
class Recruiter:
    name: str
    email: str
    company: str
    linkedin: str = ""
    role: str = ""
    notes: str = ""
    added_at: str = ""


class RecruiterManager:
    def __init__(self):
        self.file = Config.RECRUITERS_FILE
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        if self.file.exists():
            with open(self.file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {"recruiters": {}}

    def _save(self):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def add(
        self,
        company: str,
        name: str,
        email: str,
        linkedin: str = "",
        role: str = "",
        notes: str = "",
    ) -> Recruiter:
        """Add or update a recruiter (keyed by email)."""
        if company not in self.data["recruiters"]:
            self.data["recruiters"][company] = []

        entry = {
            "name": name,
            "email": email,
            "linkedin": linkedin,
            "role": role,
            "notes": notes,
            "added_at": datetime.now().strftime("%Y-%m-%d"),
        }

        existing = [r for r in self.data["recruiters"][company] if r["email"] == email]
        if existing:
            idx = self.data["recruiters"][company].index(existing[0])
            self.data["recruiters"][company][idx] = entry
        else:
            self.data["recruiters"][company].append(entry)

        self._save()
        return Recruiter(company=company, **entry)

    def get_by_company(self, company: str) -> List[Dict]:
        """Exact company name lookup."""
        return self.data["recruiters"].get(company, [])

    def find_by_company_fuzzy(self, company: str) -> List[Dict]:
        """Case-insensitive partial match, returns dicts with 'company' field added."""
        company_lower = company.lower()
        results = []
        for comp, recruiters in self.data["recruiters"].items():
            if company_lower in comp.lower() or comp.lower() in company_lower:
                for r in recruiters:
                    results.append({"company": comp, **r})
        return results

    def list_all(self) -> Dict[str, List[Dict]]:
        return self.data["recruiters"]

    def remove(self, company: str, email: str) -> bool:
        """Remove a recruiter by email. Returns True if found and removed."""
        if company not in self.data["recruiters"]:
            return False
        before = len(self.data["recruiters"][company])
        self.data["recruiters"][company] = [
            r for r in self.data["recruiters"][company] if r["email"] != email
        ]
        if len(self.data["recruiters"][company]) < before:
            self._save()
            return True
        return False

    def get_stats(self) -> Dict:
        total = sum(len(recs) for recs in self.data["recruiters"].values())
        companies_with_recruiters = sum(
            1 for recs in self.data["recruiters"].values() if recs
        )
        return {
            "total_recruiters": total,
            "companies_with_recruiters": companies_with_recruiters,
            "total_companies": len(self.data["recruiters"]),
        }
