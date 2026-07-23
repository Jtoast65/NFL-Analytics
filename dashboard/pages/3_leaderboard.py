"""Page 3: Player Leaderboard — filterable, sortable stat rankings."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import streamlit as st
from dashboard.utils import api_get

st.set_page_config(page_title="Player Leaderboard", page_icon="🏆", layout="wide")
st.title("🏆 Player Leaderboard")
st.caption("Season totals ranked by fantasy points (PPR). Filter by position, team, or season.")

# ── Filters ───────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
with col1:
    season = st.selectbox("Season", list(range(2025, 2015, -1)), index=0)
with col2:
    position = st.selectbox("Position", ["All", "QB", "RB", "WR", "TE", "K"], index=0)
with col3:
    team_input = st.text_input("Team (e.g. KC, SF)", value="").strip().upper()
with col4:
    limit = st.slider("Show top N players", 10, 100, 25, 5)

params = {"season": season, "limit": limit}
if position != "All":
    params["position"] = position
if team_input:
    params["team"] = team_input

try:
    data = api_get("/leaderboard", params=params)
except Exception as e:
    st.error(f"Could not load leaderboard: {e}")
    st.stop()

if not data:
    st.warning("No players found with those filters.")
    st.stop()

df = pd.DataFrame(data)

# ── Display columns by position ───────────────────────────────────────────────
BASE_COLS = ["rank", "display_name", "position", "team", "games_played", "fantasy_points_ppr"]
PASS_COLS = ["passing_yards", "passing_tds"]
RUSH_COLS = ["rushing_yards", "rushing_tds"]
RECV_COLS = ["receptions", "receiving_yards", "receiving_tds"]

if position == "QB":
    show_cols = BASE_COLS + PASS_COLS + RUSH_COLS
elif position == "RB":
    show_cols = BASE_COLS + RUSH_COLS + RECV_COLS
elif position in ("WR", "TE"):
    show_cols = BASE_COLS + RECV_COLS + RUSH_COLS
else:
    show_cols = BASE_COLS + PASS_COLS + RUSH_COLS + RECV_COLS

show_cols = [c for c in show_cols if c in df.columns]

# ── Highlight top 3 ───────────────────────────────────────────────────────────
def highlight_top3(row):
    if row["rank"] == 1:
        return ["background-color: #ffd700; font-weight: bold"] * len(row)
    if row["rank"] == 2:
        return ["background-color: #c0c0c0"] * len(row)
    if row["rank"] == 3:
        return ["background-color: #cd7f32"] * len(row)
    return [""] * len(row)

styled = (
    df[show_cols]
    .rename(columns={
        "display_name": "Player", "fantasy_points_ppr": "Fantasy Pts (PPR)",
        "games_played": "GP", "passing_yards": "Pass Yds", "passing_tds": "Pass TD",
        "rushing_yards": "Rush Yds", "rushing_tds": "Rush TD",
        "receiving_yards": "Rec Yds", "receiving_tds": "Rec TD",
    })
    .style.apply(highlight_top3, axis=1)
    .format({
        "Fantasy Pts (PPR)": "{:.1f}",
        "Pass Yds": "{:,.0f}", "Rush Yds": "{:,.0f}", "Rec Yds": "{:,.0f}",
    }, na_rep="—")
)

st.dataframe(styled, use_container_width=True, hide_index=True, height=600)

st.caption(f"Showing top {len(df)} players · {season} regular season · ranked by PPR fantasy points")
