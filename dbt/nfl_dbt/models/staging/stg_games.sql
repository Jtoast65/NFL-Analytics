-- Light cleaning of raw games: typed columns, derived winner.
select
    game_id,
    season,
    week,
    game_type,
    home_team,
    away_team,
    home_score,
    away_score,
    result,
    case
        when home_score > away_score then home_team
        when away_score > home_score then away_team
    end as winning_team,
    spread_line,
    total_line,
    game_date
from {{ source('raw', 'games') }}
where home_score is not null
  and away_score is not null
