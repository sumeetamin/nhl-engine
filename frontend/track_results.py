"""
track_results.py
Runs daily via GitHub Actions (10:00 UTC).

1. Appends new completed games to past_games.csv  → model improves
2. Grades yesterday's picks from daily_predictions.json
3. Writes real stats to historical_stats.json  (replaces mock data)
4. Saves results_index.json  → frontend result panels (HIT/MISS display)
"""

import json, os, requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR    = Path(__file__).resolve().parent
CSV_PATH      = SCRIPT_DIR / "frontend" / "public" / "past_games.csv"
PRED_PATH     = SCRIPT_DIR / "frontend" / "public" / "daily_predictions.json"
GRADE_LOG     = SCRIPT_DIR / "frontend" / "public" / "grade_log.json"
HIST_PATH     = SCRIPT_DIR / "frontend" / "public" / "historical_stats.json"
RESULTS_PATH  = SCRIPT_DIR / "frontend" / "public" / "results_index.json"

WINDOWS_BASE  = r"C:\Users\amins\OneDrive\Desktop\NHL\frontend\public"
PLAYOFFS_START = "2026-04-19"

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

def all_save_paths(filename):
    paths = [SCRIPT_DIR / "frontend" / "public" / filename]
    if os.name == "nt":
        paths.append(Path(WINDOWS_BASE) / filename)
    return paths

# ── 1. CSV UPDATE ─────────────────────────────────────────────────────────────
def fetch_all_completed_games():
    today   = get_est_now()
    start   = datetime.strptime(PLAYOFFS_START, "%Y-%m-%d")
    seen    = set()
    games   = []
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
                    home       = g["homeTeam"]["abbrev"]
                    away       = g["awayTeam"]["abbrev"]
                    home_score = int(g["homeTeam"].get("score", 0) or 0)
                    away_score = int(g["awayTeam"].get("score", 0) or 0)
                    if home_score == 0 and away_score == 0:
                        continue
                    game_date = day.get("date", date_str)
                    winner    = home if home_score > away_score else away
                    games.append({
                        "Date":          game_date,
                        "Away":          away,
                        "Home":          home,
                        "Actual_Winner": winner,
                        "Away_Score":    away_score,
                        "Home_Score":    home_score,
                    })
        except Exception as e:
            print(f"  ⚠️  Schedule {date_str}: {e}")
        current += timedelta(days=1)

    return games


def update_past_games_csv():
    print("\n📋 STEP 1: Updating past_games.csv")

    # Find existing CSV
    csv_path = None
    for p in all_save_paths("past_games.csv"):
        if p.exists():
            csv_path = p
            break

    if csv_path:
        df = pd.read_csv(csv_path)
    else:
        df       = pd.DataFrame(columns=["Date","Away","Home","Actual_Winner","Away_Score","Home_Score"])
        csv_path = CSV_PATH

    for col in ["Away_Score", "Home_Score"]:
        if col not in df.columns:
            df[col] = None

    existing_keys = set(zip(df["Date"].astype(str), df["Away"].astype(str), df["Home"].astype(str)))

    all_games = fetch_all_completed_games()
    new_rows  = []
    for g in all_games:
        key = (g["Date"], g["Away"], g["Home"])
        if key not in existing_keys:
            new_rows.append(g)
            existing_keys.add(key)

    if not new_rows:
        print("  ✅ CSV already up to date")
        return df

    df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    df = df.sort_values("Date").reset_index(drop=True)

    for p in all_save_paths("past_games.csv"):
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(p, index=False)
        print(f"  ✅ +{len(new_rows)} game(s) → {p}")

    for r in new_rows:
        print(f"     ➕ {r['Date']}  {r['Away']} {r['Away_Score']} @ {r['Home']} {r['Home_Score']}  → {r['Actual_Winner']}")

    return df


# ── 2. GRADE PICKS ────────────────────────────────────────────────────────────
def fetch_actual_scores_for_date(date_str):
    url     = f"https://api-web.nhle.com/v1/schedule/{date_str}"
    results = {}
    try:
        resp = requests.get(url, timeout=10).json()
        for day in resp.get("gameWeek", []):
            if day.get("date") != date_str:
                continue
            for g in day.get("games", []):
                if g.get("gameState") not in ("OFF", "FINAL", "CRIT"):
                    continue
                h  = g["homeTeam"]["abbrev"]
                a  = g["awayTeam"]["abbrev"]
                hs = int(g["homeTeam"].get("score", 0) or 0)
                as_ = int(g["awayTeam"].get("score", 0) or 0)
                if hs == 0 and as_ == 0:
                    continue
                winner = h if hs > as_ else a
                results[frozenset([h, a])] = {
                    "winner": winner, "home": h, "away": a,
                    "home_score": hs, "away_score": as_,
                    "total": hs + as_,
                }
    except Exception as e:
        print(f"  ⚠️  Scores {date_str}: {e}")
    return results


def grade_prediction(pred, actual):
    pw     = pred.get("predicted_winner", "")
    aw     = actual["winner"]
    total  = actual["total"]
    grades = {}

    # ML
    grades["ml"] = "W" if pw == aw else "L"

    # Spread (-1.5)
    margin = abs(actual["home_score"] - actual["away_score"])
    if pw == aw and margin >= 2:
        grades["spread"] = "W"
    elif margin == 1:
        grades["spread"] = "P"
    else:
        grades["spread"] = "L"

    # O/U
    ou_call = pred.get("details", {}).get("covers", {}).get("best_ou", "PASS")
    if "OVER" in ou_call:
        try:    thresh = float(ou_call.split()[-1])
        except: thresh = 5.5
        grades["ou"] = "W" if total > thresh else "L"
    elif "UNDER" in ou_call:
        try:    thresh = float(ou_call.split()[-1])
        except: thresh = 6.0
        grades["ou"] = "W" if total < thresh else "L"
    else:
        grades["ou"] = "P"

    # Edge
    tier = pred.get("tier", "NONE")
    if tier in ("EDGE", "BIG"):
        grades["edge"] = "W" if pw == aw else "L"
    else:
        grades["edge"] = "P"

    return grades


def grade_yesterday_picks():
    """
    Grades ALL slots that contain completed games — not just 'yesterday'.
    The pipeline timing means completed games can land in any slot.
    """
    print("\n📊 STEP 2: Grading completed picks across all slots")

    if not PRED_PATH.exists():
        print("  ⚠️  daily_predictions.json not found")
        return []

    preds      = load_json(PRED_PATH, {})
    grade_log  = load_json(GRADE_LOG, [])
    already    = {e["date"] + e["matchup"] for e in grade_log}
    new_grades = []
    today_edt  = get_est_now()

    slots = ["day_before_yesterday", "yesterday", "today", "tomorrow", "day_after_tomorrow"]

    for slot in slots:
        slot_games = preds.get(slot, [])
        if not slot_games:
            continue

        for pred in slot_games:
            h = pred.get("home", {}).get("name", "")
            a = pred.get("away", {}).get("name", "")
            if not h or not a:
                continue

            # Search last 7 days for this completed matchup
            actual = None
            game_date_str = None
            for offset in range(0, 7):
                check_date = (today_edt - timedelta(days=offset)).strftime("%Y-%m-%d")
                scores = fetch_actual_scores_for_date(check_date)
                if frozenset([h, a]) in scores:
                    actual = scores[frozenset([h, a])]
                    game_date_str = check_date
                    break

            if not actual:
                continue  # game hasn't happened yet

            entry_key = game_date_str + f"{a} @ {h}"
            if entry_key in already:
                continue

            grades = grade_prediction(pred, actual)
            pw     = pred.get("predicted_winner", "?")
            aw     = actual["winner"]

            entry = {
                "date":      game_date_str,
                "matchup":   f"{a} @ {h}",
                "predicted": pw,
                "actual":    aw,
                "score":     f"{actual['away_score']}-{actual['home_score']}",
                "tier":      pred.get("tier", "NONE"),
                "edge":      pred.get("edge", "N/A"),
                "grades":    grades,
            }

            grade_log.append(entry)
            new_grades.append(entry)
            already.add(entry_key)
            icon = "✅" if grades["ml"] == "W" else "❌"
            print(f"  {icon} [{slot}] {a} @ {h} ({game_date_str}): {pw} predicted, {aw} won ({actual['away_score']}-{actual['home_score']}) | ML:{grades['ml']} Spread:{grades['spread']} OU:{grades['ou']}")

    if new_grades:
        for p in all_save_paths("grade_log.json"):
            save_json(p, grade_log)
        print(f"  💾 grade_log.json — {len(grade_log)} total graded games")
    else:
        print("  ℹ️  No new completed games to grade")

    return grade_log




# ── 3. HISTORICAL STATS ───────────────────────────────────────────────────────
def build_historical_stats(grade_log):
    print("\n📈 STEP 3: Building historical_stats.json")

    if not grade_log:
        return {}

    today     = get_est_now().date()
    yesterday = today - timedelta(days=1)
    week_ago  = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    def parse_date(s):
        try:    return datetime.strptime(s, "%Y-%m-%d").date()
        except: return None

    def calc_period(entries):
        out = {}
        for pt in ("ml", "spread", "ou", "edge"):
            picks = [e["grades"].get(pt) for e in entries if e["grades"].get(pt) != "P"]
            w     = sum(1 for p in picks if p == "W")
            l     = sum(1 for p in picks if p == "L")
            total = w + l
            out[pt] = {
                "wins":     w,
                "losses":   l,
                "pushes":   sum(1 for e in entries if e["grades"].get(pt) == "P"),
                "win_rate": f"{w/total*100:.1f}%" if total else "N/A",
                "avg_edge": "N/A",
                "units":    str(round(w * 0.91 - l, 1)),
            }
        out["overall"] = {
            "wins":     out["ml"]["wins"],
            "losses":   out["ml"]["losses"],
            "win_rate": out["ml"]["win_rate"],
            "avg_edge": "N/A",
            "units":    out["ml"]["units"],
        }
        return out

    stats = {
        "all_time":   calc_period(grade_log),
        "this_month": calc_period([e for e in grade_log if parse_date(e["date"]) and parse_date(e["date"]) >= month_ago]),
        "this_week":  calc_period([e for e in grade_log if parse_date(e["date"]) and parse_date(e["date"]) >= week_ago]),
        "yesterday":  calc_period([e for e in grade_log if parse_date(e["date"]) == yesterday]),
    }

    for p in all_save_paths("historical_stats.json"):
        save_json(p, stats)

    ml = stats["all_time"]["ml"]
    print(f"  ✅ All-time: {ml['wins']}W-{ml['losses']}L ({ml['win_rate']}) | units: {ml['units']}")
    return stats


# ── 4. RESULTS INDEX (frontend HIT/MISS panels) ───────────────────────────────
def build_results_index(grade_log):
    print("\n🗂️  STEP 4: Building results_index.json")

    index = {}
    for entry in grade_log:
        raw = entry.get("matchup", "")
        if " @ " not in raw:
            continue
        away, home = [t.strip() for t in raw.split(" @ ")]
        key        = f"{away}|{home}"

        score_str   = entry.get("score", "0-0")
        parts       = score_str.split("-")
        away_actual = int(parts[0]) if len(parts) == 2 else 0
        home_actual = int(parts[1]) if len(parts) == 2 else 0

        index[key] = {
            "date":        entry["date"],
            "away":        away,
            "home":        home,
            "away_actual": away_actual,
            "home_actual": home_actual,
            "winner":      entry.get("actual", ""),
            "predicted":   entry.get("predicted", ""),
            "tier":        entry.get("tier", "NONE"),
            "grades":      entry.get("grades", {}),
        }

    for p in all_save_paths("results_index.json"):
        save_json(p, index)

    print(f"  ✅ results_index.json — {len(index)} completed games")
    return index


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== TRACK RESULTS PIPELINE ===")
    update_past_games_csv()
    grade_log = grade_yesterday_picks()
    if grade_log:
        build_historical_stats(grade_log)
        build_results_index(grade_log)
    print("\n✅ Done.")