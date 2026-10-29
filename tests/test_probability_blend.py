"""Regression tests for market-aware NHL win probabilities and odds lookup."""
import ast
import unicodedata
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path


def load_helpers():
    tree = ast.parse(Path("run_pipeline.py").read_text(encoding="utf-8"))
    names = {
        "get_odds_for_matchup",
        "odds_team_abbrev",
        "pregame_key",
        "remember_pregame_odds",
        "pregame_prices",
        "_american_implied_probability",
        "blend_home_win_probability",
    }
    constants = {"TEAM_NAME_MAP", "ODDS_TEAM_ABBREV", "PREGAME_ODDS_DAYS"}
    body = [node for node in tree.body
            if (isinstance(node, ast.FunctionDef) and node.name in names)
            or (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets))]
    namespace = {"unicodedata": unicodedata, "datetime": datetime, "timedelta": timedelta,
                 "timezone": timezone, "EASTERN": ZoneInfo("America/New_York")}
    exec(compile(ast.Module(body=body, type_ignores=[]), "run_pipeline.py", "exec"), namespace)
    return namespace


def h2h_game(home, away, home_price, away_price, commence_time="2026-10-29T23:00:00Z"):
    return {
        "commence_time": commence_time,
        "home_team": home,
        "away_team": away,
        "bookmakers": [{"markets": [{
            "key": "h2h",
            "outcomes": [
                {"name": home, "price": home_price},
                {"name": away, "price": away_price},
            ],
        }]}],
    }


class ProbabilityBlendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = load_helpers()

    def test_market_anchor_limits_extreme_model_disagreement_and_respects_favorite(self):
        blend = self.helpers["blend_home_win_probability"]
        # NJD -135 / OTT +114 implies about 55% for NJD after removing vig.
        adjusted = blend(27.0, "-135", "+114")
        self.assertAlmostEqual(adjusted, 53.7, delta=0.2)
        self.assertGreater(adjusted, 50.0)
        self.assertLess(abs(adjusted - 55.1), abs(27.0 - 55.1))

    def test_small_home_market_favorite_is_not_flipped_by_extreme_model(self):
        blend = self.helpers["blend_home_win_probability"]
        # MIN -118 / VGK -102 is only a small no-vig home edge.
        adjusted = blend(28.5, "-118", "-102")
        self.assertAlmostEqual(adjusted, 50.6, delta=0.2)
        self.assertGreater(adjusted, 50.0)

    def test_probability_falls_back_to_model_without_both_prices(self):
        blend = self.helpers["blend_home_win_probability"]
        self.assertEqual(blend(27.0), 27.0)
        self.assertEqual(blend(27.0, "-135", None), 27.0)

    def test_moneyline_lookup_distinguishes_new_jersey_from_new_york(self):
        lookup = self.helpers["get_odds_for_matchup"]
        odds = [{
            "home_team": "New Jersey Devils",
            "away_team": "New York Islanders",
            "bookmakers": [{"markets": [{
                "key": "h2h",
                "outcomes": [
                    {"name": "New Jersey Devils", "price": -135},
                    {"name": "New York Islanders", "price": 115},
                ],
            }]}],
        }]
        self.assertEqual(lookup("NJD", "NYI", odds), ("-135", "+115"))

    def test_feed_spellings_of_montreal_st_louis_and_utah_match(self):
        # These three never matched a price before: the slate showed the
        # model's own mirrored line (+326 / -326) instead of the book's.
        lookup = self.helpers["get_odds_for_matchup"]
        odds = [h2h_game("St Louis Blues", "Montréal Canadiens", 120, -140),
                h2h_game("Pittsburgh Penguins", "Utah Mammoth", -150, 130)]
        self.assertEqual(lookup("STL", "MTL", odds), ("+120", "-140"))
        self.assertEqual(lookup("PIT", "UTA", odds), ("-150", "+130"))


class PregameOddsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = load_helpers()

    def test_a_started_game_keeps_its_last_pregame_price(self):
        remember = self.helpers["remember_pregame_odds"]
        prices = self.helpers["pregame_prices"]
        start = "2026-10-28T23:30:00Z"  # 7:30 PM ET
        before = datetime(2026, 10, 28, 21, 0, tzinfo=timezone.utc)
        store = remember({}, [h2h_game("Washington Capitals", "Philadelphia Flyers", -150, 130, start)], before)
        self.assertEqual(prices(store, "2026-10-28", "WSH", "PHI"), ("-150", "+130"))
        # 9:30 PM ET: the feed now prices the game live; the stored line stands.
        during = datetime(2026, 10, 29, 1, 30, tzinfo=timezone.utc)
        store = remember(store, [h2h_game("Washington Capitals", "Philadelphia Flyers", -3500, 1400, start)], during)
        self.assertEqual(prices(store, "2026-10-28", "WSH", "PHI"), ("-150", "+130"))
        # Once finished it leaves the feed; the line still stands for grading.
        store = remember(store, [], datetime(2026, 10, 29, 10, 0, tzinfo=timezone.utc))
        self.assertEqual(prices(store, "2026-10-28", "WSH", "PHI"), ("-150", "+130"))

    def test_a_game_first_seen_after_puck_drop_gets_no_price(self):
        remember = self.helpers["remember_pregame_odds"]
        during = datetime(2026, 10, 29, 1, 30, tzinfo=timezone.utc)
        store = remember({}, [h2h_game("Washington Capitals", "Philadelphia Flyers", -3500, 1400,
                                       "2026-10-28T23:30:00Z")], during)
        self.assertEqual(store, {})

    def test_the_eastern_date_keys_a_late_start_and_old_rows_drop(self):
        remember = self.helpers["remember_pregame_odds"]
        now = datetime(2026, 10, 29, 20, 0, tzinfo=timezone.utc)
        # 10:30 PM ET on 10-29 is 02:30 UTC on 10-30.
        store = remember({"2026-10-01|BOS|TOR": {"home": "-120", "away": "+100"}},
                         [h2h_game("San Jose Sharks", "Vancouver Canucks", 105, -125,
                                   "2026-10-30T02:30:00Z")], now)
        self.assertEqual(list(store), ["2026-10-29|SJS|VAN"])


if __name__ == "__main__":
    unittest.main()

