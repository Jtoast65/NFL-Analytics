-- Weekly player stats, regular season only (marts aggregate season totals).
select
    stat_id,
    player_id,
    season,
    week,
    season_type,
    team,
    completions,
    attempts,
    passing_yards,
    passing_tds,
    interceptions,
    carries,
    rushing_yards,
    rushing_tds,
    receptions,
    targets,
    receiving_yards,
    receiving_tds,
    fantasy_points,
    fantasy_points_ppr
from {{ source('raw', 'player_stats') }}
