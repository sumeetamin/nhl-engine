"""Goal ladders: Poisson lines on team scoring rates, only from earlier games."""
import math
import unittest

from goal_ladders import BOTH_FACTOR, CARRY, P1_SHARE, both_score, expected_goals, game_ladders, p_over, team_rates


def game(day, away, home, a, h):
    return {"Date": day, "Away": away, "Home": home, "Away_Score": a, "Home_Score": h}


class GoalLadderTests(unittest.TestCase):
    def test_poisson_lines(self):
        self.assertAlmostEqual(p_over(3.0, 0.5), 1 - math.exp(-3), places=12)
        self.assertAlmostEqual(p_over(3.0, 1.5), 1 - math.exp(-3) * 4, places=12)
        self.assertAlmostEqual(p_over(3.0, 3.5), 1 - math.exp(-3) * (1 + 3 + 4.5 + 4.5), places=12)

    def test_no_history_means_league_average_for_both_teams(self):
        lam_h, lam_a = expected_goals(team_rates([], "2026-10-20"), "BOS", "TOR")
        self.assertEqual((lam_h, lam_a), (3.2, 3.0))

    def test_only_games_before_the_date_count(self):
        rows = [game("2026-10-10", "TOR", "BOS", 1, 6), game("2026-10-20", "TOR", "BOS", 9, 0)]
        before = team_rates(rows, "2026-10-20")
        self.assertEqual(before["teams"]["BOS"][0], before["teams"]["BOS"][2] * 6)  # only the 6-1 game

    def test_a_strong_attack_against_a_weak_defence_raises_the_count(self):
        rows = [game(f"2026-10-{d:02d}", "TOR", "BOS", 1, 5) for d in range(1, 15)]
        lam_bos, lam_tor = expected_goals(team_rates(rows, "2026-10-20"), "BOS", "TOR")
        self.assertGreater(lam_bos, 3.4)
        self.assertLess(lam_tor, 2.6)

    def test_last_season_counts_less(self):
        rows = [game("2026-04-10", "TOR", "BOS", 1, 6)]
        w = team_rates(rows, "2026-10-20")["teams"]["BOS"][2]
        decay = math.exp(-(193) / 480)
        self.assertAlmostEqual(w, decay * CARRY, places=9)

    def test_the_card_payload(self):
        out = game_ladders(team_rates([], "2026-10-20"), "BOS", "TOR")
        self.assertEqual(set(out), {"away", "home", "first_period", "both_score"})
        self.assertEqual(list(out["home"]["over"]), ["0.5", "1.5", "2.5", "3.5"])
        self.assertEqual(list(out["first_period"]["over"]), ["0.5", "1.5", "2.5"])
        self.assertAlmostEqual(out["first_period"]["xg"], round(6.2 * P1_SHARE, 2))
        ladder = list(out["home"]["over"].values())
        self.assertEqual(ladder, sorted(ladder, reverse=True))

    def test_both_teams_to_score_is_the_corrected_product(self):
        both = both_score(3.2, 2.9)
        self.assertEqual(list(both), ["1", "2", "3"])
        for k in (1, 2, 3):
            plain = 100 * p_over(3.2, k - 0.5) * p_over(2.9, k - 0.5)
            self.assertAlmostEqual(both[str(k)], round(BOTH_FACTOR[k] * plain, 1))
            # Never above either team's own chance.
            self.assertLessEqual(both[str(k)], 100 * p_over(2.9, k - 0.5))
        self.assertGreater(both["1"], both["2"])
        self.assertGreater(both["2"], both["3"])

    def test_bad_rows_are_skipped(self):
        rows = [game("2026-10-10", "TOR", "BOS", "", 3), {"Date": "nonsense"}, game("2026-10-11", "TOR", "BOS", 2, 3)]
        self.assertEqual(round(team_rates(rows, "2026-10-20")["teams"]["BOS"][1] /
                               team_rates(rows, "2026-10-20")["teams"]["BOS"][2], 6), 2.0)


if __name__ == "__main__":
    unittest.main()
