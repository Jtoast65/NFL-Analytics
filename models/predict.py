"""Inference helper — loads the saved model and returns win probability."""
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import joblib
import numpy as np

from features.feature_config import FEATURE_COLS

MODEL_PATH = Path("models/saved/wp_model_v1.joblib")


@lru_cache(maxsize=1)
def _load_model():
    from models.calibrated_model import CalibratedXGB  # noqa: F401 — needed for joblib unpickling
    return joblib.load(MODEL_PATH)


def predict_wp(game_state: dict) -> float:
    """
    Accept a game state dict with keys matching FEATURE_COLS.
    Returns win probability for the possession team (float 0–1).
    """
    model = _load_model()
    state = dict(game_state)
    # API callers use the standard Vegas convention: negative = home favored.
    # Training data (nflfastR) uses the opposite: positive = home favored.
    # Negate to convert, then assign relative to the possession side.
    spread_line = float(state.get("spread_line", 0) or 0)
    is_home = int(bool(state.get("is_home_possession", 0)))
    spread_nflfastr = -spread_line
    state["posteam_spread"] = spread_nflfastr if is_home else -spread_nflfastr

    # One-hot encode down from the integer field (GameState sends down: int)
    down = int(state.get("down", 1))
    for d in [1, 2, 3, 4]:
        state[f"down_{d}"] = 1 if down == d else 0
    row = np.array([[state.get(f, 0) for f in FEATURE_COLS]])
    return float(model.predict_proba(row)[0, 1])
