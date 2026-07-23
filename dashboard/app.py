"""NFL Analytics Dashboard — entry point."""
import streamlit as st

st.set_page_config(
    page_title="NFL Analytics",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏈 NFL Win Probability & Player Analytics")
st.markdown(
    """
    **An end-to-end ML pipeline** — 435K play-by-play records, XGBoost win probability model,
    and a self-built REST API.

    Use the sidebar to navigate between pages:

    | Page | Description |
    |---|---|
    | **Live Simulator** | Input any game state → instant win probability |
    | **Game Replay** | Watch any 2024 game's WP curve animate play by play |
    | **Player Leaderboard** | Ranked fantasy stats filtered by position, season, team |
    | **Model Performance** | Calibration curves, feature importance, Brier score comparison |

    ---
    Built by Joey Sandoval · [GitHub](https://github.com) · [API Docs](http://localhost:8000/docs)
    """
)
