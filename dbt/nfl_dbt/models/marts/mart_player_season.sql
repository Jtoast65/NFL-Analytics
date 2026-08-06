-- One row per (player, season): regular-season totals joined to player bio.
-- Reused by the leaderboard mart and the RAG document generator.
with stats as (
    select
        player_id,
        season,
        mode() within group (order by team) as team,
        sum(completions)        as completions,
        sum(attempts)           as attempts,
        sum(passing_yards)      as passing_yards,
        sum(passing_tds)        as passing_tds,
        sum(interceptions)      as interceptions,
        sum(carries)            as carries,
        sum(rushing_yards)      as rushing_yards,
        sum(rushing_tds)        as rushing_tds,
        sum(receptions)         as receptions,
        sum(targets)            as targets,
        sum(receiving_yards)    as receiving_yards,
        sum(receiving_tds)      as receiving_tds,
        sum(fantasy_points_ppr) as fantasy_points_ppr,
        count(*)                as games_played
    from {{ ref('stg_player_stats') }}
    where season_type = 'REG'
    group by player_id, season
)
select
    s.player_id,
    p.display_name,
    p.position,
    s.season,
    s.team,
    s.completions,
    s.attempts,
    case when s.attempts > 0
         then round(100.0 * s.completions / s.attempts, 1) end as completion_pct,
    s.passing_yards,
    s.passing_tds,
    s.interceptions,
    s.carries,
    s.rushing_yards,
    s.rushing_tds,
    s.receptions,
    s.targets,
    s.receiving_yards,
    s.receiving_tds,
    s.fantasy_points_ppr,
    s.games_played
from stats s
join {{ ref('stg_players') }} p on s.player_id = p.player_id
