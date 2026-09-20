import re
import time
from typing import Optional
import requests
from bs4 import BeautifulSoup

from core.experience_filter import YearsOfExperienceFilter
from core.db import get_db_cursor

class JobQualificationEnricher:
    """
    Enriches raw job postings with full descriptions scraped from target platforms,
    and applies candidate qualification rules (Years of Experience, Restricted Skills).
    """

    def __init__(self, *args, user_id: Optional[int] = None, max_years_of_experience: Optional[int] = None, **kwargs):
        # Backward compatibility for legacy positional db_path argument
        if args and isinstance(args[0], str) and user_id is None:
            # If called as JobEnricher(database_url, user_id=1)
            pass
        self.user_id = user_id or kwargs.get('user_id')
        self.user_configuration = {}
        
        # Load user configuration preferences from database
        if self.user_id:
            with get_db_cursor(commit=False) as cursor:
                cursor.execute("SELECT config FROM users WHERE id = %s", (self.user_id,))
                user_row = cursor.fetchone()
                if user_row:
                    self.user_configuration = user_row.get('config') or {}

        if max_years_of_experience is None:
            self.max_years_of_experience = self.user_configuration.get("max_yoe", 2)
        else:
            self.max_years_of_experience = max_years_of_experience
            
        self.experience_filter = YearsOfExperienceFilter(self.max_years_of_experience)
        
        self.http_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }

    def fetch_full_job_description(self, job_url: str) -> Optional[str]:
        """
        Scrapes and extracts full job specification text from a job posting URL.
        """
        if not job_url or "linkedin.com/jobs/view" not in job_url:
            return None
            
        try:
            response = requests.get(job_url, headers=self.http_headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                description_element = soup.find('div', class_='show-more-less-html__markup')
                if description_element:
                    for line_break in soup.find_all("br"):
                        line_break.replace_with("\n")
                    for paragraph in soup.find_all("p"):
                        paragraph.insert_before("\n")
                        paragraph.insert_after("\n")
                    return description_element.text.strip()
        except Exception as error:
            print(f"[WARN] Error fetching description from {job_url}: {error}")
            
        return None

    def enrich_and_qualify_discovered_jobs(self, logger=None):
        """
        Processes all jobs in 'discovered' status for the current user:
        1. Fetches full job specifications
        2. Evaluates restricted tech skills
        3. Evaluates years of experience ceiling
        4. Updates status to 'enriched' or 'discarded'
        """
        def log_message(msg):
            if logger:
                logger(msg)
            else:
                print(msg)
            
        if not self.user_id:
            log_message("[WARN] [Enrichment] JobQualificationEnricher requires a valid user_id.")
            return
            
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT gj.id::text AS id, gj.link, gj.title, COALESCE(c.name, 'Unknown Company') AS company
                FROM candidate_job_states cjs
                JOIN global_jobs gj ON cjs.job_id = gj.id
                LEFT JOIN companies c ON gj.company_id = c.id
                WHERE cjs.status = 'discovered' AND cjs.user_id = %s
            """, (self.user_id,))
            jobs_to_enrich = cursor.fetchall()
        
        log_message(f"[INFO] [Enrichment] Analyzing {len(jobs_to_enrich)} pending opportunities for specification details & qualification criteria...")
        
        qualified_count = 0
        disqualified_count = 0
        
        for job_posting in jobs_to_enrich:
            job_id = job_posting['id']
            job_link = job_posting['link']
            job_title = job_posting['title']
            job_company = job_posting['company']
            
            full_description = self.fetch_full_job_description(job_link)
            if full_description:
                # 1. Evaluate ignored/restricted skills with exact word boundaries
                matched_restricted_skill = None
                for restricted_skill in self.user_configuration.get("ignored_skills", []):
                    clean_skill = restricted_skill.strip()
                    if clean_skill and re.search(r'\b' + re.escape(clean_skill) + r'\b', full_description, re.IGNORECASE):
                        matched_restricted_skill = clean_skill
                        break
                
                if matched_restricted_skill:
                    disqualification_reason = f"Restricted tech: {matched_restricted_skill}"
                    with get_db_cursor() as cursor:
                        cursor.execute("""
                            UPDATE global_jobs SET description = %s, updated_at = NOW() WHERE id = %s;
                            UPDATE candidate_job_states 
                            SET status = 'discarded', is_qualified = FALSE, discard_reason = %s, updated_at = NOW() 
                            WHERE job_id = %s AND user_id = %s;
                        """, (full_description, job_id, disqualification_reason, job_id, self.user_id))
                    disqualified_count += 1
                    log_message(f"[WARN] [Enrichment] Filtered: '{job_title}' @ '{job_company}' — Matched restricted skill '{matched_restricted_skill}'")
                
                # 2. Evaluate Years of Experience requirement
                elif not self.experience_filter.is_candidate_qualified(full_description):
                    disqualification_reason = f"Requires >{self.max_years_of_experience} yrs YOE"
                    with get_db_cursor() as cursor:
                        cursor.execute("""
                            UPDATE global_jobs SET description = %s, updated_at = NOW() WHERE id = %s;
                            UPDATE candidate_job_states 
                            SET status = 'discarded', is_qualified = FALSE, discard_reason = %s, updated_at = NOW() 
                            WHERE job_id = %s AND user_id = %s;
                        """, (full_description, job_id, disqualification_reason, job_id, self.user_id))
                    disqualified_count += 1
                    log_message(f"[WARN] [Enrichment] Filtered: '{job_title}' @ '{job_company}' — Specification requires YOE exceeding candidate maximum ({self.max_years_of_experience} yrs)")
                else:
                    with get_db_cursor() as cursor:
                        cursor.execute("""
                            UPDATE global_jobs SET description = %s, updated_at = NOW() WHERE id = %s;
                            UPDATE candidate_job_states 
                            SET status = 'enriched', is_qualified = TRUE, updated_at = NOW() 
                            WHERE job_id = %s AND user_id = %s;
                        """, (full_description, job_id, job_id, self.user_id))
                    qualified_count += 1
                    log_message(f"[INFO] [Enrichment] Qualified: '{job_title}' @ '{job_company}' — Meets qualification threshold")
            else:
                # Fallback to snippet description if full description scrape fails
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        UPDATE candidate_job_states 
                        SET status = 'enriched', is_qualified = TRUE, updated_at = NOW() 
                        WHERE job_id = %s AND user_id = %s;
                    """, (job_id, self.user_id))
                qualified_count += 1
                
            time.sleep(1) # Pacing delay for rate limit protection
            
        log_message(f"[INFO] [Enrichment] Analysis complete: {qualified_count} qualified, {disqualified_count} discarded across {len(jobs_to_enrich)} roles.")

    # Backward compatibility aliases
    get_full_description = fetch_full_job_description
    enrich_new_jobs = enrich_and_qualify_discovered_jobs
    yoe_filter = property(lambda self: self.experience_filter)
    max_yoe = property(lambda self: self.max_years_of_experience)
    config = property(lambda self: self.user_configuration)

# Backward compatibility alias
JobEnricher = JobQualificationEnricher
