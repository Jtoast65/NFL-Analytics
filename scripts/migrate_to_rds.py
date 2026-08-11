"""
One-time migration: Supabase Postgres → AWS RDS Postgres.

Recreates our known schema on RDS from schema/init.sql + schema/rag.sql (avoids
Supabase-specific roles/extension placement), then streams the data table-by-table
in foreign-key order via COPY. Reads both connection strings from the environment
(DATABASE_URL = Supabase source, RDS_DATABASE_URL = RDS target) so no password is
ever passed on a shell command line.

Usage: python scripts/migrate_to_rds.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from dotenv import load_dotenv

load_dotenv()
SRC = os.environ["DATABASE_URL"]        # Supabase
DST = os.environ["RDS_DATABASE_URL"]    # RDS

# Foreign-key-safe load order.
TABLES = ["games", "players", "player_stats", "plays", "predictions", "documents"]
# BIGSERIAL columns whose sequences must be re-synced after copying explicit ids.
SEQUENCES = {
    "plays": "play_id",
    "player_stats": "stat_id",
    "predictions": "pred_id",
    "documents": "id",
}


def apply_schema(dst) -> None:
    print("Applying schema to RDS (init.sql + rag.sql) ...")
    dst.autocommit = True
    with dst.cursor() as cur:
        for f in ("schema/init.sql", "schema/rag.sql"):
            cur.execute(Path(f).read_text())
            print(f"  applied {f}")
    dst.autocommit = False


def copy_table(src, dst, table: str) -> tuple[int, int]:
    with tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024, mode="w+b") as buf:
        with src.cursor() as scur:
            scur.copy_expert(f"COPY {table} TO STDOUT", buf)
        buf.seek(0)
        with dst.cursor() as dcur:
            dcur.execute(f"TRUNCATE {table} CASCADE")
            dcur.copy_expert(f"COPY {table} FROM STDIN", buf)
        dst.commit()

    with src.cursor() as scur:
        scur.execute(f"SELECT count(*) FROM {table}")
        src_n = scur.fetchone()[0]
    with dst.cursor() as dcur:
        dcur.execute(f"SELECT count(*) FROM {table}")
        dst_n = dcur.fetchone()[0]
    return src_n, dst_n


def reset_sequences(dst) -> None:
    print("Resetting sequences ...")
    with dst.cursor() as cur:
        for table, col in SEQUENCES.items():
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence(%s, %s), "
                f"COALESCE((SELECT MAX({col}) FROM {table}), 1))",
                (table, col),
            )
    dst.commit()


def run() -> None:
    src = psycopg2.connect(SRC)
    dst = psycopg2.connect(DST)
    try:
        apply_schema(dst)
        print("\nCopying data (source → RDS):")
        all_ok = True
        for t in TABLES:
            src_n, dst_n = copy_table(src, dst, t)
            ok = src_n == dst_n
            all_ok &= ok
            print(f"  {t:14} {src_n:>8,} → {dst_n:>8,}  {'OK' if ok else 'MISMATCH'}")
        reset_sequences(dst)
        print("\nMigration complete." if all_ok else "\nMigration finished WITH MISMATCHES.")
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    run()
