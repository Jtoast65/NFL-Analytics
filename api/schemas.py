"""Pydantic request/response models for all API endpoints."""
from typing import Optional
from pydantic import BaseModel, Field


# ── /predict ────────────────────────────────────────────────────────────────

class GameState(BaseModel):
    score_differential: int = Field(..., description="Possession team score minus opponent score")
    game_seconds_remaining: int = Field(..., ge=0, le=3600)
    down: int = Field(..., ge=1, le=4)
    ydstogo: int = Field(..., ge=1, le=99)
    yardline_100: int = Field(..., ge=1, le=99, description="Yards to opponent end zone")
    is_home_possession: bool
    posteam_timeouts_remaining: int = Field(default=3, ge=0, le=3)
    defteam_timeouts_remaining: int = Field(default=3, ge=0, le=3)
    qtr: int = Field(..., ge=1, le=5)
    spread_line: float = Field(default=0.0, description="Pre-game Vegas spread (negative = home favored)")
    momentum_score: float = Field(default=0.0, description="Points scored in last 2 possessions")

    model_config = {"json_schema_extra": {"example": {
        "score_differential": -3, "game_seconds_remaining": 420,
        "down": 3, "ydstogo": 7, "yardline_100": 65,
        "is_home_possession": True, "posteam_timeouts_remaining": 2,
        "defteam_timeouts_remaining": 1, "qtr": 4,
        "spread_line": -3.5, "momentum_score": 7.0,
    }}}


class PredictionResponse(BaseModel):
    win_probability: float
    model_version: str


# ── /players ─────────────────────────────────────────────────────────────────

class WeeklyStatRow(BaseModel):
    season: int
    week: int
    season_type: str
    team: Optional[str]
    completions: Optional[int]
    attempts: Optional[int]
    passing_yards: Optional[int]
    passing_tds: Optional[int]
    interceptions: Optional[int]
    carries: Optional[int]
    rushing_yards: Optional[int]
    rushing_tds: Optional[int]
    receptions: Optional[int]
    targets: Optional[int]
    receiving_yards: Optional[int]
    receiving_tds: Optional[int]
    fantasy_points: Optional[float]
    fantasy_points_ppr: Optional[float]


class PlayerStatsResponse(BaseModel):
    player_id: str
    display_name: Optional[str]
    position: Optional[str]
    team: Optional[str]
    weekly_stats: list[WeeklyStatRow]


# ── /games ───────────────────────────────────────────────────────────────────

class PlayWP(BaseModel):
    play_idx: int
    qtr: Optional[int]
    game_seconds_remaining: Optional[int]
    score_differential: Optional[int]
    posteam: Optional[str]
    play_type: Optional[str]
    nflfastr_wp: Optional[float]
    model_wp: Optional[float]


class GameWPResponse(BaseModel):
    game_id: str
    home_team: str
    away_team: str
    home_score: Optional[int]
    away_score: Optional[int]
    plays: list[PlayWP]


class GameSummary(BaseModel):
    game_id: str
    season: int
    week: int
    home_team: str
    away_team: str
    home_score: Optional[int]
    away_score: Optional[int]
    game_date: Optional[str]


# ── /leaderboard ─────────────────────────────────────────────────────────────

class LeaderboardEntry(BaseModel):
    rank: int
    player_id: str
    display_name: Optional[str]
    position: Optional[str]
    team: Optional[str]
    season: int
    fantasy_points_ppr: Optional[float]
    passing_yards: Optional[int]
    passing_tds: Optional[int]
    rushing_yards: Optional[int]
    rushing_tds: Optional[int]
    receiving_yards: Optional[int]
    receiving_tds: Optional[int]
    receptions: Optional[int]
    games_played: int
