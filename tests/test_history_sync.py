"""Tests for the NHL results history consumed by the prediction model."""
import csv
import unittest
from pathlib import Path

import track_results


class HistorySyncTests(unittest.TestCase):
    def test_final_games_are_upserted_once_with_real_scores(self):
        game = {
            "gameState": "FINAL",
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

    def test_model_history_path_is_the_frontend_published_csv(self):
        source = Path("run_pipeline.py").read_text(encoding="utf-8")
        self.assertIn('HISTORY_CSV_PATH = os.path.join(SCRIPT_DIR, "frontend", "public", "past_games.csv")', source)
        self.assertIn('csv_path=HISTORY_CSV_PATH', source)


if __name__ == "__main__":
    unittest.main()

