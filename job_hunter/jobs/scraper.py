import time
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

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
# Location matcher — LinkedIn/JobSpy frequently return Israeli jobs with
# just a city ("Tel Aviv") or country code ("IL, Haifa") instead of the
# full country name. A strict substring match would drop legitimate local
# jobs, so we accept country name, ISO code, and common city names.
# Workday/Greenhouse/Amazon scrapers don't need this — their APIs return
# structured location data that always includes the country.
# ---------------------------------------------------------------------------

COUNTRY_LOCATION_ALIASES = {
    # NOTE: "IL" is intentionally NOT an alias — it clashes with Illinois,
    # so "Chicago, IL" would incorrectly match Israel. Amazon's "IL, Tel Aviv"
    # format is still caught via the city-name aliases below.
    "israel": [
        "israel",
        "tel aviv", "tel-aviv", "haifa", "jerusalem", "herzliya",
        "petah tikva", "petah-tikva", "petach tikva", "petach-tikva",
        "ramat gan", "netanya", "yokneam", "yoqneam",
        "kiryat gat", "kiryat-gat", "kiryat ono", "kiryat motzkin",
        "rehovot", "beer sheva", "be'er sheva", "beersheba",
        "kfar saba", "raanana", "ra'anana", "rishon le",
        "holon", "bat yam", "ashdod", "ashkelon", "nazareth",
        "lod", "modi'in", "modiin",
        "ramat hasharon", "givatayim", "hod hasharon", "or yehuda",
        "tiberias", "eilat", "ness ziona", "nes ziona",
        "caesarea", "binyamina", "karmiel", "carmiel",
        "airport city", "rosh ha'ayin", "rosh haayin",
        "zichron ya'akov", "zichron yaakov",
        "pardes hanna", "atlit", "tzfat", "safed",
        "givat shmuel", "yehud", "kfar vradim",
    ],
}


# ---------------------------------------------------------------------------
# Server-side location hints — LinkedIn's `location` URL param and JobSpy's
# default `country_indeed` are advisory. Passing the proper geoId / country
# name forces true country filtering instead of worldwide ranking.
# ---------------------------------------------------------------------------

LINKEDIN_GEOIDS = {
    "israel": "101620260",
    "united states": "103644278",
    "usa": "103644278",
    "united kingdom": "101165590",
    "uk": "101165590",
    "germany": "101282230",
    "france": "105015875",
    "india": "102713980",
    "canada": "101174742",
    "australia": "101452733",
}

JOBSPY_INDEED_COUNTRIES = {
    "israel": "israel",
    "united states": "usa",
    "usa": "usa",
    "united kingdom": "uk",
    "uk": "uk",
    "germany": "germany",
    "france": "france",
    "india": "india",
    "canada": "canada",
    "australia": "australia",
}


def _country_key(location: str) -> str:
    """Extract the country segment from a location string (last comma-split part)."""
    if not location:
        return ""
    return location.split(",")[-1].strip().lower()


def _location_matches_country(requested: str, actual: str, title: str = "") -> bool:
    """Return True if the job's location is a plausible match for the country.

    Empty requested → no filter (accept).
    Non-empty actual → must contain the country name or a known city alias.
    Empty actual → fall back to title (JobSpy often returns Israeli postings
        with no location field but the city in the title, e.g. Apple's
        'Verification Student- Jerusalem'). Without this fallback we drop
        legitimate local jobs.
    """
    if not requested:
        return True
    requested_l = requested.lower()
    aliases = COUNTRY_LOCATION_ALIASES.get(requested_l, [])

    if actual:
        actual_l = actual.lower()
        if requested_l in actual_l:
            return True
        return any(alias in actual_l for alias in aliases)

    # Empty location — try the title as a last-resort hint.
    if title:
        title_l = title.lower()
        if requested_l in title_l:
            return True
        if any(alias in title_l for alias in aliases):
            return True

    return False


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
        # LinkedIn's `location` URL param is advisory — the guest search ranker
        # returns worldwide results ranked by keyword match regardless. The
        # geoId parameter is the strict server-side country filter. Attach it
        # when we know the LinkedIn geoId for the requested country.
        params = {"keywords": query, "location": location}
        geo_id = LINKEDIN_GEOIDS.get(_country_key(location))
        if geo_id:
            params["geoId"] = geo_id

        try:
            response = requests.get(
                self.SEARCH_URL,
                params=params,
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

            job_title = title_el.get_text(strip=True)
            job_location = location_el.get_text(strip=True) if location_el else ""
            # LinkedIn often returns off-country results (esp. remote/US) despite the
            # location param. Use the country-aware matcher so Israeli jobs listed
            # as "Tel Aviv" (without the country suffix) still pass. When the
            # location field is empty, the matcher falls back to the title.
            if not _location_matches_country(location, job_location, title=job_title):
                continue

            jobs.append(JobListing(
                title=job_title,
                company=company_el.get_text(strip=True) if company_el else "Unknown",
                location=job_location or "Unknown",
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


class JobSpyScraper:
    """Wraps the python-jobspy library to scrape LinkedIn and Indeed."""

    COMPANY_NAME = "JobSpy"

    def search(self, query: str, location: str = "Israel", max_results: int = 20,
               distance: int = None) -> List[JobListing]:
        try:
            from jobspy import scrape_jobs
        except ImportError:
            logger.error("python-jobspy is not installed. Run: pip install python-jobspy")
            return []

        kwargs = dict(
            site_name=["linkedin", "indeed"],
            search_term=query,
            location=location,
            results_wanted=max_results,
        )
        # Indeed's `country_indeed` is the strict country filter (default 'usa').
        # Without it, Indeed returns worldwide results even with location set.
        country_indeed = JOBSPY_INDEED_COUNTRIES.get(_country_key(location))
        if country_indeed:
            kwargs["country_indeed"] = country_indeed
        if distance is not None:
            kwargs["distance"] = distance

        try:
            df = scrape_jobs(**kwargs)
        except Exception as e:
            logger.error("JobSpy scrape failed: %s", e)
            return []

        # When country_indeed was set, Indeed's server-side filter already
        # guarantees the country — no need to re-filter those rows client-side.
        # (Indeed returns Israeli locations as Hebrew strings like "חיפה, HA, IL"
        # which our alias list doesn't cover.) LinkedIn's rows still need the
        # filter because LinkedIn ignores the location param for guest search.
        trusted_sites = {"indeed"} if country_indeed else set()

        jobs = []
        for _, row in df.iterrows():
            title = row.get("title") or ""
            company = row.get("company") or ""
            loc = row.get("location") or ""
            url = row.get("job_url") or ""
            posted = str(row.get("date_posted") or "")[:10]
            site = str(row.get("site") or "").lower()

            if not title or not url:
                continue

            # Skip client-side location filtering for sites we trust (see above).
            # For other sites, fall back to the country-aware matcher, which also
            # checks the title when the location field is empty (e.g. Apple's
            # "Verification Student- Jerusalem" posting).
            if site not in trusted_sites:
                if not _location_matches_country(location, loc, title=title):
                    continue

            jobs.append(JobListing(
                title=title,
                company=company,
                location=loc,
                url=url,
                posted=posted,
            ))

        return jobs


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
        JobSpyScraper(),
        # WixScraper excluded: careers.wix.com is JS-rendered, no public API found
    ]

    # Registry for lookup by name — used by parallel_scan to select scrapers.
    SCRAPER_REGISTRY = {
        "IntelScraper": IntelScraper(),
        "NVIDIAScraper": NVIDIAScraper(),
        "MarvellScraper": MarvellScraper(),
        "AmazonScraper": AmazonScraper(),
        "LinkedInScraper": LinkedInScraper(),
        "JobSpyScraper": JobSpyScraper(),
    }

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

        return self._deduplicate(all_jobs)

    def company_scan(self, query: str = "student", location: str = "Israel",
                     max_per_company: int = 20, only_priority: bool = True,
                     progress_callback=None) -> List[JobListing]:
        """Scan for jobs at specific companies using the active profile's watchlist.

        Falls back to companies.json only when no profile or empty watchlist.
        When only_priority is True and using fallback, only companies with priority=true are searched.
        """
        from job_hunter.profile import get_profile
        profile = get_profile()
        if profile and profile.watchlist:
            companies = list(profile.watchlist)
        else:
            companies = _load_company_names(only_priority=only_priority)
        if not companies:
            logger.error("No companies loaded from companies.json")
            return []

        jobspy = JobSpyScraper()
        all_jobs = []

        for i, company_name in enumerate(companies, 1):
            if progress_callback:
                progress_callback(company_name, i, len(companies))
            search_term = f"{company_name} {query}" if query else company_name
            try:
                jobs = jobspy.search(
                    query=search_term,
                    location=location,
                    max_results=max_per_company,
                )
                all_jobs.extend(jobs)
                logger.info("Company scan: %s → %d jobs", company_name, len(jobs))
            except Exception as e:
                logger.warning("Company scan failed for %s: %s", company_name, e)

        return self._deduplicate(all_jobs)

    @staticmethod
    def _deduplicate(jobs: List[JobListing]) -> List[JobListing]:
        """Deduplicate by URL and by (title, company) to catch cross-source duplicates."""
        seen_urls: set = set()
        seen_title_company: set = set()
        unique = []
        for job in jobs:
            title_company_key = (job.title.lower().strip(), job.company.lower().strip())
            if job.url in seen_urls or title_company_key in seen_title_company:
                continue
            seen_urls.add(job.url)
            seen_title_company.add(title_company_key)
            unique.append(job)
        return unique

    # ------------------------------------------------------------------
    # Parallel scan — profile-driven, cached, concurrent
    # ------------------------------------------------------------------

    def parallel_scan(
        self,
        config: "SearchConfig",
        cache: "ScanCache",
        ttl_minutes: int = 90,
        max_per_source: int = 20,
        progress_callback: Optional[Callable] = None,
        include_companies: bool = True,
        only_priority: bool = True,
    ) -> List[JobListing]:
        """Run keyword + company searches in parallel with caching.

        Args:
            config: SearchConfig with queries, enabled_scrapers, companies, etc.
            cache: ScanCache instance for checking/storing results.
            ttl_minutes: Cache freshness threshold in minutes.
            max_per_source: Max results per individual scraper/query/company call.
            progress_callback: Called per-source as results arrive.
                Signature: (source_name, jobs_found, new_count, cached_age_or_none)
                cached_age_or_none is int (minutes) if served from cache, else None.
            include_companies: If False, skip company-targeted searches.
            only_priority: If True, only search priority companies.

        Returns:
            Deduplicated list of all JobListing results.
        """
        tasks = []  # list of (source_key, callable) pairs

        # --- Location variants ------------------------------------------------
        # If cities are set, JobSpy searches run per city with radius.
        # Non-JobSpy scrapers (Workday, Amazon, Greenhouse) always get country.
        if config.cities:
            jobspy_locations = [
                (f"{city}, {config.location}", config.radius_km)
                for city in config.cities
            ]
        else:
            jobspy_locations = [(config.location, None)]

        # --- Scraper tasks: each enabled scraper × each query ----------------
        for scraper_name in config.enabled_scrapers:
            scraper = self.SCRAPER_REGISTRY.get(scraper_name)
            if scraper is None:
                logger.warning("Unknown scraper: %s — skipping", scraper_name)
                continue

            is_jobspy = isinstance(scraper, JobSpyScraper)
            locations = jobspy_locations if is_jobspy else [(config.location, None)]

            for query in config.queries:
                for loc, radius in locations:
                    city_tag = f":{loc}" if len(locations) > 1 else ""
                    source_key = f"scraper:{scraper_name}:{query}{city_tag}"
                    tasks.append((
                        source_key,
                        lambda s=scraper, q=query, l=loc, r=radius: (
                            s.search(q, l, max_results=max_per_source, distance=r)
                            if r is not None and isinstance(s, JobSpyScraper)
                            else s.search(q, l, max_results=max_per_source)
                        ),
                    ))

        # --- Company tasks: each company via JobSpy --------------------------
        if include_companies:
            companies = config.priority_companies if only_priority else config.companies
            jobspy = JobSpyScraper()
            for company_name in companies:
                level = config.level_keywords[0] if config.level_keywords else ""
                search_term = f"{company_name} {level}".strip()
                for loc, radius in jobspy_locations:
                    city_tag = f":{loc}" if len(jobspy_locations) > 1 else ""
                    source_key = f"company:{company_name}{city_tag}"
                    tasks.append((
                        source_key,
                        lambda q=search_term, l=loc, r=radius: (
                            jobspy.search(q, l, max_results=max_per_source, distance=r)
                            if r is not None
                            else jobspy.search(q, l, max_results=max_per_source)
                        ),
                    ))

        # --- Execute with cache check + parallel dispatch --------------------
        all_jobs: List[JobListing] = []

        with ThreadPoolExecutor(max_workers=config.max_workers) as pool:
            futures = {}

            for source_key, task_fn in tasks:
                # Check cache first
                cached_result = cache.get(source_key, ttl_minutes=ttl_minutes)
                if cached_result is not None:
                    cached_jobs, age = cached_result
                    all_jobs.extend(cached_jobs)
                    if progress_callback:
                        progress_callback(source_key, len(cached_jobs), 0, age)
                    continue

                future = pool.submit(self._run_source, source_key, task_fn)
                futures[future] = source_key

            # Collect results as they complete
            for future in as_completed(futures):
                source_key = futures[future]
                try:
                    jobs = future.result()
                    cache.put(source_key, jobs)
                    all_jobs.extend(jobs)
                    if progress_callback:
                        progress_callback(source_key, len(jobs), len(jobs), None)
                except Exception as e:
                    logger.error("Source %s failed: %s", source_key, e)
                    if progress_callback:
                        progress_callback(source_key, 0, 0, None)

        return self._deduplicate(all_jobs)

    @staticmethod
    def _run_source(source_key: str, task_fn: Callable) -> List[JobListing]:
        """Execute a single source task with retry on 429 (rate limit)."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return task_fn()
            except Exception as e:
                # Check if it's a 429 rate limit error
                status = getattr(e, "status_code", None) or getattr(e, "code", None)
                err_str = str(e)
                is_rate_limit = status == 429 or "429" in err_str or "rate limit" in err_str.lower()

                if is_rate_limit and attempt < max_retries - 1:
                    wait = 2 ** attempt  # 1s, 2s
                    logger.info("Rate limited on %s — retrying in %ds (attempt %d/%d)",
                                source_key, wait, attempt + 1, max_retries)
                    time.sleep(wait)
                    continue
                raise


def _load_company_names(only_priority: bool = True) -> List[str]:
    """Load company names from data/jobs/companies.json.

    When only_priority is True, returns only companies with priority=true.
    """
    import json
    from job_hunter.config import Config

    companies_file = Config.companies_file()
    try:
        with open(companies_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        companies = data.get("companies", [])
        if only_priority:
            companies = [c for c in companies if c.get("priority", False)]
        return [c["name"] for c in companies if c.get("name")]
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to load companies.json: %s", e)
        return []


# ---------------------------------------------------------------------------
# Job description fetcher
# ---------------------------------------------------------------------------

_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9,he;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
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
