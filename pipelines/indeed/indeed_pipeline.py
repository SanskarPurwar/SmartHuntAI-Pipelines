from typing import List
from pipelines.base_pipeline import BaseJobPipeline, NormalizedJobDto
from .indeed_client import IndeedClient

class IndeedPipeline(BaseJobPipeline):
    """
    Autonomous pipeline for ingesting verified job postings from Indeed.
    """

    @property
    def pipeline_name(self) -> str:
        return "Indeed Jobs"

    @property
    def platform_code(self) -> str:
        return "indeed"

    def __init__(self, search_roles: List[str] = None):
        super().__init__()
        self.client = IndeedClient()
        self.search_roles = search_roles or [
            "Software Engineer",
            "Full Stack Developer",
            "Backend Engineer",
            "Frontend Engineer",
            "Python Engineer",
            "Data Engineer"
        ]

    def fetch_jobs(self) -> List[NormalizedJobDto]:
        all_dtos: List[NormalizedJobDto] = []
        seen_links = set()

        for role in self.search_roles:
            self.logger.info("Executing Indeed query: '%s'...", role)
            raw_jobs = self.client.fetch_jobs(query=role, location="remote")
            self.logger.info("Retrieved %d jobs for '%s' from Indeed", len(raw_jobs), role)

            for item in raw_jobs:
                link = item.get("link", "").strip()
                if not link or link in seen_links:
                    continue
                seen_links.add(link)

                all_dtos.append(NormalizedJobDto(
                    title=item["title"],
                    company_name=item["company_name"],
                    link=link,
                    location=item.get("location", "Remote"),
                    description=item.get("description", "")
                ))

        if not all_dtos:
            self.logger.info("Direct Indeed scraping returned 0 results (anti-bot triggered); activating verified syndication fallback...")
            syndicated = self.client.fetch_syndicated_jobs(limit=50)
            for item in syndicated:
                link = item.get("link", "").strip()
                if not link or link in seen_links:
                    continue
                seen_links.add(link)
                all_dtos.append(NormalizedJobDto(
                    title=item["title"],
                    company_name=item["company_name"],
                    link=link,
                    location=item.get("location", "Remote"),
                    description=item.get("description", "")
                ))

        return all_dtos
