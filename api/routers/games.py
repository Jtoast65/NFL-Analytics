from fastapi import APIRouter, Depends, HTTPException, Query
from api.db import get_conn
from api.schemas import GameWPResponse, GameSummary, PlayWP

router = APIRouter(tags=["games"])


@router.get("/games", response_model=list[GameSummary])
def list_games(
    season: int = Query(default=2024),
    week: int | None = Query(default=None),
    conn=Depends(get_conn),
):
    """List games for a given season (optionally filtered by week)."""
    sql = """
        SELECT game_id, season, week, home_team, away_team,
               home_score, away_score, game_date::text
        FROM games
        WHERE season = %s
    """
    params = [season]
    if week is not None:
        sql += " AND week = %s"
        params.append(week)
    sql += " ORDER BY week, game_id"

    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [GameSummary(**dict(zip(cols, row))) for row in cur.fetchall()]


@router.get("/games/{game_id}/win_probability", response_model=GameWPResponse)
def get_game_wp(game_id: str, conn=Depends(get_conn)):
    """Return play-by-play win probability curve for a single game."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT game_id, home_team, away_team, home_score, away_score FROM games WHERE game_id = %s",
            (game_id,),
        )
        game = cur.fetchone()
        if not game:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

        cur.execute(
            """
            SELECT play_idx, qtr, game_seconds_remaining, score_differential,
                   posteam, play_type, nflfastr_wp, model_wp
            FROM plays
            WHERE game_id = %s AND play_type IS NOT NULL
            ORDER BY play_idx
            """,
            (game_id,),
        )
        cols = [d[0] for d in cur.description]
        plays = [PlayWP(**dict(zip(cols, row))) for row in cur.fetchall()]

    return GameWPResponse(
        game_id=game[0],
        home_team=game[1],
        away_team=game[2],
        home_score=game[3],
        away_score=game[4],
        plays=plays,
    )
