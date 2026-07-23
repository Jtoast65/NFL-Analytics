"""
Ingest play-by-play data into the plays table.
Processes one season at a time to avoid OOM on 9 seasons of PBP data.
Idempotent: safe to run multiple times.

Usage: python ingestion/ingest_plays.py [--seasons 2016 2017 ...]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl
import nflreadpy as nfl
nfl.config.update_config(cache_mode="filesystem")  # persist downloads across runs
from ingestion.db import get_conn, upsert

SEASONS = list(range(2016, 2026))  # update upper bound each offseason
BATCH_SIZE = 10_000

# Source column → DB column
COLS = {
    "game_id":                      "game_id",
    "play_id":                      "play_idx",
    "qtr":                          "qtr",
    "down":                         "down",
    "ydstogo":                      "ydstogo",
    "yardline_100":                 "yardline_100",
    "game_seconds_remaining":       "game_seconds_remaining",
    "score_differential":           "score_differential",
    "posteam":                      "posteam",
    "defteam":                      "defteam",
    "posteam_timeouts_remaining":   "posteam_timeouts_remaining",
    "defteam_timeouts_remaining":   "defteam_timeouts_remaining",
    "wp":                           "nflfastr_wp",
    "play_type":                    "play_type",
    "yards_gained":                 "yards_gained",
    "touchdown":                    "touchdown",
    "drive":                        "drive",
}


def process_season(season: int) -> None:
    print(f"  {season}", end=" → ", flush=True)
    raw = nfl.load_pbp(seasons=season)
    print(f"{len(raw):,} plays", end=" → ", flush=True)

    # Compute is_home_possession before narrowing columns
    if "home_team" in raw.columns:
        raw = raw.with_columns(
            (pl.col("posteam") == pl.col("home_team")).alias("is_home_possession")
        )
    else:
        raw = raw.with_columns(pl.lit(None).cast(pl.Boolean).alias("is_home_possession"))

    available = {k: v for k, v in COLS.items() if k in raw.columns}
    df = raw.select(list(available.keys()) + ["is_home_possession"])
    df = df.rename(available)

    # nflfastR stores all numeric columns as float — cast to correct types
    int_cols = ["play_idx", "qtr", "down", "ydstogo", "yardline_100",
                "game_seconds_remaining", "score_differential",
                "posteam_timeouts_remaining", "defteam_timeouts_remaining",
                "yards_gained", "drive"]
    for col in int_cols:
        if col in df.columns:
            df = df.with_columns(pl.col(col).cast(pl.Int32, strict=False))

    # touchdown arrives as 0.0/1.0 float — cast to boolean
    if "touchdown" in df.columns:
        df = df.with_columns(
            pl.when(pl.col("touchdown").is_null())
            .then(None)
            .otherwise(pl.col("touchdown").cast(pl.Float64) != 0)
            .alias("touchdown")
        )

    df = df.drop_nulls(subset=["game_id", "play_idx"])

    rows = df.to_dicts()
    update_cols = [v for v in available.values() if v not in ("game_id", "play_idx")] + ["is_home_possession"]

    total = 0
    with get_conn() as conn:
        for i in range(0, len(rows), BATCH_SIZE):
            n = upsert(conn, "plays", rows[i : i + BATCH_SIZE],
                       conflict_cols=["game_id", "play_idx"],
                       update_cols=update_cols)
            total += n

    print(f"upserted {total:,}")


def run(seasons: list[int]) -> None:
    print(f"Ingesting plays for seasons {seasons[0]}–{seasons[-1]}")
    for season in seasons:
        process_season(season)
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", nargs="+", type=int, default=SEASONS)
    args = parser.parse_args()
    run(args.seasons)
