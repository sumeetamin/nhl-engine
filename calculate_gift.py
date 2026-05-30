"""
calculate_gift.py
=================
Fetches period-by-period scores from the NHL API for every game in
past_games.csv, then calculates:

  GIFT  — % of games with a goal in the 1st period (proxy for 1st-10-min)
  FP O/U — % of games where 1st period total goals > 1.5

Outputs gift_stats and fp_stats into daily_predictions.json structure
so the NHLMatchupCard can display them.

Also writes frontend/public/gift_stats.json as a standalone cache.

Run standalone:  python calculate_gift.py
Or import:       from calculate_gift import get_gift_stats, get_fp_stats
"""

import csv
import json
import os
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

ROOT         = Path(__file__).resolve().parent
CSV_PATH     = ROOT / "past_games.csv"
CACHE_PATH   = ROOT / "gift_cache.json"
OUTPUT_PATH  = ROOT / "frontend" / "public" / "gift_stats.json"
WINDOWS_PATH = Path(r"C:\Users\amins\OneDrive\Desktop\NHL\public") / "gift_stats.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept":     "application/json",
    "Referer":    "https://www.nhl.com",
}

# ── NHL team abbrev → ESPN team name fragment for schedule lookup ─────────────
ESPN_TEAM_MAP = {
    "ANA":"Anaheim",  "ARI":"Arizona",   "BOS":"Boston",    "BUF":"Buffalo",
    "CAR":"Carolina", "CBJ":"Columbus",  "CGY":"Calgary",   "CHI":"Chicago",
    "COL":"Colorado", "DAL":"Dallas",    "DET":"Detroit",   "EDM":"Edmonton",
    "FLA":"Florida",  "LAK":"LA Kings",  "MIN":"Minnesota", "MTL":"Montreal",
    "NJD":"New Jersey","NSH":"Nashville","NYI":"NY Islanders","NYR":"NY Rangers",
    "OTT":"Ottawa",   "PHI":"Philadelphia","PIT":"Pittsburgh","SEA":"Seattle",
    "SJS":"San Jose", "STL":"St. Louis", "TBL":"Tampa Bay", "TOR":"Toronto",
    "UTA":"Utah",     "VAN":"Vancouver", "VGK":"Vegas",     "WSH":"Washington",
    "WPG":"Winnipeg",
}


# ── Fetch period scores for a single game ─────────────────────────────────────
def fetch_period_scores_nhl(date_str: str, away: str, home: str) -> dict | None:
    """
    Try NHL API first: api-web.nhle.com/v1/score/{date}
    Returns {"p1_away": int, "p1_home": int, "p2_away": int, ...} or None.
    """
    url = f"https://api-web.nhle.com/v1/score/{date_str}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for game in data.get("games", []):
            at = game.get("awayTeam", {}).get("abbrev", "").upper()
            ht = game.get("homeTeam", {}).get("abbrev", "").upper()
            if at == away.upper() and ht == home.upper():
                state = game.get("gameState", "")
                if state not in ("OFF", "FINAL"):
                    return None
                periods = game.get("periodDescriptor", {})
                # Period scores are inside homeTeam/awayTeam
                away_periods = game.get("awayTeam", {}).get("periodGoals", [])
                home_periods = game.get("homeTeam", {}).get("periodGoals", [])
                if away_periods and home_periods:
                    return {
                        "p1_away": int(away_periods[0]) if len(away_periods) > 0 else 0,
                        "p1_home": int(home_periods[0]) if len(home_periods) > 0 else 0,
                        "p2_away": int(away_periods[1]) if len(away_periods) > 1 else 0,
                        "p2_home": int(home_periods[1]) if len(home_periods) > 1 else 0,
                        "p3_away": int(away_periods[2]) if len(away_periods) > 2 else 0,
                        "p3_home": int(home_periods[2]) if len(home_periods) > 2 else 0,
                    }
    except Exception as e:
        pass
    return None


def fetch_period_scores_espn(date_str: str, away: str, home: str) -> dict | None:
    """
    Fallback: ESPN scoreboard API.
    """
    espn_date = date_str.replace("-", "")
    url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={espn_date}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        away_frag = ESPN_TEAM_MAP.get(away.upper(), away)
        home_frag = ESPN_TEAM_MAP.get(home.upper(), home)

        for event in data.get("events", []):
            comp    = event.get("competitions", [{}])[0]
            status  = comp.get("status", {}).get("type", {}).get("name", "")
            if "final" not in status.lower():
                continue

            team_names = [c.get("team", {}).get("displayName", "") for c in comp.get("competitors", [])]
            if not any(away_frag.lower() in n.lower() for n in team_names):
                continue
            if not any(home_frag.lower() in n.lower() for n in team_names):
                continue

            # Extract linescores (period scores)
            periods_away = periods_home = []
            for competitor in comp.get("competitors", []):
                ls = [int(x.get("value", 0)) for x in competitor.get("linescores", [])]
                if away_frag.lower() in competitor.get("team", {}).get("displayName", "").lower():
                    periods_away = ls
                else:
                    periods_home = ls

            if periods_away and periods_home:
                return {
                    "p1_away": periods_away[0] if len(periods_away) > 0 else 0,
                    "p1_home": periods_home[0] if len(periods_home) > 0 else 0,
                    "p2_away": periods_away[1] if len(periods_away) > 1 else 0,
                    "p2_home": periods_home[1] if len(periods_home) > 1 else 0,
                    "p3_away": periods_away[2] if len(periods_away) > 2 else 0,
                    "p3_home": periods_home[2] if len(periods_home) > 2 else 0,
                }
    except Exception as e:
        pass
    return None


def fetch_period_scores(date_str: str, away: str, home: str) -> dict | None:
    """Try NHL API first, ESPN as fallback."""
    result = fetch_period_scores_nhl(date_str, away, home)
    if result:
        return result
    time.sleep(0.3)
    return fetch_period_scores_espn(date_str, away, home)


# ── Load / save cache ─────────────────────────────────────────────────────────
def load_cache() -> dict:
    if CACHE_PATH.exists():
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


# ── Calculate stats ───────────────────────────────────────────────────────────
def calculate_gift_stats(games_with_periods: list[dict]) -> dict:
    """
    games_with_periods: list of {date, away, home, winner, p1_away, p1_home, ...}

    For each team calculates:
      - gift_pct   : % of games where team's game had ANY 1st period goal
      - fp_ou_pct  : % of games where total 1st period goals > 1.5
      - home/away splits
      - L5 / L10 sub-rates
      - current GIFT streak
    """
    # Group by team
    team_games: dict[str, list] = defaultdict(list)

    for g in games_with_periods:
        away   = g["away"].upper()
        home   = g["home"].upper()
        p1_tot = g.get("p1_away", 0) + g.get("p1_home", 0)
        had_gift  = p1_tot > 0      # any 1st period goal
        fp_over   = p1_tot > 1      # first period over 1.5 goals
        is_home_a = False            # away team is playing away
        is_home_h = True             # home team is playing home

        for team, is_home in [(away, False), (home, True)]:
            team_games[team].append({
                "date":     g["date"],
                "is_home":  is_home,
                "had_gift": had_gift,
                "fp_over":  fp_over,
            })

    result: dict[str, dict] = {}

    for team, tg in team_games.items():
        # Sort newest first
        tg_sorted = sorted(tg, key=lambda x: x["date"], reverse=True)

        def pct_str(games):
            if not games:
                return "N/A"
            rate = sum(1 for g in games if g["had_gift"]) / len(games) * 100
            return f"{rate:.1f}%"

        def fp_pct_str(games):
            if not games:
                return "N/A"
            rate = sum(1 for g in games if g["fp_over"]) / len(games) * 100
            return f"{rate:.1f}%"

        def record_str(games, key="had_gift"):
            w = sum(1 for g in games if g[key])
            return f"{w}-{len(games)-w}"

        # GIFT streak (consecutive games with 1st period goal, from most recent)
        streak = 0
        for g in tg_sorted:
            if g["had_gift"]:
                streak += 1
            else:
                break

        home_games = [g for g in tg_sorted if g["is_home"]]
        away_games = [g for g in tg_sorted if not g["is_home"]]

        all_gift_pct    = pct_str(tg_sorted)
        pct_num         = float(all_gift_pct.replace("%","")) if all_gift_pct != "N/A" else 0

        result[team] = {
            "gift": {
                "pct_season":    all_gift_pct,
                "pct_l5":        pct_str(tg_sorted[:5]),
                "pct_l10":       pct_str(tg_sorted[:10]),
                "record_season": record_str(tg_sorted, "had_gift"),
                "streak":        streak,
                "home_pct":      pct_str(home_games) if home_games else "N/A",
                "away_pct":      pct_str(away_games) if away_games else "N/A",
                "scoring_rate":  all_gift_pct,
                "games":         len(tg_sorted),
            },
            "fp_ou": {
                "pct_season":    fp_pct_str(tg_sorted),
                "pct_l5":        fp_pct_str(tg_sorted[:5]),
                "pct_l10":       fp_pct_str(tg_sorted[:10]),
                "record_season": record_str(tg_sorted, "fp_over"),
                "over_games":    sum(1 for g in tg_sorted if g["fp_over"]),
                "home_pct":      fp_pct_str(home_games) if home_games else "N/A",
                "away_pct":      fp_pct_str(away_games) if away_games else "N/A",
            }
        }

    return result


# ── Public interface ──────────────────────────────────────────────────────────
def get_gift_stats(abbr: str, all_stats: dict) -> dict:
    return all_stats.get(abbr.upper(), {}).get("gift", {
        "pct_season": "N/A", "pct_l5": "N/A", "pct_l10": "N/A",
        "record_season": "N/A", "streak": 0,
        "home_pct": "N/A", "away_pct": "N/A", "scoring_rate": "N/A",
    })


def get_fp_stats(abbr: str, all_stats: dict) -> dict:
    return all_stats.get(abbr.upper(), {}).get("fp_ou", {
        "pct_season": "N/A", "record_season": "N/A",
        "over_games": 0, "home_pct": "N/A", "away_pct": "N/A",
    })


def build_all_gift_stats() -> dict:
    """
    Main entry point. Reads past_games.csv, fetches period scores,
    calculates GIFT stats, saves cache + output JSON.
    """
    print("\n🏒 Building GIFT stats from past_games.csv...")

    if not CSV_PATH.exists():
        print(f"  ⚠️  {CSV_PATH} not found — returning empty stats")
        return {}

    with open(CSV_PATH) as f:
        rows = list(csv.DictReader(f))

    cache = load_cache()
    enriched = []
    fetched  = 0
    skipped  = 0

    for row in rows:
        date = row["Date"]
        away = row["Away"].upper()
        home = row["Home"].upper()
        key  = f"{date}_{away}_{home}"

        if key in cache:
            period_data = cache[key]
            skipped += 1
        else:
            print(f"  📡 Fetching period scores: {away} @ {home} on {date}")
            period_data = fetch_period_scores(date, away, home)
            if period_data:
                cache[key] = period_data
                fetched += 1
            else:
                # Could not fetch — assume 0 goals in P1 (conservative)
                cache[key] = {"p1_away": 0, "p1_home": 0, "p2_away": 0,
                              "p2_home": 0, "p3_away": 0, "p3_home": 0,
                              "estimated": True}
                print(f"    ⚠️  Could not fetch — using 0 estimate")
            time.sleep(0.4)  # be polite

        enriched.append({
            "date":     date,
            "away":     away,
            "home":     home,
            "winner":   row.get("Actual_Winner", "").upper(),
            **cache[key],
        })

    save_cache(cache)
    print(f"  ✅ Fetched {fetched} new | Used {skipped} cached | Total {len(enriched)} games")

    all_stats = calculate_gift_stats(enriched)

    # Print summary
    print("\n  📊 GIFT Summary:")
    for team, stats in sorted(all_stats.items()):
        g = stats["gift"]
        print(f"    {team:4s}  GIFT={g['pct_season']:6s}  L10={g['pct_l10']:6s}  "
              f"Streak={g['streak']}  Games={g['games']}")

    # Save output files
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(all_stats, f, indent=2)
    print(f"\n  💾 Saved → {OUTPUT_PATH}")

    # Also save to Windows path if on Windows
    if os.name == "nt":
        try:
            WINDOWS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(WINDOWS_PATH, "w") as f:
                json.dump(all_stats, f, indent=2)
        except Exception:
            pass

    return all_stats


if __name__ == "__main__":
    stats = build_all_gift_stats()
    print(f"\nDone — {len(stats)} teams processed")
