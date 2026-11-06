"""Checkpointed regular-season NHL player/team game-log ingestion.

The NHL Stats REST API is public but undocumented as a stable developer contract.
This importer validates the live per-game response shape and fails closed if it
receives aggregate rows or loses required columns. It writes local JSONL caches;
it does not call a sportsbook or require/print any API key.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import requests

API_BASE = "https://api.nhle.com/stats/rest/en"
TABLE_PATHS = {
    "skaters": "skater/summary",
    "goalies": "goalie/summary",
    "teams": "team/summary",
}
TABLE_REQUIRED = {
    "skaters": ("gameId", "gameDate", "playerId", "skaterFullName", "teamAbbrev",
                "opponentTeamAbbrev", "homeRoad", "shots", "goals", "assists",
                "points", "timeOnIcePerGame", "gamesPlayed"),
    "goalies": ("gameId", "gameDate", "playerId", "goalieFullName", "teamAbbrev",
                "opponentTeamAbbrev", "homeRoad", "saves", "shotsAgainst",
                "goalsAgainst", "gamesStarted", "timeOnIce", "gamesPlayed"),
    "teams": ("gameId", "gameDate", "teamId", "teamFullName", "opponentTeamAbbrev",
              "homeRoad", "shotsForPerGame", "shotsAgainstPerGame", "gamesPlayed"),
}


class IngestionError(RuntimeError):
    """Raised when the upstream API or returned schema cannot be trusted."""


def current_season_start(today: date | None = None) -> int:
    today = today or date.today()
    return today.year if today.month >= 9 else today.year - 1


def default_seasons(today: date | None = None, prior_seasons: int = 5) -> list[int]:
    """Return five completed season starts plus the current season start."""
    current = current_season_start(today)
    return list(range(current - prior_seasons, current + 1))


def season_id(start_year: int) -> int:
    return int(f"{start_year}{start_year + 1}")


def _request_json(session: requests.Session, url: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
    for attempt in range(6):
        try:
            response = session.get(url, params=params, timeout=(10, 45))
        except requests.RequestException as exc:
            if attempt == 5:
                raise IngestionError(f"Request failed after retries: {exc}") from exc
            time.sleep(min(2 ** attempt, 30))
            continue

        if response.status_code == 429 or response.status_code >= 500:
            if attempt == 5:
                response.raise_for_status()
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt, 30)
            time.sleep(delay)
            continue
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise IngestionError(f"Expected JSON from {url}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise IngestionError(f"Unexpected response shape from {url}: expected a data array")
        return payload
    raise IngestionError(f"Request failed after retries: {url}")


def fetch_game_rows(
    session: requests.Session,
    table: str,
    season: int,
    *,
    game_type: int = 2,
    page_size: int = 1000,
    pause_seconds: float = 0.12,
) -> list[dict[str, Any]]:
    if table not in TABLE_PATHS:
        raise ValueError(f"Unknown table: {table}")
    if page_size < 1 or page_size > 1000:
        raise ValueError("page_size must be between 1 and 1000")

    url = f"{API_BASE}/{TABLE_PATHS[table]}"
    cayenne = f"seasonId={season} and gameTypeId={game_type}"
    start = 0
    total: int | None = None
    rows: list[dict[str, Any]] = []

    while total is None or start < total:
        payload = _request_json(session, url, {
            "isAggregate": "false",
            "isGame": "true",
            "cayenneExp": cayenne,
            "limit": page_size,
            "start": start,
        })
        page = payload["data"]
        if total is None:
            try:
                total = int(payload["total"])
            except (KeyError, TypeError, ValueError) as exc:
                raise IngestionError(f"Missing or invalid total for {table} {season}") from exc
        if not page and start < total:
            raise IngestionError(f"Pagination stopped early for {table} {season}: {start}/{total}")
        rows.extend(page)
        start += len(page)
        if start < total:
            time.sleep(max(0.0, pause_seconds))
    if len(rows) != total:
        raise IngestionError(f"Truncated {table} {season} response: got {len(rows)}, expected {total}")
    return rows


def _required(row: Mapping[str, Any], table: str) -> None:
    missing = [key for key in TABLE_REQUIRED[table] if key not in row]
    if missing:
        raise IngestionError(f"{table} row is missing required fields: {', '.join(missing)}")


def _integer(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise IngestionError(f"Invalid integer for {field}: {value!r}") from exc


def _number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise IngestionError(f"Invalid number for {field}: {value!r}") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise IngestionError(f"Non-finite number for {field}")
    return number


def normalize_game_rows(table: str, rows: Iterable[Mapping[str, Any]], season: int) -> list[dict[str, Any]]:
    if table not in TABLE_REQUIRED:
        raise ValueError(f"Unknown table: {table}")
    ingested_at = datetime.now(timezone.utc).isoformat()
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for row in rows:
        _required(row, table)
        game_id = _integer(row["gameId"], "gameId")
        game_date = str(row["gameDate"])
        try:
            date.fromisoformat(game_date[:10])
        except ValueError as exc:
            raise IngestionError(f"Invalid gameDate for game {game_id}: {game_date!r}") from exc
        games_played = _integer(row["gamesPlayed"], "gamesPlayed")
        if games_played != 1:
            raise IngestionError(f"Expected one-game rows; got gamesPlayed={games_played} for {game_id}")
        home_away = {"H": "home", "R": "away"}.get(str(row["homeRoad"]).upper())
        if home_away is None:
            raise IngestionError(f"Invalid homeRoad value for game {game_id}: {row['homeRoad']!r}")

        record: dict[str, Any] = {
            "game_id": game_id,
            "game_date": game_date[:10],
            "season": season,
            "game_type": 2,
            "home_away": home_away,
            "team_abbrev": row.get("teamAbbrev"),
            "opponent_abbrev": row.get("opponentTeamAbbrev"),
            "source": "nhl_stats_rest",
            "source_fetched_at": ingested_at,
        }

        if table == "skaters":
            record.update({
                "player_id": _integer(row["playerId"], "playerId"),
                "player_name": row.get("skaterFullName"),
                "position": row.get("positionCode"),
                "shots_on_goal": _integer(row["shots"], "shots"),
                "goals": _integer(row["goals"], "goals"),
                "assists": _integer(row["assists"], "assists"),
                "points": _integer(row["points"], "points"),
                "toi_seconds": _number(row["timeOnIcePerGame"], "timeOnIcePerGame"),
            })
            key = (game_id, record["player_id"], record["team_abbrev"])
        elif table == "goalies":
            record.update({
                "player_id": _integer(row["playerId"], "playerId"),
                "player_name": row.get("goalieFullName"),
                "saves": _integer(row["saves"], "saves"),
                "shots_against": _integer(row["shotsAgainst"], "shotsAgainst"),
                "goals_against": _integer(row["goalsAgainst"], "goalsAgainst"),
                "started": bool(_integer(row["gamesStarted"], "gamesStarted")),
                "toi_seconds": _integer(row["timeOnIce"], "timeOnIce"),
            })
            key = (game_id, record["player_id"], record["team_abbrev"])
        else:
            record.update({
                "team_id": _integer(row["teamId"], "teamId"),
                "team_name": row.get("teamFullName"),
                # In an isGame=true response, the per-game value is the game total.
                "team_shots_on_goal": _integer(round(_number(row["shotsForPerGame"], "shotsForPerGame")),
                                                "shotsForPerGame"),
                "shots_against": _integer(round(_number(row["shotsAgainstPerGame"], "shotsAgainstPerGame")),
                                          "shotsAgainstPerGame"),
            })
            key = (game_id, record["team_id"])

        if not record.get("team_abbrev") or not record.get("opponent_abbrev"):
            raise IngestionError(f"Missing team identity for game {game_id} in {table}")
        if key in seen:
            raise IngestionError(f"Duplicate game/player/team row in {table}: {key}")
        seen.add(key)
        normalized.append(record)
    return normalized


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temp_path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            stream.write("\n")
            count += 1
    os.replace(temp_path, path)
    return count


def ingest_seasons(
    seasons: Iterable[int],
    output_dir: str | Path,
    *,
    game_type: int = 2,
    page_size: int = 1000,
    pause_seconds: float = 0.12,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    manifest: dict[str, Any] = {
        "source": "nhl_stats_rest",
        "game_type": game_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seasons": {},
    }
    with requests.Session() as session:
        session.headers.update({"User-Agent": "nhl-engine-player-props/1.0"})
        for start_year in seasons:
            season = season_id(start_year)
            season_counts: dict[str, int] = {}
            game_sets: dict[str, set[int]] = {}
            for table in TABLE_PATHS:
                raw_rows = fetch_game_rows(session, table, season, game_type=game_type,
                                           page_size=page_size, pause_seconds=pause_seconds)
                normalized = normalize_game_rows(table, raw_rows, season)
                if not normalized:
                    raise IngestionError(f"No {table} rows returned for season {season}")
                game_sets[table] = {row["game_id"] for row in normalized}
                output_path = output_dir / f"{table}_{season}.jsonl"
                season_counts[table] = _write_jsonl(output_path, normalized)

            manifest["seasons"][str(season)] = {
                "start_year": start_year,
                "table_rows": season_counts,
                "unique_games": {name: len(ids) for name, ids in game_sets.items()},
                "team_game_pairs": season_counts["teams"],
                "complete": True,
            }

    manifest_path = output_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_manifest = manifest_path.with_suffix(".json.tmp")
    temp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.replace(temp_manifest, manifest_path)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", nargs="+", type=int, help="Season start years, e.g. 2021 2022 2023")
    parser.add_argument("--prior-seasons", type=int, default=5,
                        help="Number of completed seasons before the current season (default: 5)")
    parser.add_argument("--out-dir", type=Path, default=Path("player_props_data"),
                        help="Directory for generated JSONL files (default: player_props_data)")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--pause-seconds", type=float, default=0.12)
    args = parser.parse_args()
    if args.prior_seasons < 1:
        parser.error("--prior-seasons must be at least 1")
    seasons = args.seasons or default_seasons(prior_seasons=args.prior_seasons)
    if any(year < 1917 or year > date.today().year for year in seasons):
        parser.error("Season start years must be valid NHL season years")
    try:
        manifest = ingest_seasons(seasons, args.out_dir, page_size=args.page_size,
                                  pause_seconds=args.pause_seconds)
    except (IngestionError, requests.RequestException, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for season, details in manifest["seasons"].items():
        counts = details["table_rows"]
        print(f"{season}: skaters={counts['skaters']}, goalies={counts['goalies']}, teams={counts['teams']}")
    print(f"Manifest: {args.out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
