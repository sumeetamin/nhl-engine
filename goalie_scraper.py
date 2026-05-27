import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_starting_goalies():
    print(f"🏒 [{datetime.now().strftime('%I:%M %p')}] Connecting to DailyFaceoff...")
    
    url = "https://www.dailyfaceoff.com/starting-goalies"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        todays_goalies = {}

        # The new DailyFaceoff structure puts matchups in an 'article' tag
        matchups = soup.find_all('article')
        
        if not matchups:
            print("⚠️ Could not find the main game blocks. Let's try the fallback class.")
            # Fallback based on your snippet
            matchups = soup.find_all('div', class_=lambda x: x and 'xl:flex-row-reverse' in x)

        for game in matchups:
            # Inside the game block, goalies are in spans with text-lg or text-2xl
            goalie_spans = game.find_all('span', class_=lambda x: x and ('text-lg' in x or 'text-2xl' in x))
            
            # The status is kept in a div with text-green-700 (Confirmed) or text-yellow/red (Expected)
            status_divs = game.find_all('div', class_=lambda x: x and ('text-green-700' in x or 'text-yellow' in x or 'text-red' in x))

            if len(goalie_spans) >= 2 and len(status_divs) >= 2:
                # Away team is usually the first block, Home is the second
                away_goalie = goalie_spans[0].get_text(strip=True)
                home_goalie = goalie_spans[1].get_text(strip=True)

                # Determine status based on the color class they use
                away_status = "Confirmed" if 'text-green-700' in status_divs[0].get('class', []) else "Expected"
                home_status = "Confirmed" if 'text-green-700' in status_divs[1].get('class', []) else "Expected"
                
                # Note: Because the abbreviation isn't easily visible in the snippet without the parent block, 
                # we map by Goalie name for now. We can cross-reference the team in the pipeline.
                todays_goalies[f"Away_Goalie_{away_goalie}"] = {"goalie": away_goalie, "status": away_status}
                todays_goalies[f"Home_Goalie_{home_goalie}"] = {"goalie": home_goalie, "status": home_status}

        print(f"✅ Successfully mapped {len(todays_goalies)} goalies!")
        return todays_goalies

    except Exception as e:
        print(f"❌ Failed to scrape goalies: {e}")
        return None

if __name__ == "__main__":
    goalie_data = fetch_starting_goalies()
    if goalie_data:
        for key, data in goalie_data.items():
            status_icon = "🟢" if data['status'] == "Confirmed" else "🟡"
            print(f"{data['goalie']} {status_icon} ({data['status']})")