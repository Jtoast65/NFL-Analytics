# Airflow Orchestration (Astro)

Local Airflow via the [Astro CLI](https://docs.astronomer.io/astro/cli/overview).
Runs the `nfl_pipeline` DAG: **ingest_raw → load_to_s3 → dbt_build → retrain → rag_reindex**.

## Prerequisites
- Docker Desktop running
- Astro CLI (`brew install astro`)
- AWS provisioned + `infra/aws_setup.md` completed (S3 bucket, RDS, IAM keys)

## One-time setup

1. Create `airflow/.env` (gitignored) with the pipeline credentials:
   ```
   DATABASE_URL=postgresql://postgres:PASSWORD@RDS_ENDPOINT:5432/postgres?sslmode=require
   S3_BUCKET=nfl-analytics-raw-xyz
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   AWS_DEFAULT_REGION=us-west-2
   OPENAI_API_KEY=sk-...
   # dbt reads these (same RDS):
   DBT_HOST=RDS_ENDPOINT
   DBT_USER=postgres
   DBT_PASSWORD=PASSWORD
   DBT_DBNAME=postgres
   PROJECT_DIR=/usr/local/airflow/include/nfl-analytics
   ```

2. Make the repo available to the DAG by symlinking it into `include/`
   (Astro mounts `include/` into the containers):
   ```bash
   mkdir -p include
   ln -s ../.. include/nfl-analytics    # from the airflow/ directory
   ```

## Run

```bash
cd airflow
astro dev start      # boots scheduler + webserver + postgres (~4 containers)
# open http://localhost:8080  (admin / admin), enable & trigger the nfl_pipeline DAG
astro dev stop
```

## Notes
- `ingest_raw`, `dbt_build`, `retrain`, and `rag_reindex` shell out to the mounted
  project scripts; their Python deps are baked into the image via `requirements.txt`.
- `load_to_s3` uses boto3 with the `AWS_*` env vars.
- Schedule is `@weekly`; trigger manually from the UI for a demo.
