import requests

# Check specifically for May 22, 2026 (a known playoff date)
date_to_check = "2026-05-22"
url = f"https://api-web.nhle.com/v1/score/{date_to_check}"

try:
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    res.raise_for_status()
    data = res.json()
    
    print(f"✅ Successfully connected to API for {date_to_check}")
    # Print the first few games to see their status
    games = data.get("games", [])
    print(f"Found {len(games)} games.")
    for game in games:
        home = game["homeTeam"]["abbrev"]
        away = game["awayTeam"]["abbrev"]
        state = game.get("gameState", "Unknown")
        print(f"Game: {away} @ {home} | Status: {state}")
except Exception as e:
    print(f"❌ Error: {e}")