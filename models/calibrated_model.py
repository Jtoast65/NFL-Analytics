"""CalibratedXGB lives here so joblib can always unpickle it regardless of entry point."""
import numpy as np
from sklearn.isotonic import IsotonicRegression
from xgboost import XGBClassifier


class CalibratedXGB:
    """XGBoost + isotonic calibration. sklearn 1.9 compatible."""

    def __init__(self, xgb_model: XGBClassifier, iso: IsotonicRegression):
        self.xgb_model = xgb_model
        self.iso = iso

    def predict_proba(self, X):
        raw = self.xgb_model.predict_proba(X)[:, 1]
        calibrated = self.iso.predict(raw)
        return np.column_stack([1 - calibrated, calibrated])

    def get_booster(self):
        return self.xgb_model.get_booster()
