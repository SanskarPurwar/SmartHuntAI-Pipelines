import os
import sys
import time
import random
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional, Dict
import requests
from bs4 import BeautifulSoup

# Ensure core module can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scraper_models import JobPostingScraperModel, JobPosting

class RotatingProxyPool:
    """
    Manages a pool of public HTTP/HTTPS proxies with round-robin rotation
    and multi-source fallback.
    """
    def __init__(self, logger=None):
        self.logger = logger
        self.proxy_list = []
        self.current_proxy_index = 0
        self._load_proxies()

    def _log(self, msg: str):
        if self.logger:
            self.logger(msg)
        else:
            print(msg)

    def _load_proxies(self):
        self._log("[INFO] [ProxyPool] Fetching free proxies from Geonode...")
        try:
            geonode_url = "https://proxylist.geonode.com/api/proxy-list?limit=50&page=1&sort_by=lastChecked&sort_type=desc&protocols=http"
            response = requests.get(geonode_url, timeout=10)
            data = response.json()
            for proxy_item in data.get('data', []):
                self.proxy_list.append(f"{proxy_item['ip']}:{proxy_item['port']}")
            self._log(f"[INFO] [ProxyPool] Loaded {len(self.proxy_list)} proxies from Geonode.")
        except Exception as geonode_error:
            self._log(f"[WARN] [ProxyPool] Failed to load Geonode proxies: {geonode_error}")

        # Fallback to free-proxy-list.net
        if not self.proxy_list:
            self._log("[INFO] [ProxyPool] Fetching free proxies from free-proxy-list.net...")
            try:
                response = requests.get('https://free-proxy-list.net/', timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                table = soup.find("table")
                if table:
                    for row in table.find_all("tr")[1:50]:
                        cells = row.find_all("td")
                        try:
                            if cells[4].text.strip() == "transparent":
                                continue
                            ip_address = cells[0].text.strip()
                            port_number = cells[1].text.strip()
                            self.proxy_list.append(f"{ip_address}:{port_number}")
                        except IndexError:
                            pass
                self._log(f"[INFO] [ProxyPool] Loaded {len(self.proxy_list)} proxies from free-proxy-list.")
            except Exception as proxy_list_error:
                self._log(f"[WARN] [ProxyPool] Failed to load free-proxy-list proxies: {proxy_list_error}")
                
        random.shuffle(self.proxy_list)

    def get_next_proxy(self) -> Optional[Dict[str, str]]:
        if not self.proxy_list:
            return None
        selected_proxy = self.proxy_list[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
        return {
            "http": f"http://{selected_proxy}",
            "https": f"http://{selected_proxy}"
        }

    # Backward compatibility alias
    get_proxy = get_next_proxy

# Backward compatibility alias
FreeProxyRotator = RotatingProxyPool


class DuckDuckGoPostsCollector:
    """
    Scrapes LinkedIn hiring and recruiter posts indexed on DuckDuckGo HTML search.
    """
    def __init__(self):
        self.search_url = 'https://html.duckduckgo.com/html/'
        self.user_agent_pool = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        ]
        
    def _build_request_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': random.choice(self.user_agent_pool),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Origin': 'https://html.duckduckgo.com',
            'Referer': 'https://html.duckduckgo.com/',
        }

    def fetch_posts(
        self,
        keyword: str,
        location: str,
        max_pages: int = 3,
        logger=None
    ) -> List[JobPostingScraperModel]:
        """
        Discovers recruiter hiring posts on LinkedIn via DuckDuckGo search queries.
        """
        def log_message(msg):
            if logger:
                logger(msg)
            else:
                print(msg)
            
        # Add negative keywords to exclude senior/lead roles
        search_query = f'site:linkedin.com/posts "hiring {keyword}" {location} -senior -sr -lead -staff -principal -manager -director'
        
        extracted_posts = []
        proxy_rotator = None
        active_proxy = None
        proxy_retry_attempts = 0
        
        for page_index in range(max_pages):
            form_payload = {
                'q': search_query,
                'b': '',
                's': str(page_index * 30),
                'df': 'w' 
            }
            
            page_fetch_successful = False
            while not page_fetch_successful and proxy_retry_attempts < 10:
                try:
                    proxy_display_string = active_proxy['http'] if active_proxy else 'Direct Connection (No Proxy)'
                    log_message(f"[INFO] [DuckDuckGo] Post Search (Page {page_index + 1}): Using {proxy_display_string}")
                    
                    response = requests.post(
                        self.search_url,
                        headers=self._build_request_headers(),
                        data=form_payload,
                        proxies=active_proxy,
                        timeout=10
                    )
                    
                    if response.status_code == 202:
                        log_message(f"[WARN] [DuckDuckGo] Request challenge (Status 202). Rotating proxy...")
                        if not proxy_rotator:
                            proxy_rotator = RotatingProxyPool(logger=log_message)
                        active_proxy = proxy_rotator.get_next_proxy()
                        proxy_retry_attempts += 1
                        continue
                    elif response.status_code != 200:
                        log_message(f"[WARN] [DuckDuckGo] Request failed (Status {response.status_code}). Rotating proxy...")
                        if not proxy_rotator:
                            proxy_rotator = RotatingProxyPool(logger=log_message)
                        active_proxy = proxy_rotator.get_next_proxy()
                        proxy_retry_attempts += 1
                        continue
                        
                    soup = BeautifulSoup(response.text, 'html.parser')
                    result_elements = soup.find_all('div', class_='result')
                    
                    if not result_elements:
                        log_message(f"[INFO] [DuckDuckGo] No more hiring posts found on page {page_index + 1}.")
                        page_fetch_successful = True
                        break
                        
                    for result_elem in result_elements:
                        try:
                            url_anchor = result_elem.find('a', class_='result__url')
                            if not url_anchor:
                                continue
                                
                            post_link = url_anchor.get('href', '')
                            if 'linkedin.com/posts/' not in post_link:
                                continue
                                
                            post_title = result_elem.find('h2', class_='result__title').text.strip()
                            post_snippet = result_elem.find('a', class_='result__snippet').text.strip()
                            
                            extracted_posts.append(JobPostingScraperModel(
                                title=post_title,
                                company="Unknown Recruiter",
                                location=location,
                                link=post_link,
                                description=post_snippet,
                                source="linkedin_posts_ddg",
                                posted_at=datetime.now(timezone.utc)
                            ))
                        except Exception:
                            continue
                            
                    page_fetch_successful = True
                    proxy_retry_attempts = 0
                    time.sleep(random.randint(5, 10))
                    
                except requests.exceptions.RequestException as network_exception:
                    log_message(f"[WARN] [DuckDuckGo] Connection issue ({type(network_exception).__name__}). Rotating proxy...")
                    if not proxy_rotator:
                        proxy_rotator = RotatingProxyPool(logger=log_message)
                    active_proxy = proxy_rotator.get_next_proxy()
                    proxy_retry_attempts += 1
            
            if proxy_retry_attempts >= 10:
                log_message("[ERROR] [DuckDuckGo] Exhausted 10 proxy attempts. Skipping remaining post searches.")
                break
                
        return extracted_posts

# Backward compatibility alias
DDGPostsCollector = DuckDuckGoPostsCollector
