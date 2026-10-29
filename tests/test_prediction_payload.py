"""Test payload dates without importing the model or making network requests."""
import ast
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


class PredictionPayloadTests(unittest.TestCase):
    def test_delayed_run_keeps_dates_and_top_plays_aligned(self):
        tree = ast.parse(Path('run_pipeline.py').read_text(encoding='utf-8'))
        wanted = {'build_daily_json', 'strongest_plays', 'edge_value'}
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
        saved = {}
        calls = []

        def games(date, *args):
            calls.append(date)
            return [{'date': date, 'tier': 'EDGE'}]

        ns = dict(datetime=datetime, timedelta=timedelta, timezone=timezone,
                  get_est_now=lambda: datetime(2026, 9, 30, 23, 59),
                  get_schedule_window=lambda dates: {date: [] for date in dates},
                  fetch_nhl_odds=lambda: [], fetch_standings=lambda: {},
                  load_pregame_odds=lambda: {}, remember_pregame_odds=lambda store, odds, now: store,
                  PREGAME_ODDS_FILE='pregame_odds.json',
                  annotate_slate=lambda games, rows, as_of, standings: [], load_history=lambda path: [],
                  HISTORY_CSV_PATH='past_games.csv',
                  fetch_goalie_table=lambda day: None,
                  GIFT_AVAILABLE=False, get_all_games_for_date=games,
                  save_json=lambda name, payload: saved.update(payload), print=lambda *a: None)
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'run_pipeline.py', 'exec'), ns)
        ns['build_daily_json']()
        self.assertEqual(calls, ['2026-09-28', '2026-09-29', '2026-09-30', '2026-10-01', '2026-10-02'])
        self.assertEqual(saved['timezone'], 'America/New_York')
        self.assertEqual(saved['today'], saved['games_by_date']['2026-09-30'])
        self.assertEqual(saved['games_by_date']['2026-10-01'][0]['date'], '2026-10-01')
        self.assertEqual(saved['top_plays_date'], '2026-09-30')
        self.assertEqual(saved['top_plays'][0]['date'], '2026-09-30')
        self.assertIsNotNone(datetime.fromisoformat(saved['generated_at']).tzinfo)


    def test_slate_is_in_start_time_order_and_top_plays_by_edge(self):
        tree = ast.parse(Path('run_pipeline.py').read_text(encoding='utf-8'))
        wanted = {'get_all_games_for_date', 'strongest_plays', 'edge_value'}
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
        edges = {'NYR': '+3.0%', 'BOS': '+20.0%', 'SEA': '+12.0%', 'TOR': '+15.0%'}

        def engine(home, away, time, **kwargs):
            return {'home': {'name': home}, 'time': time, 'edge': edges[home], 'tier': 'EDGE'}

        ns = dict(scrape_goalies=lambda **kwargs: {}, run_ml_engine=engine,
                  convert_to_est=lambda utc: utc, logging=None)
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'run_pipeline.py', 'exec'), ns)
        schedule = [
            {'homeTeam': {'abbrev': 'BOS'}, 'awayTeam': {'abbrev': 'MTL'}, 'startTimeUTC': '2026-10-29T23:30:00Z'},
            {'homeTeam': {'abbrev': 'SEA'}, 'awayTeam': {'abbrev': 'VAN'}, 'startTimeUTC': '2026-10-30T02:00:00Z'},
            {'homeTeam': {'abbrev': 'NYR'}, 'awayTeam': {'abbrev': 'NJD'}, 'startTimeUTC': '2026-10-29T23:00:00Z'},
            {'homeTeam': {'abbrev': 'TOR'}, 'awayTeam': {'abbrev': 'OTT'}, 'startTimeUTC': '2026-10-29T23:30:00Z'},
        ]
        games = ns['get_all_games_for_date']('2026-10-29', schedule, {}, {}, {})
        self.assertEqual([g['home']['name'] for g in games], ['NYR', 'BOS', 'TOR', 'SEA'])
        self.assertEqual([g['home']['name'] for g in ns['strongest_plays'](games)], ['BOS', 'TOR', 'SEA'])


if __name__ == '__main__':
    unittest.main()

