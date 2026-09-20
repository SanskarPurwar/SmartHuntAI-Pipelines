"""
Company Discovery Engine for Greenhouse, Lever, Ashby, and SmartRecruiters.
Probes public endpoints of modern ATS platforms to discover career board slugs
and automatically expand seed lists for India-focused hiring.
"""

import re
import requests
import json
import time
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.logger import setup_logger
from tools.indian_company_list import INDIAN_COMPANIES

logger = setup_logger("tools.company_discovery")

TIMEOUT = 3.5

def generate_candidate_slugs(company_name: str, hints: Optional[List[str]] = None) -> List[str]:
    """Generates normalized candidate slugs from company name and explicit hints."""
    candidates = list(hints or [])
    clean_name = company_name.strip().lower()

    # 1. Alphanumeric only (e.g., 'Tata Consultancy Services' -> 'tataconsultancyservices')
    s1 = re.sub(r'[^a-z0-9]', '', clean_name)
    if s1 and s1 not in candidates:
        candidates.append(s1)

    # 2. Hyphenated (e.g., 'tata-consultancy-services')
    s2 = re.sub(r'[^a-z0-9]+', '-', clean_name).strip('-')
    if s2 and s2 not in candidates:
        candidates.append(s2)

    # 3. First word if multi-word (e.g. 'Razorpay Software' -> 'razorpay')
    words = clean_name.split()
    if len(words) > 1:
        s3 = re.sub(r'[^a-z0-9]', '', words[0])
        if s3 and len(s3) >= 3 and s3 not in candidates:
            candidates.append(s3)

    return candidates

class CompanyDiscoveryEngine:
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "JobAgent/2.0 (+https://smarthunt.ai)",
            "Accept": "application/json"
        })

        # Load known seeds to filter out existing companies
        from pipelines.greenhouse.seed_companies import GREENHOUSE_SEED_COMPANIES
        from pipelines.lever.seed_companies import LEVER_SEED_COMPANIES
        from pipelines.ashby.seed_companies import ASHBY_SEED_COMPANIES
        from pipelines.smartrecruiters.seed_companies import SMARTRECRUITERS_SEED_COMPANIES

        self.known_greenhouse = {c["slug"].lower() for c in GREENHOUSE_SEED_COMPANIES}
        self.known_lever = {c["slug"].lower() for c in LEVER_SEED_COMPANIES}
        self.known_ashby = {c["slug"].lower() for c in ASHBY_SEED_COMPANIES}
        self.known_smartrecruiters = {c["slug"].lower() for c in SMARTRECRUITERS_SEED_COMPANIES}

    def probe_greenhouse(self, slug: str) -> Optional[int]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        try:
            r = self.session.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                jobs = data.get("jobs", [])
                return len(jobs)
        except Exception:
            pass
        return None

    def probe_lever(self, slug: str) -> Optional[int]:
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        try:
            r = self.session.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    return len(data)
        except Exception:
            pass
        return None

    def probe_ashby(self, slug: str) -> Optional[int]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        try:
            r = self.session.post(url, json={}, timeout=TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                jobs = data.get("jobs", [])
                return len(jobs)
        except Exception:
            pass
        return None

    def probe_smartrecruiters(self, slug: str) -> Optional[int]:
        url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1"
        try:
            r = self.session.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                return data.get("totalFound", 0)
        except Exception:
            pass
        return None

    def probe_company(self, company_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
        name = company_meta["name"]
        hints = company_meta.get("slug_hints", [])
        slugs = generate_candidate_slugs(name, hints)

        matches = []
        for slug in slugs:
            lower_slug = slug.lower()
            
            # 1. Greenhouse
            if lower_slug not in self.known_greenhouse:
                gh_jobs = self.probe_greenhouse(slug)
                if gh_jobs and gh_jobs > 0:
                    matches.append({"company": name, "platform": "greenhouse", "slug": slug, "jobs_count": gh_jobs})

            # 2. Lever
            if lower_slug not in self.known_lever:
                lever_jobs = self.probe_lever(slug)
                if lever_jobs and lever_jobs > 0:
                    matches.append({"company": name, "platform": "lever", "slug": slug, "jobs_count": lever_jobs})

            # 3. Ashby
            if lower_slug not in self.known_ashby:
                ashby_jobs = self.probe_ashby(slug)
                if ashby_jobs and ashby_jobs > 0:
                    matches.append({"company": name, "platform": "ashby", "slug": slug, "jobs_count": ashby_jobs})

            # 4. SmartRecruiters
            if lower_slug not in self.known_smartrecruiters:
                sr_jobs = self.probe_smartrecruiters(slug)
                if sr_jobs and sr_jobs > 0:
                    matches.append({"company": name, "platform": "smartrecruiters", "slug": slug, "jobs_count": sr_jobs})

        return matches

    def run_discovery(self, company_list: Optional[List[Dict[str, Any]]] = None, max_workers: int = 10, auto_add: bool = False) -> Dict[str, List[Dict[str, Any]]]:
        target_list = company_list or INDIAN_COMPANIES
        logger.info("Starting ATS board discovery for %d companies (workers: %d)...", len(target_list), max_workers)

        discovered: Dict[str, List[Dict[str, Any]]] = {
            "greenhouse": [],
            "lever": [],
            "ashby": [],
            "smartrecruiters": []
        }
        total_matches = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_company = {
                executor.submit(self.probe_company, comp): comp["name"]
                for comp in target_list
            }

            for future in as_completed(future_to_company):
                cname = future_to_company[future]
                try:
                    matches = future.result()
                    for m in matches:
                        plat = m["platform"]
                        discovered[plat].append(m)
                        total_matches += 1
                        logger.info("  [DISCOVERED] %s -> %s (slug: %s, jobs: %d)", m['company'], plat.upper(), m['slug'], m['jobs_count'])
                except Exception as ex:
                    logger.debug("Error probing company %s: %s", cname, ex)

        logger.info("Discovery complete. Discovered %d ATS boards across %d companies.", total_matches, len(target_list))
        
        if auto_add and total_matches > 0:
            self._auto_add_to_seeds(discovered)
            
        return discovered

    def _auto_add_to_seeds(self, discovered: Dict[str, List[Dict[str, Any]]]):
        import os
        base_dir = os.path.dirname(os.path.dirname(__file__))
        
        for platform, items in discovered.items():
            if not items:
                continue
                
            seed_file = os.path.join(base_dir, "pipelines", platform, "seed_companies.py")
            if not os.path.exists(seed_file):
                logger.warning(f"Seed file not found: {seed_file}")
                continue
                
            with open(seed_file, "r") as f:
                content = f.read()
                
            # Find the last closing bracket of the list
            last_bracket_idx = content.rfind("]")
            if last_bracket_idx == -1:
                continue
                
            before_bracket = content[:last_bracket_idx].rstrip()
            if before_bracket and not before_bracket.endswith(',') and not before_bracket.endswith('['):
                content = before_bracket + ",\n" + content[last_bracket_idx:]
                last_bracket_idx = content.rfind("]")
                
            new_entries = []
            for item in items:
                name = item["company"].replace('"', '\\"')
                slug = item["slug"].replace('"', '\\"')
                if platform == "smartrecruiters":
                    new_entries.append(f'    {{"name": "{name}", "slug": "{slug}", "country": "in"}},')
                else:
                    new_entries.append(f'    {{"name": "{name}", "slug": "{slug}"}},')
                    
            if new_entries:
                insert_str = "\n".join(new_entries) + "\n"
                new_content = content[:last_bracket_idx] + insert_str + content[last_bracket_idx:]
                
                with open(seed_file, "w") as f:
                    f.write(new_content)
                logger.info(f"Auto-added {len(new_entries)} companies to {platform} seed list.")

if __name__ == "__main__":
    engine = CompanyDiscoveryEngine()
    # Test discovery on 15 well-known companies
    test_sample = INDIAN_COMPANIES[:15]
    print(f"Running test discovery on {len(test_sample)} companies...")
    results = engine.run_discovery(test_sample, max_workers=6)
    for plat, items in results.items():
        print(f"\n[{plat.upper()}] Discovered {len(items)} boards:")
        for item in items:
            print(f"  - {item['company']}: {item['slug']} ({item['jobs_count']} jobs)")
