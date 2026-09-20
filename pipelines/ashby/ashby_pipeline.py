import time
from typing import List, Optional
from bs4 import BeautifulSoup

from core.time_utils import parse_posted_at
from pipelines.base_pipeline import BaseJobPipeline, NormalizedJobDto
from .ashby_client import AshbyClient
from .seed_companies import ASHBY_SEED_COMPANIES

class AshbyPipeline(BaseJobPipeline):
    """
    Autonomous pipeline for ingesting verified job postings directly from
    Ashby ATS public endpoints for high-growth tech and AI companies.
    """

    @property
    def pipeline_name(self) -> str:
        return "Ashby ATS"

    @property
    def platform_code(self) -> str:
        return "ashby"

    def __init__(self, target_companies=None, max_companies: int = 15):
        super().__init__()
        self.client = AshbyClient()
        self.target_companies = target_companies or ASHBY_SEED_COMPANIES[:max_companies]

    def _clean_html_content(self, html_str: str) -> str:
        if not html_str:
            return ""
        try:
            soup = BeautifulSoup(html_str, "html.parser")
            return soup.get_text(separator="\n").strip()
        except Exception:
            return html_str

    def fetch_jobs(self) -> List[NormalizedJobDto]:
        normalized_jobs: List[NormalizedJobDto] = []
        self.logger.info("Ingesting Ashby jobs across %d target companies...", len(self.target_companies))

        for company in self.target_companies:
            name = company["name"]
            slug = company["slug"]

            try:
                self.logger.info("Querying Ashby board for '%s' (slug: %s)...", name, slug)
                raw_jobs = self.client.fetch_jobs(slug)
                self.logger.info("Retrieved %d jobs for '%s'", len(raw_jobs), name)

                for rj in raw_jobs:
                    title = rj.get("title", "").strip()
                    apply_url = rj.get("jobUrl") or rj.get("applyUrl")
                    if not title or not apply_url:
                        continue

                    # Location
                    location_str = rj.get("location")
                    if not location_str or not str(location_str).strip():
                        location_str = "Remote"

                    # Description
                    desc = rj.get("descriptionPlain")
                    if not desc:
                        raw_html = rj.get("descriptionHtml") or rj.get("description", "")
                        desc = self._clean_html_content(raw_html)

                    # Employment type
                    emp_type = rj.get("employmentType") or "FullTime"
                    emp_type_clean = "full-time" if "full" in str(emp_type).lower() else str(emp_type).lower()

                    # Posted at timestamp
                    published_at = rj.get("publishedAt", "Recently")

                    # Compensation
                    min_sal = None
                    max_sal = None
                    currency = "USD"
                    comp = rj.get("compensation")
                    if isinstance(comp, dict):
                        min_sal = comp.get("minSalary")
                        max_sal = comp.get("maxSalary")
                        currency = comp.get("currency", "USD")

                    normalized_jobs.append(
                        NormalizedJobDto(
                            title=title,
                            company_name=name,
                            link=apply_url.strip(),
                            location=str(location_str).strip(),
                            description=desc.strip() if desc else "",
                            employment_type=emp_type_clean,
                            posted_at=parse_posted_at(published_at),
                            min_salary=min_sal,
                            max_salary=max_sal,
                            currency=currency
                        )
                    )

                time.sleep(0.2)

            except Exception as company_err:
                self.logger.warning("Error fetching Ashby board for '%s': %s", name, company_err)
                continue

        return normalized_jobs

if __name__ == "__main__":
    pipeline = AshbyPipeline()
    result = pipeline.run()
    print(f"\n[Ashby Pipeline Result] Status: {result.status} | Fetched: {result.jobs_fetched} | Added: {result.new_jobs_added} | Duration: {result.duration_seconds}s")
