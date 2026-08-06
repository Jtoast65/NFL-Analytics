"""
PySpark port of features/build_features.py.

Replicates the pandas feature-engineering step — one-hot downs, possession-relative
spread, and the "points in the last two drives" momentum feature — using Spark
window functions instead of pandas groupby/rolling. Reads the raw plays+games from
Postgres over JDBC and writes a features parquet.

Run locally (standalone Spark, needs JDK 17 + JAVA_HOME):
    python spark/feature_engineering_spark.py

Output: data/processed/features_spark.parquet  (row count should match the pandas
features.parquet — see the verification note in the plan).
"""
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

load_dotenv()
OUT_PATH = "data/processed/features_spark.parquet"
PG_DRIVER_PKG = "org.postgresql:postgresql:42.7.3"

PLAYS_QUERY = """
    (SELECT
        p.play_id, p.game_id, p.play_idx, g.season,
        p.qtr, p.down, p.ydstogo, p.yardline_100,
        p.game_seconds_remaining, p.score_differential,
        p.posteam, p.posteam_timeouts_remaining, p.defteam_timeouts_remaining,
        p.is_home_possession, p.nflfastr_wp, p.drive,
        g.spread_line, g.result AS game_result
     FROM plays p
     JOIN games g ON p.game_id = g.game_id
     WHERE p.play_type IS NOT NULL
       AND p.down IS NOT NULL
       AND p.game_seconds_remaining IS NOT NULL) AS plays
"""


def _jdbc(url: str) -> dict:
    u = urlparse(url)
    jdbc_url = f"jdbc:postgresql://{u.hostname}:{u.port or 5432}{u.path}?sslmode=require"
    return {
        "url": jdbc_url,
        "properties": {
            "user": u.username,
            "password": unquote(u.password),
            "driver": "org.postgresql.Driver",
            "ssl": "true",
        },
    }


def build_features(spark: SparkSession, df):
    # One-hot encode down (1-4)
    for d in (1, 2, 3, 4):
        df = df.withColumn(f"down_{d}", (F.col("down") == d).cast("int"))

    # Numeric / filled columns
    df = df.withColumn("is_home_possession",
                       F.coalesce(F.col("is_home_possession"), F.lit(False)).cast("int"))
    for c in ("posteam_timeouts_remaining", "defteam_timeouts_remaining"):
        df = df.withColumn(c, F.least(F.greatest(F.coalesce(F.col(c), F.lit(3)), F.lit(0)), F.lit(3)))
    df = df.withColumn("spread_line", F.coalesce(F.col("spread_line"), F.lit(0.0)))

    # Possession-relative spread (negative = possession team favored)
    df = df.withColumn(
        "posteam_spread",
        F.when(F.col("is_home_possession") == 1, F.col("spread_line"))
         .otherwise(-F.col("spread_line")),
    )

    df = _momentum(df)

    # Target: did the possession team win?
    df = df.withColumn("home_won", (F.col("game_result") > 0).cast("int"))
    df = df.withColumn(
        "posteam_won",
        F.when(F.col("is_home_possession") == 1, F.col("home_won"))
         .otherwise(1 - F.col("home_won")),
    )
    return df


def _momentum(df):
    """Points scored by posteam in their last two completed drives (Spark windows)."""
    w_game = Window.partitionBy("game_id").orderBy("play_idx")

    df = df.withColumn(
        "score_diff_prev",
        F.coalesce(F.lag("score_differential").over(w_game), F.col("score_differential")),
    )
    df = df.withColumn("next_drive", F.lead("drive").over(w_game))
    df = df.withColumn(
        "drive_ended",
        (F.col("next_drive") != F.col("drive")) | F.col("next_drive").isNull(),
    )
    df = df.withColumn(
        "pts_this_play",
        F.greatest(F.col("score_differential") - F.col("score_diff_prev"), F.lit(0)),
    )

    drive_pts = (
        df.filter(F.col("drive_ended"))
          .groupBy("game_id", "posteam", "drive")
          .agg(F.sum("pts_this_play").alias("drive_points"))
    )

    # Rolling sum of the previous two drives for this team (shift(1).rolling(2)).
    w_team = Window.partitionBy("game_id", "posteam").orderBy("drive").rowsBetween(-2, -1)
    drive_pts = drive_pts.withColumn(
        "momentum_score",
        F.coalesce(F.sum("drive_points").over(w_team), F.lit(0.0)),
    )

    df = df.join(
        drive_pts.select("game_id", "posteam", "drive", "momentum_score"),
        on=["game_id", "posteam", "drive"], how="left",
    )
    return df.withColumn("momentum_score", F.coalesce(F.col("momentum_score"), F.lit(0.0)))


FEATURE_OUT = [
    "game_id", "play_idx", "season", "nflfastr_wp", "posteam_won",
    "score_differential", "game_seconds_remaining",
    "down_1", "down_2", "down_3", "down_4",
    "ydstogo", "yardline_100", "is_home_possession",
    "posteam_timeouts_remaining", "defteam_timeouts_remaining",
    "qtr", "posteam_spread", "momentum_score",
]


def run():
    db_url = os.environ["DATABASE_URL"]
    jdbc = _jdbc(db_url)

    spark = (
        SparkSession.builder
        .appName("nfl-feature-engineering")
        .config("spark.jars.packages", PG_DRIVER_PKG)
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )
    print("Reading plays+games over JDBC ...")
    raw = spark.read.jdbc(url=jdbc["url"], table=PLAYS_QUERY, properties=jdbc["properties"])

    feats = build_features(spark, raw).select(*FEATURE_OUT).dropna(
        subset=[c for c in FEATURE_OUT if c not in ("nflfastr_wp",)]
    )

    n = feats.count()
    print(f"Engineered {n:,} feature rows")
    feats.write.mode("overwrite").parquet(OUT_PATH)
    print(f"Wrote → {OUT_PATH}")
    spark.stop()


if __name__ == "__main__":
    run()
