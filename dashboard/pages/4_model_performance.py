"""Page 4: Model Performance — calibration curve, feature importance, metrics."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="Model Performance", page_icon="📊", layout="wide")
st.title("📊 Model Performance")
st.caption("Calibration curves, feature importance, and Brier score comparison vs nflfastR baseline.")

SAVED = Path("models/saved")

# ── Load artifacts ────────────────────────────────────────────────────────────
try:
    cal_data = json.loads((SAVED / "calibration_data.json").read_text())
    fi_data  = json.loads((SAVED / "feature_importance.json").read_text())
    metrics  = json.loads((SAVED / "eval_metrics.json").read_text())
except FileNotFoundError as e:
    st.error(f"Model artifacts not found ({e}). Run `python models/train.py` first.")
    st.stop()

# ── Metrics table ─────────────────────────────────────────────────────────────
st.subheader("Evaluation Metrics vs nflfastR Baseline")
rows = []
for m in metrics:
    rows.append({
        "Split": m["split"],
        "Plays": f"{m['n_plays']:,}",
        "Brier — Ours": f"{m['brier_ours']:.4f}",
        "Brier — nflfastR": f"{m['brier_nflfastr']:.4f}",
        "Improvement": f"{(m['brier_nflfastr'] - m['brier_ours']):.4f}",
        "Log Loss — Ours": f"{m['log_loss_ours']:.4f}",
        "ROC-AUC": f"{m['roc_auc']:.4f}",
    })
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
st.caption("Brier score: lower is better. Improvement = nflfastR − ours (positive means we win).")

st.markdown("---")

# ── Two charts side by side ───────────────────────────────────────────────────
col_cal, col_fi = st.columns(2)

with col_cal:
    st.subheader("Calibration Curve (Test set — 2024)")
    fig_cal = go.Figure()

    fig_cal.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1],
        mode="lines", name="Perfect calibration",
        line=dict(color="#bdc3c7", dash="dash"),
    ))
    fig_cal.add_trace(go.Scatter(
        x=cal_data["nflfastr"]["mean_pred"],
        y=cal_data["nflfastr"]["frac_pos"],
        mode="lines+markers", name="nflfastR baseline",
        line=dict(color="#95a5a6"), marker=dict(size=6),
    ))
    fig_cal.add_trace(go.Scatter(
        x=cal_data["ours"]["mean_pred"],
        y=cal_data["ours"]["frac_pos"],
        mode="lines+markers", name="Our XGBoost model",
        line=dict(color="#2980b9", width=2.5), marker=dict(size=7),
    ))
    fig_cal.update_layout(
        xaxis_title="Mean predicted probability",
        yaxis_title="Fraction of positives (actual win rate)",
        xaxis=dict(tickformat=".0%"),
        yaxis=dict(tickformat=".0%"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=420,
    )
    st.plotly_chart(fig_cal, use_container_width=True)
    st.caption("A perfectly calibrated model follows the dashed diagonal. "
               "Closer = more trustworthy probabilities.")

with col_fi:
    st.subheader("Feature Importance (XGBoost gain)")
    fi_sorted = sorted(fi_data.items(), key=lambda x: x[1])
    features, scores = zip(*fi_sorted)

    FEATURE_LABELS = {
        "score_differential": "Score differential",
        "game_seconds_remaining": "Seconds remaining",
        "down_1": "Down 1", "down_2": "Down 2", "down_3": "Down 3", "down_4": "Down 4",
        "ydstogo": "Yards to go",
        "yardline_100": "Yards to end zone",
        "is_home_possession": "Home possession",
        "posteam_timeouts_remaining": "Offense timeouts",
        "defteam_timeouts_remaining": "Defense timeouts",
        "qtr": "Quarter",
        "spread_line": "Vegas spread",
        "momentum_score": "Momentum (last 2 drives)",
    }
    labels = [FEATURE_LABELS.get(f, f) for f in features]

    fig_fi = go.Figure(go.Bar(
        x=list(scores), y=labels,
        orientation="h",
        marker_color="#2980b9",
    ))
    fig_fi.update_layout(
        xaxis_title="Gain (importance score)",
        height=420,
        margin=dict(l=160),
    )
    st.plotly_chart(fig_fi, use_container_width=True)
    st.caption("Gain = average improvement in loss function from splits on this feature.")

# ── Model details ─────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Model Details")
st.markdown("""
| | |
|---|---|
| **Algorithm** | XGBoost classifier + Isotonic calibration |
| **Training data** | 2016–2022 seasons (282,906 plays) |
| **Validation** | 2023 season (41,917 plays) |
| **Test** | 2024 season (41,469 plays) |
| **Features** | 14 (score, time, field position, timeouts, down/distance, Vegas spread, momentum) |
| **Target** | Did the possession team win the game? (binary) |
| **Early stopping** | 20 rounds on validation log loss |
""")
