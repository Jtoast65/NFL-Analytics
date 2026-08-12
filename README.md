# NFL Win Probability & Player Performance Pipeline

End-to-end ML engineering portfolio project: play-by-play ingestion → PostgreSQL → calibrated XGBoost win-probability model → FastAPI → Streamlit dashboard, extended with a **retrieval-augmented (RAG) Q&A layer** and a **cloud batch/orchestration pipeline** (Airflow · dbt · AWS RDS + S3 · PySpark).

**Live demo:** https://nfl-analytics-crwjgsvzmwtrhl75mwpmtp.streamlit.app · **API docs:** https://nfl-analytics-api-aku6.onrender.com/docs

---

## Architecture

The project runs as two complementary stacks: an always-on **serving stack** (free-tier hosted) and an on-demand **AWS batch/orchestration stack** that demonstrates production data-engineering patterns and can be spun up and torn down to control cost.

### Serving stack (always-on)

```
nflreadpy (nflfastR data)
        │
        ▼  idempotent ingestion scripts
┌─────────────────────────────────────────────┐
│  PostgreSQL (Supabase)  ·  pgvector          │
│  games · plays · players · player_stats      │
│  predictions · documents (RAG embeddings)    │
└───────┬─────────────────────────────────────┘
        │
        ▼  feature engineering
  XGBoost + Isotonic Calibration
  (Brier 0.140 vs 0.157 nflfastR baseline, 2024 holdout)
        │
        ▼  joblib
┌─────────────────────────────────────────────┐
│  FastAPI  (Render)                           │
│  POST /predict      · GET /leaderboard       │
│  GET  /games/{id}/win_probability            │
│  GET  /players/{id}/stats                    │
│  POST /ask          (RAG Q&A → OpenAI)       │
└───────┬─────────────────────────────────────┘
        │  HTTP
        ▼
┌─────────────────────────────────────────────┐
│  Streamlit  (Community Cloud)                │
│  1 · Live Simulator     2 · Game Replay      │
│  3 · Player Leaderboard 4 · Model Performance│
│  5 · Ask the Data (natural-language Q&A)     │
└─────────────────────────────────────────────┘
```

### AWS batch/orchestration stack (on-demand)

```
        Apache Airflow (Astro / local Docker)
        DAG: nfl_pipeline  (@weekly, max_active_runs=1)

  ingest_raw ─▶ load_to_s3 ─▶ dbt_build ─▶ retrain ─▶ rag_reindex
      │             │             │           │            │
      ▼             ▼             ▼           ▼            ▼
 nflreadpy →   S3 raw lake    dbt marts   XGBoost    re-embed docs
 RDS + parquet (raw/…,        on RDS      retrain +  (OpenAI) into
 (data/raw)   partitioned     (staging→   batch      pgvector
              plays/season=*) marts)      predict
```

- **AWS RDS (PostgreSQL)** — the batch pipeline's warehouse; data migrated from Supabase via `scripts/migrate_to_rds.py` (schema-recreate + `COPY` in FK order).
- **AWS S3** — file-based raw layer (`s3://…/raw/`), plays partitioned by season.
- **dbt** (`dbt/nfl_dbt`) — `staging` views + `analytics_marts` (`mart_player_season`, `mart_leaderboard`, `mart_game_summary`) with not-null/unique tests.
- **PySpark** (`spark/feature_engineering_spark.py`) — momentum/feature engineering ported to Spark window functions; output matches the pandas pipeline row-for-row (407,060 rows).

---

## Features

- **407K+ plays** ingested from 2016–2025 NFL seasons via [nflreadpy](https://github.com/nflreadpy/nflreadpy)
- **14-feature XGBoost model** with isotonic calibration: score differential, time, field position, timeouts, down/distance, Vegas spread, and rolling momentum
- **Beats nflfastR baseline** by 8% on Brier score (0.140 vs 0.157) on the 2024 test season
- **Real-time win probability simulator** — adjust any game-state parameter and see WP update instantly
- **Historical game replay** — animate the WP curve for any game since 2016
- **Player leaderboard** with PPR fantasy-point rankings filterable by position, team, and season
- **Ask the Data (RAG)** — natural-language questions answered by retrieval over a pgvector store, grounded in ranked-fact documents (embeddings: `text-embedding-3-small`; generation: `gpt-4o-mini`)
- **Orchestrated cloud pipeline** — Airflow DAG runs ingest → S3 → dbt → retrain → RAG reindex end-to-end against AWS RDS + S3

---

## Extension 1 — RAG Q&A layer

Natural-language Q&A over the database using classic retrieval-augmented generation (chunk → embed → retrieve → prompt), not text-to-SQL.

- `rag/build_documents.py` — turns DB rows into short natural-language docs (player-season, game recap, leaderboard snapshot), **baking ranked facts into the text** (e.g. "…2,005 rushing yards, 1st among RBs in 2024…") so ranking questions retrieve correctly.
- `rag/embed_store.py` — batch-embeds docs with OpenAI and upserts into the `documents` table (pgvector, HNSW cosine index).
- `rag/retriever.py` / `rag/qa.py` — top-k cosine retrieval → prompt grounded strictly in retrieved context → `gpt-4o-mini` → `{answer, sources}`.
- Served at `POST /ask` (`api/routers/ask.py`) and surfaced on Streamlit page **5 · Ask the Data**.

~7,600 documents embedded. Example: *"Who had the most rushing yards in 2024?"* → *"Saquon Barkley (PHI), 2,005 yards"* with cited sources.

---

## Extension 2 — Orchestration + cloud

Wraps the existing ingestion/model/RAG code in Airflow and moves the batch warehouse to AWS — **no rebuild of the model or dashboard**.

- **Migration** — `scripts/migrate_to_rds.py` recreates the schema on RDS and streams every table (incl. the pgvector `documents` table) via `COPY`, then resyncs sequences.
- **dbt** (`dbt/nfl_dbt`) — sources → staging → marts, materialized in `analytics_marts`, with tests. `dbt build` runs green on RDS.
- **Airflow** (`airflow/`, Astro Runtime) — `nfl_pipeline` DAG: `ingest_raw → load_to_s3 → dbt_build → retrain → rag_reindex`. Validated with `astro dev parse` and run green end-to-end.
- **PySpark** (`spark/`) — Spark port of the feature engineering, verified against the pandas output.

**Notable engineering decisions (see `airflow/README.md`):**
- dbt and the project's ML/RAG deps install into **isolated virtualenvs** in the Airflow image (`dbt_venv`, `project_venv`); the Airflow env stays minimal. Installing `dbt-core` into the Airflow environment triggers a pip `ResolutionTooDeep` failure.
- The repo is mounted into containers via a `docker-compose.override.yml` **bind mount** (a symlink escaping the build context breaks Docker).
- `max_active_runs=1` on the DAG — concurrent runs deadlock on shared RDS upserts.

See `infra/aws_setup.md` for provisioning **and teardown** (free-tier RDS + S3; stop/delete the instance when not demoing to avoid charges).

---

## Local Setup

**Prerequisites:** Python 3.11+, PostgreSQL client (`psql`). For the RAG layer: an OpenAI API key. For the cloud pipeline (optional): Docker Desktop, the [Astro CLI](https://docs.astronomer.io/astro/cli/overview), and JDK 17 (PySpark).

```bash
git clone https://github.com/Jtoast65/NFL-Analytics.git
cd nfl-analytics

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — add DATABASE_URL (Supabase) and OPENAI_API_KEY.
# For Extension 2: RDS_DATABASE_URL, AWS_* and S3_BUCKET (see .env.example).
```

**Run with Docker Compose:**
```bash
docker-compose up
# API: http://localhost:8000/docs
# Dashboard: http://localhost:8501
```

**Or run manually:**
```bash
make serve       # Terminal 1 — API
make dashboard   # Terminal 2 — Dashboard
```

**Run the Airflow pipeline locally (Extension 2):**
```bash
cd airflow
cp .env.example .env         # fill in RDS + AWS + OpenAI creds
astro dev parse              # validate the DAG + image (no boot)
astro dev start              # boot Airflow at http://localhost:8080 (admin/admin)
# trigger the nfl_pipeline DAG from the UI, then: astro dev stop
```

---

## Reproducing the Model

```bash
# 1. Ingest all data (~10 min first run; nflreadpy caches downloads).
#    Also writes a parquet raw layer to data/raw/ for the S3 upload task.
make ingest

# 2. Build the feature matrix and run batch predictions
python features/build_features.py
python models/batch_predict.py

# 3. Train (train 2016–2022, val 2023, test 2024)
make train

# 4. (Optional) Build + embed the RAG documents
python rag/build_documents.py
python rag/embed_store.py

# 5. Smoke tests
make test
```

---

## Model Details

| | |
|---|---|
| **Algorithm** | XGBoost + Isotonic Regression calibration |
| **Training** | 2016–2022 seasons (282,906 plays) |
| **Validation** | 2023 season (41,917 plays) |
| **Test** | 2024 season (41,469 plays) |
| **Brier score** | 0.1400 (ours) vs 0.1570 (nflfastR baseline) |
| **ROC-AUC** | 0.884 on 2024 holdout |
| **Target** | Did the possession team win? (`posteam_won`) |

---

## API Reference

```bash
# Real-time win probability
curl -X POST https://nfl-analytics-api-aku6.onrender.com/predict \
  -H "Content-Type: application/json" \
  -d '{
    "score_differential": -3,
    "game_seconds_remaining": 420,
    "down": 3,
    "ydstogo": 7,
    "yardline_100": 65,
    "is_home_possession": true,
    "qtr": 4,
    "spread_line": -3.5
  }'
# → {"win_probability": 0.42, "model_version": "v1"}
# spread_line convention: negative = home team favored

# Natural-language Q&A (RAG)
curl -X POST https://nfl-analytics-api-aku6.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Who had the most rushing yards in 2024?", "k": 6}'
# → {"answer": "Saquon Barkley (PHI) … 2005 yards", "sources": [...]}

# Game replay
GET https://nfl-analytics-api-aku6.onrender.com/games/{game_id}/win_probability

# Player stats
GET https://nfl-analytics-api-aku6.onrender.com/players/{player_id}/stats

# Leaderboard
GET https://nfl-analytics-api-aku6.onrender.com/leaderboard?season=2024&position=QB&limit=25
```

> **Note:** The Render free tier spins down after ~15 minutes of inactivity, so the first request after idle cold-starts (~30–80s). The dashboard's API client uses generous timeouts (30s GET / 90s POST) so the RAG call plus a cold start don't fail. This is expected behavior for free-tier hosting.

---

## Security

- **Row Level Security** is enabled on all public Supabase tables, so the auto-generated anon Data API returns no rows; the application reaches the database only through its direct Postgres connection (whose role bypasses RLS). RLS is enabled at the DB layer via `ALTER TABLE … ENABLE ROW LEVEL SECURITY`.
- Secrets (`.env`, `airflow/.env`) are gitignored; AWS/DB credentials are supplied via environment variables, never committed.

---

## Deployment

### FastAPI → Render
Deployed at https://nfl-analytics-api-aku6.onrender.com — push to `main`; Render auto-deploys via the `render.yaml` blueprint. Set `OPENAI_API_KEY` in the Render environment for the `/ask` route.

### Streamlit Dashboard → Community Cloud
Deployed at https://nfl-analytics-crwjgsvzmwtrhl75mwpmtp.streamlit.app — push to `main`; Streamlit Cloud auto-deploys from GitHub.

### AWS batch pipeline
Provisioned per `infra/aws_setup.md` (free-tier RDS + S3). Runs locally via the Astro CLI; **remember the teardown steps** to avoid RDS charges.

---

## Resume Bullets

- Built an end-to-end NFL analytics pipeline ingesting 407K+ play-by-play records into PostgreSQL with idempotent upsert scripts and a normalized schema across 10 seasons (2016–2025)
- Trained and calibrated an XGBoost win-probability model (Brier 0.140, ROC-AUC 0.884), beating the nflfastR industry baseline by 8% on a held-out 2024 season, with isotonic calibration and features including rolling momentum and Vegas spread
- Deployed a FastAPI REST service with Pydantic validation serving real-time predictions, player rankings, and a **retrieval-augmented (RAG) Q&A endpoint** (OpenAI embeddings + `gpt-4o-mini` over a pgvector store), backed by a 5-page Streamlit dashboard
- Engineered a cloud batch pipeline orchestrated with **Apache Airflow** — ingest → S3 raw lake → **dbt** marts on **AWS RDS** → model retrain → RAG reindex — plus a **PySpark** feature-engineering port, migrating the warehouse from Supabase to RDS via a `COPY`-based ETL

---

## What's Next

- Keep-warm ping (cron → `/health`) to eliminate Render cold starts across all pages
- Move the live serving warehouse fully onto AWS RDS (currently Supabase-hosted; RDS powers the batch pipeline)
- Real-time ingestion via NFL data feeds during live games
- Player-level contextual features (injuries, recent form, matchup history)
- Meta-model ensembling nflfastR's `wp` as an additional feature
- Great Expectations for data-quality checks alongside the dbt tests
- Draft value model and trade analyzer page
```
