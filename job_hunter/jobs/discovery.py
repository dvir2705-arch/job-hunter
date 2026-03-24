"""Automatic company discovery from job listings."""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

from .scraper import JobListing

DISCOVERED_FILE = Path("data/jobs/discovered_companies.json")
COMPANIES_FILE = Path("data/jobs/companies.json")

RELEVANT_KEYWORDS = [
    "chip", "asic", "fpga", "verification", "rtl", "digital design",
    "analog", "rf", "signal", "embedded", "firmware", "hardware",
    "ai", "ml", "deep learning", "neural", "inference",
    "semiconductor", "silicon", "processor", "architecture",
    "python", "software", "algorithm", "dsp",
]

IRRELEVANT_KEYWORDS = [
    "marketing", "sales", "hr", "recruiter", "finance", "accounting",
    "legal", "admin", "customer success", "support",
]


class CompanyDiscovery:
    """Tracks companies found in scans that are not yet in companies.json."""

    def __init__(self):
        self.discovered_file = DISCOVERED_FILE
        self.discovered_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()
        self._load_known_companies()

    def _load(self):
        if self.discovered_file.exists():
            with open(self.discovered_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {
                "last_updated": None,
                "discovered": {},
                "added_to_main": [],
                "ignored": [],
            }

    def _save(self):
        self.data["last_updated"] = datetime.now().isoformat()
        with open(self.discovered_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def _load_known_companies(self):
        if COMPANIES_FILE.exists():
            with open(COMPANIES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.known_companies = {c["name"].lower() for c in data.get("companies", [])}
        else:
            self.known_companies = set()

    def _calculate_relevance(self, job_titles: List[str]) -> str:
        text = " ".join(job_titles).lower()
        relevant_hits = sum(1 for kw in RELEVANT_KEYWORDS if kw in text)
        irrelevant_hits = sum(1 for kw in IRRELEVANT_KEYWORDS if kw in text)

        if relevant_hits >= 2:
            return "high"
        elif relevant_hits >= 1 and irrelevant_hits == 0:
            return "medium"
        elif irrelevant_hits >= 1 and relevant_hits == 0:
            return "low"
        else:
            return "unknown"

    def process_jobs(self, jobs: List[JobListing]) -> Dict[str, int]:
        """Process job listings, track unknown companies. Returns {"new": N, "updated": N}."""
        stats = {"new": 0, "updated": 0}

        for job in jobs:
            company = job.company.strip()
            company_lower = company.lower()

            if company_lower in self.known_companies:
                continue
            if company in self.data.get("ignored", []):
                continue
            if company in self.data.get("added_to_main", []):
                continue

            if company not in self.data["discovered"]:
                self.data["discovered"][company] = {
                    "first_seen": datetime.now().isoformat(),
                    "times_seen": 0,
                    "job_titles": [],
                    "locations": [],
                    "source": getattr(job, "source", "linkedin"),
                    "relevance_score": "unknown",
                    "status": "pending",
                }
                stats["new"] += 1
            else:
                stats["updated"] += 1

            entry = self.data["discovered"][company]
            entry["times_seen"] += 1
            if job.title not in entry["job_titles"]:
                entry["job_titles"].append(job.title)
            if job.location and job.location not in entry["locations"]:
                entry["locations"].append(job.location)
            entry["relevance_score"] = self._calculate_relevance(entry["job_titles"])

        self._save()
        return stats

    def get_pending(self, relevance: str = None) -> List[Dict]:
        """Return pending companies sorted by relevance then times_seen."""
        order = {"high": 0, "medium": 1, "unknown": 2, "low": 3}
        results = []
        for name, info in self.data["discovered"].items():
            if info["status"] != "pending":
                continue
            if relevance and info["relevance_score"] != relevance:
                continue
            results.append({"name": name, **info})
        results.sort(key=lambda x: (order.get(x["relevance_score"], 99), -x["times_seen"]))
        return results

    def mark_ignored(self, company: str):
        if company in self.data["discovered"]:
            self.data["discovered"][company]["status"] = "ignored"
        if company not in self.data["ignored"]:
            self.data["ignored"].append(company)
        self._save()

    def mark_added(self, company: str):
        if company in self.data["discovered"]:
            self.data["discovered"][company]["status"] = "added"
        if company not in self.data["added_to_main"]:
            self.data["added_to_main"].append(company)
        self._save()

    def add_to_companies_json(self, company: str) -> bool:
        """Append a basic stub entry to companies.json and mark as added.

        Returns True on success, False if company already exists there.
        """
        if not COMPANIES_FILE.exists():
            return False

        with open(COMPANIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Guard: don't duplicate
        existing_names = {c["name"].lower() for c in data.get("companies", [])}
        if company.lower() in existing_names:
            return False

        entry = self.data["discovered"].get(company, {})
        stub = {
            "name": company,
            "career_url": "",
            "locations": list(set(entry.get("locations", []))),
            "domain": [],
            "ats": "unknown",
            "scraper": "todo",
            "target_keywords": ["student", "intern"],
            "notes": f"Auto-discovered via {entry.get('source', 'scan')}. "
                     f"Seen {entry.get('times_seen', 1)}x. "
                     f"Sample roles: {', '.join(entry.get('job_titles', [])[:2])}",
        }

        data.setdefault("companies", []).append(stub)

        with open(COMPANIES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.mark_added(company)
        # Refresh known companies so subsequent calls in the same session are correct
        self.known_companies.add(company.lower())
        return True

    def get_stats(self) -> Dict:
        pending = [c for c in self.data["discovered"].values() if c["status"] == "pending"]
        return {
            "total_discovered": len(self.data["discovered"]),
            "pending_review": len(pending),
            "high_relevance": sum(1 for c in pending if c["relevance_score"] == "high"),
            "added_to_main": len(self.data.get("added_to_main", [])),
            "ignored": len(self.data.get("ignored", [])),
        }
