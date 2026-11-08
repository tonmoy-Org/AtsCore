import logging
import threading
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from app.config import Config

logger = logging.getLogger("atscore.db")

_pg_pool = None
_pool_lock = threading.Lock()


def init_pg_pool():
    """Initializes the thread-safe PostgreSQL connection pool."""
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool

    with _pool_lock:
        if _pg_pool is not None:
            return _pg_pool
        try:
            logger.info(
                f"Connecting to PostgreSQL at {Config.PG_HOST}:{Config.PG_PORT}/{Config.PG_DATABASE}..."
            )
            _pg_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=Config.PG_POOL_MIN,
                maxconn=Config.PG_POOL_MAX,
                host=Config.PG_HOST,
                port=Config.PG_PORT,
                database=Config.PG_DATABASE,
                user=Config.PG_USER,
                password=Config.PG_PASSWORD,
                connect_timeout=5,
            )
            logger.info("PostgreSQL ThreadedConnectionPool initialized successfully.")
            return _pg_pool
        except Exception as e:
            logger.warning(f"Failed to initialize PostgreSQL pool: {e}")
            return None


def close_pg_pool():
    """Closes all connections in the pool."""
    global _pg_pool
    with _pool_lock:
        if _pg_pool is not None:
            _pg_pool.closeall()
            _pg_pool = None
            logger.info("PostgreSQL Connection Pool closed.")


@contextmanager
def get_pg_connection():
    """Context manager to lease and safely release a PostgreSQL connection."""
    pool_inst = init_pg_pool()
    if pool_inst is None:
        raise ConnectionError(
            f"Cannot acquire PostgreSQL connection: pool is unavailable for {Config.PG_HOST}:{Config.PG_PORT}/{Config.PG_DATABASE}"
        )
    conn = pool_inst.getconn()
    try:
        yield conn
    finally:
        pool_inst.putconn(conn)


@contextmanager
def get_pg_cursor(dict_cursor=False, autocommit=False):
    """Context manager for obtaining a database cursor with automatic commit/rollback."""
    with get_pg_connection() as conn:
        conn.autocommit = autocommit
        cursor_factory = RealDictCursor if dict_cursor else None
        cursor = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
            if not autocommit:
                conn.commit()
        except Exception:
            if not autocommit:
                conn.rollback()
            raise
        finally:
            cursor.close()


def check_pg_health():
    """Checks the health of the PostgreSQL server and returns version & response time."""
    import time
    t0 = time.perf_counter()
    try:
        with get_pg_cursor(dict_cursor=True) as cur:
            cur.execute("SELECT version() as pg_version, current_database() as db_name, NOW() as server_time")
            res = cur.fetchone()
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "online": True,
                "version": res["pg_version"],
                "database": res["db_name"],
                "server_time": str(res["server_time"]),
                "latency_ms": latency_ms,
            }
    except Exception as e:
        return {
            "online": False,
            "error": str(e),
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        }

