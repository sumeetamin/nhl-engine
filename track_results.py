import json
import os
import csv
import time
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ── 1. REPOSITORY-RELATIVE DATA PATHS ─────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "frontend", "public")
HISTORY_PATH = os.path.join(PUBLIC_DIR, "past_games.csv")
TEAM_ABBREVS = (
    "ANA", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ", "DAL", "DET",
    "EDM", "FLA", "LAK", "MIN", "MTL", "NSH", "NJD", "NYI", "NYR", "OTT",
    "PHI", "PIT", "SJS", "SEA", "STL", "TBL", "TOR", "UTA", "VAN", "VGK",
    "WSH", "WPG",
)
HISTORY_FIELDS = ["Date", "Away", "Home", "Actual_Winner", "Away_Score", "Home_Score"]
EASTERN = ZoneInfo("America/New_York")

DB_PATH = os.path.join(BASE_DIR, "graded_picks_db.json")
PREDICTIONS_PATH = os.path.join(PUBLIC_DIR, "daily_predictions.json")
FRONTEND_PATH = os.path.join(PUBLIC_DIR, "historical_stats.json")


# ── 2. UNIT PAYOUT CALCULATION UTILITIES ──────────────────────────────────────
def calculate_ml_units(odds_str, won):
    """Parses American odds string to compute exact unit payout changes."""
    try:
        odds = int(odds_str.replace("+", ""))
        if won:
            return round(odds / 100, 2) if odds > 0 else round(100 / abs(odds), 2)
        else:
            return -1.0
    except Exception:
        return 0.0

def calculate_ou_units(won, push=False):
    """Standard Over/Under juice lines generally track at -110 market baseline."""
    if push: return 0.0
    return 0.91 if won else -1.0


# ── 3. TIME AND UTILITY HELPERS ───────────────────────────────────────────────
def get_yesterday_est_str():
    return (datetime.now(EASTERN).date() - timedelta(days=1)).isoformat()

def load_json_file(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}


def _game_to_history_row(game):
    """Return a completed NHL schedule game in the model's canonical CSV schema."""
    if game.get("gameState") not in {"OFF", "FINAL", "CRIT"}:
        return None
    home = game.get("homeTeam", {})
    away = game.get("awayTeam", {})
    date = game.get("gameDate")
    if not date or not home.get("abbrev") or not away.get("abbrev"):
        return None
    try:
        home_score = int(home["score"])
        away_score = int(away["score"])
    except (KeyError, TypeError, ValueError):
        return None
    if home_score == away_score:
        return None
    return {
        "Date": date[:10], "Away": away["abbrev"], "Home": home["abbrev"],
        "Actual_Winner": home["abbrev"] if home_score > away_score else away["abbrev"],
        "Away_Score": away_score, "Home_Score": home_score,
    }


def _read_history(path=HISTORY_PATH):
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as history_file:
        rows = csv.DictReader(history_file)
        return {
            (row.get("Date", ""), row.get("Away", ""), row.get("Home", "")): row
            for row in rows
            if row.get("Date") and row.get("Away") and row.get("Home")
        }


def _write_history(rows, path=HISTORY_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as history_file:
        writer = csv.DictWriter(history_file, fieldnames=HISTORY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(rows.values(), key=lambda row: (row["Date"], row["Away"], row["Home"])))


def merge_final_games(games, path=HISTORY_PATH):
    """Upsert completed schedule games by date and matchup; safe to rerun."""
    history = _read_history(path)
    before = len(history)
    changed = False
    for game in games:
        row = _game_to_history_row(game)
        if row:
            key = (row["Date"], row["Away"], row["Home"])
            if history.get(key) != row:
                history[key] = row
                changed = True
    if changed:
        _write_history(history, path)
    return len(history) - before


def _previous_nhl_season(now=None):
    now = now or datetime.now(EASTERN)
    current_start_year = now.year if now.month >= 7 else now.year - 1
    return f"{current_start_year - 1}{current_start_year:04d}"


def bootstrap_previous_season(path=HISTORY_PATH, get=requests.get):
    """Fill a missing history baseline from the official completed-season club logs.

    The 32 API calls happen only while the stored history has fewer than 500 games;
    a complete baseline is committed by the workflow and won't be fetched daily.
    """
    history = _read_history(path)
    if len(history) >= 500:
        return 0

    season = _previous_nhl_season()
    season_rows = {}
    failed_teams = []
    for team in TEAM_ABBREVS:
        url = f"https://api-web.nhle.com/v1/club-schedule-season/{team}/{season}"
        try:
            response = get(url, timeout=15)
            response.raise_for_status()
            games = response.json().get("games", [])
            for game in games:
                row = _game_to_history_row(game)
                if row:
                    season_rows[(row["Date"], row["Away"], row["Home"])] = row
        except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
            failed_teams.append(team)
            print(f"⚠️ Could not load {team} {season} schedule: {exc}")
        time.sleep(0.15)

    # Do not install a partial season snapshot: retry on the next tracker run.
    if failed_teams:
        print(f"⚠️ Season history bootstrap incomplete ({len(failed_teams)} teams); preserving existing CSV.")
        return 0
    if len(season_rows) < 500:
        print(f"⚠️ Season history returned only {len(season_rows)} completed games; preserving existing CSV.")
        return 0

    before = len(history)
    history.update(season_rows)
    _write_history(history, path)
    added = len(history) - before
    print(f"✅ Seeded history from {season}: {len(season_rows)} completed games ({added} added).")
    return added


def fetch_schedule_games(date_str, get=requests.get):
    url = f"https://api-web.nhle.com/v1/schedule/{date_str}"
    response = get(url, timeout=15)
    response.raise_for_status()
    day = next((item for item in response.json().get("gameWeek", []) if item.get("date") == date_str), None)
    if day is None:
        raise ValueError(f"NHL schedule response omitted {date_str}")
    return day.get("games", [])


# ── 4. THE AUTOMATED GRADER ───────────────────────────────────────────────────
def auto_grade_yesterday():
    yesterday_str = get_yesterday_est_str()
    print(f"Checking results for sports date: {yesterday_str}")

    # Query official NHL Schedule API for final game data
    try:
        games_list = fetch_schedule_games(yesterday_str)
    except Exception as e:
        print(f"❌ Failed to reach NHL Schedule API: {e}")
        return

    # Bootstrap a complete model baseline once, then incorporate each day's final scores.
    bootstrap_previous_season()
    added = merge_final_games(games_list)
    print(f"📚 Model game history refreshed ({added} newly completed games).")

    predictions_payload = load_json_file(PREDICTIONS_PATH)
    yesterday_predictions = predictions_payload.get("yesterday", [])
    if not yesterday_predictions:
        print("⚠️ No predictions discovered for yesterday inside daily_predictions.json. Skipping grading.")
        return

    db = load_json_file(DB_PATH)
    db_updated = False

    for pred in yesterday_predictions:
        home = pred["home"]["name"]
        away = pred["away"]["name"]
        game_id = f"{yesterday_str}_{home}_{away}"

        # Locate match details inside the API payload
        api_game = next((g for g in games_list if g["homeTeam"]["abbrev"] == home and g["awayTeam"]["abbrev"] == away), None)
        
        if not api_game:
            continue
        
        # Verify the game state is complete
        if api_game.get("gameState") not in ["OFF", "FINAL"]:
            print(f"⏳ Game {game_id} is not marked completed yet ({api_game.get('gameState')}). Skipping.")
            continue

        home_score = api_game["homeTeam"].get("score", 0)
        away_score = api_game["awayTeam"].get("score", 0)
        actual_winner = home if home_score > away_score else away
        total_goals = home_score + away_score

        # A. Grade Moneyline Market
        predicted_winner = pred["predicted_winner"]
        ml_won = predicted_winner == actual_winner
        ml_res = "W" if ml_won else "L"
        chosen_odds = pred["home"]["ml"] if predicted_winner == home else pred["away"]["ml"]
        ml_units = calculate_ml_units(chosen_odds, ml_won)

        # B. Grade Over/Under Market
        best_ou = pred["details"]["covers"]["best_ou"]
        ou_res, ou_units = "P", 0.0 # Default state
        
        if "OVER" in best_ou:
            target_line = float(best_ou.replace("OVER ", ""))
            if total_goals > target_line:
                ou_res, ou_units = "W", calculate_ou_units(won=True)
            elif total_goals < target_line:
                ou_res, ou_units = "L", calculate_ou_units(won=False)
        elif "UNDER" in best_ou:
            target_line = float(best_ou.replace("UNDER ", ""))
            if total_goals < target_line:
                ou_res, ou_units = "W", calculate_ou_units(won=True)
            elif total_goals > target_line:
                ou_res, ou_units = "L", calculate_ou_units(won=False)

        # C. Grade Spread Market (Fallback to Pass if not explicitly evaluated)
        best_spread = pred["details"]["covers"]["best_spread"]
        spread_res, spread_units = "P", 0.0

        # Idempotent write operation using unique game composite key
        db[game_id] = {
            "date": yesterday_str,
            "ml": {"result": ml_res, "units": ml_units},
            "spread": {"result": spread_res, "units": spread_units},
            "ou": {"result": ou_res, "units": ou_units}
        }
        db_updated = True
        print(f"🎯 Graded {game_id} -> ML: {ml_res} ({ml_units} U) | O/U: {ou_res} ({ou_units} U)")

    if db_updated:
        with open(DB_PATH, "w") as f:
            json.dump(db, f, indent=4)
        build_frontend_stats()


# ── 5. THE MATH AGGREGATOR ────────────────────────────────────────────────────
def build_frontend_stats():
    db = load_json_file(DB_PATH)
    
    def empty_stats():
        return {
            "ml": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0},
            "spread": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0},
            "ou": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0},
        }

    stats = {
        "all_time": empty_stats(),
        "this_month": empty_stats(),
        "this_week": empty_stats(),
        "yesterday": empty_stats(),
    }
    
    today = datetime.now()
    
    for game_id, data in db.items():
        game_date = datetime.strptime(data["date"], "%Y-%m-%d")
        days_ago = (today - game_date).days
        
        timeframes = ["all_time"]
        if days_ago <= 30: timeframes.append("this_month")
        if days_ago <= 7:  timeframes.append("this_week")
        if days_ago == 1:  timeframes.append("yesterday")
        
        for tf in timeframes:
            for market in ["ml", "spread", "ou"]:
                res = data[market]["result"]
                if res == "W": stats[tf][market]["wins"] += 1
                elif res == "L": stats[tf][market]["losses"] += 1
                elif res == "P": stats[tf][market]["pushes"] += 1
                
                stats[tf][market]["units"] += data[market]["units"]

    for tf, data in stats.items():
        o_wins = data["ml"]["wins"] + data["spread"]["wins"] + data["ou"]["wins"]
        o_losses = data["ml"]["losses"] + data["spread"]["losses"] + data["ou"]["losses"]
        o_pushes = data["ml"]["pushes"] + data["spread"]["pushes"] + data["ou"]["pushes"]
        o_units = data["ml"]["units"] + data["spread"]["units"] + data["ou"]["units"]
        
        data["overall"] = {
            "wins": o_wins, "losses": o_losses, "pushes": o_pushes, "units": round(o_units, 2)
        }
        
        for m in ["ml", "spread", "ou", "overall"]:
            w, l = data[m]["wins"], data[m]["losses"]
            rate = (w / (w + l) * 100) if (w + l) > 0 else 0
            data[m]["win_rate"] = f"{round(rate, 1)}%"
            data[m]["units"] = str(round(float(data[m]["units"]), 2))

    with open(FRONTEND_PATH, "w") as f:
        json.dump(stats, f, indent=4)
    print("🚀 Rebuilt frontend stats manifest cleanly without duplicates.")


if __name__ == "__main__":
    auto_grade_yesterday()

