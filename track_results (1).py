"""
track_results.py — NHL Engine Result Tracker
=============================================
Runs AFTER a game day is complete.
1. Reads yesterday's predictions from  predictions_YYYYMMDD.json
2. Fetches actual NHL scores from the free NHL API
3. Grades ML / Spread / O/U / Edge picks
4. Appends to model_records_ledger.json
5. Regenerates frontend/public/historical_stats.json

Add to GitHub Actions cron — run daily ~10:00 UTC (after overnight games finish).
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT          = Path(__file__).resolve().parent
LEDGER_PATH   = ROOT / "model_records_ledger.json"
HIST_OUT      = ROOT / "frontend" / "public" / "historical_stats.json"
PRED_ARCHIVE  = ROOT  # predictions_YYYYMMDD.json live here

# ── Helpers ──────────────────────────────────────────────────────────────────
def fetch_json(url: str, retries: int = 3) -> dict | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.nhl.com",
    }
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} for {url} (attempt {attempt+1})")
        except Exception as e:
            print(f"  Error fetching {url}: {e} (attempt {attempt+1})")
    return None


def get_nhl_scores(date_str: str) -> list[dict]:
    """
    Fetch completed NHL game scores for date_str (YYYY-MM-DD).
    Returns list of: {away_abbr, home_abbr, away_score, home_score}
    """
    url = f"https://api-web.nhle.com/v1/score/{date_str}"
    data = fetch_json(url)
    if not data:
        # Fallback: try ESPN
        espn_date = date_str.replace("-", "")
        url2 = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={espn_date}"
        data = fetch_json(url2)
        if data:
            return _parse_espn(data)
        print(f"  Could not fetch scores for {date_str}")
        return []
    return _parse_nhl(data)


def _parse_nhl(data: dict) -> list[dict]:
    """Parse api-web.nhle.com /v1/score response."""
    results = []
    for g in data.get("games", []):
        state = g.get("gameState", "")
        if state not in ("OFF", "FINAL"):
            continue  # skip in-progress / scheduled
        away = g.get("awayTeam", {})
        home = g.get("homeTeam", {})
        away_score = away.get("score")
        home_score = home.get("score")
        if away_score is None or home_score is None:
            continue
        results.append({
            "away_abbr": away.get("abbrev", "").upper(),
            "home_abbr": home.get("abbrev", "").upper(),
            "away_score": int(away_score),
            "home_score": int(home_score),
        })
    return results


def _parse_espn(data: dict) -> list[dict]:
    """Parse ESPN scoreboard response as fallback."""
    results = []
    for event in data.get("events", []):
        comp = event.get("competitions", [{}])[0]
        status = comp.get("status", {}).get("type", {}).get("name", "")
        if "Final" not in status and "final" not in status:
            continue
        away_score = home_score = None
        away_abbr = home_abbr = ""
        for team in comp.get("competitors", []):
            abbr = team.get("team", {}).get("abbreviation", "").upper()
            score = int(team.get("score", 0))
            if team.get("homeAway") == "home":
                home_abbr = abbr
                home_score = score
            else:
                away_abbr = abbr
                away_score = score
        if away_score is not None and home_score is not None:
            results.append({
                "away_abbr": away_abbr,
                "home_abbr": home_abbr,
                "away_score": away_score,
                "home_score": home_score,
            })
    return results


def match_game(pred_away: str, pred_home: str, scores: list[dict]) -> dict | None:
    """Find the actual score entry matching a prediction's team pair."""
    for g in scores:
        if g["away_abbr"] == pred_away.upper() and g["home_abbr"] == pred_home.upper():
            return g
        # Sometimes home/away can be swapped in different APIs
        if g["away_abbr"] == pred_home.upper() and g["home_abbr"] == pred_away.upper():
            # Swap so our convention stays consistent
            return {
                "away_abbr": pred_away.upper(),
                "home_abbr": pred_home.upper(),
                "away_score": g["home_score"],
                "home_score": g["away_score"],
            }
    return None


# ── Grading Logic ─────────────────────────────────────────────────────────────
def grade_ml(pick: str, actual: dict) -> str:
    """
    pick:   e.g. 'CAR ML'  or 'MTL ML'
    actual: {away_abbr, home_abbr, away_score, home_score}
    Returns 'W', 'L', or 'PUSH' (OT result treated as push for ML if requested,
    but here we just call it a win/loss on final score).
    """
    if not pick or pick.upper() in ("PASS", "N/A", "TBD", ""):
        return "SKIP"

    pick_team = pick.split()[0].upper()
    away, home = actual["away_abbr"], actual["home_abbr"]
    a_score, h_score = actual["away_score"], actual["home_score"]

    if a_score == h_score:
        return "PUSH"
    winner = away if a_score > h_score else home
    return "W" if winner == pick_team else "L"


def grade_spread(pick: str, actual: dict) -> str:
    """
    pick:   e.g. 'CAR -1.5'  or 'MTL +1.5'  or 'PASS'
    Returns 'W', 'L', 'PUSH', or 'SKIP'.
    """
    if not pick or pick.upper() in ("PASS", "N/A", "TBD", ""):
        return "SKIP"

    # Parse team and spread value
    parts = pick.strip().split()
    if len(parts) < 2:
        return "SKIP"
    pick_team = parts[0].upper()
    try:
        spread = float(parts[1])
    except ValueError:
        return "SKIP"

    away, home = actual["away_abbr"], actual["home_abbr"]
    a_score, h_score = actual["away_score"], actual["home_score"]

    # Get pick team's margin
    if pick_team == away:
        margin = a_score - h_score
    elif pick_team == home:
        margin = h_score - a_score
    else:
        return "SKIP"

    # Apply spread: margin + spread
    result = margin + spread
    if result > 0:
        return "W"
    elif result < 0:
        return "L"
    else:
        return "PUSH"


def grade_ou(pick: str, actual: dict) -> str:
    """
    pick:   e.g. 'OVER 6.0'  or 'UNDER 5.5'
    Returns 'W', 'L', 'PUSH', or 'SKIP'.
    """
    if not pick or pick.upper() in ("PASS", "N/A", "TBD", ""):
        return "SKIP"

    parts = pick.strip().upper().split()
    if len(parts) < 2:
        return "SKIP"
    direction = parts[0]  # 'OVER' or 'UNDER'
    try:
        line = float(parts[1])
    except ValueError:
        return "SKIP"

    total = actual["away_score"] + actual["home_score"]

    if total == line:
        return "PUSH"
    if direction == "OVER":
        return "W" if total > line else "L"
    elif direction == "UNDER":
        return "W" if total < line else "L"
    return "SKIP"


def grade_edge(best_angle: dict, actual: dict) -> str:
    """Grade the best_angle play (usually a ML pick)."""
    play = best_angle.get("play", "")
    if not play:
        return "SKIP"
    # Edge play is always the ML of the picked team
    pick_team = play.split()[0].upper()
    return grade_ml(pick_team + " ML", actual)


# ── Ledger I/O ────────────────────────────────────────────────────────────────
def load_ledger() -> list[dict]:
    if LEDGER_PATH.exists():
        with open(LEDGER_PATH) as f:
            return json.load(f)
    return []


def save_ledger(ledger: list[dict]):
    with open(LEDGER_PATH, "w") as f:
        json.dump(ledger, f, indent=2)
    print(f"  Ledger saved → {LEDGER_PATH} ({len(ledger)} entries)")


# ── Stats Calculator ──────────────────────────────────────────────────────────
def calc_stats(entries: list[dict]) -> dict:
    """
    Compute win/loss/push/win_rate/avg_edge/units for a slice of ledger entries.
    """
    play_types = ["ml", "spread", "ou", "edge"]
    stats = {}
    all_w = all_l = 0

    for pt in play_types:
        wins = losses = pushes = 0
        edges = []
        units = 0.0

        for e in entries:
            result = e.get(pt)
            edge_val = e.get("edge_pct", 0.0)
            if result == "W":
                wins += 1
                units += 1.0
                edges.append(edge_val)
            elif result == "L":
                losses += 1
                units -= 1.0
                edges.append(edge_val)
            elif result == "PUSH":
                pushes += 1

        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0.0
        avg_edge = (sum(edges) / len(edges)) if edges else 0.0

        stats[pt] = {
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": f"{win_rate:.1f}%",
            "avg_edge": f"+{avg_edge:.1f}%" if avg_edge >= 0 else f"{avg_edge:.1f}%",
            "units": f"{units:+.1f}",
        }
        all_w += wins
        all_l += losses

    total_all = all_w + all_l
    overall_rate = (all_w / total_all * 100) if total_all > 0 else 0.0
    all_edges = [e.get("edge_pct", 0.0) for e in entries if e.get("edge_pct")]
    avg_all_edge = sum(all_edges) / len(all_edges) if all_edges else 0.0

    stats["overall"] = {
        "wins": all_w,
        "losses": all_l,
        "win_rate": f"{overall_rate:.1f}%",
        "avg_edge": f"+{avg_all_edge:.1f}%" if avg_all_edge >= 0 else f"{avg_all_edge:.1f}%",
        "units": f"{sum(e.get('units_delta', 0) for e in entries):+.1f}",
    }
    return stats


def build_historical_stats(ledger: list[dict]) -> dict:
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=7)
    month_start = today.replace(day=1)

    def filter_by_date(start=None, end=None):
        result = []
        for e in ledger:
            try:
                d = datetime.strptime(e["date"], "%Y-%m-%d").date()
            except Exception:
                continue
            if start and d < start:
                continue
            if end and d > end:
                continue
            result.append(e)
        return result

    return {
        "all_time":   calc_stats(ledger),
        "this_month": calc_stats(filter_by_date(start=month_start)),
        "this_week":  calc_stats(filter_by_date(start=week_start)),
        "yesterday":  calc_stats(filter_by_date(start=yesterday, end=yesterday)),
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # Determine which date to grade (default: yesterday)
    if len(sys.argv) > 1:
        target_date_str = sys.argv[1]          # e.g. python track_results.py 2026-05-28
    else:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        target_date_str = str(yesterday)

    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    date_compact = target_date_str.replace("-", "")  # 20260528

    print(f"\n{'='*55}")
    print(f"  NHL Engine — Result Tracker for {target_date_str}")
    print(f"{'='*55}")

    # ── 1. Load prediction archive for that date ──────────────────────────────
    pred_file = PRED_ARCHIVE / f"predictions_{date_compact}.json"
    if pred_file.exists():
        print(f"\n[1] Loading predictions from {pred_file.name}...")
        with open(pred_file) as f:
            pred_data = json.load(f)
        # Archive files store a list of games OR a single dict depending on pipeline
        games_to_grade = pred_data if isinstance(pred_data, list) else [pred_data]
    else:
        # Fall back: use daily_predictions.json "yesterday" key
        fallback = PRED_ARCHIVE / "daily_predictions.json"
        if not fallback.exists():
            print(f"  No predictions found for {target_date_str}. Exiting.")
            sys.exit(0)
        print(f"\n[1] Archive not found — using daily_predictions.json[yesterday]...")
        with open(fallback) as f:
            dp = json.load(f)
        yest_game = dp.get("yesterday")
        if not yest_game or yest_game.get("tier") == "NONE":
            print("  No qualifying prediction for yesterday. Exiting.")
            sys.exit(0)
        games_to_grade = [yest_game]

    print(f"  {len(games_to_grade)} game(s) to grade.")

    # ── 2. Fetch actual NHL scores ────────────────────────────────────────────
    print(f"\n[2] Fetching actual NHL scores for {target_date_str}...")
    actual_scores = get_nhl_scores(target_date_str)
    if not actual_scores:
        print("  No scores returned. Cannot grade. Exiting.")
        sys.exit(1)
    print(f"  {len(actual_scores)} game(s) found:")
    for s in actual_scores:
        print(f"    {s['away_abbr']} {s['away_score']} @ {s['home_abbr']} {s['home_score']}")

    # ── 3. Grade each prediction ──────────────────────────────────────────────
    print(f"\n[3] Grading predictions...")
    ledger = load_ledger()
    
    # Check if date already graded to avoid duplicates
    already_graded = {e["date"] + e["away"] + e["home"] for e in ledger}
    new_entries = []

    for game in games_to_grade:
        away = game.get("away", {}).get("name", "").upper()
        home = game.get("home", {}).get("name", "").upper()
        tier = game.get("tier", "NONE")
        edge_str = game.get("edge", "+0.0%")

        if not away or not home:
            continue

        # Skip NONE tier games (no qualifying pick)
        if tier == "NONE":
            print(f"  Skipping {away} @ {home} — tier=NONE")
            continue

        entry_key = target_date_str + away + home
        if entry_key in already_graded:
            print(f"  Already graded: {away} @ {home} on {target_date_str}")
            continue

        actual = match_game(away, home, actual_scores)
        if not actual:
            print(f"  Could not match {away} @ {home} in actual scores!")
            continue

        covers = game.get("details", {}).get("covers", {})
        best_angle = game.get("details", {}).get("best_angle", {})

        ml_pick     = covers.get("best_ml", "")
        spread_pick = covers.get("best_spread", "")
        ou_pick     = covers.get("best_ou", "")

        ml_result     = grade_ml(ml_pick, actual)
        spread_result = grade_spread(spread_pick, actual)
        ou_result     = grade_ou(ou_pick, actual)
        edge_result   = grade_edge(best_angle, actual)

        # Parse edge % as float
        try:
            edge_pct = float(edge_str.replace("%", "").replace("+", ""))
        except Exception:
            edge_pct = 0.0

        # Units delta = average of all graded plays
        results = [r for r in [ml_result, spread_result, ou_result] if r in ("W", "L")]
        if results:
            units_delta = sum(1 if r == "W" else -1 for r in results) / len(results)
        else:
            units_delta = 0.0

        entry = {
            "date":         target_date_str,
            "away":         away,
            "home":         home,
            "tier":         tier,
            "edge_pct":     edge_pct,
            "units_delta":  round(units_delta, 2),
            "ml_pick":      ml_pick,
            "spread_pick":  spread_pick,
            "ou_pick":      ou_pick,
            "edge_play":    best_angle.get("play", ""),
            "actual":       f"{away} {actual['away_score']}-{actual['home_score']} {home}",
            "ml":           ml_result,
            "spread":       spread_result,
            "ou":           ou_result,
            "edge":         edge_result,
        }

        print(f"\n  {away} {actual['away_score']}-{actual['home_score']} {home}  [tier={tier}]")
        print(f"    ML  : {ml_pick:20s} → {ml_result}")
        print(f"    SPR : {spread_pick:20s} → {spread_result}")
        print(f"    O/U : {ou_pick:20s} → {ou_result}")
        print(f"    EDGE: {best_angle.get('play',''):20s} → {edge_result}")

        new_entries.append(entry)

    if not new_entries:
        print("\n  Nothing new to record.")
    else:
        ledger.extend(new_entries)
        save_ledger(ledger)
        print(f"\n  Added {len(new_entries)} new record(s) to ledger.")

    # ── 4. Rebuild historical_stats.json ─────────────────────────────────────
    print(f"\n[4] Rebuilding historical_stats.json...")
    hist = build_historical_stats(ledger)

    HIST_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(HIST_OUT, "w") as f:
        json.dump(hist, f, indent=2)
    print(f"  Saved → {HIST_OUT}")

    # ── 5. Summary ────────────────────────────────────────────────────────────
    overall = hist["all_time"]["overall"]
    print(f"\n{'='*55}")
    print(f"  ALL TIME  {overall['wins']}W-{overall['losses']}L  "
          f"({overall['win_rate']})  Avg Edge: {overall['avg_edge']}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
