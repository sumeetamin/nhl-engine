import test from 'node:test';
import assert from 'node:assert/strict';
import { easternDate, dateOptions, gamesForDate, strongestPlays } from '../lib/predictionDates.mjs';

test('Eastern dates across midnight, DST, and year boundaries', () => {
  for (const [utc, date] of [
    ['2026-09-30T03:59:59Z', '2026-09-29'], ['2026-09-30T04:00:00Z', '2026-09-30'],
    ['2026-01-01T04:59:59Z', '2025-12-31'], ['2026-01-01T05:00:00Z', '2026-01-01'],
    ['2026-03-08T07:00:00Z', '2026-03-08'], ['2026-11-01T06:00:00Z', '2026-11-01'],
  ]) assert.equal(easternDate(new Date(utc)), date);
});

test('calendar offsets remain correct across DST and leap days', () => {
  assert.deepEqual(dateOptions('2026-03-08').map(d => d.key),
    ['2026-03-06', '2026-03-07', '2026-03-08', '2026-03-09', '2026-03-10']);
  assert.equal(dateOptions('2028-03-01')[1].key, '2028-02-29');
});

test('delayed payload never moves Tuesday games to Wednesday', () => {
  const tuesday = [{ id: 'Tuesday game' }];
  const payload = { today: tuesday, games_by_date: { '2026-09-29': tuesday, '2026-09-30': [] } };
  assert.equal(gamesForDate(payload, '2026-09-29'), tuesday);
  assert.deepEqual(gamesForDate(payload, '2026-09-30'), []);
  assert.equal(gamesForDate(payload, '2026-10-01'), null);
  assert.equal(gamesForDate({ today: tuesday }, '2026-09-30'), null);
  assert.equal(gamesForDate(null, '2026-09-30'), null);
  assert.equal(gamesForDate({games_by_date: {'2026-09-30': null}}, '2026-09-30'), null);
});

test('top plays are the three strongest EDGE/BIG games, whatever the slate order', () => {
  const games = [
    { id: 'early', tier: 'EDGE', edge: '+3.1%' }, { id: 'none', tier: 'NONE', edge: '+30.0%' },
    { id: 'big', tier: 'BIG', edge: '+27.5%' }, { id: 'mid', tier: 'EDGE', edge: '+12.0%' },
    { id: 'late', tier: 'EDGE', edge: '+15.4%' },
  ];
  assert.deepEqual(strongestPlays(games).map(g => g.id), ['big', 'late', 'mid']);
  assert.deepEqual(games.map(g => g.id), ['early', 'none', 'big', 'mid', 'late']);
  assert.equal(strongestPlays(null), null);
});
