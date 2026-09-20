import uuid
from typing import Optional, List, Dict, Any, Union
from core.db import get_db_cursor

class CompanyRepository:
    """
    Encapsulates all database persistence and queries for the `companies` table using UUIDv7.
    """

    @staticmethod
    def find_or_create_batch(company_names: List[str]) -> Dict[str, str]:
        """
        High-performance bulk company resolution and insertion in a single transaction.
        Returns a mapping of {company_name: company_id_uuid_string}.
        """
        if not company_names:
            return {}

        unique_clean_names = list(set(name.strip()[:200] for name in company_names if name and name.strip()))
        if not unique_clean_names:
            return {}

        mapping: Dict[str, str] = {}
        with get_db_cursor(commit=True) as cursor:
            # 1. Fetch existing companies
            cursor.execute(
                "SELECT id::text AS id, name FROM companies WHERE name = ANY(%s);",
                (unique_clean_names,)
            )
            for row in cursor.fetchall():
                mapping[row['name']] = row['id']

            # 2. Bulk insert missing companies
            missing = [n for n in unique_clean_names if n not in mapping]
            if missing:
                for n in missing:
                    cid = str(uuid.uuid7())
                    cursor.execute("""
                        INSERT INTO companies (id, name)
                        VALUES (%s, %s)
                        ON CONFLICT (name) DO UPDATE SET updated_at = NOW()
                        RETURNING id::text AS id;
                    """, (cid, n))
                    res = cursor.fetchone()
                    mapping[n] = res['id']

        return mapping

    @staticmethod
    def find_or_create(name: str) -> str:
        res = CompanyRepository.find_or_create_batch([name])
        return res.get(name.strip()[:200], "")

    @staticmethod
    def find_by_id(company_id: Union[str, uuid.UUID]) -> Optional[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("SELECT id::text AS id, name, logo_url, description, size, website_url, created_at, updated_at FROM companies WHERE id = %s", (str(company_id),))
            return cursor.fetchone()

    @staticmethod
    def find_by_name(name: str) -> Optional[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("SELECT * FROM companies WHERE LOWER(name) = LOWER(%s)", (name.strip(),))
            return cursor.fetchone()

    @staticmethod
    def find_all(limit: int = 100) -> List[Dict[str, Any]]:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("SELECT * FROM companies ORDER BY name ASC LIMIT %s", (limit,))
            return cursor.fetchall()
