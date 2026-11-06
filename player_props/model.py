"""Train leak-aware NHL player-prop count models and chronological backtests.

The module consumes JSONL produced by ``history_ingest.py``. Each feature row is
computed from games strictly before that row's game date. Training here creates
statistical projections only; it does not fetch odds, lineups, or sportsbook data.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_poisson_deviance


SKATER_TARGETS = {
    "player_shots_on_goal": "shots_on_goal",
    "player_goals": "goals",
    "player_assists": "assists",
    "player_points": "points",
}
TARGETS = {
    **{name: ("skaters", field) for name, field in SKATER_TARGETS.items()},
    "goalie_saves": ("goalies", "saves"),
    "team_shots_on_goal": ("teams", "team_shots_on_goal"),
}
WINDOWS = (5, 10, 20)
MODEL_VERSION = "nhl-player-props-count-v1"


def _read_jsonl(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_json(path, lines=True)


def load_history(history_dir: str | Path) -> dict[str, pd.DataFrame]:
    root = Path(history_dir)
    result: dict[str, list[pd.DataFrame]] = {"skaters": [], "goalies": [], "teams": []}
    for table in result:
        for path in sorted(root.glob(f"{table}_*.jsonl")):
            frame = _read_jsonl(path)
            if not frame.empty:
                result[table].append(frame)
    frames = {table: pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
              for table, parts in result.items()}
    for table, frame in frames.items():
        if frame.empty:
            raise ValueError(f"No {table} history found in {root}")
        required = {"game_id", "game_date", "season", "team_abbrev", "opponent_abbrev", "home_away"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{table} history missing fields: {', '.join(sorted(missing))}")
        frame["game_date"] = pd.to_datetime(frame["game_date"], errors="raise")
        frame["season_start"] = frame["season"].astype(int) // 10000
        frames[table] = frame.sort_values(["game_date", "game_id"], kind="stable").reset_index(drop=True)
    return frames


def _rolling_features(
    frame: pd.DataFrame,
    *,
    groups: list[str],
    stats: list[str],
    prefix: str,
) -> pd.DataFrame:
    """Add strictly prior rolling means, expanding mean, count, and rest days."""
    frame = frame.sort_values([*groups, "game_date", "game_id"], kind="stable").copy()
    for stat in stats:
        grouped = frame.groupby(groups, sort=False, dropna=False)[stat]
        prior = grouped.shift(1)
        for window in WINDOWS:
            frame[f"{prefix}_{stat}_l{window}"] = prior.groupby(
                [frame[group] for group in groups], sort=False, dropna=False
            ).rolling(window, min_periods=1).mean().reset_index(level=list(range(len(groups))), drop=True)
        season_groups = [*groups, "season_start"]
        prior_season = frame.groupby(season_groups, sort=False, dropna=False)[stat].shift(1)
        frame[f"{prefix}_{stat}_season"] = prior_season.groupby(
            [frame[group] for group in season_groups], sort=False, dropna=False
        ).expanding(min_periods=1).mean().reset_index(level=list(range(len(season_groups))), drop=True)
    previous_date = frame.groupby(groups, sort=False, dropna=False)["game_date"].shift(1)
    rest_column = f"{prefix}_rest_days"
    games_column = f"{prefix}_games_before"
    frame[rest_column] = (frame["game_date"] - previous_date).dt.days.clip(0, 14)
    frame[games_column] = frame.groupby(groups, sort=False, dropna=False).cumcount()
    if "_candidate_row" in frame and frame["_candidate_row"].any():
        is_candidate = frame["_candidate_row"].fillna(False).astype(bool)
        history = frame.loc[~is_candidate]
        counts = history.groupby(groups, sort=False, dropna=False).size().to_dict()
        latest = history.groupby(groups, sort=False, dropna=False)["game_date"].max().to_dict()

        def group_key(row: pd.Series) -> Any:
            values = tuple(row[column] for column in groups)
            return values if len(values) > 1 else values[0]

        candidate_keys = frame.loc[is_candidate, groups].apply(group_key, axis=1)
        frame.loc[is_candidate, games_column] = candidate_keys.map(counts).fillna(0).to_numpy()
        latest_dates = candidate_keys.map(latest)
        frame.loc[is_candidate, rest_column] = [
            min(14, max(0, (row.game_date - previous).days)) if pd.notna(previous) else np.nan
            for row, previous in zip(frame.loc[is_candidate].itertuples(), latest_dates)
        ]
    return frame


def _home_flag(frame: pd.DataFrame) -> pd.Series:
    return frame["home_away"].astype(str).str.casefold().eq("home").astype(float)


def _skater_features(skaters: pd.DataFrame) -> dict[str, tuple[pd.DataFrame, list[str]]]:
    stats = [*SKATER_TARGETS.values(), "toi_seconds"]
    base = _rolling_features(skaters, groups=["player_id"], stats=stats, prefix="player")
    base["is_defense"] = base["position"].eq("D").astype(float)
    base["is_center"] = base["position"].eq("C").astype(float)
    base["is_wing"] = base["position"].isin(["L", "R", "W"]).astype(float)
    base["home"] = _home_flag(base)

    # Defense allowance is the aggregate stat produced by opposing skaters in
    # each game, grouped for the team defending and the position being faced.
    allowed = skaters.loc[~skaters.get("_candidate_row", pd.Series(False, index=skaters.index)).fillna(False).astype(bool)].copy()
    allowed["defense_team"] = allowed["opponent_abbrev"]
    allowed = allowed.groupby(
        ["game_id", "game_date", "season", "season_start", "defense_team", "position"],
        dropna=False, as_index=False,
    )[list(SKATER_TARGETS.values())].sum()
    allowed = _rolling_features(
        allowed, groups=["defense_team", "position"],
        stats=list(SKATER_TARGETS.values()), prefix="allowed",
    )
    allow_cols = [f"allowed_{stat}_l{window}" for stat in SKATER_TARGETS.values() for window in (5, 10)]
    base = base.merge(
        allowed[["game_id", "defense_team", "position", *allow_cols]],
        left_on=["game_id", "opponent_abbrev", "position"],
        right_on=["game_id", "defense_team", "position"],
        how="left", validate="many_to_one",
    ).drop(columns=["defense_team"])

    result = {}
    for market, target in SKATER_TARGETS.items():
        features = [
            "home", "is_defense", "is_center", "is_wing",
            f"player_{target}_l5", f"player_{target}_l10", f"player_{target}_l20",
            f"player_{target}_season", "player_toi_seconds_l5", "player_toi_seconds_l10",
            "player_rest_days", "player_games_before",
            f"allowed_{target}_l5", f"allowed_{target}_l10",
        ]
        result[market] = (base, features)
    return result


def _team_features(teams: pd.DataFrame) -> pd.DataFrame:
    return _rolling_features(
        teams, groups=["team_abbrev"], stats=["team_shots_on_goal", "shots_against"], prefix="team"
    ).assign(home=lambda x: _home_flag(x))


def _goalie_features(goalies: pd.DataFrame, teams: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    base = _rolling_features(
        goalies, groups=["player_id"], stats=["saves", "shots_against", "goals_against", "toi_seconds"],
        prefix="goalie",
    )
    base["home"] = _home_flag(base)
    team_features = _team_features(teams)
    opp = team_features[[
        "game_id", "team_abbrev", "team_team_shots_on_goal_l5", "team_team_shots_on_goal_l10",
    ]].rename(columns={
        "team_abbrev": "opponent_abbrev",
        "team_team_shots_on_goal_l5": "opp_team_sog_l5",
        "team_team_shots_on_goal_l10": "opp_team_sog_l10",
    })
    base = base.merge(opp, on=["game_id", "opponent_abbrev"], how="left", validate="many_to_one")
    return base, [
        "home", "goalie_saves_l5", "goalie_saves_l10", "goalie_saves_l20", "goalie_saves_season",
        "goalie_shots_against_l5", "goalie_shots_against_l10", "goalie_goals_against_l5",
        "goalie_toi_seconds_l5", "goalie_rest_days", "goalie_games_before", "opp_team_sog_l5",
        "opp_team_sog_l10",
    ]


def _team_target_features(teams: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    base = _team_features(teams)
    opponent = base[[
        "game_id", "team_abbrev", "team_shots_against_l5", "team_shots_against_l10",
    ]].rename(columns={
        "team_abbrev": "opponent_abbrev",
        "team_shots_against_l5": "opp_shots_against_l5",
        "team_shots_against_l10": "opp_shots_against_l10",
    })
    base = base.merge(opponent, on=["game_id", "opponent_abbrev"], how="left", validate="many_to_one")
    return base, [
        "home", "team_team_shots_on_goal_l5", "team_team_shots_on_goal_l10",
        "team_team_shots_on_goal_l20", "team_team_shots_on_goal_season",
        "team_shots_against_l5", "team_shots_against_l10", "team_rest_days", "team_games_before",
        "opp_shots_against_l5", "opp_shots_against_l10",
    ]


def build_training_frames(history: Mapping[str, pd.DataFrame]) -> dict[str, tuple[pd.DataFrame, list[str]]]:
    skaters = _skater_features(history["skaters"])
    goalies, goalie_features = _goalie_features(history["goalies"], history["teams"])
    teams, team_features = _team_target_features(history["teams"])
    result = dict(skaters)
    result["goalie_saves"] = (goalies, goalie_features)
    result["team_shots_on_goal"] = (teams, team_features)
    return result


def _candidate_rows(candidates: pd.DataFrame, market: str) -> pd.DataFrame:
    required = {"game_id", "game_date", "team_abbrev", "opponent_abbrev", "home_away"}
    table, _ = TARGETS[market]
    if table in {"skaters", "goalies"}:
        required.add("player_id")
    if table == "skaters":
        required.add("position")
    missing = required - set(candidates.columns)
    if missing:
        raise ValueError(f"Candidate rows for {market} need fields: {', '.join(sorted(missing))}")
    future = candidates.copy().reset_index(drop=True)
    if "candidate_id" not in future:
        future["candidate_id"] = [f"{market}-{i}" for i in range(len(future))]
    if future["candidate_id"].duplicated().any():
        raise ValueError("candidate_id values must be unique")
    future["game_date"] = pd.to_datetime(future["game_date"], errors="raise")
    if "season" not in future:
        starts = future["game_date"].map(lambda value: value.year if value.month >= 9 else value.year - 1)
        future["season"] = starts.map(lambda year: int(f"{year}{year + 1}"))
    future["season_start"] = future["season"].astype(int) // 10000
    future["_candidate_row"] = True
    for field in ("shots_on_goal", "goals", "assists", "points", "saves", "shots_against",
                  "goals_against", "team_shots_on_goal", "toi_seconds"):
        future[field] = np.nan
    return future


def _add_future_team_context(teams: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    rows: dict[tuple[Any, str], dict[str, Any]] = {}
    reverse_home = {"home": "away", "away": "home", "h": "away", "r": "home"}
    for row in candidates.to_dict(orient="records"):
        for team, opponent, side in (
            (row["team_abbrev"], row["opponent_abbrev"], row["home_away"]),
            (row["opponent_abbrev"], row["team_abbrev"], reverse_home.get(str(row["home_away"]).casefold(), "away")),
        ):
            key = (row["game_id"], str(team))
            if key not in rows:
                rows[key] = {
                    "game_id": row["game_id"], "game_date": row["game_date"],
                    "season": row["season"], "season_start": row["season_start"],
                    "team_abbrev": str(team), "opponent_abbrev": str(opponent),
                    "home_away": side, "team_shots_on_goal": np.nan,
                    "shots_against": np.nan, "_candidate_row": True,
                }
            if str(team) == str(row["team_abbrev"]):
                rows[key]["candidate_id"] = row["candidate_id"]
                rows[key]["is_requested_candidate"] = True
    context = pd.DataFrame(rows.values())
    if context.empty:
        raise ValueError("At least one future game candidate is required")
    return pd.concat([teams, context], ignore_index=True, sort=False)


def build_candidate_features(
    history: Mapping[str, pd.DataFrame],
    candidates: pd.DataFrame,
    market: str,
) -> tuple[pd.DataFrame, list[str]]:
    """Build pregame features for candidate player/team rows without using outcomes."""
    if market not in TARGETS:
        raise ValueError(f"Unsupported market: {market}")
    future = _candidate_rows(candidates, market)
    table, _ = TARGETS[market]
    if table == "skaters":
        combined = pd.concat([history["skaters"], future], ignore_index=True, sort=False)
        feature_sets = _skater_features(combined)
        frame, features = feature_sets[market]
    elif table == "goalies":
        combined = pd.concat([history["goalies"], future], ignore_index=True, sort=False)
        teams = _add_future_team_context(history["teams"], future)
        frame, features = _goalie_features(combined, teams)
    else:
        teams = _add_future_team_context(history["teams"], future)
        frame, features = _team_target_features(teams)
    selected = frame.loc[
        frame.get("is_requested_candidate", frame.get("_candidate_row", pd.Series(False, index=frame.index))).fillna(False)
    ].copy()
    # Skater/goalie candidates have no separate synthetic context rows.
    if "is_requested_candidate" not in selected:
        selected = selected.loc[selected["_candidate_row"].fillna(False)]
    selected = selected.drop_duplicates("candidate_id", keep="first")
    if selected["candidate_id"].nunique() != len(future):
        raise ValueError("Could not build features for every candidate; check candidate game/team/player IDs")
    return selected, features


def predict_candidates(
    model_bundle: Mapping[str, Any],
    history: Mapping[str, pd.DataFrame],
    candidates: pd.DataFrame,
    market: str,
    *,
    line_column: str = "line",
) -> list[dict[str, Any]]:
    """Return projection and optional line probabilities for schedule/lineup candidates."""
    model = model_bundle["models"][market]
    features_frame, _ = build_candidate_features(history, candidates, market)
    source = candidates.copy().reset_index(drop=True)
    if "candidate_id" not in source:
        source["candidate_id"] = [f"{market}-{i}" for i in range(len(source))]
    meta = source.set_index("candidate_id", drop=False).to_dict(orient="index")
    predictions = []
    for row in features_frame.to_dict(orient="records"):
        candidate = dict(meta[row["candidate_id"]])
        line = candidate.get(line_column)
        if line is None or pd.isna(line):
            line = None
        prediction = predict_count(model, row, line=None if line is None else float(line))
        predictions.append({**candidate, **prediction})
    return predictions


def _fit_estimator(frame: pd.DataFrame, features: list[str], target: str) -> HistGradientBoostingRegressor:
    model = HistGradientBoostingRegressor(
        loss="poisson", learning_rate=0.06, max_iter=140, max_leaf_nodes=15,
        min_samples_leaf=35, l2_regularization=3.0, early_stopping=False,
        random_state=2026,
    )
    model.fit(frame[features].replace([np.inf, -np.inf], np.nan), frame[target].astype(float))
    return model


def _estimate_dispersion(actual: np.ndarray, baseline: np.ndarray) -> float:
    baseline = np.maximum(np.asarray(baseline, dtype=float), 1e-6)
    actual = np.asarray(actual, dtype=float)
    # Method-of-moments NB dispersion from out-of-sample rolling-baseline errors.
    alpha = float(np.sum((actual - baseline) ** 2 - baseline) / np.sum(baseline ** 2))
    return min(2.0, max(0.0, alpha))


def _count_probability(mean: float, dispersion: float, line: float) -> dict[str, float]:
    mean = max(0.0, float(mean))
    line = float(line)
    max_k = max(40, int(math.ceil(mean + 12 * math.sqrt(mean + dispersion * mean * mean + 1))))
    if dispersion > 1e-6:
        size = 1.0 / dispersion
        p = size / (size + mean) if mean else 1.0
        log_p0 = size * math.log(max(p, 1e-15))
        probs = [math.exp(log_p0)]
        for k in range(1, max_k + 1):
            probs.append(probs[-1] * ((k - 1 + size) / k) * (1 - p))
    else:
        probs = [math.exp(-mean)]
        for k in range(1, max_k + 1):
            probs.append(probs[-1] * mean / k)
    total = sum(probs)
    if total <= 0:
        return {"over": 0.0, "under": 0.0, "push": 0.0}
    probs = [v / total for v in probs]
    over = sum(value for k, value in enumerate(probs) if k > line)
    under = sum(value for k, value in enumerate(probs) if k < line)
    push = sum(value for k, value in enumerate(probs) if k == line) if line.is_integer() else 0.0
    return {"over": over, "under": under, "push": push}


def predict_count(model: Mapping[str, Any], row: Mapping[str, Any], *, line: float | None = None) -> dict[str, Any]:
    features = model["features"]
    dispersion = float(model["dispersion"])
    values = pd.DataFrame([{key: row.get(key) for key in features}])
    projection = max(0.0, float(model["estimator"].predict(values.replace([np.inf, -np.inf], np.nan))[0]))
    result: dict[str, Any] = {
        "projection": projection,
        "dispersion": dispersion,
        "model_version": MODEL_VERSION,
    }
    if line is not None:
        result["probabilities"] = _count_probability(projection, dispersion, float(line))
    return result


def _baseline(frame: pd.DataFrame, target: str, features: list[str]) -> np.ndarray:
    name = next((c for c in features if c.endswith(f"{target}_l10")), None)
    if name is None:
        name = next((c for c in features if c.endswith(f"{target}_season")), None)
    if name is None:
        return np.full(len(frame), float(frame[target].mean()))
    return frame[name].fillna(float(frame[target].mean())).to_numpy(dtype=float)


def train_and_backtest(
    history: Mapping[str, pd.DataFrame],
    *,
    validation_season: int,
    model_path: str | Path,
) -> dict[str, Any]:
    """Hold out one complete season, then fit deployable models on all history."""
    prepared = build_training_frames(history)
    bundle: dict[str, dict[str, Any]] = {}
    metrics: dict[str, Any] = {}
    for market, (frame, features) in prepared.items():
        source, target = TARGETS[market]
        if target not in frame:
            raise ValueError(f"Target {target} missing for {market}")
        usable = frame.dropna(subset=[target, "season_start"]).copy()
        train = usable[usable["season_start"] < validation_season]
        valid = usable[usable["season_start"] == validation_season]
        if train.empty or valid.empty:
            raise ValueError(f"Need both prior training data and season {validation_season} for {market}")
        valid_model = _fit_estimator(train, features, target)
        valid_mean = np.maximum(1e-6, valid_model.predict(valid[features].replace([np.inf, -np.inf], np.nan)))
        actual = valid[target].to_numpy(dtype=float)
        baseline = _baseline(valid, target, features)
        baseline = np.maximum(1e-6, baseline)
        backtest = {
            "validation_season": validation_season,
            "train_rows": int(len(train)),
            "validation_rows": int(len(valid)),
            "model_mae": float(mean_absolute_error(actual, valid_mean)),
            "baseline_mae": float(mean_absolute_error(actual, baseline)),
            "model_rmse": float(math.sqrt(mean_squared_error(actual, valid_mean))),
            "baseline_rmse": float(math.sqrt(mean_squared_error(actual, baseline))),
            "model_poisson_deviance": float(mean_poisson_deviance(actual, valid_mean)),
            "baseline_poisson_deviance": float(mean_poisson_deviance(actual, baseline)),
            "dispersion": _estimate_dispersion(train[target].to_numpy(dtype=float), _baseline(train, target, features)),
        }
        all_model = _fit_estimator(usable, features, target)
        all_mean = np.maximum(1e-6, all_model.predict(usable[features].replace([np.inf, -np.inf], np.nan)))
        dispersion = _estimate_dispersion(usable[target].to_numpy(dtype=float), _baseline(usable, target, features))
        bundle[market] = {
            "estimator": all_model,
            "features": features,
            "dispersion": dispersion,
            "train_rows": int(len(usable)),
            "target_mean": float(usable[target].mean()),
        }
        metrics[market] = backtest

    output_path = Path(model_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"version": MODEL_VERSION, "models": bundle, "trained_at": pd.Timestamp.now(tz="UTC").isoformat()}, output_path)
    return {
        "model_version": MODEL_VERSION,
        "validation_season": validation_season,
        "models_path": str(output_path),
        "markets": metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-dir", type=Path, default=Path("player_props_data"))
    parser.add_argument("--model-path", type=Path, default=Path("player_props_models/model_bundle.joblib"))
    parser.add_argument("--report-path", type=Path, default=Path("player_props_models/backtest.json"))
    parser.add_argument("--validation-season", type=int, default=2025,
                        help="Start year of a complete held-out season, e.g. 2025 for 2025-26")
    args = parser.parse_args()
    try:
        history = load_history(args.history_dir)
        report = train_and_backtest(history, validation_season=args.validation_season, model_path=args.model_path)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

