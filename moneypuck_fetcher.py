import pandas as pd
import requests
import io

def fetch_moneypuck_data():
    print("🏒 Fetching latest advanced stats from MoneyPuck...")
    
    # Updated: The correct active URL for MoneyPuck's master team stats file
    url = "https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to download MoneyPuck data: {e}")
        return pd.DataFrame()
        
    print("✅ Downloaded MoneyPuck dataset. Parsing advanced stats...")
    
    # Read the CSV string directly into pandas
    df = pd.read_csv(io.StringIO(response.text))
    
    # Filter for the current active season (2025 represents the 2025-2026 season)
    current_season = 2025
    df_current = df[df['season'] == current_season].copy()
    
    if df_current.empty:
        # Fallback in case their season integer hasn't rolled over
        current_season = df['season'].max()
        df_current = df[df['season'] == current_season].copy()
        
    print(f"📊 Filtering for season: {current_season}-{current_season+1}")
    
    # Filter for 5-on-5 situations (The most predictive state for Machine Learning)
    df_5v5 = df_current[df_current['situation'] == '5on5'].copy()
    
    # Clean up the date column and sort so the newest games are at the top
    df_5v5['gameDate'] = pd.to_datetime(df_5v5['gameDate'].astype(str), format='%Y%m%d', errors='coerce')
    df_5v5 = df_5v5.sort_values('gameDate', ascending=False)
    
    # We only extract the core possession/luck metrics needed for our ML proxies
    cols_to_keep = [
        'team', 'gameDate', 'opposingTeam',
        'xGoalsPercentage', 'corsiPercentage', 'fenwickPercentage',
        'goalsFor', 'goalsAgainst', 'xGoalsFor', 'xGoalsAgainst'
    ]
    
    # Keep columns that actually exist to avoid KeyErrors
    existing_cols = [c for c in cols_to_keep if c in df_5v5.columns]
    final_df = df_5v5[existing_cols]
    
    # Save to a local CSV for the main ML engine to consume
    filename = "moneypuck_advanced_stats.csv"
    final_df.to_csv(filename, index=False)
    
    print(f"✅ Successfully processed {len(final_df)} team games.")
    print(f"💾 Saved to '{filename}'.")
    print("\nPreview of the most recent games:")
    print(final_df[['team', 'opposingTeam', 'xGoalsPercentage', 'corsiPercentage']].head(5))
    
    return final_df

if __name__ == "__main__":
    fetch_moneypuck_data()