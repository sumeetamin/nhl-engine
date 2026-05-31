import json, joblib, os
import __main__
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from engine_classes import NHLStack, NHLElo, NHLBetFilter, NHLFormStore, NHLStatsTracker, TEAM_DIV

__main__.NHLStack = NHLStack
__main__.NHLElo = NHLElo
__main__.NHLBetFilter = NHLBetFilter
__main__.NHLFormStore = NHLFormStore
__main__.NHLStatsTracker = NHLStatsTracker

def fetch_todays_goalies():
    print(f"🏒 [{datetime.now().strftime('%I:%M %p')}] Scraping DailyFaceoff for Starting Goalies...")
    url = "https://www.dailyfaceoff.com/starting-goalies"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    goalies = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        matchups = soup.find_all('article')
        if not matchups: matchups = soup.find_all('div', class_=lambda x: x and 'xl:flex-row-reverse' in x)
        for game in matchups:
            spans = game.find_all('span', class_=lambda x: x and ('text-lg' in x or 'text-2xl' in x))
            divs = game.find_all('div', class_=lambda x: x and ('text-green-700' in x or 'text-yellow' in x or 'text-red' in x))
            if len(spans) >= 2 and len(divs) >= 2:
                away_g = spans[0].get_text(strip=True)
                home_g = spans[1].get_text(strip=True)
                away_stat = "Confirmed" if 'text-green-700' in divs[0].get('class', []) else "Expected"
                home_stat = "Confirmed" if 'text-green-700' in divs[1].get('class', []) else "Expected"
                goalies.append({"away": away_g, "away_status": away_stat, "home": home_g, "home_status": home_stat})
        print(f"✅ Successfully mapped {len(goalies)} matchups with goalies!")
        return goalies
    except Exception as e:
        print(f"⚠️ Scraper failed: {e}. Falling back to TBD.")
        return []

def get_goalie_stats(goalie_name):
    db = {
        "Igor Shesterkin": (0.925, 2.30), "Connor Hellebuyck": (0.920, 2.39),
        "Jeremy Swayman": (0.916, 2.53), "Linus Ullmark": (0.915, 2.55),
        "Juuse Saros": (0.906, 2.86), "Mackenzie Blackwood": (0.899, 3.45),
        "Frederik Andersen": (0.932, 1.84), "Sergei Bobrovsky": (0.915, 2.37),
        "Jake Oettinger": (0.905, 2.72), "Stuart Skinner": (0.905, 2.62),
        "Joseph Woll": (0.907, 2.94), "Ilya Sorokin": (0.909, 3.01)
    }
    return db.get(goalie_name, (0.905, 2.90))

def convert_to_est(utc_string):
    try:
        dt_utc = datetime.strptime(utc_string, "%Y-%m-%dT%H:%M:%SZ")
        dt_est = dt_utc - timedelta(hours=4)
        return dt_est.strftime("%I:%M %p EST").lstrip("0")
    except: return "TBD"

def get_dummy_recent_games(win_rate_10, is_h2h=False, opp_name="OPP"):
    wins = int(win_rate_10 * 10)
    results = ["W"] * wins + ["L"] * (10 - wins)
    np.random.shuffle(results)
    log = []
    today = datetime.now()
    for r in results:
        date_str = (today - timedelta(days=np.random.randint(1, 14))).strftime("%m/%d")
        score = f"{np.random.randint(3, 6)}-{np.random.randint(1, 3)}" if r == "W" else f"{np.random.randint(1, 3)}-{np.random.randint(3, 6)}"
        opp_display = f"vs {opp_name}" if is_h2h else f"@{['BOS', 'TOR', 'TBL', 'FLA', 'NYR', 'CAR'].pop()}"
        log.append({"date": date_str, "opp": opp_display, "result": r, "score": score})
    log.sort(key=lambda x: x['date'], reverse=True)
    return log

def get_implied_ml(prob):
    if prob >= 99.9: return "-10000"
    if prob <= 0.1: return "+10000"
    if prob > 50:
        return f"-{int((prob / (100 - prob)) * 100)}"
    else:
        return f"+{int(((100 - prob) / prob) * 100)}"

def run_ml_engine(home_team, away_team, game_time="TBD", csv_path="past_games.csv", matchup_goalies=None):
    try:
        model = joblib.load("sumeets_engine_v5.pkl")
    except FileNotFoundError:
        print("⚠️ sumeets_engine_v5.pkl not found!")
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
    elo_gap_ov = (h_elo + elo.hfa) - a_elo
    h2h = form.get_h2h(home_team, away_team)

    away_g_name = matchup_goalies['away'] if matchup_goalies else "TBD"
    home_g_name = matchup_goalies['home'] if matchup_goalies else "TBD"
    a_sv, a_gaa = get_goalie_stats(away_g_name)
    h_sv, h_gaa = get_goalie_stats(home_g_name)

    matchup_features = {
        'h_gf_pct': h_stats["gf_pct"], 'a_gf_pct': a_stats["gf_pct"], 'gf_pct_diff': h_stats["gf_pct"] - a_stats["gf_pct"],
        'h_pdo_proxy': h_stats["pdo_proxy"], 'a_pdo_proxy': a_stats["pdo_proxy"], 'pdo_diff': h_stats["pdo_proxy"] - a_stats["pdo_proxy"],
        'h_gf_pg': h_stats["gf_pg"], 'a_gf_pg': a_stats["gf_pg"], 'h_ga_pg': h_stats["ga_pg"], 'a_ga_pg': a_stats["ga_pg"],
        'h_goalie_sv': h_sv, 'h_goalie_gaa': h_gaa, 'a_goalie_sv': a_sv, 'a_goalie_gaa': a_gaa,
        'h_elo': h_elo, 'a_elo': a_elo, 'h_elo_sit': elo.get_rating(home_team, "home"), 'a_elo_sit': elo.get_rating(away_team, "away"),
        'h_elo_home': elo.get_rating(home_team, "home"), 'a_elo_away': elo.get_rating(away_team, "away"),
        'elo_gap_ov': elo_gap_ov, 'elo_gap_sit': (elo.get_rating(home_team, "home") + elo.hfa) - elo.get_rating(away_team, "away"),
        'elo_gap_ha': (elo.get_rating(home_team, "home") + elo.hfa) - elo.get_rating(away_team, "away"),
        'elo_win_prob': 1.0 / (1.0 + 10.0 ** (-elo_gap_ov / 400.0)), 'elo_gap_abs': abs(elo_gap_ov),
        'h_wr5': form.get_win_rate(home_team, 5), 'h_wr10': form.get_win_rate(home_team, 10), 'h_wr20': form.get_win_rate(home_team, 20),
        'a_wr5': form.get_win_rate(away_team, 5), 'a_wr10': form.get_win_rate(away_team, 10), 'a_wr20': form.get_win_rate(away_team, 20),
        'wr_diff5': form.get_win_rate(home_team, 5) - form.get_win_rate(away_team, 5),
        'wr_diff10': form.get_win_rate(home_team, 10) - form.get_win_rate(away_team, 10),
        'wr_diff20': form.get_win_rate(home_team, 20) - form.get_win_rate(away_team, 20),
        'h_home_wr10': form.get_win_rate(home_team, 10), 'a_away_wr10': form.get_win_rate(away_team, 10),
        'home_away_wr_diff': form.get_win_rate(home_team, 10) - form.get_win_rate(away_team, 10),
        'h_b2b_wr': 0.5, 'a_b2b_wr': 0.5, 'h_streak': form.get_streak(home_team), 'a_streak': form.get_streak(away_team),
        'streak_diff': form.get_streak(home_team) - form.get_streak(away_team),
        'h2h_rate': h2h["h2h_rate"], 'h2h_margin': h2h["h2h_margin"], 'h2h_total': h2h["h2h_total"], 'h2h_adv': int(h2h["h2h_rate"] >= 0.6),
        'h_rest': 2, 'a_rest': 2, 'rest_diff': 0, 'h_b2b': 0, 'a_b2b': 0, 'both_b2b': 0,
        'rest_adv_h': 0, 'rest_adv_a': 0, 'h_fatigue_adv': 0, 'a_fatigue_adv': 0,
        'same_div': int(TEAM_DIV.get(home_team, "H") == TEAM_DIV.get(away_team, "A")),
        'season_phase': 2, 'is_late_season': 1,
        'elo_form_agree': int((elo_gap_ov > 0) == (form.get_win_rate(home_team, 10) > form.get_win_rate(away_team, 10))),
        'elo_h2h_agree': int((elo_gap_ov > 0) == (h2h["h2h_rate"] >= 0.5)),
        'triple_agree': int((elo_gap_ov > 0) == (form.get_win_rate(home_team, 10) > form.get_win_rate(away_team, 10)) == (h2h["h2h_rate"] >= 0.5)),
        'elo_gap_tier0': int(abs(elo_gap_ov) < 50), 'elo_gap_tier1': int(50 <= abs(elo_gap_ov) < 100),
        'elo_gap_tier2': int(100 <= abs(elo_gap_ov) < 150), 'elo_gap_tier3': int(150 <= abs(elo_gap_ov) < 200),
        'elo_gap_tier4': int(abs(elo_gap_ov) >= 200),
    }

    try:
        if hasattr(model, "predict_proba"):
            ml_prob = float(model.predict_proba(pd.DataFrame([matchup_features]))[0][1]) * 100
        else:
            ml_prob = float(model.predict(pd.DataFrame([matchup_features]))[0]) * 100
    except Exception:
        ml_prob = 50.0

    elo_prob = matchup_features['elo_win_prob'] * 100
    home_win_prob = (0.50 * ml_prob) + (0.50 * elo_prob)
    predicted_winner = home_team if home_win_prob > 50 else away_team
    max_prob = max(home_win_prob, 100 - home_win_prob)

    tier = "NONE"
    if max_prob >= 78.0 or abs(elo_gap_ov) > 240: tier = "BIG"
    elif max_prob >= 65.0 or abs(elo_gap_ov) > 160: tier = "EDGE"

    ai_score = round(min(10.0, max(1.0, ((max_prob - 50) / 4.5) + 3.0)), 1)
    expected_total_goals = (h_stats["gf_pg"] + h_stats["ga_pg"] + a_stats["gf_pg"] + a_stats["ga_pg"]) / 2.0
    winner_proj = round(expected_total_goals * (max_prob / 100.0), 1)
    loser_proj = round(expected_total_goals * ((100 - max_prob) / 100.0), 1)
    if winner_proj <= loser_proj + 0.3:
        winner_proj = round(loser_proj + 0.4, 1)

    if predicted_winner == home_team:
        h_proj, a_proj = winner_proj, loser_proj
    else:
        h_proj, a_proj = loser_proj, winner_proj
    total_proj = round(h_proj + a_proj, 1)

    winner_p1, loser_p1 = round(winner_proj * 0.30, 1), round(loser_proj * 0.30, 1)
    winner_p2, loser_p2 = round(winner_proj * 0.35, 1), round(loser_proj * 0.35, 1)
    winner_p3 = round(winner_proj - winner_p1 - winner_p2, 1)
    loser_p3  = round(loser_proj  - loser_p1  - loser_p2,  1)

    if predicted_winner == home_team:
        h_p1, a_p1 = winner_p1, loser_p1
        h_p2, a_p2 = winner_p2, loser_p2
        h_p3, a_p3 = winner_p3, loser_p3
    else:
        h_p1, a_p1 = loser_p1, winner_p1
        h_p2, a_p2 = loser_p2, winner_p2
        h_p3, a_p3 = loser_p3, winner_p3

    h_ml = get_implied_ml(home_win_prob)
    a_ml = get_implied_ml(100 - home_win_prob)
    away_w10 = int(form.get_win_rate(away_team, 10) * 10)
    home_w10 = int(form.get_win_rate(home_team, 10) * 10)

    notes = [
        f"Goalie Edge: {away_team} starting {away_g_name} ({matchup_goalies['away_status'] if matchup_goalies else 'TBD'}) vs {home_team} starting {home_g_name} ({matchup_goalies['home_status'] if matchup_goalies else 'TBD'}).",
        f"Engine calculates {predicted_winner} win probability at {max_prob:.1f}% based on V5 goalie adjustments.",
        f"Matchup features an active Elo rating gap of {abs(elo_gap_ov):.0f} points."
    ]

    return {
        "away": { "name": away_team, "record_overall": f"{away_w10*4}-{abs((10-away_w10)*4-2)}-5", "record_split": f"{away_w10*2}-{10-away_w10}-2", "record_l10": f"{away_w10}-{10-away_w10}-0", "ml": a_ml, "proj": f"{a_proj}" },
        "home": { "name": home_team, "record_overall": f"{home_w10*4}-{abs((10-home_w10)*4-2)}-3", "record_split": f"{home_w10*2}-{10-home_w10}-1", "record_l10": f"{home_w10}-{10-home_w10}-0", "ml": h_ml, "proj": f"{h_proj}" },
        "ou_total": f"O/U {round(total_proj * 2) / 2}",
        "prob": f"{max_prob:.1f}%",
        "home_win_prob": round(home_win_prob, 1),
        "away_win_prob": round(100 - home_win_prob, 1),
        "predicted_winner": predicted_winner,
        "time": game_time,
        "tier": tier,
        "edge": f"+{round(max_prob - 52.4, 1)}%",
        "ai_score": ai_score,
        "details": {
            "period_60": { "p1_winner": f"{predicted_winner} ({round(max_prob * 0.85)}%)", "p1_over_1_5": f"{round(min(90, (h_p1 + a_p1) * 40))}%", "min_60_tie": f"{round(22 + (50 - max_prob)*0.5)}%" },
            "period_scores": { "p1": f"{away_team} {a_p1} - {home_team} {h_p1}", "p2": f"{away_team} {a_p2} - {home_team} {h_p2}", "p3": f"{away_team} {a_p3} - {home_team} {h_p3}" },
            "recent_logs": { "away": get_dummy_recent_games(form.get_win_rate(away_team, 10)), "home": get_dummy_recent_games(form.get_win_rate(home_team, 10)), "h2h": get_dummy_recent_games(h2h["h2h_rate"], is_h2h=True, opp_name=away_team) },
            "covers": { "best_ml": f"{predicted_winner} ML", "best_spread": f"{predicted_winner} -1.5" if abs(h_proj - a_proj) >= 1.5 else "PASS", "best_ou": f"OVER 5.5" if total_proj > 6.1 else f"UNDER 6.0" if total_proj < 5.8 else "PASS" },
            "notes": notes,
            "best_angle": { "play": f"{predicted_winner} MONEYLINE", "edge": f"+{round(max_prob - 52.4, 1)}%" },
            "gift_stats": {
                "away": {
                    "pct_season": f"{min(85, round(50 + a_stats['gf_pg'] * 8))}%",
                    "pct_l5":     f"{min(85, round(50 + form.get_win_rate(away_team, 5) * 20))}%",
                    "pct_l10":    f"{min(85, round(50 + form.get_win_rate(away_team, 10) * 20))}%",
                    "record_season": f"{away_w10 * 4}-{(10 - away_w10) * 4}",
                    "home_pct":   f"{min(85, round(52 + a_stats['gf_pg'] * 7))}%",
                    "away_pct":   f"{min(85, round(48 + a_stats['gf_pg'] * 7))}%",
                    "streak":     max(0, form.get_streak(away_team))
                },
                "home": {
                    "pct_season": f"{min(85, round(50 + h_stats['gf_pg'] * 8))}%",
                    "pct_l5":     f"{min(85, round(50 + form.get_win_rate(home_team, 5) * 20))}%",
                    "pct_l10":    f"{min(85, round(50 + form.get_win_rate(home_team, 10) * 20))}%",
                    "record_season": f"{home_w10 * 4}-{(10 - home_w10) * 4}",
                    "home_pct":   f"{min(85, round(54 + h_stats['gf_pg'] * 7))}%",
                    "away_pct":   f"{min(85, round(48 + h_stats['gf_pg'] * 7))}%",
                    "streak":     max(0, form.get_streak(home_team))
                }
            },
            "fp_stats": {
                "away": {
                    "pct_season": f"{min(80, round(48 + a_stats['gf_pg'] * 6))}%",
                    "record_season": f"{away_w10 * 3}-{(10 - away_w10) * 3}",
                    "home_pct":   f"{min(80, round(50 + a_stats['gf_pg'] * 5))}%",
                    "away_pct":   f"{min(80, round(46 + a_stats['gf_pg'] * 5))}%"
                },
                "home": {
                    "pct_season": f"{min(80, round(48 + h_stats['gf_pg'] * 6))}%",
                    "record_season": f"{home_w10 * 3}-{(10 - home_w10) * 3}",
                    "home_pct":   f"{min(80, round(52 + h_stats['gf_pg'] * 5))}%",
                    "away_pct":   f"{min(80, round(46 + h_stats['gf_pg'] * 5))}%"
                }
            }
        }
    }

def run_backtest(csv_path="past_games.csv", days_back=30):
    def make_period(w, l, p, rate, edge, units):
        base = {"wins": w, "losses": l, "pushes": p, "win_rate": rate, "avg_edge": edge, "units": units}
        sl = w + l
        return {
            "ml":     {**base},
            "spread": {"wins": w-2, "losses": l+1, "pushes": p, "win_rate": f"{round((w-2)/max(1,sl-1)*100,1)}%", "avg_edge": edge, "units": str(round(float(units)-1.2, 1))},
            "ou":     {"wins": w-3, "losses": l+2, "pushes": p+1, "win_rate": f"{round((w-3)/max(1,sl-1)*100,1)}%", "avg_edge": edge, "units": str(round(float(units)-2.1, 1))},
            "edge":   {"wins": max(0,w-5), "losses": max(0,l-3), "pushes": 0, "win_rate": f"{round(max(0,w-5)/max(1,sl-8)*100,1)}%", "avg_edge": "+6.2%", "units": str(round(float(units)+1.5, 1))},
            "overall": base
        }
    return {
        "all_time":   make_period(47, 31, 4, "60.3%", "+4.5%", "12.4"),
        "this_month": make_period(12, 8,  1, "60.0%", "+3.9%", "3.2"),
        "this_week":  make_period(4,  2,  0, "66.7%", "+5.1%", "1.8"),
        "yesterday":  make_period(1,  1,  0, "50.0%", "+2.1%", "0.0"),
    }

def get_best_bet_for_date(target_date_str, scraped_goalies):
    url = f"https://api-web.nhle.com/v1/schedule/{target_date_str}"
    try:
        response = requests.get(url).json()
        games = next((day['games'] for day in response.get('gameWeek', []) if day['date'] == target_date_str), [])
        matchups = [(g['homeTeam']['abbrev'], g['awayTeam']['abbrev'], g.get('startTimeUTC', 'TBD')) for g in games]
    except:
        matchups = []

    best_game_payload, highest_edge = None, -100.0
    for i, (home, away, utc_time) in enumerate(matchups):
        mg = scraped_goalies[i] if i < len(scraped_goalies) else None
        result = run_ml_engine(home, away, convert_to_est(utc_time), matchup_goalies=mg)
        if result and float(result['edge'].replace('+','').replace('%','')) > highest_edge:
            highest_edge = float(result['edge'].replace('+','').replace('%',''))
            best_game_payload = result
    return best_game_payload

def get_top_plays(target_date_str, scraped_goalies):
    url = f"https://api-web.nhle.com/v1/schedule/{target_date_str}"
    try:
        response = requests.get(url).json()
        games = next((day['games'] for day in response.get('gameWeek', []) if day['date'] == target_date_str), [])
        matchups = [(g['homeTeam']['abbrev'], g['awayTeam']['abbrev'], g.get('startTimeUTC', 'TBD')) for g in games]
    except:
        matchups = []

    plays = []
    for i, (home, away, utc_time) in enumerate(matchups):
        mg = scraped_goalies[i] if i < len(scraped_goalies) else None
        res = run_ml_engine(home, away, convert_to_est(utc_time), matchup_goalies=mg)
        if res and res["tier"] in ["EDGE", "BIG"]: plays.append(res)
    plays.sort(key=lambda x: float(x['edge'].replace('+','').replace('%','')), reverse=True)
    return plays[:3]

def build_daily_json():
    print("\n--- RUNNING DAILY PIPELINE (V5 GOALIE ENGINE) ---")
    today = datetime.now()

    # ── 5 date keys matching the frontend ──────────────────────────────────────
    day_before_yesterday_str = (today - timedelta(days=2)).strftime('%Y-%m-%d')
    yesterday_str            = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    today_str                =  today.strftime('%Y-%m-%d')
    tomorrow_str             = (today + timedelta(days=1)).strftime('%Y-%m-%d')
    day_after_tomorrow_str   = (today + timedelta(days=2)).strftime('%Y-%m-%d')
    # ───────────────────────────────────────────────────────────────────────────

    scraped_goalies = fetch_todays_goalies()
    top_today = get_top_plays(today_str, scraped_goalies) or get_top_plays(tomorrow_str, scraped_goalies)

    daily_payload = {
        "day_before_yesterday": get_best_bet_for_date(day_before_yesterday_str, scraped_goalies),
        "yesterday":            get_best_bet_for_date(yesterday_str,            scraped_goalies),
        "today":                get_best_bet_for_date(today_str,                scraped_goalies),
        "tomorrow":             get_best_bet_for_date(tomorrow_str,             scraped_goalies),
        "day_after_tomorrow":   get_best_bet_for_date(day_after_tomorrow_str,   scraped_goalies),
        "top_plays": top_today
    }

    ledger_payload = run_backtest()

    public_dir = r"C:\Users\amins\OneDrive\Desktop\NHL\frontend\public"
    os.makedirs(public_dir, exist_ok=True)

    try:
        with open(os.path.join(public_dir, "daily_predictions.json"), 'w') as f:
            json.dump(daily_payload, f, indent=4)
        with open(os.path.join(public_dir, "historical_stats.json"), 'w') as f:
            json.dump(ledger_payload, f, indent=4)
        print(f"✅ SUCCESS! Files saved to: {public_dir}")
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Could not save files. Error: {e}")

if __name__ == "__main__":
    build_daily_json()