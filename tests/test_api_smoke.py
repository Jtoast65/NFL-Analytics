"""Smoke tests for all API endpoints. Run with: pytest tests/ -v"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

VALID_GAME_STATE = {
    "score_differential": 0,
    "game_seconds_remaining": 1800,
    "down": 1,
    "ydstogo": 10,
    "yardline_100": 75,
    "is_home_possession": True,
    "posteam_timeouts_remaining": 3,
    "defteam_timeouts_remaining": 3,
    "qtr": 2,
    "spread_line": 0.0,
    "momentum_score": 0.0,
}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_openapi_docs():
    r = client.get("/docs")
    assert r.status_code == 200


def test_predict_valid_payload():
    r = client.post("/predict", json=VALID_GAME_STATE)
    assert r.status_code == 200
    body = r.json()
    assert "win_probability" in body
    assert 0.0 <= body["win_probability"] <= 1.0
    assert body["model_version"] == "v1"


def test_predict_midgame_tied_is_near_50():
    r = client.post("/predict", json=VALID_GAME_STATE)
    wp = r.json()["win_probability"]
    assert 0.35 <= wp <= 0.65, f"Expected ~0.50 for tied midgame, got {wp}"


def test_predict_missing_required_field():
    bad = {k: v for k, v in VALID_GAME_STATE.items() if k != "down"}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_list_games_default_season():
    r = client.get("/games?season=2024&week=1")
    assert r.status_code == 200
    games = r.json()
    assert len(games) > 0
    assert "game_id" in games[0]
    assert "home_team" in games[0]


def test_game_wp_valid_id():
    r = client.get("/games/2024_01_ARI_BUF/win_probability")
    assert r.status_code == 200
    body = r.json()
    assert body["game_id"] == "2024_01_ARI_BUF"
    assert len(body["plays"]) > 0
    assert "nflfastr_wp" in body["plays"][0]


def test_game_wp_invalid_id():
    r = client.get("/games/FAKE_GAME_ID/win_probability")
    assert r.status_code == 404


def test_player_stats_valid_id():
    r = client.get("/players/00-0034796/stats")  # Lamar Jackson
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] == "Lamar Jackson"
    assert len(body["weekly_stats"]) > 0


def test_player_stats_invalid_id():
    r = client.get("/players/FAKE-PLAYER-ID/stats")
    assert r.status_code == 404


def test_leaderboard_default():
    r = client.get("/leaderboard")
    assert r.status_code == 200
    entries = r.json()
    assert len(entries) > 0
    assert entries[0]["rank"] == 1
    assert entries[0]["fantasy_points_ppr"] >= entries[1]["fantasy_points_ppr"]


def test_leaderboard_position_filter():
    r = client.get("/leaderboard?position=QB&season=2024&limit=5")
    assert r.status_code == 200
    entries = r.json()
    assert all(e["position"] == "QB" for e in entries)
    assert len(entries) <= 5
