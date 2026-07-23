import os
from fastapi import APIRouter
from api.schemas import GameState, PredictionResponse
from models.predict import predict_wp

router = APIRouter(tags=["predictions"])
MODEL_VERSION = os.getenv("MODEL_VERSION", "v1")


@router.post("/predict", response_model=PredictionResponse)
def predict(state: GameState):
    """Return win probability for the possession team given the current game state."""
    wp = predict_wp(state.model_dump())
    return PredictionResponse(win_probability=round(wp, 4), model_version=MODEL_VERSION)
