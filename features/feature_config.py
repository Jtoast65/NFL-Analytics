"""Feature column definitions shared between build_features.py and model training."""

# Raw columns pulled from DB to build features
DB_COLS = [
    "play_id",
    "game_id",
    "play_idx",
    "season",
    "qtr",
    "down",
    "ydstogo",
    "yardline_100",
    "game_seconds_remaining",
    "score_differential",
    "posteam",
    "defteam",
    "posteam_timeouts_remaining",
    "defteam_timeouts_remaining",
    "is_home_possession",
    "nflfastr_wp",
    "drive",
    "touchdown",
    "play_type",
]

# Final feature columns fed to the model (order matters for joblib compatibility)
FEATURE_COLS = [
    "score_differential",
    "game_seconds_remaining",
    "down_1", "down_2", "down_3", "down_4",
    "ydstogo",
    "yardline_100",
    "is_home_possession",
    "posteam_timeouts_remaining",
    "defteam_timeouts_remaining",
    "qtr",
    "posteam_spread",
    "momentum_score",
]

# Columns written back to the plays table
PLAYS_UPDATE_COLS = ["momentum_score"]

MODEL_TARGET = "posteam_won"
