import requests
from typing import List, Dict, Any, Optional
from core.logger import setup_logger

logger = setup_logger("client.remotive")

class RemotiveClient:
    """
    Dedicated HTTP client for Remotive Remote Jobs public API.
    API endpoint: https://remotive.com/api/remote-jobs
    """

    BASE_URL = "https://remotive.com/api/remote-jobs"

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "JobAgent/2.0 (Compatible; Remote Job Ingestor; +https://jobagent.ai)",
            "Accept": "application/json"
        })

    def fetch_remote_jobs(self, category: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieves remote job postings from Remotive.
        Optional category filter: 'software-dev', 'data', 'design', 'product', etc.
        """
        params = {}
        if category:
            params["category"] = category
        if limit:
            params["limit"] = limit

        try:
            logger.info("Querying Remotive API (params: %s)...", params)
            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                jobs = data.get("jobs", [])
                logger.info("Successfully fetched %d jobs from Remotive", len(jobs))
                return jobs
            else:
                logger.warning("Remotive API returned status %d: %s", response.status_code, response.text[:200])
                return []

        except requests.exceptions.RequestException as req_err:
            logger.error("HTTP error connecting to Remotive API: %s", req_err)
            return []
        except Exception as e:
            logger.error("Unexpected error fetching Remotive API: %s", e)
            return []
