from fastapi import APIRouter, Depends, Query
from api.db import get_conn
from api.schemas import LeaderboardEntry

router = APIRouter(tags=["leaderboard"])

VALID_POSITIONS = {"QB", "RB", "WR", "TE", "K"}


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
def get_leaderboard(
    season: int = Query(default=2024),
    position: str | None = Query(default=None, description="QB, RB, WR, TE, K"),
    team: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    conn=Depends(get_conn),
):
    """
    Top players ranked by total season fantasy points (PPR).
    Aggregates all regular-season weeks for the given season.
    """
    where_clauses = ["ps.season_type = 'REG'", "ps.season = %s"]
    params: list = [season]

    if position:
        where_clauses.append("p.position = %s")
        params.append(position.upper())
    if team:
        where_clauses.append("ps.team = %s")
        params.append(team.upper())

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT
            p.player_id,
            p.display_name,
            p.position,
            ps.team,
            ps.season,
            SUM(ps.fantasy_points_ppr)      AS fantasy_points_ppr,
            SUM(ps.passing_yards)           AS passing_yards,
            SUM(ps.passing_tds)             AS passing_tds,
            SUM(ps.rushing_yards)           AS rushing_yards,
            SUM(ps.rushing_tds)             AS rushing_tds,
            SUM(ps.receiving_yards)         AS receiving_yards,
            SUM(ps.receiving_tds)           AS receiving_tds,
            SUM(ps.receptions)              AS receptions,
            COUNT(*)                        AS games_played
        FROM player_stats ps
        JOIN players p ON ps.player_id = p.player_id
        WHERE {where_sql}
        GROUP BY p.player_id, p.display_name, p.position, ps.team, ps.season
        HAVING SUM(ps.fantasy_points_ppr) IS NOT NULL
        ORDER BY fantasy_points_ppr DESC NULLS LAST
        LIMIT %s
    """
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()

    return [
        LeaderboardEntry(rank=i + 1, **dict(zip(cols, row)))
        for i, row in enumerate(rows)
    ]
