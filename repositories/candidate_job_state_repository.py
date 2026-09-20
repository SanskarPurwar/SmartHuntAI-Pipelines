import uuid
from typing import Optional, Dict, Any, List, Union
from core.db import get_db_cursor

class CandidateJobStateRepository:
    """
    Encapsulates all personalized candidate interactions, status transitions,
    and tailored resume associations for jobs in the global pool using UUIDv7.
    """

    @staticmethod
    def upsert_state(
        user_id: int,
        job_id: Union[str, uuid.UUID],
        status: str = 'discovered',
        is_qualified: bool = True,
        match_score: int = 0,
        discard_reason: Optional[str] = None,
        is_tailored_resume: bool = False,
        tailored_resume_link: Optional[str] = None
    ) -> bool:
        query = """
            INSERT INTO candidate_job_states (
                user_id, job_id, status, is_qualified, match_score,
                discard_reason, is_tailored_resume, tailored_resume_link, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id, job_id) DO UPDATE SET
                status = EXCLUDED.status,
                is_qualified = EXCLUDED.is_qualified,
                match_score = GREATEST(candidate_job_states.match_score, EXCLUDED.match_score),
                discard_reason = COALESCE(EXCLUDED.discard_reason, candidate_job_states.discard_reason),
                is_tailored_resume = EXCLUDED.is_tailored_resume OR candidate_job_states.is_tailored_resume,
                tailored_resume_link = COALESCE(EXCLUDED.tailored_resume_link, candidate_job_states.tailored_resume_link),
                updated_at = NOW()
        """
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(query, (
                user_id, str(job_id), status, is_qualified, match_score,
                discard_reason, is_tailored_resume, tailored_resume_link
            ))
            return cursor.rowcount > 0

    @staticmethod
    def update_status(user_id: Union[str, uuid.UUID], job_id: Union[str, uuid.UUID], status: str, discard_reason: Optional[str] = None) -> bool:
        return CandidateJobStateRepository.upsert_state(
            user_id=user_id,
            job_id=job_id,
            status=status,
            is_qualified=(status != 'discarded'),
            discard_reason=discard_reason
        )

    @staticmethod
    def update_tailored_resume(user_id: int, job_id: Union[str, uuid.UUID], resume_link: str) -> bool:
        query = """
            UPDATE candidate_job_states
            SET is_tailored_resume = TRUE,
                tailored_resume_link = %s,
                updated_at = NOW()
            WHERE user_id = %s AND job_id = %s
        """
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(query, (resume_link, user_id, str(job_id)))
            return cursor.rowcount > 0

    @staticmethod
    def delete_all_for_user(user_id: int) -> int:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("DELETE FROM candidate_job_states WHERE user_id = %s", (user_id,))
            return cursor.rowcount
