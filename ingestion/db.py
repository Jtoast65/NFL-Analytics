"""Database connection and bulk-upsert helpers for ingestion scripts."""
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

_DATABASE_URL = os.environ["DATABASE_URL"]

# Raw parquet lands here so the orchestration DAG's load_to_s3 task has a
# file-based "raw layer" to ship to S3 (see airflow/dags/nfl_pipeline_dag.py).
_RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def save_raw(df, name: str) -> Path:
    """Persist a cleaned ingestion DataFrame to data/raw/<name>.parquet.

    Accepts a polars DataFrame (what nflreadpy returns); the parquet mirror is
    what gets uploaded to s3://$S3_BUCKET/raw/ by the pipeline DAG.
    """
    path = _RAW_DIR / f"{name}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)  # `name` may include subdirs (e.g. plays/season=2024)
    df.write_parquet(path)
    print(f"  Wrote raw parquet: {path.relative_to(_RAW_DIR.parent.parent)} ({df.height:,} rows)")
    return path


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
