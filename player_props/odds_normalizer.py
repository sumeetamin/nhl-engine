"""Normalize The Odds API event odds into the player-props data contract.

This is a pure transformation layer. It deliberately does not fetch odds or read
secrets; the caller controls the once-daily snapshot schedule and API budget.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

PLAYER_MARKETS = {
    "player_shots_on_goal": "shots_on_goal",
    "player_points": "points",
    "player_assists": "assists",
    "player_goals": "goals",
    "player_total_saves": "saves",
}


def _as_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError("A valid ISO timestamp is required")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def normalize_event_odds(
    event: Mapping[str, Any],
    *,
    snapshot_at: str | datetime,
    allowed_bookmaker_keys: Iterable[str],
    now: str | datetime | None = None,
    stale_after_hours: float = 24,
) -> list[dict[str, Any]]:
    """Flatten a single event-odds response into approved, timestamped rows.

    Player IDs are intentionally left null because The Odds API identifies the
    player by display name; callers must resolve names against NHL IDs separately.
    Only the explicitly allowed bookmaker keys are emitted.
    """
    event_id = event.get("id")
    if not event_id:
        raise ValueError("Event payload is missing its id")
    snapshot_time = _as_utc(snapshot_at)
    current_time = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    max_age = max(0.0, float(stale_after_hours))
    age_hours = max(0.0, (current_time - snapshot_time).total_seconds() / 3600)
    is_stale = age_hours > max_age
    allowed = {str(key).strip().casefold() for key in allowed_bookmaker_keys if str(key).strip()}
    if not allowed:
        raise ValueError("Pass the approved bookmaker keys returned by the provider")

    rows: list[dict[str, Any]] = []
    for bookmaker in event.get("bookmakers") or []:
        bookmaker_key = str(bookmaker.get("key") or "").strip()
        if bookmaker_key.casefold() not in allowed:
            continue
        for market in bookmaker.get("markets") or []:
            market_key = str(market.get("key") or "")
            stat = PLAYER_MARKETS.get(market_key)
            if not stat:
                continue
            provider_updated_at = market.get("last_update") or bookmaker.get("last_update")
            for outcome in market.get("outcomes") or []:
                side = str(outcome.get("name") or "").strip().casefold()
                if side not in {"over", "under"}:
                    continue
                player_name = str(outcome.get("description") or "").strip()
                line = _number(outcome.get("point"))
                odds = _number(outcome.get("price"))
                if not player_name or line is None or odds is None:
                    continue
                rows.append({
                    "event_id": str(event_id),
                    "game_id": None,
                    "commence_time": event.get("commence_time"),
                    "home_team": event.get("home_team"),
                    "away_team": event.get("away_team"),
                    "player_id": None,
                    "player_name": player_name,
                    "market_key": market_key,
                    "stat": stat,
                    "side": side,
                    "line": line,
                    "american_odds": int(odds) if odds.is_integer() else odds,
                    "bookmaker_key": bookmaker_key,
                    "bookmaker_title": bookmaker.get("title"),
                    "snapshot_at": snapshot_time.isoformat(),
                    "provider_updated_at": provider_updated_at,
                    "age_hours": round(age_hours, 3),
                    "is_stale": is_stale,
                    "source": "the_odds_api",
                })
    return rows
