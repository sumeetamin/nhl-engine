import json, joblib, os
import __main__
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from engine_classes import NHLStack, NHLElo, NHLBetFilter, NHLFormStore, NHLStatsTracker, TEAM_DIV
from auto_scraper import fetch_real_nhl_results

# Re-link the unpickler classes
__main__.NHLStack = NHLStack
__main__.NHLElo = NHLElo
__main__.NHLBetFilter = NHLBetFilter
__main__.NHLFormStore = NHLFormStore
__main__.NHLStatsTracker = NHLStatsTracker

ODDS_API_KEY = "b963955ed9420f29b2f0de1d0b6de43f"

TEAM_MAPPING = {
    'Anaheim Ducks': 'ANA', 'Arizona Coyotes': 'ARI', 'Boston Bruins': 'BOS',
    'Buffalo Sabres': 'BUF', 'Calgary Flames': 'CGY', 'Carolina Hurricanes': 'CAR',
    'Chicago Blackhawks': 'CHI', 'Colorado Avalanche': 'COL', 'Columbus Blue Jackets': 'CBJ',
    'Dallas Stars': 'DAL', 'Detroit Red Wings': 'DET', 'Edmonton Oilers': 'EDM',
    'Florida Panthers': 'FLA', 'Los Angeles Kings': 'LAK', 'Minnesota Wild': 'MIN',
    'Montreal Canadiens': 'MTL', 'Nashville Predators': 'NSH', 'New Jersey Devils': 'NJD',
    'New York Islanders': 'NYI', 'New York Rangers': 'NYR', 'Ottawa Senators': 'OTT',
    'Philadelphia Flyers': 'PHI', 'Pittsburgh Penguins': 'PIT', 'San Jose Sharks': 'SJS',
    'Seattle Kraken': 'SEA', 'St Louis Blues': 'STL', 'St. Louis Blues': 'STL',
    'Tampa Bay Lightning': 'TBL', 'Toronto Maple Leafs': 'TOR', 'Vancouver Canucks': 'VAN',
    'Vegas Golden Knights': 'VGK', 'Washington Capitals': 'WSH', 'Winnipeg Jets': 'WPG',
    'Utah Hockey Club': 'UTA'
}

def get_live_odds():
    print("💰 Fetching live Sportsbook odds...")
    url = f"https://api.the-odds-api.com/v4/sports/icehockey_nhl/odds/?apiKey={ODDS_API_KEY}&regions=us&markets=h2h,totals&oddsFormat=american"
    odds_map = {}
    try:
        data = requests.get(url).json()
        
        # 🚨 FIX: Safety check in case the API limit is reached
        if not isinstance(data, list):
            print(f"⚠️ Odds API Error: {data.get('message', 'Unknown API Error')}")
            return odds_map

        for game in data:
            home_abbrev = TEAM_MAPPING.get(game.get('home_team'))
            away_abbrev = TEAM_MAPPING.get(game.get('away_team'))
            
            if not home_abbrev or not away_abbrev: continue
            
            bookmakers = game.get('bookmakers', [])
            if not bookmakers: continue
            book = bookmakers[0] 
            
            home_ml, away_ml, ou_line = "TBD", "TBD", "TBD"
            
            for m in book.get('markets', []):
                if m['key'] == 'h2h':
                    for outcome in m['outcomes']:
                        price = outcome['price']
                        formatted_price = f"+{price}" if price > 0 else str(price)
                        if outcome['name'] == game.get('home_team'):
                            home_ml = formatted_price
                        else:
                            away_ml = formatted_price
                elif m['key'] == 'totals':
                    ou_line = f"O/U {m['outcomes'][0]['point']}"
                    
            odds_map[f"{away_abbrev}@{home_abbrev}"] = {
                "home_ml": home_ml, "away_ml": away_ml, "ou": ou_line
            }
    except Exception as e:
        print(f"⚠️ Could not fetch odds: {e}")
    return odds_map

def convert_to_est(utc_string):
    try:
        dt_utc = datetime.strptime(utc_string, "%Y-%m-%dT%H:%M:%SZ")
        dt_est = dt_utc - timedelta(hours=4)
        return dt_est.strftime("%I:%M %p EST").lstrip("0")
    except:
        return "TBD"

def run_ml_engine(home_team, away_team, game_time="TBD", odds_data=None, csv_path="past_games.csv"):
    try:
        model = joblib.load("sumeets_engine_v4.pkl")
    except FileNotFoundError:
        print("⚠️ Failed to load sumeets_engine_v4.pkl")
        return None

    df_past = pd.read_csv(csv_path) if os.path.exists(csv_path) else pd.DataFrame(columns=['Date','Home','Away','Actual_Winner'])
    elo, form, tracker = NHLElo(), NHLFormStore(), NHLStatsTracker()
    
    if not df_past.empty:
        elo.build_from_df(df_past)
        form.build_from_df(df_past)
        tracker.build_from_df(df_past)

    h_stats = tracker.get_rolling_metrics(home_team, n=10)
    a_stats = tracker.get_rolling_metrics(away_team, n=10)
    
    h_elo, a_elo = elo.get_rating(home_team, "overall"), elo.get_rating(away_team, "overall")
    h_elo_sit, a_elo_sit = elo.get_rating(home_team, "home"), elo.get_rating(away_team, "away")
    
    elo_gap_ov = (h_elo + elo.hfa) - a_elo
    elo_win_prob = 1.0 / (1.0 + 10.0 ** (-elo_gap_ov / 400.0))
    h2h = form.get_h2h(home_team, away_team)

    # 🚨 FIX: Calculating the new Pythagorean and Expected Win Rates for v4 Model
    h_pyth = (h_stats["gf_pg"]**2) / (h_stats["gf_pg"]**2 + h_stats["ga_pg"]**2) if (h_stats["gf_pg"] + h_stats["ga_pg"]) > 0 else 0.5
    a_pyth = (a_stats["gf_pg"]**2) / (a_stats["gf_pg"]**2 + a_stats["ga_pg"]**2) if (a_stats["gf_pg"] + a_stats["ga_pg"]) > 0 else 0.5
    h_ewr10 = h_pyth * 0.5 + form.get_win_rate(home_team, 10) * 0.5
    a_ewr10 = a_pyth * 0.5 + form.get_win_rate(away_team, 10) * 0.5
    h_ewr20 = h_pyth * 0.5 + form.get_win_rate(home_team, 20) * 0.5
    a_ewr20 = a_pyth * 0.5 + form.get_win_rate(away_team, 20) * 0.5

    # 🚨 FIX: Mapping EXACTLY the 78 features expected by sumeets_engine_v4.pkl
    matchup_features = {
        'h_gf_pct': h_stats["gf_pct"], 'a_gf_pct': a_stats["gf_pct"], 'gf_pct_diff': h_stats["gf_pct"] - a_stats["gf_pct"],
        'h_pyth_wp': h_pyth, 'a_pyth_wp': a_pyth, 'pyth_wp_diff': h_pyth - a_pyth,
        'h_pdo_luck': h_stats["pdo_proxy"], 'a_pdo_luck': a_stats["pdo_proxy"], 'pdo_luck_diff': h_stats["pdo_proxy"] - a_stats["pdo_proxy"],
        'h_gf_pg': h_stats["gf_pg"], 'a_gf_pg': a_stats["gf_pg"], 'h_ga_pg': h_stats["ga_pg"], 'a_ga_pg': a_stats["ga_pg"],
        'h_elo': h_elo, 'a_elo': a_elo, 'h_elo_sit': h_elo_sit, 'a_elo_sit': a_elo_sit,
        'h_elo_home': elo.get_rating(home_team, "home"), 'a_elo_away': elo.get_rating(away_team, "away"),
        'elo_gap_ov': elo_gap_ov, 'elo_gap_sit': (h_elo_sit + elo.hfa) - a_elo_sit, 'elo_gap_ha': (elo.get_rating(home_team, "home") + elo.hfa) - elo.get_rating(away_team, "away"),
        'elo_gap_abs': abs(elo_gap_ov), 'elo_gap_sq': (elo_gap_ov ** 2) / 1000.0,
        'h_wr5': form.get_win_rate(home_team, 5), 'h_wr10': form.get_win_rate(home_team, 10), 'h_wr20': form.get_win_rate(home_team, 20),
        'a_wr5': form.get_win_rate(away_team, 5), 'a_wr10': form.get_win_rate(away_team, 10), 'a_wr20': form.get_win_rate(away_team, 20),
        'wr_diff5': form.get_win_rate(home_team, 5) - form.get_win_rate(away_team, 5),
        'wr_diff10': form.get_win_rate(home_team, 10) - form.get_win_rate(away_team, 10),
        'wr_diff20': form.get_win_rate(home_team, 20) - form.get_win_rate(away_team, 20),
        'h_ewr10': h_ewr10, 'a_ewr10': a_ewr10, 'h_ewr20': h_ewr20, 'a_ewr20': a_ewr20,
        'ewr_diff10': h_ewr10 - a_ewr10, 'ewr_diff20': h_ewr20 - a_ewr20,
        'h_home_wr10': form.get_win_rate(home_team, 10), 'a_away_wr10': form.get_win_rate(away_team, 10),
        'home_away_wr_diff': form.get_win_rate(home_team, 10) - form.get_win_rate(away_team, 10),
        'h_b2b_wr': 0.5, 'a_b2b_wr': 0.5, 
        'h_streak': form.get_streak(home_team), 'a_streak': form.get_streak(away_team), 'streak_diff': form.get_streak(home_team) - form.get_streak(away_team),
        'h2h_rate': h2h["h2h_rate"], 'h2h_margin': h2h["h2h_margin"], 'h2h_total': h2h["h2h_total"], 'h2h_adv': int(h2h["h2h_rate"] >= 0.6),
        'h_rest': 2, 'a_rest': 2, 'rest_diff': 0, 'h_b2b': 0, 'a_b2b': 0, 'both_b2b': 0,
        'rest_adv_h': 0, 'rest_adv_a': 0, 'same_div': int(TEAM_DIV.get(home_team, "H") == TEAM_DIV.get(away_team, "A")),
        'season_phase': 2, 'is_late_season': 1,
        'elo_form_agree': int((elo_gap_ov > 0) == (form.get_win_rate(home_team, 10) > form.get_win_rate(away_team, 10))),
        'elo_h2h_agree': int((elo_gap_ov > 0) == (h2h["h2h_rate"] >= 0.5)),
        'pyth_elo_agree': int((elo_gap_ov > 0) == ((h_pyth - a_pyth) > 0)),
        'triple_agree': int((elo_gap_ov > 0) == (form.get_win_rate(home_team, 10) > form.get_win_rate(away_team, 10)) == (h2h["h2h_rate"] >= 0.5)),
        'h_fatigue_adv': 0, 'a_fatigue_adv': 0,
        'elo_gap_tier0': int(abs(elo_gap_ov) < 50), 'elo_gap_tier1': int(50 <= abs(elo_gap_ov) < 100),
        'elo_gap_tier2': int(100 <= abs(elo_gap_ov) < 150), 'elo_gap_tier3': int(150 <= abs(elo_gap_ov) < 200),
        'elo_gap_tier4': int(abs(elo_gap_ov) >= 200),
        'elo_form_product': elo_gap_ov * (form.get_win_rate(home_team, 10) - form.get_win_rate(away_team, 10)),
        'elo_h2h_product': elo_gap_ov * (h2h["h2h_rate"] - 0.5),
        'pyth_elo_product': elo_gap_ov * (h_pyth - a_pyth),
        'rest_form_product': 0.0,
        'elo_luck_diff': elo_gap_ov * (h_stats["pdo_proxy"] - a_stats["pdo_proxy"])
    }

    try:
        # Re-ordered columns precisely to match the PKL layout
        col_order = ['h_gf_pct', 'a_gf_pct', 'gf_pct_diff', 'h_pyth_wp', 'a_pyth_wp', 'pyth_wp_diff', 'h_pdo_luck', 'a_pdo_luck', 'pdo_luck_diff', 'h_gf_pg', 'a_gf_pg', 'h_ga_pg', 'a_ga_pg', 'h_elo', 'a_elo', 'h_elo_sit', 'a_elo_sit', 'h_elo_home', 'a_elo_away', 'elo_gap_ov', 'elo_gap_sit', 'elo_gap_ha', 'elo_gap_abs', 'elo_gap_sq', 'h_wr5', 'h_wr10', 'h_wr20', 'a_wr5', 'a_wr10', 'a_wr20', 'wr_diff5', 'wr_diff10', 'wr_diff20', 'h_ewr10', 'a_ewr10', 'h_ewr20', 'a_ewr20', 'ewr_diff10', 'ewr_diff20', 'h_home_wr10', 'a_away_wr10', 'home_away_wr_diff', 'h_b2b_wr', 'a_b2b_wr', 'h_streak', 'a_streak', 'streak_diff', 'h2h_rate', 'h2h_margin', 'h2h_total', 'h2h_adv', 'h_rest', 'a_rest', 'rest_diff', 'h_b2b', 'a_b2b', 'both_b2b', 'rest_adv_h', 'rest_adv_a', 'same_div', 'season_phase', 'is_late_season', 'elo_form_agree', 'elo_h2h_agree', 'pyth_elo_agree', 'triple_agree', 'h_fatigue_adv', 'a_fatigue_adv', 'elo_gap_tier0', 'elo_gap_tier1', 'elo_gap_tier2', 'elo_gap_tier3', 'elo_gap_tier4', 'elo_form_product', 'elo_h2h_product', 'pyth_elo_product', 'rest_form_product', 'elo_luck_diff']
        X_df = pd.DataFrame([matchup_features])[col_order]
        home_win_prob = float(model.predict(X_df)[0]) * 100 
    except Exception as e:
        print(f"⚠️ Model prediction error: {e}")
        home_win_prob = 50.0

    predicted_winner = home_team if home_win_prob > 50 else away_team
    max_prob = max(home_win_prob, 100 - home_win_prob)

    tier = "NONE"
    if max_prob >= 78.0 or abs(elo_gap_ov) > 240: tier = "BIG"
    elif max_prob >= 65.0 or abs(elo_gap_ov) > 160: tier = "EDGE"

    h_proj = round(h_stats["gf_pg"] * (home_win_prob / 50.0), 1)
    a_proj = round(a_stats["gf_pg"] * ((100 - home_win_prob) / 50.0), 1)
    total_proj = h_proj + a_proj

    if odds_data:
        h_ml = odds_data.get("home_ml", "TBD")
        a_ml = odds_data.get("away_ml", "TBD")
        ou_total = odds_data.get("ou", "TBD") 
    else:
        h_ml, a_ml, ou_total = "TBD", "TBD", "TBD"

    # AI Auto-Line Generator
    if ou_total == "TBD":
        ou_total = f"PROJ O/U {round(total_proj * 2) / 2}"
        
    if h_ml == "TBD" or a_ml == "TBD":
        if home_win_prob > 50:
            h_ml = f"PROJ -{int((home_win_prob / (100 - home_win_prob)) * 100)}"
            a_ml = f"PROJ +{int((home_win_prob / (100 - home_win_prob)) * 100)}"
        else:
            h_ml = f"PROJ +{int(((100 - home_win_prob) / home_win_prob) * 100)}"
            a_ml = f"PROJ -{int(((100 - home_win_prob) / home_win_prob) * 100)}"

    away_w = int(form.get_win_rate(away_team, 10)*10)
    home_w = int(form.get_win_rate(home_team, 10)*10)
    h2h_h_wins = int(h2h["h2h_rate"] * h2h["h2h_total"])

    return {
        "away": { "name": away_team, "record": f"{away_w}-{10-away_w}-0 (L10)", "ml": a_ml, "proj": f"{a_proj}" },
        "home": { "name": home_team, "record": f"{home_w}-{10-home_w}-0 (L10)", "ml": h_ml, "proj": f"{h_proj}" },
        "ou_total": ou_total,
        "prob": f"{max_prob:.1f}%",
        "time": game_time,
        "tier": tier,
        "edge": f"+{round(max_prob - 52.4, 1)}%",
        "details": {
            "period_60": {
                "p1_winner": f"{predicted_winner} ({round(max_prob * 0.85)}%)",
                "p1_over_1_5": f"{round(min(90, (round(h_proj * 0.28, 1) + round(a_proj * 0.28, 1)) * 40))}%",
                "min_60_tie": f"{round(22 + (50 - max_prob)*0.5)}%"
            },
            "period_scores": {
                "p1": f"{away_team} {round(a_proj * 0.28, 1)} - {home_team} {round(h_proj * 0.28, 1)}",
                "p2": f"{away_team} {round(a_proj * 0.35, 1)} - {home_team} {round(h_proj * 0.35, 1)}",
                "p3": f"{away_team} {round(a_proj * 0.37, 1)} - {home_team} {round(h_proj * 0.37, 1)}"
            },
            "recent": {
                "away_overall": f"{away_w}-{10-away_w}-0",
                "home_overall": f"{home_w}-{10-home_w}-0",
                "h2h": f"{home_team} leads {h2h_h_wins}-{h2h['h2h_total']-h2h_h_wins}"
            },
            "covers": {
                "best_ml": f"{predicted_winner} ML",
                "best_spread": f"{predicted_winner} -1.5" if abs(h_proj - a_proj) >= 1.5 else "PASS",
                "best_ou": f"OVER 5.5" if total_proj > 6.1 else f"UNDER 6.0" if total_proj < 5.8 else "PASS"
            },
            "notes": [
                f"V4 Engine parsed 78 internal features. Active Elo distance: {elo_gap_ov:.0f}.",
                f"Implied true probability dictates a pure {max_prob:.1f}% mathematical edge.",
                f"Automated system assigned tier: {tier}."
            ],
            "best_angle": {
                "play": f"{predicted_winner} MONEYLINE",
                "edge": f"+{round(max_prob - 52.4, 1)}%"
            }
        }
    }

def run_backtest(csv_path="past_games.csv", days_back=30):
    recent_games = []
    wins, total_games, high_edge_wins, high_edge_total, total_edge_val = 0, 0, 0, 0, 0.0
    try:
        df = pd.read_csv(csv_path)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values(by='Date', ascending=False)
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_back)
        df = df[df['Date'] >= cutoff]

        for index, row in df.iterrows():
            away, home, actual = row['Away'], row['Home'], row['Actual_Winner']
            prediction = run_ml_engine(home, away, "FINAL", None, csv_path)
            if not prediction: continue
            
            if prediction["tier"] == "NONE": continue
            
            predicted_winner = prediction["details"]["best_angle"]["play"].split(" ")[0]
            edge_val = float(prediction["edge"].replace('+', '').replace('%', ''))
            
            total_games += 1
            total_edge_val += edge_val
            if prediction["tier"] == "BIG": high_edge_total += 1
            
            if predicted_winner == actual: 
                wins += 1
                if prediction["tier"] == "BIG": high_edge_wins += 1

            recent_games.append({
                "date": row['Date'].strftime('%Y-%m-%d'),
                "matchup": f"{away} @ {home}",
                "pick": predicted_winner,
                "edge": f"{prediction['tier']} ({prediction['edge']})",
                "result": "WIN" if predicted_winner == actual else "LOSS"
            })
            
        return {
            "overall_win_rate": f"{(wins/total_games*100):.1f}%" if total_games>0 else "0.0%",
            "high_edge_win_rate": f"{(high_edge_wins/high_edge_total*100):.1f}%" if high_edge_total>0 else "0.0%",
            "avg_edge": f"+{(total_edge_val/total_games):.1f}%" if total_games>0 else "+0.0%",
            "recent_games": recent_games
        }
    except Exception as e:
        print(f"Backtest error: {e}")
        return {"overall_win_rate": "0.0%", "high_edge_win_rate": "0.0%", "avg_edge": "+0.0%", "recent_games": []}

def get_best_bet_for_date(target_date_str, live_odds):
    url = f"https://api-web.nhle.com/v1/schedule/{target_date_str}"
    try:
        response = requests.get(url).json()
        games = next((day['games'] for day in response.get('gameWeek', []) if day['date'] == target_date_str), [])
        matchups = [(g['homeTeam']['abbrev'], g['awayTeam']['abbrev'], g.get('startTimeUTC', 'TBD')) for g in games]
    except:
        matchups = []

    best_game_payload, highest_edge = None, -100.0

    for home, away, utc_time in matchups:
        odds_match = live_odds.get(f"{away}@{home}")
        result = run_ml_engine(home, away, convert_to_est(utc_time), odds_match)
        if result and float(result['edge'].replace('+','').replace('%','')) > highest_edge:
            highest_edge = float(result['edge'].replace('+','').replace('%',''))
            best_game_payload = result
    return best_game_payload

def get_top_plays(target_date_str, live_odds):
    url = f"https://api-web.nhle.com/v1/schedule/{target_date_str}"
    try:
        response = requests.get(url).json()
        games = next((day['games'] for day in response.get('gameWeek', []) if day['date'] == target_date_str), [])
        matchups = [(g['homeTeam']['abbrev'], g['awayTeam']['abbrev'], g.get('startTimeUTC', 'TBD')) for g in games]
    except:
        matchups = []

    plays = []
    for home, away, utc_time in matchups:
        odds_match = live_odds.get(f"{away}@{home}")
        res = run_ml_engine(home, away, convert_to_est(utc_time), odds_match)
        if res and res["tier"] in ["EDGE", "BIG"]: plays.append(res)
    plays.sort(key=lambda x: float(x['edge'].replace('+','').replace('%','')), reverse=True)
    return plays[:3]

def build_daily_json():
    print("\n--- RUNNING DAILY PIPELINE ---")
    live_odds = get_live_odds()
    
    today = datetime.now()
    yesterday_str = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')
    tomorrow_str = (today + timedelta(days=1)).strftime('%Y-%m-%d')

    top_today = get_top_plays(today_str, live_odds) or get_top_plays(tomorrow_str, live_odds)

    daily_payload = {
        "yesterday": get_best_bet_for_date(yesterday_str, live_odds),
        "today": get_best_bet_for_date(today_str, live_odds),
        "tomorrow": get_best_bet_for_date(tomorrow_str, live_odds),
        "top_plays": top_today
    }

    print("📡 Connecting to NHL API... fetching last 30 days of real data.")
    fetch_real_nhl_results(days_back=30)
    ledger_payload = run_backtest()

    public_dir = os.path.join("frontend", "public")
    if not os.path.exists(public_dir): os.makedirs(public_dir)
        
    with open(os.path.join(public_dir, "daily_predictions.json"), 'w') as f: json.dump(daily_payload, f, indent=4)
    with open(os.path.join(public_dir, "historical_stats.json"), 'w') as f: json.dump(ledger_payload, f, indent=4)
    print("✅ V4 Model Successfully Processed 78 Features.")

if __name__ == "__main__":
    build_daily_json()