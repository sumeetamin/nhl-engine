import json
import requests
import os
from datetime import datetime, timedelta

# Map NHL API team abbreviations to our model's standard
TEAM_MAP = {
    "ANA": "ANA", "ARI": "UTA", "BOS": "BOS", "BUF": "BUF", "CGY": "CGY",
    "CAR": "CAR", "CHI": "CHI", "COL": "COL", "CBJ": "CBJ", "DAL": "DAL",
    "DET": "DET", "EDM": "EDM", "FLA": "FLA", "LAK": "LAK", "MIN": "MIN",
    "MTL": "MTL", "NSH": "NSH", "NJD": "NJD", "NYI": "NYI", "NYR": "NYR",
    "OTT": "OTT", "PHI": "PHI", "PIT": "PIT", "SJS": "SJS", "SEA": "SEA",
    "STL": "STL", "TBL": "TBL", "TOR": "TOR", "VAN": "VAN", "VGK": "VGK",
    "WSH": "WSH", "WPG": "WPG", "UTA": "UTA"
}

def fetch_yesterdays_scores(date_str):
    """Fetches final scores from the official NHL API for a given date (YYYY-MM-DD)"""
    url = f"https://api-web.nhle.com/v1/score/{date_str}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"❌ Failed to fetch NHL scores: {e}")
        return {}

    results = {}
    for game in data.get("games", []):
        # Only process completed games
        if game.get("gameState") in ["FINAL", "OFF"]:
            home = TEAM_MAP.get(game["homeTeam"]["abbrev"])
            away = TEAM_MAP.get(game["awayTeam"]["abbrev"])
            
            home_score = game["homeTeam"].get("score", 0)
            away_score = game["awayTeam"].get("score", 0)
            
            winner = home if home_score > away_score else away
            total_goals = home_score + away_score
            
            # Create a unique key matching our prediction ID format
            game_id = f"{away}_at_{home}_{date_str.replace('-', '')}"
            
            results[game_id] = {
                "actual_winner": winner,
                "actual_total": total_goals,
                "home_score": home_score,
                "away_score": away_score
            }
            
    return results

def grade_predictions():
    # 1. Get Yesterday's Date
    yesterday_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"📊 [AUDITOR] Grading predictions for {yesterday_date}...")

    # 2. Load yesterday's predictions
    # Note: In production, the Heartbeat script should save files by date (e.g., predictions_2026-05-22.json)
    # For now, we'll look at daily_predictions.json
    try:
        with open("daily_predictions.json", "r") as f:
            predictions_payload = json.load(f)
    except FileNotFoundError:
        print("❌ ERROR: daily_predictions.json not found. Nothing to grade.")
        return

    # 3. Load or Initialize the Ledger
    ledger_file = "model_records_ledger.json"
    if os.path.exists(ledger_file):
        with open(ledger_file, "r") as f:
            ledger = json.load(f)
    else:
        ledger = {
            "moneyline": {"wins": 0, "losses": 0, "win_pct": 0.0},
            "history": []
        }

    # 4. Fetch Actual Scores
    actual_scores = fetch_yesterdays_scores(yesterday_date)
    if not actual_scores:
        print("⚠️ No completed games found for yesterday or API failed.")
        return

    games_graded = 0
    new_wins = 0
    new_losses = 0

    # 5. Grade the Homework
    for game in predictions_payload.get("games", []):
        game_id = game["id"]
        
        # If the game in our prediction file matches a completed game from the API
        if game_id in actual_scores:
            projected = game["predictions"]["projected_winner"]
            actual = actual_scores[game_id]["actual_winner"]
            
            is_win = (projected == actual)
            
            if is_win:
                new_wins += 1
                ledger["moneyline"]["wins"] += 1
            else:
                new_losses += 1
                ledger["moneyline"]["losses"] += 1
                
            # Log the individual result
            ledger["history"].append({
                "date": yesterday_date,
                "game_id": game_id,
                "projected": projected,
                "actual": actual,
                "result": "WIN" if is_win else "LOSS",
                "tier": game["predictions"]["tier"]
            })
            games_graded += 1

    # 6. Update Overall Win %
    total_ml_bets = ledger["moneyline"]["wins"] + ledger["moneyline"]["losses"]
    if total_ml_bets > 0:
        ledger["moneyline"]["win_pct"] = round((ledger["moneyline"]["wins"] / total_ml_bets) * 100, 2)

    # 7. Save the Ledger
    with open(ledger_file, "w") as f:
        json.dump(ledger, f, indent=4)

    print(f"✅ Graded {games_graded} games.")
    print(f"📈 Daily Result: {new_wins}W - {new_losses}L")
    print(f"🏆 Overall ML Record: {ledger['moneyline']['wins']}W - {ledger['moneyline']['losses']}L ({ledger['moneyline']['win_pct']}%)")
    print(f"💾 Ledger successfully updated -> {ledger_file}")

if __name__ == "__main__":
    grade_predictions()