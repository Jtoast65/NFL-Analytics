"""
NFL analytics pipeline DAG.

Orchestrates the weekly refresh end-to-end:

    ingest_raw → load_to_s3 → dbt_build → retrain → rag_reindex

The project repo is mounted into the Astro container at PROJECT_DIR (see
airflow/README or the docker-compose override). Credentials (DATABASE_URL,
AWS_*, S3_BUCKET, DBT_*, OPENAI_API_KEY) are supplied via airflow/.env.
"""
from __future__ import annotations

import os

import pendulum
from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# Where the repo is mounted inside the Airflow worker.
PROJECT_DIR = os.environ.get("PROJECT_DIR", "/usr/local/airflow/include/nfl-analytics")

default_args = {
    "owner": "nfl-analytics",
    "retries": 1,
    "retry_delay": pendulum.duration(minutes=5),
}


def _load_raw_to_s3() -> None:
    """Upload the cached raw parquet files to S3 under raw/."""
    import glob

    import boto3

    bucket = os.environ["S3_BUCKET"]
    raw_dir = os.path.join(PROJECT_DIR, "data", "raw")
    s3 = boto3.client("s3")

    uploaded = 0
    for path in glob.glob(os.path.join(raw_dir, "**", "*.parquet"), recursive=True):
        key = "raw/" + os.path.relpath(path, raw_dir)
        s3.upload_file(path, bucket, key)
        uploaded += 1
    print(f"Uploaded {uploaded} raw parquet files to s3://{bucket}/raw/")


with DAG(
    dag_id="nfl_pipeline",
    description="Ingest → S3 → dbt → retrain → RAG reindex",
    schedule="@weekly",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args=default_args,
    tags=["nfl", "etl", "ml"],
) as dag:

    ingest_raw = BashOperator(
        task_id="ingest_raw",
        bash_command=(
            f"cd {PROJECT_DIR} && "
            "python ingestion/ingest_games.py && "
            "python ingestion/ingest_players.py && "
            "python ingestion/ingest_plays.py && "
            "python ingestion/ingest_player_stats.py"
        ),
    )

    load_to_s3 = PythonOperator(
        task_id="load_to_s3",
        python_callable=_load_raw_to_s3,
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd {PROJECT_DIR}/dbt/nfl_dbt && dbt build --profiles-dir .",
    )

    retrain = BashOperator(
        task_id="retrain",
        bash_command=(
            f"cd {PROJECT_DIR} && "
            "python features/build_features.py && "
            "python models/train.py && "
            "python models/batch_predict.py"
        ),
    )

    rag_reindex = BashOperator(
        task_id="rag_reindex",
        bash_command=f"cd {PROJECT_DIR} && python rag/embed_store.py",
    )

    ingest_raw >> load_to_s3 >> dbt_build >> retrain >> rag_reindex
