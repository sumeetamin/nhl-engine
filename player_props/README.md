# NHL Player Props Data Foundation

Task 1 establishes a reproducible, validated game-history source for the player-props work. It does not yet train or serve prediction models.

## Data source and coverage

Historical game results are fetched from the NHL Stats REST API:

- `/skater/summary`: per-game skater shots, goals, assists, points, position, and time on ice.
- `/goalie/summary`: per-game saves, shots against, goals against, starts, and time on ice.
- `/team/summary`: per-game team shots for and against.
- `/team`: team ID to tricode lookup used for team result rows.

The importer requests regular-season game rows and keeps the season, game ID, date, team/opponent, and home/away identity. It uses explicit game-ID ordering, paginates with a bounded worker pool, partitions skater requests by team to stay below the API's 10,000-row result ceiling, removes only identical repeated source rows, and stops on conflicting duplicates, incomplete pages, missing fields, or incomplete home/away game pairs.

### Verified backfill (November 6, 2026)

Five completed seasons and the active 2026–27 season were fetched and normalized:

| Season | Skater rows | Goalie rows | Team rows | Exact duplicate rows removed (skaters) |
| --- | ---: | ---: | ---: | ---: |
| 2021–22 | 46,070 | 2,818 | 2,624 | 1,138 |
| 2022–23 | 46,129 | 2,785 | 2,624 | 1,079 |
| 2023–24 | 46,090 | 2,797 | 2,624 | 1,131 |
| 2024–25 | 46,100 | 2,764 | 2,624 | 1,124 |
| 2025–26 | 46,129 | 2,768 | 2,624 | 1,101 |
| 2026–27 (current, as of Nov 6) | 9,275 | 549 | 522 | 120 |

Each completed season has 1,312 unique games with two team rows per game; the active season snapshot has 261 unique games. The importer validates these relationships before writing the season files.

## Normalized fields

- **Skaters:** NHL player ID/name, position, team/opponent, home/away, shots on goal, goals, assists, points, and time on ice in seconds.
- **Goalies:** NHL player ID/name, team/opponent, home/away, saves, shots against, goals against, whether the goalie started, and time on ice in seconds.
- **Teams:** NHL team ID/name, team/opponent, home/away, team shots on goal, and shots against.
- All result rows include game ID/date, season, game type, source, and fetch timestamp. The source is the NHL Stats REST API.

Regular season is the current importer scope. Preseason and playoffs are excluded and must remain separate if added later. The NHL does not publish a stable developer contract for these endpoints, so the importer validates fields and completeness rather than silently accepting upstream schema changes.

## Odds and other source constraints

The existing The Odds API connection can provide NHL player lines for shots on goal, points, assists, goals, and goalie saves, depending on the subscribed plan and bookmaker coverage. The current market catalog does not list team shots on goal; that outcome can be projected and graded from NHL results, but a matching sportsbook line needs another approved source. The odds normalizer is a separate pure transformation and does not make network calls or change the existing API key. One odds fetch per day means line snapshots need a timestamp and age indicator.

MoneyPuck data is not included: its published download terms restrict use to noncommercial purposes unless permission is obtained. Highlightly lineup/goalie status also is not included in this historical import; access depends on the customer's key and plan. A goalie or lineup must not be labeled confirmed unless the provider explicitly confirms it.

Historical player results span six seasons. Historical player-prop odds do not: The Odds API documents additional-market history only from May 2023 on paid plans. Backtests must distinguish observed historical lines from simulated lines.

## Proposed modeling path (future task)

Task 1 delivers source data, not trained predictions. A sensible next step is per-market count modeling for shots, goals, assists, points, saves, and team shots, using player/team rolling form, time on ice, opponent and home/away context, with only information available before the game. Compare count-distribution baselines (Poisson/negative binomial) with a regularized tree model, use chronological walk-forward validation, and calibrate probabilities before comparing them with no-vig sportsbook probabilities. No accuracy or edge claim should be made until those evaluations are complete.

## Generate the local data cache

The generated JSONL files and `manifest.json` are bulk artifacts and are not committed to Git. Run the importer to reproduce them:

```powershell
python player_props/history_ingest.py --out-dir player_props_data
```

Use `--seasons 2021 2022 2023 2024 2025 2026` to pin the same season range. The manifest records row totals, game coverage, team partitions, and exact duplicate counts. `requests` is already part of the repository's Python dependencies.

## Related implementation

- `history_ingest.py`: validated regular-season history importer.
- `odds_normalizer.py`: normalize supported NHL player-prop event markets from an odds response.
- `../../docs/PLAYER_PROPS_DATA_FOUNDATION.md`: source contracts, freshness, and quality safeguards.
