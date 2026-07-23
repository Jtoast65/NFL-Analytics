"""Database connection and bulk-upsert helpers for ingestion scripts."""
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

_DATABASE_URL = os.environ["DATABASE_URL"]


@contextmanager
def get_conn():
    """Yield a raw psycopg2 connection with autocommit off; commits on exit."""
    conn = psycopg2.connect(_DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert(conn, table: str, rows: list[dict], conflict_cols: list[str], update_cols: list[str]) -> int:
    """Bulk upsert using execute_values — one round-trip per batch regardless of row count."""
    if not rows:
        return 0

    col_names = list(rows[0].keys())
    cols_sql = ", ".join(col_names)
    conflict_sql = ", ".join(conflict_cols)
    update_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    template = "(" + ", ".join(f"%({c})s" for c in col_names) + ")"

    sql = (
        f"INSERT INTO {table} ({cols_sql}) VALUES %s "
        f"ON CONFLICT ({conflict_sql}) DO UPDATE SET {update_sql}"
    )

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, rows, template=template, page_size=len(rows))

    return len(rows)
