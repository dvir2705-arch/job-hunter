"""Hunter.io API integration for finding recruiter emails."""

import json

import requests

from job_hunter.config import Config
from job_hunter.logger import get_logger

logger = get_logger(__name__)


def _load_company_domains() -> dict[str, str]:
    """Load company name → email domain mapping from companies.json."""
    companies_file = Config.companies_file()
    if not companies_file.exists():
        return {}
    try:
        with open(companies_file, encoding="utf-8") as f:
            data = json.load(f)
        return {
            c["name"].lower(): c["email_domain"]
            for c in data.get("companies", [])
            if c.get("email_domain")
        }
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to load company domains from %s: %s", companies_file, e)
        return {}


def get_domain_for_company(company_name: str) -> str:
    """Return the email domain for a company name."""
    name_lower = company_name.lower()
    domains = _load_company_domains()
    for key, domain in domains.items():
        if key in name_lower or name_lower in key:
            return domain
    # Fallback: first word + .com
    simple = name_lower.split()[0].rstrip(".,")
    return f"{simple}.com"


class HunterAPI:
    BASE_URL = "https://api.hunter.io/v2"

    def __init__(self):
        self.api_key = Config.HUNTER_API_KEY
        if not self.api_key:
            raise ValueError("HUNTER_API_KEY not set in .env")

    def domain_search(self, domain: str, limit: int = 10) -> dict:
        """Search for emails at a domain."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/domain-search",
                params={
                    "domain": domain,
                    "api_key": self.api_key,
                    "limit": limit,
                    "type": "personal",
                },
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
            logger.error("Hunter.io domain_search failed for %s: %s", domain, e)
            return {"error": str(e), "domain": domain, "emails": []}

    def get_quota(self) -> dict:
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
        except requests.RequestException as e:
            logger.error("Hunter.io get_quota failed: %s", e)
            return {"error": "Could not fetch quota"}
