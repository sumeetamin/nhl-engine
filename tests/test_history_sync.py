"""Tests for the NHL results history consumed by the prediction model."""
import csv
import unittest
from pathlib import Path

import track_results
from datetime import date, timedelta


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class HistorySyncTests(unittest.TestCase):
    def test_final_games_are_upserted_once_with_real_scores(self):
        game = {
            "gameState": "FINAL",
            "gameType": 2,
            "gameDate": "2026-10-11",
            "awayTeam": {"abbrev": "BOS", "score": 2},
            "homeTeam": {"abbrev": "BUF", "score": 4},
        }
        path = Path(__file__).with_name("past_games_test.csv")
        try:
            self.assertEqual(track_results.merge_final_games([game], path), 1)
            self.assertEqual(track_results.merge_final_games([game], path), 0)
            with open(path, newline="", encoding="utf-8") as history_file:
                rows = list(csv.DictReader(history_file))
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Actual_Winner"], "BUF")
        self.assertEqual(rows[0]["Away_Score"], "2")
        self.assertEqual(rows[0]["Home_Score"], "4")

    def test_preseason_games_are_excluded(self):
        game = {
            "gameState": "FINAL",
            "gameType": 1,
            "gameDate": "2025-09-20",
            "awayTeam": {"abbrev": "BOS", "score": 2},
            "homeTeam": {"abbrev": "BUF", "score": 4},
        }
        self.assertIsNone(track_results._game_to_history_row(game))

    def test_schedule_games_are_stamped_with_their_day_so_they_are_kept(self):
        week = {"gameWeek": [{"date": "2026-10-18", "games": [{
            "gameState": "OFF", "gameType": 2,
            "awayTeam": {"abbrev": "CBJ", "score": 1}, "homeTeam": {"abbrev": "MIN", "score": 2}}]}]}
        games = track_results.fetch_schedule_games("2026-10-18", get=lambda url, timeout: FakeResponse(week))
        row = track_results._game_to_history_row(games[0])
        self.assertEqual(row["Date"], "2026-10-18")
        self.assertEqual(row["Actual_Winner"], "MIN")

    def test_catch_up_starts_after_the_newest_stored_game_one_call_a_week(self):
        calls = []

        def get(url, timeout):
            calls.append(url.rsplit("/", 1)[1])
            start = date.fromisoformat(calls[-1])
            return FakeResponse({"gameWeek": [
                {"date": (start + timedelta(days=i)).isoformat(), "games": [{"id": i}]} for i in range(7)]})

        history = {("2026-10-01", "BOS", "BUF"): {}}
        games = track_results.fetch_games_since(history, "2026-10-19", get=get)
        self.assertEqual(calls, ["2026-10-02", "2026-10-09", "2026-10-16"])
        self.assertEqual(games[0]["gameDate"], "2026-10-02")
        self.assertEqual(games[-1]["gameDate"], "2026-10-19")  # nothing after yesterday
        self.assertEqual(len(games), 18)

    def test_an_up_to_date_history_makes_no_call_and_a_long_gap_stops_at_45_days(self):
        def no_call(url, timeout):
            raise AssertionError("no call expected")
        self.assertEqual(track_results.fetch_games_since({("2026-10-19", "A", "B"): {}}, "2026-10-19", get=no_call), [])
        calls = []
        track_results.fetch_games_since({("2026-06-14", "A", "B"): {}}, "2026-10-19",
                                        get=lambda url, timeout: calls.append(url) or FakeResponse({"gameWeek": []}))
        self.assertTrue(calls[0].endswith("2026-09-05"))

    def test_model_history_path_is_the_frontend_published_csv(self):
        source = Path("run_pipeline.py").read_text(encoding="utf-8")
        self.assertIn('HISTORY_CSV_PATH = os.path.join(SCRIPT_DIR, "frontend", "public", "past_games.csv")', source)
        self.assertIn('csv_path=HISTORY_CSV_PATH', source)


if __name__ == "__main__":
    unittest.main()

