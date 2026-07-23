# NFL Win Probability & Player Performance Pipeline

End-to-end ML engineering portfolio project: play-by-play data ingestion → PostgreSQL → XGBoost win probability model → FastAPI → Streamlit dashboard.

**API docs:** https://nfl-analytics-api-aku6.onrender.com/docs

---

## Architecture

```
nflreadpy (nflfastR data)
        │
        ▼  idempotent ingestion scripts
┌───────────────────────────────────┐
│  PostgreSQL (Supabase)            │
│  games · plays · players          │
│  player_stats · predictions       │
└───────┬───────────────────────────┘
        │
        ▼  feature engineering
  XGBoost + Isotonic Calibration
  (Brier score 0.140 vs 0.157 nflfastR baseline on 2024 holdout)
        │
        ▼  joblib
┌───────────────────────────────────┐
│  FastAPI  (Render)                │
│  POST /predict                    │
│  GET  /games/{id}/win_probability │
│  GET  /leaderboard                │
│  GET  /players/{id}/stats         │
└───────┬───────────────────────────┘
        │  HTTP
        ▼
┌───────────────────────────────────┐
│  Streamlit  (Community Cloud)     │
│  1 · Live Simulator               │
│  2 · Game Replay                  │
│  3 · Player Leaderboard           │
│  4 · Model Performance            │
└───────────────────────────────────┘
```

---

## Features

- **407K+ plays** ingested from 2016–2025 NFL seasons via [nflreadpy](https://github.com/nflreadpy/nflreadpy)
- **14-feature XGBoost model** with isotonic calibration: score differential, time, field position, timeouts, down/distance, Vegas spread, and rolling momentum
- **Beats nflfastR baseline** by 8% on Brier score (0.140 vs 0.157) on 2024 test season
- **Real-time win probability simulator** — adjust any game state parameter and see WP update instantly
- **Historical game replay** — animate the WP curve for any game since 2016
- **Player leaderboard** with PPR fantasy point rankings filterable by position, team, and season

---

## Local Setup

**Prerequisites:** Python 3.11+, PostgreSQL client (`psql`)

```bash
git clone https://github.com/YOUR_USERNAME/nfl-analytics.git
cd nfl-analytics

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — add your Supabase DATABASE_URL
```

**Run with Docker Compose:**
```bash
docker-compose up
# API: http://localhost:8000/docs
# Dashboard: http://localhost:8501
```

**Or run manually:**
```bash
# Terminal 1 — API
make serve

# Terminal 2 — Dashboard
make dashboard
```

---

## Reproducing the Model

```bash
# 1. Ingest all data (takes ~10 min on first run, downloads are cached)
make ingest

# 2. Build feature matrix and run batch predictions
python features/build_features.py
python models/batch_predict.py

# 3. Train model (train 2016–2022, val 2023, test 2024)
make train

# 4. Run smoke tests
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

# Game replay
GET https://nfl-analytics-api-aku6.onrender.com/games/{game_id}/win_probability

# Player stats
GET https://nfl-analytics-api-aku6.onrender.com/players/{player_id}/stats

# Leaderboard
GET https://nfl-analytics-api-aku6.onrender.com/leaderboard?season=2024&position=QB&limit=25
```

> **Note:** The Render free tier spins down after 15 minutes of inactivity. The first request after idle takes ~30 seconds to cold-start — this is expected behavior for free-tier hosting.

---

## Deployment

### FastAPI → Render

Deployed at https://nfl-analytics-api-aku6.onrender.com

To redeploy: push to `main` — Render auto-deploys via the `render.yaml` blueprint.

### Streamlit Dashboard → Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Connect GitHub repo → main file: `dashboard/app.py`
3. Add secrets (Settings → Secrets):
   ```toml
   DATABASE_URL = "postgresql://..."
   API_URL = "https://your-app.onrender.com"
   MODEL_VERSION = "v1"
   ```

---

## Resume Bullets

- Built end-to-end NFL analytics pipeline ingesting 407K+ play-by-play records into PostgreSQL with idempotent upsert scripts and a normalized 5-table schema across 10 seasons (2016–2025)
- Trained and calibrated XGBoost win probability model (Brier score 0.140, ROC-AUC 0.884) beating the nflfastR industry baseline by 8% on a held-out 2024 test season, with isotonic regression calibration and feature engineering including rolling momentum and Vegas spread
- Designed and deployed a FastAPI REST service with Pydantic validation serving real-time ML predictions and player performance rankings, backed by a Streamlit dashboard with live game simulation and historical play-by-play replay

---

## What's Next

- Real-time ingestion via NFL data feeds during live games
- Player-level contextual features (injuries, recent form, matchup history)
- Meta-model ensembling nflfastR's `wp` as an additional feature
- dbt transformation layer + Great Expectations for data quality checks
- Draft value model and trade analyzer page
