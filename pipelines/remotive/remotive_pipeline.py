import re
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup

from core.time_utils import parse_posted_at
from pipelines.base_pipeline import BaseJobPipeline, NormalizedJobDto
from .remotive_client import RemotiveClient

class RemotivePipeline(BaseJobPipeline):
    """
    Autonomous pipeline for ingesting verified remote developer and tech
    opportunities from Remotive's global API.
    """

    @property
    def pipeline_name(self) -> str:
        return "Remotive API"

    @property
    def platform_code(self) -> str:
        return "remotive"

    def __init__(self, category: Optional[str] = "software-dev", limit: Optional[int] = 100):
        super().__init__()
        self.client = RemotiveClient()
        self.category = category
        self.limit = limit

    def _clean_html_content(self, html_str: str) -> str:
        if not html_str:
            return ""
        try:
            soup = BeautifulSoup(html_str, "html.parser")
            return soup.get_text(separator="\n").strip()
        except Exception:
            return html_str

    def _parse_salary(self, salary_str: str) -> Tuple[Optional[float], Optional[float], str]:
        """
        Parses salary strings like '$120,000 - $150,000' or '$80k - $100k'
        """
        if not salary_str:
            return None, None, "USD"

        currency = "USD"
        if "€" in salary_str or "EUR" in salary_str:
            currency = "EUR"
        elif "£" in salary_str or "GBP" in salary_str:
            currency = "GBP"

        # Find numbers
        numbers = re.findall(r'(\d+[\d,.]*)\s*(k)?', salary_str, re.IGNORECASE)
        vals = []
        for num_str, is_k in numbers:
            try:
                cleaned = num_str.replace(',', '')
                val = float(cleaned)
                if is_k:
                    val *= 1000
                vals.append(val)
            except ValueError:
                continue

        if len(vals) >= 2:
            return min(vals), max(vals), currency
        elif len(vals) == 1:
            return vals[0], vals[0], currency
        return None, None, currency

    def fetch_jobs(self) -> List[NormalizedJobDto]:
        normalized_jobs: List[NormalizedJobDto] = []
        self.logger.info("Ingesting remote tech postings from Remotive API...")

        raw_jobs = self.client.fetch_remote_jobs(category=self.category, limit=self.limit)
        self.logger.info("Processing %d raw jobs from Remotive", len(raw_jobs))

        for rj in raw_jobs:
            title = rj.get("title", "").strip()
            company_name = rj.get("company_name", "").strip()
            apply_url = rj.get("url", "").strip()

            if not title or not company_name or not apply_url:
                continue

            # Location formatting
            loc = rj.get("candidate_required_location")
            location_str = f"Remote ({loc.strip()})" if loc and loc.strip() else "Remote"

            # Clean HTML description
            raw_html = rj.get("description", "")
            desc = self._clean_html_content(raw_html)

            # Employment type
            job_type = rj.get("job_type") or "full_time"
            employment_type = str(job_type).replace("_", "-").lower()

            # Publication date
            pub_date = rj.get("publication_date", "Recently")

            # Salary extraction
            salary_str = rj.get("salary", "")
            min_sal, max_sal, curr = self._parse_salary(salary_str)

            normalized_jobs.append(
                NormalizedJobDto(
                    title=title,
                    company_name=company_name,
                    link=apply_url,
                    location=location_str,
                    description=desc,
                    employment_type=employment_type,
                    posted_at=parse_posted_at(pub_date),
                    min_salary=min_sal,
                    max_salary=max_sal,
                    currency=curr
                )
            )

        return normalized_jobs

if __name__ == "__main__":
    pipeline = RemotivePipeline(limit=50)
    result = pipeline.run()
    print(f"\n[Remotive Pipeline Result] Status: {result.status} | Fetched: {result.jobs_fetched} | Added: {result.new_jobs_added} | Duration: {result.duration_seconds}s")
