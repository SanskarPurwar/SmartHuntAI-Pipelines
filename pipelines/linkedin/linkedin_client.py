import urllib.parse
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from core.time_utils import parse_posted_at
from core.logger import setup_logger

logger = setup_logger("client.linkedin")

class LinkedInClient:
    """
    Client for public LinkedIn Guest Job Search API.
    Zero authentication / zero credentials required.
    """

    def __init__(self):
        self.base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

    def fetch_guest_jobs(self, keywords: str = "Software Engineer", location: str = "Remote", start: int = 0) -> List[Dict[str, Any]]:
        """
        Queries LinkedIn guest search endpoint and extracts parsed job card dictionaries.
        """
        params = {
            "keywords": keywords,
            "location": location,
            "start": start
        }
        encoded_query = urllib.parse.urlencode(params)
        request_url = f"{self.base_url}?{encoded_query}"

        try:
            response = requests.get(request_url, headers=self.headers, timeout=12)
            if response.status_code != 200:
                logger.warning("LinkedIn guest search returned status %s for query %s", response.status_code, keywords)
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            job_cards = soup.find_all("li")
            extracted_jobs: List[Dict[str, Any]] = []

            for card in job_cards:
                title_elem = card.find("h3", class_="base-search-card__title")
                company_elem = card.find("h4", class_="base-search-card__subtitle")
                location_elem = card.find("span", class_="job-search-card__location")
                link_elem = card.find("a", class_="base-card__full-link")
                time_elem = card.find("time")

                if not title_elem or not link_elem:
                    continue

                raw_title = title_elem.get_text(strip=True)
                raw_company = company_elem.get_text(strip=True) if company_elem else "Hiring Company"
                raw_location = location_elem.get_text(strip=True) if location_elem else location
                raw_link = link_elem.get("href", "").split("?")[0]  # Strip tracking parameters for clean link

                posted_at_val = None
                if time_elem:
                    posted_at_val = time_elem.get("datetime") or time_elem.get_text(strip=True)

                extracted_jobs.append({
                    "title": raw_title,
                    "company_name": raw_company,
                    "location": raw_location,
                    "link": raw_link,
                    "posted_at": posted_at_val,
                    "description": f"Verified LinkedIn guest job posting for {raw_title} at {raw_company} ({raw_location})."
                })

            return extracted_jobs
        except Exception as err:
            logger.error("Error querying LinkedIn guest search: %s", err)
            return []
