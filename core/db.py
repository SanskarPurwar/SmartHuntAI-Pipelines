from contextlib import contextmanager
import psycopg2
import psycopg2.pool
import psycopg2.extras
from core.config import settings

# Register native UUID adapter for seamless PostgreSQL UUID mapping
psycopg2.extras.register_uuid()

_DATABASE_URL = settings.DATABASE_URL
_pool = None

def get_pool(minconn: int = 1, maxconn: int = 15) -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        if not _DATABASE_URL:
            raise RuntimeError("DATABASE_URL environment variable is not configured.")
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            dsn=_DATABASE_URL
        )
    return _pool

def close_pool():
    global _pool
    if _pool and not _pool.closed:
        _pool.closeall()
        _pool = None

@contextmanager
def get_db_connection():
    """
    Context manager that acquires a connection from the pool,
    and guarantees it is returned to the pool even on exceptions.
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)

@contextmanager
def get_db_cursor(commit: bool = True, cursor_factory=psycopg2.extras.RealDictCursor):
    """
    Context manager that yields a database cursor with automatic transaction
    commit/rollback and connection return to pool.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
