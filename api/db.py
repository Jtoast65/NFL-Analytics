"""Connection pool for FastAPI — shared across all requests."""
import os

import psycopg2.pool
from dotenv import load_dotenv

load_dotenv()

_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    dsn=os.environ["DATABASE_URL"],
)


def get_conn():
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)
