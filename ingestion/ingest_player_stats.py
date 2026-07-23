"""
Ingest weekly player stats into the player_stats table.
Idempotent: safe to run multiple times.

Usage: python ingestion/ingest_player_stats.py [--seasons 2016 2017 ...]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import nflreadpy as nfl
nfl.config.update_config(cache_mode="filesystem")
from ingestion.db import get_conn, upsert

SEASONS = list(range(2016, 2026))  # update upper bound each offseason

COLS = {
    "player_id": "player_id",
    "season": "season",
    "week": "week",
    "season_type": "season_type",
    "team": "team",                           # nflreadpy uses 'team', not 'recent_team'
    "completions": "completions",
    "attempts": "attempts",
    "passing_yards": "passing_yards",
    "passing_tds": "passing_tds",
    "passing_interceptions": "interceptions", # nflreadpy prefixes with 'passing_'
    "sacks_suffered": "sacks",               # sacks taken by the QB
    "carries": "carries",
    "rushing_yards": "rushing_yards",
    "rushing_tds": "rushing_tds",
    "receptions": "receptions",
    "targets": "targets",
    "receiving_yards": "receiving_yards",
    "receiving_tds": "receiving_tds",
    "fantasy_points": "fantasy_points",
    "fantasy_points_ppr": "fantasy_points_ppr",
}


def run(seasons: list[int]) -> None:
    print(f"Loading weekly player stats for {seasons[0]}–{seasons[-1]} ...")
    df = nfl.load_player_stats(seasons=seasons, summary_level="week")
    print(f"  {len(df):,} rows loaded")

    available = {k: v for k, v in COLS.items() if k in df.columns}
    df = df.select(list(available.keys()))
    df = df.rename(available)
    df = df.drop_nulls(subset=["player_id", "season", "week"])

    # Default season_type to REG if missing
    if "season_type" not in df.columns:
        import polars as pl
        df = df.with_columns(pl.lit("REG").alias("season_type"))

    rows = df.to_dicts()
    update_cols = [v for k, v in available.items() if v not in ("player_id", "season", "week", "season_type")]

    with get_conn() as conn:
        n = upsert(
            conn, "player_stats", rows,
            conflict_cols=["player_id", "season", "week", "season_type"],
            update_cols=update_cols,
        )

    print(f"  Upserted {n} stat rows.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", nargs="+", type=int, default=SEASONS)
    args = parser.parse_args()
    run(args.seasons)
