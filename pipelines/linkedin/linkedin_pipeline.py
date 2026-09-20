from typing import List
from pipelines.base_pipeline import BaseJobPipeline, NormalizedJobDto
from .linkedin_client import LinkedInClient

class LinkedInPipeline(BaseJobPipeline):
    """
    Autonomous pipeline for ingesting verified job postings from LinkedIn Guest Search API.
    """

    @property
    def pipeline_name(self) -> str:
        return "LinkedIn Jobs"

    @property
    def platform_code(self) -> str:
        return "linkedin_jobs"

    def __init__(self, search_queries: List[str] = None):
        super().__init__()
        self.client = LinkedInClient()
        self.search_queries = search_queries or [
            "Software Engineer",
            "Full Stack Developer",
            "Backend Engineer",
            "Frontend Engineer",
            "Python Developer",
            "DevOps Engineer"
        ]

    def fetch_jobs(self) -> List[NormalizedJobDto]:
        all_dtos: List[NormalizedJobDto] = []
        seen_links = set()

        for query in self.search_queries:
            self.logger.info("Executing LinkedIn guest query: '%s'...", query)
            raw_jobs = self.client.fetch_guest_jobs(keywords=query, location="Remote")
            self.logger.info("Retrieved %d jobs for query '%s'", len(raw_jobs), query)

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
                    description=item.get("description", ""),
                    posted_at=item.get("posted_at")
                ))

        return all_dtos
