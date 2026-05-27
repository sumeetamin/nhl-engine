import pandas as pd
import random
from datetime import datetime, timedelta

def generate_past_schedule():
    teams = ["COL", "VGK", "NYR", "FLA", "DAL", "EDM", "BOS", "TOR", "CAR", "TBL", "VAN", "WPG"]
    
    data = []
    # Generate 50 games over the last 30 days
    for i in range(50):
        days_ago = random.randint(1, 30)
        game_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        
        # Pick two random teams
        matchup = random.sample(teams, 2)
        away = matchup[0]
        home = matchup[1]
        
        # Randomly decide who actually won the game in real life
        actual_winner = random.choice([away, home])
        
        data.append({
            "Date": game_date,
            "Away": away,
            "Home": home,
            "Actual_Winner": actual_winner
        })
        
    df = pd.DataFrame(data)
    # Sort chronologically
    df = df.sort_values(by='Date', ascending=False)
    
    # Save to CSV
    df.to_csv("past_games.csv", index=False)
    print("✅ Successfully generated 'past_games.csv' with 50 historical matchups!")

if __name__ == "__main__":
    generate_past_schedule()