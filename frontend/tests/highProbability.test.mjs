import test from 'node:test';
import assert from 'node:assert/strict';
import { fairAmerican, formatAmerican, highestProbabilityLines } from '../lib/highProbability.mjs';

const game = (away, home, a, h, p1) => ({
  away: { name: away }, home: { name: home },
  goal_ladders: {
    away: { xg: 3, over: a }, home: { xg: 3, over: h }, first_period: { xg: 1.8, over: p1 },
  },
});

test('fair American odds from a percent', () => {
  assert.equal(fairAmerican(88), -733);
  assert.equal(fairAmerican(50), -100);
  assert.equal(fairAmerican(40), 150);
  assert.equal(fairAmerican(100), null);
  assert.equal(formatAmerican(150), '+150');
  assert.equal(formatAmerican(-733), '-733');
});

test('only lines at or above 85%, never an Over 0.5, highest first, capped', () => {
  const games = [
    game('CAR', 'VAN', { '0.5': 98.2, '1.5': 91.1, '2.5': 76.8, '3.5': 57.4 },
      { '0.5': 92.7, '1.5': 73.6, '2.5': 48.6, '3.5': 26.8 }, { '0.5': 84.9, '1.5': 56.4, '2.5': 29.4 }),
    game('SJS', 'TOR', { '0.5': 95, '1.5': 84.9, '2.5': 60, '3.5': 35 },
      { '0.5': 97, '1.5': 86.0, '2.5': 85.0, '3.5': 50 }, { '0.5': 90, '1.5': 60, '2.5': 30 }),
  ];
  const lines = highestProbabilityLines(games);
  assert.deepEqual(lines.map((l) => [l.label, l.pct]), [
    ['CAR goals Over 1.5', 91.1], ['TOR goals Over 1.5', 86.0], ['TOR goals Over 2.5', 85.0],
  ]);
  assert.equal(lines[0].fair, fairAmerican(91.1));
  assert.equal(lines[0].game, games[0]);
  assert.equal(highestProbabilityLines(games, { max: 1 }).length, 1);
});

test('a game with no ladders, or no games, gives an empty list', () => {
  assert.deepEqual(highestProbabilityLines([{ away: { name: 'A' }, home: { name: 'B' } }]), []);
  assert.deepEqual(highestProbabilityLines(undefined), []);
});
