# NHL Player Props — Task 1: Data Foundation

## Purpose

Task 1 delivers the reproducible historical game-result source, normalized records, coverage validation, and odds-market normalization needed by later model and website tasks. It does not claim that projections are trained, calibrated, or deployed.

## Verified historical coverage

On November 6, 2026, the importer completed five full regular seasons (2021–22 through 2025–26) and the active 2026–27 season snapshot. It normalized skater, goalie, and team game rows and validated complete home/away team pairs before writing each season.

| Season | Skaters | Goalies | Teams | Skater exact duplicates removed |
| --- | ---: | ---: | ---: | ---: |
| 2021–22 | 46,070 | 2,818 | 2,624 | 1,138 |
| 2022–23 | 46,129 | 2,785 | 2,624 | 1,079 |
| 2023–24 | 46,090 | 2,797 | 2,624 | 1,131 |
| 2024–25 | 46,100 | 2,764 | 2,624 | 1,124 |
| 2025–26 | 46,129 | 2,768 | 2,624 | 1,101 |
| 2026–27 current snapshot | 9,275 | 549 | 522 | 120 |

Each complete season has 1,312 unique games and two team rows per game. The current-season snapshot has 261 unique games. The full local backfill and manifest are reproducible with `python player_props/history_ingest.py --out-dir player_props_data`; generated bulk JSONL files are not committed to Git.

## Source plan and constraints

| Data | Source | Use | Constraint |
| --- | --- | --- | --- |
| Skater game results | NHL Stats REST `/skater/summary` | Shots, goals, assists, points, position, time on ice, actual outcomes | Public endpoint with no stable published developer contract; importer validates schema, pagination, and row completeness. |
| Goalie game results | NHL Stats REST `/goalie/summary` | Saves, shots against, goals against, starts, time on ice, actual outcomes | Goalie fields are validated before writing. |
| Team game results | NHL Stats REST `/team/summary` | Team shots on goal and shots against | Two team rows per game are required and validated. |
| Team IDs | NHL Stats REST `/team` catalog | Resolve team IDs and tricodes | Display names are not join keys. |
| Player prop odds | Existing The Odds API integration | Lines/odds for player shots, points, assists, goals, and goalie saves when covered by the account | Verify actual book/market coverage with the customer plan. One odds fetch per day requires a visible snapshot age. No team-SOG market is listed in its current market catalog. |
| Lineups and goalie status | Highlightly if customer key/plan is available; otherwise supported schedule/roster sources with limited status | Availability and starter context | Never label a projected player/goalie as confirmed without explicit provider status. |
| Advanced shot context | MoneyPuck only after commercial permission is granted | Optional xG/shot-quality context | Not included in this implementation because published download terms restrict use to noncommercial purposes unless permission is obtained. |

The Odds API documents historical additional player markets from May 2023 on paid plans; this is shorter than the six seasons of game results. Backtests must not present simulated or unavailable bookmaker prices as observed lines.

## Current normalized records

The importer writes local JSONL rows with game ID/date, season, game type, team/opponent, home/away, source, and fetch timestamp:

- **Skaters:** player ID/name, position, shots on goal, goals, assists, points, time on ice seconds.
- **Goalies:** player ID/name, saves, shots against, goals against, started flag, time on ice seconds.
- **Teams:** team ID/name, team shots on goal, shots against.

Odds snapshots and predictions are separate records and are not included in this historical result import. Later stages will add lineup status, event start times, model versions, bookmaker lines, and prediction probabilities.

## Quality and modeling safeguards

1. Join on NHL/player/game/team IDs where supplied; names are display values.
2. Keep regular season, preseason, and playoffs separate. Task 1 imports regular-season rows only.
3. Remove only exact duplicate source rows; fail on conflicting duplicate identities.
4. Sort explicitly, verify page totals, partition skater history below the API result ceiling, and require one home and one away team row for every game.
5. Missing data stays missing; it is not converted to zero or a confirmed status.
6. Build rolling features only from information available before the prediction cutoff.
7. Grade using the sportsbook's settlement and void/push rules.
8. Use chronological walk-forward validation and calibration. Do not promise guaranteed or “highly accurate” results before evaluation.

Task 2 now trains separate Poisson-loss histogram gradient-boosting count models for skater shots, goals, assists, points, goalie saves, and team shots on goal. The held-out 2025–26 evaluation and current limitations are documented in [PLAYER_PROPS_MODELING.md](PLAYER_PROPS_MODELING.md). The model is an initial baseline; probability calibration against historical book lines and betting-edge evaluation remain future work.

## Refresh and freshness

The requested refresh times are midnight, 7 a.m., and 3 p.m. Eastern. The requested one-odds-fetch-per-day limit means the later runs must display the original odds snapshot time and its age. Fresh prices at all three times would require more odds fetches or acceptance of stale prices.

## Task 1 acceptance checklist

- [x] Confirmed repo stack and kept the existing odds API key unchanged.
- [x] Added an NHL player-market odds normalizer.
- [x] Documented sources, normalized result fields, odds coverage limits, freshness, and modeling/validation safeguards.
- [x] Added a history importer with schema validation, explicit ordering, bounded parallel paging, skater partitioning, exact-repeat handling, and season completeness checks.
- [x] Ran and verified five completed regular seasons plus the current season; row totals are recorded above and in `player_props/README.md`.

Live bookmaker coverage and lineup-provider credentials are external prerequisites for the later live integration. They do not block this data-foundation deliverable; verify them when the later integration is authorized, without exposing or changing secrets.

## Sources

- [NHL Stats REST skater summary](https://api.nhle.com/stats/rest/en/skater/summary)
- [NHL Stats REST goalie summary](https://api.nhle.com/stats/rest/en/goalie/summary)
- [NHL Stats REST team summary](https://api.nhle.com/stats/rest/en/team/summary)
- [NHL Stats REST team catalog](https://api.nhle.com/stats/rest/en/team)
- [The Odds API — NHL odds and player prop markets](https://the-odds-api.com/sports/nhl-odds.html)
- [The Odds API — available betting markets](https://the-odds-api.com/sports-odds-data/betting-markets.html)
- [MoneyPuck — data download terms](https://moneypuck.com/data.htm)
- [Highlightly — NHL lineups endpoint](https://highlightly.net/nhl-api/documentation/lineups/)
