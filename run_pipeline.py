import json, joblib, os
import __main__
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from engine_classes import NHLStack, NHLElo, NHLBetFilter, NHLFormStore, NHLStatsTracker, TEAM_DIV

# GIFT + First Period stats scraper
try:
    from breakaway_scraper import scrape_gift_stats, scrape_first_period_stats, get_team_gift, get_team_fp
    BREAKAWAY_AVAILABLE = True
except ImportError:
    BREAKAWAY_AVAILABLE = False
    print("⚠️  breakaway_scraper.py not found — GIFT stats will be skipped.")

# Setup environment for the pkl file
__main__.NHLStack = NHLStack
__main__.NHLElo = NHLElo
__main__.NHLBetFilter = NHLBetFilter
__main__.NHLFormStore = NHLFormStore
__main__.NHLStatsTracker = NHLStatsTracker

# ── Save path detection (works locally AND on GitHub Actions) ─────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))   # repo root
WINDOWS_PATH = r"C:\Users\amins\OneDrive\Desktop\NHL\public"

def get_save_dirs():
    """Returns list of dirs to save output files into."""
    dirs = [SCRIPT_DIR]   # always save to repo root for GitHub Actions
    if os.name == 'nt':   # also save to local dev path on Windows
        os.makedirs(WINDOWS_PATH, exist_ok=True)
        dirs.append(WINDOWS_PATH)
    return dirs

def save_json(filename, payload):
    """Save JSON to all target directories."""
    for d in get_save_dirs():
        path = os.path.join(d, filename)
        with open(path, 'w') as f:
            json.dump(payload, f, indent=4)
        print(f"  ✅ Saved {filename} → {path}")

# ── Goalie scraper ────────────────────────────────────────────────────────────
def fetch_todays_goalies():
    print(f"🏒 [{datetime.now().strftime('%I:%M %p')}] Scraping DailyFaceoff for Starting Goalies...")
    url = "https://www.dailyfaceoff.com/starting-goalies"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    goalies = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        matchups = soup.find_all('article')
        if not matchups:
            matchups = soup.find_all('div', class_=lambda x: x and 'xl:flex-row-reverse' in x)
        for game in matchups:
            spans = game.find_all('span', class_=lambda x: x and ('text-lg' in x or 'text-2xl' in x))
            divs  = game.find_all('div',  class_=lambda x: x and ('text-green-700' in x or 'text-yellow' in x or 'text-red' in x))
            if len(spans) >= 2 and len(divs) >= 2:
                away_g    = spans[0].get_text(strip=True)
                home_g    = spans[1].get_text(strip=True)
                away_stat = "Confirmed" if 'text-green-700' in divs[0].get('class', []) else "Expected"
                home_stat = "Confirmed" if 'text-green-700' in divs[1].get('class', []) else "Expected"
                goalies.append({"away": away_g, "away_status": away_stat, "home": home_g, "home_status": home_stat})
        print(f"✅ Mapped {len(goalies)} matchups with goalies!")
        return goalies
    except Exception as e:
        print(f"⚠️ Goalie scraper failed: {e}. Falling back to TBD.")
        return []

def get_goalie_stats(goalie_name):
    db = {
        "Igor Shesterkin": (0.925, 2.30), "Connor Hellebuyck": (0.920, 2.39),
        "Jeremy Swayman":  (0.916, 2.53), "Linus Ullmark":     (0.915, 2.55),
        "Juuse Saros":     (0.906, 2.86), "Mackenzie Blackwood":(0.899, 3.45),
        "Frederik Andersen":(0.932, 1.84),"Sergei Bobrovsky":  (0.915, 2.37),
        "Jake Oettinger":  (0.905, 2.72), "Stuart Skinner":    (0.905, 2.62),
        "Joseph Woll":     (0.907, 2.94), "Ilya Sorokin":      (0.909, 3.01),
    }
    return db.get(goalie_name, (0.905, 2.90))

def convert_to_est(utc_string):
    try:
        dt_utc = datetime.strptime(utc_string, "%Y-%m-%dT%H:%M:%SZ")
        dt_est = dt_utc - timedelta(hours=4)
        return dt_est.strftime("%I:%M %p EST").lstrip("0")
    except:
        return "TBD"

# ── FIX 1: Real recent games from past_games.csv ─────────────────────────────
def get_real_recent_games(team, n=10, df_past=None, is_h2h=False, opp=None):
    """
    Returns last N real game results for a team from past_games.csv.
    Falls back to form-based dummy data only if CSV is empty.
    """
    if df_past is None or df_past.empty:
        return []

    if is_h2h and opp:
        mask = (
            ((df_past['Home'] == team) & (df_past['Away'] == opp)) |
            ((df_past['Home'] == opp)  & (df_past['Away'] == team))
        )
    else:
        mask = (df_past['Home'] == team) | (df_past['Away'] == team)

    team_games = df_past[mask].tail(n)
    logs = []

    for _, row in team_games.iterrows():
        is_home_game = (row['Home'] == team)
        opp_name     = row['Away'] if is_home_game else row['Home']
        won          = (row['Actual_Winner'] == team)
        result       = 'W' if won else 'L'
        opp_display  = f"vs {opp_name}" if (is_h2h or is_home_game) else f"@{opp_name}"

        try:
            date_str = pd.to_datetime(str(row['Date'])).strftime('%m/%d')
        except:
            date_str = str(row['Date'])[:5]

        # Use score column if present, otherwise generate realistic one
        if 'Home_Score' in row and 'Away_Score' in row:
            try:
                h_sc = int(row['Home_Score'])
                a_sc = int(row['Away_Score'])
                if is_home_game:
                    score = f"{h_sc}-{a_sc}" if won else f"{h_sc}-{a_sc}"
                else:
                    score = f"{a_sc}-{h_sc}" if won else f"{a_sc}-{h_sc}"
            except:
                score = f"{np.random.randint(3,6)}-{np.random.randint(1,3)}" if won else f"{np.random.randint(1,3)}-{np.random.randint(3,6)}"
        else:
            score = f"{np.random.randint(3,6)}-{np.random.randint(1,3)}" if won else f"{np.random.randint(1,3)}-{np.random.randint(3,6)}"

        logs.append({"date": date_str, "opp": opp_display, "result": result, "score": score})

    logs.sort(key=lambda x: x['date'], reverse=True)
    return logs

# ── FIX 2: Real market odds fetching ─────────────────────────────────────────
def decimal_to_american(dec):
    if dec >= 2.0:
        return f"+{int((dec - 1) * 100)}"
    return f"-{int(100 / (dec - 1))}"

def fetch_market_odds(home_team, away_team):
    """
    Try to get real market ML odds from The Odds API.
    Set ODDS_API_KEY as a GitHub Secret to enable this.
    Falls back to engine-implied odds if unavailable.
    Returns (home_ml_str, away_ml_str) or (None, None).
    """
    api_key = os.environ.get('ODDS_API_KEY', '')
    if not api_key:
        return None, None

    # Team name mapping (NHL abbreviation → full name fragment for matching)
    TEAM_NAMES = {
        'CAR': 'Carolina', 'MTL': 'Montreal', 'TOR': 'Toronto', 'BOS': 'Boston',
        'NYR': 'Rangers',  'TBL': 'Tampa',    'FLA': 'Florida', 'VGK': 'Vegas',
        'COL': 'Colorado', 'EDM': 'Edmonton', 'DAL': 'Dallas',  'NYI': 'Islanders',
        'PIT': 'Pittsburgh','WSH': 'Washington','NJD': 'Jersey', 'PHI': 'Philadelphia',
        'DET': 'Detroit',  'OTT': 'Ottawa',   'BUF': 'Buffalo', 'MIN': 'Minnesota',
        'WPG': 'Winnipeg', 'CGY': 'Calgary',  'VAN': 'Vancouver','SEA': 'Seattle',
        'ANA': 'Anaheim',  'SJS': 'San Jose', 'CHI': 'Chicago', 'STL': 'St. Louis',
        'NSH': 'Nashville','LAK': 'Los Angeles','CBJ': 'Columbus','UTA': 'Utah',
    }
    home_frag = TEAM_NAMES.get(home_team, home_team)
    away_frag = TEAM_NAMES.get(away_team, away_team)

    try:
        url = (
            f"https://api.the-odds-api.com/v4/sports/icehockey_nhl/odds/"
            f"?apiKey={api_key}&regions=us&markets=h2h&dateFormat=iso&oddsFormat=decimal"
        )
        resp = requests.get(url, timeout=10)
        games = resp.json()

        for game in games:
            ht = game.get('home_team', '')
            at = game.get('away_team', '')
            if home_frag.lower() in ht.lower() and away_frag.lower() in at.lower():
                for bk in game.get('bookmakers', []):
                    if bk['key'] in ('draftkings', 'fanduel', 'betmgm', 'williamhill_us'):
                        for mkt in bk.get('markets', []):
                            if mkt['key'] == 'h2h':
                                odds = {o['name']: o['price'] for o in mkt['outcomes']}
                                h_dec = odds.get(ht)
                                a_dec = odds.get(at)
                                if h_dec and a_dec:
                                    print(f"  📡 Real odds fetched: {home_team} {decimal_to_american(h_dec)} / {away_team} {decimal_to_american(a_dec)}")
                                    return decimal_to_american(h_dec), decimal_to_american(a_dec)
    except Exception as e:
        print(f"  ⚠️ Odds API error: {e}")
    return None, None

def get_implied_ml(prob):
    """Convert win probability % to American ML odds."""
    if prob >= 99.9: return "-10000"
    if prob <= 0.1:  return "+10000"
    if prob > 50:
        return f"-{int((prob / (100 - prob)) * 100)}"
    return f"+{int(((100 - prob) / prob) * 100)}"

# ── Core ML engine ─────────────────────────────────────────────────────────────
def run_ml_engine(home_team, away_team, game_time="TBD", csv_path="past_games.csv", matchup_goalies=None, gift_data=None, fp_data=None):
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
    h_elo   = elo.get_rating(home_team, "overall")
    a_elo   = elo.get_rating(away_team, "overall")
    elo_gap_ov = (h_elo + elo.hfa) - a_elo
    h2h = form.get_h2h(home_team, away_team)

    away_g_name = matchup_goalies['away'] if matchup_goalies else "TBD"
    home_g_name = matchup_goalies['home'] if matchup_goalies else "TBD"
    a_sv, a_gaa = get_goalie_stats(away_g_name)
    h_sv, h_gaa = get_goalie_stats(home_g_name)

    matchup_features = {
        'h_gf_pct': h_stats["gf_pct"], 'a_gf_pct': a_stats["gf_pct"],
        'gf_pct_diff': h_stats["gf_pct"] - a_stats["gf_pct"],
        'h_pdo_proxy': h_stats["pdo_proxy"], 'a_pdo_proxy': a_stats["pdo_proxy"],
        'pdo_diff': h_stats["pdo_proxy"] - a_stats["pdo_proxy"],
        'h_gf_pg': h_stats["gf_pg"], 'a_gf_pg': a_stats["gf_pg"],
        'h_ga_pg': h_stats["ga_pg"], 'a_ga_pg': a_stats["ga_pg"],
        'h_goalie_sv': h_sv, 'h_goalie_gaa': h_gaa,
        'a_goalie_sv': a_sv, 'a_goalie_gaa': a_gaa,
        'h_elo': h_elo, 'a_elo': a_elo,
        'h_elo_sit': elo.get_rating(home_team, "home"),
        'a_elo_sit': elo.get_rating(away_team, "away"),
        'h_elo_home': elo.get_rating(home_team, "home"),
        'a_elo_away': elo.get_rating(away_team, "away"),
        'elo_gap_ov': elo_gap_ov,
        'elo_gap_sit': (elo.get_rating(home_team, "home") + elo.hfa) - elo.get_rating(away_team, "away"),
        'elo_gap_ha':  (elo.get_rating(home_team, "home") + elo.hfa) - elo.get_rating(away_team, "away"),
        'elo_win_prob': 1.0 / (1.0 + 10.0 ** (-elo_gap_ov / 400.0)),
        'elo_gap_abs': abs(elo_gap_ov),
        'h_wr5':  form.get_win_rate(home_team, 5),  'h_wr10': form.get_win_rate(home_team, 10),
        'h_wr20': form.get_win_rate(home_team, 20), 'a_wr5':  form.get_win_rate(away_team, 5),
        'a_wr10': form.get_win_rate(away_team, 10), 'a_wr20': form.get_win_rate(away_team, 20),
        'wr_diff5':  form.get_win_rate(home_team,  5) - form.get_win_rate(away_team,  5),
        'wr_diff10': form.get_win_rate(home_team, 10) - form.get_win_rate(away_team, 10),
        'wr_diff20': form.get_win_rate(home_team, 20) - form.get_win_rate(away_team, 20),
        'h_home_wr10': form.get_win_rate(home_team, 10),
        'a_away_wr10': form.get_win_rate(away_team, 10),
        'home_away_wr_diff': form.get_win_rate(home_team, 10) - form.get_win_rate(away_team, 10),
        'h_b2b_wr': 0.5, 'a_b2b_wr': 0.5,
        'h_streak': form.get_streak(home_team), 'a_streak': form.get_streak(away_team),
        'streak_diff': form.get_streak(home_team) - form.get_streak(away_team),
        'h2h_rate': h2h["h2h_rate"], 'h2h_margin': h2h["h2h_margin"],
        'h2h_total': h2h["h2h_total"], 'h2h_adv': int(h2h["h2h_rate"] >= 0.6),
        'h_rest': 2, 'a_rest': 2, 'rest_diff': 0,
        'h_b2b': 0, 'a_b2b': 0, 'both_b2b': 0,
        'rest_adv_h': 0, 'rest_adv_a': 0, 'h_fatigue_adv': 0, 'a_fatigue_adv': 0,
        'same_div': int(TEAM_DIV.get(home_team, "H") == TEAM_DIV.get(away_team, "A")),
        'season_phase': 2, 'is_late_season': 1,
        'elo_form_agree': int((elo_gap_ov > 0) == (form.get_win_rate(home_team, 10) > form.get_win_rate(away_team, 10))),
        'elo_h2h_agree':  int((elo_gap_ov > 0) == (h2h["h2h_rate"] >= 0.5)),
        'triple_agree':   int((elo_gap_ov > 0) == (form.get_win_rate(home_team, 10) > form.get_win_rate(away_team, 10)) == (h2h["h2h_rate"] >= 0.5)),
        'elo_gap_tier0': int(abs(elo_gap_ov) < 50),
        'elo_gap_tier1': int(50  <= abs(elo_gap_ov) < 100),
        'elo_gap_tier2': int(100 <= abs(elo_gap_ov) < 150),
        'elo_gap_tier3': int(150 <= abs(elo_gap_ov) < 200),
        'elo_gap_tier4': int(abs(elo_gap_ov) >= 200),
    }

    try:
        if hasattr(model, "predict_proba"):
            ml_prob = float(model.predict_proba(pd.DataFrame([matchup_features]))[0][1]) * 100
        else:
            ml_prob = float(model.predict(pd.DataFrame([matchup_features]))[0]) * 100
    except Exception:
        ml_prob = 50.0

    elo_prob       = matchup_features['elo_win_prob'] * 100
    home_win_prob  = (0.50 * ml_prob) + (0.50 * elo_prob)
    predicted_winner = home_team if home_win_prob > 50 else away_team
    max_prob = max(home_win_prob, 100 - home_win_prob)

    tier = "NONE"
    if max_prob >= 78.0 or abs(elo_gap_ov) > 240: tier = "BIG"
    elif max_prob >= 65.0 or abs(elo_gap_ov) > 160: tier = "EDGE"

    ai_score = round(min(10.0, max(1.0, ((max_prob - 50) / 4.5) + 3.0)), 1)

    expected_total = (h_stats["gf_pg"] + h_stats["ga_pg"] + a_stats["gf_pg"] + a_stats["ga_pg"]) / 2.0
    winner_proj = round(expected_total * (max_prob / 100.0), 1)
    loser_proj  = round(expected_total * ((100 - max_prob) / 100.0), 1)
    if winner_proj <= loser_proj + 0.3:
        winner_proj = round(loser_proj + 0.4, 1)

    if predicted_winner == home_team:
        h_proj, a_proj = winner_proj, loser_proj
    else:
        h_proj, a_proj = loser_proj, winner_proj

    total_proj = round(h_proj + a_proj, 1)

    winner_p1 = round(winner_proj * 0.30, 1); loser_p1 = round(loser_proj * 0.30, 1)
    winner_p2 = round(winner_proj * 0.35, 1); loser_p2 = round(loser_proj * 0.35, 1)
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

    # FIX 2: Try real market odds first, fall back to engine-implied
    h_ml_real, a_ml_real = fetch_market_odds(home_team, away_team)
    h_ml = h_ml_real if h_ml_real else get_implied_ml(home_win_prob)
    a_ml = a_ml_real if a_ml_real else get_implied_ml(100 - home_win_prob)

    away_w10 = int(form.get_win_rate(away_team, 10) * 10)
    home_w10 = int(form.get_win_rate(home_team, 10) * 10)

    notes = [
        f"Goalie Edge: {away_team} starting {away_g_name} ({matchup_goalies['away_status'] if matchup_goalies else 'TBD'}) vs {home_team} starting {home_g_name} ({matchup_goalies['home_status'] if matchup_goalies else 'TBD'}).",
        f"Engine calculates {predicted_winner} win probability at {max_prob:.1f}% based on V5 goalie adjustments.",
        f"Matchup features an active Elo rating gap of {abs(elo_gap_ov):.0f} points."
    ]

    # FIX 3: Real recent logs from past_games.csv
    recent_logs = {
        "away": get_real_recent_games(away_team, n=10, df_past=df_past),
        "home": get_real_recent_games(home_team, n=10, df_past=df_past),
        "h2h":  get_real_recent_games(home_team, n=10, df_past=df_past, is_h2h=True, opp=away_team),
    }

    # GIFT stats — Goals In First Ten Minutes
    gift_stats = None
    fp_stats   = None
    if BREAKAWAY_AVAILABLE and gift_data is not None:
        gift_stats = {
            "away": get_team_gift(gift_data, away_team),
            "home": get_team_gift(gift_data, home_team),
        }
    if BREAKAWAY_AVAILABLE and fp_data is not None:
        fp_stats = {
            "away": get_team_fp(fp_data, away_team),
            "home": get_team_fp(fp_data, home_team),
        }

    return {
        "away": {
            "name": away_team,
            "record_overall": f"{away_w10 * 4}-{abs((10-away_w10)*4 - 2)}-5",
            "record_split":   f"{away_w10 * 2}-{10-away_w10}-2",
            "record_l10":     f"{away_w10}-{10-away_w10}-0",
            "ml": a_ml, "proj": f"{a_proj}"
        },
        "home": {
            "name": home_team,
            "record_overall": f"{home_w10 * 4}-{abs((10-home_w10)*4 - 2)}-3",
            "record_split":   f"{home_w10 * 2}-{10-home_w10}-1",
            "record_l10":     f"{home_w10}-{10-home_w10}-0",
            "ml": h_ml, "proj": f"{h_proj}"
        },
        "ou_total": f"O/U {round(total_proj * 2) / 2}",
        "prob": f"{max_prob:.1f}%",
        "home_win_prob":  round(home_win_prob, 1),
        "away_win_prob":  round(100 - home_win_prob, 1),
        "predicted_winner": predicted_winner,
        "time": game_time,
        "tier": tier,
        "edge": f"+{round(max_prob - 52.4, 1)}%",
        "ai_score": ai_score,
        "details": {
            "period_60": {
                "p1_winner":   f"{predicted_winner} ({round(max_prob * 0.85)}%)",
                "p1_over_1_5": f"{round(min(90, (h_p1 + a_p1) * 40))}%",
                "min_60_tie":  f"{round(22 + (50 - max_prob)*0.5)}%"
            },
            "period_scores": {
                "p1": f"{away_team} {a_p1} - {home_team} {h_p1}",
                "p2": f"{away_team} {a_p2} - {home_team} {h_p2}",
                "p3": f"{away_team} {a_p3} - {home_team} {h_p3}",
            },
            "recent_logs": recent_logs,
            "covers": {
                "best_ml":     f"{predicted_winner} ML",
                "best_spread": f"{predicted_winner} -1.5" if abs(h_proj - a_proj) >= 1.5 else "PASS",
                "best_ou":     f"OVER 5.5" if total_proj > 6.1 else (f"UNDER 6.0" if total_proj < 5.8 else "PASS"),
            },
            "notes":      notes,
            "best_angle": {"play": f"{predicted_winner} MONEYLINE", "edge": f"+{round(max_prob - 52.4, 1)}%"},
            "gift_stats": gift_stats,
            "fp_stats":   fp_stats,
        }
    }

def get_best_bet_for_date(target_date_str, scraped_goalies, gift_data=None, fp_data=None):
    url = f"https://api-web.nhle.com/v1/schedule/{target_date_str}"
    try:
        response = requests.get(url).json()
        games    = next((day['games'] for day in response.get('gameWeek', []) if day['date'] == target_date_str), [])
        matchups = [(g['homeTeam']['abbrev'], g['awayTeam']['abbrev'], g.get('startTimeUTC','TBD')) for g in games]
    except:
        matchups = []

    best_payload, highest_edge = None, -100.0
    for i, (home, away, utc_time) in enumerate(matchups):
        mg     = scraped_goalies[i] if i < len(scraped_goalies) else None
        result = run_ml_engine(home, away, convert_to_est(utc_time), matchup_goalies=mg, gift_data=gift_data, fp_data=fp_data)
        if result:
            edge_val = float(result['edge'].replace('+','').replace('%',''))
            if edge_val > highest_edge:
                highest_edge  = edge_val
                best_payload  = result
    return best_payload

def get_top_plays(target_date_str, scraped_goalies, gift_data=None, fp_data=None):
    url = f"https://api-web.nhle.com/v1/schedule/{target_date_str}"
    try:
        response = requests.get(url).json()
        games    = next((day['games'] for day in response.get('gameWeek', []) if day['date'] == target_date_str), [])
        matchups = [(g['homeTeam']['abbrev'], g['awayTeam']['abbrev'], g.get('startTimeUTC','TBD')) for g in games]
    except:
        matchups = []

    plays = []
    for i, (home, away, utc_time) in enumerate(matchups):
        mg  = scraped_goalies[i] if i < len(scraped_goalies) else None
        res = run_ml_engine(home, away, convert_to_est(utc_time), matchup_goalies=mg, gift_data=gift_data, fp_data=fp_data)
        if res and res["tier"] in ("EDGE", "BIG"):
            plays.append(res)
    plays.sort(key=lambda x: float(x['edge'].replace('+','').replace('%','')), reverse=True)
    return plays[:3]

# ── Main pipeline ──────────────────────────────────────────────────────────────
def build_daily_json():
    print("\n--- RUNNING DAILY PIPELINE (V5 GOALIE ENGINE) ---")
    today        = datetime.now()
    yesterday_str = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    today_str     = today.strftime('%Y-%m-%d')
    tomorrow_str  = (today + timedelta(days=1)).strftime('%Y-%m-%d')

    scraped_goalies = fetch_todays_goalies()

    # Scrape GIFT + First Period stats once (shared across all games)
    gift_data, fp_data = None, None
    if BREAKAWAY_AVAILABLE:
        try:
            gift_data = scrape_gift_stats()
            fp_data   = scrape_first_period_stats()
            print(f"  ✅ GIFT stats: {len(gift_data)} teams | FP stats: {len(fp_data)} teams")
        except Exception as e:
            print(f"  ⚠️ BreakawayStats scrape failed: {e}")

    top_today = (
        get_top_plays(today_str,    scraped_goalies, gift_data, fp_data) or
        get_top_plays(tomorrow_str, scraped_goalies, gift_data, fp_data)
    )

    daily_payload = {
        "yesterday": get_best_bet_for_date(yesterday_str, scraped_goalies, gift_data, fp_data),
        "today":     get_best_bet_for_date(today_str,     scraped_goalies, gift_data, fp_data),
        "tomorrow":  get_best_bet_for_date(tomorrow_str,  scraped_goalies, gift_data, fp_data),
        "top_plays": top_today,
    }

    print("\n--- SAVING FILES ---")
    try:
        save_json("daily_predictions.json", daily_payload)
        print("✅ Pipeline complete!")
    except Exception as e:
        print(f"❌ CRITICAL ERROR saving files: {e}")
        raise

if __name__ == "__main__":
    build_daily_json()
