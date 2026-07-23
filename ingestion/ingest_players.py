"""
Ingest player roster data into the players table.
Uses load_players() for current player metadata.
Idempotent: safe to run multiple times.

Usage: python ingestion/ingest_players.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import nflreadpy as nfl
nfl.config.update_config(cache_mode="filesystem")
from ingestion.db import get_conn, upsert

COLS = {
    "gsis_id": "player_id",
    "display_name": "display_name",
    "position": "position",
    "team_abbr": "team",
    "birth_date": "birth_date",
    "college_name": "college",
    "entry_year": "entry_year",
    "status": "status",
}


def run() -> None:
    print("Loading player roster...")
    df = nfl.load_players()

    available = {k: v for k, v in COLS.items() if k in df.columns}
    df = df.select(list(available.keys()))
    df = df.rename(available)
    df = df.drop_nulls(subset=["player_id"])
    df = df.unique(subset=["player_id"], keep="last")

    rows = df.to_dicts()
    update_cols = [v for k, v in COLS.items() if v != "player_id"]

    with get_conn() as conn:
        n = upsert(conn, "players", rows, conflict_cols=["player_id"], update_cols=update_cols)

    print(f"  Upserted {n} players.")


if __name__ == "__main__":
    run()
