"""Build the scheduled NHL player-props JSON feed from the Task 1/2 artifacts.

Only NHL-hosted schedule/roster/goalie-comparison data and approved Odds API
bookmakers are used. If a source is missing, the output records that fact instead
of inventing a lineup, goalie confirmation, or sportsbook price.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import joblib
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from player_props.history_ingest import default_seasons, ingest_seasons
from player_props.model import TARGETS, build_candidate_features, load_history, predict_count
from player_props.odds_normalizer import normalize_event_odds

NHL_API = "https://api-web.nhle.com/v1"
ODDS_API = "https://api.the-odds-api.com/v4"
ODDS_SPORT = "icehockey_nhl"
ALLOWED_BOOKS = {"fanduel", "draftkings", "fanatics", "novig", "prophetx"}
ODDS_MARKETS = (
    "player_shots_on_goal,player_points,player_assists,player_goals,player_total_saves"
)
MARKET_LABELS = {
    "player_shots_on_goal": "Shots on Goal",
    "player_points": "Points",
    "player_assists": "Assists",
    "player_goals": "Goals",
    "goalie_saves": "Goalie Saves",
    "team_shots_on_goal": "Team Shots",
}
MARKET_SOURCE = {
    "player_shots_on_goal": ("skaters", "shots_on_goal"),
    "player_points": ("skaters", "points"),
    "player_assists": ("skaters", "assists"),
    "player_goals": ("skaters", "goals"),
    "goalie_saves": ("goalies", "saves"),
    "team_shots_on_goal": ("teams", "team_shots_on_goal"),
}
LOG = logging.getLogger("player_props")


class FeedError(RuntimeError):
    pass


def request_json(url: str, *, params: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = requests.get(url, params=params, timeout=timeout,
                                    headers={"User-Agent": "nhl-engine-player-props/1.0"})
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 3:
                    time.sleep(min(2 ** attempt, 8))
                    continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(min(2 ** attempt, 8))
    status = getattr(getattr(last_error, "response", None), "status_code", None)
    detail = f"HTTP {status}" if status else type(last_error).__name__ if last_error else "unknown error"
    raise FeedError(f"Request failed for {url}: {detail}")


EASTERN = ZoneInfo("America/New_York")


def eastern_today() -> date:
    return datetime.now(EASTERN).date()


def eastern_game_date(commence_time: str | None) -> str | None:
    if not commence_time:
        return None
    try:
        start = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
    except ValueError:
        return None
    if start.tzinfo is None:
        return None
    return start.astimezone(EASTERN).date().isoformat()


def game_dates(start: date) -> list[str]:
    return [(start + timedelta(days=offset)).isoformat() for offset in range(3)]


def team_full_name(team: dict[str, Any]) -> str:
    place = team.get("placeName") or {}
    name = team.get("commonName") or team.get("teamName") or {}
    if isinstance(place, dict):
        place = place.get("default", "")
    if isinstance(name, dict):
        name = name.get("default", "")
    return f"{place} {name}".strip()


def flatten_schedule(start: date) -> list[dict[str, Any]]:
    wanted = set(game_dates(start))
    payload = request_json(f"{NHL_API}/schedule/{start.isoformat()}")
    games: list[dict[str, Any]] = []
    for week in payload.get("gameWeek") or []:
        for game in week.get("games") or []:
            day = eastern_game_date(game.get("startTimeUTC")) or game.get("gameDate") or week.get("date")
            if day not in wanted:
                continue
            home, away = game.get("homeTeam") or {}, game.get("awayTeam") or {}
            game_id = game.get("id")
            if not game_id or not home.get("abbrev") or not away.get("abbrev"):
                continue
            games.append({
                "game_id": str(game_id),
                "game_date": day,
                "commence_time": game.get("startTimeUTC"),
                "home_team": str(home["abbrev"]),
                "away_team": str(away["abbrev"]),
                "home_name": team_full_name(home),
                "away_name": team_full_name(away),
                "game_label": f"{away.get('abbrev')} @ {home.get('abbrev')}",
            })
    return sorted(games, key=lambda row: (row["game_date"], row["commence_time"] or ""))


def normalize_name(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", raw.casefold())


def player_name(player: dict[str, Any]) -> str:
    first = player.get("firstName") or {}
    last = player.get("lastName") or {}
    if isinstance(first, dict):
        first = first.get("default", "")
    if isinstance(last, dict):
        last = last.get("default", "")
    return f"{first} {last}".strip()


def load_roster(team: str) -> dict[str, Any]:
    data = request_json(f"{NHL_API}/roster/{team}/current")
    result: dict[str, Any] = {"skaters": [], "goalies": []}
    for group, position in (("forwards", None), ("defensemen", "D")):
        for player in data.get(group) or []:
            pid = player.get("id")
            name = player_name(player)
            if pid and name:
                result["skaters"].append({
                    "player_id": int(pid), "player": name,
                    "position": str(player.get("positionCode") or position or "F"),
                })
    for player in data.get("goalies") or []:
        pid = player.get("id")
        name = player_name(player)
        if pid and name:
            result["goalies"].append({"player_id": int(pid), "player": name, "position": "G"})
    return result


def fetch_odds_snapshot(games: list[dict[str, Any]], api_key: str) -> dict[str, Any]:
    events = request_json(f"{ODDS_API}/sports/{ODDS_SPORT}/events", params={"apiKey": api_key})
    game_by_pair = {
        (frozenset((normalize_name(g["home_name"]), normalize_name(g["away_name"]))), g["game_date"]): g
        for g in games
    }
    candidates = []
    for event in events if isinstance(events, list) else []:
        pair = frozenset((normalize_name(event.get("home_team")), normalize_name(event.get("away_team"))))
        event_date = eastern_game_date(event.get("commence_time"))
        game = game_by_pair.get((pair, event_date))
        if game:
            candidates.append((event, game))
    snapshots = []
    now = datetime.now(timezone.utc).isoformat()
    for event, game in candidates:
        try:
            payload = request_json(
                f"{ODDS_API}/sports/{ODDS_SPORT}/events/{event['id']}/odds",
                params={
                    "apiKey": api_key, "bookmakers": ",".join(sorted(ALLOWED_BOOKS)),
                    "markets": ODDS_MARKETS, "oddsFormat": "american", "dateFormat": "iso",
                },
            )
        except FeedError as exc:
            if "HTTP 404" not in str(exc):
                raise
            LOG.warning("Odds event %s is no longer listed", event["id"])
            continue
        payload.setdefault("id", event["id"])
        payload["event_id"] = event["id"]
        payload["game_id"] = game["game_id"]
        payload["commence_time"] = game["commence_time"]
        payload["home_team"] = game["home_name"]
        payload["away_team"] = game["away_name"]
        payload["bookmakers"] = [
            book for book in (payload.get("bookmakers") or [])
            if str(book.get("key", "")).casefold() in ALLOWED_BOOKS
        ]
        snapshots.append(payload)
    LOG.info(
        "Odds API returned %d NHL events; matched %d to %d scheduled games",
        len(events) if isinstance(events, list) else 0, len(candidates), len(games),
    )
    if not candidates:
        LOG.warning(
            "No Odds API events matched the scheduled NHL slate; the feed will use the last recent usable snapshot if available."
        )
    return {"snapshot_at": now, "events": snapshots, "source": "the_odds_api",
            "bookmakers": sorted(ALLOWED_BOOKS)}


def has_player_prop_markets(snapshot: dict[str, Any]) -> bool:
    market_keys = set(ODDS_MARKETS.split(","))
    return any(
        market.get("key") in market_keys and bool(market.get("outcomes"))
        for event in snapshot.get("events") or []
        for bookmaker in event.get("bookmakers") or []
        if str(bookmaker.get("key", "")).casefold() in ALLOWED_BOOKS
        for market in bookmaker.get("markets") or []
    )


def keep_recent_usable_snapshot(
    fresh: dict[str, Any], snapshot_path: Path, *, max_age_hours: int = 30
) -> dict[str, Any]:
    if has_player_prop_markets(fresh):
        return fresh
    try:
        previous = json.loads(snapshot_path.read_text(encoding="utf-8"))
        timestamp = datetime.fromisoformat(
            str(previous.get("snapshot_at", "")).replace("Z", "+00:00")
        )
        age_hours = (datetime.now(timezone.utc) - timestamp).total_seconds() / 3600
    except (OSError, TypeError, ValueError):
        return fresh
    if has_player_prop_markets(previous) and 0 <= age_hours <= max_age_hours:
        LOG.warning(
            "Fresh player-prop odds were unavailable; retaining the last usable snapshot from %s (%.1f hours old)",
            previous.get("snapshot_at"), age_hours,
        )
        previous["fallback_reason"] = (
            "The latest odds fetch had no usable approved-book player markets; "
            "the last usable snapshot is retained and labeled with its timestamp."
        )
        return previous
    return fresh


def american_probability(price: float | None) -> float | None:
    if price is None or price == 0:
        return None
    return (100 / (price + 100)) if price > 0 else (-price / (-price + 100))


def safe_float(value: Any) -> float | None:
    try:
        number = float(value)
        return number if pd.notna(number) else None
    except (TypeError, ValueError):
        return None


def hit_split(frame: pd.DataFrame, stat: str, line: float | None, side: str | None) -> dict[str, Any]:
    if frame.empty or line is None or side not in {"over", "under"} or stat not in frame:
        return {"hits": 0, "total": 0, "hit_rate": None}
    values = pd.to_numeric(frame[stat], errors="coerce").dropna()
    pushes = values == line
    settled = values.loc[~pushes]
    wins = settled > line if side == "over" else settled < line
    total = int(len(settled))
    hits = int(wins.sum())
    return {"hits": hits, "total": total, "hit_rate": round(100 * hits / total, 1) if total else None}


def history_for(history: dict[str, pd.DataFrame], market: str, candidate: dict[str, Any],
                line: float | None, side: str | None) -> dict[str, Any]:
    table, stat = MARKET_SOURCE[market]
    frame = history[table]
    if frame.empty:
        empty = {"hits": 0, "total": 0, "hit_rate": None}
        return {"l5": empty, "l10": empty, "h2h": empty, "season": empty}
    prior = frame[frame["game_date"] < pd.Timestamp(candidate["game_date"])]
    if table == "teams":
        prior = prior[prior["team_abbrev"] == candidate["team_abbrev"]]
    else:
        prior = prior[prior["player_id"].astype(str) == str(candidate["player_id"])]
    prior = prior.sort_values(["game_date", "game_id"], ascending=False)
    head_to_head = prior[prior["opponent_abbrev"] == candidate["opponent_abbrev"]]
    season = prior[prior["season_start"] == int(candidate["season"]) // 10000]
    return {
        "l5": hit_split(prior.head(5), stat, line, side),
        "l10": hit_split(prior.head(10), stat, line, side),
        "h2h": hit_split(head_to_head, stat, line, side),
        "season": hit_split(season, stat, line, side),
    }


def prior_stat_frame(history: dict[str, pd.DataFrame], market: str, game_date: str) -> pd.DataFrame:
    table, _ = MARKET_SOURCE[market]
    frame = history[table]
    return frame[frame["game_date"] < pd.Timestamp(game_date)].copy() if not frame.empty else frame


def opponent_position_rank(history: dict[str, pd.DataFrame], market: str, game_date: str,
                           opponent: str, position: str | None) -> tuple[int | None, float | None]:
    if market not in {"player_shots_on_goal", "player_points", "player_assists", "player_goals"}:
        return None, None
    frame = prior_stat_frame(history, market, game_date)
    if frame.empty:
        return None, None
    frame = frame[frame["position"] == position]
    if frame.empty:
        return None, None
    stat = MARKET_SOURCE[market][1]
    allowed_by_game = frame.groupby(["game_id", "opponent_abbrev"], as_index=False)[stat].sum()
    allowed = allowed_by_game.groupby("opponent_abbrev")[stat].mean()
    rank = allowed.rank(method="min", ascending=True)
    value = allowed.get(opponent)
    return (int(rank[opponent]) if opponent in rank else None,
            round(float(value), 2) if value is not None else None)


def odds_lines(snapshot: dict[str, Any], games: list[dict[str, Any]],
               rosters: dict[str, dict[str, Any]]) -> dict[tuple[str, str, str, float], dict[str, Any]]:
    game_by_id = {game["game_id"]: game for game in games}
    # Legacy snapshots without an NHL ID still need to distinguish rematches.
    game_by_pair_date = {
        (frozenset((normalize_name(g["home_name"]), normalize_name(g["away_name"]))), g["game_date"]): g
        for g in games
    }
    player_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for team, roster in rosters.items():
        for player in roster["skaters"] + roster["goalies"]:
            player_lookup[(team, normalize_name(player["player"]))] = player
    result: dict[tuple[str, str, str, float], dict[str, Any]] = {}
    normalized_market = {
        "player_shots_on_goal": "player_shots_on_goal",
        "player_points": "player_points",
        "player_assists": "player_assists",
        "player_goals": "player_goals",
        "player_total_saves": "goalie_saves",
    }
    for event in snapshot.get("events") or []:
        if event.get("game_id") is not None:
            game = game_by_id.get(str(event["game_id"]))
        else:
            pair = frozenset((normalize_name(event.get("home_team")), normalize_name(event.get("away_team"))))
            game = game_by_pair_date.get((pair, eastern_game_date(event.get("commence_time"))))
        if not game:
            continue
        rows = normalize_event_odds(
            event, snapshot_at=snapshot["snapshot_at"], allowed_bookmaker_keys=ALLOWED_BOOKS,
            stale_after_hours=30,
        )
        for row in rows:
            if row["is_stale"]:
                continue
            market = normalized_market.get(row["market_key"])
            if not market:
                continue
            # Exact team-scoped matching prevents same-name or prefix collisions.
            normalized_player = normalize_name(row["player_name"])
            matches = [
                player_lookup[(team, normalized_player)]
                for team in (game["home_team"], game["away_team"])
                if (team, normalized_player) in player_lookup
            ]
            if len(matches) != 1:
                continue
            player = matches[0]
            key = (game["game_id"], str(player["player_id"]), market, float(row["line"]))
            group = result.setdefault(key, {"books": {}, "candidate": player, "line": float(row["line"])})
            book = group["books"].setdefault(row["bookmaker_key"], {})
            book[row["side"]] = row["american_odds"]
            group["commence_time"] = game["commence_time"]
    return result


def build_feed(history: dict[str, pd.DataFrame], bundle: dict[str, Any], games: list[dict[str, Any]],
               rosters: dict[str, dict[str, Any]], goalie_status: dict[tuple[str, str], dict[str, Any]],
               snapshot: dict[str, Any]) -> dict[str, Any]:
    stats_by_id: dict[str, dict[str, Any]] = {}
    game_map = {game["game_id"]: game for game in games}
    for game in games:
        season_start = int(game["game_date"][:4]) if int(game["game_date"][5:7]) >= 9 else int(game["game_date"][:4]) - 1
        for team, opponent, side in (
            (game["home_team"], game["away_team"], "home"),
            (game["away_team"], game["home_team"], "away"),
        ):
            base = {
                "game_id": game["game_id"], "game_date": game["game_date"],
                "season": int(f"{season_start}{season_start + 1}"),
                "team_abbrev": team, "opponent_abbrev": opponent, "home_away": side,
            }
            for player in rosters.get(team, {}).get("skaters", []):
                stats_by_id[f"{game['game_id']}:{player['player_id']}"] = {
                    **base, **player, "candidate_id": f"{game['game_id']}:{player['player_id']}",
                    "availability_status": "roster (lineup not confirmed)",
                }
    line_map = odds_lines(snapshot, games, rosters)
    props: list[dict[str, Any]] = []
    candidate_data: dict[str, tuple[str, dict[str, Any], dict[str, Any]]] = {}

    for market, (table, stat) in MARKET_SOURCE.items():
        if market == "team_shots_on_goal":
            candidates = []
            for game in games:
                start = int(game["game_date"][:4]) if int(game["game_date"][5:7]) >= 9 else int(game["game_date"][:4]) - 1
                for team, opponent, side in ((game["home_team"], game["away_team"], "home"),
                                             (game["away_team"], game["home_team"], "away")):
                    candidates.append({
                        "game_id": game["game_id"], "game_date": game["game_date"],
                        "season": int(f"{start}{start + 1}"), "team_abbrev": team,
                        "opponent_abbrev": opponent, "home_away": side,
                        "candidate_id": f"{game['game_id']}:{team}",
                    })
        elif market == "goalie_saves":
            candidates = []
            for game in games:
                for team, opponent, side in ((game["home_team"], game["away_team"], "home"),
                                             (game["away_team"], game["home_team"], "away")):
                    goalie = goalie_status.get((game["game_date"], team))
                    if not goalie:
                        continue
                    roster_goalies = rosters.get(team, {}).get("goalies", [])
                    matched = next((p for p in roster_goalies if normalize_name(p["player"]) == normalize_name(goalie.get("name"))), None)
                    if not matched:
                        continue
                    start = int(game["game_date"][:4]) if int(game["game_date"][5:7]) >= 9 else int(game["game_date"][:4]) - 1
                    candidates.append({
                        "game_id": game["game_id"], "game_date": game["game_date"],
                        "season": int(f"{start}{start + 1}"), "team_abbrev": team,
                        "opponent_abbrev": opponent, "home_away": side,
                        "candidate_id": f"{game['game_id']}:{matched['player_id']}",
                        "player_id": matched["player_id"], "player": matched["player"],
                        "position": "G", "goalie_status": "confirmed" if goalie.get("confirmed") else "projected",
                    })
        else:
            candidates = []
            for base in stats_by_id.values():
                candidates.append({
                    key: base[key] for key in (
                        "game_id", "game_date", "season", "team_abbrev", "opponent_abbrev",
                        "home_away", "candidate_id", "player_id", "player", "position",
                        "availability_status",
                    )
                })
        if not candidates:
            continue
        candidate_frame = pd.DataFrame(candidates)
        feature_frame, features = build_candidate_features(history, candidate_frame, market)
        model = bundle["models"][market]
        predictions = {str(row["candidate_id"]): row for row in feature_frame.to_dict(orient="records")}
        for candidate in candidates:
            cid = str(candidate["candidate_id"])
            feature_row = predictions.get(cid)
            if feature_row is None:
                continue
            prediction = predict_count(model, feature_row)
            game = game_map[candidate["game_id"]]
            player = candidate.get("player") or candidate.get("team_abbrev")
            base_prop = {
                "prop_id": f"{candidate['game_id']}:{cid}:{market}",
                "game_id": candidate["game_id"], "game_date": candidate["game_date"],
                "commence_time": game["commence_time"], "game_label": game["game_label"],
                "player_id": candidate.get("player_id"), "player": player,
                "team": candidate["team_abbrev"], "opponent": candidate["opponent_abbrev"],
                "position": candidate.get("position"), "market": market,
                "market_label": MARKET_LABELS[market], "projection": round(prediction["projection"], 2),
                "confidence": None, "line": None, "side": None, "price": None,
                "best_book": None, "edge_pct": None, "over_probability": None,
                "under_probability": None, "probability": None, "books": [],
                "goalie_status": candidate.get("goalie_status"),
                "goalie_name": candidate.get("player") if market == "goalie_saves" else None,
                "availability_status": candidate.get("availability_status"),
            }
            if market in {"player_shots_on_goal", "player_points", "player_assists", "player_goals"}:
                rank, allowed = opponent_position_rank(history, market, candidate["game_date"],
                                                       candidate["opponent_abbrev"], candidate.get("position"))
                base_prop["defense_rank"] = rank
                base_prop["defense_allowed"] = allowed
                history_frame = history["skaters"]
                prior = history_frame[
                    (history_frame["player_id"].astype(str) == str(candidate["player_id"])) &
                    (history_frame["game_date"] < pd.Timestamp(candidate["game_date"]))
                ].sort_values("game_date")
                toi = pd.to_numeric(prior.tail(10)["toi_seconds"], errors="coerce").mean()
                base_prop["toi_minutes"] = round(float(toi) / 60, 1) if pd.notna(toi) else None
            if market == "team_shots_on_goal":
                teams = history["teams"]
                prior_team = teams[
                    (teams["team_abbrev"] == candidate["team_abbrev"]) &
                    (teams["game_date"] < pd.Timestamp(candidate["game_date"]))
                ].sort_values("game_date")
                prior_opp = teams[
                    (teams["team_abbrev"] == candidate["opponent_abbrev"]) &
                    (teams["game_date"] < pd.Timestamp(candidate["game_date"]))
                ].sort_values("game_date")
                base_prop["team_pace"] = round(float(prior_team.tail(10)["team_shots_on_goal"].mean()), 1) if not prior_team.empty else None
                base_prop["opponent_pace"] = round(float(prior_opp.tail(10)["team_shots_on_goal"].mean()), 1) if not prior_opp.empty else None

            groups = [value for key, value in line_map.items()
                      if key[0] == candidate["game_id"] and key[1] == str(candidate.get("player_id")) and key[2] == market] if candidate.get("player_id") is not None else []
            if not groups:
                stats = history[table]
                hist_candidate = {**candidate, "player_id": candidate.get("player_id", 0)}
                base_prop["history"] = history_for(history, market, hist_candidate, None, None)
                props.append(base_prop)
                continue
            for group in groups:
                books = group["books"]
                all_books = [
                    {"book": book, "over": prices.get("over"), "under": prices.get("under")}
                    for book, prices in books.items()
                ]
                over_p = predict_count(model, feature_row, line=group_line(groups, group))["probabilities"]
                line_value = group_line(groups, group)
                settled_probability = over_p["over"] + over_p["under"]
                over_result = {
                    "over": round(100 * over_p["over"] / settled_probability, 1) if settled_probability else 0.0,
                    "under": round(100 * over_p["under"] / settled_probability, 1) if settled_probability else 0.0,
                    "push": round(100 * over_p["push"], 1),
                }
                for side in ("over", "under"):
                    choices = []
                    for book, prices in books.items():
                        price = prices.get(side)
                        opposite = prices.get("under" if side == "over" else "over")
                        p, q = american_probability(price), american_probability(opposite)
                        no_vig = p / (p + q) if p is not None and q is not None and p + q else None
                        model_prob = over_p["over"] if side == "over" else over_p["under"]
                        if price is not None:
                            choices.append({
                                "book": book, "price": price, "edge": (model_prob - no_vig) * 100 if no_vig is not None else None,
                            })
                    best = max(choices, key=lambda item: (item["edge"] if item["edge"] is not None else -999,
                                                          item["price"]), default=None)
                    prop = {
                        **base_prop, "prop_id": f"{base_prop['prop_id']}:{line_value}:{side}",
                        "line": line_value, "side": side,
                        "price": best["price"] if best else None,
                        "best_book": best["book"] if best else None,
                        "edge_pct": round(best["edge"], 1) if best and best["edge"] is not None else None,
                        "over_probability": over_result["over"], "under_probability": over_result["under"],
                        "push_probability": over_result["push"], "probability": over_result[side],
                        "confidence": over_result[side], "books": all_books,
                    }
                    prop["history"] = history_for(history, market, candidate, line_value, side)
                    props.append(prop)
    return build_output(history, props, games, snapshot)


def group_line(groups: list[dict[str, Any]], group: dict[str, Any]) -> float:
    return float(group["line"])


def grade_tracker(history: dict[str, pd.DataFrame], old_rows: list[dict[str, Any]],
                  current_picks: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    tracker = {str(row.get("prop_id")): dict(row) for row in old_rows if row.get("prop_id")}
    for row in tracker.values():
        if row.get("result") != "pending":
            continue
        market = row.get("market")
        if market not in MARKET_SOURCE or row.get("line") is None or row.get("side") not in {"over", "under"}:
            row["result"] = "void"
            continue
        table, stat = MARKET_SOURCE[market]
        frame = history[table]
        actual_rows = frame[frame["game_id"].astype(str) == str(row.get("game_id"))]
        if table == "teams":
            actual_rows = actual_rows[actual_rows["team_abbrev"] == row.get("team")]
        else:
            actual_rows = actual_rows[actual_rows["player_id"].astype(str) == str(row.get("player_id"))]
        if not actual_rows.empty:
            value = safe_float(actual_rows.iloc[0].get(stat))
            line = float(row["line"])
            if value is None:
                row["result"] = "void"
            elif value == line:
                row["result"] = "push"
            elif (value > line) == (row["side"] == "over"):
                row["result"] = "hit"
            else:
                row["result"] = "miss"
        else:
            game_date = str(row.get("game_date") or "")[:10]
            if game_date and date.fromisoformat(game_date) < today - timedelta(days=3):
                row["result"] = "void"
    for pick in current_picks:
        key = str(pick["prop_id"])
        tracker.setdefault(key, {
            "prop_id": key, "game_id": pick["game_id"], "game_date": pick["game_date"],
            "player_id": pick.get("player_id"), "team": pick.get("team"),
            "market": pick["market"], "line": pick.get("line"), "side": pick.get("side"),
            "result": "pending",
        })
    return list(tracker.values())


def build_output(history: dict[str, pd.DataFrame], props: list[dict[str, Any]],
                 games: list[dict[str, Any]], snapshot: dict[str, Any],
                 tracker: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    cheat_sheets = []
    top_plays = []
    for row in props:
        eligible = []
        for window in ("l5", "l10"):
            split = (row.get("history") or {}).get(window) or {}
            if split.get("hit_rate") is not None and split["hit_rate"] >= 80:
                eligible.append((window, split["hit_rate"]))
        for window, rate in eligible:
            cheat_sheets.append({**row, "window": window, "hit_rate": rate})
        if row.get("edge_pct") is not None and row["edge_pct"] > 0:
            top_plays.append(row)
    top_plays.sort(key=lambda row: row["edge_pct"], reverse=True)
    return {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "odds_snapshot_at": snapshot.get("snapshot_at"),
        "source_status": (
            "Props use official NHL game logs and NHL schedule/roster data. " +
            ("Prices are a once-daily snapshot from approved books." if any(row.get("best_book") for row in props) else
             "No fresh approved-book player-prop lines were available in the latest snapshot.")
        ),
        "games": games,
        "props": props,
        "cheat_sheets": cheat_sheets,
        "top_plays": top_plays[:20],
        "tracker": tracker or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-dir", type=Path, default=Path("player_props_data"))
    parser.add_argument("--model-path", type=Path, default=Path("player_props_models/model_bundle.joblib"))
    parser.add_argument("--odds-path", type=Path, default=Path("frontend/public/player_props_odds_snapshot.json"))
    parser.add_argument("--output", type=Path, default=Path("frontend/public/player_props.json"))
    parser.add_argument("--fetch-odds", action="store_true",
                        help="Fetch a new odds snapshot; scheduled workflow enables this only once per day")
    args = parser.parse_args()
    try:
        seasons = default_seasons()
        current = seasons[-1]
        missing = [year for year in seasons[:-1]
                   if not all((args.history_dir / f"{table}_{year}{year + 1}.jsonl").exists()
                              for table in ("skaters", "goalies", "teams"))]
        refresh = sorted(set(missing + [current]))
        if refresh:
            LOG.info("Refreshing history seasons: %s", refresh)
            ingest_seasons(refresh, args.history_dir)

        history = load_history(args.history_dir)
        validation_season = current - 1
        args.model_path.parent.mkdir(parents=True, exist_ok=True)
        report = __import__("player_props.model", fromlist=["train_and_backtest"]).train_and_backtest(
            history, validation_season=validation_season, model_path=args.model_path
        )
        bundle = joblib.load(args.model_path)
        start = eastern_today()
        games = flatten_schedule(start)
        team_codes = sorted({g[key] for g in games for key in ("home_team", "away_team")})
        rosters = {team: load_roster(team) for team in team_codes}
        goalie_status: dict[tuple[str, str], dict[str, Any]] = {}
        from goalie_scraper import _from_nhl_api
        for day in sorted({game["game_date"] for game in games}):
            teams_for_day = sorted({team for game in games if game["game_date"] == day
                                    for team in (game["home_team"], game["away_team"])})
            try:
                for team, status in _from_nhl_api(day, teams_for_day).items():
                    goalie_status[(day, team)] = status
            except Exception as exc:
                LOG.warning("Official goalie status unavailable for %s: %s", day, exc)

        snapshot = {"snapshot_at": None, "events": [], "source": "the_odds_api"}
        if args.odds_path.exists():
            try:
                snapshot = json.loads(args.odds_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                LOG.warning("Saved odds snapshot could not be read")
        already_fetched = (
            eastern_game_date(snapshot.get("snapshot_at")) == start.isoformat()
            and has_player_prop_markets(snapshot)
        )
        if args.fetch_odds and not already_fetched:
            api_key = os.environ.get("ODDS_API_KEY")
            if api_key:
                try:
                    snapshot = fetch_odds_snapshot(games, api_key)
                except FeedError as exc:
                    LOG.warning("Odds snapshot unavailable: %s", str(exc).replace(api_key, "[redacted]"))
                    snapshot = {
                        "snapshot_at": None, "events": [], "source": "the_odds_api",
                        "error": "The daily odds request did not return usable player markets.",
                    }
            else:
                snapshot = {
                    "snapshot_at": None, "events": [], "source": "the_odds_api",
                    "error": "ODDS_API_KEY is not configured",
                }
            snapshot = keep_recent_usable_snapshot(snapshot, args.odds_path)
            args.odds_path.parent.mkdir(parents=True, exist_ok=True)
            args.odds_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        elif args.fetch_odds:
            LOG.info("Reusing today's completed player-prop odds snapshot")
        previous = {}
        if args.output.exists():
            try:
                previous = json.loads(args.output.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                previous = {}
        feed = build_feed(history, bundle, games, rosters, goalie_status, snapshot)
        feed["tracker"] = grade_tracker(
            history, previous.get("tracker") or [], feed.get("top_plays") or [], eastern_today()
        )
        if snapshot.get("error"):
            feed["source_status"] += " " + snapshot["error"] + "."
        if snapshot.get("fallback_reason"):
            feed["source_status"] = (
                "Props use official NHL game logs and NHL schedule/roster data. "
                + str(snapshot["fallback_reason"])
            )
        feed["training_report"] = {
            "validation_season": report["validation_season"],
            "market_count": len(report["markets"]),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temp = args.output.with_suffix(args.output.suffix + ".tmp")
        temp.write_text(json.dumps(feed, indent=2), encoding="utf-8")
        os.replace(temp, args.output)
    except (FeedError, OSError, ValueError, KeyError, requests.RequestException) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {len(feed['props'])} player-prop rows for {len(feed['games'])} games")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(main())
