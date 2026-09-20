import uuid
from typing import Optional, List, Dict, Any, Union
from psycopg2.extras import execute_batch
from core.db import get_db_cursor
from core.time_utils import parse_posted_at
from core.job_enrichment import enrich_job_data

class GlobalJobRepository:
    """
    Encapsulates all database operations for the master `global_jobs` ingestion lake using UUIDv7.
    Enforces deterministic zero-LLM enrichment and link-canonical deduplication.
    """

    @staticmethod
    def upsert_job(job: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        raw_data = dict(job or {})
        raw_data.update(kwargs)
        job_data = enrich_job_data(raw_data)

        new_job_id = job_data.get('id') or uuid.uuid7()
        posted_at_dt = parse_posted_at(job_data.get('posted_at'))

        insert_query = """
            INSERT INTO global_jobs (
                id, title, description, yoe, yoe_min, yoe_max, min_salary, max_salary, currency,
                location, country_code, company_id, source_platform_id, link, employment_type,
                work_mode, job_category,
                is_active, posted_at, yoe_confidence, tech_stack, last_visited_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (company_id, title) DO UPDATE SET
                link = EXCLUDED.link,
                description = COALESCE(EXCLUDED.description, global_jobs.description),
                yoe = COALESCE(EXCLUDED.yoe, global_jobs.yoe),
                yoe_min = COALESCE(EXCLUDED.yoe_min, global_jobs.yoe_min),
                yoe_max = COALESCE(EXCLUDED.yoe_max, global_jobs.yoe_max),
                yoe_confidence = COALESCE(EXCLUDED.yoe_confidence, global_jobs.yoe_confidence),
                tech_stack = CASE WHEN array_length(EXCLUDED.tech_stack, 1) > 0 THEN EXCLUDED.tech_stack ELSE global_jobs.tech_stack END,
                min_salary = COALESCE(EXCLUDED.min_salary, global_jobs.min_salary),
                max_salary = COALESCE(EXCLUDED.max_salary, global_jobs.max_salary),
                currency = COALESCE(EXCLUDED.currency, global_jobs.currency),
                location = COALESCE(EXCLUDED.location, global_jobs.location),
                country_code = COALESCE(EXCLUDED.country_code, global_jobs.country_code),
                employment_type = COALESCE(EXCLUDED.employment_type, global_jobs.employment_type),
                work_mode = COALESCE(EXCLUDED.work_mode, global_jobs.work_mode),
                job_category = COALESCE(EXCLUDED.job_category, global_jobs.job_category),
                is_active = TRUE,
                posted_at = COALESCE(EXCLUDED.posted_at, global_jobs.posted_at),
                last_visited_at = NOW(),
                updated_at = NOW()
            RETURNING id::text AS id
        """
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(insert_query, (
                str(new_job_id),
                job_data['title'],
                job_data.get('description'),
                job_data.get('yoe'),
                job_data.get('yoe_min'),
                job_data.get('yoe_max'),
                job_data.get('min_salary'),
                job_data.get('max_salary'),
                job_data.get('currency', 'USD'),
                job_data.get('location'),
                job_data.get('country_code'),
                str(job_data['company_id']) if job_data.get('company_id') else None,
                str(job_data['source_platform_id']) if job_data.get('source_platform_id') else None,
                job_data['link'],
                job_data.get('employment_type', 'full-time'),
                job_data.get('work_mode'),
                job_data.get('job_category'),
                job_data.get('is_active', True),
                posted_at_dt,
                job_data.get('yoe_confidence', 'unknown'),
                job_data.get('tech_stack') or []
            ))
            row = cursor.fetchone()
            return str(row['id'])

    @staticmethod
    def upsert_batch(jobs: List[Dict[str, Any]]) -> int:
        """
        High-performance bulk upsert for pipelines using execute_batch in a single transaction.
        Deduplicates strictly by (company_id, title) and link, and enriches deterministically without LLM.
        """
        if not jobs:
            return 0

        insert_query = """
            INSERT INTO global_jobs (
                id, title, description, yoe, yoe_min, yoe_max, min_salary, max_salary, currency,
                location, country_code, company_id, source_platform_id, link, employment_type,
                work_mode, job_category,
                is_active, posted_at, yoe_confidence, tech_stack, last_visited_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (company_id, title) DO UPDATE SET
                link = EXCLUDED.link,
                description = COALESCE(EXCLUDED.description, global_jobs.description),
                yoe = COALESCE(EXCLUDED.yoe, global_jobs.yoe),
                yoe_min = COALESCE(EXCLUDED.yoe_min, global_jobs.yoe_min),
                yoe_max = COALESCE(EXCLUDED.yoe_max, global_jobs.yoe_max),
                yoe_confidence = COALESCE(EXCLUDED.yoe_confidence, global_jobs.yoe_confidence),
                tech_stack = CASE WHEN array_length(EXCLUDED.tech_stack, 1) > 0 THEN EXCLUDED.tech_stack ELSE global_jobs.tech_stack END,
                min_salary = COALESCE(EXCLUDED.min_salary, global_jobs.min_salary),
                max_salary = COALESCE(EXCLUDED.max_salary, global_jobs.max_salary),
                currency = COALESCE(EXCLUDED.currency, global_jobs.currency),
                location = COALESCE(EXCLUDED.location, global_jobs.location),
                country_code = COALESCE(EXCLUDED.country_code, global_jobs.country_code),
                employment_type = COALESCE(EXCLUDED.employment_type, global_jobs.employment_type),
                work_mode = COALESCE(EXCLUDED.work_mode, global_jobs.work_mode),
                job_category = COALESCE(EXCLUDED.job_category, global_jobs.job_category),
                is_active = TRUE,
                posted_at = COALESCE(EXCLUDED.posted_at, global_jobs.posted_at),
                last_visited_at = NOW(),
                updated_at = NOW()
        """
        params_list = []
        seen_keys = set()
        seen_links = set()
        for raw_job in jobs:
            link = raw_job.get('link')
            cid = str(raw_job.get('company_id') or '')
            title = (raw_job.get('title') or '').strip().lower()
            key = (cid, title)
            if not link or link in seen_links or key in seen_keys:
                continue
            seen_links.add(link)
            seen_keys.add(key)

            job_data = enrich_job_data(raw_job)
            new_job_id = job_data.get('id') or uuid.uuid7()
            posted_at_dt = parse_posted_at(job_data.get('posted_at'))
            params_list.append((
                str(new_job_id),
                job_data['title'],
                job_data.get('description'),
                job_data.get('yoe'),
                job_data.get('yoe_min'),
                job_data.get('yoe_max'),
                job_data.get('min_salary'),
                job_data.get('max_salary'),
                job_data.get('currency', 'USD'),
                job_data.get('location'),
                job_data.get('country_code'),
                str(job_data['company_id']) if job_data.get('company_id') else None,
                str(job_data['source_platform_id']) if job_data.get('source_platform_id') else None,
                link,
                job_data.get('employment_type', 'full-time'),
                job_data.get('work_mode'),
                job_data.get('job_category'),
                job_data.get('is_active', True),
                posted_at_dt,
                job_data.get('yoe_confidence', 'unknown'),
                job_data.get('tech_stack') or []
            ))

        with get_db_cursor(commit=True) as cursor:
            execute_batch(cursor, insert_query, params_list, page_size=200)
            return len(params_list)

    @staticmethod
    def find_by_id(job_id: Union[str, uuid.UUID]) -> Optional[Dict[str, Any]]:
        query = """
            SELECT gj.id::text AS id, gj.title, gj.description, gj.yoe, gj.yoe_min, gj.yoe_max,
                   gj.yoe_confidence, gj.tech_stack,
                   gj.min_salary, gj.max_salary, gj.currency, gj.location, gj.company_id::text AS company_id,
                   gj.source_platform_id::text AS source_platform_id, gj.link, gj.employment_type,
                   gj.is_active, gj.posted_at, gj.last_visited_at, gj.created_at, gj.updated_at,
                   c.name AS company_name, c.logo_url AS company_logo, p.name AS platform_name
            FROM global_jobs gj
            LEFT JOIN companies c ON gj.company_id = c.id
            LEFT JOIN platforms p ON gj.source_platform_id = p.id
            WHERE gj.id = %s
        """
        with get_db_cursor(commit=False) as cursor:
            cursor.execute(query, (str(job_id),))
            return cursor.fetchone()

    @staticmethod
    def find_active_jobs(
        role_keyword: Optional[str] = None,
        location_keyword: Optional[str] = None,
        max_yoe: Optional[int] = None,
        min_salary: Optional[float] = None,
        employment_type: Optional[str] = None,
        platform_name: Optional[str] = None,
        sort_by: str = 'recency',
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT gj.id::text AS id, gj.title, gj.description, gj.yoe, gj.yoe_min, gj.yoe_max,
                   gj.yoe_confidence, gj.tech_stack,
                   gj.min_salary, gj.max_salary, gj.currency, gj.location, gj.company_id::text AS company_id,
                   gj.source_platform_id::text AS source_platform_id, gj.link, gj.employment_type,
                   gj.is_active, gj.posted_at, gj.last_visited_at, gj.created_at, gj.updated_at,
                   c.name AS company_name, c.logo_url AS company_logo, p.name AS platform_name
            FROM global_jobs gj
            LEFT JOIN companies c ON gj.company_id = c.id
            LEFT JOIN platforms p ON gj.source_platform_id = p.id
            WHERE gj.is_active = TRUE
        """
        params = []
        if role_keyword:
            query += " AND (gj.title ILIKE %s OR c.name ILIKE %s)"
            params.append(f"%{role_keyword}%")
            params.append(f"%{role_keyword}%")
        if location_keyword:
            query += " AND gj.location ILIKE %s"
            params.append(f"%{location_keyword}%")
        if max_yoe is not None:
            query += " AND (gj.yoe_min IS NULL OR gj.yoe_min <= %s)"
            params.append(max_yoe)
        if min_salary is not None:
            query += " AND (gj.max_salary IS NULL OR gj.max_salary >= %s)"
            params.append(min_salary)
        if employment_type and employment_type != 'all':
            query += " AND gj.employment_type = %s"
            params.append(employment_type)
        if platform_name and platform_name != 'all':
            query += " AND p.name = %s"
            params.append(platform_name)

        if sort_by == 'salary':
            query += " ORDER BY gj.max_salary DESC NULLS LAST, gj.posted_at DESC NULLS LAST"
        elif sort_by == 'yoe':
            query += " ORDER BY gj.yoe_min ASC NULLS LAST, gj.posted_at DESC NULLS LAST"
        else:
            query += " ORDER BY gj.posted_at DESC NULLS LAST, gj.created_at DESC"

        query += " LIMIT %s OFFSET %s"
        params.append(limit)
        params.append(offset)

        with get_db_cursor(commit=False) as cursor:
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    @staticmethod
    def mark_inactive(job_id: Union[str, uuid.UUID]) -> bool:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("UPDATE global_jobs SET is_active = FALSE, updated_at = NOW() WHERE id = %s", (str(job_id),))
            return cursor.rowcount > 0

    @staticmethod
    def prune_inactive_jobs_older_than(days: int = 30) -> int:
        """
        Soft-deactivates jobs that have not been re-visited or refreshed within TTL days.
        """
        query = """
            UPDATE global_jobs
            SET is_active = FALSE, updated_at = NOW()
            WHERE is_active = TRUE AND last_visited_at < NOW() - INTERVAL '%s days'
        """
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(query, (days,))
            return cursor.rowcount

    @staticmethod
    def find_candidate_feed(
        user_id: Optional[Union[str, uuid.UUID]] = None,
        search_query: Optional[str] = None,
        platform_name: Optional[str] = None,
        yoe_tier: Optional[str] = None,
        max_yoe: Optional[int] = None,
        min_salary: Optional[float] = None,
        employment_type: Optional[str] = None,
        work_mode: Optional[str] = None,
        location_keywords: Optional[List[str]] = None,
        status: Optional[str] = None,
        sort_by: str = 'recency',
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                gj.id::text AS id,
                gj.title,
                gj.description,
                gj.yoe,
                gj.yoe_min,
                gj.yoe_max,
                gj.min_salary,
                gj.max_salary,
                gj.currency,
                gj.location,
                gj.country_code,
                gj.company_id::text AS company_id,
                gj.source_platform_id::text AS source_platform_id,
                gj.link,
                gj.employment_type,
                gj.is_active,
                gj.posted_at,
                gj.created_at,
                gj.yoe_confidence,
                gj.tech_stack,
                COALESCE(c.name, 'Direct Employer') AS company_name,
                c.logo_url AS company_logo,
                COALESCE(p.name, 'direct_ats') AS platform_name,
                cjs.status AS user_status,
                cjs.match_score AS stored_match_score,
                cjs.discard_reason,
                cjs.tailored_resume_link
            FROM global_jobs gj
            LEFT JOIN companies c ON gj.company_id = c.id
            LEFT JOIN platforms p ON gj.source_platform_id = p.id
            LEFT JOIN candidate_job_states cjs ON cjs.job_id = gj.id AND cjs.user_id = %s
            WHERE gj.is_active = TRUE
        """
        params: List[Any] = [str(user_id) if user_id else None]

        if search_query:
            query += " AND (gj.title ILIKE %s OR c.name ILIKE %s OR gj.description ILIKE %s)"
            kw = f"%{search_query.strip()}%"
            params.extend([kw, kw, kw])

        if platform_name and platform_name != 'all':
            query += " AND p.name = %s"
            params.append(platform_name)

        if employment_type and employment_type != 'all':
            query += " AND gj.employment_type = %s"
            params.append(employment_type)

        if min_salary and min_salary > 0:
            query += " AND (gj.max_salary IS NULL OR gj.max_salary >= %s)"
            params.append(min_salary)

        # Exact YOE filtering: show jobs where yoe_min <= candidate's max_yoe
        if max_yoe is not None:
            query += " AND (gj.yoe_min IS NULL OR gj.yoe_min <= %s)"
            params.append(max_yoe)
        elif yoe_tier and yoe_tier != 'all':
            # Fallback to tier-based filtering if no exact max_yoe
            if yoe_tier == 'entry':
                query += " AND (gj.yoe_min IS NULL OR gj.yoe_min <= 1)"
            elif yoe_tier == 'mid':
                query += " AND (gj.yoe_min >= 2 AND gj.yoe_min <= 5)"
            elif yoe_tier == 'senior':
                query += " AND (gj.yoe_min >= 5 AND gj.yoe_min <= 8)"
            elif yoe_tier == 'lead':
                query += " AND (gj.yoe_min >= 8)"

        # Location filter: match against multiple location keywords
        if location_keywords and len(location_keywords) > 0:
            loc_conditions = []
            for kw in location_keywords:
                loc_conditions.append("gj.location ILIKE %s")
                params.append(f"%{kw}%")
            query += f" AND ({' OR '.join(loc_conditions)})"

        if work_mode and work_mode != 'all':
            query += " AND gj.work_mode = %s"
            params.append(work_mode.lower())

        if status and status != 'all':
            if status == 'active':
                query += " AND (cjs.status IS NULL OR cjs.status NOT IN ('discarded', 'rejected_yoe'))"
            elif status == 'saved':
                query += " AND cjs.status = 'saved'"
            elif status == 'applied':
                query += " AND cjs.status = 'applied'"
            elif status == 'discarded':
                query += " AND cjs.status IN ('discarded', 'rejected_yoe')"

        if sort_by == 'salary':
            query += " ORDER BY gj.max_salary DESC NULLS LAST, gj.posted_at DESC NULLS LAST"
        elif sort_by == 'yoe':
            query += " ORDER BY gj.yoe_min ASC NULLS LAST, gj.posted_at DESC NULLS LAST"
        else:
            query += " ORDER BY gj.posted_at DESC NULLS LAST, gj.created_at DESC"

        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with get_db_cursor(commit=False) as cursor:
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    @staticmethod
    def count_candidate_feed(
        user_id: Optional[Union[str, uuid.UUID]] = None,
        search_query: Optional[str] = None,
        platform_name: Optional[str] = None,
        yoe_tier: Optional[str] = None,
        max_yoe: Optional[int] = None,
        min_salary: Optional[float] = None,
        employment_type: Optional[str] = None,
        work_mode: Optional[str] = None,
        location_keywords: Optional[List[str]] = None,
        status: Optional[str] = None
    ) -> int:
        query = """
            SELECT COUNT(*) AS total
            FROM global_jobs gj
            LEFT JOIN companies c ON gj.company_id = c.id
            LEFT JOIN platforms p ON gj.source_platform_id = p.id
            LEFT JOIN candidate_job_states cjs ON cjs.job_id = gj.id AND cjs.user_id = %s
            WHERE gj.is_active = TRUE
        """
        params: List[Any] = [str(user_id) if user_id else None]

        if search_query:
            query += " AND (gj.title ILIKE %s OR c.name ILIKE %s OR gj.description ILIKE %s)"
            kw = f"%{search_query.strip()}%"
            params.extend([kw, kw, kw])

        if platform_name and platform_name != 'all':
            query += " AND p.name = %s"
            params.append(platform_name)

        if employment_type and employment_type != 'all':
            query += " AND gj.employment_type = %s"
            params.append(employment_type)

        if min_salary and min_salary > 0:
            query += " AND (gj.max_salary IS NULL OR gj.max_salary >= %s)"
            params.append(min_salary)

        # Exact YOE filtering
        if max_yoe is not None:
            query += " AND (gj.yoe_min IS NULL OR gj.yoe_min <= %s)"
            params.append(max_yoe)
        elif yoe_tier and yoe_tier != 'all':
            if yoe_tier == 'entry':
                query += " AND (gj.yoe_min IS NULL OR gj.yoe_min <= 1)"
            elif yoe_tier == 'mid':
                query += " AND (gj.yoe_min >= 2 AND gj.yoe_min <= 5)"
            elif yoe_tier == 'senior':
                query += " AND (gj.yoe_min >= 5 AND gj.yoe_min <= 8)"
            elif yoe_tier == 'lead':
                query += " AND (gj.yoe_min >= 8)"

        # Location filter
        if location_keywords and len(location_keywords) > 0:
            loc_conditions = []
            for kw in location_keywords:
                loc_conditions.append("gj.location ILIKE %s")
                params.append(f"%{kw}%")
            query += f" AND ({' OR '.join(loc_conditions)})"

        if work_mode and work_mode != 'all':
            query += " AND gj.work_mode = %s"
            params.append(work_mode.lower())

        if status and status != 'all':
            if status == 'active':
                query += " AND (cjs.status IS NULL OR cjs.status NOT IN ('discarded', 'rejected_yoe'))"
            elif status == 'saved':
                query += " AND cjs.status = 'saved'"
            elif status == 'applied':
                query += " AND cjs.status = 'applied'"
            elif status == 'discarded':
                query += " AND cjs.status IN ('discarded', 'rejected_yoe')"

        with get_db_cursor(commit=False) as cursor:
            cursor.execute(query, tuple(params))
            row = cursor.fetchone()
            return row['total'] if row else 0
