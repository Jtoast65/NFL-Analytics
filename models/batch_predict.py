"""
Write model_wp predictions back to the plays table for all ingested plays.
Run once after training: python models/batch_predict.py

This enables the Game Replay dashboard page to show our model's WP curve
alongside the nflfastR baseline.
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

from features.feature_config import FEATURE_COLS
from models.predict import predict_wp, _load_model

load_dotenv()
DB_URL = os.environ["DATABASE_URL"]
BATCH_SIZE = 5_000


def run():
    print("Loading feature matrix...")
    df = pd.read_parquet("data/processed/features.parquet")
    print(f"  {len(df):,} plays")

    model = _load_model()
    X = df[FEATURE_COLS].values
    print("Running batch inference...")
    probs = model.predict_proba(X)[:, 1]
    df["model_wp"] = np.round(probs, 5)

    print("Writing model_wp to plays table...")
    records = df[["game_id", "play_idx", "model_wp"]].to_dict("records")
    conn = psycopg2.connect(DB_URL)
    total = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                "UPDATE plays SET model_wp = data.wp "
                "FROM (VALUES %s) AS data(game_id, play_idx, wp) "
                "WHERE plays.game_id = data.game_id AND plays.play_idx = data.play_idx",
                [(r["game_id"], r["play_idx"], r["model_wp"]) for r in batch],
                page_size=len(batch),
            )
        conn.commit()
        total += len(batch)
        print(f"  {total:,} / {len(records):,}", end="\r")

    conn.close()
    print(f"\nDone. Wrote model_wp for {total:,} plays.")


if __name__ == "__main__":
    run()
