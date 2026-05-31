"""
calculate_gift.py — Real GIFT + First Period Stats via NHL API
=============================================================
GIFT  = % of games with a goal in the first 10 minutes (play-by-play)
FP O/U = % of games where 1st period total goals > 1.5 (boxscore)

Both are calculated per team for Season / L5 / L10 with Home/Away splits.
Results are cached in gift_cache.json so repeat runs are instant.

Standalone:  python calculate_gift.py CAR MTL
Import:      from calculate_gift import build_gift_stats_for_teams
"""

import json, os, time, sys, requests
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).resolve().parent
CACHE_FILE  = SCRIPT_DIR / "gift_cache.json"
OUTPUT_FILE = SCRIPT_DIR / "frontend" / "public" / "gift_stats.json"

NHL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin":          "https://www.nhl.com",
    "Referer":         "https://www.nhl.com/",
}
SEASON = "20252026"


# ── Cache helpers ──────────────────────────────────────────────────────────────
def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_cache(cache: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


# ── NHL API helpers ────────────────────────────────────────────────────────────
def _get(url: str, timeout: int = 12) -> dict | None:
    try:
        r = requests.get(url, headers=NHL_HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"    ⚠️  GET failed: {url}  →  {e}")
        return None


def fetch_team_game_ids(abbrev: str, n: int = 15) -> list[dict]:
    """
    Returns last N finished games for a team as list of:
    { id, date, home_abbrev, away_abbrev, is_home }
    """
    url  = f"https://api-web.nhle.com/v1/club-schedule-season/{abbrev}/{SEASON}"
    data = _get(url)
    if not data:
        return []

    games = []
    for g in data.get("games", []):
        if g.get("gameState") not in ("OFF", "FINAL"):
            continue
        home_abbrev = g.get("homeTeam", {}).get("abbrev", "")
        away_abbrev = g.get("awayTeam", {}).get("abbrev", "")
        games.append({
            "id":           g["id"],
            "date":         g.get("gameDate", "")[:10],
            "home_abbrev":  home_abbrev,
            "away_abbrev":  away_abbrev,
            "is_home":      home_abbrev == abbrev,
        })

    # Sort newest first, take last N
    games.sort(key=lambda x: x["date"], reverse=True)
    return games[:n]


# ── Play-by-play: GIFT (goal in first 10 min) ──────────────────────────────────
def fetch_gift_from_pbp(game_id: int) -> bool | None:
    """
    Returns True  if there was a goal in first 10:00 of period 1.
    Returns False if period 1 had no goal in first 10 min.
    Returns None  if API call failed.
    """
    url  = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"
    data = _get(url)
    if not data:
        return None

    for play in data.get("plays", []):
        if play.get("typeDescKey") != "goal":
            continue
        period = play.get("periodDescriptor", {}).get("number", 0)
        if period != 1:
            continue
        time_str = play.get("timeInPeriod", "99:99")   # "MM:SS"
        try:
            mins, secs = map(int, time_str.split(":"))
            total_secs = mins * 60 + secs
        except Exception:
            continue
        if total_secs <= 600:   # ≤ 10:00
            return True

    # Period 1 had no goal in first 10 min (or no goals at all)
    return False


# ── Boxscore: First Period O/U ─────────────────────────────────────────────────
def fetch_fp_from_boxscore(game_id: int) -> int | None:
    """
    Returns total 1st period goals, or None on failure.
    """
    url  = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore"
    data = _get(url)
    if not data:
        return None

    # Try linescore → byPeriod
    by_period = (
        data.get("linescore", {}).get("byPeriod")
        or data.get("boxscore", {}).get("linescore", {}).get("byPeriod")
        or []
    )
    for period_entry in by_period:
        if period_entry.get("periodDescriptor", {}).get("number") == 1:
            away_goals = period_entry.get("away", 0)
            home_goals = period_entry.get("home", 0)
            return int(away_goals) + int(home_goals)

    # Fallback: sum period goals from team stats
    try:
        home_p = data.get("homeTeam", {}).get("goals", {})
        away_p = data.get("awayTeam", {}).get("goals", {})
        if isinstance(home_p, dict) and isinstance(away_p, dict):
            return home_p.get("p1", 0) + away_p.get("p1", 0)
    except Exception:
        pass

    return None


# ── Per-game data builder ──────────────────────────────────────────────────────
def fetch_game_data(game_info: dict, cache: dict) -> dict | None:
    """
    Fetch GIFT + FP data for a single game, using cache when available.
    Returns { gift: bool, fp_goals: int, is_home: bool, date: str }
    """
    game_id  = game_info["id"]
    cache_key = str(game_id)

    if cache_key in cache:
        cached = cache[cache_key]
        return {
            "gift":     cached.get("gift"),
            "fp_goals": cached.get("fp_goals"),
            "is_home":  game_info["is_home"],
            "date":     game_info["date"],
        }

    print(f"      📡 Game {game_id} ({game_info['date']}) …", end=" ", flush=True)

    # Fetch play-by-play for GIFT
    gift = fetch_gift_from_pbp(game_id)
    time.sleep(0.3)

    # Fetch boxscore for FP goals
    fp_goals = fetch_fp_from_boxscore(game_id)
    time.sleep(0.3)

    print(f"GIFT={'✓' if gift else ('✗' if gift is False else '?')}  "
          f"P1={fp_goals if fp_goals is not None else '?'}")

    # Cache even if partial
    cache[cache_key] = {
        "gift":     gift,
        "fp_goals": fp_goals,
        "date":     game_info["date"],
    }
    return {
        "gift":     gift,
        "fp_goals": fp_goals,
        "is_home":  game_info["is_home"],
        "date":     game_info["date"],
    }


# ── Stats calculator ───────────────────────────────────────────────────────────
def _pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "N/A"
    return f"{numerator / denominator * 100:.1f}%"


def calc_team_stats(games: list[dict]) -> dict:
    """
    games: list of { gift: bool|None, fp_goals: int|None, is_home: bool, date: str }
    Returns gift + fp_ou dicts.
    """
    # Filter out games where API failed
    gift_games = [g for g in games if g["gift"] is not None]
    fp_games   = [g for g in games if g["fp_goals"] is not None]

    # Sort newest first
    gift_sorted = sorted(gift_games, key=lambda x: x["date"], reverse=True)
    fp_sorted   = sorted(fp_games,   key=lambda x: x["date"], reverse=True)

    # GIFT stats
    gift_season = sum(1 for g in gift_sorted if g["gift"])
    gift_l5     = sum(1 for g in gift_sorted[:5] if g["gift"])
    gift_l10    = sum(1 for g in gift_sorted[:10] if g["gift"])
    gift_home   = [g for g in gift_sorted if g["is_home"]]
    gift_away   = [g for g in gift_sorted if not g["is_home"]]

    # GIFT streak (consecutive games with GIFT, newest first)
    streak = 0
    for g in gift_sorted:
        if g["gift"]:
            streak += 1
        else:
            break

    # FP O/U stats (over 1.5 goals in 1st period = 2+ goals)
    fp_over_season = sum(1 for g in fp_sorted if (g["fp_goals"] or 0) > 1)
    fp_over_l5     = sum(1 for g in fp_sorted[:5] if (g["fp_goals"] or 0) > 1)
    fp_over_l10    = sum(1 for g in fp_sorted[:10] if (g["fp_goals"] or 0) > 1)
    fp_home        = [g for g in fp_sorted if g["is_home"]]
    fp_away        = [g for g in fp_sorted if not g["is_home"]]

    n_gift = len(gift_sorted)
    n_fp   = len(fp_sorted)

    return {
        "gift": {
            "pct_season":    _pct(gift_season, n_gift),
            "pct_l5":        _pct(gift_l5, min(5, n_gift)),
            "pct_l10":       _pct(gift_l10, min(10, n_gift)),
            "record_season": f"{gift_season}-{n_gift - gift_season}",
            "streak":        streak,
            "home_pct":      _pct(sum(1 for g in gift_home if g["gift"]), len(gift_home)),
            "away_pct":      _pct(sum(1 for g in gift_away if g["gift"]), len(gift_away)),
            "scoring_rate":  _pct(gift_season, n_gift),
            "games":         n_gift,
        },
        "fp_ou": {
            "pct_season":    _pct(fp_over_season, n_fp),
            "pct_l5":        _pct(fp_over_l5, min(5, n_fp)),
            "pct_l10":       _pct(fp_over_l10, min(10, n_fp)),
            "record_season": f"{fp_over_season}-{n_fp - fp_over_season}",
            "over_games":    fp_over_season,
            "home_pct":      _pct(sum(1 for g in fp_home if (g["fp_goals"] or 0) > 1), len(fp_home)),
            "away_pct":      _pct(sum(1 for g in fp_away if (g["fp_goals"] or 0) > 1), len(fp_away)),
            "games":         n_fp,
        },
    }


# ── Public API ─────────────────────────────────────────────────────────────────
def build_gift_stats_for_teams(team_abbrevs: list[str], n_games: int = 15) -> dict:
    """
    Main entry point called by run_pipeline.py.
    Returns { "CAR": { "gift": {...}, "fp_ou": {...} }, "MTL": {...}, ... }
    """
    cache   = load_cache()
    result  = {}
    changed = False

    for abbrev in team_abbrevs:
        abbrev = abbrev.upper()
        print(f"  🏒 {abbrev}: fetching last {n_games} games …")

        game_list = fetch_team_game_ids(abbrev, n=n_games)
        if not game_list:
            print(f"    ⚠️  No game list returned for {abbrev}")
            result[abbrev] = _empty_stats()
            continue

        games_data = []
        for game_info in game_list:
            gd = fetch_game_data(game_info, cache)
            if gd:
                games_data.append(gd)
                if str(game_info["id"]) not in cache or cache.get(str(game_info["id"])) != {
                    "gift": gd["gift"], "fp_goals": gd["fp_goals"], "date": gd["date"]
                }:
                    changed = True

        result[abbrev] = calc_team_stats(games_data)
        g = result[abbrev]["gift"]
        print(f"    ✅ {abbrev}: GIFT={g['pct_season']}  L10={g['pct_l10']}  "
              f"Streak={g['streak']}  ({g['games']} games)")

    if changed:
        save_cache(cache)

    # Save output file
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n  💾 gift_stats.json saved → {OUTPUT_FILE} ({len(result)} teams)")

    return result


def get_gift_stats(abbr: str, all_stats: dict) -> dict:
    return all_stats.get(abbr.upper(), _empty_stats()).get("gift", _empty_gift())


def get_fp_stats(abbr: str, all_stats: dict) -> dict:
    return all_stats.get(abbr.upper(), _empty_stats()).get("fp_ou", _empty_fp())


def _empty_gift() -> dict:
    return {"pct_season":"N/A","pct_l5":"N/A","pct_l10":"N/A",
            "record_season":"N/A","streak":0,"home_pct":"N/A","away_pct":"N/A","scoring_rate":"N/A"}

def _empty_fp() -> dict:
    return {"pct_season":"N/A","pct_l5":"N/A","pct_l10":"N/A",
            "record_season":"N/A","over_games":0,"home_pct":"N/A","away_pct":"N/A"}

def _empty_stats() -> dict:
    return {"gift": _empty_gift(), "fp_ou": _empty_fp()}


# ── Standalone run ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    teams = sys.argv[1:] if len(sys.argv) > 1 else ["CAR", "MTL", "VGK", "COL"]
    print(f"\n🏒 Building real GIFT stats for: {teams}\n")
    stats = build_gift_stats_for_teams(teams, n_games=15)
    print("\n📊 Final Results:")
    for team, data in stats.items():
        g  = data["gift"]
        fp = data["fp_ou"]
        print(f"  {team:4s}  GIFT {g['pct_season']:7s}  L10 {g['pct_l10']:7s}  "
              f"Streak {g['streak']}  |  FP O/U {fp['pct_season']:7s}  L10 {fp['pct_l10']}")