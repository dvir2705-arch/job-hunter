"""Hunter.io API integration for finding recruiter emails."""

import requests
from typing import Dict

from job_hunter.config import Config
from job_hunter.logger import get_logger

logger = get_logger(__name__)

COMPANY_DOMAINS = {
    "intel": "intel.com",
    "nvidia": "nvidia.com",
    "amazon": "amazon.com",
    "annapurna labs": "amazon.com",
    "marvell": "marvell.com",
    "wix": "wix.com",
    "microsoft": "microsoft.com",
    "google": "google.com",
    "apple": "apple.com",
    "qualcomm": "qualcomm.com",
    "broadcom": "broadcom.com",
    "applied materials": "amat.com",
    "analog devices": "analog.com",
    "tower semiconductor": "towersemi.com",
    "sandisk": "sandisk.com",
    "samsung": "samsung.com",
    "ibm": "ibm.com",
    "cisco": "cisco.com",
    "elbit": "elbitsystems.com",
    "gm": "gm.com",
    "vayyar": "vayyar.com",
    "arbe": "arberobotics.com",
    "ceragon": "ceragon.com",
    "valens": "valens.com",
    "nextsilicon": "nextsilicon.com",
    "hailo": "hailotech.com",
    "base44": "base44.com",
    "imagen": "imagen-ai.com",
    "siemens": "siemens.com",
    "texas instruments": "ti.com",
    "nanox": "nanox.vision",
    "stratasys": "stratasys.com",
    "mobileye": "mobileye.com",
    "experis": "experis.com",
}


def get_domain_for_company(company_name: str) -> str:
    """Return the email domain for a company name."""
    name_lower = company_name.lower()
    for key, domain in COMPANY_DOMAINS.items():
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
            logger.error("Hunter.io domain_search failed for %s: %s", domain, e)
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
        except requests.RequestException as e:
            logger.error("Hunter.io get_quota failed: %s", e)
            return {"error": "Could not fetch quota"}
