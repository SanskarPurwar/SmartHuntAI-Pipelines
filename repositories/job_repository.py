import uuid
from typing import Optional, List, Dict, Any, Union
from core.db import get_db_cursor
from repositories.company_repository import CompanyRepository
from repositories.platform_repository import PlatformRepository
from repositories.global_job_repository import GlobalJobRepository
from repositories.candidate_job_state_repository import CandidateJobStateRepository

class JobRepository:
    """
    Decoupled Adapter Repository: Seamlessly coordinates queries and mutations
    across `global_jobs`, `candidate_job_states`, `companies`, and `platforms`
    using native UUIDv7 while preserving 100% backwards compatibility with the UI.
    """

    @staticmethod
    def find_all_jobs_by_user(user_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                gj.id::text AS id,
                gj.title,
                COALESCE(c.name, 'Unknown Company') AS company,
                COALESCE(gj.location, 'Unknown Location') AS location,
                gj.link,
                COALESCE(p.name, 'linkedin_jobs') AS source,
                gj.description,
                gj.posted_at,
                cjs.status AS stage,
                cjs.status AS status,
                cjs.user_id,
                gj.min_salary,
                gj.max_salary,
                gj.currency,
                COALESCE(cjs.match_score, 0) AS match_score,
                cjs.discard_reason,
                cjs.tailored_resume_link AS tailored_resume_path
            FROM candidate_job_states cjs
            JOIN global_jobs gj ON cjs.job_id = gj.id
            LEFT JOIN companies c ON gj.company_id = c.id
            LEFT JOIN platforms p ON gj.source_platform_id = p.id
            WHERE cjs.user_id = %s
            ORDER BY gj.created_at DESC, gj.id DESC
        """
        with get_db_cursor(commit=False) as cursor:
            cursor.execute(query, (user_id,))
            return cursor.fetchall()

    @staticmethod
    def find_job_by_id_and_user(user_id: int, job_id: Union[str, uuid.UUID]) -> Optional[Dict[str, Any]]:
        query = """
            SELECT 
                gj.id::text AS id,
                gj.title,
                COALESCE(c.name, 'Unknown Company') AS company,
                COALESCE(gj.location, 'Unknown Location') AS location,
                gj.link,
                COALESCE(p.name, 'linkedin_jobs') AS source,
                gj.description,
                gj.posted_at,
                cjs.status AS stage,
                cjs.status AS status,
                cjs.user_id,
                gj.min_salary,
                gj.max_salary,
                gj.currency,
                COALESCE(cjs.match_score, 0) AS match_score,
                cjs.discard_reason,
                cjs.tailored_resume_link AS tailored_resume_path
            FROM candidate_job_states cjs
            JOIN global_jobs gj ON cjs.job_id = gj.id
            LEFT JOIN companies c ON gj.company_id = c.id
            LEFT JOIN platforms p ON gj.source_platform_id = p.id
            WHERE cjs.user_id = %s AND gj.id = %s
        """
        with get_db_cursor(commit=False) as cursor:
            cursor.execute(query, (user_id, str(job_id)))
            return cursor.fetchone()

    @staticmethod
    def delete_all_jobs_by_user(user_id: int) -> int:
        return CandidateJobStateRepository.delete_all_for_user(user_id)

    @staticmethod
    def update_job_status(user_id: int, job_id: Union[str, uuid.UUID], status: str, discard_reason: Optional[str] = None) -> bool:
        return CandidateJobStateRepository.update_status(user_id, str(job_id), status, discard_reason)

    @staticmethod
    def update_tailored_resume_path(user_id: int, job_id: Union[str, uuid.UUID], path: str) -> bool:
        return CandidateJobStateRepository.update_tailored_resume(user_id, str(job_id), path)

    @staticmethod
    def batch_insert_jobs(records: List[tuple]) -> List[str]:
        """
        Ingests discovered job records into decoupled schema:
        1. Resolves or creates Company
        2. Resolves Platform
        3. Upserts GlobalJob
        4. Links CandidateJobState
        """
        if not records:
            return []

        inserted_job_ids = []
        for record in records:
            # Tuple schema: (title, company, location, link, source, description, posted_at, stage, status, user_id)
            title = record[0]
            company_name = record[1]
            location = record[2]
            link = record[3]
            source_name = record[4] if len(record) > 4 else 'linkedin_jobs'
            description = record[5] if len(record) > 5 else ''
            posted_at = record[6] if len(record) > 6 else None
            status = record[8] if len(record) > 8 else 'discovered'
            user_id = record[9] if len(record) > 9 else None

            # 1. Company
            company_id = CompanyRepository.find_or_create(company_name)

            # 2. Platform
            platform_row = PlatformRepository.find_by_name(source_name)
            platform_id = platform_row['id'] if platform_row else None

            # 3. Global Job
            global_job_id = GlobalJobRepository.upsert_job({
                'title': title,
                'description': description,
                'location': location,
                'company_id': company_id,
                'source_platform_id': platform_id,
                'link': link,
                'posted_at': posted_at
            })

            # 4. Candidate Job State
            if user_id:
                is_new = CandidateJobStateRepository.upsert_state(
                    user_id=user_id,
                    job_id=global_job_id,
                    status=status
                )
                if is_new:
                    inserted_job_ids.append(global_job_id)

        return inserted_job_ids

    # Backward compatibility aliases
    get_all_by_user = find_all_jobs_by_user
    get_by_id_and_user = find_job_by_id_and_user
    delete_all_by_user = delete_all_jobs_by_user
    update_status = update_job_status
    batch_insert = batch_insert_jobs
