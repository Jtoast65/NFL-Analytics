-- Player roster, deduplicated by player_id.
select
    player_id,
    display_name,
    position,
    team,
    college,
    entry_year,
    status
from {{ source('raw', 'players') }}
