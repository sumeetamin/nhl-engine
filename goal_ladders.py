"""Each team's chance to score over 0.5 / 1.5 / 2.5 / 3.5 goals, and the
first-period total over 0.5 / 1.5 / 2.5.

HOW. Each team gets an expected goal count for the game: the league's home
(or away) scoring rate x the team's scoring rate x the opponent's rate of
goals allowed, both relative to the league. Rates come from past_games.csv
(final scores, the shootout winner credited one goal as the books do), only
games BEFORE the game's date, weighted down with age (e-folding time 480
days), last season's games x0.6, and 20 games' worth of league average mixed
into every team so a hot week does not run away with it. The chance of each
line is a Poisson on that count. The first period gets 28.4% of the game's
expected total, the league's share.

TESTED, walk-forward on every game of 2024-25, 2025-26 and 2026-27 so far
(nhl_goals_bt, tuned on 2022-23 and 2023-24 only):
  - team lines: calibrated within about 2 points at every line (says 77%,
    hit 77%; says 84%, hit 83%; says 56%, hit 57%), and better than the
    league average for every team in all three test seasons;
  - negative binomial fitted no better than Poisson;
  - first period: team differences are small (expected total 1.6 to 1.9 in
    95% of games). Over 0.5 is ~83% nearly every game, over 1.5 sits between
    48% and 60%. The previous "1st Period Over 1.5" figure,
    min(90, P1 goals x 40)%, averaged 70% on games that went over 53% of
    the time.

These are probabilities, not edges: no price is read here.
"""
import math
from datetime import date, datetime

DECAY_DAYS = 480
CARRY = 0.6           # per season boundary crossed
PRIOR_GAMES = 20      # league-average games mixed into each team
P1_SHARE = 0.284      # first period's share of the game's goals
TEAM_LINES = (0.5, 1.5, 2.5, 3.5)
P1_LINES = (0.5, 1.5, 2.5)


def _season(day: date) -> int:
    return day.year if day.month >= 9 else day.year - 1


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def team_rates(rows, as_of) -> dict:
    """Weighted goals for/against per team from games strictly before `as_of`.

    rows: dicts (or a DataFrame's records) with Date, Away, Home, Away_Score,
    Home_Score. Returns {"teams": {abbr: (gf, ga, weight)}, "mu_home", "mu_away"}.
    """
    as_of = _as_date(as_of)
    season_now = _season(as_of)
    teams: dict[str, list[float]] = {}
    lh = la = lw = 0.0
    for r in rows:
        try:
            day = _as_date(r["Date"])
            hs, as_ = float(r["Home_Score"]), float(r["Away_Score"])
        except (KeyError, TypeError, ValueError):
            continue
        if day >= as_of or math.isnan(hs) or math.isnan(as_):
            continue
        decay = math.exp(-(as_of - day).days / DECAY_DAYS)
        w = decay * CARRY ** (season_now - _season(day))
        for team, gf, ga in ((r["Home"], hs, as_), (r["Away"], as_, hs)):
            t = teams.setdefault(team, [0.0, 0.0, 0.0])
            t[0] += w * gf
            t[1] += w * ga
            t[2] += w
        # The league's own averages decay but carry no season penalty.
        lh += decay * hs
        la += decay * as_
        lw += decay
    return {"teams": {k: tuple(v) for k, v in teams.items()},
            "mu_home": lh / lw if lw else 3.2, "mu_away": la / lw if lw else 3.0}


def expected_goals(rates: dict, home: str, away: str) -> tuple[float, float]:
    mu_h, mu_a = rates["mu_home"], rates["mu_away"]
    mu = (mu_h + mu_a) / 2

    def rel(team):
        gf, ga, w = rates["teams"].get(team, (0.0, 0.0, 0.0))
        return ((gf + PRIOR_GAMES * mu) / (w + PRIOR_GAMES) / mu,
                (ga + PRIOR_GAMES * mu) / (w + PRIOR_GAMES) / mu)

    att_h, def_h = rel(home)
    att_a, def_a = rel(away)
    return mu_h * att_h * def_a, mu_a * att_a * def_h


def p_over(lam: float, line: float) -> float:
    """Poisson P(goals > line)."""
    k = math.floor(line)
    term = cdf = math.exp(-lam)
    for i in range(1, k + 1):
        term *= lam / i
        cdf += term
    return max(0.0, 1.0 - cdf)


def ladder(lam: float, lines=TEAM_LINES) -> dict:
    return {"xg": round(lam, 2), "over": {str(l): round(100 * p_over(lam, l), 1) for l in lines}}


def game_ladders(rates: dict, home: str, away: str) -> dict:
    """What the card shows: each team's ladder and the first-period total."""
    lam_h, lam_a = expected_goals(rates, home, away)
    return {"away": ladder(lam_a), "home": ladder(lam_h),
            "first_period": ladder((lam_h + lam_a) * P1_SHARE, P1_LINES)}
