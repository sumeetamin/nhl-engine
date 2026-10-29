"""Power ratings, game score and back-to-back flags (power.py)."""
import unittest
from datetime import date

from power import annotate_slate, game_score, power_ranks, power_ratings


def row(day, away, home, away_goals, home_goals):
    return {"Date": day, "Away": away, "Home": home,
            "Away_Score": str(away_goals), "Home_Score": str(home_goals)}


def game(away, home, home_win_prob=50.0):
    return {"away": {"name": away}, "home": {"name": home}, "home_win_prob": home_win_prob}


class PowerRatingTests(unittest.TestCase):
    def test_the_team_that_beats_everyone_ranks_first_and_ratings_centre_on_zero(self):
        rows = [row("2026-10-10", "BBB", "AAA", 1, 4), row("2026-10-12", "AAA", "CCC", 3, 1),
                row("2026-10-14", "CCC", "BBB", 2, 2), row("2026-10-16", "BBB", "CCC", 3, 2)]
        ratings = power_ratings(rows, date(2026, 10, 20))
        self.assertEqual(power_ranks(ratings)["AAA"], 1)
        self.assertAlmostEqual(sum(ratings.values()), 0.0, places=9)

    def test_home_ice_is_taken_out(self):
        # Every game is won at home by one goal: no team is better than another.
        rows = [row("2026-10-10", "BBB", "AAA", 2, 3), row("2026-10-12", "AAA", "BBB", 2, 3),
                row("2026-10-14", "CCC", "AAA", 2, 3), row("2026-10-16", "AAA", "CCC", 2, 3),
                row("2026-10-18", "CCC", "BBB", 2, 3), row("2026-10-19", "BBB", "CCC", 2, 3)]
        for value in power_ratings(rows, date(2026, 10, 20)).values():
            self.assertAlmostEqual(value, 0.0, places=6)

    def test_only_games_before_the_date_and_from_the_last_two_seasons_count(self):
        rows = [row("2024-11-01", "BBB", "AAA", 0, 9),   # two seasons back: ignored
                row("2026-10-20", "BBB", "AAA", 0, 9),   # the slate's own date: ignored
                row("2026-10-10", "AAA", "BBB", 1, 2), row("2026-10-12", "BBB", "AAA", 1, 1)]
        ratings = power_ratings(rows, date(2026, 10, 20))
        self.assertGreater(ratings["BBB"], ratings["AAA"])

    def test_this_season_outweighs_last_season(self):
        # Last spring AAA won big; this October BBB won twice by a goal on the road.
        rows = [row(f"2026-03-{d:02d}", "BBB", "AAA", 1, 5) for d in range(1, 21)]
        rows += [row("2026-10-10", "BBB", "AAA", 3, 2), row("2026-10-12", "BBB", "AAA", 3, 2)]
        ratings = power_ratings(rows, date(2026, 10, 14))
        self.assertGreater(ratings["BBB"], ratings["AAA"])


class GameScoreTests(unittest.TestCase):
    def test_top_teams_in_a_close_game_score_highest(self):
        best = game_score(1, 2, 32, 50.0)
        lopsided = game_score(1, 32, 32, 85.0)
        weak_and_close = game_score(31, 32, 32, 50.0)
        self.assertGreater(best, 95)
        self.assertGreater(best, weak_and_close)
        self.assertGreater(best, lopsided)
        self.assertEqual(game_score(1, 1, 32, 100.0), 60)


class AnnotateSlateTests(unittest.TestCase):
    def test_back_to_back_power_game_score_and_table(self):
        history = [row("2026-10-27", "BBB", "AAA", 1, 4), row("2026-10-26", "CCC", "DDD", 2, 3)]
        slate = {"2026-10-28": [game("CCC", "AAA", 70.0)], "2026-10-29": [game("AAA", "BBB", 40.0)]}
        table = annotate_slate(slate, history, date(2026, 10, 28),
                               {"AAA": {"overall": "1-0-0", "points": 2, "home": "1-0-0"}})
        first = slate["2026-10-28"][0]
        self.assertEqual(first["b2b"], {"away": False, "home": True})   # AAA played 10-27
        self.assertEqual(slate["2026-10-29"][0]["b2b"], {"away": True, "home": False})  # AAA plays 10-28
        self.assertEqual(first["power"]["home"]["rank"], 1)
        self.assertIn("game_score", first)
        self.assertEqual(table[0], {"rank": 1, "team": "AAA", "power": table[0]["power"],
                                    "overall": "1-0-0", "points": 2})
        self.assertEqual([r["rank"] for r in table], [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
