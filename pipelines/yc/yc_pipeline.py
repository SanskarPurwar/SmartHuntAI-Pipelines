from typing import List
from pipelines.base_pipeline import BaseJobPipeline, NormalizedJobDto
from .yc_client import YCClient

class YCPipeline(BaseJobPipeline):
    """
    Autonomous pipeline for ingesting verified job postings from Y Combinator companies
    via Hacker News Job Stories and Ask HN: Who is Hiring threads.
    """

    @property
    def pipeline_name(self) -> str:
        return "Y Combinator (Work at a Startup & HN)"

    @property
    def platform_code(self) -> str:
        return "yc"

    def __init__(self, max_stories: int = 30, max_comments: int = 40):
        super().__init__()
        self.client = YCClient()
        self.max_stories = max_stories
        self.max_comments = max_comments

    def fetch_jobs(self) -> List[NormalizedJobDto]:
        all_dtos: List[NormalizedJobDto] = []
        seen_links = set()

        # 1. Fetch official YC job stories
        self.logger.info("Fetching YC company job stories...")
        stories = self.client.fetch_yc_job_stories(limit=self.max_stories)
        self.logger.info("Retrieved %d YC job stories", len(stories))
        for item in stories:
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

        # 2. Fetch recent Who is Hiring comments
        self.logger.info("Fetching Ask HN: Who is hiring listings...")
        comments = self.client.fetch_who_is_hiring_comments(limit=self.max_comments)
        self.logger.info("Retrieved %d Ask HN job comments", len(comments))
        for item in comments:
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
