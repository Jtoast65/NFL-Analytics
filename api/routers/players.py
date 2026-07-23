from fastapi import APIRouter, Depends, HTTPException
from api.db import get_conn
from api.schemas import PlayerStatsResponse, WeeklyStatRow

router = APIRouter(tags=["players"])


@router.get("/players/{player_id}/stats", response_model=PlayerStatsResponse)
def get_player_stats(player_id: str, conn=Depends(get_conn)):
    """Return player metadata and full weekly stat history."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT player_id, display_name, position, team FROM players WHERE player_id = %s",
            (player_id,),
        )
        player = cur.fetchone()
        if not player:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

        cur.execute(
            """
            SELECT season, week, season_type, team,
                   completions, attempts, passing_yards, passing_tds, interceptions,
                   carries, rushing_yards, rushing_tds,
                   receptions, targets, receiving_yards, receiving_tds,
                   fantasy_points, fantasy_points_ppr
            FROM player_stats
            WHERE player_id = %s
            ORDER BY season DESC, week DESC
            """,
            (player_id,),
        )
        cols = [d[0] for d in cur.description]
        rows = [WeeklyStatRow(**dict(zip(cols, row))) for row in cur.fetchall()]

    return PlayerStatsResponse(
        player_id=player[0],
        display_name=player[1],
        position=player[2],
        team=player[3],
        weekly_stats=rows,
    )
