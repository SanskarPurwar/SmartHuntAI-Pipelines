import requests
from typing import List, Dict, Any, Optional

class GreenhouseClient:
    """
    Dedicated HTTP Client for the official Greenhouse Job Board REST API.
    API Docs: https://developers.greenhouse.io/job-board.html
    """
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "JobAgent/2.0 (+https://smarthunt.ai)",
            "Accept": "application/json"
        })

    def fetch_board_jobs(self, board_slug: str, include_content: bool = True) -> List[Dict[str, Any]]:
        """
        Fetches all published jobs for a specific company board slug.
        Returns a list of raw job dictionaries.
        """
        endpoint = f"{self.BASE_URL}/{board_slug}/jobs"
        params = {"content": "true"} if include_content else {}

        try:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()
            return data.get("jobs", [])
        except requests.RequestException as req_err:
            raise RuntimeError(f"Greenhouse API request failed for '{board_slug}': {req_err}") from req_err
