import os
import time
import random
from typing import Optional

from collectors.linkedin_jobs_collector import LinkedInJobsCollector
from core.job_qualification_enricher import JobQualificationEnricher
from core.ai_job_evaluator import AIJobEvaluator
from repositories.user_repository import UserRepository
from repositories.job_repository import JobRepository
from repositories.pipeline_run_repository import PipelineRunRepository

from core.config import settings
from core.logger import get_pipeline_logger

DATABASE_URL = settings.DATABASE_URL
TAILORED_RESUMES_DIR = str(settings.TAILORED_RESUMES_DIR)

def execute_job_pipeline(run_id: Optional[int] = None, user_id: Optional[int] = None) -> None:
    """
    Central pipeline orchestrator executing the 3-phase automated job hunt:
    Phase 1: Opportunity Discovery (LinkedIn Jobs)
    Phase 2: Deep Specification Enrichment & Qualification Checks
    Phase 3: AI-Driven Valuation & Match Scoring
    """
    if not user_id:
        print("[ERROR] [Pipeline] user_id is required to run the pipeline!")
        return

    logger = get_pipeline_logger(run_id)

    def log(msg: str):
        logger.info(msg)

    try:
        log(f"[INFO] [Pipeline] Initializing pipeline execution (Run ID: {run_id or 'standalone'}, User ID: {user_id})")
        
        user_record = UserRepository.find_by_id(user_id)
        if not user_record:
            log(f"[ERROR] [Pipeline] User {user_id} configuration record not found.")
            if run_id:
                PipelineRunRepository.set_pipeline_run_status(run_id, 'failed')
            return
            
        user_configuration = user_record.get('config') or {}
            
        # -------------------------------------------------------------
        # PHASE 1: DISCOVERY PHASE
        # -------------------------------------------------------------
        log("[INFO] [Discovery] Phase 1: Initiating opportunity discovery across target profiles...")
        jobs_collector = LinkedInJobsCollector()
        
        target_roles = user_configuration.get("roles", ["Software Developer"])
        target_locations = user_configuration.get("locations", ["Remote"])
        
        new_jobs_count = 0
        pipeline_statistics = {
            "total_searches": len(target_roles) * len(target_locations),
            "successful_jobs": 0,
            "failed_jobs": 0,
            "successful_posts": 0,
            "failed_posts": 0
        }
        
        start_page = user_configuration.get("start_page", 1)
        end_page = user_configuration.get("end_page", 3)
        posting_time_unit = user_configuration.get("time_filter_unit", "days")
        posting_time_value = user_configuration.get("time_filter_value", 7)
        max_years_of_experience = user_configuration.get("max_yoe", 2)
        
        for target_role in target_roles:
            for target_location in target_locations:
                log(f"[INFO] [Discovery] Querying roles matching '{target_role}' in '{target_location}' (Pages {start_page}-{end_page})")
                
                # Artificial human pacing delay to protect against scraping blocks
                cooldown_delay_seconds = random.randint(10, 25)
                log(f"[INFO] [Discovery] Applying pacing delay: cooling down {cooldown_delay_seconds}s to avoid rate limits...")
                time.sleep(cooldown_delay_seconds)
                
                try:
                    discovered_postings = jobs_collector.fetch_jobs(
                        keyword=target_role,
                        location=target_location,
                        start_page=start_page,
                        end_page=end_page,
                        time_unit=posting_time_unit,
                        time_value=posting_time_value,
                        max_yoe=max_years_of_experience,
                        logger=log
                    )
                    pipeline_statistics["successful_jobs"] += 1
                    log(f"[INFO] [Discovery] Retrieved {len(discovered_postings)} postings from LinkedIn Jobs.")
                except Exception as discovery_error:
                    log(f"[ERROR] [Discovery] Failed to query jobs for '{target_role}' in '{target_location}': {discovery_error}")
                    discovered_postings = []
                    pipeline_statistics["failed_jobs"] += 1
                    
                if discovered_postings:
                    indexed_job_records = [
                        (
                            posting.title,
                            posting.company,
                            posting.location,
                            posting.link,
                            posting.source,
                            posting.description,
                            posting.posted_at,
                            'discovered',
                            'discovered',
                            user_id
                        )
                        for posting in discovered_postings
                    ]
                    inserted_ids = JobRepository.batch_insert_jobs(indexed_job_records)
                    batch_added = len(inserted_ids)
                    new_jobs_count += batch_added
                    log(f"[INFO] [Discovery] Indexed {batch_added} new opportunities ({len(discovered_postings) - batch_added} duplicates skipped).")
                        
        log(f"[INFO] [Discovery] Discovery phase finished. {new_jobs_count} new unique opportunities indexed.")
        
        # Save Phase 1 interim statistics, status remains 'running'
        if run_id:
            PipelineRunRepository.update_pipeline_run_progress(run_id, pipeline_statistics, new_jobs_count, status='running')
        
        # -------------------------------------------------------------
        # PHASE 2: ENRICHMENT & QUALIFICATION PHASE
        # -------------------------------------------------------------
        log("[INFO] [Enrichment] Phase 2: Starting deep specification extraction and qualification filtering...")
        enricher = JobQualificationEnricher(user_id=user_id, max_years_of_experience=max_years_of_experience)
        enricher.enrich_and_qualify_discovered_jobs(logger=log)
        log("[INFO] [Enrichment] Phase 2: Specification extraction and qualification checks completed.")
        
        # -------------------------------------------------------------
        # PHASE 3: AI VALUATION & FIT MATCHING PHASE
        # -------------------------------------------------------------
        log("[INFO] [Valuation] Phase 3: Commencing AI-driven compensation estimation and candidate fit scoring...")
        evaluator = AIJobEvaluator(resumes_dir=TAILORED_RESUMES_DIR, user_id=user_id)
        evaluator.batch_evaluate_compensation_and_fit(logger=log)
        log("[INFO] [Valuation] Phase 3: Compensation estimation and candidate fit scoring completed.")
        
        # Finalize pipeline run status as completed ONLY when all phases terminate cleanly
        if run_id:
            PipelineRunRepository.update_pipeline_run_progress(run_id, pipeline_statistics, new_jobs_count, status='completed')
        
        log(f"[INFO] [Pipeline] Execution finalized successfully. Run ID: {run_id or 'standalone'}, New Jobs: {new_jobs_count}.")
    
    except Exception as fatal_pipeline_error:
        log(f"[ERROR] [Pipeline] Critical pipeline failure: {fatal_pipeline_error}")
        if run_id:
            try:
                PipelineRunRepository.set_pipeline_run_status(run_id, 'failed')
            except Exception:
                pass

# Backward compatibility alias
main = execute_job_pipeline

if __name__ == "__main__":
    import argparse
    argument_parser = argparse.ArgumentParser(description="Execute automated job hunting pipeline")
    argument_parser.add_argument('--user_id', type=int, required=True, help="Database ID of target user profile")
    arguments = argument_parser.parse_args()
    execute_job_pipeline(user_id=arguments.user_id)
