"""Power ratings, game score and back-to-back flags for the slate (display only).

POWER RATING: goals per game better than an average team on neutral ice. A
simple rating system (each team's average margin plus the average rating of
its opponents, solved by iteration and centred on zero) on past_games.csv,
only games BEFORE the slate's date, with home ice taken out of every margin.
This season's games weigh 1, halving every HALF_LIFE_DAYS days back; last
season's together count as LAST_SEASON_GAMES games per team, so October leans
on them a little and they fade within weeks. The NBA page uses the same
formula in points.

GAME SCORE, 0-100: GAME_SCORE_STRENGTH from how good both teams are (their
power ranks) and the rest from how close the game is (the card's win %). Two
top teams in a coin flip score highest; the NBA and football pages use the
same formula.

BACK TO BACK: a team that played the day before (the second night).

None of this feeds the model or the picks.
"""
import csv
from collections import defaultdict
from datetime import date, timedelta

LAST_SEASON_GAMES = 10
HALF_LIFE_DAYS = 60
GAME_SCORE_STRENGTH = 0.6


def season_start_year(day):
    """The year an NHL season starts: October to June is one season."""
    return day.year if day.month >= 8 else day.year - 1


def load_history(path):
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def _finals(rows):
    for r in rows:
        try:
            day = date.fromisoformat(str(r["Date"])[:10])
            home_goals, away_goals = float(r["Home_Score"]), float(r["Away_Score"])
        except (KeyError, TypeError, ValueError):
            continue
        yield day, r["Home"], r["Away"], home_goals - away_goals


def power_ratings(rows, as_of):
    """{team: goals per game better than average} from games before `as_of`."""
    this_season = season_start_year(as_of)
    used = [(d, h, a, m) for d, h, a, m in _finals(rows)
            if d < as_of and season_start_year(d) in (this_season, this_season - 1)]
    if not used:
        return {}
    home_ice = sum(m for _, _, _, m in used) / len(used)
    games = defaultdict(list)
    for day, home, away, margin in used:
        if season_start_year(day) == this_season:
            weight = 0.5 ** ((as_of - day).days / HALF_LIFE_DAYS)
        else:
            weight = LAST_SEASON_GAMES / 82
        games[home].append((away, margin - home_ice, weight))
        games[away].append((home, home_ice - margin, weight))
    # Each step is averaged with the last: the plain iteration can swing
    # back and forth for ever (two teams that only meet each other); the
    # damped one settles on the same answer.
    rating = {team: 0.0 for team in games}
    for _ in range(500):
        nxt = {team: sum(w * (m + rating[o]) for o, m, w in played) / sum(w for _, _, w in played)
               for team, played in games.items()}
        mean = sum(nxt.values()) / len(nxt)
        rating = {team: (rating[team] + value - mean) / 2 for team, value in nxt.items()}
    return rating


def power_ranks(ratings):
    order = sorted(ratings, key=lambda team: -ratings[team])
    return {team: i + 1 for i, team in enumerate(order)}


def game_score(home_rank, away_rank, teams, home_win_pct):
    """0-100: two highly ranked teams in a close game score highest."""
    strength = 100 * (1 - ((home_rank + away_rank) / 2 - 1) / (teams - 1))
    closeness = 100 * (1 - abs(2 * home_win_pct / 100 - 1))
    return round(GAME_SCORE_STRENGTH * strength + (1 - GAME_SCORE_STRENGTH) * closeness)


def annotate_slate(games_by_date, history_rows, as_of, standings=None):
    """Add power, game_score and b2b to every game; return the rankings table."""
    ratings = power_ratings(history_rows, as_of)
    ranks = power_ranks(ratings)
    played = set()
    for day, home, away, _ in _finals(history_rows):
        played.update({(home, day), (away, day)})
    for date_str, games in games_by_date.items():
        for g in games or []:
            day = date.fromisoformat(date_str)
            played.update({(g["home"]["name"], day), (g["away"]["name"], day)})
    for date_str, games in games_by_date.items():
        before = date.fromisoformat(date_str) - timedelta(days=1)
        for g in games or []:
            home, away = g["home"]["name"], g["away"]["name"]
            g["b2b"] = {"away": (away, before) in played, "home": (home, before) in played}
            g["power"] = {side: {"rank": ranks.get(team), "rating": round(ratings[team], 2)}
                          for side, team in (("away", away), ("home", home)) if team in ratings}
            if home in ranks and away in ranks:
                g["game_score"] = game_score(ranks[home], ranks[away], len(ranks), g["home_win_prob"])
    table = []
    for team in sorted(ranks, key=ranks.get):
        row = {"rank": ranks[team], "team": team, "power": round(ratings[team], 2)}
        row.update({k: v for k, v in (standings or {}).get(team, {}).items()
                    if k in ("overall", "l10", "points", "gp", "gd", "division", "conference", "streak")})
        table.append(row)
    return table
