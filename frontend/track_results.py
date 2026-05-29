import json
import os
import requests
from datetime import datetime, timedelta

def grade_yesterdays_bets():
    print(f"📊 [{datetime.now().strftime('%I:%M %p')}] Initializing Auto-Grader...")
    
    # Locate the public directory automatically
    base_dir = os.path.dirname(os.path.abspath(__file__))
    public_dir = os.path.join(base_dir, "public")
    
    predictions_file = os.path.join(public_dir, "daily_predictions.json")
    stats_file = os.path.join(public_dir, "historical_stats.json")
    
    # 1. Ensure files exist before attempting to grade
    if not os.path.exists(predictions_file) or not os.path.exists(stats_file):
        print("⚠️ Missing JSON files. Skipping grading for today.")
        return

    with open(predictions_file, 'r') as f:
        daily_data = json.load(f)
        
    with open(stats_file, 'r') as f:
        stats_data = json.load(f)

    # 2. Fetch Actual Results from the NHL API for Yesterday
    yesterday_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"🔄 Fetching official NHL results for {yesterday_date}...")
    
    url = f"https://api-web.nhle.com/v1/score/{yesterday_date}"
    try:
        response = requests.get(url, timeout=10).json()
        games = response.get('gameWeek', [{}])[0].get('games', []) if 'gameWeek' in response else []
    except Exception as e:
        print(f"❌ Failed to reach NHL API: {e}")
        return

    # Map actual winners based on final scores
    actual_winners = {}
    for game in games:
        if game.get('gameState') in ['FINAL', 'OFF']:
            home = game['homeTeam']['abbrev']
            away = game['awayTeam']['abbrev']
            home_score = game['homeTeam']['score']
            away_score = game['awayTeam']['score']
            
            # Identify the real winner
            winner = home if home_score > away_score else away
            actual_winners[f"{away}@{home}"] = winner

    if not actual_winners:
        print("⏸️ No completed games found for yesterday (or API hasn't finalized them).")
        return

    # 3. Grade the Engine's Top Plays
    top_plays = daily_data.get('top_plays', [])
    daily_wins = 0
    daily_losses = 0
    
    for play in top_plays:
        home_team = play['home']['name']
        away_team = play['away']['name']
        predicted_winner = play['predicted_winner']
        
        game_key = f"{away_team}@{home_team}"
        
        if game_key in actual_winners:
            if predicted_winner == actual_winners[game_key]:
                daily_wins += 1
            else:
                daily_losses += 1

    print(f"✅ Grading Complete: {daily_wins} Wins, {daily_losses} Losses.")

    # 4. Update the Historical Ledger (Initialize keys if it's currently a blank template)
    if "all_time" not in stats_data:
        stats_data["all_time"] = {"wins": 0, "losses": 0, "win_rate": "0.0%", "total_units": 0.0}
        
    stats_data["all_time"]["wins"] += daily_wins
    stats_data["all_time"]["losses"] += daily_losses
    
    # Calculate updated Win Rate
    total_graded = stats_data["all_time"]["wins"] + stats_data["all_time"]["losses"]
    if total_graded > 0:
        win_rate = (stats_data["all_time"]["wins"] / total_graded) * 100
        stats_data["all_time"]["win_rate"] = f"{win_rate:.1f}%"
        
        # Simple Unit Tracking (Assuming 1 Unit per play)
        stats_data["all_time"]["total_units"] = round((stats_data["all_time"]["wins"] * 0.9) - daily_losses, 2) 

    # 5. Save the updated ledger back to the JSON file
    try:
        with open(stats_file, 'w') as f:
            json.dump(stats_data, f, indent=4)
        print("💾 historical_stats.json successfully updated with live records.")
    except Exception as e:
        print(f"❌ Failed to save stats: {e}")

if __name__ == "__main__":
    grade_yesterdays_bets()