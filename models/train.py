"""
Phase 4: Train and calibrate XGBoost win probability model.

Split: train 2016-2022 | val 2023 | test 2024
Outputs: models/saved/wp_model_v1.joblib  +  models/saved/eval_metrics.json

Usage: python models/train.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from xgboost import XGBClassifier

from features.feature_config import FEATURE_COLS, MODEL_TARGET
from models.calibrated_model import CalibratedXGB

FEATURES_PATH = Path("data/processed/features.parquet")
MODEL_PATH = Path("models/saved/wp_model_v1.joblib")
METRICS_PATH = Path("models/saved/eval_metrics.json")

TRAIN_SEASONS = list(range(2016, 2023))   # 2016–2022
VAL_SEASONS = [2023]
TEST_SEASONS = [2024]


def load_splits():
    print("Loading feature matrix...")
    df = pd.read_parquet(FEATURES_PATH)
    print(f"  {len(df):,} plays loaded")

    train = df[df["season"].isin(TRAIN_SEASONS)]
    val   = df[df["season"].isin(VAL_SEASONS)]
    test  = df[df["season"].isin(TEST_SEASONS)]

    print(f"  Train: {len(train):,} | Val: {len(val):,} | Test: {len(test):,}")
    return (
        train[FEATURE_COLS].values, train[MODEL_TARGET].values,
        val[FEATURE_COLS].values,   val[MODEL_TARGET].values,
        test[FEATURE_COLS].values,  test[MODEL_TARGET].values,
        val[["nflfastr_wp"]].values.ravel(),
        test[["nflfastr_wp"]].values.ravel(),
    )



def train(X_train, y_train, X_val, y_val):
    print("\nTraining XGBoost base model...")
    base = XGBClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        early_stopping_rounds=20,
        random_state=42,
        n_jobs=-1,
    )
    base.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=50)
    print(f"  Best iteration: {base.best_iteration}")

    print("Calibrating with isotonic regression on validation set...")
    raw_val_probs = base.predict_proba(X_val)[:, 1]
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(raw_val_probs, y_val)

    return CalibratedXGB(base, iso)


def evaluate(model, X, y, nflfastr_wp, split_name):
    probs = model.predict_proba(X)[:, 1]

    brier_ours   = brier_score_loss(y, probs)
    brier_nfl    = brier_score_loss(y, nflfastr_wp)
    ll_ours      = log_loss(y, probs)
    ll_nfl       = log_loss(y, nflfastr_wp)
    auc          = roc_auc_score(y, probs)

    print(f"\n--- {split_name} Evaluation ---")
    print(f"  Brier score  — ours: {brier_ours:.4f}  |  nflfastR: {brier_nfl:.4f}")
    print(f"  Log loss     — ours: {ll_ours:.4f}  |  nflfastR: {ll_nfl:.4f}")
    print(f"  ROC-AUC      — ours: {auc:.4f}")

    return {
        "split": split_name,
        "brier_ours": round(brier_ours, 5),
        "brier_nflfastr": round(brier_nfl, 5),
        "log_loss_ours": round(ll_ours, 5),
        "log_loss_nflfastr": round(ll_nfl, 5),
        "roc_auc": round(auc, 5),
        "n_plays": int(len(y)),
    }


def save_calibration_data(model, X_test, y_test, nflfastr_wp):
    """Save calibration curve data so the dashboard can render it without recomputing."""
    probs = model.predict_proba(X_test)[:, 1]

    frac_pos_ours, mean_pred_ours = calibration_curve(y_test, probs, n_bins=20)
    frac_pos_nfl,  mean_pred_nfl  = calibration_curve(y_test, nflfastr_wp, n_bins=20)

    cal_data = {
        "ours": {"mean_pred": mean_pred_ours.tolist(), "frac_pos": frac_pos_ours.tolist()},
        "nflfastr": {"mean_pred": mean_pred_nfl.tolist(), "frac_pos": frac_pos_nfl.tolist()},
    }
    cal_path = Path("models/saved/calibration_data.json")
    cal_path.write_text(json.dumps(cal_data, indent=2))
    print(f"  Calibration data saved → {cal_path}")


def save_feature_importance(model, feature_names):
    """Save feature importance via XGBoost's built-in gain scores."""
    scores = model.get_booster().get_score(importance_type="gain")
    importance = {feature_names[int(k[1:])]: round(v, 2) for k, v in scores.items()}
    importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    fi_path = Path("models/saved/feature_importance.json")
    fi_path.write_text(json.dumps(importance, indent=2))
    print(f"  Feature importance saved → {fi_path}")


def run():
    (X_tr, y_tr, X_val, y_val, X_te, y_te,
     nfl_val, nfl_te) = load_splits()

    model = train(X_tr, y_tr, X_val, y_val)

    metrics_val  = evaluate(model, X_val, y_val, nfl_val, "Validation (2023)")
    metrics_test = evaluate(model, X_te,  y_te,  nfl_te,  "Test (2024)")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"\nModel saved → {MODEL_PATH}")

    METRICS_PATH.write_text(json.dumps([metrics_val, metrics_test], indent=2))
    print(f"Metrics saved → {METRICS_PATH}")

    save_calibration_data(model, X_te, y_te, nfl_te)
    save_feature_importance(model, FEATURE_COLS)

    print("\nTraining complete.")


if __name__ == "__main__":
    run()
