import uuid
from typing import Optional, List, Dict, Any, Union
from core.db import get_db_cursor

class PipelineRunRepository:
    """
    Encapsulates all database operations for `run_stats` and `run_logs` tables
    with UUIDv7 identifiers and serialized text responses.
    """

    @staticmethod
    def find_all_runs_by_user(user_id: Union[str, uuid.UUID]) -> List[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT id::text AS id, timestamp, status, total_searches, successful_jobs, failed_jobs,
                       successful_posts, failed_posts, total_added, user_id::text AS user_id
                FROM run_stats WHERE user_id = %s ORDER BY timestamp DESC, id DESC
            """, (str(user_id),))
            return cursor.fetchall()

    @staticmethod
    def find_latest_stats_by_user(user_id: Union[str, uuid.UUID]) -> Optional[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT id::text AS id, timestamp, status, total_searches, successful_jobs, failed_jobs,
                       successful_posts, failed_posts, total_added, user_id::text AS user_id
                FROM run_stats WHERE user_id = %s ORDER BY timestamp DESC, id DESC LIMIT 1
            """, (str(user_id),))
            return cursor.fetchone()

    @staticmethod
    def find_active_run_by_user(user_id: Union[str, uuid.UUID]) -> Optional[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT id::text AS id, status, timestamp
                FROM run_stats WHERE user_id = %s AND status = 'running' ORDER BY timestamp DESC, id DESC LIMIT 1
            """, (str(user_id),))
            return cursor.fetchone()

    @staticmethod
    def find_run_by_id(run_id: Union[str, uuid.UUID]) -> Optional[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT id::text AS id, timestamp, status, total_searches, successful_jobs, failed_jobs,
                       successful_posts, failed_posts, total_added, user_id::text AS user_id
                FROM run_stats WHERE id = %s
            """, (str(run_id),))
            return cursor.fetchone()

    @staticmethod
    def create_pipeline_run(user_id: Union[str, uuid.UUID], status: str = 'running', total_searches: int = 0) -> str:
        new_run_id = uuid.uuid7()
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "INSERT INTO run_stats (id, user_id, status, total_searches) VALUES (%s, %s, %s, %s) RETURNING id::text AS id",
                (str(new_run_id), str(user_id), status, total_searches)
            )
            return str(cursor.fetchone()['id'])

    @staticmethod
    def update_pipeline_run_progress(run_id: Union[str, uuid.UUID], stats: Dict[str, Any], total_added: int, status: str) -> bool:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE run_stats 
                SET total_searches = %s, successful_jobs = %s, failed_jobs = %s, successful_posts = %s, failed_posts = %s, total_added = %s, status = %s
                WHERE id = %s
            """, (
                stats.get("total_searches", 0),
                stats.get("successful_jobs", 0),
                stats.get("failed_jobs", 0),
                stats.get("successful_posts", 0),
                stats.get("failed_posts", 0),
                total_added,
                status,
                str(run_id)
            ))
            return cursor.rowcount > 0

    @staticmethod
    def set_pipeline_run_status(run_id: Union[str, uuid.UUID], status: str) -> bool:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("UPDATE run_stats SET status = %s WHERE id = %s", (status, str(run_id)))
            return cursor.rowcount > 0

    @staticmethod
    def find_logs_by_run_id(run_id: Union[str, uuid.UUID]) -> List[str]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("SELECT message FROM run_logs WHERE run_id = %s ORDER BY timestamp ASC, id ASC", (str(run_id),))
            return [row['message'] for row in cursor.fetchall()]

    @staticmethod
    def append_pipeline_log(run_id: Union[str, uuid.UUID], message: str) -> None:
        new_log_id = uuid.uuid7()
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("INSERT INTO run_logs (id, run_id, message) VALUES (%s, %s, %s)", (str(new_log_id), str(run_id), message))

    @staticmethod
    def cleanup_stale_runs() -> int:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("UPDATE run_stats SET status = 'failed' WHERE status = 'running'")
            return cursor.rowcount

    # Backward compatibility aliases
    get_all_by_user = find_all_runs_by_user
    get_latest_stats_by_user = find_latest_stats_by_user
    get_active_run_by_user = find_active_run_by_user
    get_run_by_id = find_run_by_id
    create_run = create_pipeline_run
    update_run_stats = update_pipeline_run_progress
    set_run_status = set_pipeline_run_status
    get_logs_by_run_id = find_logs_by_run_id
    append_log = append_pipeline_log
    insert_log = append_pipeline_log

# Class alias for backward compatibility
RunRepository = PipelineRunRepository
