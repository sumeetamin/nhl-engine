"""Goalie cards: real save % matched by name, coloured against the league."""
import unittest
from datetime import datetime

from goalie_stats import build_table, goalie_card, previous_season_id, season_id


def line(name, gp, saves, shots, team="MIN"):
    return {"goalieFullName": name, "gamesPlayed": gp, "saves": saves, "shotsAgainst": shots,
            "savePct": saves / shots, "goalsAgainstAverage": 2.5, "teamAbbrevs": team}


# This season is past the 2,000-shot mark, so its league average is .900 from it alone;
# over both seasons it is .901.
CURRENT = [line("Jesper Wallstedt", 8, 188, 204), line("Karel Vejmelka", 8, 153, 174),
           line("Filler Goalie", 60, 1459, 1622)]
PREVIOUS = [line("Jesper Wallstedt", 30, 700, 760), line("Karel Vejmelka", 50, 1150, 1290),
            line("Ukko-Pekka Luukkonen", 50, 1100, 1220)]


class GoalieStatsTests(unittest.TestCase):
    def setUp(self):
        self.table = build_table(CURRENT, PREVIOUS)

    def test_season_ids_turn_over_in_september(self):
        self.assertEqual(season_id(datetime(2026, 10, 20)), "20262027")
        self.assertEqual(season_id(datetime(2027, 4, 1)), "20262027")
        self.assertEqual(season_id(datetime(2026, 8, 31)), "20252026")
        self.assertEqual(previous_season_id("20262027"), "20252026")

    def test_league_average_is_saves_over_shots(self):
        self.assertAlmostEqual(self.table["league_sv_pct"], 1800 / 2000, places=6)
        self.assertAlmostEqual(self.table["league_both"], (1800 + 2950) / (2000 + 3270), places=6)

    def test_opening_nights_take_last_season_into_the_shown_average_too(self):
        table = build_table([line("Rookie Starter", 2, 60, 62)], PREVIOUS)
        self.assertAlmostEqual(table["league_sv_pct"], table["league_both"], places=6)

    def test_a_starter_shows_this_season_and_last(self):
        card = goalie_card("Jesper Wallstedt", "Confirmed", self.table)
        self.assertEqual(card["sv_pct"], 0.922)
        self.assertEqual(card["gp"], 8)
        self.assertEqual(card["prev_sv_pct"], 0.921)
        self.assertEqual(card["status"], "Confirmed")

    def test_colour_uses_both_seasons_so_one_hot_week_does_not_decide_it(self):
        # .921 over 964 shots: well above .900
        self.assertEqual(goalie_card("Jesper Wallstedt", "Expected", self.table)["rating"], "good")
        # .879 this season but .890 over both, 1,464 shots: below .901 by more than the band
        self.assertEqual(goalie_card("Karel Vejmelka", "Expected", self.table)["rating"], "poor")

    def test_names_match_without_accents_or_case(self):
        self.assertEqual(goalie_card("ukko-pekka luukkonen", "Expected", self.table)["prev_sv_pct"], 0.902)

    def test_unknown_or_tbd_goalies_and_a_failed_fetch_stay_grey(self):
        for name, table in (("Nobody Atall", self.table), ("TBD", self.table), ("Jesper Wallstedt", None)):
            card = goalie_card(name, "Expected", table)
            self.assertIsNone(card["sv_pct"])
            self.assertEqual(card["rating"], "average")

    def test_too_few_shots_stays_grey(self):
        table = build_table([line("Rookie Starter", 2, 60, 62)], [])
        self.assertEqual(goalie_card("Rookie Starter", "Expected", table)["rating"], "average")


if __name__ == "__main__":
    unittest.main()
