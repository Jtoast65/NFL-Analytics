"""
Phase 3: Feature engineering pipeline.

Reads plays + games from PostgreSQL, engineers all model features,
writes momentum_score back to the plays table, and saves a
features.parquet file ready for model training.

Usage: python features/build_features.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from features.feature_config import FEATURE_COLS, MODEL_TARGET

load_dotenv()
DB_URL = os.environ["DATABASE_URL"]
OUT_PATH = Path("data/processed/features.parquet")


# ---------------------------------------------------------------------------
# 1. Load raw data from DB
# ---------------------------------------------------------------------------

def load_plays() -> pd.DataFrame:
    print("Loading plays from DB...")
    sql = """
        SELECT
            p.play_id,
            p.game_id,
            p.play_idx,
            g.season,
            p.qtr,
            p.down,
            p.ydstogo,
            p.yardline_100,
            p.game_seconds_remaining,
            p.score_differential,
            p.posteam,
            p.posteam_timeouts_remaining,
            p.defteam_timeouts_remaining,
            p.is_home_possession,
            p.nflfastr_wp,
            p.drive,
            p.touchdown,
            p.play_type,
            g.spread_line,
            g.result AS game_result,
            g.home_team
        FROM plays p
        JOIN games g ON p.game_id = g.game_id
        WHERE p.play_type IS NOT NULL
          AND p.down IS NOT NULL
          AND p.game_seconds_remaining IS NOT NULL
    """
    conn = psycopg2.connect(DB_URL)
    df = pd.read_sql(sql, conn)
    conn.close()
    print(f"  Loaded {len(df):,} plays from {df['season'].nunique()} seasons")
    return df


# ---------------------------------------------------------------------------
# 2. Engineer features
# ---------------------------------------------------------------------------

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    print("Engineering features...")

    # One-hot encode down (1–4)
    for d in [1, 2, 3, 4]:
        df[f"down_{d}"] = (df["down"] == d).astype(int)

    # Ensure boolean column is numeric
    df["is_home_possession"] = df["is_home_possession"].fillna(False).astype(int)

    # Fill missing timeouts with 3 (start of game default)
    df["posteam_timeouts_remaining"] = df["posteam_timeouts_remaining"].fillna(3).clip(0, 3)
    df["defteam_timeouts_remaining"] = df["defteam_timeouts_remaining"].fillna(3).clip(0, 3)

    # Fill missing spread_line with 0 (pick-em)
    df["spread_line"] = df["spread_line"].fillna(0)

    # posteam_spread: spread from the POSSESSION team's perspective.
    # spread_line in nflfastR is always the HOME team's spread (negative = home favored).
    # Flip sign when away team has the ball so the feature is always
    # "negative = possession team is favored" regardless of who has the ball.
    df["posteam_spread"] = np.where(
        df["is_home_possession"] == 1,
        df["spread_line"],
        -df["spread_line"],
    )

    # Momentum score: points scored by posteam in their last 2 possessions
    df = _compute_momentum(df)

    # Target variable: did posteam win?
    # game_result = home_score - away_score (positive → home won)
    df["home_won"] = (df["game_result"] > 0).astype(int)
    df[MODEL_TARGET] = np.where(
        df["is_home_possession"] == 1,
        df["home_won"],
        1 - df["home_won"],
    )

    print(f"  Win rate in dataset: {df[MODEL_TARGET].mean():.3f} (expect ~0.50)")
    return df


def _compute_momentum(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute points scored by posteam in their last 2 completed drives.

    Strategy:
    1. Sort by game + play order.
    2. Detect score changes between consecutive plays within a game.
    3. Attribute points to the scoring team's drive.
    4. For each play, look back 2 completed drives for that team in that game.
    """
    df = df.sort_values(["game_id", "play_idx"]).copy()

    # Points scored ON each play (from score_differential delta within game)
    df["score_diff_prev"] = df.groupby("game_id")["score_differential"].shift(1)
    df["score_diff_prev"] = df["score_diff_prev"].fillna(df["score_differential"])

    # Identify drive end: drive number changes or game ends
    df["next_drive"] = df.groupby("game_id")["drive"].shift(-1)
    df["drive_ended"] = (df["next_drive"] != df["drive"]) | df["next_drive"].isna()

    # Points scored per drive by posteam (sum of positive score changes while on offense)
    df["pts_this_play"] = (df["score_differential"] - df["score_diff_prev"]).clip(lower=0)
    drive_pts = (
        df[df["drive_ended"]]
        .groupby(["game_id", "posteam", "drive"])["pts_this_play"]
        .sum()
        .reset_index()
        .rename(columns={"pts_this_play": "drive_points"})
    )

    # For each team in each game, compute rolling sum of last 2 drives
    drive_pts = drive_pts.sort_values(["game_id", "posteam", "drive"])
    drive_pts["momentum_score"] = (
        drive_pts.groupby(["game_id", "posteam"])["drive_points"]
        .transform(lambda x: x.shift(1).rolling(2, min_periods=1).sum())
        .fillna(0)
    )

    # Merge momentum back onto plays via game_id + posteam + drive
    df = df.merge(
        drive_pts[["game_id", "posteam", "drive", "momentum_score"]],
        on=["game_id", "posteam", "drive"],
        how="left",
    )
    df["momentum_score"] = df["momentum_score"].fillna(0)

    # Clean up temp columns
    df.drop(columns=["score_diff_prev", "next_drive", "drive_ended", "pts_this_play"], inplace=True)
    return df


# ---------------------------------------------------------------------------
# 3. Write momentum_score back to plays table
# ---------------------------------------------------------------------------

def write_momentum_to_db(df: pd.DataFrame) -> None:
    print("Writing momentum_score back to plays table...")
    records = df[["game_id", "play_idx", "momentum_score"]].dropna().to_dict("records")

    conn = psycopg2.connect(DB_URL)
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            "UPDATE plays SET momentum_score = data.ms FROM "
            "(VALUES %s) AS data(game_id, play_idx, ms) "
            "WHERE plays.game_id = data.game_id AND plays.play_idx = data.play_idx",
            [(r["game_id"], r["play_idx"], r["momentum_score"]) for r in records],
            page_size=5000,
        )
    conn.commit()
    conn.close()
    print(f"  Updated {len(records):,} plays with momentum_score")


# ---------------------------------------------------------------------------
# 4. Save feature matrix to parquet
# ---------------------------------------------------------------------------

def save_features(df: pd.DataFrame) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cols = ["game_id", "play_idx", "season", "nflfastr_wp", MODEL_TARGET] + FEATURE_COLS
    out = df[cols].dropna(subset=FEATURE_COLS + [MODEL_TARGET])
    out.to_parquet(OUT_PATH, index=False)
    print(f"  Saved {len(out):,} rows → {OUT_PATH}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run() -> None:
    df = load_plays()
    df = engineer_features(df)
    write_momentum_to_db(df)
    save_features(df)
    print("\nFeature engineering complete.")
    print(f"  Feature matrix: {OUT_PATH}")
    print(f"  Seasons: {sorted(df['season'].unique())}")
    print(f"  Total plays: {len(df):,}")


if __name__ == "__main__":
    run()
