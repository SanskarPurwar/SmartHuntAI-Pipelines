import uuid
from typing import Optional, List, Dict, Any, Union
from core.db import get_db_cursor

class PlatformRepository:
    """
    Encapsulates database operations for the `platforms` table (ingestion source schedules) using UUIDv7.
    """

    @staticmethod
    def find_by_name(name: str) -> Optional[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT id::text AS id, name, display_name, schedule_time, is_active, last_run_at,
                       last_status, total_jobs_indexed, last_error_message, created_at, updated_at
                FROM platforms WHERE name = %s
            """, (name,))
            return cursor.fetchone()

    @staticmethod
    def find_by_id(platform_id: Union[str, uuid.UUID]) -> Optional[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT id::text AS id, name, display_name, schedule_time, is_active, last_run_at,
                       last_status, total_jobs_indexed, last_error_message, created_at, updated_at
                FROM platforms WHERE id = %s
            """, (str(platform_id),))
            return cursor.fetchone()

    @staticmethod
    def find_all() -> List[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT id::text AS id, name, display_name, schedule_time, is_active, last_run_at,
                       last_status, total_jobs_indexed, last_error_message, created_at, updated_at
                FROM platforms ORDER BY name ASC
            """)
            return cursor.fetchall()

    @staticmethod
    def find_all_active() -> List[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT id::text AS id, name, display_name, schedule_time, is_active, last_run_at,
                       last_status, total_jobs_indexed, last_error_message, created_at, updated_at
                FROM platforms WHERE is_active = TRUE ORDER BY name ASC
            """)
            return cursor.fetchall()

    @staticmethod
    def update_last_run(platform_id: Union[str, uuid.UUID]) -> bool:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE platforms 
                SET last_run_at = NOW(), updated_at = NOW() 
                WHERE id = %s
            """, (str(platform_id),))
            return cursor.rowcount > 0

    @staticmethod
    def record_run_telemetry(platform_code: str, status: str, error_message: Optional[str] = None, new_jobs: int = 0) -> bool:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE platforms
                SET last_run_at = NOW(),
                    last_status = %s,
                    last_error_message = %s,
                    total_jobs_indexed = COALESCE(total_jobs_indexed, 0) + %s,
                    updated_at = NOW()
                WHERE name = %s
            """, (status, error_message, new_jobs, platform_code))
            return cursor.rowcount > 0


