import requests
import pandas as pd
from datetime import datetime, timedelta
import time

def fetch_real_nhl_results(days_back=30):
    print(f"📡 Connecting to NHL API... fetching last {days_back} days of real data.")
    data = []

    # Loop backward through the last X days
    for i in range(1, days_back + 1):
        target_date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        url = f"https://api-web.nhle.com/v1/score/{target_date}"

        try:
            response = requests.get(url)
            if response.status_code == 200:
                json_data = response.json()
                # The API returns a 'games' array for the given date
                games = json_data.get('games', [])

                for game in games:
                    away_team = game['awayTeam']['abbrev']
                    away_score = game['awayTeam'].get('score', 0)
                    home_team = game['homeTeam']['abbrev']
                    home_score = game['homeTeam'].get('score', 0)

                    # If both scores are 0, the game was likely postponed or not played
                    if away_score == 0 and home_score == 0:
                        continue 

                    # Determine the actual winner mathematically
                    actual_winner = away_team if away_score > home_score else home_team

                    data.append({
                        "Date": target_date,
                        "Away": away_team,
                        "Home": home_team,
                        "Actual_Winner": actual_winner
                    })
            
            # Brief pause so we don't spam the NHL servers and get blocked
            time.sleep(0.2)
            
        except Exception as e:
            print(f"⚠️ Error fetching data for {target_date}: {e}")

    # Save the fresh data to your CSV
    if data:
        df = pd.DataFrame(data)
        df = df.sort_values(by='Date', ascending=False)
        df.to_csv("past_games.csv", index=False)
        print(f"✅ Successfully scraped and saved {len(df)} real NHL games to past_games.csv!")
    else:
        print("⚠️ No game data found for this period.")

if __name__ == "__main__":
    fetch_real_nhl_results()