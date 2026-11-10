import unittest

from player_props.generate_daily import odds_lines


def make_event(markets):
    return {
        "id": "odds-event",
        "home_team": "Toronto Maple Leafs",
        "away_team": "Colorado Avalanche",
        "commence_time": "2026-11-12T00:00:00Z",
        "bookmakers": markets,
    }


def book(key, outcomes):
    return {
        "key": key,
        "title": key,
        "markets": [{
            "key": "player_goals",
            "last_update": "2026-11-11T00:00:00Z",
            "outcomes": outcomes,
        }],
    }


def outcome(side, line, price):
    return {"name": side, "description": "Test Skater", "point": line, "price": price}


class MainLineOddsTests(unittest.TestCase):
    def setUp(self):
        self.games = [{
            "game_id": "nhl-game",
            "game_date": "2026-11-11",
            "home_name": "Toronto Maple Leafs",
            "away_name": "Colorado Avalanche",
            "home_team": "TOR",
            "away_team": "COL",
            "commence_time": "2026-11-12T00:00:00Z",
        }]
        player = {"player_id": 1, "player": "Test Skater", "position": "C"}
        self.rosters = {
            "TOR": {"skaters": [player], "goalies": []},
            "COL": {"skaters": [], "goalies": []},
        }

    def run_lines(self, books):
        snapshot = {
            "snapshot_at": "2026-11-11T00:00:00Z",
            "events": [make_event(books)],
        }
        return odds_lines(snapshot, self.games, self.rosters)

    def test_excludes_one_sided_exchange_alternate(self):
        data = self.run_lines([
            book("fanduel", [outcome("Over", 0.5, 150), outcome("Under", 0.5, -200)]),
            book("novig", [outcome("Over", 2.5, 33233)]),
        ])
        key = ("nhl-game", "1", "player_goals", 0.5)
        self.assertEqual(set(data), {key})
        self.assertEqual(data[key]["books"], {"fanduel": {"over": 150, "under": -200}})

    def test_falls_back_to_draftkings_for_complete_pair(self):
        data = self.run_lines([
            book("fanduel", [outcome("Over", 0.5, 150)]),
            book("draftkings", [outcome("Over", 0.5, 145), outcome("Under", 0.5, -190)]),
        ])
        key = ("nhl-game", "1", "player_goals", 0.5)
        self.assertEqual(set(data), {key})
        self.assertEqual(set(data[key]["books"]), {"draftkings"})

    def test_suppresses_ambiguous_alternates_without_provider_agreement(self):
        data = self.run_lines([
            book("fanduel", [
                outcome("Over", 0.5, 150), outcome("Under", 0.5, -200),
                outcome("Over", 1.5, 500), outcome("Under", 1.5, -900),
            ]),
        ])
        self.assertEqual(data, {})


if __name__ == "__main__":
    unittest.main()
