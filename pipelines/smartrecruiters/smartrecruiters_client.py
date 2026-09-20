"""
Dedicated HTTP Client for the official SmartRecruiters Public Posting API.
API Docs: https://dev.smartrecruiters.com/customer-api/posting-api/
"""

import requests
import time
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.logger import setup_logger

logger = setup_logger("pipelines.smartrecruiters.client")

class SmartRecruitersClient:
    """
    Client for querying unauthenticated public postings on SmartRecruiters.
    """
    BASE_URL = "https://api.smartrecruiters.com/v1/companies"

    def __init__(self, timeout: int = 15, max_workers: int = 6):
        self.timeout = timeout
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "JobAgent/2.0 (+https://smarthunt.ai)",
            "Accept": "application/json"
        })

    def fetch_company_postings(
        self,
        company_slug: str,
        country: Optional[str] = None,
        limit_per_page: int = 100,
        max_pages: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Paginates through public postings for a company identifier.
        Optionally filters by ISO 3166-1 alpha-2 country code (e.g. 'in').
        """
        all_postings: List[Dict[str, Any]] = []
        offset = 0

        for page in range(max_pages):
            endpoint = f"{self.BASE_URL}/{company_slug}/postings"
            params: Dict[str, Any] = {
                "limit": limit_per_page,
                "offset": offset
            }
            if country:
                params["country"] = country.lower()

            try:
                response = self.session.get(endpoint, params=params, timeout=self.timeout)
                if response.status_code == 404:
                    logger.debug("Company '%s' not found on SmartRecruiters (404).", company_slug)
                    break
                if response.status_code == 429:
                    logger.warning("SmartRecruiters rate limit (429) on '%s'. Backing off 2s...", company_slug)
                    time.sleep(2.0)
                    response = self.session.get(endpoint, params=params, timeout=self.timeout)

                response.raise_for_status()
                data = response.json()
                content = data.get("content", [])
                if not content:
                    break

                all_postings.extend(content)
                total_found = data.get("totalFound", len(all_postings))

                offset += len(content)
                if offset >= total_found or len(content) < limit_per_page:
                    break

            except requests.RequestException as req_err:
                logger.warning("SmartRecruiters list request failed for '%s' offset=%d: %s", company_slug, offset, req_err)
                break

        return all_postings

    def fetch_posting_detail(self, company_slug: str, posting_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the full job advertisement containing descriptions, requirements, and apply links.
        """
        endpoint = f"{self.BASE_URL}/{company_slug}/postings/{posting_id}"
        try:
            response = self.session.get(endpoint, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            return None
        except requests.RequestException:
            return None

    def fetch_postings_with_details(
        self,
        company_slug: str,
        country: Optional[str] = None,
        max_jobs: int = 150
    ) -> List[Dict[str, Any]]:
        """
        Fetches postings and concurrently fetches their complete descriptions.
        """
        postings = self.fetch_company_postings(company_slug, country=country)
        if not postings:
            return []

        postings = postings[:max_jobs]
        enriched_postings: List[Dict[str, Any]] = []

        def _fetch_one(p: Dict[str, Any]) -> Dict[str, Any]:
            pid = str(p.get("id"))
            detail = self.fetch_posting_detail(company_slug, pid)
            if detail:
                merged = dict(p)
                merged.update(detail)
                return merged
            return p

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_job = {executor.submit(_fetch_one, p): p for p in postings}
            for future in as_completed(future_to_job):
                try:
                    res = future.result()
                    enriched_postings.append(res)
                except Exception as ex:
                    enriched_postings.append(future_to_job[future])

        return enriched_postings
