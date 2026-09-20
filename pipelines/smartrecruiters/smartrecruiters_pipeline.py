"""
Autonomous pipeline for ingesting verified job postings directly from
SmartRecruiters Public Posting API.
"""

import time
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from core.time_utils import parse_posted_at
from pipelines.base_pipeline import BaseJobPipeline, NormalizedJobDto
from .smartrecruiters_client import SmartRecruitersClient
from .seed_companies import SMARTRECRUITERS_SEED_COMPANIES

class SmartRecruitersPipeline(BaseJobPipeline):
    """
    Autonomous pipeline for ingesting verified job postings from SmartRecruiters ATS.
    Focuses heavily on Indian operations and enterprise tech opportunities.
    """

    @property
    def pipeline_name(self) -> str:
        return "SmartRecruiters ATS"

    @property
    def platform_code(self) -> str:
        return "smartrecruiters"

    def __init__(
        self,
        target_companies: Optional[List[Dict[str, str]]] = None,
        max_companies: int = 30,
        max_jobs_per_company: int = 150,
        india_only: bool = True
    ):
        super().__init__()
        self.client = SmartRecruitersClient()
        self.target_companies = target_companies or SMARTRECRUITERS_SEED_COMPANIES[:max_companies]
        self.max_jobs_per_company = max_jobs_per_company
        self.india_only = india_only

    def _clean_html(self, html_str: str) -> str:
        if not html_str:
            return ""
        try:
            soup = BeautifulSoup(html_str, "html.parser")
            return soup.get_text(separator="\n").strip()
        except Exception:
            return html_str

    def _extract_pure_description(self, posting: Dict[str, Any]) -> str:
        """
        Extracts only job description, qualifications, and additional info.
        Explicitly excludes company history / about company to prevent false positive YOE.
        """
        job_ad = posting.get("jobAd") or {}
        sections = job_ad.get("sections") or {}

        parts = []
        # 1. Job Description / Responsibilities
        jd_sec = sections.get("jobDescription") or {}
        if jd_sec.get("text"):
            parts.append(self._clean_html(jd_sec["text"]))

        # 2. Qualifications & Requirements (Primary YOE & Tech Stack source)
        qual_sec = sections.get("qualifications") or {}
        if qual_sec.get("text"):
            parts.append(self._clean_html(qual_sec["text"]))

        # 3. Additional Information
        add_sec = sections.get("additionalInformation") or {}
        if add_sec.get("text"):
            parts.append(self._clean_html(add_sec["text"]))

        if parts:
            return "\n\n".join(parts).strip()

        # Fallback to general description if structured sections aren't available
        return posting.get("description") or posting.get("name") or ""

    def fetch_jobs(self) -> List[NormalizedJobDto]:
        normalized_jobs: List[NormalizedJobDto] = []

        self.logger.info("Ingesting SmartRecruiters jobs across %d target companies...", len(self.target_companies))

        for company in self.target_companies:
            name = company["name"]
            slug = company["slug"]
            country_filter = "in" if self.india_only else company.get("country")

            try:
                self.logger.info("Querying SmartRecruiters for '%s' (slug: %s, country: %s)...", name, slug, country_filter)
                postings = self.client.fetch_postings_with_details(
                    slug,
                    country=country_filter,
                    max_jobs=self.max_jobs_per_company
                )
                self.logger.info("Retrieved %d postings with details for '%s'", len(postings), name)

                for p in postings:
                    title = (p.get("name") or "").strip()
                    pid = str(p.get("id"))
                    if not title or not pid:
                        continue

                    # Direct apply URL / Career portal URL
                    link = (
                        p.get("postingUrl")
                        or p.get("applyUrl")
                        or f"https://jobs.smartrecruiters.com/{slug}/{pid}"
                    ).strip()

                    # Location
                    loc_dict = p.get("location") or {}
                    city = loc_dict.get("city", "")
                    country_code = loc_dict.get("country", "").upper()
                    full_loc = loc_dict.get("fullLocation") or (f"{city}, {country_code}" if city else country_code or "India")

                    # Description: excludes company intro to avoid YOE hallucinations
                    clean_description = self._extract_pure_description(p)

                    # Employment type
                    emp_type_label = (p.get("typeOfEmployment") or {}).get("label") or "full-time"

                    # Posted timestamp
                    posted_at_dt = parse_posted_at(p.get("releasedDate"))

                    # Currency default for India jobs
                    currency = "INR" if country_code == "IN" or "india" in full_loc.lower() else "USD"

                    normalized_jobs.append(
                        NormalizedJobDto(
                            title=title,
                            company_name=name,
                            link=link,
                            location=full_loc,
                            description=clean_description,
                            employment_type=emp_type_label,
                            posted_at=posted_at_dt,
                            currency=currency
                        )
                    )

                # Polite spacing
                time.sleep(0.2)

            except Exception as company_err:
                self.logger.warning("Error fetching SmartRecruiters for '%s': %s", name, company_err)
                continue

        return normalized_jobs

if __name__ == "__main__":
    pipeline = SmartRecruitersPipeline()
    result = pipeline.run()
    print(f"\n[SmartRecruiters Result] Status: {result.status} | Fetched: {result.jobs_fetched} | Added: {result.new_jobs_added} | Duration: {result.duration_seconds}s")
