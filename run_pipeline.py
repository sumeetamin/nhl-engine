import json
import os
from datetime import datetime
import pandas as pd

# If you saved your scrapers as modules, we can import them directly.
# For now, we will simulate the pipeline assuming the CSV/JSON files are freshly downloaded.
# import goalie_scraper
# import moneypuck_fetcher

def generate_period_projections(total_expected_goals, home_edge):
    """
    Temporary distribution logic to split total goals into P1, P2, P3 for the UI cards.
    (We will replace this with actual XGBoost sub-models in Phase 3).
    """
    # Standard NHL goal distribution roughly follows: 30% P1, 34% P2, 36% P3
    home_total = (total_expected_goals / 2) + (home_edge * 1.5)
    away_total = total_expected_goals - home_total
    
    return {
        "P1": {"home": round(home_total * 0.30, 1), "away": round(away_total * 0.30, 1), "total": round(total_expected_goals * 0.30, 1)},
        "P2": {"home": round(home_total * 0.34, 1), "away": round(away_total * 0.34, 1), "total": round(total_expected_goals * 0.34, 1)},
        "P3": {"home": round(home_total * 0.36, 1), "away": round(away_total * 0.36, 1), "total": round(total_expected_goals * 0.36, 1)}
    }

def build_daily_predictions():
    print(f"⚙️ [{datetime.now().strftime('%H:%M:%S')}] INITIALIZING NHL MASTER PIPELINE...")
    
    # 1. TRIGGER SCRAPERS (In production, uncomment these)
    # print("  -> Running ESPN Goalie Scraper...")
    # goalie_scraper.fetch_espn_goalies()
    # print("  -> Running MoneyPuck Advanced Stats Fetcher...")
    # moneypuck_fetcher.fetch_moneypuck_data()

    # 2. LOAD DAILY DATA
    try:
        with open("today_goalies.json", "r") as f:
            matchups = json.load(f)
    except FileNotFoundError:
        print("❌ ERROR: today_goalies.json not found. Run the scraper first.")
        return

    # 3. BUILD THE VERCEL UI JSON SCHEMA
    print("  -> Generating Vercel UI JSON payload...")
    frontend_payload = {
        "metadata": {
            "last_updated": datetime.now().isoformat(),
            "slate_date": datetime.now().strftime("%Y-%m-%d"),
            "total_games": len(matchups)
        },
        "games": []
    }

    for game in matchups:
        # In the final version, this is where your v3.1 NHLStack model runs its predict() function.
        # For today, we route the scraper data into the exact schema Tyler's UI needs.
        
        home = game.get("Home_Team")
        away = game.get("Away_Team")
        
        # Simulated Model Outputs (to be mapped to your v3.1 Engine's actual output)
        sim_win_prob = 0.62 # Example
        sim_total = 6.1
        edge_tier = "EDGE"
        
        # Explicitly define the projected winner to prevent frontend missing-data errors
        projected_winner = home if sim_win_prob >= 0.50 else away
        home_win_pct = int(sim_win_prob * 100) if projected_winner == home else int((1 - sim_win_prob) * 100)
        away_win_pct = 100 - home_win_pct

        period_projections = generate_period_projections(sim_total, home_edge=(sim_win_prob - 0.5))

        game_card = {
            "id": f"{away}_at_{home}_{datetime.now().strftime('%Y%m%d')}",
            "status": "Scheduled",
            "matchup": {
                "home": {
                    "team": home,
                    "goalie": game.get("Home_Goalie", "TBD"),
                    "goalie_status": game.get("Home_Status", "Unconfirmed"),
                    "win_prob_pct": home_win_pct
                },
                "away": {
                    "team": away,
                    "goalie": game.get("Away_Goalie", "TBD"),
                    "goalie_status": game.get("Away_Status", "Unconfirmed"),
                    "win_prob_pct": away_win_pct
                }
            },
            "predictions": {
                "projected_winner": projected_winner,
                "tier": edge_tier,
                "projected_total": sim_total,
                "confidence_edge": "+5.1%", # Will map to elo_gap_ov
                "quality": "GOOD" if edge_tier in ["EDGE", "BIG"] else "PASS"
            },
            "period_projections": period_projections,
            # Placeholder for the BettingPros trend scraper we will build next
            "game_notes": [
                f"{projected_winner} is 14-6 ATS in their last 20 games.",
                f"Model identifies {edge_tier} value on the 60-minute Moneyline."
            ]
        }
        
        frontend_payload["games"].append(game_card)

    # 4. EXPORT TO JSON
    output_file = "daily_predictions.json"
    with open(output_file, "w") as f:
        json.dump(frontend_payload, f, indent=4)
        
    print(f"✅ PIPELINE COMPLETE. Data successfully exported to {output_file}.")
    print(f"   -> This JSON file is now ready to be consumed by the Next.js/Vercel frontend.")

if __name__ == "__main__":
    build_daily_predictions()