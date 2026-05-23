import requests
import json
import pandas as pd
from datetime import datetime

# Map ESPN's abbreviations back to our model's official NHL API abbreviations
TEAM_MAP = {
    "ANA": "ANA", "ARI": "UTA", "BOS": "BOS", "BUF": "BUF", "CGY": "CGY",
    "CAR": "CAR", "CHI": "CHI", "COL": "COL", "CBJ": "CBJ", "DAL": "DAL",
    "DET": "DET", "EDM": "EDM", "FLA": "FLA", "LAK": "LAK", "MIN": "MIN",
    "MTL": "MTL", "NSH": "NSH", "NJ": "NJD",  "NYI": "NYI", "NYR": "NYR",
    "OTT": "OTT", "PHI": "PHI", "PIT": "PIT", "SJ": "SJS",  "SEA": "SEA",
    "STL": "STL", "TB": "TBL",  "TOR": "TOR", "VAN": "VAN", "VGK": "VGK",
    "WSH": "WSH", "WPG": "WPG", "UTA": "UTA" 
}

def fetch_espn_goalies():
    print(f"🏒 Fetching today's goalies via ESPN API...")
    
    # 1. Get today's scoreboard to find game IDs
    today = datetime.now().strftime("%Y%m%d")
    scoreboard_url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={today}"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(scoreboard_url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"❌ Failed to fetch ESPN scoreboard: {e}")
        return pd.DataFrame()

    games = data.get("events", [])
    if not games:
        print("⚠️ No NHL games scheduled for today according to ESPN.")
        return pd.DataFrame()

    games_data = []

    # 2. Loop through each game and get the starting goalies
    for game in games:
        try:
            game_id = game["id"]
            
            # The competitions array holds the team data
            competitors = game["competitions"][0]["competitors"]
            
            # ESPN puts home team at index 0 and away at index 1 usually, but let's check homeAway flag
            home_team_data = next(c for c in competitors if c["homeAway"] == "home")
            away_team_data = next(c for c in competitors if c["homeAway"] == "away")
            
            home_team_raw = home_team_data["team"]["abbreviation"].upper()
            away_team_raw = away_team_data["team"]["abbreviation"].upper()
            
            home_team = TEAM_MAP.get(home_team_raw, home_team_raw)
            away_team = TEAM_MAP.get(away_team_raw, away_team_raw)
            
            # 3. Fetch specific game matchup data for goalies
            matchup_url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event={game_id}"
            m_res = requests.get(matchup_url, headers=headers, timeout=5)
            m_data = m_res.json()
            
            home_goalie = "TBD"
            home_status = "Unconfirmed"
            away_goalie = "TBD"
            away_status = "Unconfirmed"
            
            # ESPN stores starting goalies in the boxscore -> players section if available before puck drop
            boxscore = m_data.get("boxscore", {}).get("players", [])
            for team_box in boxscore:
                is_home = team_box["team"]["abbreviation"].upper() == home_team_raw
                
                # Check statistics for goalies
                stats = team_box.get("statistics", [])
                goalie_stats = next((s for s in stats if s["name"] == "goaltending"), None)
                
                if goalie_stats:
                    athletes = goalie_stats.get("athletes", [])
                    if athletes:
                        # The first athlete listed in goaltending is usually the starter
                        starter = athletes[0]["athlete"]["shortName"]
                        if is_home:
                            home_goalie = starter
                            home_status = "Expected" # ESPN doesn't strictly define confirmed vs expected via API easily
                        else:
                            away_goalie = starter
                            away_status = "Expected"
            
            games_data.append({
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Away_Team": away_team,
                "Home_Team": home_team,
                "Away_Goalie": away_goalie,
                "Away_Status": away_status,
                "Home_Goalie": home_goalie,
                "Home_Status": home_status
            })
            
        except Exception as e:
            continue

    df = pd.DataFrame(games_data)
    
    if not df.empty:
        df.to_json("today_goalies.json", orient="records", indent=4)
        print(f"✅ Successfully fetched {len(df)} games and saved to 'today_goalies.json'.")
        print("\nPreview:")
        print(df[["Away_Team", "Away_Goalie", "Home_Team", "Home_Goalie"]])
    else:
        print("⚠️ Could not parse any games from the API.")
        
    return df

if __name__ == "__main__":
    fetch_espn_goalies()