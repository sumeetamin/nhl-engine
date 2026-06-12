"""
GOALIE SCRAPER FIX (V5 GOALIE ENGINE)
=====================================
Replaces DailyFaceoff with a multi-tier fallback system.
  Primary  : NHL official API  (api-web.nhle.com)
  Secondary: RotowireHTML scrape (fallback)
  Tertiary : Season-stats leader from NHL API (fast O(1) fallback)
"""

import requests
import logging
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

NHL_API  = "https://api-web.nhle.com/v1"
HEADERS  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"}
TIMEOUT  = 12


# ─────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────

def scrape_goalies(teams: list[str] | None = None, date_str: str | None = None) -> dict:
    """
    Fetch probable/confirmed starting goalies for today's games.
    """
    date_str = date_str or _today_est()
    result   = {}

    # ── Strategy 1: NHL gamecenter landing (most reliable) ──────────────────
    try:
        result = _from_nhl_api(date_str, teams)
        if result:
            logger.info(f"[Goalies] NHL API: {len(result)} goalies — {list(result.keys())}")
            return result
    except Exception as e:
        logger.warning(f"[Goalies] NHL API failed: {e}")

    # ── Strategy 2: RotoWire lineup page ────────────────────────────────────
    try:
        result = _from_rotowire(teams)
        if result:
            logger.info(f"[Goalies] RotoWire: {len(result)} goalies — {list(result.keys())}")
            return result
    except Exception as e:
        logger.warning(f"[Goalies] RotoWire failed: {e}")

    # ── Strategy 3: Season stats leader per team (last resort) ──────────────
    if teams:
        try:
            result = _from_season_leaders(teams, date_str)
            if result:
                logger.info(f"[Goalies] Season-leader fallback: {len(result)} goalies")
                return result
        except Exception as e:
            logger.warning(f"[Goalies] Season leader fallback failed: {e}")

    logger.error("[Goalies] All sources exhausted — returning empty dict")
    return {}


# ─────────────────────────────────────────────
# STRATEGY 1 — NHL Official API
# ─────────────────────────────────────────────

def _from_nhl_api(date_str: str, teams: list | None) -> dict:
    sched_url = f"{NHL_API}/schedule/{date_str}"
    sched = requests.get(sched_url, headers=HEADERS, timeout=TIMEOUT).json()

    result = {}

    for week in sched.get("gameWeek", []):
        for game in week.get("games", []):
            home_abbr = game["homeTeam"]["abbrev"]
            away_abbr = game["awayTeam"]["abbrev"]

            if teams and not any(t in [home_abbr, away_abbr] for t in teams):
                continue

            game_id = game["id"]
            landing_url = f"{NHL_API}/gamecenter/{game_id}/landing"
            landing = requests.get(landing_url, headers=HEADERS, timeout=TIMEOUT).json()

            for side, abbr in [("homeTeam", home_abbr), ("awayTeam", away_abbr)]:
                if teams and abbr not in teams:
                    continue
                goalie = _extract_goalie_from_landing(landing, side, abbr)
                if goalie:
                    result[abbr] = goalie

    return result


def _extract_goalie_from_landing(landing: dict, side: str, abbr: str) -> dict | None:
    # ── 1. Boxscore (available during/after warmups or live) ───────────────
    try:
        boxscore = landing.get("boxscore", {}).get("playerByGameStats", {}).get(side, {})
        goalies = boxscore.get("goalies", [])
        if goalies:
            g = goalies[0] # The starter is almost always listed first
            return {
                "name":      _full_name(g),
                "confirmed": True,
                "svpct":     round(g.get("savePctg", 0), 3) if g.get("savePctg") else None,
                "gaa":       None, # Boxscore doesn't pass GAA usually
                "source":    "nhl_api_boxscore",
            }
    except Exception:
        pass

    # ── 2. Matchup Goalie Comparison (pre-game probable) ────────────────────
    try:
        comp = landing.get("matchup", {}).get("goalieComparison", {}).get(side, {})
        if comp and (comp.get("id") or comp.get("name")):
            return {
                "name":      _full_name(comp),
                "confirmed": False, # Usually probable unless marked otherwise
                "svpct":     round(comp.get("savePctg", 0), 3) if comp.get("savePctg") else None,
                "gaa":       round(comp.get("goalsAgainstAvg", 0), 2) if comp.get("goalsAgainstAvg") else None,
                "source":    "nhl_api_matchup",
            }
    except Exception:
        pass

    return None


# ─────────────────────────────────────────────
# STRATEGY 2 — RotoWire
# ─────────────────────────────────────────────

def _from_rotowire(teams: list | None) -> dict:
    url  = "https://www.rotowire.com/hockey/nhl-lineups.php"
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    soup = BeautifulSoup(resp.text, "html.parser")

    result = {}

    for game_div in soup.select(".lineup.is-nhl"):
        for team_box in game_div.select(".lineup__team"):
            abbr_elem = team_box.select_one(".lineup__abbr")
            if not abbr_elem:
                continue
            
            abbr = abbr_elem.get_text(strip=True)
            if teams and abbr not in teams:
                continue

            # Rotowire lists the goalie prominently at the top of the lineup box
            goalie_node = team_box.select_one(".lineup__player a")
            if goalie_node:
                name = goalie_node.get_text(strip=True)
                if name and name.lower() not in ("tbd", "?", ""):
                    
                    # Check if Rotowire marks them as confirmed (usually parent element has a specific class)
                    parent = goalie_node.find_parent()
                    is_confirmed = parent and "is-confirmed" in parent.get("class", [])

                    result[abbr] = {
                        "name":      name,
                        "confirmed": is_confirmed,
                        "svpct":     None,
                        "gaa":       None,
                        "source":    "rotowire",
                    }

    return result


# ─────────────────────────────────────────────
# STRATEGY 3 — Season Stats Leader
# ─────────────────────────────────────────────

def _from_season_leaders(teams: list, date_str: str) -> dict:
    result = {}

    for abbr in teams:
        try:
            # club-stats returns ALL player stats for the current season in ONE fast request
            stats_url = f"{NHL_API}/club-stats/{abbr}/now"
            resp = requests.get(stats_url, headers=HEADERS, timeout=TIMEOUT).json()

            goalies = resp.get("goalies", [])
            if not goalies:
                continue

            # Sort goalies by games played (descending)
            goalies_sorted = sorted(goalies, key=lambda x: x.get("gamesPlayed", 0), reverse=True)
            best = goalies_sorted[0]

            result[abbr] = {
                "name":      _full_name(best),
                "confirmed": False,
                "svpct":     best.get("savePercentage"),
                "gaa":       best.get("goalsAgainstAverage"),
                "source":    "season_leader_fallback",
            }
        except Exception as e:
            logger.warning(f"Failed to fetch club-stats for {abbr}: {e}")

    return result


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _full_name(player: dict) -> str:
    fn = player.get("firstName", "")
    ln = player.get("lastName", "")
    first = fn.get("default", fn) if isinstance(fn, dict) else fn
    last  = ln.get("default", ln) if isinstance(ln, dict) else ln
    
    # Handle direct 'name' key in some payloads
    if not first and not last:
        name_obj = player.get("name", "")
        return name_obj.get("default", name_obj) if isinstance(name_obj, dict) else str(name_obj)
        
    return f"{first} {last}".strip()


def _today_est() -> str:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    goalies = scrape_goalies(teams=["CAR", "VGK"])
    print("\n=== GOALIES ===")
    for team, data in goalies.items():
        print(f"  {team}: {data}")