"""
track_results.py
Runs daily via GitHub Actions (10:00 UTC, after overnight games finish).

Does three things:
  1. Appends any new completed games to past_games.csv
     → ELO + form + score projections update automatically next pipeline run
  2. Grades yesterday's predictions from daily_predictions.json
     → Records ML / Spread / O/U pick accuracy
  3. Writes real cumulative stats to historical_stats.json
     (replaces the hardcoded mock data in run_backtest())
"""

import json, os, requests, sys
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR    = Path(__file__).resolve().parent
CSV_PATH      = SCRIPT_DIR / "frontend" / "public" / "past_games.csv"
PRED_PATH     = SCRIPT_DIR / "frontend" / "public" / "daily_predictions.json"
GRADE_LOG     = SCRIPT_DIR / "frontend" / "public" / "grade_log.json"
HIST_PATH     = SCRIPT_DIR / "frontend" / "public" / "historical_stats.json"

WINDOWS_CSV   = r"C:\Users\amins\OneDrive\Desktop\NHL\frontend\public\past_games.csv"
WINDOWS_HIST  = r"C:\Users\amins\OneDrive\Desktop\NHL\frontend\public\historical_stats.json"

PLAYOFFS_START = "2026-04-19"   # first day of 2026 playoffs

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_est_now():
    est = datetime.now(timezone.utc) - timedelta(hours=4)
    return est.replace(tzinfo=None)

def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_json(path, default):
    if Path(path).exists():
        try:
            with open(path) as f:
                return json.load(f)
        except:
            pass
    return default

# ── 1. CSV UPDATE — append new completed games ────────────────────────────────
def fetch_all_completed_games():
    """Scan every date from playoffs start to today and collect completed games."""
    today     = get_est_now()
    start     = datetime.strptime(PLAYOFFS_START, "%Y-%m-%d")
    seen      = set()
    all_games = []

    current = start
    while current <= today:
        date_str = current.strftime("%Y-%m-%d")
        url      = f"https://api-web.nhle.com/v1/schedule/{date_str}"
        try:
            resp = requests.get(url, timeout=10).json()
            for day in resp.get("gameWeek", []):
                for g in day.get("games", []):
                    if g.get("gameState") not in ("OFF", "FINAL", "CRIT"):
                        continue
                    gid = g.get("id")
                    if gid in seen:
                        continue
                    seen.add(gid)

                    home_abbr  = g["homeTeam"]["abbrev"]
                    away_abbr  = g["awayTeam"]["abbrev"]
                    home_score = int(g["homeTeam"].get("score", 0) or 0)
                    away_score = int(g["awayTeam"].get("score", 0) or 0)

                    if home_score == 0 and away_score == 0:
                        continue

                    # Use the scheduled game date (already in EDT from NHL API)
                    game_date  = day.get("date", date_str)
                    winner     = home_abbr if home_score > away_score else away_abbr

                    all_games.append({
                        "Date":         game_date,
                        "Away":         away_abbr,
                        "Home":         home_abbr,
                        "Actual_Winner": winner,
                        "Away_Score":   away_score,
                        "Home_Score":   home_score,
                    })
        except Exception as e:
            print(f"  ⚠️  Schedule {date_str}: {e}")

        current += timedelta(days=1)

    return all_games


def update_past_games_csv():
    """Append any new completed games to past_games.csv."""
    print("\n📋 STEP 1: Updating past_games.csv")

    # Load existing CSV — support both 4-col and 6-col formats
    paths = [CSV_PATH]
    if os.name == "nt":
        paths.append(Path(WINDOWS_CSV))

    csv_path = None
    for p in paths:
        if p.exists():
            csv_path = p
            break

    if csv_path:
        df = pd.read_csv(csv_path)
    else:
        df = pd.DataFrame(columns=["Date","Away","Home","Actual_Winner","Away_Score","Home_Score"])
        csv_path = CSV_PATH

    # Ensure score columns exist (backward compat with old 4-col CSV)
    for col in ["Away_Score", "Home_Score"]:
        if col not in df.columns:
            df[col] = None

    existing_keys = set(zip(
        df["Date"].astype(str),
        df["Away"].astype(str),
        df["Home"].astype(str)
    ))

    # Fetch all games
    all_games = fetch_all_completed_games()
    new_rows  = []
    for g in all_games:
        key = (g["Date"], g["Away"], g["Home"])
        if key not in existing_keys:
            new_rows.append(g)
            existing_keys.add(key)

    if not new_rows:
        print("  ✅ CSV already up to date — no new games found")
        return df

    new_df = pd.DataFrame(new_rows)
    df     = pd.concat([df, new_df], ignore_index=True)
    df     = df.sort_values("Date").reset_index(drop=True)

    for save_path in paths:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(save_path, index=False)
        print(f"  ✅ Added {len(new_rows)} game(s) → {save_path}")

    for row in new_rows:
        score_line = f"{row['Away']} {row['Away_Score']} @ {row['Home']} {row['Home_Score']}"
        print(f"     ➕ {row['Date']}  {score_line}  → {row['Actual_Winner']} wins")

    return df


# ── 2. GRADE PICKS — compare yesterday's predictions to actual ────────────────
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

def fetch_actual_scores_for_date(date_str):
    """Returns dict keyed by frozenset({home, away}) → {winner, home_score, away_score}."""
    url = f"https://api-web.nhle.com/v1/schedule/{date_str}"
    results = {}
    try:
        resp = requests.get(url, timeout=10).json()
        for day in resp.get("gameWeek", []):
            if day.get("date") != date_str:
                continue
            for g in day.get("games", []):
                if g.get("gameState") not in ("OFF", "FINAL", "CRIT"):
                    continue
                h = g["homeTeam"]["abbrev"]
                a = g["awayTeam"]["abbrev"]
                hs = int(g["homeTeam"].get("score", 0) or 0)
                as_ = int(g["awayTeam"].get("score", 0) or 0)
                if hs == 0 and as_ == 0:
                    continue
                winner = h if hs > as_ else a
                results[frozenset([h, a])] = {
                    "winner": winner, "home": h, "away": a,
                    "home_score": hs, "away_score": as_,
                    "total": hs + as_
                }
    except Exception as e:
        print(f"  ⚠️  Scores fetch {date_str}: {e}")
    return results


def grade_prediction(pred, actual):
    """
    Grade a single game prediction dict against actual result dict.
    Returns dict of {pick_type: "W"/"L"/"P"}.
    """
    pw      = pred.get("predicted_winner", "")
    aw      = actual["winner"]
    total   = actual["total"]
    grades  = {}

    # ML (moneyline)
    grades["ml"] = "W" if pw == aw else "L"

    # Spread: predicted winner covers -1.5 if they won by 2+
    h, a = actual["home"], actual["away"]
    hs, as_ = actual["home_score"], actual["away_score"]
    winner_margin = abs(hs - as_)
    grades["spread"] = "W" if (pw == aw and winner_margin >= 2) else ("P" if winner_margin == 1 else "L")

    # O/U — read from prediction
    covers = pred.get("details", {}).get("covers", {})
    ou_call = covers.get("best_ou", "PASS")
    if "OVER" in ou_call:
        threshold = float(ou_call.split()[-1]) if len(ou_call.split()) > 1 else 5.5
        grades["ou"] = "W" if total > threshold else "L"
    elif "UNDER" in ou_call:
        threshold = float(ou_call.split()[-1]) if len(ou_call.split()) > 1 else 6.0
        grades["ou"] = "W" if total < threshold else "L"
    else:
        grades["ou"] = "P"

    # Edge tier
    tier = pred.get("tier", "NONE")
    grades["edge"] = "W" if (tier in ("EDGE","BIG") and pw == aw) else ("L" if tier in ("EDGE","BIG") else "P")

    return grades


def grade_yesterday_picks():
    """Load daily_predictions.json, grade 'yesterday' slot, save results."""
    print("\n📊 STEP 2: Grading yesterday's picks")

    if not PRED_PATH.exists():
        print("  ⚠️  daily_predictions.json not found — skipping grade")
        return

    preds = load_json(PRED_PATH, {})
    yesterday_games = preds.get("yesterday", [])

    if not yesterday_games:
        print("  ℹ️  No games in yesterday slot")
        return

    # Determine the date from the first game's time field (e.g. "7:00 PM EST")
    # We can compute yesterday in EDT directly
    yesterday_edt = (get_est_now() - timedelta(days=1)).strftime("%Y-%m-%d")
    actual_scores = fetch_actual_scores_for_date(yesterday_edt)

    if not actual_scores:
        print(f"  ⚠️  No actual scores found for {yesterday_edt}")
        return

    grade_log  = load_json(GRADE_LOG, [])
    new_grades = []

    for pred in yesterday_games:
        h = pred.get("home", {}).get("name", "")
        a = pred.get("away", {}).get("name", "")
        key = frozenset([h, a])

        if key not in actual_scores:
            print(f"  ⚠️  No actual score for {a} @ {h}")
            continue

        actual  = actual_scores[key]
        grades  = grade_prediction(pred, actual)
        pw      = pred.get("predicted_winner", "?")
        aw      = actual["winner"]

        grade_entry = {
            "date":      yesterday_edt,
            "matchup":   f"{a} @ {h}",
            "predicted": pw,
            "actual":    aw,
            "score":     f"{actual['away_score']}-{actual['home_score']}",
            "tier":      pred.get("tier", "NONE"),
            "edge":      pred.get("edge", "N/A"),
            "grades":    grades,
        }
        grade_log.append(grade_entry)
        new_grades.append(grade_entry)

        result_icon = "✅" if grades["ml"] == "W" else "❌"
        print(f"  {result_icon} {a} @ {h}: predicted {pw}, actual {aw} ({actual['away_score']}-{actual['home_score']}) | ML:{grades['ml']} Spread:{grades['spread']} OU:{grades['ou']}")

    if new_grades:
        save_json(GRADE_LOG, grade_log)
        print(f"  💾 grade_log.json updated ({len(grade_log)} total graded games)")

    return grade_log


# ── 3. HISTORICAL STATS — compute real cumulative performance ─────────────────
def build_historical_stats(grade_log):
    """Aggregate grade_log into historical_stats.json for the Snapshot tab."""
    if not grade_log:
        return {}

    from datetime import date as date_cls

    today     = get_est_now().date()
    yesterday = today - timedelta(days=1)
    week_ago  = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    def parse_date(s):
        try:    return datetime.strptime(s, "%Y-%m-%d").date()
        except: return None

    def calc_period(entries, pick_types=("ml","spread","ou","edge")):
        out = {}
        for pt in pick_types:
            picks = [e["grades"].get(pt) for e in entries if e["grades"].get(pt) != "P"]
            w = sum(1 for p in picks if p == "W")
            l = sum(1 for p in picks if p == "L")
            total = w + l
            out[pt] = {
                "wins":     w,
                "losses":   l,
                "pushes":   sum(1 for e in entries if e["grades"].get(pt) == "P"),
                "win_rate": f"{w/total*100:.1f}%" if total else "N/A",
                "avg_edge": "N/A",
                "units":    str(round(w * 0.91 - l, 1)),  # -110 juice approximation
            }
        out["overall"] = {
            "wins":     out["ml"]["wins"],
            "losses":   out["ml"]["losses"],
            "win_rate": out["ml"]["win_rate"],
            "avg_edge": "N/A",
            "units":    out["ml"]["units"],
        }
        return out

    all_entries       = grade_log
    yesterday_entries = [e for e in all_entries if parse_date(e["date"]) == yesterday]
    week_entries      = [e for e in all_entries if parse_date(e["date"]) and parse_date(e["date"]) >= week_ago]
    month_entries     = [e for e in all_entries if parse_date(e["date"]) and parse_date(e["date"]) >= month_ago]

    stats = {
        "all_time":   calc_period(all_entries),
        "this_month": calc_period(month_entries),
        "this_week":  calc_period(week_entries),
        "yesterday":  calc_period(yesterday_entries),
    }

    # Save to both paths
    for save_path in [HIST_PATH]:
        save_json(save_path, stats)
    if os.name == "nt":
        save_json(WINDOWS_HIST, stats)

    ml = stats["all_time"]["ml"]
    print(f"\n  📈 All-time: {ml['wins']}W-{ml['losses']}L ({ml['win_rate']}) | units: {ml['units']}")
    print(f"  💾 historical_stats.json updated")
    return stats


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== TRACK RESULTS PIPELINE ===")
    update_past_games_csv()
    grade_log = grade_yesterday_picks()
    if grade_log:
        build_historical_stats(grade_log)
    print("\n✅ Done.")