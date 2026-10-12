"""Regression tests for market-aware NHL win probabilities and odds lookup."""
import ast
import unittest
from pathlib import Path


def load_helpers():
    tree = ast.parse(Path("run_pipeline.py").read_text(encoding="utf-8"))
    names = {
        "get_odds_for_matchup",
        "_american_implied_probability",
        "blend_home_win_probability",
    }
    functions = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = {
        "ABBREV_TO_NAME": {
            "NJD": "New Jersey Devils",
            "NYI": "New York Islanders",
            "OTT": "Ottawa Senators",
        }
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), "run_pipeline.py", "exec"), namespace)
    return namespace


class ProbabilityBlendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = load_helpers()

    def test_market_anchor_limits_extreme_model_disagreement_and_respects_favorite(self):
        blend = self.helpers["blend_home_win_probability"]
        # NJD -135 / OTT +114 implies about 55% for NJD after removing vig.
        adjusted = blend(27.0, "-135", "+114")
        self.assertAlmostEqual(adjusted, 52.3, delta=0.2)
        self.assertGreater(adjusted, 50.0)
        self.assertLess(abs(adjusted - 55.1), abs(27.0 - 55.1))

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


if __name__ == "__main__":
    unittest.main()

