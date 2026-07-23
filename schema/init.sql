-- NFL Analytics Schema
-- Run via: psql $DATABASE_URL -f schema/init.sql
-- All tables use ON CONFLICT for idempotent upserts in ingestion scripts.

CREATE TABLE IF NOT EXISTS games (
    game_id         VARCHAR(20) PRIMARY KEY,   -- e.g. "2023_01_ATL_CAR"
    season          SMALLINT    NOT NULL,
    week            SMALLINT    NOT NULL,
    game_type       VARCHAR(10) NOT NULL,       -- REG, WC, DIV, CON, SB
    home_team       VARCHAR(5)  NOT NULL,
    away_team       VARCHAR(5)  NOT NULL,
    home_score      SMALLINT,
    away_score      SMALLINT,
    result          SMALLINT,                   -- home_score - away_score
    spread_line     REAL,                       -- Vegas spread (negative = home favored)
    total_line      REAL,                       -- Vegas over/under
    game_date       DATE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS plays (
    play_id                     BIGSERIAL PRIMARY KEY,
    game_id                     VARCHAR(20) NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
    play_idx                    INTEGER     NOT NULL,   -- nflfastR play_id within game
    qtr                         SMALLINT,
    down                        SMALLINT,
    ydstogo                     SMALLINT,
    yardline_100                SMALLINT,               -- yards to opponent end zone
    game_seconds_remaining      INTEGER,
    score_differential          SMALLINT,               -- posteam score - defteam score
    posteam                     VARCHAR(5),
    defteam                     VARCHAR(5),
    posteam_timeouts_remaining  SMALLINT,
    defteam_timeouts_remaining  SMALLINT,
    is_home_possession          BOOLEAN,
    nflfastr_wp                 REAL,                   -- nflfastR baseline win prob
    play_type                   VARCHAR(30),
    yards_gained                SMALLINT,
    touchdown                   BOOLEAN,
    drive                       SMALLINT,               -- drive number within game
    -- engineered in Phase 3:
    momentum_score              REAL,
    -- model output written in Phase 4:
    model_wp                    REAL,
    UNIQUE (game_id, play_idx)
);

CREATE INDEX IF NOT EXISTS idx_plays_game_id ON plays (game_id);
CREATE INDEX IF NOT EXISTS idx_plays_posteam ON plays (posteam);

CREATE TABLE IF NOT EXISTS players (
    player_id       VARCHAR(20) PRIMARY KEY,    -- gsis_id from nflfastR
    display_name    VARCHAR(200),
    position        VARCHAR(10),
    team            VARCHAR(5),
    birth_date      DATE,
    college         TEXT,           -- some players list multiple schools
    entry_year      SMALLINT,
    status          VARCHAR(20),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS player_stats (
    stat_id             BIGSERIAL PRIMARY KEY,
    player_id           VARCHAR(20) NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    season              SMALLINT    NOT NULL,
    week                SMALLINT    NOT NULL,
    season_type         VARCHAR(10) NOT NULL DEFAULT 'REG',
    team                VARCHAR(5),
    -- passing
    completions         SMALLINT,
    attempts            SMALLINT,
    passing_yards       SMALLINT,
    passing_tds         SMALLINT,
    interceptions       SMALLINT,
    sacks               SMALLINT,
    -- rushing
    carries             SMALLINT,
    rushing_yards       SMALLINT,
    rushing_tds         SMALLINT,
    -- receiving
    receptions          SMALLINT,
    targets             SMALLINT,
    receiving_yards     SMALLINT,
    receiving_tds       SMALLINT,
    -- fantasy
    fantasy_points      REAL,
    fantasy_points_ppr  REAL,
    UNIQUE (player_id, season, week, season_type)
);

CREATE INDEX IF NOT EXISTS idx_player_stats_player ON player_stats (player_id);
CREATE INDEX IF NOT EXISTS idx_player_stats_season ON player_stats (season, week);

CREATE TABLE IF NOT EXISTS predictions (
    pred_id         BIGSERIAL PRIMARY KEY,
    game_id         VARCHAR(20) NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
    play_idx        INTEGER     NOT NULL,
    model_version   VARCHAR(50) NOT NULL,
    predicted_wp    REAL        NOT NULL,
    actual_outcome  SMALLINT,               -- 1 = posteam won, 0 = lost
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (game_id, play_idx, model_version)
);
