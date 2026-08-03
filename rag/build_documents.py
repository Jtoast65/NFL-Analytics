"""
Generate natural-language documents from the NFL database for the RAG layer.

The retrieval pipeline is classic RAG (embed docs → cosine top-k → prompt), so a
document can only answer a question if the answer text lives inside it. That means
ranked facts must be baked into the documents — a player-season doc explicitly states
"1,921 rushing yards (2nd among RBs, 3rd overall)" so a top-k lookup surfaces the
answer to "who had the most rushing yards in 2024?".

Three document types are produced:
  - player_season : one per (player, season) with totals + ranks (offense, PPR >= 5)
  - game_recap    : one per game with final score + win-probability summary
  - leaderboard   : top-10 snapshots per (season, category)

Usage: python rag/build_documents.py     # prints counts + sample docs
Consumed by rag/embed_store.py, which embeds and upserts into the `documents` table.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.environ["DATABASE_URL"]

# Offensive skill positions — the ones fantasy/leaderboard questions care about.
SKILL_POSITIONS = ("QB", "RB", "WR", "TE", "K", "FB")
MIN_PPR = 5          # drop marginal player-seasons
MIN_QB_ATTEMPTS = 100  # completion-rate qualifier


def _conn():
    return psycopg2.connect(DB_URL)


def _ordinal(n) -> str:
    if n is None:
        return "unranked"
    n = int(n)
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _i(v) -> int:
    return int(v) if v is not None else 0


# ---------------------------------------------------------------------------
# Player-season documents
# ---------------------------------------------------------------------------

PLAYER_SEASON_SQL = f"""
WITH agg AS (
    SELECT
        ps.player_id,
        p.display_name,
        p.position,
        ps.season,
        MODE() WITHIN GROUP (ORDER BY ps.team)      AS team,
        SUM(ps.completions)         AS completions,
        SUM(ps.attempts)            AS attempts,
        SUM(ps.passing_yards)       AS passing_yards,
        SUM(ps.passing_tds)         AS passing_tds,
        SUM(ps.interceptions)       AS interceptions,
        SUM(ps.carries)             AS carries,
        SUM(ps.rushing_yards)       AS rushing_yards,
        SUM(ps.rushing_tds)         AS rushing_tds,
        SUM(ps.receptions)          AS receptions,
        SUM(ps.targets)             AS targets,
        SUM(ps.receiving_yards)     AS receiving_yards,
        SUM(ps.receiving_tds)       AS receiving_tds,
        SUM(ps.fantasy_points_ppr)  AS fantasy_points_ppr,
        COUNT(*)                    AS games_played
    FROM player_stats ps
    JOIN players p ON ps.player_id = p.player_id
    WHERE ps.season_type = 'REG'
      AND p.position IN {SKILL_POSITIONS}
    GROUP BY ps.player_id, p.display_name, p.position, ps.season
    HAVING SUM(ps.fantasy_points_ppr) >= {MIN_PPR}
)
SELECT *,
    RANK() OVER (PARTITION BY season ORDER BY rushing_yards DESC NULLS LAST)              AS rush_yds_rank_all,
    RANK() OVER (PARTITION BY season, position ORDER BY rushing_yards DESC NULLS LAST)    AS rush_yds_rank_pos,
    RANK() OVER (PARTITION BY season ORDER BY passing_yards DESC NULLS LAST)              AS pass_yds_rank_all,
    RANK() OVER (PARTITION BY season, position ORDER BY passing_yards DESC NULLS LAST)    AS pass_yds_rank_pos,
    RANK() OVER (PARTITION BY season ORDER BY receiving_yards DESC NULLS LAST)            AS rec_yds_rank_all,
    RANK() OVER (PARTITION BY season, position ORDER BY receiving_yards DESC NULLS LAST)  AS rec_yds_rank_pos,
    RANK() OVER (PARTITION BY season ORDER BY fantasy_points_ppr DESC NULLS LAST)         AS ppr_rank_all,
    RANK() OVER (PARTITION BY season, position ORDER BY fantasy_points_ppr DESC NULLS LAST) AS ppr_rank_pos,
    CASE WHEN attempts >= {MIN_QB_ATTEMPTS}
         THEN RANK() OVER (
            PARTITION BY season
            ORDER BY (CASE WHEN attempts >= {MIN_QB_ATTEMPTS}
                           THEN completions::float / NULLIF(attempts, 0) END) DESC NULLS LAST)
    END AS comp_pct_rank
FROM agg
"""


def player_season_documents(conn) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(PLAYER_SEASON_SQL)
        rows = cur.fetchall()

    docs = []
    for r in rows:
        pos = r["position"]
        parts = [f"In the {r['season']} NFL regular season, {r['display_name']} "
                 f"({pos}, {r['team']}) played {_i(r['games_played'])} games."]

        # Passing (QBs and anyone who threw)
        if _i(r["attempts"]) > 0:
            line = (f"Passing: {_i(r['passing_yards'])} yards "
                    f"({_ordinal(r['pass_yds_rank_all'])} overall, "
                    f"{_ordinal(r['pass_yds_rank_pos'])} among {pos}s), "
                    f"{_i(r['passing_tds'])} touchdowns, {_i(r['interceptions'])} interceptions, "
                    f"{_i(r['completions'])}/{_i(r['attempts'])} completions")
            if r["attempts"] and r["attempts"] >= MIN_QB_ATTEMPTS:
                pct = 100.0 * _i(r["completions"]) / _i(r["attempts"])
                rank = f", {_ordinal(r['comp_pct_rank'])} in completion rate" if r["comp_pct_rank"] else ""
                line += f" for a {pct:.1f}% completion rate{rank}"
            parts.append(line + ".")

        # Rushing
        if _i(r["carries"]) > 0:
            parts.append(
                f"Rushing: {_i(r['rushing_yards'])} yards "
                f"({_ordinal(r['rush_yds_rank_all'])} overall, "
                f"{_ordinal(r['rush_yds_rank_pos'])} among {pos}s), "
                f"{_i(r['rushing_tds'])} touchdowns on {_i(r['carries'])} carries."
            )

        # Receiving
        if _i(r["targets"]) > 0 or _i(r["receptions"]) > 0:
            parts.append(
                f"Receiving: {_i(r['receptions'])} receptions for {_i(r['receiving_yards'])} yards "
                f"({_ordinal(r['rec_yds_rank_all'])} overall, "
                f"{_ordinal(r['rec_yds_rank_pos'])} among {pos}s), "
                f"{_i(r['receiving_tds'])} touchdowns on {_i(r['targets'])} targets."
            )

        parts.append(
            f"Fantasy: {r['fantasy_points_ppr']:.1f} PPR points "
            f"({_ordinal(r['ppr_rank_all'])} overall, {_ordinal(r['ppr_rank_pos'])} among {pos}s)."
        )

        docs.append({
            "doc_type": "player_season",
            "ref_id": f"{r['player_id']}:{r['season']}",
            "content": " ".join(parts),
            "metadata": {
                "player_id": r["player_id"], "name": r["display_name"],
                "position": pos, "team": r["team"], "season": int(r["season"]),
            },
        })
    return docs


# ---------------------------------------------------------------------------
# Game recap documents
# ---------------------------------------------------------------------------

GAME_RECAP_SQL = """
WITH hp AS (
    SELECT
        p.game_id,
        p.play_idx,
        CASE WHEN p.posteam = g.home_team THEN p.model_wp ELSE 1 - p.model_wp END AS home_wp
    FROM plays p
    JOIN games g ON p.game_id = g.game_id
    WHERE p.model_wp IS NOT NULL
),
wp AS (
    SELECT
        game_id,
        (ARRAY_AGG(home_wp ORDER BY play_idx))[1] AS opening_home_wp,
        MAX(home_wp) AS max_home_wp,
        MIN(home_wp) AS min_home_wp
    FROM hp
    GROUP BY game_id
)
SELECT
    g.game_id, g.season, g.week, g.game_type, g.game_date,
    g.home_team, g.away_team, g.home_score, g.away_score, g.result,
    wp.opening_home_wp, wp.max_home_wp, wp.min_home_wp
FROM games g
LEFT JOIN wp ON g.game_id = wp.game_id
WHERE g.home_score IS NOT NULL AND g.away_score IS NOT NULL
"""

ROUND_LABEL = {"WC": "Wild Card round", "DIV": "Divisional round",
               "CON": "Conference Championship", "SB": "Super Bowl"}

# Full team names so questions phrased with the nickname ("Chiefs") match the docs.
TEAM_NAMES = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
    "JAC": "Jacksonville Jaguars", "KC": "Kansas City Chiefs", "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams", "LA": "Los Angeles Rams", "LV": "Las Vegas Raiders",
    "OAK": "Oakland Raiders", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
    "SD": "San Diego Chargers", "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers",
    "STL": "St. Louis Rams", "TB": "Tampa Bay Buccaneers", "TEN": "Tennessee Titans",
    "WAS": "Washington", "WSH": "Washington",
}


def _team(abbr: str) -> str:
    return TEAM_NAMES.get(abbr, abbr)


def game_recap_documents(conn) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(GAME_RECAP_SQL)
        rows = cur.fetchall()

    docs = []
    for r in rows:
        home, away = _team(r["home_team"]), _team(r["away_team"])
        hs, as_ = _i(r["home_score"]), _i(r["away_score"])
        when = (ROUND_LABEL.get(r["game_type"], f"Week {r['week']}")
                + f" of the {r['season']} NFL season")
        date = f" (played {r['game_date']})" if r["game_date"] else ""

        if hs > as_:
            outcome = f"The {home} beat the {away} {hs}-{as_} at home"
        elif as_ > hs:
            outcome = f"The {away} beat the {home} {as_}-{hs} on the road"
        else:
            outcome = f"The {home} and {away} tied {hs}-{as_}"

        # Lead with season + week + both team names so exact-game queries retrieve well.
        parts = [f"{r['season']} season, {when}{date}: {away} at {home}. {outcome}."]

        if r["opening_home_wp"] is not None:
            parts.append(
                f"Pregame, the win-probability model gave the {home} a "
                f"{100 * r['opening_home_wp']:.0f}% chance to win. "
                f"Over the game the {home} win probability peaked at "
                f"{100 * r['max_home_wp']:.0f}% and bottomed out at "
                f"{100 * r['min_home_wp']:.0f}% (the inverse for the {away})."
            )

        docs.append({
            "doc_type": "game_recap",
            "ref_id": r["game_id"],
            "content": " ".join(parts),
            "metadata": {
                "game_id": r["game_id"], "season": int(r["season"]),
                "week": int(r["week"]), "home_team": home, "away_team": away,
            },
        })
    return docs


# ---------------------------------------------------------------------------
# Leaderboard snapshot documents
# ---------------------------------------------------------------------------

# (label, stat column, optional position filter, min-qualifier column/threshold)
LEADERBOARD_CATEGORIES = [
    ("rushing yards",       "rushing_yards",      None, None),
    ("passing yards",       "passing_yards",      None, None),
    ("receiving yards",     "receiving_yards",    None, None),
    ("passing touchdowns",  "passing_tds",        None, None),
    ("PPR fantasy points",  "fantasy_points_ppr", None, None),
]


def leaderboard_documents(conn) -> list[dict]:
    docs = []
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT DISTINCT season FROM player_stats WHERE season_type='REG' ORDER BY season")
        seasons = [row["season"] for row in cur.fetchall()]

        for season in seasons:
            for label, col, _pos, _q in LEADERBOARD_CATEGORIES:
                cur.execute(f"""
                    SELECT p.display_name, p.position,
                           MODE() WITHIN GROUP (ORDER BY ps.team) AS team,
                           SUM(ps.{col}) AS total
                    FROM player_stats ps
                    JOIN players p ON ps.player_id = p.player_id
                    WHERE ps.season_type = 'REG' AND ps.season = %s
                    GROUP BY p.player_id, p.display_name, p.position
                    HAVING SUM(ps.{col}) IS NOT NULL AND SUM(ps.{col}) > 0
                    ORDER BY total DESC
                    LIMIT 10
                """, (season,))
                top = cur.fetchall()
                if not top:
                    continue
                is_float = col == "fantasy_points_ppr"
                lines = ", ".join(
                    f"{i+1}. {t['display_name']} ({t['team']}) "
                    f"{t['total']:.1f}" if is_float else
                    f"{i+1}. {t['display_name']} ({t['team']}) {_i(t['total'])}"
                    for i, t in enumerate(top)
                )
                content = f"{season} NFL regular-season leaders in {label}: {lines}."
                docs.append({
                    "doc_type": "leaderboard",
                    "ref_id": f"{season}:{col}",
                    "content": content,
                    "metadata": {"season": int(season), "category": col},
                })

            # QB completion rate (min attempts qualifier)
            cur.execute(f"""
                SELECT p.display_name,
                       MODE() WITHIN GROUP (ORDER BY ps.team) AS team,
                       SUM(ps.completions) AS comp, SUM(ps.attempts) AS att
                FROM player_stats ps
                JOIN players p ON ps.player_id = p.player_id
                WHERE ps.season_type = 'REG' AND ps.season = %s AND p.position = 'QB'
                GROUP BY p.player_id, p.display_name
                HAVING SUM(ps.attempts) >= {MIN_QB_ATTEMPTS}
                ORDER BY SUM(ps.completions)::float / NULLIF(SUM(ps.attempts), 0) DESC
                LIMIT 10
            """, (season,))
            qbs = cur.fetchall()
            if qbs:
                lines = ", ".join(
                    f"{i+1}. {q['display_name']} ({q['team']}) "
                    f"{100*_i(q['comp'])/_i(q['att']):.1f}%"
                    for i, q in enumerate(qbs)
                )
                docs.append({
                    "doc_type": "leaderboard",
                    "ref_id": f"{season}:completion_pct",
                    "content": (f"{season} NFL regular-season leaders in QB completion rate "
                                f"(min {MIN_QB_ATTEMPTS} attempts): {lines}."),
                    "metadata": {"season": int(season), "category": "completion_pct"},
                })
    return docs


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate_documents() -> list[dict]:
    conn = _conn()
    try:
        docs = (player_season_documents(conn)
                + game_recap_documents(conn)
                + leaderboard_documents(conn))
    finally:
        conn.close()
    return docs


def run() -> None:
    conn = _conn()
    try:
        ps = player_season_documents(conn)
        gr = game_recap_documents(conn)
        lb = leaderboard_documents(conn)
    finally:
        conn.close()

    print(f"player_season : {len(ps):,}")
    print(f"game_recap    : {len(gr):,}")
    print(f"leaderboard   : {len(lb):,}")
    print(f"TOTAL         : {len(ps) + len(gr) + len(lb):,}\n")

    print("── sample player_season ──")
    print(next(d["content"] for d in ps if "1st overall" in d["content"]), "\n")
    print("── sample game_recap ──")
    print(gr[0]["content"], "\n")
    print("── sample leaderboard ──")
    print(next(d["content"] for d in lb if d["ref_id"].endswith("rushing_yards")))


if __name__ == "__main__":
    run()
