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

2. Make the repo available to the DAG. The tasks shell out to the project scripts
   at `/usr/local/airflow/include/nfl-analytics`, provided by a **runtime bind
   mount** in `docker-compose.override.yml` (a `include/` symlink does NOT work —
   Docker rejects a symlink that escapes the build context). The override's host
   path is absolute; update it if you move the repo:
   ```yaml
   # docker-compose.override.yml (already committed)
   services:
     scheduler:
       volumes:
         - /ABS/PATH/TO/nfl-analytics:/usr/local/airflow/include/nfl-analytics:rw
   ```

## Run

```bash
cd airflow
astro dev start      # boots scheduler + webserver + postgres (~4 containers)
# open http://localhost:8080  (admin / admin), enable & trigger the nfl_pipeline DAG
astro dev stop
```

## Notes
- `ingest_raw`, `retrain`, and `rag_reindex` run from an isolated **project venv**
  (`/usr/local/airflow/project_venv`, built from `project_requirements.txt`);
  `dbt_build` runs from an isolated **dbt venv** (`dbt_venv`, `dbt_requirements.txt`).
  These are kept out of the Airflow environment on purpose — installing dbt-core
  into the Airflow env triggers a pip `ResolutionTooDeep` failure.
- `load_to_s3` runs in the Airflow env and uses boto3 (in `requirements.txt`) with
  the `AWS_*` env vars.
- Validate DAG + image without booting anything: `astro dev parse`.
- Schedule is `@weekly`; trigger manually from the UI for a demo.
