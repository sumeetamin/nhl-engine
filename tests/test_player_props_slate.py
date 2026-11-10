"""Regression for NHL evening games that start on the following UTC day."""
import unittest
from datetime import date
from unittest.mock import patch

from player_props import generate_daily as daily


class PlayerPropsSlateTests(unittest.TestCase):
    def test_evening_game_on_final_slate_day_matches_odds(self):
        start = "2026-11-13T00:00:00Z"
        home = {"abbrev": "TOR", "placeName": "Toronto", "commonName": "Maple Leafs"}
        away = {"abbrev": "COL", "placeName": "Colorado", "commonName": "Avalanche"}
        game = {"id": 123, "startTimeUTC": start, "homeTeam": home, "awayTeam": away}
        schedule = {"gameWeek": [{"date": "2026-11-12", "games": [game]}]}
        event = {"id": "abc", "home_team": "Toronto Maple Leafs",
                 "away_team": "Colorado Avalanche", "commence_time": start}
        with patch.object(daily, "request_json", side_effect=[schedule, [event], {}]) as fetch:
            games = daily.flatten_schedule(date(2026, 11, 10))
            snapshot = daily.fetch_odds_snapshot(games, "test")
        self.assertEqual(games[0]["game_date"], "2026-11-12")
        self.assertEqual(snapshot["events"][0]["game_id"], "123")
        books = fetch.call_args.kwargs["params"]["bookmakers"].split(",")
        self.assertEqual(set(books), daily.ALLOWED_BOOKS)

    def test_saved_lines_cannot_move_to_a_rematch(self):
        rematch = {"game_id": "2", "game_date": "2026-11-13",
                   "home_name": "Toronto Maple Leafs", "away_name": "Colorado Avalanche"}
        previous = {"game_id": "1", "commence_time": "2026-11-11T00:00:00Z",
                    "home_team": rematch["home_name"], "away_team": rematch["away_name"]}
        for event in [previous, {k: v for k, v in previous.items() if k != "game_id"}]:
            with self.subTest(event=event):
                self.assertEqual(daily.odds_lines({"events": [event]}, [rematch], {}), {})
