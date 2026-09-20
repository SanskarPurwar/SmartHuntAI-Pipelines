import os
import sys
import urllib.parse
from typing import List, Optional
import requests
from bs4 import BeautifulSoup

# Ensure core module can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scraper_models import JobPostingScraperModel, JobPosting
from core.time_utils import parse_posted_at

class LinkedInJobsCollector:
    """
    Scrapes job postings from the public LinkedIn Guest Job Search API
    with 3-tier proxy escalation (Direct -> Standard Proxy -> Premium Proxy).
    """

    def __init__(self):
        self.base_search_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        self.http_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
    
    def _is_relevant_job_title(self, raw_title: str, target_keyword: str) -> bool:
        title_lower = raw_title.lower()
        keyword_lower = target_keyword.lower()
        
        # 1. Direct keyword match or any word match (>2 characters)
        keyword_tokens = [token for token in keyword_lower.split() if len(token) > 2]
        if any(token in title_lower for token in keyword_tokens):
            return True
            
        # 2. Industry synonym mapping for software & tech engineering roles
        tech_search_terms = {
            'developer', 'engineer', 'sde', 'programmer', 'software', 'frontend',
            'backend', 'fullstack', 'full stack', 'web', 'devops', 'architect',
            'coding', 'application', 'mobile', 'ios', 'android'
        }
        is_tech_search = any(term in keyword_lower for term in tech_search_terms)
        if is_tech_search:
            tech_role_indicators = {
                'developer', 'engineer', 'sde', 'swe', 'architect', 'programmer',
                'fullstack', 'full stack', 'backend', 'frontend', 'web dev',
                'software', 'devops', 'tech lead', 'coding', 'application dev'
            }
            if any(indicator in title_lower for indicator in tech_role_indicators):
                return True
                
        # 3. Word stem match for non-tech roles (e.g., 'audit' in 'auditor')
        for token in keyword_tokens:
            if len(token) >= 4 and (token[:4] in title_lower or token in title_lower):
                return True
                
        # If keyword has no long tokens, allow through
        if not keyword_tokens:
            return True
            
        return False

    # Backward compatibility alias
    _is_relevant_title = _is_relevant_job_title

    def _fetch_html_page(self, request_url: str, logger=None) -> Optional[str]:
        """
        3-Tier Smart Fetch Strategy to preserve ScrapingBee credits:
        - Tier 1: Direct Request (0 credits). Works for ~90% of requests.
        - Tier 2: ScrapingBee Standard Proxy (1 credit). Triggered on 429/999 or network timeout.
        - Tier 3: ScrapingBee Premium Proxy (10 credits). Escalation on captcha/blocking.
        """
        scrapingbee_api_key = os.getenv("SCRAPINGBEE_API_KEY")
        
        # --- Tier 1: Direct Request (0 Credits) ---
        try:
            direct_response = requests.get(request_url, headers=self.http_headers, timeout=12)
            if direct_response.status_code == 200:
                return direct_response.text
            if logger:
                logger(f"[INFO] [Discovery] Direct fetch returned HTTP {direct_response.status_code}. Initiating Tier 2 standard proxy fallback...")
        except Exception as network_error:
            if logger:
                logger(f"[INFO] [Discovery] Direct fetch connection issue ({network_error}). Initiating Tier 2 standard proxy fallback...")
                
        # --- Tier 2: ScrapingBee Standard Proxy (1 Credit, premium_proxy=false) ---
        if scrapingbee_api_key:
            encoded_target_url = urllib.parse.quote(request_url)
            standard_proxy_api_url = f"https://app.scrapingbee.com/api/v1/?api_key={scrapingbee_api_key}&url={encoded_target_url}&premium_proxy=false&render_js=false"
            try:
                standard_proxy_response = requests.get(standard_proxy_api_url, headers=self.http_headers, timeout=25)
                if standard_proxy_response.status_code == 200:
                    credit_cost = standard_proxy_response.headers.get("spb-cost", "1")
                    if logger:
                        logger(f"[INFO] [Discovery] ScrapingBee standard proxy successful ({credit_cost} credit used).")
                    return standard_proxy_response.text
                if logger:
                    logger(f"[WARN] [Discovery] ScrapingBee standard proxy returned HTTP {standard_proxy_response.status_code}. Escalating to Tier 3 premium proxy...")
            except Exception as proxy_error:
                if logger:
                    logger(f"[WARN] [Discovery] ScrapingBee standard proxy failed ({proxy_error}). Escalating to Tier 3...")

            # --- Tier 3: ScrapingBee Premium Proxy (10 Credits, emergency fallback) ---
            premium_proxy_api_url = f"https://app.scrapingbee.com/api/v1/?api_key={scrapingbee_api_key}&url={encoded_target_url}&premium_proxy=true&render_js=false"
            try:
                premium_proxy_response = requests.get(premium_proxy_api_url, headers=self.http_headers, timeout=40)
                if premium_proxy_response.status_code == 200:
                    credit_cost = premium_proxy_response.headers.get("spb-cost", "10")
                    if logger:
                        logger(f"[WARN] [Discovery] ScrapingBee premium proxy emergency fallback successful ({credit_cost} credits used).")
                    return premium_proxy_response.text
                if logger:
                    logger(f"[ERROR] [Discovery] ScrapingBee premium proxy failed with HTTP {premium_proxy_response.status_code}.")
            except Exception as premium_proxy_error:
                if logger:
                    logger(f"[ERROR] [Discovery] ScrapingBee premium proxy failed with exception: {premium_proxy_error}")

        return None

    def fetch_jobs(
        self,
        keyword: str,
        location: str,
        start_page: int = 1,
        end_page: int = 3,
        time_unit: str = 'days',
        time_value: int = 7,
        max_yoe: int = 2,
        logger=None
    ) -> List[JobPostingScraperModel]:
        """
        Fetches job postings matching keyword and location across specified page ranges.
        """
        def log_message(msg):
            if logger:
                logger(msg)
            else:
                print(msg)
                
        encoded_keyword = urllib.parse.quote(keyword)
        encoded_location = urllib.parse.quote(location)
        
        # Calculate time window filter in seconds for LinkedIn f_TPR parameter
        time_window_seconds = time_value * 86400 if time_unit == 'days' else time_value * 3600
        
        extracted_job_postings = []
        
        # LinkedIn guest API returns 10 jobs per page. Step by 10 so zero jobs are skipped between pages.
        for page_index in range(start_page - 1, end_page):
            offset_start = page_index * 10
            paginated_search_url = (
                f"{self.base_search_url}?keywords={encoded_keyword}&location={encoded_location}"
                f"&f_TPR=r{time_window_seconds}&start={offset_start}"
            )
            
            try:
                html_page_content = self._fetch_html_page(paginated_search_url, logger=log_message)
                if not html_page_content:
                    log_message(f"[WARN] [Discovery] No content retrieved for page {page_index + 1}")
                    break
                    
                soup = BeautifulSoup(html_page_content, 'html.parser')
                job_list_elements = soup.find_all('li')
                
                if not job_list_elements:
                    log_message(f"[INFO] [Discovery] Reached end of postings at page {page_index + 1}")
                    break
                    
                page_extracted_count = 0
                for job_element in job_list_elements: 
                    title_element = job_element.find('h3', class_='base-search-card__title')
                    company_element = job_element.find('h4', class_='base-search-card__subtitle')
                    link_element = job_element.find('a', class_='base-card__full-link')
                    location_element = job_element.find('span', class_='job-search-card__location')
                    
                    if title_element and company_element:
                        job_title = title_element.text.strip()
                        job_company = company_element.text.strip()
                        job_location = location_element.text.strip() if location_element else "N/A"
                        clean_job_link = link_element['href'].split('?')[0] if link_element else "N/A"
                        
                        # Validate title relevance with domain synonym matching
                        if not self._is_relevant_job_title(job_title, keyword):
                            continue
                            
                        time_element = job_element.find('time')
                        if time_element:
                            datetime_attr = time_element.get('datetime', '').strip()
                            relative_time_text = " ".join(time_element.text.split())
                            raw_time = datetime_attr or relative_time_text
                            posted_at_dt = parse_posted_at(raw_time)
                        else:
                            posted_at_dt = parse_posted_at(None)
                            
                        extracted_job_postings.append(JobPostingScraperModel(
                            title=job_title,
                            company=job_company,
                            location=job_location,
                            link=clean_job_link,
                            posted_at=posted_at_dt
                        ))
                        page_extracted_count += 1
                        
                log_message(f"[INFO] [Discovery] Page {page_index + 1} (offset {offset_start}): parsed {len(job_list_elements)} items, extracted {page_extracted_count} matching opportunities.")
            except Exception as parse_error:
                log_message(f"[ERROR] [Discovery] Exception occurred while parsing page {page_index + 1}: {parse_error}")
                
        return extracted_job_postings

if __name__ == "__main__":
    collector = LinkedInJobsCollector()
    sample_jobs = collector.fetch_jobs("Backend Engineer", "India", start_page=1, end_page=2)
    for idx, sample_job in enumerate(sample_jobs[:5]):
        print(f"{idx+1}. {sample_job.title} @ {sample_job.company} | {sample_job.location}")
