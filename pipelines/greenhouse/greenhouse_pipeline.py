import time
from typing import List
from bs4 import BeautifulSoup

from core.time_utils import parse_posted_at
from pipelines.base_pipeline import BaseJobPipeline, NormalizedJobDto
from .greenhouse_client import GreenhouseClient
from .seed_companies import GREENHOUSE_SEED_COMPANIES

class GreenhousePipeline(BaseJobPipeline):
    """
    Autonomous pipeline for ingesting verified job postings directly from
    company Greenhouse ATS board endpoints.
    """

    @property
    def pipeline_name(self) -> str:
        return "Greenhouse ATS"

    @property
    def platform_code(self) -> str:
        return "greenhouse"

    def __init__(self, target_companies=None, max_companies: int = 25):
        super().__init__()
        self.client = GreenhouseClient()
        self.target_companies = target_companies or GREENHOUSE_SEED_COMPANIES[:max_companies]

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

        self.logger.info("Ingesting Greenhouse jobs across %d target companies...", len(self.target_companies))

        for company in self.target_companies:
            name = company["name"]
            slug = company["slug"]

            try:
                self.logger.info("Querying Greenhouse board for '%s' (slug: %s)...", name, slug)
                raw_jobs = self.client.fetch_board_jobs(slug, include_content=True)
                self.logger.info("Retrieved %d jobs for '%s'", len(raw_jobs), name)

                for rj in raw_jobs:
                    title = rj.get("title", "").strip()
                    apply_url = rj.get("absolute_url", "").strip()
                    if not title or not apply_url:
                        continue

                    # Extract location
                    loc_data = rj.get("location") or {}
                    location_str = loc_data.get("name") if isinstance(loc_data, dict) else str(loc_data)
                    location_str = location_str.strip() if location_str else "Remote"

                    # Clean description
                    raw_content = rj.get("content", "")
                    clean_desc = self._clean_html_content(raw_content)

                    # Posted at timestamp
                    updated_at = rj.get("updated_at")
                    posted_at_dt = parse_posted_at(updated_at)

                    normalized_jobs.append(
                        NormalizedJobDto(
                            title=title,
                            company_name=name,
                            link=apply_url,
                            location=location_str,
                            description=clean_desc,
                            employment_type="full-time",
                            posted_at=posted_at_dt,
                            currency="USD"
                        )
                    )

                # Polite spacing between company boards (0.2s)
                time.sleep(0.2)

            except Exception as company_err:
                self.logger.warning("Error fetching Greenhouse board for '%s': %s", name, company_err)
                continue

        return normalized_jobs

if __name__ == "__main__":
    pipeline = GreenhousePipeline()
    result = pipeline.run()
    print(f"\n[Greenhouse Pipeline Result] Status: {result.status} | Fetched: {result.jobs_fetched} | Added: {result.new_jobs_added} | Duration: {result.duration_seconds}s")
