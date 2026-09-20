import json
import uuid
from typing import Optional, Dict, Any, Union
from core.db import get_db_cursor

class UserRepository:
    """
    Encapsulates all database operations for the `users` table with UUIDv7 identifiers.
    """

    @staticmethod
    def find_by_id(user_id: Union[str, uuid.UUID]) -> Optional[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute(
                """
                SELECT id::text AS id, username, email, full_name, avatar_url, auth_provider, oauth_id, config, master_resume 
                FROM users 
                WHERE id = %s
                """,
                (str(user_id),)
            )
            return cursor.fetchone()

    @staticmethod
    def find_by_username(username: str) -> Optional[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute(
                "SELECT id::text AS id, username, password_hash, config, master_resume FROM users WHERE username = %s",
                (username,)
            )
            return cursor.fetchone()

    @staticmethod
    def create_user(username: str, password_hash: str) -> str:
        new_user_id = uuid.uuid7()
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "INSERT INTO users (id, username, password_hash, config, master_resume) VALUES (%s, %s, %s, '{}'::jsonb, '') RETURNING id::text AS id",
                (str(new_user_id), username, password_hash)
            )
            row = cursor.fetchone()
            return str(row['id'])

    @staticmethod
    def find_by_oauth(auth_provider: str, oauth_id: str) -> Optional[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute(
                """
                SELECT id::text AS id, username, email, full_name, avatar_url, auth_provider, oauth_id, config, master_resume 
                FROM users 
                WHERE auth_provider = %s AND oauth_id = %s
                """,
                (auth_provider, str(oauth_id))
            )
            return cursor.fetchone()

    @staticmethod
    def find_by_email(email: str) -> Optional[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute(
                """
                SELECT id::text AS id, username, email, full_name, avatar_url, auth_provider, oauth_id, config, master_resume 
                FROM users 
                WHERE email = %s
                """,
                (email,)
            )
            return cursor.fetchone()

    @staticmethod
    def create_oauth_user(email: str, full_name: str, avatar_url: str, auth_provider: str, oauth_id: str, suggested_username: Optional[str] = None) -> str:
        new_user_id = uuid.uuid7()
        base_username = suggested_username or (email.split('@')[0] if email else f"{auth_provider}_{str(new_user_id)[:8]}")
        with get_db_cursor(commit=True) as cursor:
            # Check if username exists, if so append random suffix
            cursor.execute("SELECT id FROM users WHERE username = %s", (base_username,))
            if cursor.fetchone():
                base_username = f"{base_username}_{str(new_user_id)[:6]}"

            cursor.execute(
                """
                INSERT INTO users (id, username, email, full_name, avatar_url, auth_provider, oauth_id, config, master_resume)
                VALUES (%s, %s, %s, %s, %s, %s, %s, '{}'::jsonb, '')
                RETURNING id::text AS id
                """,
                (str(new_user_id), base_username, email, full_name, avatar_url, auth_provider, str(oauth_id))
            )
            row = cursor.fetchone()
            return str(row['id'])

    @staticmethod
    def link_oauth_to_user(user_id: Union[str, uuid.UUID], auth_provider: str, oauth_id: str, avatar_url: Optional[str] = None, full_name: Optional[str] = None) -> bool:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                """
                UPDATE users 
                SET auth_provider = %s, oauth_id = %s, avatar_url = COALESCE(%s, avatar_url), full_name = COALESCE(%s, full_name)
                WHERE id = %s
                """,
                (auth_provider, str(oauth_id), avatar_url, full_name, str(user_id))
            )
            return cursor.rowcount > 0

    @staticmethod
    def update_config(user_id: Union[str, uuid.UUID], config: Dict[str, Any]) -> bool:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "UPDATE users SET config = %s WHERE id = %s",
                (json.dumps(config), str(user_id))
            )
            return cursor.rowcount > 0

    @staticmethod
    def update_master_resume(user_id: Union[str, uuid.UUID], resume_text: str) -> bool:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "UPDATE users SET master_resume = %s WHERE id = %s",
                (resume_text, str(user_id))
            )
            return cursor.rowcount > 0

    @staticmethod
    def update_config_and_resume(user_id: Union[str, uuid.UUID], config: Dict[str, Any], resume_text: str) -> bool:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "UPDATE users SET config = %s, master_resume = %s WHERE id = %s",
                (json.dumps(config), resume_text, str(user_id))
            )
            return cursor.rowcount > 0

    @staticmethod
    def delete_user(user_id: Union[str, uuid.UUID]) -> bool:
        """
        Permanently deletes user record. Cascades automatically in PostgreSQL
        to candidate_job_states, daily_quotas, run_stats, and jobs.
        """
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("DELETE FROM users WHERE id = %s", (str(user_id),))
            return cursor.rowcount > 0

    # Backward compatibility aliases
    get_by_id = find_by_id
    get_by_username = find_by_username
