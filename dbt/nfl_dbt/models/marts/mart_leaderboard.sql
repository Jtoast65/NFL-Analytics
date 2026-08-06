-- Player-season rows ranked by PPR fantasy points, overall and within position.
-- Ports the ranking logic from api/routers/leaderboard.py into the warehouse.
select
    player_id,
    display_name,
    position,
    season,
    team,
    fantasy_points_ppr,
    passing_yards,
    passing_tds,
    rushing_yards,
    rushing_tds,
    receiving_yards,
    receiving_tds,
    receptions,
    games_played,
    rank() over (
        partition by season
        order by fantasy_points_ppr desc nulls last
    ) as ppr_rank_overall,
    rank() over (
        partition by season, position
        order by fantasy_points_ppr desc nulls last
    ) as ppr_rank_position
from {{ ref('mart_player_season') }}
where fantasy_points_ppr is not null
