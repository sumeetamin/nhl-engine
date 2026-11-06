# NHL Player Props — Task 1: Data Foundation

## Purpose

This document defines the data sources, normalized records, and quality rules for the NHL player-props feature. It is the first milestone deliverable: source and schema groundwork for the later model and website integration. It does not claim that the projections are already built or validated.

## What the feature will project

The planned markets are:

- Skater shots on goal
- Skater goals, assists, and points
- Goalie saves
- Team shots on goal

Each prediction record must keep the player/team/game identity, scheduled start, market/stat, model projection, probability, bookmaker and line (when available), source timestamps, and data quality flags. A projection should remain distinct from a sportsbook's line and price.

## Source plan

| Data | Preferred source | Use | Constraints to account for |
| --- | --- | --- | --- |
| Historical and current skater game results | NHL Web API player game logs and game-center boxscores | Goals, assists, points, shots, time on ice, games played, and actual outcomes for grading | The NHL Web API is public but has no published stable API contract; pin and validate response fields, use timeouts/retries, and retain raw-response timestamps. |
| Historical and current goalie results | NHL Web API game logs and game-center boxscores | Saves, shots faced, goals against, starts, and actual outcomes for grading | Validate goalie-specific fields and player identity before training or grading. |
| Team/game context | NHL schedule, roster, and game-center feeds | Opponent, home/away, game date, team shots, roster/team membership, game status | Use stable NHL IDs; names are display values only. |
| Advanced shot and on-ice context | MoneyPuck CSV downloads | Optional xG, shot-quality, and on-ice context features | Use published downloads only; confirm its current terms before automated reuse. Do not assume every field is available for every historical season. |
| Current player prop lines | Existing The Odds API connection | Book line and price; compare against model probability | The current market catalog lists over/under markets for shots on goal, points, assists, goals, and goalie total saves. Props are requested by event. A once-daily odds pull means displayed lines can be stale later in the day; preserve the snapshot time and mark age. Verify requested bookmaker coverage against the account before showing lines. |
| Projected/confirmed lineups and goalies | Highlightly lineups endpoint, if the customer has an active key/plan; otherwise NHL roster/schedule data plus a clearly marked status | Availability and goalie/lineup context | Do not label a goalie or lineup confirmed unless the provider explicitly marks it confirmed. A roster or projected lineup is not confirmation. Provider access and coverage are prerequisites. |

### Historical coverage

The requested five-plus seasons should apply to historical game results/features, subject to the fields that can be reliably sourced and normalized. It should not be represented as five years of historical player-prop odds: The Odds API documents historical additional markets from May 2023 on paid plans, so that history is shorter than five NHL seasons. A backtest can still use historical player results and available lines, but it must not present simulated prices as observed bookmaker prices.

### Team shots-on-goal odds coverage

The current Odds API market catalog lists player SOG and team goal totals, but does not list a team-shots-on-goal market. Team SOG can still be projected and graded from NHL game results, but this odds source should not be assumed to provide a comparable book line for it. Another approved provider or a no-book-line display would be needed for that column.

## Normalized data contract

A persisted game-result row should contain:

- game_id, game_date, season, game_type, team_id, team_abbrev, opponent_id, home_away
- player_id, player_name, position, starter_status (nullable; values such as unknown, projected, confirmed)
- stat_minutes, shots_on_goal, goals, assists, points
- For goalies: saves, shots_against, goals_against, started
- For team outcomes: team_shots_on_goal
- source, source_updated_at, ingested_at, raw_payload_hash

A market snapshot should contain:

- event_id, game_id, player_id (nullable for team markets), market_key, side, line, american_odds, bookmaker_key
- snapshot_at, provider_updated_at, is_stale, source

A prediction record should contain:

- Identity fields above, market_key, line, projection, probability_over, probability_under, model_version, generated_at
- Separate nullable bookmaker_key, book_line, and book_odds fields; do not blend odds into the model projection
- Data-quality flags explaining missing lineup, goalie, history, or odds data

## Data and modeling safeguards

1. Join on NHL/player/event IDs whenever available, not name prefixes or fuzzy name matching alone.
2. Keep regular season, preseason, and playoffs distinct. The customer requested recent seasons plus current data; the first model should default to regular-season games unless playoff support is explicitly configured and validated.
3. Generate rolling features only from games before the prediction timestamp. Never use the target game's result, post-start odds, or confirmed lineup information that arrived after the prediction cutoff.
4. Keep a point-in-time odds snapshot. Store when it was fetched and which books actually returned a line.
5. Missing data stays missing; it must not become a zero stat or a false “confirmed” status.
6. Grading uses the same market settlement definition and void/push rules as the target sportsbook.
7. Evaluate predictions with chronological walk-forward validation and calibration/error metrics. Do not claim a guaranteed or “highly accurate” model before those results exist.

## Refresh and freshness behavior

The requested refresh schedule is midnight, 7 a.m., and 3 p.m. Eastern. Model/features may refresh on that schedule. The odds constraint is one fetch per day, so odds used in later refreshes must be shown with the original snapshot timestamp and an age/staleness indicator. If the customer expects fresh prices at all three times, that conflicts with the one-fetch-per-day constraint and requires changing the odds-pull frequency or accepting stale prices.

## Task 1 acceptance checklist

- [x] Confirmed existing repo uses Python for its NHL pipeline and a Next.js frontend.
- [x] Identified The Odds API's event-level player-prop endpoint and added a pure normalizer for its supported NHL player markets; the existing key remains unchanged.
- [x] Defined an ID-based result, odds-snapshot, and prediction data contract.
- [x] Recorded the five-season historical-stat requirement separately from the shorter historical player-prop odds window.
- [x] Documented line/goalie confirmation, freshness, leakage, missing-data, and settlement safeguards.
- [ ] Ingest and normalize five-plus seasons of historical player/game results; confirm fields with representative provider responses.
- [ ] Confirm the account's allowed sportsbook/market coverage and the lineup provider key/plan before live integration.

## Sources

- [The Odds API — NHL odds and player prop markets](https://the-odds-api.com/sports/nhl-odds.html)
- [The Odds API — available betting markets (NHL player props)](https://the-odds-api.com/sports-odds-data/betting-markets.html)
- [MoneyPuck — data downloads](https://moneypuck.com/data.htm)
- [NHL Web API player game-log endpoint](https://api-web.nhle.com/v1/player/8478402/game-log/now) (public endpoint; the NHL does not publish a stable developer contract)
- [Highlightly — NHL lineups endpoint](https://highlightly.net/nhl-api/documentation/lineups/)
