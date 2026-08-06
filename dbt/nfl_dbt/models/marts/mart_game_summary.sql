-- One row per game: final result plus win-probability summary from the model.
-- home_wp is expressed from the home team's perspective on every play.
with home_wp as (
    select
        p.game_id,
        p.play_idx,
        case when p.posteam = g.home_team then p.model_wp
             else 1 - p.model_wp end as home_wp
    from {{ ref('stg_plays') }} p
    join {{ ref('stg_games') }} g on p.game_id = g.game_id
    where p.model_wp is not null
),
wp as (
    select
        game_id,
        (array_agg(home_wp order by play_idx))[1] as opening_home_wp,
        max(home_wp) as max_home_wp,
        min(home_wp) as min_home_wp
    from home_wp
    group by game_id
)
select
    g.game_id,
    g.season,
    g.week,
    g.game_type,
    g.home_team,
    g.away_team,
    g.home_score,
    g.away_score,
    g.winning_team,
    g.spread_line,
    wp.opening_home_wp,
    wp.max_home_wp,
    wp.min_home_wp
from {{ ref('stg_games') }} g
left join wp on g.game_id = wp.game_id
