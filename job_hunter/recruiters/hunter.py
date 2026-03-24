"""Hunter.io API integration for finding recruiter emails."""

import requests
from typing import Dict

from job_hunter.config import Config


class HunterAPI:
    BASE_URL = "https://api.hunter.io/v2"

    def __init__(self):
        self.api_key = Config.HUNTER_API_KEY
        if not self.api_key:
            raise ValueError("HUNTER_API_KEY not set in .env")

    def domain_search(self, domain: str, limit: int = 10) -> Dict:
        """Search for emails at a domain."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/domain-search",
                params={"domain": domain, "api_key": self.api_key,
                        "limit": limit, "type": "personal"},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json().get("data", {})
            return {
                "domain": domain,
                "pattern": data.get("pattern", ""),
                "emails": [
                    {
                        "email": e.get("value", ""),
                        "name": f"{e.get('first_name', '')} {e.get('last_name', '')}".strip(),
                        "position": e.get("position", ""),
                        "confidence": e.get("confidence", 0),
                    }
                    for e in data.get("emails", [])
                ],
            }
        except requests.RequestException as e:
            return {"error": str(e), "domain": domain, "emails": []}

    def get_quota(self) -> Dict:
        """Check remaining API quota."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/account",
                params={"api_key": self.api_key},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json().get("data", {})
            searches = data.get("requests", {}).get("searches", {})
            return {
                "used": searches.get("used", 0),
                "available": searches.get("available", 0),
            }
        except requests.RequestException:
            return {"error": "Could not fetch quota"}
