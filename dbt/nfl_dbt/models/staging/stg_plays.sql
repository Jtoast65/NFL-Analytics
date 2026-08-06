-- Plays narrowed to the columns marts/analytics use.
select
    play_id,
    game_id,
    play_idx,
    qtr,
    down,
    ydstogo,
    yardline_100,
    game_seconds_remaining,
    score_differential,
    posteam,
    defteam,
    is_home_possession,
    nflfastr_wp,
    model_wp,
    play_type,
    touchdown,
    drive
from {{ source('raw', 'plays') }}
