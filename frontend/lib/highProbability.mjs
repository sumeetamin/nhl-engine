// The slate's most likely lines, so the 85-90% games do not have to be
// searched for card by card (the client, 2026-10-20).
//
// WHICH LINES. Each team's Over 1.5 / 2.5 / 3.5 and the first-period
// Over 1.5 / 2.5. Every "Over 0.5" is left out: a team scores at least once
// 92-98% of the time and the first period has a goal ~83% of the time in
// nearly every game, so listing them would fill the strip with every game
// on the slate and point at none.
//
// THE THRESHOLD, 85%. Walk-forward on 2024-25 to 2026-27 (goal_ladders.py),
// team lines said 80-90% hit 83% (said 84%), and said 90%+ hit 90% (said
// 91%), so a number here means what it says. It is still a probability, not
// an edge: no book price is read. The fair price is what that chance is
// worth; a line is only worth betting when the book pays better than it.
// Pulling book prices to show edges was weighed on 2026-10-20 and left out:
// these rates are barely better than the league average (log loss 0.496 vs
// 0.499 in 2025-26), so gaps against a book that knows the goalies would
// mostly be this model's own misses.

export const MIN_PCT = 85;
export const MAX_LINES = 5;
const TEAM_LINES = ['1.5', '2.5', '3.5'];
const P1_LINES = ['1.5', '2.5'];

// American odds for a probability in percent: 88 -> -733, 40 -> +150.
export function fairAmerican(pct) {
  const p = pct / 100;
  if (!(p > 0 && p < 1)) return null;
  const odds = p >= 0.5 ? -(100 * p) / (1 - p) : (100 * (1 - p)) / p;
  return Math.round(odds);
}

export const formatAmerican = (odds) => (odds == null ? '' : odds > 0 ? `+${odds}` : `${odds}`);

export function highestProbabilityLines(games, { minPct = MIN_PCT, max = MAX_LINES } = {}) {
  const lines = [];
  for (const game of games || []) {
    const ladders = game?.goal_ladders;
    if (!ladders) continue;
    const add = (label, ladder, keys, side) => {
      for (const key of keys) {
        const pct = ladder?.over?.[key];
        if (typeof pct === 'number' && pct >= minPct) {
          lines.push({ game, side, label: `${label} Over ${key}`, pct, fair: fairAmerican(pct) });
        }
      }
    };
    add(`${game.away?.name} goals`, ladders.away, TEAM_LINES, 'away');
    add(`${game.home?.name} goals`, ladders.home, TEAM_LINES, 'home');
    add('1st period total', ladders.first_period, P1_LINES, 'p1');
  }
  return lines.sort((a, b) => b.pct - a.pct).slice(0, max);
}

// Both teams to score 2+ / 3+ worth a highlight at the top (the client,
// 2026-10-30: "only 2+ and 3+, maybe 60%").
//
// THE THRESHOLDS. Walk-forward on 1,607 games from 2025-10-01, each priced
// from games before its date with goal_ladders.both_score: 60% would flag
// 83% of games for 2+ (5.5 a day) and none for 3+ (it never went past 44%).
// At 67.5%, 2+ flags about one game a day (16%), which said 69% and hit 70%;
// at 40%, 3+ flags about one a week (2%), which said 41% and hit 40.5%.
// Probabilities, not edges: no book price is read.
export const BOTH_MIN_PCT = { '2': 67.5, '3': 40 };

export function bothScoreHighlights(games, { minPct = BOTH_MIN_PCT, max = MAX_LINES } = {}) {
  const lines = [];
  for (const game of games || []) {
    const both = game?.goal_ladders?.both_score;
    if (!both) continue;
    for (const [k, min] of Object.entries(minPct)) {
      const pct = both[k];
      if (typeof pct === 'number' && pct >= min) {
        lines.push({ game, k, label: `Both teams ${k}+ goals`, pct, fair: fairAmerican(pct) });
      }
    }
  }
  // 3+ first (the rarer one), then highest chance.
  return lines.sort((a, b) => b.k.localeCompare(a.k) || b.pct - a.pct).slice(0, max);
}
