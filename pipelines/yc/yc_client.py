import re
import requests
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from core.logger import setup_logger

logger = setup_logger("client.yc")

class YCClient:
    """
    Client for ingesting Y Combinator startup job postings via:
    1. Official Hacker News YC Job Stories API (hacker-news.firebaseio.com)
    2. Ask HN: Who is Hiring Algolia comments index
    """

    def __init__(self):
        self.hn_job_stories_url = "https://hacker-news.firebaseio.com/v0/jobstories.json"
        self.hn_item_url = "https://hacker-news.firebaseio.com/v0/item/{}.json"
        self.algolia_url = "https://hn.algolia.com/api/v1/search_by_date"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

    def fetch_yc_job_stories(self, limit: int = 40) -> List[Dict[str, Any]]:
        """
        Fetches live YC company job postings from the official Hacker News job stories endpoint.
        """
        jobs: List[Dict[str, Any]] = []
        try:
            resp = requests.get(self.hn_job_stories_url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                logger.warning("HN jobstories returned status %s", resp.status_code)
                return []

            story_ids = resp.json()[:limit]
            for s_id in story_ids:
                try:
                    item_resp = requests.get(self.hn_item_url.format(s_id), headers=self.headers, timeout=6)
                    if item_resp.status_code != 200:
                        continue
                    item = item_resp.json()
                    if not item:
                        continue

                    title = item.get("title", "")
                    url = item.get("url") or f"https://news.ycombinator.com/item?id={s_id}"
                    text = item.get("text", "")
                    created_at = item.get("time")

                    # Parse company and role from standard HN format: "Company (YC W24) Is Hiring a Senior SWE" or "Company is hiring..."
                    company_name = "YC Startup"
                    role_title = title
                    if " is hiring " in title.lower():
                        parts = re.split(r'\s+is hiring\s+', title, flags=re.IGNORECASE)
                        company_name = parts[0].strip()
                        role_title = parts[1].strip() if len(parts) > 1 else title
                    elif "|" in title:
                        parts = title.split("|")
                        company_name = parts[0].strip()
                        role_title = " | ".join(parts[1:]).strip()
                    elif ":" in title:
                        parts = title.split(":", 1)
                        company_name = parts[0].strip()
                        role_title = parts[1].strip()

                    # Clean company name from parenthetical YC batch e.g. "Acme (YC S23)" -> "Acme"
                    company_clean = re.sub(r'\s*\([^\)]*YC[^\)]*\)', '', company_name, flags=re.IGNORECASE).strip()

                    clean_desc = BeautifulSoup(text, "html.parser").get_text(separator="\n").strip() if text else title

                    jobs.append({
                        "title": role_title,
                        "company_name": company_clean or "YC Startup",
                        "link": url,
                        "location": "Remote / San Francisco",
                        "description": clean_desc,
                        "posted_at": created_at
                    })
                except Exception as item_err:
                    logger.debug("Failed to fetch HN item %s: %s", s_id, item_err)

            return jobs
        except Exception as err:
            logger.error("Failed to query HN job stories: %s", err)
            return []

    def fetch_who_is_hiring_comments(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetches top comments from the most recent "Ask HN: Who is hiring?" thread via Algolia.
        """
        jobs: List[Dict[str, Any]] = []
        try:
            # 1. Find the latest "Who is hiring" story
            params = {
                "tags": "story,author_whoishiring",
                "query": "Ask HN: Who is hiring?",
                "hitsPerPage": 1
            }
            res = requests.get(self.algolia_url, params=params, headers=self.headers, timeout=10)
            if res.status_code != 200:
                return []

            hits = res.json().get("hits", [])
            if not hits:
                return []

            story_id = hits[0].get("objectID")
            if not story_id:
                return []

            # 2. Fetch comments from this story
            comments_res = requests.get(
                self.algolia_url,
                params={"tags": f"comment,story_{story_id}", "hitsPerPage": limit},
                headers=self.headers,
                timeout=12
            )
            if comments_res.status_code != 200:
                return []

            comment_hits = comments_res.json().get("hits", [])
            for c in comment_hits:
                text = c.get("comment_text", "")
                if not text:
                    continue

                soup = BeautifulSoup(text, "html.parser")
                first_line = soup.get_text().split("\n")[0].strip()
                
                # Standard format: "Company | Role | Location | REMOTE"
                if "|" in first_line:
                    segments = [s.strip() for s in first_line.split("|") if s.strip()]
                    if len(segments) >= 2:
                        company = segments[0]
                        role = segments[1]
                        location = segments[2] if len(segments) > 2 else "Remote"
                        
                        # Find link inside text or fallback to HN item URL
                        link_tag = soup.find("a", href=True)
                        link = link_tag["href"] if link_tag else f"https://news.ycombinator.com/item?id={c.get('objectID')}"

                        jobs.append({
                            "title": role,
                            "company_name": company,
                            "location": location,
                            "link": link,
                            "description": soup.get_text(separator="\n").strip(),
                            "posted_at": c.get("created_at")
                        })
            return jobs
        except Exception as err:
            logger.error("Failed to query Algolia Who is Hiring: %s", err)
            return []
