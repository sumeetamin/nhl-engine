# Task 3: Player Props Feed and Frontend Integration

## What this adds

Task 3 connects the Task 2 count-projection models to the NHL page through a generated static feed. The Next.js frontend reads `frontend/public/player_props.json`; the scheduled job regenerates the feed and commits the JSON files for Vercel to serve.

The NHL page adds **Player Props** and **Cheat Sheets** tabs. Player Props includes search, game/market/side filters, sorting, player detail expansion, price comparisons, and a browser-local saved sheet. Cheat Sheets surfaces L5/L10 hit-rate rows at 80% or better. A compact top-plays area lists positive model-vs-book edges and shows a graded tracker summary.

## Markets and data

Model projections cover player shots on goal, points, assists, goals, goalie saves, and team shots on goal. The Odds API snapshot is limited to player shots, points, assists, goals, and goalie saves when those markets are available. Team shots remain model-only unless an approved line source is added.

Odds are restricted to FanDuel, DraftKings, Fanatics, Novig, and ProphetX. The current `ODDS_API_KEY` GitHub secret is read by the workflow; the implementation does not change the secret. Prices older than 30 hours based on the provider update time (or snapshot time when no provider time exists) are excluded. Odds are fetched once daily; other refreshes reuse the stored snapshot.

Game schedule and current rosters come from the NHL API. Goalie labels use NHL's game center goalie comparison / boxscore data only. A goalie is shown as projected or confirmed according to that source. Skater availability is marked as a current-roster candidate, not a confirmed lineup. No player prop is assigned a price or bookmaker when none is present in the approved snapshot.

History hit rates use only results before the scheduled game date. A push is excluded from the hit-rate denominator. Team-shot projections and historical team pace use NHL team game logs.

## Refresh schedule and deployment

The GitHub Actions workflow is scheduled at midnight, 7 AM, and 3 PM Eastern time. Only the midnight run fetches a fresh odds snapshot. The other two runs reuse that snapshot and refresh the generated projections, history-backed features, and tracker. A manual workflow run can optionally request an odds refresh.

The workflow requires the repository's existing `ODDS_API_KEY` secret for bookmaker prices. The frontend does not call that secret or The Odds API directly. Until this branch is merged, the schedule will not run from the default branch. A successful merge will trigger the site's normal Vercel deployment; the scheduled workflow then needs to complete before the public feed contains live player-prop data.

## Output contract

- `player_props.json`: feed version, update timestamps, source status, games, projections/lines, L5/L10/H2H/season hit splits, top plays, cheat sheets, and tracker results.
- `player_props_odds_snapshot.json`: last fetched, filtered odds payload and snapshot timestamp, used by the 7 AM and 3 PM refreshes.
- Each prop row includes the model projection, probability, available line and odds, permitted books, opponent position rank/allowed average, recent time on ice, team pace context, and goalie/availability labels when known.

The saved sheet is stored in the viewer's browser local storage; it is not shared across devices or users.

## Model and reporting limitations

The count model and probability distribution are not calibrated yet; the interface labels this limitation and edge values should be treated as exploratory until calibration and out-of-sample checks are reviewed. Historical player-prop odds coverage is shorter than the NHL result history, so historical hit rates use actual stat outcomes against the currently available line and must not be described as a historical betting record. No accuracy or profitability guarantee is made.

The feed degrades gracefully when the NHL goalie comparison or an approved player market is missing. Team SOG book lines, confirmed skater lineups, and cross-device saved sheets require additional data or persistence work if desired.
