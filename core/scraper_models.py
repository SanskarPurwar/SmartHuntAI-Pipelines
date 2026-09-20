from pydantic import BaseModel
from typing import Optional, Union
from datetime import datetime

class JobPostingScraperModel(BaseModel):
    """
    Standard schema for raw job postings scraped from external platforms
    (LinkedIn, DuckDuckGo, Job Boards).
    """
    title: str
    company: str
    location: str
    link: str
    source: str = "linkedin_jobs"
    posted_at: Optional[Union[str, datetime]] = None
    description: Optional[str] = None

# Backward compatibility alias
JobPosting = JobPostingScraperModel
