# NHL Player Props — Task 2: Modeling and Backtest

## Model design

This stage trains one count model per requested outcome:

- Skater shots on goal
- Skater goals
- Skater assists
- Skater points
- Goalie saves
- Team shots on goal

Each estimator is a scikit-learn histogram gradient-boosting regressor with Poisson loss. Features are computed from games before the target game only:

- Player or team rolling averages over the previous 5, 10, and 20 games, plus season-to-date averages
- Player time on ice, games played to date, and rest days
- Skater position and home/away status
- Opponent's prior game-by-game production allowed by position
- Goalie opponent team shots-on-goal form
- Team shots-for/against form and the opponent's prior shots allowed

The model bundle stores each market estimator, its feature list, training row count, and a negative-binomial dispersion estimate. Given a projection and book line, `predict_count` can return over, under, and push probabilities. The probabilities are statistical estimates; they are not calibrated against a historical sportsbook line sample yet.

## Chronological validation

A full regular season is held out: **2025–26**. Training rows come from seasons before it. Rolling features for validation games use only earlier games, including earlier games within the held-out season. Results below compare the model against a simple prior-10-game average baseline.

| Market | Validation rows | Model MAE | Baseline MAE | Model Poisson deviance | Baseline Poisson deviance |
| --- | ---: | ---: | ---: | ---: | ---: |
| Skater shots on goal | 46,129 | 1.019 | 1.057 | 1.246 | 1.380 |
| Skater goals | 46,129 | 0.269 | 0.266 | 0.589 | 1.181 |
| Skater assists | 46,129 | 0.404 | 0.400 | 0.777 | 1.309 |
| Skater points | 46,129 | 0.527 | 0.527 | 0.917 | 1.294 |
| Goalie saves | 2,768 | 5.897 | 6.148 | 2.764 | 3.015 |
| Team shots on goal | 2,624 | 4.937 | 5.135 | 1.361 | 1.504 |

The model improves Poisson deviance over the rolling baseline for all six outcomes. MAE is slightly worse for goals and assists; points are nearly tied. This is one season-level holdout, so it is an initial signal, not proof of stable performance. It does not establish betting profit, edge, or probability calibration.

## Current limitations

- The odds feed is not part of model fitting. Available historical player-prop lines are shorter than the game-results history, so this backtest measures count-projection error only.
- Player availability, projected line combinations, confirmed goalie status, and expected time on ice are not available in the Task 2 training data. Integrating trusted lineup inputs and producing today's candidate predictions is a later step.
- No team-SOG sportsbook market is currently available through the agreed odds source; team SOG can be projected, but a book-line edge cannot be shown without an approved source.
- The current model uses public NHL game-log features and excludes MoneyPuck advanced data pending commercial-use permission.

## Train and reproduce

`scikit-learn`, `pandas`, `numpy`, and `joblib` are already listed in repository dependencies. After generating the Task 1 JSONL cache:

```powershell
python player_props/model.py --history-dir player_props_data --model-path player_props_models/model_bundle.joblib --report-path player_props_models/backtest.json --validation-season 2025
```

The large fitted model and report are local artifacts and are not committed to Git. The code re-runs the holdout and fits final estimators on all available history after the backtest.


## Candidate inference interface

The model bundle can score a future slate after a caller supplies schedule and player candidates. `build_candidate_features(history, candidates, market)` creates pregame features from cached history only; `predict_candidates(bundle, history, candidates, market)` returns each candidate with its projection and, when the candidate row contains a numeric `line`, over/under/push probabilities.

Candidate rows require `game_id`, `game_date`, `team_abbrev`, `opponent_abbrev`, and `home_away`. Skater rows also require NHL `player_id` and `position`; goalie rows require NHL `player_id`. A unique `candidate_id` is recommended. For example, markets are `player_shots_on_goal`, `player_goals`, `player_assists`, `player_points`, `goalie_saves`, and `team_shots_on_goal`.

The inference module does not fetch the schedule, lineups, odds, or confirmed-starter status. The caller must provide candidates using trustworthy NHL IDs and current schedule/lineup data. It does not treat an odds line as a model input; a line is used only to calculate probabilities from the projection. The generated model bundle uses plain mappings around scikit-learn estimators so the artifact can be loaded by an imported prediction service as well as by the training CLI.
