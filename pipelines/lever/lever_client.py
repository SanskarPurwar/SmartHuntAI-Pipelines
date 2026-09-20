import requests
from typing import List, Dict, Any
from core.logger import setup_logger

logger = setup_logger("client.lever")

class LeverClient:
    """
    Dedicated HTTP client for fetching job listings from Lever ATS public API.
    API endpoint: https://api.lever.co/v0/postings/{slug}?mode=json
    """

    BASE_URL = "https://api.lever.co/v0/postings"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "JobAgent/2.0 (Compatible; Job Aggregator Engine; +https://jobagent.ai)",
            "Accept": "application/json"
        })

    def fetch_postings(self, company_slug: str) -> List[Dict[str, Any]]:
        """
        Retrieves all public postings for a given company slug.
        Returns empty list on 404 or connection failures.
        """
        slug = company_slug.strip().lower()
        url = f"{self.BASE_URL}/{slug}?mode=json"

        try:
            logger.info("Fetching Lever postings from: %s", url)
            response = self.session.get(url, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return data
                logger.warning("Lever returned unexpected non-list JSON payload for '%s'", slug)
                return []
            elif response.status_code == 404:
                logger.info("No active Lever board found for '%s' (404 Not Found)", slug)
                return []
            else:
                logger.warning("Lever API responded with status %d for '%s'", response.status_code, slug)
                return []

        except requests.exceptions.RequestException as req_err:
            logger.error("HTTP request error connecting to Lever board '%s': %s", slug, req_err)
            return []
        except Exception as e:
            logger.error("Unexpected error fetching Lever board '%s': %s", slug, e)
            return []
