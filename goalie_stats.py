"""Starting goalies' real save % for the game cards (display only).

The model still reads its own goalie table (get_goalie_stats in
run_pipeline.py); nothing here changes a prediction. This module only gives
each card the two starters with their actual numbers from the NHL's public
stats API: one call for this season and one for last season, covering every
goalie in the league.

THE COLOUR. Green means better than the league average, red worse, grey in
between or not enough shots to say. Early in a season a goalie has faced 150
shots and his save % carries about +/- .020 of pure noise, so a colour from
this season alone would flip with every start. The colour is therefore judged
on this season and last season together (shots-weighted), against the
league's average over the same two seasons, and a goalie with fewer than
MIN_SHOTS across both stays grey. The card still shows this season's number
as the headline, beside this season's league average.
"""
import unicodedata
from datetime import datetime

import requests

STATS_URL = "https://api.nhle.com/stats/rest/en/goalie/summary"
TIMEOUT = 15
MIN_SHOTS = 300      # across both seasons, before a colour is given
BAND = 0.007         # how far from the league average counts as better or worse


def season_id(day: datetime) -> str:
    """'20262027' for any date from September 2026 to August 2027."""
    start = day.year if day.month >= 9 else day.year - 1
    return f"{start}{start + 1}"


def previous_season_id(season: str) -> str:
    start = int(season[:4]) - 1
    return f"{start}{start + 1}"


def _key(name: str) -> str:
    """Name for matching across sources: no accents, no case, no punctuation."""
    plain = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return "".join(ch for ch in plain.lower() if ch.isalnum())


def fetch_season(season: str) -> list[dict]:
    """Every goalie's regular-season line for one season; [] if the call fails."""
    try:
        response = requests.get(
            STATS_URL,
            params={"limit": -1, "cayenneExp": f"seasonId={season} and gameTypeId=2"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.json().get("data", [])
    except (requests.RequestException, ValueError) as exc:
        print(f"⚠️ Goalie stats {season}: {exc}")
        return []


def build_table(current: list[dict], previous: list[dict]) -> dict:
    """Index both seasons by name, with the league averages the card needs.

    `league_sv_pct` is this season's, for the card to show beside the number
    (last season's too on opening nights, under 2,000 shots). `league_both`
    is over both seasons: the yardstick for the colour, which is judged on
    both seasons too. Early-season scoring moves this season's average, and a
    two-season number set against it would flatter nearly everyone.
    """
    def index(rows):
        return {_key(r.get("goalieFullName", "")): r for r in rows if r.get("goalieFullName")}

    def totals(rows):
        return (sum(r.get("saves") or 0 for r in rows), sum(r.get("shotsAgainst") or 0 for r in rows))

    cur_saves, cur_shots = totals(current)
    prev_saves, prev_shots = totals(previous)
    both = (cur_saves + prev_saves) / (cur_shots + prev_shots) if cur_shots + prev_shots else None
    league = cur_saves / cur_shots if cur_shots >= 2000 else both
    return {"current": index(current), "previous": index(previous),
            "league_sv_pct": league, "league_both": both}


def fetch_table(day: datetime) -> dict:
    season = season_id(day)
    return build_table(fetch_season(season), fetch_season(previous_season_id(season)))


def rating(saves: int, shots: int, league: float | None) -> str:
    """'good', 'poor' or 'average' against the league; 'average' too when unsure."""
    if not league or shots < MIN_SHOTS:
        return "average"
    sv = saves / shots
    if sv >= league + BAND:
        return "good"
    if sv <= league - BAND:
        return "poor"
    return "average"


def goalie_card(name: str, status: str, table: dict | None) -> dict:
    """What a game card shows for one starter."""
    card = {"name": name or "TBD", "status": status, "sv_pct": None, "gp": 0,
            "gaa": None, "prev_sv_pct": None, "rating": "average"}
    if not table or not name or name == "TBD":
        return card
    cur = table["current"].get(_key(name))
    prev = table["previous"].get(_key(name))
    if cur:
        card.update(sv_pct=round(cur.get("savePct") or 0, 3) or None,
                    gp=cur.get("gamesPlayed") or 0,
                    gaa=round(cur["goalsAgainstAverage"], 2) if cur.get("goalsAgainstAverage") else None)
    if prev and prev.get("savePct"):
        card["prev_sv_pct"] = round(prev["savePct"], 3)
    saves = sum((r or {}).get("saves") or 0 for r in (cur, prev))
    shots = sum((r or {}).get("shotsAgainst") or 0 for r in (cur, prev))
    card["rating"] = rating(saves, shots, table.get("league_both"))
    return card
