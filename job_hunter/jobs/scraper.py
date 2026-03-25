import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Optional

from job_hunter.logger import get_logger

logger = get_logger(__name__)


@dataclass
class JobListing:
    title: str
    company: str
    location: str
    url: str
    posted: str = ""

    def __str__(self):
        posted = f" ({self.posted})" if self.posted else ""
        return f"{self.title} | {self.company} | {self.location}{posted}\n  {self.url}"


# ---------------------------------------------------------------------------
# Base Workday scraper — reused by Intel, NVIDIA, Marvell
# ---------------------------------------------------------------------------

class WorkdayScraper:
    """Generic scraper for companies using the Workday ATS JSON API."""

    API_URL: str = ""
    JOB_BASE_URL: str = ""
    COMPANY_NAME: str = ""

    HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    def search(self, query: str, location: str = "Israel", max_results: int = 20) -> List[JobListing]:
        payload = {
            "appliedFacets": {},
            "limit": 20,   # Always fetch Workday's maximum; filter after
            "offset": 0,
            "searchText": query,
        }

        try:
            response = requests.post(
                self.API_URL,
                headers=self.HEADERS,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error("%s request failed: %s", self.COMPANY_NAME, e)
            return []

        data = response.json()
        postings = data.get("jobPostings", [])

        jobs = []
        for post in postings:
            loc = post.get("locationsText", "")
            if location and location.lower() not in loc.lower():
                continue

            external_path = post.get("externalPath", "")
            if not external_path:
                continue

            url = f"{self.JOB_BASE_URL}{external_path}"
            jobs.append(JobListing(
                title=post.get("title", "Unknown"),
                company=self.COMPANY_NAME,
                location=loc,
                url=url,
            ))

            if len(jobs) >= max_results:
                break

        return jobs


# ---------------------------------------------------------------------------
# Company-specific scrapers
# ---------------------------------------------------------------------------

class IntelScraper(WorkdayScraper):
    API_URL = "https://intel.wd1.myworkdayjobs.com/wday/cxs/intel/External/jobs"
    JOB_BASE_URL = "https://intel.wd1.myworkdayjobs.com/External"
    COMPANY_NAME = "Intel"


class NVIDIAScraper(WorkdayScraper):
    API_URL = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"
    JOB_BASE_URL = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"
    COMPANY_NAME = "NVIDIA"


class MarvellScraper(WorkdayScraper):
    API_URL = "https://marvell.wd1.myworkdayjobs.com/wday/cxs/marvell/MarvellCareers/jobs"
    JOB_BASE_URL = "https://marvell.wd1.myworkdayjobs.com/MarvellCareers"
    COMPANY_NAME = "Marvell"


class AmazonScraper:
    """Scrapes Amazon/Annapurna Labs jobs via the amazon.jobs JSON search API."""

    API_URL = "https://www.amazon.jobs/en/search.json"
    JOB_BASE_URL = "https://www.amazon.jobs"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    def search(self, query: str, location: str = "Israel", max_results: int = 20) -> List[JobListing]:
        params = {
            "base_query": query,
            "loc_query": location,
            "country": "ISR",
            "result_limit": max_results,
        }

        try:
            response = requests.get(
                self.API_URL,
                params=params,
                headers=self.HEADERS,
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error("Amazon request failed: %s", e)
            return []

        data = response.json()
        jobs = []
        for post in data.get("jobs", []):
            job_path = post.get("job_path", "")
            if not job_path:
                continue

            jobs.append(JobListing(
                title=post.get("title", "Unknown"),
                company=post.get("company_name", "Amazon"),
                location=post.get("location", ""),
                url=f"{self.JOB_BASE_URL}{job_path}",
            ))

        return jobs


class LinkedInScraper:
    """Scrapes LinkedIn public job search page (no login required).
    Uses the guest search endpoint which returns server-rendered HTML with job cards.
    """

    SEARCH_URL = "https://www.linkedin.com/jobs/search/"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def search(self, query: str, location: str = "Israel", max_results: int = 25) -> List[JobListing]:
        try:
            response = requests.get(
                self.SEARCH_URL,
                params={"keywords": query, "location": location},
                headers=self.HEADERS,
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error("LinkedIn request failed: %s", e)
            return []

        if "authwall" in response.url or "login" in response.url:
            raise RuntimeError("LinkedIn redirected to login — guest access blocked.")

        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.find_all("div", class_="job-search-card")

        if not cards:
            raise RuntimeError(
                f"No job cards found in LinkedIn response ({len(soup.find_all('div'))} divs). "
                "LinkedIn may have changed their HTML structure."
            )

        jobs = []
        for card in cards[:max_results]:
            title_el    = card.find("h3", class_="base-search-card__title")
            company_el  = card.find("h4", class_="base-search-card__subtitle")
            location_el = card.find("span", class_="job-search-card__location")
            date_el     = card.find("time")
            link_el     = card.find("a", class_="base-card__full-link")

            if not title_el or not link_el:
                continue

            # Strip tracking query params — keep only the clean job URL
            raw_url = link_el.get("href", "")
            clean_url = raw_url.split("?")[0] if raw_url else ""
            if not clean_url.startswith("http"):
                continue

            jobs.append(JobListing(
                title=title_el.get_text(strip=True),
                company=company_el.get_text(strip=True) if company_el else "Unknown",
                location=location_el.get_text(strip=True) if location_el else "Unknown",
                url=clean_url,
                posted=date_el.get("datetime", "") if date_el else "",
            ))

        return jobs


# ---------------------------------------------------------------------------
# Greenhouse ATS scraper — reused by Wix and future Greenhouse companies
# ---------------------------------------------------------------------------

class GreenhouseScraper:
    """Generic scraper for companies using the Greenhouse ATS public JSON API."""

    API_URL = "https://boards-api.greenhouse.io/v1/boards/{board_id}/jobs"

    def __init__(self, company_name: str, board_id: str):
        self.company_name = company_name
        self.board_id = board_id
        self.COMPANY_NAME = company_name  # for JobScanner error reporting

    def search(self, query: str = "", location: str = "Israel", max_results: int = 20) -> List[JobListing]:
        url = self.API_URL.format(board_id=self.board_id)
        try:
            response = requests.get(url, params={"content": "true"}, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            logger.error("Greenhouse API error for %s: %s", self.company_name, e)
            return []

        jobs = []
        for job in data.get("jobs", []):
            job_location = job.get("location", {}).get("name", "")
            title = job.get("title", "")

            if location and location.lower() not in job_location.lower():
                continue
            if query and query.lower() not in title.lower():
                continue

            jobs.append(JobListing(
                title=title,
                company=self.company_name,
                location=job_location,
                url=job.get("absolute_url", ""),
                posted=job.get("updated_at", "")[:10] if job.get("updated_at") else "",
            ))

            if len(jobs) >= max_results:
                break

        return jobs


class WixScraper(GreenhouseScraper):
    """Scraper for Wix careers (Greenhouse ATS, board_id='wix')."""

    def __init__(self):
        super().__init__(company_name="Wix", board_id="wix")


# ---------------------------------------------------------------------------
# Companies investigated but not yet accessible
#
# Apple     — Workday HTTP 500 (tenant misconfiguration or geo-block)
# Qualcomm  — Workday HTTP 500
# Mobileye  — Workday HTTP 401; own portal (careers.mobileye.com) is JS-rendered
# Broadcom  — DNS resolution fails for careers.broadcom.com
# Microsoft — gcsservices API returns 502; likely geo-blocked or requires session
# Google    — Fully custom JS portal, no public API found
#
# Startups / other investigated:
# Wix       — careers.wix.com is a Wix site itself (JS-rendered); SmartRecruiters/Ashby/Greenhouse all 404
# Hailo     — JS-rendered careers page, no public API found
# Arbe      — DNS resolution failed
# Vayyar    — Workable ATS, API requires account auth
# Innoviz   — Monday.com ATS, no public API
# Run:AI    — Acquired by NVIDIA, redirects to nvidia.com
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Job scanner — runs all working scrapers and combines results
# ---------------------------------------------------------------------------

class JobScanner:
    """Runs all available scrapers and returns a combined, deduplicated list."""

    SCRAPERS = [
        IntelScraper(),
        NVIDIAScraper(),
        MarvellScraper(),
        AmazonScraper(),
        LinkedInScraper(),
        # WixScraper excluded: careers.wix.com is JS-rendered, no public API found
    ]

    def scan(self, query: str = "student", location: str = "Israel", max_per_company: int = 20) -> List[JobListing]:
        all_jobs = []
        errors = []

        for scraper in self.SCRAPERS:
            try:
                jobs = scraper.search(query, location, max_results=max_per_company)
                all_jobs.extend(jobs)
            except RuntimeError as e:
                errors.append(f"{getattr(scraper, 'COMPANY_NAME', type(scraper).__name__)}: {e}")

        if errors:
            for err in errors:
                logger.warning(err)

        # Deduplicate by URL
        seen = set()
        unique = []
        for job in all_jobs:
            if job.url not in seen:
                seen.add(job.url)
                unique.append(job)

        return unique


# ---------------------------------------------------------------------------
# Job description fetcher
# ---------------------------------------------------------------------------

_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_job_description(job: "JobListing") -> Optional[str]:
    """Fetch job description. Falls back to web search if direct fetch fails."""
    description = _fetch_from_url(job.url)
    if description:
        return description

    description = _fetch_via_search(job.title, job.company)
    if description:
        return description

    return None


def _fetch_from_url(url: str) -> Optional[str]:
    """Fetch job description directly from the job URL."""
    try:
        r = requests.get(url, headers=_FETCH_HEADERS, timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.error("Could not fetch job page %s: %s", url, e)
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # LinkedIn public job page
    if "linkedin.com" in url:
        el = soup.find("div", class_="show-more-less-html__markup")
        if el:
            return el.get_text(separator="\n", strip=True)

    # Amazon / Annapurna Labs job page
    if "amazon.jobs" in url:
        rows = soup.find_all("div", class_="row")
        for row in rows:
            text = row.get_text(separator="\n", strip=True)
            if len(text) > 500:
                return text

    # Workday — JS-rendered; use the CXS detail API instead
    if "myworkdayjobs.com" in url:
        return _fetch_workday_description(url)

    # Generic fallback: find the longest div > 300 chars
    candidates = [
        t for t in soup.find_all("div")
        if len(t.get_text(strip=True)) > 300
    ]
    if candidates:
        best = max(candidates, key=lambda t: len(t.get_text(strip=True)))
        return best.get_text(separator="\n", strip=True)

    return None


def _fetch_workday_description(url: str) -> Optional[str]:
    """Fetch job description from Workday via the CXS detail API.

    Workday job URL:  https://{host}/{site}/job/...
    CXS detail URL:   https://{host}/wday/cxs/{tenant}/{site}/job/...
    Tenant = first segment of the hostname (e.g. 'intel' from 'intel.wd1.myworkdayjobs.com').
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.netloc                    # e.g. intel.wd1.myworkdayjobs.com
    tenant = host.split(".")[0]             # e.g. intel
    path = parsed.path                      # e.g. /External/job/Israel-Haifa/...

    cxs_url = f"https://{host}/wday/cxs/{tenant}{path}"

    try:
        r = requests.get(
            cxs_url,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        html_desc = r.json().get("jobPostingInfo", {}).get("jobDescription", "")
        if not html_desc:
            return None
        # Strip HTML tags
        soup = BeautifulSoup(html_desc, "html.parser")
        return soup.get_text(separator="\n", strip=True)
    except Exception as e:
        logger.warning("Workday detail API failed for %s: %s", url, e)
        return None


def _fetch_via_search(title: str, company: str) -> Optional[str]:
    """Search for job description via DuckDuckGo and fetch from results."""
    import urllib.parse

    query = f"{title} {company} job description"
    search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"

    try:
        response = requests.get(
            search_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=10,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for link in soup.find_all("a", class_="result__a"):
            href = link.get("href", "")

            if "linkedin.com/jobs/view" in href:
                logger.info("Found LinkedIn link via DuckDuckGo: %s", href)
                desc = _fetch_from_url_direct(href)
                if desc:
                    return desc

            if "glassdoor.com/job" in href:
                logger.info("Found Glassdoor link via DuckDuckGo: %s", href)
                desc = _fetch_from_url_direct(href)
                if desc:
                    return desc

        logger.info("No job description links found in DuckDuckGo results for: %s at %s", title, company)
        return None

    except Exception as e:
        logger.warning("DuckDuckGo search fallback failed: %s", e)
        return None


def _fetch_from_url_direct(url: str) -> Optional[str]:
    """Fetch job description from a LinkedIn or Glassdoor URL."""
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=10,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        if "linkedin.com" in url:
            el = soup.find("div", class_="show-more-less-html__markup")
            if el:
                return el.get_text(separator="\n", strip=True)

        if "glassdoor.com" in url:
            el = soup.find("div", class_="jobDescriptionContent")
            if el:
                return el.get_text(separator="\n", strip=True)

        return None
    except Exception as e:
        logger.warning("Failed to fetch from %s: %s", url, e)
        return None


# ---------------------------------------------------------------------------
# Legacy scrapers (blocked — kept for future Selenium upgrade)
# ---------------------------------------------------------------------------

class IndeedScraper:
    BASE_URL = "https://il.indeed.com"
    SEARCH_URL = f"{BASE_URL}/jobs"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def search(self, query: str, location: str = "Israel", max_results: int = 20) -> List[JobListing]:
        try:
            response = requests.get(
                self.SEARCH_URL,
                params={"q": query, "l": location},
                headers=self.HEADERS,
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"Request failed: {e}")

        soup = BeautifulSoup(response.text, "html.parser")

        if "captcha" in response.url or "sorry" in response.url:
            raise RuntimeError("Indeed returned a captcha page — scraping blocked.")
        if len(soup.find_all("div")) < 10:
            raise RuntimeError("Indeed returned an unexpected page — possibly blocked.")

        job_cards = soup.find_all("div", class_="job_seen_beacon")
        if not job_cards:
            job_cards = soup.find_all("li", attrs={"class": lambda c: c and "job" in c.lower()})

        jobs = []
        for card in job_cards[:max_results]:
            title_el = card.find("h2", class_="jobTitle")
            company_el = card.find("span", {"data-testid": "company-name"})
            location_el = card.find("div", {"data-testid": "text-location"})
            link_el = card.find("a", href=True)

            if not title_el or not link_el:
                continue

            href = link_el["href"]
            url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
            if not url.startswith("http"):
                continue

            jobs.append(JobListing(
                title=title_el.get_text(strip=True),
                company=company_el.get_text(strip=True) if company_el else "Unknown",
                location=location_el.get_text(strip=True) if location_el else "Unknown",
                url=url,
            ))

        return jobs


class GlassdoorScraper:
    BASE_URL = "https://www.glassdoor.com"
    SEARCH_URL = f"{BASE_URL}/Job/jobs.htm"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.google.com/",
    }

    def search(self, query: str, location: str = "Israel", max_results: int = 20) -> List[JobListing]:
        try:
            response = requests.get(
                self.SEARCH_URL,
                params={"sc.keyword": query, "locT": "N", "locKeyword": location},
                headers=self.HEADERS,
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"Request failed: {e}")

        if response.status_code == 403 or "cf-browser-verification" in response.text:
            raise RuntimeError("Glassdoor is protected by Cloudflare — scraping blocked.")
        if "challenge" in response.url or "captcha" in response.url:
            raise RuntimeError("Glassdoor returned a challenge/captcha page — scraping blocked.")

        soup = BeautifulSoup(response.text, "html.parser")

        if len(soup.find_all("div")) < 10:
            raise RuntimeError("Glassdoor returned an unexpected page — possibly blocked.")

        job_cards = soup.find_all("li", {"class": lambda c: c and "JobsList_jobListItem" in " ".join(c)})
        if not job_cards:
            job_cards = soup.find_all("article", {"class": lambda c: c and "job" in " ".join(c).lower()})
        if not job_cards:
            job_cards = soup.find_all("li", {"data-test": "jobListing"})

        if not job_cards:
            raise RuntimeError(
                f"No job cards found in Glassdoor response. "
                f"The page may be JavaScript-rendered (got {len(soup.find_all('div'))} divs). "
                f"requests+BeautifulSoup cannot execute JavaScript — a browser-based tool is needed."
            )

        jobs = []
        for card in job_cards[:max_results]:
            title_el = (
                card.find("a", {"data-test": "job-title"}) or
                card.find(attrs={"class": lambda c: c and "JobCard_jobTitle" in " ".join(c)})
            )
            company_el = (
                card.find("span", {"class": lambda c: c and "EmployerProfile_compactEmployerName" in " ".join(c)}) or
                card.find(attrs={"data-test": "employer-name"})
            )
            location_el = card.find(attrs={"data-test": "emp-location"})
            link_el = card.find("a", href=True)

            if not title_el or not link_el:
                continue

            href = link_el["href"]
            url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
            if not url.startswith("http"):
                continue

            jobs.append(JobListing(
                title=title_el.get_text(strip=True),
                company=company_el.get_text(strip=True) if company_el else "Unknown",
                location=location_el.get_text(strip=True) if location_el else "Unknown",
                url=url,
            ))

        return jobs
