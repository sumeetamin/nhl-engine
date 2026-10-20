"""Test payload dates without importing the model or making network requests."""
import ast
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


class PredictionPayloadTests(unittest.TestCase):
    def test_delayed_run_keeps_dates_and_top_plays_aligned(self):
        tree = ast.parse(Path('run_pipeline.py').read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build_daily_json')
        saved = {}
        calls = []

        def games(date, *args):
            calls.append(date)
            return [{'date': date, 'tier': 'EDGE'}]

        ns = dict(datetime=datetime, timedelta=timedelta, timezone=timezone,
                  get_est_now=lambda: datetime(2026, 9, 30, 23, 59),
                  get_schedule_window=lambda dates: {date: [] for date in dates},
                  fetch_nhl_odds=lambda: {}, fetch_standings=lambda: {},
                  fetch_goalie_table=lambda day: None,
                  GIFT_AVAILABLE=False, get_all_games_for_date=games,
                  save_json=lambda name, payload: saved.update(payload), print=lambda *a: None)
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'run_pipeline.py', 'exec'), ns)
        ns['build_daily_json']()
        self.assertEqual(calls, ['2026-09-28', '2026-09-29', '2026-09-30', '2026-10-01', '2026-10-02'])
        self.assertEqual(saved['timezone'], 'America/New_York')
        self.assertEqual(saved['today'], saved['games_by_date']['2026-09-30'])
        self.assertEqual(saved['games_by_date']['2026-10-01'][0]['date'], '2026-10-01')
        self.assertEqual(saved['top_plays_date'], '2026-09-30')
        self.assertEqual(saved['top_plays'][0]['date'], '2026-09-30')
        self.assertIsNotNone(datetime.fromisoformat(saved['generated_at']).tzinfo)


if __name__ == '__main__':
    unittest.main()

