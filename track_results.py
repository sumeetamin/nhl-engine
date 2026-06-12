import json
import os
import requests
from datetime import datetime, timedelta, timezone

# ── 1. ENVIRONMENT-AWARE ADAPTIVE PATHS ───────────────────────────────────────
IS_GITHUB = "GITHUB_ACTIONS" in os.environ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if IS_GITHUB:
    DB_PATH = os.path.join(BASE_DIR, "graded_picks_db.json")
    PREDICTIONS_PATH = os.path.join(BASE_DIR, "frontend", "public", "daily_predictions.json")
    FRONTEND_PATH = os.path.join(BASE_DIR, "frontend", "public", "historical_stats.json")
else:
    DB_PATH = "graded_picks_db.json"
    PREDICTIONS_PATH = r"C:\Users\amins\OneDrive\Desktop\NHL\frontend\public\daily_predictions.json"
    FRONTEND_PATH = r"C:\Users\amins\OneDrive\Desktop\NHL\frontend\public\historical_stats.json"


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
    est = datetime.now(timezone.utc) - timedelta(hours=4)
    yesterday = est - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")

def load_json_file(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}


# ── 4. THE AUTOMATED GRADER ───────────────────────────────────────────────────
def auto_grade_yesterday():
    yesterday_str = get_yesterday_est_str()
    print(f"Checking results for sports date: {yesterday_str}")

    predictions_payload = load_json_file(PREDICTIONS_PATH)
    yesterday_predictions = predictions_payload.get("yesterday", [])
    
    if not yesterday_predictions:
        print("⚠️ No predictions discovered for yesterday inside daily_predictions.json. Skipping grading.")
        return

    # Query official NHL Schedule API for final game data
    url = f"https://api-web.nhle.com/v1/schedule/{yesterday_str}"
    try:
        response = requests.get(url, timeout=10).json()
        games_list = next((day['games'] for day in response.get('gameWeek', []) if day['date'] == yesterday_str), [])
    except Exception as e:
        print(f"❌ Failed to reach NHL Schedule API: {e}")
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