"""
Ingest game metadata from nflreadpy schedules into the games table.
Idempotent: safe to run multiple times.

Usage: python ingestion/ingest_games.py [--seasons 2016 2017 ...]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import nflreadpy as nfl
nfl.config.update_config(cache_mode="filesystem")
from ingestion.db import get_conn, upsert

SEASONS = list(range(2016, 2026))  # 2016–2025 inclusive

COLS = {
    "game_id": "game_id",
    "season": "season",
    "week": "week",
    "game_type": "game_type",
    "home_team": "home_team",
    "away_team": "away_team",
    "home_score": "home_score",
    "away_score": "away_score",
    "result": "result",
    "spread_line": "spread_line",
    "total_line": "total_line",
    "gameday": "game_date",
}


def run(seasons: list[int]) -> None:
    print(f"Loading schedules for seasons {seasons[0]}–{seasons[-1]} ...")
    df = nfl.load_schedules(seasons=seasons)

    df = df.select([c for c in COLS if c in df.columns])
    df = df.rename({k: v for k, v in COLS.items() if k in df.columns and k != v})
    df = df.drop_nulls(subset=["game_id", "home_team", "away_team"])

    rows = df.to_dicts()
    update_cols = [c for c in COLS.values() if c != "game_id"]

    with get_conn() as conn:
        n = upsert(conn, "games", rows, conflict_cols=["game_id"], update_cols=update_cols)

    print(f"  Upserted {n} games.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", nargs="+", type=int, default=SEASONS)
    args = parser.parse_args()
    run(args.seasons)
