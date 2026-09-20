import uuid
from typing import Optional, Tuple, Union, Any
from core.db import get_db_cursor

class QuotaRepository:
    """
    Encapsulates all database operations for the multi-tenant `daily_quotas` table
    with UUIDv7 identifiers and user scoping.
    """

    @staticmethod
    def initialize_daily_quota_if_missing(user_id: Optional[Union[str, uuid.UUID]], date_str: str) -> None:
        new_quota_id = uuid.uuid7()
        user_param = str(user_id) if user_id else None
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO daily_quotas (id, user_id, date_str, premium_used, bulk_used)
                VALUES (%s, %s, %s, 0, 0)
                ON CONFLICT (user_id, date_str) DO NOTHING
            """, (str(new_quota_id), user_param, date_str))

    @staticmethod
    def find_daily_quotas(user_id: Optional[Union[str, uuid.UUID]], date_str: str) -> Tuple[int, int]:
        QuotaRepository.initialize_daily_quota_if_missing(user_id, date_str)
        with get_db_cursor(commit=False) as cursor:
            if user_id is not None:
                cursor.execute(
                    "SELECT premium_used, bulk_used FROM daily_quotas WHERE user_id = %s AND date_str = %s",
                    (str(user_id), date_str)
                )
            else:
                cursor.execute(
                    "SELECT premium_used, bulk_used FROM daily_quotas WHERE user_id IS NULL AND date_str = %s",
                    (date_str,)
                )
            row = cursor.fetchone()
            if row:
                return row.get('premium_used', 0) or 0, row.get('bulk_used', 0) or 0
            return 0, 0

    @staticmethod
    def record_quota_usage(user_id: Optional[Union[str, uuid.UUID]], date_str: str, pool_type: str, count: int = 1) -> None:
        QuotaRepository.initialize_daily_quota_if_missing(user_id, date_str)
        column_name = 'premium_used' if pool_type == 'premium' else 'bulk_used'
        with get_db_cursor(commit=True) as cursor:
            if user_id is not None:
                cursor.execute(
                    f"UPDATE daily_quotas SET {column_name} = {column_name} + %s WHERE user_id = %s AND date_str = %s",
                    (count, str(user_id), date_str)
                )
            else:
                cursor.execute(
                    f"UPDATE daily_quotas SET {column_name} = {column_name} + %s WHERE user_id IS NULL AND date_str = %s",
                    (count, date_str)
                )

    # Backward compatibility aliases
    init_today = initialize_daily_quota_if_missing
    get_quotas = find_daily_quotas
    record_usage = record_quota_usage
