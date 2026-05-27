import json, requests, os, glob
from datetime import datetime

def grade_predictions():
    ledger_file = "model_records_ledger.json"
    ledger = json.load(open(ledger_file, "r")) if os.path.exists(ledger_file) else \
             {"moneyline": {"wins": 0, "losses": 0, "win_pct": 0.0}, "history": []}
    
    processed_ids = {h["game_id"] for h in ledger["history"]}
    prediction_files = glob.glob("predictions_*.json")
    
    for file in prediction_files:
        with open(file, "r") as f:
            data = json.load(f)
            gid = data["id"]
            if gid in processed_ids: continue
            
            # Simple simulation of result fetching (Replace with NHL API call)
            # This is where you would call fetch_scores_for_date()
            print(f"Checking game: {gid}...")
            
    with open(ledger_file, "w") as f:
        json.dump(ledger, f, indent=4)
    print("✅ Records ledger updated.")

if __name__ == "__main__":
    grade_predictions()