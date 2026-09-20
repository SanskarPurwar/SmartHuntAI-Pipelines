import sys
import os
import time
from typing import List, Dict, Any

from core.db import get_db_cursor
from core.yoe_ai_resolver import YOEAIResolver
from core.logger import setup_logger
from psycopg2.extras import execute_batch

logger = setup_logger("scripts.retroactive_enrichment")

def get_active_jobs() -> List[Dict[str, Any]]:
    """Fetch all active jobs that need enrichment."""
    logger.info("Fetching active jobs from DB...")
    with get_db_cursor() as cursor:
        # Fetch all active jobs, since we added new columns that are NULL
        cursor.execute(
            "SELECT id::text, title, description, location, yoe, yoe_min, yoe_max "
            "FROM global_jobs WHERE is_active = TRUE AND work_mode IS NULL"
        )
        return [dict(r) for r in cursor.fetchall()]

def update_jobs_batch(enriched_jobs: List[Dict[str, Any]]):
    """Update jobs with enriched data."""
    if not enriched_jobs:
        return

    update_query = """
        UPDATE global_jobs SET
            location = COALESCE(%s, location),
            work_mode = %s,
            job_category = %s,
            tech_stack = %s,
            yoe_min = %s,
            yoe_max = %s,
            yoe_confidence = %s,
            updated_at = NOW()
        WHERE id = %s
    """
    
    params = []
    for job in enriched_jobs:
        params.append((
            job.get("location"),
            job.get("work_mode"),
            job.get("job_category"),
            job.get("tech_stack") or [],
            job.get("yoe_min"),
            job.get("yoe_max"),
            job.get("yoe_confidence", "unspecified"),
            job["id"]
        ))
        
    with get_db_cursor(commit=True) as cursor:
        execute_batch(cursor, update_query, params, page_size=100)

def main():
    resolver = YOEAIResolver()
    jobs = get_active_jobs()
    total_jobs = len(jobs)
    
    if total_jobs == 0:
        logger.info("No active jobs requiring enrichment found.")
        return
        
    logger.info(f"Found {total_jobs} jobs to enrich.")
    
    chunk_size = 100
    for i in range(0, total_jobs, chunk_size):
        chunk = jobs[i:i+chunk_size]
        logger.info(f"Processing chunk {i} to {i+len(chunk)} / {total_jobs}")
        try:
            enriched = resolver.resolve_batch(chunk)
            update_jobs_batch(enriched)
            logger.info(f"Successfully updated {len(enriched)} jobs.")
        except Exception as e:
            logger.error(f"Error processing chunk: {e}")
            
if __name__ == "__main__":
    main()
