"""NFL Analytics REST API — FastAPI entry point."""
import sys
from pathlib import Path

# Allow imports from project root (models/, features/)
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import games, leaderboard, players, predict

app = FastAPI(
    title="NFL Analytics API",
    description=(
        "Win probability predictions and player performance data "
        "for NFL games 2016–2024. Built with XGBoost + FastAPI."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict.router)
app.include_router(players.router)
app.include_router(games.router)
app.include_router(leaderboard.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "version": "1.0.0"}
