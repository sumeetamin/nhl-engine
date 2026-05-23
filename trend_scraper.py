import pandas as pd
import os

def fetch_game_notes(away_team, home_team):
    print(f"🔍 Generating Sumeet's Proprietary Insights: {away_team} @ {home_team}...")
    notes = []
    
    # 1. Base Model Insights
    notes.append(f"Sumeet's Engine projects value on the {home_team} Moneyline based on rolling xGF%.")
    notes.append(f"Expected Goalie Matchup: {away_team} vs {home_team}.")

    # 2. Data-Driven Trends from our local MoneyPuck database
    file_path = "moneypuck_advanced_stats.csv"
    
    if not os.path.exists(file_path):
        print("  [!] MoneyPuck data not found. Skipping advanced trends.")
        return notes

    try:
        # Load the advanced stats
        df = pd.read_csv(file_path)
        
        def get_team_metrics(team):
            # Filter for the specific team's games
            team_games = df[df['team'] == team].copy()
            if team_games.empty: return None
            
            # Sort by date descending to get the most recent games
            if 'gameDate' in team_games.columns:
                team_games = team_games.sort_values('gameDate', ascending=False)
                
            last_5 = team_games.head(5)
            
            # Calculate rolling metrics safely
            avg_xgf = last_5['xGoalsPercentage'].mean() if 'xGoalsPercentage' in last_5.columns else 0.5
            goals_for = last_5['goalsFor'].sum() if 'goalsFor' in last_5.columns else 0
            goals_against = last_5['goalsAgainst'].sum() if 'goalsAgainst' in last_5.columns else 0
            
            return {
                "avg_xgf": avg_xgf,
                "gf": goals_for,
                "ga": goals_against
            }

        home_stats = get_team_metrics(home_team)
        away_stats = get_team_metrics(away_team)

        # 3. Generate dynamic text based on the math
        if home_stats:
            # Possession Dominance Trend
            if home_stats['avg_xgf'] > 0.53:
                notes.append(f"{home_team} is dominating possession, controlling {home_stats['avg_xgf']*100:.1f}% of Expected Goals in their last 5 games.")
            elif home_stats['avg_xgf'] < 0.47:
                notes.append(f"{home_team} is struggling defensively, controlling only {home_stats['avg_xgf']*100:.1f}% of Expected Goals recently.")
            
            # Scoring Trend
            if home_stats['gf'] > home_stats['ga']:
                notes.append(f"{home_team} is outscoring opponents {home_stats['gf']}-{home_stats['ga']} at 5-on-5 over their last 5 games.")

        if away_stats:
            # Away Team Analysis
            if away_stats['avg_xgf'] > 0.52:
                notes.append(f"{away_team} carries strong underlying metrics ({away_stats['avg_xgf']*100:.1f}% xGF) despite playing on the road.")
            elif away_stats['avg_xgf'] < 0.48:
                notes.append(f"{away_team} is failing to generate high-danger chances ({away_stats['avg_xgf']*100:.1f}% xGF in L5).")

    except Exception as e:
        print(f"  [!] Failed to generate data trends: {e}")

    # 4. Limit to the top 4 notes for a clean UI
    final_notes = list(dict.fromkeys(notes))[:4] # deduplicate while preserving order
    
    print(f"  ✅ Generated {len(final_notes)} proprietary game notes.")
    return final_notes

if __name__ == "__main__":
    print("\nTesting Proprietary Trend Generator...")
    trends = fetch_game_notes("VGK", "COL")
    for t in trends:
        print(f" - {t}")