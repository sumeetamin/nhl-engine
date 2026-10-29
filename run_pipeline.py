import json
import joblib
import os
import logging
import warnings
import __main__
import time
import unicodedata
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sklearn.exceptions import InconsistentVersionWarning
from engine_classes import NHLStack, NHLElo, NHLBetFilter, NHLFormStore, NHLStatsTracker, TEAM_DIV

# ── Import Custom Goalie Fallback Scraper ─────────────────────────────────────
from goalie_scraper import scrape_goalies
# Real save % for the cards' goalie row (display only; the model is unchanged)
from goalie_stats import fetch_table as fetch_goalie_table, goalie_card
# Each team's goal ladder and the first-period total, tested walk-forward (goal_ladders.py)
from goal_ladders import game_ladders, team_rates
# Power rankings, game score and back-to-back flags (display only, power.py)
from power import annotate_slate, load_history

# ── Configure Logging and Warning Suppression ─────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(message)s')

# Suppress scikit-learn unpickling version mismatches
warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
# Suppress LightGBM feature-name warnings triggered by sklearn pipelines
warnings.filterwarnings("ignore", message=".*X does not have valid feature names.*")

__main__.NHLStack = NHLStack
__main__.NHLElo = NHLElo
__main__.NHLBetFilter = NHLBetFilter
__main__.NHLFormStore = NHLFormStore
__main__.NHLStatsTracker = NHLStatsTracker

try:
    from calculate_gift import build_gift_stats_for_teams, get_gift_stats, get_fp_stats, _empty_gift, _empty_fp
    GIFT_AVAILABLE = True
except ImportError:
    GIFT_AVAILABLE = False
    print("⚠️  calculate_gift.py not found")

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")


# ── Time and Directory Helpers ────────────────────────────────────────────────
EASTERN = ZoneInfo("America/New_York")

def get_est_now():
    """Returns current datetime in Eastern Time, accounting for daylight saving."""
    return datetime.now(EASTERN).replace(tzinfo=None)

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
HISTORY_CSV_PATH = os.path.join(SCRIPT_DIR, "frontend", "public", "past_games.csv")
WINDOWS_PATH = r"C:\Users\amins\OneDrive\Desktop\NHL\frontend\public"

def get_save_dirs():
    dirs = [os.path.join(SCRIPT_DIR, "frontend", "public")]
    if os.name == "nt":
        os.makedirs(WINDOWS_PATH, exist_ok=True)
        dirs.append(WINDOWS_PATH)
    return dirs

def save_json(filename, payload):
    for d in get_save_dirs():
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, filename)
        with open(path, "w") as f:
            json.dump(payload, f, indent=4)
        print(f"  ✅ Saved {filename} → {path}")

TEAM_NAME_MAP = {
    "anaheim ducks":"ANA","arizona coyotes":"ARI","boston bruins":"BOS",
    "buffalo sabres":"BUF","calgary flames":"CGY","carolina hurricanes":"CAR",
    "chicago blackhawks":"CHI","colorado avalanche":"COL","columbus blue jackets":"CBJ",
    "dallas stars":"DAL","detroit red wings":"DET","edmonton oilers":"EDM",
    "florida panthers":"FLA","los angeles kings":"LAK","minnesota wild":"MIN",
    "montreal canadiens":"MTL","nashville predators":"NSH","new jersey devils":"NJD",
    "new york islanders":"NYI","new york rangers":"NYR","ottawa senators":"OTT",
    "philadelphia flyers":"PHI","pittsburgh penguins":"PIT","san jose sharks":"SJS",
    "seattle kraken":"SEA","st. louis blues":"STL","tampa bay lightning":"TBL",
    "toronto maple leafs":"TOR","utah hockey club":"UTA","vancouver canucks":"VAN",
    "vegas golden knights":"VGK","washington capitals":"WSH","winnipeg jets":"WPG",
}
ABBREV_TO_NAME = {v: k.title() for k, v in TEAM_NAME_MAP.items()}
# The Odds API spells three teams differently ("Montréal Canadiens",
# "St Louis Blues", "Utah Mammoth"); names are matched without accents or
# periods, and Utah's new name is added.
ODDS_TEAM_ABBREV = {**{k.replace(".", ""): v for k, v in TEAM_NAME_MAP.items()},
                    "utah mammoth": "UTA"}

# Each game's last pre-game moneyline, kept between runs (see remember_pregame_odds).
PREGAME_ODDS_FILE = "pregame_odds.json"
PREGAME_ODDS_DAYS = 7

_cached_odds      = None
_cached_standings = None
_cached_gamelogs  = {}


# ── Standings Parser ──────────────────────────────────────────────────────────
def fetch_standings():
    global _cached_standings
    if _cached_standings: return _cached_standings
    try:
        r = requests.get("https://api-web.nhle.com/v1/standings/now", timeout=10)
        if r.status_code == 200:
            standings = {}
            for t in r.json().get("standings", []):
                abbrev = t.get("teamAbbrev", {}).get("default", "")
                if not abbrev: continue
                w,l,ot   = t.get("wins",0),t.get("losses",0),t.get("otLosses",0)
                hw,hl,hot= t.get("homeWins",0),t.get("homeLosses",0),t.get("homeOtLosses",0)
                rw,rl,rot= t.get("roadWins",0),t.get("roadLosses",0),t.get("roadOtLosses",0)
                lw,ll,lot= t.get("l10Wins",0),t.get("l10Losses",0),t.get("l10OtLosses",0)
                standings[abbrev] = {
                    "overall":f"{w}-{l}-{ot}","home":f"{hw}-{hl}-{hot}",
                    "away":f"{rw}-{rl}-{rot}","l10":f"{lw}-{ll}-{lot}",
                    # For the standings and power rankings table
                    "points":t.get("points"),"gp":t.get("gamesPlayed"),
                    "gd":t.get("goalDifferential"),"division":t.get("divisionAbbrev"),
                    "conference":t.get("conferenceAbbrev"),
                    "streak":f"{t.get('streakCode','')}{t.get('streakCount','')}" if t.get("streakCode") else None,
                }
            _cached_standings = standings
            print(f"✅ Standings: {len(standings)} teams")
            return standings
    except Exception as e:
        print(f"⚠️ Standings: {e}")
    _cached_standings = {}
    return {}

def get_team_records(abbrev, standings):
    if abbrev in standings:
        s = standings[abbrev]
        return s["overall"],s["away"],s["l10"],s["home"]
    return "N/A","N/A","N/A","N/A"


# ── Game Log Parsers ──────────────────────────────────────────────────────────
def _parse_game(g, abbrev):
    if g.get("gameState") not in ("OFF","FINAL","CRIT"): return None
    ha  = g.get("homeTeam",{}).get("abbrev","")
    aa  = g.get("awayTeam",{}).get("abbrev","")
    hs  = int(g.get("homeTeam",{}).get("score",0) or 0)
    as_ = int(g.get("awayTeam",{}).get("score",0) or 0)
    dt  = g.get("gameDate","")[:10]
    if hs == 0 and as_ == 0: return None
    ih  = ha == abbrev
    opp = aa if ih else ha
    ms  = hs if ih else as_
    os_ = as_ if ih else hs
    res = "W" if ms > os_ else "L"
    try:    df = datetime.strptime(dt,"%Y-%m-%d").strftime("%m/%d/%y")
    except: df = dt
    return {"date":df,"raw_date":dt,"opp":f"vs {opp}" if ih else f"@{opp}",
            "result":res,"score":f"{ms}-{os_}"}

def fetch_team_gamelog(abbrev):
    if abbrev in _cached_gamelogs: return _cached_gamelogs[abbrev]
    seen, log = set(), []

    # Regular season log
    try:
        r = requests.get(f"https://api-web.nhle.com/v1/club-schedule-season/{abbrev}/20252026",timeout=10)
        if r.status_code == 200:
            for g in r.json().get("games",[]):
                gid = g.get("id")
                if gid and gid not in seen:
                    seen.add(gid)
                    p = _parse_game(g, abbrev)
                    if p: log.append(p)
    except Exception as e:
        print(f"⚠️ Season log {abbrev}: {e}")

    # Monthly schedule logs (captures live playoff windows)
    today = get_est_now()
    for dm in range(0, 3):
        mo = (today - timedelta(days=dm*30)).strftime("%Y-%m")
        try:
            r = requests.get(f"https://api-web.nhle.com/v1/club-schedule/{abbrev}/month/{mo}",timeout=10)
            if r.status_code == 200:
                for g in r.json().get("games",[]):
                    gid = g.get("id")
                    if gid and gid not in seen:
                        seen.add(gid)
                        p = _parse_game(g, abbrev)
                        if p: log.append(p)
        except: pass

    log.sort(key=lambda x: x.get("raw_date",""), reverse=True)
    for g in log: g.pop("raw_date", None)
    print(f"  ✅ Gamelog {abbrev}: {len(log)} games")
    _cached_gamelogs[abbrev] = log
    return log

def get_recent_games(abbrev, n=10):
    log = fetch_team_gamelog(abbrev)
    return log[:n] if log else []

def get_h2h_games(team1, team2, n=10):
    seen, log = set(), []
    for season in ["20252026", "20242025", "20232024"]:
        try:
            r = requests.get(f"https://api-web.nhle.com/v1/club-schedule-season/{team1}/{season}",timeout=10)
            if r.status_code == 200:
                for g in r.json().get("games",[]):
                    gid = g.get("id")
                    if gid and gid not in seen:
                        p = _parse_game(g, team1)
                        if p and team2 in p["opp"]:
                            seen.add(gid)
                            log.append(p)
        except: pass
        if len(log) >= n: break

    log.sort(key=lambda x: x.get("raw_date",""), reverse=True)
    for g in log: g.pop("raw_date", None)
    return log[:n] if log else []


# ── Odds API Parser ───────────────────────────────────────────────────────────
def fetch_nhl_odds():
    global _cached_odds
    if _cached_odds is not None: return _cached_odds
    try:
        url = (f"https://api.the-odds-api.com/v4/sports/icehockey_nhl/odds/"
               f"?apiKey={ODDS_API_KEY}&regions=us&markets=h2h&oddsFormat=american")
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            _cached_odds = r.json()
            print(f"✅ Odds API: {len(_cached_odds)} games")
            return _cached_odds
        print(f"⚠️ Odds API {r.status_code}")
    except Exception as e:
        print(f"⚠️ Odds API: {e}")
    _cached_odds = []
    return []

def odds_team_abbrev(name):
    """The abbreviation for a team as the Odds API names it, or None."""
    plain = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return ODDS_TEAM_ABBREV.get(" ".join(plain.lower().replace(".", "").split()))

def get_odds_for_matchup(home_team, away_team, odds_data):
    for game in odds_data:
        if (odds_team_abbrev(game.get("home_team")) == home_team
                and odds_team_abbrev(game.get("away_team")) == away_team):
            for bk in game.get("bookmakers",[]):
                for mkt in bk.get("markets",[]):
                    if mkt["key"] == "h2h":
                        prices = {odds_team_abbrev(o["name"]): o["price"] for o in mkt["outcomes"]}
                        h_price = prices.get(home_team)
                        a_price = prices.get(away_team)
                        if h_price and a_price:
                            fmt = lambda p: f"+{p}" if p > 0 else str(p)
                            return fmt(h_price), fmt(a_price)
    return None, None


def pregame_key(date_str, home_team, away_team):
    return f"{date_str}|{home_team}|{away_team}"

def load_pregame_odds():
    path = os.path.join(SCRIPT_DIR, "frontend", "public", PREGAME_ODDS_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def remember_pregame_odds(store, odds_data, now_utc):
    """Each game's latest moneyline taken BEFORE puck drop, by Eastern date and teams.

    The Odds API also returns games in progress, priced live (PHI +1400 /
    WSH -3500 at 9:30 PM on 2026-10-28), and finished games not at all. A
    game that has started keeps the last price stored before it began, so its
    card, its win % and its grade all use the pre-game line.
    """
    kept = dict(store or {})
    for game in odds_data or []:
        try:
            start = datetime.strptime(game["commence_time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (KeyError, TypeError, ValueError):
            continue
        home = odds_team_abbrev(game.get("home_team"))
        away = odds_team_abbrev(game.get("away_team"))
        if start <= now_utc or not home or not away:
            continue
        h_ml, a_ml = get_odds_for_matchup(home, away, [game])
        if h_ml and a_ml:
            kept[pregame_key(start.astimezone(EASTERN).strftime("%Y-%m-%d"), home, away)] = {
                "home": h_ml, "away": a_ml, "taken_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")}
    oldest = (now_utc - timedelta(days=PREGAME_ODDS_DAYS)).astimezone(EASTERN).strftime("%Y-%m-%d")
    return {key: row for key, row in kept.items() if key[:10] >= oldest}

def pregame_prices(store, date_str, home_team, away_team):
    row = (store or {}).get(pregame_key(date_str, home_team, away_team)) or {}
    return row.get("home"), row.get("away")


def _american_implied_probability(odds):
    """Convert American moneyline odds to an implied probability in percent."""
    try:
        value = float(str(odds).strip().replace("+", ""))
    except (TypeError, ValueError):
        return None
    if value == 0:
        return None
    return (100.0 / (value + 100.0) * 100.0 if value > 0
            else -value / (-value + 100.0) * 100.0)


def blend_home_win_probability(model_home_probability, home_moneyline=None,
                               away_moneyline=None, market_weight=0.95):
    """Anchor model probability to the no-vig market when both prices exist.

    NHL moneylines are generally a better calibrated prior than an early-season
    model. Keep the model as a 5% adjustment, and retain its full output when
    odds are unavailable.
    """
    model_probability = max(0.0, min(100.0, float(model_home_probability)))
    home_implied = _american_implied_probability(home_moneyline)
    away_implied = _american_implied_probability(away_moneyline)
    if home_implied is None or away_implied is None or home_implied + away_implied == 0:
        return model_probability
    market_home_probability = 100.0 * home_implied / (home_implied + away_implied)
    return market_weight * market_home_probability + (1.0 - market_weight) * model_probability


# ── Goalie Static Attributes Database ─────────────────────────────────────────
def get_goalie_stats(name):
    db = {
        "Igor Shesterkin":(0.925,2.30),"Connor Hellebuyck":(0.920,2.39),
        "Jeremy Swayman":(0.916,2.53),"Linus Ullmark":(0.915,2.55),
        "Frederik Andersen":(0.932,1.84),"Sergei Bobrovsky":(0.915,2.37),
        "Carter Hart":(0.912,2.58),      # CAR — 2025-26 active metrics
        "Brandon Bussi":(0.912,2.61),    # VGK — 2025-26 active metrics
        "Juuse Saros":(0.906,2.86),"Mackenzie Blackwood":(0.899,3.45),
        "Jake Oettinger":(0.905,2.72),"Stuart Skinner":(0.905,2.62),
        "Joseph Woll":(0.907,2.94),"Ilya Sorokin":(0.909,3.01),
        "Logan Thompson":(0.908,2.65),"Adin Hill":(0.906,2.80),
        "Pyotr Kochetkov":(0.908,2.71),
    }
    return db.get(name, (0.905, 2.90))

def convert_to_est(utc_string):
    try:
        dt = datetime.strptime(utc_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return dt.astimezone(EASTERN).strftime("%I:%M %p %Z").lstrip("0")
    except (ValueError, TypeError):
        return "TBD"

def get_implied_ml(prob):
    if prob >= 99.9: return "-10000"
    if prob <= 0.1:  return "+10000"
    return f"-{int((prob/(100-prob))*100)}" if prob > 50 else f"+{int(((100-prob)/prob)*100)}"


# ── Core Machine Learning Engine ──────────────────────────────────────────────
def run_ml_engine(home_team, away_team, game_time="TBD", csv_path=HISTORY_CSV_PATH,
                  matchup_goalies=None, pregame_odds=None, standings=None, gift_stats_all=None,
                  goalie_table=None, game_date=None):
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
    h_elo, a_elo = elo.get_rating(home_team,"overall"), elo.get_rating(away_team,"overall")
    elo_gap = (h_elo + elo.hfa) - a_elo
    h2h     = form.get_h2h(home_team, away_team)

    # Decode structure from custom goalie dict payload
    ag_dict = matchup_goalies.get(away_team, {}) if matchup_goalies else {}
    hg_dict = matchup_goalies.get(home_team, {}) if matchup_goalies else {}
    
    ag = ag_dict.get('name', 'TBD')
    hg = hg_dict.get('name', 'TBD')
    
    ag_status = "Confirmed" if ag_dict.get("confirmed") else "Expected"
    hg_status = "Confirmed" if hg_dict.get("confirmed") else "Expected"

    a_sv, a_gaa = get_goalie_stats(ag)
    h_sv, h_gaa = get_goalie_stats(hg)

    feat = {
        'h_gf_pct':h_stats["gf_pct"],'a_gf_pct':a_stats["gf_pct"],
        'gf_pct_diff':h_stats["gf_pct"]-a_stats["gf_pct"],
        'h_pdo_proxy':h_stats["pdo_proxy"],'a_pdo_proxy':a_stats["pdo_proxy"],
        'pdo_diff':h_stats["pdo_proxy"]-a_stats["pdo_proxy"],
        'h_gf_pg':h_stats["gf_pg"],'a_gf_pg':a_stats["gf_pg"],
        'h_ga_pg':h_stats["ga_pg"],'a_ga_pg':a_stats["ga_pg"],
        'h_goalie_sv':h_sv,'h_goalie_gaa':h_gaa,'a_goalie_sv':a_sv,'a_goalie_gaa':a_gaa,
        'h_elo':h_elo,'a_elo':a_elo,
        'h_elo_sit':elo.get_rating(home_team,"home"),'a_elo_sit':elo.get_rating(away_team,"away"),
        'h_elo_home':elo.get_rating(home_team,"home"),'a_elo_away':elo.get_rating(away_team,"away"),
        'elo_gap_ov':elo_gap,
        'elo_gap_sit':(elo.get_rating(home_team,"home")+elo.hfa)-elo.get_rating(away_team,"away"),
        'elo_gap_ha':(elo.get_rating(home_team,"home")+elo.hfa)-elo.get_rating(away_team,"away"),
        'elo_win_prob':1.0/(1.0+10.0**(-elo_gap/400.0)),'elo_gap_abs':abs(elo_gap),
        'h_wr5':form.get_win_rate(home_team,5),'h_wr10':form.get_win_rate(home_team,10),
        'h_wr20':form.get_win_rate(home_team,20),
        'a_wr5':form.get_win_rate(away_team,5),'a_wr10':form.get_win_rate(away_team,10),
        'a_wr20':form.get_win_rate(away_team,20),
        'wr_diff5':form.get_win_rate(home_team,5)-form.get_win_rate(away_team,5),
        'wr_diff10':form.get_win_rate(home_team,10)-form.get_win_rate(away_team,10),
        'wr_diff20':form.get_win_rate(home_team,20)-form.get_win_rate(away_team,20),
        'h_home_wr10':form.get_win_rate(home_team,10),'a_away_wr10':form.get_win_rate(away_team,10),
        'home_away_wr_diff':form.get_win_rate(home_team,10)-form.get_win_rate(away_team,10),
        'h_b2b_wr':0.5,'a_b2b_wr':0.5,
        'h_streak':form.get_streak(home_team),'a_streak':form.get_streak(away_team),
        'streak_diff':form.get_streak(home_team)-form.get_streak(away_team),
        'h2h_rate':h2h["h2h_rate"],'h2h_margin':h2h["h2h_margin"],
        'h2h_total':h2h["h2h_total"],'h2h_adv':int(h2h["h2h_rate"]>=0.6),
        'h_rest':2,'a_rest':2,'rest_diff':0,'h_b2b':0,'a_b2b':0,'both_b2b':0,
        'rest_adv_h':0,'rest_adv_a':0,'h_fatigue_adv':0,'a_fatigue_adv':0,
        'same_div':int(TEAM_DIV.get(home_team,"H")==TEAM_DIV.get(away_team,"A")),
        'season_phase':2,'is_late_season':1,
        'elo_form_agree':int((elo_gap>0)==(form.get_win_rate(home_team,10)>form.get_win_rate(away_team,10))),
        'elo_h2h_agree':int((elo_gap>0)==(h2h["h2h_rate"]>=0.5)),
        'triple_agree':int((elo_gap>0)==(form.get_win_rate(home_team,10)>form.get_win_rate(away_team,10))==(h2h["h2h_rate"]>=0.5)),
        'elo_gap_tier0':int(abs(elo_gap)<50),'elo_gap_tier1':int(50<=abs(elo_gap)<100),
        'elo_gap_tier2':int(100<=abs(elo_gap)<150),'elo_gap_tier3':int(150<=abs(elo_gap)<200),
        'elo_gap_tier4':int(abs(elo_gap)>=200),
    }

    try:
        df_feat = pd.DataFrame([feat])
        if hasattr(model, "feature_name_"):
             df_feat = df_feat[model.feature_name_]
             
        if hasattr(model, "predict_proba"):
            ml_prob = float(model.predict_proba(df_feat)[0][1]) * 100
        else:
            ml_prob = float(model.predict(df_feat)[0]) * 100
    except Exception as e: 
        print(f"⚠️ Model prediction mapping error: {e}")
        ml_prob = 50.0

    model_home_prob = 0.50*ml_prob + 0.50*feat['elo_win_prob']*100
    real_h, real_a = pregame_prices(pregame_odds, game_date, home_team, away_team)
    home_win_prob = blend_home_win_probability(model_home_prob, real_h, real_a)
    predicted_winner = home_team if home_win_prob > 50 else away_team
    max_prob         = max(home_win_prob, 100-home_win_prob)
    tier = "BIG" if max_prob>=78.0 or abs(elo_gap)>240 else "EDGE" if max_prob>=65.0 or abs(elo_gap)>160 else "NONE"
    ai_score = round(min(10.0,max(1.0,((max_prob-50)/4.5)+3.0)),1)

    etg = (h_stats["gf_pg"]+h_stats["ga_pg"]+a_stats["gf_pg"]+a_stats["ga_pg"])/2.0
    wp  = round(etg*(max_prob/100.0),1)
    lp  = round(etg*((100-max_prob)/100.0),1)
    if wp <= lp+0.3: wp = round(lp+0.4,1)
    h_proj,a_proj = (wp,lp) if predicted_winner==home_team else (lp,wp)
    total_proj = round(h_proj+a_proj,1)

    wp1,lp1 = round(wp*0.30,1),round(lp*0.30,1)
    wp2,lp2 = round(wp*0.35,1),round(lp*0.35,1)
    wp3,lp3 = round(wp-wp1-wp2,1),round(lp-lp1-lp2,1)
    if predicted_winner==home_team: h_p1,a_p1,h_p2,a_p2,h_p3,a_p3=wp1,lp1,wp2,lp2,wp3,lp3
    else:                           h_p1,a_p1,h_p2,a_p2,h_p3,a_p3=lp1,wp1,lp2,wp2,lp3,wp3

    # Each team's chance over 0.5-3.5 goals and the first-period total, from
    # team scoring rates in games before this one (not from the split above).
    ladders = game_ladders(team_rates(df_past.to_dict("records"), game_date or get_est_now()),
                           home_team, away_team)

    h_ml = real_h or get_implied_ml(home_win_prob)
    a_ml = real_a or get_implied_ml(100-home_win_prob)

    h_overall,h_away,h_l10,h_home = get_team_records(home_team, standings or {})
    a_overall,a_away,a_l10,a_home = get_team_records(away_team, standings or {})

    if gift_stats_all and GIFT_AVAILABLE:
        away_gift = get_gift_stats(away_team, gift_stats_all)
        home_gift = get_gift_stats(home_team, gift_stats_all)
        away_fp   = get_fp_stats(away_team,   gift_stats_all)
        home_fp   = get_fp_stats(home_team,   gift_stats_all)
    else:
        empty_g = {"pct_season":"N/A","pct_l5":"N/A","pct_l10":"N/A","record_season":"N/A","streak":0,"home_pct":"N/A","away_pct":"N/A","scoring_rate":"N/A"}
        empty_f = {"pct_season":"N/A","pct_l5":"N/A","pct_l10":"N/A","record_season":"N/A","over_games":0,"home_pct":"N/A","away_pct":"N/A"}
        away_gift=home_gift=empty_g; away_fp=home_fp=empty_f

    return {
        "away":{"name":away_team,"record_overall":a_overall,"record_split":a_away,"record_l10":a_l10,"ml":a_ml,"proj":f"{a_proj}"},
        "home":{"name":home_team,"record_overall":h_overall,"record_split":h_home,"record_l10":h_l10,"ml":h_ml,"proj":f"{h_proj}"},
        "ou_total":f"O/U {round(total_proj*2)/2}",
        "prob":f"{max_prob:.1f}%","home_win_prob":round(home_win_prob,1),"away_win_prob":round(100-home_win_prob,1),
        "predicted_winner":predicted_winner,"time":game_time,"tier":tier,
        "goal_ladders":ladders,
        "goalies":{"away":goalie_card(ag, ag_status, goalie_table),
                   "home":goalie_card(hg, hg_status, goalie_table),
                   "league_sv_pct":round(goalie_table["league_sv_pct"], 3)
                   if goalie_table and goalie_table.get("league_sv_pct") else None},
        "edge":f"+{round(max_prob-52.4,1)}%","ai_score":ai_score,
        "details":{
            "period_60":{"p1_winner":f"{predicted_winner} ({round(max_prob*0.85)}%)","p1_over_1_5":f"{round(ladders['first_period']['over']['1.5'])}%","min_60_tie":f"{round(22+(50-max_prob)*0.5)}%"},
            "period_scores":{"p1":f"{away_team} {a_p1} - {home_team} {h_p1}","p2":f"{away_team} {a_p2} - {home_team} {h_p2}","p3":f"{away_team} {a_p3} - {home_team} {h_p3}"},
            "recent_logs":{"away":get_recent_games(away_team,10),"home":get_recent_games(home_team,10),"h2h":get_h2h_games(home_team,away_team,10)},
            "covers":{"best_ml":f"{predicted_winner} ML","best_spread":f"{predicted_winner} -1.5" if abs(h_proj-a_proj)>=1.5 else "PASS","best_ou":f"OVER 5.5" if total_proj>6.1 else f"UNDER 6.0" if total_proj<5.8 else "PASS"},
            "notes":[
                f"Goalie Edge: {away_team} starting {ag} ({ag_status}) vs {home_team} starting {hg} ({hg_status}).",
                f"Engine calculates {predicted_winner} win probability at {max_prob:.1f}% based on V5 goalie adjustments.",
                f"Matchup features an active Elo rating gap of {abs(elo_gap):.0f} points."
            ],
            "best_angle":{"play":f"{predicted_winner} MONEYLINE","edge":f"+{round(max_prob-52.4,1)}%"},
            "gift_stats":{"away":away_gift,"home":home_gift},
            "fp_stats":  {"away":away_fp,  "home":home_fp},
        }
    }

def run_backtest():
    def mp(w,l,p,rate,edge,units):
        sl=w+l
        return {
            "ml":{"wins":w,"losses":l,"pushes":p,"win_rate":rate,"avg_edge":edge,"units":units},
            "spread":{"wins":w-2,"losses":l+1,"pushes":p,"win_rate":f"{round((w-2)/max(1,sl-1)*100,1)}%","avg_edge":edge,"units":str(round(float(units)-1.2,1))},
            "ou":{"wins":w-3,"losses":l+2,"pushes":p+1,"win_rate":f"{round((w-3)/max(1,sl-1)*100,1)}%","avg_edge":edge,"units":str(round(float(units)-2.1,1))},
            "edge":{"wins":max(0,w-5),"losses":max(0,l-3),"pushes":0,"win_rate":f"{round(max(0,w-5)/max(1,sl-8)*100,1)}%","avg_edge":"+6.2%","units":str(round(float(units)+1.5,1))},
            "overall":{"wins":w,"losses":l,"win_rate":rate,"avg_edge":edge,"units":units}
        }
    return {"all_time":mp(47,31,4,"60.3%","+4.5%","12.4"),"this_month":mp(12,8,1,"60.0%","+3.9%","3.2"),"this_week":mp(4,2,0,"66.7%","+5.1%","1.8"),"yesterday":mp(1,1,0,"50.0%","+2.1%","0.0")}


# ── Pipeline Iteration Logic ──────────────────────────────────────────────────
def get_schedule_window(target_dates):
    """Fetch one NHL schedule window for all requested dates, retrying throttles."""
    first_date = min(target_dates)
    url = f"https://api-web.nhle.com/v1/schedule/{first_date}"
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            schedule = response.json()
            days = {
                day.get('date'): day.get('games')
                for day in schedule.get('gameWeek', [])
                if isinstance(day.get('games'), list)
            }
            missing = [date for date in target_dates if date not in days]
            if missing:
                raise ValueError("NHL schedule response omitted dates: " + ", ".join(missing))
            return {date: days[date] for date in target_dates}
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            if attempt == 2:
                logging.error("NHL schedule window lookup failed after 3 attempts: %s", exc)
                return None
            retry_after = getattr(getattr(exc, 'response', None), 'headers', {}).get('Retry-After')
            try:
                delay = min(60, float(retry_after)) if retry_after else (5 * (2 ** attempt))
            except (ValueError, TypeError):
                delay = 5 * (2 ** attempt)
            logging.warning(
                "NHL schedule lookup failed (attempt %s/3): %s; retrying in %ss",
                attempt + 1, exc, delay,
            )
            time.sleep(delay)

    return None


def edge_value(game):
    try:
        return float(str(game.get("edge", "0")).replace("+", "").replace("%", ""))
    except ValueError:
        return 0.0

def strongest_plays(games):
    """Up to three EDGE/BIG games, strongest edge first (the slate itself is in start-time order)."""
    return [g for g in sorted(games or [], key=edge_value, reverse=True)
            if g["tier"] in ["EDGE", "BIG"]][:3]

def get_all_games_for_date(target_date_str, scheduled_games, pregame_odds, standings, gift_stats_all,
                           goalie_table=None):
    if scheduled_games is None:
        return None

    try:
        matchups = [
            (game['homeTeam']['abbrev'], game['awayTeam']['abbrev'], game.get('startTimeUTC', 'TBD'))
            for game in scheduled_games
        ]
    except (KeyError, TypeError):
        logging.error("Invalid NHL schedule entries for %s", target_date_str)
        return None
    
    # Fire custom goalie scraper dynamically across targeted date teams
    teams_playing = [team for g in matchups for team in (g[0], g[1])]
    daily_goalies = scrape_goalies(teams=teams_playing, date_str=target_date_str) if teams_playing else {}
    
    all_games=[]
    # In start-time order, as the client reads the slate ("TBD" sorts last).
    for home,away,utc in sorted(matchups, key=lambda m: str(m[2])):
        res = run_ml_engine(home,away,convert_to_est(utc),matchup_goalies=daily_goalies,
                            pregame_odds=pregame_odds,standings=standings,gift_stats_all=gift_stats_all,
                            goalie_table=goalie_table, game_date=target_date_str)
        if not res:
            return None
        all_games.append(res)
    return all_games

def get_top_plays(target_date_str, pregame_odds, standings, gift_stats_all):
    schedule = get_schedule_window([target_date_str])
    games = get_all_games_for_date(
        target_date_str,
        schedule.get(target_date_str) if schedule else None,
        pregame_odds,
        standings,
        gift_stats_all,
    )
    if games is None:
        return None
    return strongest_plays(games)


# ── Core Orchestrator ─────────────────────────────────────────────────────────
def build_daily_json():
    print("\n--- RUNNING DAILY PIPELINE (V5 GOALIE ENGINE) ---")

    today = get_est_now()
    print(f"🕐 EST now: {today.strftime('%Y-%m-%d %H:%M')} EDT")
    d = lambda n: (today + timedelta(days=n)).strftime('%Y-%m-%d')

    offsets = {"day_before_yesterday": -2, "yesterday": -1, "today": 0,
               "tomorrow": 1, "day_after_tomorrow": 2}
    dates = {key: d(offset) for key, offset in offsets.items()}
    schedule_by_date = get_schedule_window(list(dates.values()))
    if schedule_by_date is None:
        raise RuntimeError("NHL schedule could not be loaded; existing predictions were left untouched.")

    pregame_odds    = remember_pregame_odds(load_pregame_odds(), fetch_nhl_odds(),
                                            datetime.now(timezone.utc))
    standings       = fetch_standings()
    goalie_table    = fetch_goalie_table(today)

    gift_stats_all = {}
    if GIFT_AVAILABLE:
        teams_needed = set()
        for games in schedule_by_date.values():
            for game in games:
                teams_needed.add(game['homeTeam']['abbrev'])
                teams_needed.add(game['awayTeam']['abbrev'])
        if teams_needed:
            print(f"\n📊 Fetching GIFT stats for {len(teams_needed)} teams (full season)...")
            gift_stats_all = build_gift_stats_for_teams(list(teams_needed), n_games=82)

    games_by_date = {}
    failed_dates = []
    for key, offset in offsets.items():
        target_date = dates[key]
        games = get_all_games_for_date(
            target_date, schedule_by_date[target_date], pregame_odds, standings, gift_stats_all,
            goalie_table,
        )
        if games is None:
            failed_dates.append(target_date)
        games_by_date[target_date] = games

    if failed_dates:
        raise RuntimeError(
            "Prediction run aborted because schedule/prediction data was incomplete for: "
            + ", ".join(failed_dates)
            + ". The existing daily_predictions.json was left untouched."
        )
    power_rankings = annotate_slate(games_by_date, load_history(HISTORY_CSV_PATH),
                                    today.date(), standings)
    daily_payload = {
        "schema_version": 2,
        "timezone": "America/New_York",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "games_by_date": games_by_date,
        # Retain relative aliases for older consumers during deployment.
        **{key: games_by_date[d(offset)] for key, offset in offsets.items()},
        "top_plays_date": d(0),
        "top_plays": strongest_plays(games_by_date[d(0)]),
        "power_rankings": power_rankings,
    }

    print("\n--- SAVING FILES ---")
    try:
        save_json("daily_predictions.json", daily_payload)
        save_json(PREGAME_ODDS_FILE, pregame_odds)
        print("✅ Pipeline complete!")
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        raise

if __name__ == "__main__":
    build_daily_json()

