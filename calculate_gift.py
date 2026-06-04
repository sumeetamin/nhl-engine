"""
calculate_gift.py — GIFT + First Period + P1 L5/L10 Stats via NHL API
Full season stats (n_games=82) from play-by-play data.
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

def load_cache():
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f: return json.load(f)
        except: pass
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f: json.dump(cache, f, indent=2)

def _get(url, timeout=12):
    try:
        r = requests.get(url, headers=NHL_HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"    ⚠️  GET failed {url} → {e}")
        return None

def fetch_team_game_ids(abbrev, n=82):
    url  = f"https://api-web.nhle.com/v1/club-schedule-season/{abbrev}/{SEASON}"
    data = _get(url)
    if not data: return []
    games = []
    for g in data.get("games", []):
        if g.get("gameState") not in ("OFF", "FINAL"): continue
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

def fetch_pbp_stats(game_id):
    """
    Single play-by-play call returns:
      - gift: bool (any goal in first 10 min of P1)
      - fp_goals: total P1 goals by both teams
      - p1_home_goals: goals scored by HOME team in P1
      - p1_away_goals: goals scored by AWAY team in P1
    """
    url  = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"
    data = _get(url)
    if not data: return None

    # Identify which team ID is home
    home_id = (data.get("homeTeam") or {}).get("id")

    gift          = False
    fp_goals      = 0
    p1_home_goals = 0
    p1_away_goals = 0

    for play in data.get("plays", []):
        if play.get("typeDescKey") != "goal": continue
        pd_num = play.get("periodDescriptor", {}).get("number", 0)
        try:    pd_num = int(pd_num)
        except: continue
        if pd_num != 1: continue

        fp_goals += 1

        # Which team scored?
        scorer_team_id = (play.get("details") or {}).get("eventOwnerTeamId")
        if scorer_team_id is not None and home_id is not None:
            if scorer_team_id == home_id:
                p1_home_goals += 1
            else:
                p1_away_goals += 1

        # GIFT: goal within first 10 minutes
        time_str = play.get("timeInPeriod", "99:99")
        try:
            mins, secs = map(int, time_str.split(":"))
            if mins * 60 + secs <= 600: gift = True
        except: pass

    return {
        "gift":          gift,
        "fp_goals":      fp_goals,
        "p1_home_goals": p1_home_goals,
        "p1_away_goals": p1_away_goals,
    }

def _cache_needs_refresh(entry):
    """Returns True if cache entry is missing the new P1 per-team fields."""
    return "p1_home_goals" not in entry or "p1_away_goals" not in entry

def fetch_game_data(game_info, cache):
    game_id   = game_info["id"]
    cache_key = str(game_id)
    is_home   = game_info["is_home"]

    if cache_key in cache and not _cache_needs_refresh(cache[cache_key]):
        c = cache[cache_key]
        p1_for     = c["p1_home_goals"] if is_home else c["p1_away_goals"]
        p1_against = c["p1_away_goals"] if is_home else c["p1_home_goals"]
        return {
            "gift":        c["gift"],
            "fp_goals":    c["fp_goals"],
            "p1_for":      p1_for,
            "p1_against":  p1_against,
            "p1_win":      p1_for > p1_against,
            "is_home":     is_home,
            "date":        game_info["date"],
        }

    print(f"      📡 Game {game_id} ({game_info['date']}) …", end=" ", flush=True)
    stats = fetch_pbp_stats(game_id)
    time.sleep(0.2)

    if stats is None:
        print("FAILED")
        return None

    p1_for     = stats["p1_home_goals"] if is_home else stats["p1_away_goals"]
    p1_against = stats["p1_away_goals"] if is_home else stats["p1_home_goals"]

    print(
        f"GIFT={'✓' if stats['gift'] else '✗'}  "
        f"P1={stats['fp_goals']}  "
        f"P1-for={p1_for}  P1-against={p1_against}"
    )

    cache[cache_key] = {
        "gift":          stats["gift"],
        "fp_goals":      stats["fp_goals"],
        "p1_home_goals": stats["p1_home_goals"],
        "p1_away_goals": stats["p1_away_goals"],
        "date":          game_info["date"],
    }
    return {
        "gift":       stats["gift"],
        "fp_goals":   stats["fp_goals"],
        "p1_for":     p1_for,
        "p1_against": p1_against,
        "p1_win":     p1_for > p1_against,
        "is_home":    is_home,
        "date":       game_info["date"],
    }

def _pct(num, den):
    if den == 0: return "N/A"
    return f"{num/den*100:.1f}%"

def _avg(values):
    if not values: return "N/A"
    return f"{sum(values)/len(values):.2f}"

def calc_team_stats(games):
    if not games: return _empty_stats()
    gs = sorted(games, key=lambda x: x["date"], reverse=True)
    ng = len(gs)

    # ── GIFT ─────────────────────────────────────────────────────────────────
    gift_wins = sum(1 for g in gs if g["gift"])
    streak = 0
    for g in gs:
        if g["gift"]: streak += 1
        else: break

    gh = [g for g in gs if g["is_home"]]
    ga = [g for g in gs if not g["is_home"]]

    gift_stats = {
        "pct_season":    _pct(gift_wins, ng),
        "pct_l5":        _pct(sum(1 for g in gs[:5]  if g["gift"]), min(5,  ng)),
        "pct_l10":       _pct(sum(1 for g in gs[:10] if g["gift"]), min(10, ng)),
        "record_season": f"{gift_wins}-{ng-gift_wins}",
        "streak":        streak,
        "home_pct":      _pct(sum(1 for g in gh if g["gift"]), len(gh)),
        "away_pct":      _pct(sum(1 for g in ga if g["gift"]), len(ga)),
        "scoring_rate":  _pct(gift_wins, ng),
        "games":         ng,
    }

    # ── FP O/U (total P1 goals > 1) ──────────────────────────────────────────
    fp_over = sum(1 for g in gs if g["fp_goals"] > 1)
    nf      = ng
    fh      = [g for g in gs if g["is_home"]]
    fa      = [g for g in gs if not g["is_home"]]

    fp_ou_stats = {
        "pct_season":    _pct(fp_over, nf),
        "pct_l5":        _pct(sum(1 for g in gs[:5]  if g["fp_goals"] > 1), min(5,  nf)),
        "pct_l10":       _pct(sum(1 for g in gs[:10] if g["fp_goals"] > 1), min(10, nf)),
        "record_season": f"{fp_over}-{nf-fp_over}",
        "over_games":    fp_over,
        "home_pct":      _pct(sum(1 for g in fh if g["fp_goals"] > 1), len(fh)),
        "away_pct":      _pct(sum(1 for g in fa if g["fp_goals"] > 1), len(fa)),
        "games":         nf,
    }

    # ── P1 SCORING (team-specific 1st period goals for/against) ──────────────
    l5  = gs[:5]
    l10 = gs[:10]

    p1_wins_season = sum(1 for g in gs  if g["p1_win"])
    p1_wins_l5     = sum(1 for g in l5  if g["p1_win"])
    p1_wins_l10    = sum(1 for g in l10 if g["p1_win"])

    p1_scored_season = sum(1 for g in gs  if g["p1_for"] > 0)   # games where team scored in P1
    p1_scored_l5     = sum(1 for g in l5  if g["p1_for"] > 0)
    p1_scored_l10    = sum(1 for g in l10 if g["p1_for"] > 0)

    p1_stats = {
        # Win the 1st period
        "p1_win_pct_season": _pct(p1_wins_season, ng),
        "p1_win_pct_l5":     _pct(p1_wins_l5,     min(5,  ng)),
        "p1_win_pct_l10":    _pct(p1_wins_l10,    min(10, ng)),
        "p1_win_record":     f"{p1_wins_season}-{ng - p1_wins_season}",

        # Avg goals FOR in P1
        "p1_gf_avg_season":  _avg([g["p1_for"]     for g in gs]),
        "p1_gf_avg_l5":      _avg([g["p1_for"]     for g in l5]),
        "p1_gf_avg_l10":     _avg([g["p1_for"]     for g in l10]),

        # Avg goals AGAINST in P1
        "p1_ga_avg_season":  _avg([g["p1_against"] for g in gs]),
        "p1_ga_avg_l5":      _avg([g["p1_against"] for g in l5]),
        "p1_ga_avg_l10":     _avg([g["p1_against"] for g in l10]),

        # % of games where team scored at least 1 goal in P1
        "p1_scored_pct_season": _pct(p1_scored_season, ng),
        "p1_scored_pct_l5":     _pct(p1_scored_l5,     min(5,  ng)),
        "p1_scored_pct_l10":    _pct(p1_scored_l10,    min(10, ng)),

        # Home/Away splits
        "p1_win_home_pct":  _pct(sum(1 for g in gh if g["p1_win"]), len(gh)),
        "p1_win_away_pct":  _pct(sum(1 for g in ga if g["p1_win"]), len(ga)),

        "games": ng,
    }

    return {
        "gift":   gift_stats,
        "fp_ou":  fp_ou_stats,
        "p1":     p1_stats,
    }

def build_gift_stats_for_teams(team_abbrevs, n_games=82):
    cache   = load_cache()
    result  = {}
    changed = False

    for abbrev in team_abbrevs:
        abbrev = abbrev.upper()
        print(f"  🏒 {abbrev}: fetching up to {n_games} games …")
        game_list = fetch_team_game_ids(abbrev, n=n_games)
        if not game_list:
            print(f"    ⚠️  No games for {abbrev}")
            result[abbrev] = _empty_stats()
            continue

        games_data = []
        for game_info in game_list:
            was_cached = (
                str(game_info["id"]) in cache and
                not _cache_needs_refresh(cache.get(str(game_info["id"]), {}))
            )
            gd = fetch_game_data(game_info, cache)
            if gd:
                games_data.append(gd)
                if not was_cached: changed = True

        result[abbrev] = calc_team_stats(games_data)
        g  = result[abbrev]["gift"]
        fp = result[abbrev]["fp_ou"]
        p1 = result[abbrev]["p1"]
        print(
            f"    ✅ {abbrev}: "
            f"GIFT={g['pct_season']}  L10={g['pct_l10']}  Streak={g['streak']}  |  "
            f"FP O/U={fp['pct_season']}  |  "
            f"P1-Win={p1['p1_win_pct_season']}  P1-GF/g={p1['p1_gf_avg_season']}  "
            f"({g['games']} games)"
        )

    if changed: save_cache(cache)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f: json.dump(result, f, indent=2)
    print(f"\n  💾 gift_stats.json → {OUTPUT_FILE} ({len(result)} teams)")
    return result

# ── Public accessors ──────────────────────────────────────────────────────────
def get_gift_stats(abbr, all_stats):
    return all_stats.get(abbr.upper(), _empty_stats()).get("gift", _empty_gift())

def get_fp_stats(abbr, all_stats):
    return all_stats.get(abbr.upper(), _empty_stats()).get("fp_ou", _empty_fp())

def get_p1_stats(abbr, all_stats):
    return all_stats.get(abbr.upper(), _empty_stats()).get("p1", _empty_p1())

# ── Empty fallbacks ───────────────────────────────────────────────────────────
def _empty_gift():
    return {
        "pct_season":"N/A","pct_l5":"N/A","pct_l10":"N/A",
        "record_season":"N/A","streak":0,
        "home_pct":"N/A","away_pct":"N/A","scoring_rate":"N/A",
    }

def _empty_fp():
    return {
        "pct_season":"N/A","pct_l5":"N/A","pct_l10":"N/A",
        "record_season":"N/A","over_games":0,
        "home_pct":"N/A","away_pct":"N/A",
    }

def _empty_p1():
    return {
        "p1_win_pct_season":"N/A","p1_win_pct_l5":"N/A","p1_win_pct_l10":"N/A",
        "p1_win_record":"N/A",
        "p1_gf_avg_season":"N/A","p1_gf_avg_l5":"N/A","p1_gf_avg_l10":"N/A",
        "p1_ga_avg_season":"N/A","p1_ga_avg_l5":"N/A","p1_ga_avg_l10":"N/A",
        "p1_scored_pct_season":"N/A","p1_scored_pct_l5":"N/A","p1_scored_pct_l10":"N/A",
        "p1_win_home_pct":"N/A","p1_win_away_pct":"N/A",
        "games":0,
    }

def _empty_stats():
    return {"gift": _empty_gift(), "fp_ou": _empty_fp(), "p1": _empty_p1()}


if __name__ == "__main__":
    teams = sys.argv[1:] if len(sys.argv) > 1 else ["CAR","VGK"]
    print(f"\n🏒 Building GIFT+P1 stats for: {teams} (full season)\n")
    stats = build_gift_stats_for_teams(teams, n_games=82)
    print("\n📊 Results:")
    for team, data in stats.items():
        g  = data["gift"]
        fp = data["fp_ou"]
        p1 = data["p1"]
        print(f"  {team:4s}  GIFT {g['pct_season']:7s}  L10 {g['pct_l10']:7s}  Streak {g['streak']}")
        print(f"        P1-Win Season={p1['p1_win_pct_season']}  L5={p1['p1_win_pct_l5']}  L10={p1['p1_win_pct_l10']}")
        print(f"        P1-GF  Season={p1['p1_gf_avg_season']}  L5={p1['p1_gf_avg_l5']}  L10={p1['p1_gf_avg_l10']}")
        print(f"        P1-GA  Season={p1['p1_ga_avg_season']}  L5={p1['p1_ga_avg_l5']}  L10={p1['p1_ga_avg_l10']}")