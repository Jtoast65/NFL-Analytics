"""Page 1: Live Game Simulator — real-time win probability from user inputs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import plotly.graph_objects as go
import streamlit as st
from dashboard.utils import api_post

st.set_page_config(page_title="Live Simulator", page_icon="📡", layout="wide")
st.title("📡 Live Win Probability Simulator")
st.caption("Adjust any game state parameter and see win probability update instantly.")

# ── Controls ─────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Game Situation")
    score_diff = st.slider("Score differential (possession team − opponent)", -35, 35, 0, 1)
    qtr = st.selectbox("Quarter", [1, 2, 3, 4, 5], index=2, format_func=lambda q: f"Q{q}" if q <= 4 else "OT")
    minutes = st.slider("Minutes remaining in game", 0, 60, 30, 1)
    game_seconds_remaining = minutes * 60
    is_home = st.checkbox("Home team currently has the ball", value=True)
    spread_line = st.slider("Pre-game spread (negative = home favored)", -20.0, 20.0, 0.0, 0.5)
    st.caption("Spread is the pre-game betting line — negative means home team is favored. "
               "Win probability updates automatically based on which team has possession.")

with col_right:
    st.subheader("Drive Situation")
    down = st.selectbox("Down", [1, 2, 3, 4], index=0)
    ydstogo = st.slider("Yards to go", 1, 30, 10, 1)
    yardline_100 = st.slider("Yards to end zone", 1, 99, 75, 1)
    posteam_to = st.slider("Possession team timeouts", 0, 3, 3)
    defteam_to = st.slider("Defense timeouts", 0, 3, 3)
    momentum = st.slider("Momentum (pts in last 2 possessions)", 0, 21, 0, 1)

# ── One-hot encode down for the model ────────────────────────────────────────
payload = {
    "score_differential": score_diff,
    "game_seconds_remaining": game_seconds_remaining,
    "down": down,
    "ydstogo": ydstogo,
    "yardline_100": yardline_100,
    "is_home_possession": is_home,
    "posteam_timeouts_remaining": posteam_to,
    "defteam_timeouts_remaining": defteam_to,
    "qtr": qtr,
    "spread_line": spread_line,
    "momentum_score": float(momentum),
}

# ── Call API ──────────────────────────────────────────────────────────────────
try:
    result = api_post("/predict", payload)
    wp = result["win_probability"]
    model_ver = result["model_version"]
except Exception as e:
    st.error(f"API error: {e}")
    st.stop()

# ── Gauge chart ───────────────────────────────────────────────────────────────
pct = round(wp * 100, 1)
color = "#2ecc71" if wp >= 0.5 else "#e74c3c"

fig = go.Figure(go.Indicator(
    mode="gauge+number",
    value=pct,
    number={"suffix": "%", "font": {"size": 52}},
    title={"text": f"{'Home' if is_home else 'Away'} Win Probability", "font": {"size": 20}},
    gauge={
        "axis": {"range": [0, 100], "tickwidth": 1},
        "bar": {"color": color},
        "steps": [
            {"range": [0, 30], "color": "#fadbd8"},
            {"range": [30, 70], "color": "#fdfefe"},
            {"range": [70, 100], "color": "#d5f5e3"},
        ],
        "threshold": {"line": {"color": "black", "width": 3}, "value": 50},
    },
))
fig.update_layout(height=340, margin=dict(t=60, b=0))
st.plotly_chart(fig, use_container_width=True)

# ── Context ───────────────────────────────────────────────────────────────────
st.caption(f"Model: XGBoost + Isotonic Calibration · version {model_ver}")

st.markdown("---")
st.markdown("**How to read this:** Win probability for the team currently with possession. "
            "50% = coin flip. Values above 80% indicate a strong favorite to win from this game state.")
