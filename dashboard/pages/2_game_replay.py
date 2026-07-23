"""Page 2: Historical Game Replay — animate WP curve play by play."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dashboard.utils import api_get

st.set_page_config(page_title="Game Replay", page_icon="🎬", layout="wide")
st.title("🎬 Historical Game Replay")
st.caption("Select any game and watch the win probability swing play by play.")

# ── Game selection ────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 2])
with col1:
    season = st.selectbox("Season", list(range(2025, 2015, -1)), index=0)
    week = st.selectbox("Week", list(range(1, 23)), index=0)

try:
    games = api_get("/games", params={"season": season, "week": week})
except Exception as e:
    st.error(f"Could not load games: {e}")
    st.stop()

if not games:
    st.warning("No games found for that week.")
    st.stop()

game_labels = {
    g["game_id"]: f"{g['away_team']} @ {g['home_team']}  "
                  f"({g['away_score']}–{g['home_score']})"
    for g in games
}
with col2:
    selected_id = st.selectbox("Game", list(game_labels.keys()), format_func=lambda k: game_labels[k])

# ── Load play-by-play WP data ─────────────────────────────────────────────────
try:
    data = api_get(f"/games/{selected_id}/win_probability")
except Exception as e:
    st.error(f"Could not load game data: {e}")
    st.stop()

plays = pd.DataFrame(data["plays"])
if plays.empty:
    st.warning("No play data available for this game.")
    st.stop()

home = data["home_team"]
away = data["away_team"]
home_score = data["home_score"]
away_score = data["away_score"]

# Convert possession-team WP → home-team WP for consistent plotting
plays["home_nflfastr_wp"] = plays.apply(
    lambda r: r["nflfastr_wp"] if r["posteam"] == home else (1 - r["nflfastr_wp"])
    if pd.notna(r["nflfastr_wp"]) else None, axis=1
)
plays["home_model_wp"] = plays.apply(
    lambda r: r["model_wp"] if r["posteam"] == home else (1 - r["model_wp"])
    if pd.notna(r["model_wp"]) else None, axis=1
)
plays["play_num"] = range(1, len(plays) + 1)

# Quarter boundaries for vertical lines
qtr_starts = plays.groupby("qtr")["play_num"].first().to_dict()

# ── Chart ─────────────────────────────────────────────────────────────────────
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=plays["play_num"], y=plays["home_nflfastr_wp"],
    mode="lines", name="nflfastR baseline",
    line=dict(color="#95a5a6", width=1.5, dash="dot"),
    hovertemplate="Play %{x}<br>nflfastR WP: %{y:.1%}<extra></extra>",
))

if plays["home_model_wp"].notna().any():
    fig.add_trace(go.Scatter(
        x=plays["play_num"], y=plays["home_model_wp"],
        mode="lines", name="Our XGBoost model",
        line=dict(color="#2980b9", width=2.5),
        hovertemplate="Play %{x}<br>Model WP: %{y:.1%}<extra></extra>",
    ))

# Quarter dividers
for qtr, play_n in qtr_starts.items():
    if qtr > 1:
        fig.add_vline(x=play_n, line_dash="dash", line_color="#bdc3c7", line_width=1)
        fig.add_annotation(x=play_n, y=1.02, text=f"Q{qtr}", showarrow=False,
                           yref="paper", font=dict(size=10, color="#7f8c8d"))

fig.add_hline(y=0.5, line_dash="dash", line_color="#e74c3c", line_width=1, opacity=0.5)

fig.update_layout(
    title=f"{away} @ {home}  ·  Final: {away} {away_score} – {home} {home_score}",
    xaxis_title="Play number",
    yaxis_title=f"{home} win probability",
    yaxis=dict(tickformat=".0%", range=[0, 1]),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=480,
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)

# ── Play-by-play table ────────────────────────────────────────────────────────
with st.expander("Show raw play-by-play data"):
    display_cols = ["play_idx", "qtr", "game_seconds_remaining",
                    "posteam", "play_type", "score_differential",
                    "nflfastr_wp", "model_wp"]
    st.dataframe(
        plays[[c for c in display_cols if c in plays.columns]],
        use_container_width=True,
        hide_index=True,
    )
