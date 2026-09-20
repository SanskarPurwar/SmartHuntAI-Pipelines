import time
import traceback
from abc import ABC, abstractmethod
from typing import List, Optional, Union
from datetime import datetime
from dataclasses import dataclass

from repositories.company_repository import CompanyRepository
from repositories.platform_repository import PlatformRepository
from repositories.global_job_repository import GlobalJobRepository
from core.time_utils import parse_posted_at
from core.logger import setup_logger

@dataclass
class NormalizedJobDto:
    """
    Normalized, provider-agnostic data transfer object for ingested job postings.
    """
    title: str
    company_name: str
    link: str
    location: str = "Remote"
    description: str = ""
    employment_type: str = "full-time"
    posted_at: Optional[Union[str, int, float, datetime]] = None
    yoe: Optional[int] = None
    min_salary: Optional[float] = None
    max_salary: Optional[float] = None
    currency: str = "USD"
    company_logo_url: Optional[str] = None
    tech_stack: Optional[List[str]] = None
    yoe_confidence: Optional[str] = None
    work_mode: Optional[str] = None
    job_category: Optional[str] = None

@dataclass
class PipelineRunResult:
    """
    Standardized execution summary and telemetry for a pipeline run.
    """
    pipeline_name: str
    platform_code: str
    status: str              # 'success', 'partial_failure', 'failed'
    jobs_fetched: int
    new_jobs_added: int
    duration_seconds: float
    error_message: Optional[str] = None

class BaseJobPipeline(ABC):
    """
    Abstract Base Contract for autonomous job data ingestion pipelines.
    Guarantees strict fault isolation, standardized DTO output, and platform telemetry.
    """

    def __init__(self):
        self.logger = setup_logger(f"pipeline.{self.platform_code}")

    @property
    @abstractmethod
    def pipeline_name(self) -> str:
        """Human-readable display name (e.g. 'Greenhouse ATS')"""
        pass

    @property
    @abstractmethod
    def platform_code(self) -> str:
        """Database platform key matching platforms.name (e.g. 'greenhouse')"""
        pass

    @abstractmethod
    def fetch_jobs(self) -> List[NormalizedJobDto]:
        """
        Fetch, extract, and normalize job postings from this specific source.
        Must return a list of NormalizedJobDto objects.
        """
        pass

    def run(self) -> PipelineRunResult:
        """
        Executes the pipeline with circuit-breaker isolation, database persistence,
        and telemetry tracking. Exceptions are caught and recorded, never bubbling up
        to disrupt other concurrent pipelines.
        """
        start_time = time.time()
        self.logger.info(">>> Starting pipeline execution: %s (%s)", self.pipeline_name, self.platform_code)

        platform_record = PlatformRepository.find_by_name(self.platform_code)
        platform_id = platform_record['id'] if platform_record else None

        jobs_fetched = 0
        new_jobs_added = 0
        run_status = 'success'
        error_msg = None

        try:
            # 1. Source-specific extraction
            raw_jobs = self.fetch_jobs()
            jobs_fetched = len(raw_jobs)
            self.logger.info("Fetched %d opportunities from %s", jobs_fetched, self.pipeline_name)

            # 2. Universal DB normalization & persistence
            all_company_names = [(job.company_name or "Hiring Company").strip()[:200] for job in raw_jobs]
            company_cache = CompanyRepository.find_or_create_batch(all_company_names)
            jobs_to_upsert = []
            for job in raw_jobs:
                try:
                    cname = (job.company_name or "Hiring Company").strip()[:200]
                    company_id = company_cache.get(cname)

                    jobs_to_upsert.append({
                        "title": (job.title or "Software Role").strip()[:300],
                        "description": job.description or "",
                        "location": (job.location or "Remote").strip()[:200],
                        "company_id": company_id,
                        "source_platform_id": platform_id,
                        "link": job.link.strip(),
                        "employment_type": job.employment_type,
                        "work_mode": job.work_mode,
                        "job_category": job.job_category,
                        "posted_at": parse_posted_at(job.posted_at),
                        "yoe": job.yoe,
                        "min_salary": job.min_salary,
                        "max_salary": job.max_salary,
                        "currency": job.currency or "USD"
                    })
                except Exception as item_err:
                    self.logger.warning("Failed to normalize job '%s': %s", getattr(job, 'title', 'unknown'), item_err)

            if jobs_to_upsert:
                from core.job_enrichment import enrich_job_data
                from core.yoe_ai_resolver import YOEAIResolver

                enriched_jobs = [enrich_job_data(j) for j in jobs_to_upsert]
                ambiguous_jobs = [j for j in enriched_jobs if j.get('yoe_confidence') in ('medium', 'low', 'unknown')]

                if ambiguous_jobs:
                    self.logger.info("Routing %d / %d ambiguous jobs to Gemini Flash-Lite resolver...", len(ambiguous_jobs), len(enriched_jobs))
                    resolver = YOEAIResolver()
                    resolved_chunk = resolver.resolve_batch(ambiguous_jobs)
                    resolved_map = {str(j.get('link')): j for j in resolved_chunk}
                    final_jobs = [resolved_map.get(str(j.get('link')), j) for j in enriched_jobs]
                else:
                    final_jobs = enriched_jobs

                new_jobs_added = GlobalJobRepository.upsert_batch(final_jobs)

            self.logger.info("Committed %d opportunities to global_jobs", new_jobs_added)

        except Exception as pipeline_fatal_error:
            run_status = 'failed'
            error_msg = f"{type(pipeline_fatal_error).__name__}: {str(pipeline_fatal_error)}\n{traceback.format_exc()}"
            self.logger.error("Pipeline failure in %s: %s", self.pipeline_name, pipeline_fatal_error)

        duration = round(time.time() - start_time, 2)

        # 3. Record telemetry to PostgreSQL platforms table
        try:
            PlatformRepository.record_run_telemetry(
                platform_code=self.platform_code,
                status=run_status,
                error_message=error_msg[:1000] if error_msg else None,
                new_jobs=new_jobs_added
            )
        except Exception as telemetry_error:
            self.logger.warning("Failed to update platform telemetry: %s", telemetry_error)

        self.logger.info(
            "<<< Finished %s in %.2fs. Status: %s. Fetched: %d, Added: %d",
            self.pipeline_name, duration, run_status, jobs_fetched, new_jobs_added
        )

        return PipelineRunResult(
            pipeline_name=self.pipeline_name,
            platform_code=self.platform_code,
            status=run_status,
            jobs_fetched=jobs_fetched,
            new_jobs_added=new_jobs_added,
            duration_seconds=duration,
            error_message=error_msg
        )
