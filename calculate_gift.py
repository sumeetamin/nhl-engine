"""
calculate_gift.py — Real GIFT + First Period Stats via NHL API
=============================================================
GIFT   = % of games with a goal in the first 10 minutes (play-by-play)
FP O/U = % of games where 1st period total goals > 1.5 (also from play-by-play)

Both calculated from a single play-by-play API call per game.
Results cached in gift_cache.json so repeat runs are instant.

Standalone:  python calculate_gift.py CAR MTL
Import:      from calculate_gift import build_gift_stats_for_teams
"""

import json, os, time, sys, requests
from datetime import datetime
from pathlib import Path

SCRIPT_DIR  = Path(__file__).resolve().parent
CACHE_FILE  = SCRIPT_DIR / "gift_cache.json"
OUTPUT_FILE = SCRIPT_DIR / "frontend" / "public" / "gift_stats.json"

NHL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nhl.com",
    "Referer": "https://www.nhl.com/",
}
SEASON = "20252026"


# ── Cache ──────────────────────────────────────────────────────────────────────
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


# ── NHL API ────────────────────────────────────────────────────────────────────
def _get(url: str, timeout: int = 12) -> dict | None:
    try:
        r = requests.get(url, headers=NHL_HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"    ⚠️  GET failed {url} → {e}")
        return None


def fetch_team_game_ids(abbrev: str, n: int = 15) -> list:
    url  = f"https://api-web.nhle.com/v1/club-schedule-season/{abbrev}/{SEASON}"
    data = _get(url)
    if not data:
        return []
    games = []
    for g in data.get("games", []):
        if g.get("gameState") not in ("OFF", "FINAL"):
            continue
        ha = g.get("homeTeam", {}).get("abbrev", "")
        aa = g.get("awayTeam", {}).get("abbrev", "")
        games.append({
            "id":          g["id"],
            "date":        g.get("gameDate", "")[:10],
            "home_abbrev": ha,
            "away_abbrev": aa,
            "is_home":     ha == abbrev,
        })
    games.sort(key=lambda x: x["date"], reverse=True)
    return games[:n]


# ── Single play-by-play call → both GIFT and FP goals ─────────────────────────
def fetch_pbp_stats(game_id: int) -> dict | None:
    """
    One API call per game. Returns:
    { gift: bool, fp_goals: int }
    gift     = True if any goal scored in period 1 within first 10:00
    fp_goals = total goals scored in period 1
    """
    url  = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"
    data = _get(url)
    if not data:
        return None

    gift     = False
    fp_goals = 0

    for play in data.get("plays", []):
        if play.get("typeDescKey") != "goal":
            continue

        # Period number — handle both int and string
        pd_num = play.get("periodDescriptor", {}).get("number", 0)
        try:
            pd_num = int(pd_num)
        except (TypeError, ValueError):
            continue

        if pd_num != 1:
            continue

        # It's a 1st period goal
        fp_goals += 1

        # Check if it's within first 10:00
        time_str = play.get("timeInPeriod", "99:99")
        try:
            mins, secs = map(int, time_str.split(":"))
            if mins * 60 + secs <= 600:
                gift = True
        except Exception:
            pass

    return {"gift": gift, "fp_goals": fp_goals}


# ── Per-game data with cache ───────────────────────────────────────────────────
def fetch_game_data(game_info: dict, cache: dict) -> dict | None:
    game_id   = game_info["id"]
    cache_key = str(game_id)

    if cache_key in cache:
        c = cache[cache_key]
        # Only use cache if it has the new combined format
        if "gift" in c and "fp_goals" in c:
            return {
                "gift":     c["gift"],
                "fp_goals": c["fp_goals"],
                "is_home":  game_info["is_home"],
                "date":     game_info["date"],
            }

    print(f"      📡 Game {game_id} ({game_info['date']}) …", end=" ", flush=True)

    stats = fetch_pbp_stats(game_id)
    time.sleep(0.25)

    if stats is None:
        print("FAILED")
        return None

    print(f"GIFT={'✓' if stats['gift'] else '✗'}  P1_goals={stats['fp_goals']}")

    cache[cache_key] = {
        "gift":     stats["gift"],
        "fp_goals": stats["fp_goals"],
        "date":     game_info["date"],
    }

    return {
        "gift":     stats["gift"],
        "fp_goals": stats["fp_goals"],
        "is_home":  game_info["is_home"],
        "date":     game_info["date"],
    }


# ── Stats calculator ───────────────────────────────────────────────────────────
def _pct(num: int, den: int) -> str:
    if den == 0:
        return "N/A"
    return f"{num / den * 100:.1f}%"


def calc_team_stats(games: list) -> dict:
    if not games:
        return _empty_stats()

    games_sorted = sorted(games, key=lambda x: x["date"], reverse=True)

    # GIFT
    gift_all  = games_sorted
    gift_l5   = games_sorted[:5]
    gift_l10  = games_sorted[:10]
    gift_home = [g for g in games_sorted if g["is_home"]]
    gift_away = [g for g in games_sorted if not g["is_home"]]

    streak = 0
    for g in games_sorted:
        if g["gift"]: streak += 1
        else: break

    ng = len(gift_all)
    gift_wins = sum(1 for g in gift_all if g["gift"])

    # FP O/U (over 1.5 = 2+ goals in period 1)
    fp_all   = games_sorted
    fp_l5    = games_sorted[:5]
    fp_l10   = games_sorted[:10]
    fp_home  = [g for g in games_sorted if g["is_home"]]
    fp_away  = [g for g in games_sorted if not g["is_home"]]

    nf = len(fp_all)
    fp_over = sum(1 for g in fp_all if g["fp_goals"] > 1)

    return {
        "gift": {
            "pct_season":    _pct(gift_wins, ng),
            "pct_l5":        _pct(sum(1 for g in gift_l5  if g["gift"]), min(5,  ng)),
            "pct_l10":       _pct(sum(1 for g in gift_l10 if g["gift"]), min(10, ng)),
            "record_season": f"{gift_wins}-{ng - gift_wins}",
            "streak":        streak,
            "home_pct":      _pct(sum(1 for g in gift_home if g["gift"]), len(gift_home)),
            "away_pct":      _pct(sum(1 for g in gift_away if g["gift"]), len(gift_away)),
            "scoring_rate":  _pct(gift_wins, ng),
            "games":         ng,
        },
        "fp_ou": {
            "pct_season":    _pct(fp_over, nf),
            "pct_l5":        _pct(sum(1 for g in fp_l5  if g["fp_goals"] > 1), min(5,  nf)),
            "pct_l10":       _pct(sum(1 for g in fp_l10 if g["fp_goals"] > 1), min(10, nf)),
            "record_season": f"{fp_over}-{nf - fp_over}",
            "over_games":    fp_over,
            "home_pct":      _pct(sum(1 for g in fp_home if g["fp_goals"] > 1), len(fp_home)),
            "away_pct":      _pct(sum(1 for g in fp_away if g["fp_goals"] > 1), len(fp_away)),
            "games":         nf,
        },
    }


# ── Public API ─────────────────────────────────────────────────────────────────
def build_gift_stats_for_teams(team_abbrevs: list, n_games: int = 15) -> dict:
    cache   = load_cache()
    result  = {}
    changed = False

    for abbrev in team_abbrevs:
        abbrev = abbrev.upper()
        print(f"  🏒 {abbrev}: fetching last {n_games} games …")

        game_list = fetch_team_game_ids(abbrev, n=n_games)
        if not game_list:
            print(f"    ⚠️  No games for {abbrev}")
            result[abbrev] = _empty_stats()
            continue

        games_data = []
        for game_info in game_list:
            was_cached = str(game_info["id"]) in cache
            gd = fetch_game_data(game_info, cache)
            if gd:
                games_data.append(gd)
                if not was_cached:
                    changed = True

        result[abbrev] = calc_team_stats(games_data)
        g  = result[abbrev]["gift"]
        fp = result[abbrev]["fp_ou"]
        print(f"    ✅ {abbrev}: GIFT={g['pct_season']}  L10={g['pct_l10']}  "
              f"Streak={g['streak']}  |  FP O/U={fp['pct_season']}  ({g['games']} games)")

    if changed:
        save_cache(cache)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n  💾 gift_stats.json → {OUTPUT_FILE} ({len(result)} teams)")

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


# ── Standalone ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    teams = sys.argv[1:] if len(sys.argv) > 1 else ["CAR", "MTL", "VGK", "COL"]
    print(f"\n🏒 Building real GIFT stats for: {teams}\n")
    stats = build_gift_stats_for_teams(teams, n_games=15)
    print("\n📊 Results:")
    for team, data in stats.items():
        g  = data["gift"]
        fp = data["fp_ou"]
        print(f"  {team:4s}  GIFT {g['pct_season']:7s}  L10 {g['pct_l10']:7s}  "
              f"Streak {g['streak']}  |  FP O/U {fp['pct_season']:7s}  L10 {fp['pct_l10']}")