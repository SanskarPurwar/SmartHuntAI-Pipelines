import time
from datetime import datetime, timezone
from typing import List, Optional
from bs4 import BeautifulSoup

from core.time_utils import parse_posted_at
from pipelines.base_pipeline import BaseJobPipeline, NormalizedJobDto
from .lever_client import LeverClient
from .seed_companies import LEVER_SEED_COMPANIES

class LeverPipeline(BaseJobPipeline):
    """
    Autonomous pipeline for ingesting verified job postings directly from
    company Lever ATS public endpoints.
    """

    @property
    def pipeline_name(self) -> str:
        return "Lever ATS"

    @property
    def platform_code(self) -> str:
        return "lever"

    def __init__(self, target_companies=None, max_companies: int = 20):
        super().__init__()
        self.client = LeverClient()
        self.target_companies = target_companies or LEVER_SEED_COMPANIES[:max_companies]

    def _clean_html_content(self, html_str: str) -> str:
        if not html_str:
            return ""
        try:
            soup = BeautifulSoup(html_str, "html.parser")
            return soup.get_text(separator="\n").strip()
        except Exception:
            return html_str

    def _format_created_at(self, timestamp_ms: Optional[int]) -> datetime:
        return parse_posted_at(timestamp_ms)

    def fetch_jobs(self) -> List[NormalizedJobDto]:
        normalized_jobs: List[NormalizedJobDto] = []
        self.logger.info("Ingesting Lever jobs across %d target companies...", len(self.target_companies))

        for company in self.target_companies:
            name = company["name"]
            slug = company["slug"]

            try:
                self.logger.info("Querying Lever board for '%s' (slug: %s)...", name, slug)
                raw_jobs = self.client.fetch_postings(slug)
                self.logger.info("Retrieved %d jobs for '%s'", len(raw_jobs), name)

                for rj in raw_jobs:
                    title = rj.get("text", "").strip()
                    apply_url = rj.get("hostedUrl") or rj.get("applyUrl")
                    if not title or not apply_url:
                        continue

                    # Categories extraction
                    categories = rj.get("categories") or {}
                    location_str = categories.get("location")
                    if not location_str:
                        workplace = rj.get("workplaceType")
                        location_str = workplace.capitalize() if workplace else "Remote"

                    # Description extraction
                    desc = rj.get("descriptionPlain") or rj.get("descriptionBodyPlain")
                    if not desc:
                        raw_body = rj.get("description") or rj.get("descriptionBody", "")
                        desc = self._clean_html_content(raw_body)

                    # Employment type
                    commitment = categories.get("commitment") or "full-time"

                    # Timestamp
                    posted_str = self._format_created_at(rj.get("createdAt"))

                    normalized_jobs.append(
                        NormalizedJobDto(
                            title=title,
                            company_name=name,
                            link=apply_url.strip(),
                            location=location_str.strip(),
                            description=desc.strip() if desc else "",
                            employment_type=commitment.lower(),
                            posted_at=posted_str,
                            currency="USD"
                        )
                    )

                time.sleep(0.2)

            except Exception as company_err:
                self.logger.warning("Error fetching Lever board for '%s': %s", name, company_err)
                continue

        return normalized_jobs

if __name__ == "__main__":
    pipeline = LeverPipeline()
    result = pipeline.run()
    print(f"\n[Lever Pipeline Result] Status: {result.status} | Fetched: {result.jobs_fetched} | Added: {result.new_jobs_added} | Duration: {result.duration_seconds}s")
