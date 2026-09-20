import requests
from typing import List, Dict, Any
from core.logger import setup_logger

logger = setup_logger("client.ashby")

class AshbyClient:
    """
    Dedicated HTTP client for fetching job listings from Ashby ATS public API.
    API endpoint: https://api.ashbyhq.com/posting-api/job-board/{slug}
    """

    BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "JobAgent/2.0 (Compatible; Job Aggregator Engine; +https://jobagent.ai)",
            "Accept": "application/json"
        })

    def fetch_jobs(self, company_slug: str) -> List[Dict[str, Any]]:
        """
        Retrieves all public job postings for a given company slug on Ashby.
        Returns empty list on 404 or connection failure.
        """
        slug = company_slug.strip().lower()
        url = f"{self.BASE_URL}/{slug}"

        try:
            logger.info("Fetching Ashby job board from: %s", url)
            response = self.session.get(url, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                jobs = data.get("jobs", [])
                if isinstance(jobs, list):
                    return jobs
                logger.warning("Ashby returned unexpected payload format for '%s'", slug)
                return []
            elif response.status_code == 404:
                logger.info("No active Ashby board found for '%s' (404 Not Found)", slug)
                return []
            else:
                logger.warning("Ashby API responded with status %d for '%s'", response.status_code, slug)
                return []

        except requests.exceptions.RequestException as req_err:
            logger.error("HTTP request error connecting to Ashby board '%s': %s", slug, req_err)
            return []
        except Exception as e:
            logger.error("Unexpected error fetching Ashby board '%s': %s", slug, e)
            return []
