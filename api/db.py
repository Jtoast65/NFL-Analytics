"""Connection pool for FastAPI — shared across all requests."""
import os
import threading

import psycopg2.pool
from dotenv import load_dotenv

load_dotenv()

_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=10,
                    dsn=os.environ["DATABASE_URL"],
                )
    return _pool


def get_conn():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)
