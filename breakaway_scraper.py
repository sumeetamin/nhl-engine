"""
breakaway_scraper.py
====================
Scrapes BreakawayStats.com for:
  - GIFT  : Goals In First Ten minutes (first_10_min)
  - 1P O/U: First Period Over/Under trends (first_period_ou)

Returns a dict keyed by NHL team abbreviation:
{
  "CAR": {
    "gift": { "pct_season": "69.8%", "pct_l5": "60.0%", "pct_l10": "70.0%",
              "record_season": "44-19", "streak": 3,
              "home_pct": "76%", "away_pct": "63%", "scoring_rate": "70%" },
    "fp_ou": { "pct_season": "62.5%", "record_season": "40-24",
               "over_games": 40, "home_pct": "67%", "away_pct": "58%" }
  }, ...
}
"""

import requests
import json
import re
import time
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://breakawaystats.com",
}

BASE_URL = "https://breakawaystats.com"

# NHL abbreviation → fragments that BreakawayStats might use for matching
TEAM_LOOKUP = {
    "ANA": ["Ducks",       "Anaheim"],
    "BOS": ["Bruins",      "Boston"],
    "BUF": ["Sabres",      "Buffalo"],
    "CAR": ["Hurricanes",  "Carolina"],
    "CBJ": ["Blue Jackets","Columbus"],
    "CGY": ["Flames",      "Calgary"],
    "CHI": ["Blackhawks",  "Chicago"],
    "COL": ["Avalanche",   "Colorado"],
    "DAL": ["Stars",       "Dallas"],
    "DET": ["Red Wings",   "Detroit"],
    "EDM": ["Oilers",      "Edmonton"],
    "FLA": ["Panthers",    "Florida"],
    "LAK": ["Kings",       "Los Angeles"],
    "MIN": ["Wild",        "Minnesota"],
    "MTL": ["Canadiens",   "Montreal"],
    "NJD": ["Devils",      "New Jersey"],
    "NSH": ["Predators",   "Nashville"],
    "NYI": ["Islanders",   "New York I"],
    "NYR": ["Rangers",     "New York R"],
    "OTT": ["Senators",    "Ottawa"],
    "PHI": ["Flyers",      "Philadelphia"],
    "PIT": ["Penguins",    "Pittsburgh"],
    "SEA": ["Kraken",      "Seattle"],
    "SJS": ["Sharks",      "San Jose"],
    "STL": ["Blues",       "St. Louis"],
    "TBL": ["Lightning",   "Tampa"],
    "TOR": ["Maple Leafs", "Toronto"],
    "UTA": ["Hockey Club", "Utah"],
    "VAN": ["Canucks",     "Vancouver"],
    "VGK": ["Golden Knights","Vegas"],
    "WSH": ["Capitals",    "Washington"],
    "WPG": ["Jets",        "Winnipeg"],
}


def _get(url: str, params: dict = None, timeout: int = 12) -> requests.Response | None:
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp
    except Exception as e:
        print(f"  ⚠️  GET failed {url}: {e}")
        return None


def _find_team_abbrev(name_text: str) -> str | None:
    """Match a team name string to an NHL abbreviation."""
    name_lower = name_text.lower()
    for abbr, frags in TEAM_LOOKUP.items():
        for frag in frags:
            if frag.lower() in name_lower:
                return abbr
    return None


# ── Strategy 1: Try Next.js __NEXT_DATA__ embedded JSON ───────────────────────
def _try_next_data(category: str) -> dict | None:
    """
    Next.js apps embed their page data in a <script id="__NEXT_DATA__"> tag.
    This is the cleanest extraction method if available.
    """
    url = f"{BASE_URL}/nhl/betting-trends"
    resp = _get(url, params={"category": category, "sortBy": "most"})
    if not resp:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    script = soup.find("script", {"id": "__NEXT_DATA__"})
    if not script:
        return None

    try:
        nd = json.loads(script.string)
        # Navigate into pageProps → teams or similar key
        props = nd.get("props", {}).get("pageProps", {})
        teams_raw = props.get("teams") or props.get("data") or props.get("teamStats")
        if teams_raw:
            print(f"  ✅ __NEXT_DATA__ found for {category}")
            return teams_raw
    except Exception as e:
        print(f"  ⚠️  __NEXT_DATA__ parse error: {e}")
    return None


# ── Strategy 2: Try common Next.js API routes ──────────────────────────────────
def _try_api_route(category: str) -> list | None:
    candidates = [
        f"{BASE_URL}/api/nhl/betting-trends",
        f"{BASE_URL}/api/trends",
        f"{BASE_URL}/api/nhl/trends/{category}",
    ]
    for url in candidates:
        resp = _get(url, params={"category": category})
        if resp and resp.headers.get("content-type", "").startswith("application/json"):
            try:
                data = resp.json()
                if isinstance(data, list) and data:
                    print(f"  ✅ API route worked: {url}")
                    return data
                if isinstance(data, dict):
                    for v in data.values():
                        if isinstance(v, list) and v:
                            return v
            except Exception:
                pass
    return None


# ── Strategy 3: HTML parse fallback ───────────────────────────────────────────
def _parse_html_cards(category: str) -> dict:
    """
    Parse the rendered HTML cards on the betting-trends page.
    Each team card contains percentage, record, home/away splits.
    """
    url  = f"{BASE_URL}/nhl/betting-trends"
    resp = _get(url, params={"category": category, "sortBy": "most"})
    if not resp:
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    result = {}

    # Look for card containers — BreakawayStats uses div cards with percentage text
    cards = soup.find_all("div", class_=re.compile(r"card|team|trend", re.I))

    for card in cards:
        text = card.get_text(" ", strip=True)

        # Try to identify team
        abbr = None
        for known_abbr, frags in TEAM_LOOKUP.items():
            if any(f.lower() in text.lower() for f in frags):
                abbr = known_abbr
                break
        if not abbr:
            continue

        # Extract percentage (e.g. "69.8%")
        pct_match = re.search(r"(\d{1,3}\.\d)%", text)
        pct = pct_match.group(0) if pct_match else "N/A"

        # Extract record (e.g. "44-19")
        rec_match = re.search(r"(\d{1,3}-\d{1,3})", text)
        rec = rec_match.group(0) if rec_match else "N/A"

        # Extract streak (number after "1ST 10 GOAL" or "2+ GOALS")
        streak_match = re.search(r"(?:goal|goals)[^\d]*(\d+)", text, re.I)
        streak = int(streak_match.group(1)) if streak_match else 0

        # Home/Away splits — look for patterns like "25-8 (76%)" 
        ha_matches = re.findall(r"\d+-\d+\s*\((\d+)%\)", text)
        home_pct = f"{ha_matches[0]}%" if len(ha_matches) > 0 else "N/A"
        away_pct = f"{ha_matches[1]}%" if len(ha_matches) > 1 else "N/A"

        result[abbr] = {
            "pct_season":    pct,
            "pct_l5":        "N/A",   # L5/L10 need tab interaction (JS required)
            "pct_l10":       "N/A",
            "record_season": rec,
            "streak":        streak,
            "home_pct":      home_pct,
            "away_pct":      away_pct,
            "scoring_rate":  pct,
        }

    print(f"  📝 HTML parse found {len(result)} teams for {category}")
    return result


# ── Public API ─────────────────────────────────────────────────────────────────
def scrape_gift_stats() -> dict:
    """
    Returns GIFT stats (Goals In First Ten Minutes) for all NHL teams.
    Dict keyed by team abbreviation.
    """
    print("🔍 Scraping BreakawayStats: GIFT (first_10_min)...")

    # Try strategies in order
    raw = _try_next_data("first_10_min")
    if not raw:
        raw = _try_api_route("first_10_min")

    if raw and isinstance(raw, list):
        return _parse_structured(raw, stat_type="gift")

    # Fall back to HTML
    return _parse_html_cards("first_10_min")


def scrape_first_period_stats() -> dict:
    """
    Returns First Period O/U stats for all NHL teams.
    Dict keyed by team abbreviation.
    """
    print("🔍 Scraping BreakawayStats: 1st Period O/U...")
    time.sleep(1)   # polite delay

    raw = _try_next_data("first_period_ou")
    if not raw:
        raw = _try_api_route("first_period_ou")

    if raw and isinstance(raw, list):
        return _parse_structured(raw, stat_type="fp_ou")

    return _parse_html_cards("first_period_ou")


def _parse_structured(raw: list, stat_type: str) -> dict:
    """Parse structured JSON data from Next.js __NEXT_DATA__ or API routes."""
    result = {}
    for item in raw:
        # Try to extract team abbreviation
        abbr = (
            item.get("abbrev") or item.get("abbreviation") or
            item.get("teamAbbrev") or item.get("team_abbrev")
        )
        if not abbr:
            name = item.get("team") or item.get("teamName") or item.get("name", "")
            abbr = _find_team_abbrev(name)
        if not abbr:
            continue

        if stat_type == "gift":
            result[abbr.upper()] = {
                "pct_season":    _pf(item.get("pct") or item.get("percentage") or item.get("seasonPct")),
                "pct_l5":        _pf(item.get("l5Pct")  or item.get("last5Pct")),
                "pct_l10":       _pf(item.get("l10Pct") or item.get("last10Pct")),
                "record_season": item.get("record") or item.get("seasonRecord") or "N/A",
                "streak":        int(item.get("streak") or item.get("currentStreak") or 0),
                "home_pct":      _pf(item.get("homePct") or item.get("home_pct")),
                "away_pct":      _pf(item.get("awayPct") or item.get("away_pct")),
                "scoring_rate":  _pf(item.get("scoringRate") or item.get("scoring_rate")),
            }
        else:  # fp_ou
            result[abbr.upper()] = {
                "pct_season":    _pf(item.get("pct") or item.get("percentage")),
                "record_season": item.get("record") or "N/A",
                "over_games":    int(item.get("overGames") or item.get("over_games") or 0),
                "home_pct":      _pf(item.get("homePct")),
                "away_pct":      _pf(item.get("awayPct")),
            }

    print(f"  ✅ Structured parse: {len(result)} teams")
    return result


def _pf(val) -> str:
    """Format a percentage value safely."""
    if val is None:
        return "N/A"
    s = str(val)
    if "%" not in s:
        try:
            s = f"{float(s):.1f}%"
        except Exception:
            pass
    return s


def get_team_gift(gift_data: dict, abbr: str) -> dict:
    """Get GIFT stats for a specific team, with safe fallback."""
    return gift_data.get(abbr.upper(), {
        "pct_season":    "N/A",
        "pct_l5":        "N/A",
        "pct_l10":       "N/A",
        "record_season": "N/A",
        "streak":        0,
        "home_pct":      "N/A",
        "away_pct":      "N/A",
        "scoring_rate":  "N/A",
    })


def get_team_fp(fp_data: dict, abbr: str) -> dict:
    """Get First Period O/U stats for a specific team, with safe fallback."""
    return fp_data.get(abbr.upper(), {
        "pct_season":    "N/A",
        "record_season": "N/A",
        "over_games":    0,
        "home_pct":      "N/A",
        "away_pct":      "N/A",
    })


if __name__ == "__main__":
    gift = scrape_gift_stats()
    fp   = scrape_first_period_stats()
    print("\nGIFT sample:", json.dumps(dict(list(gift.items())[:3]), indent=2))
    print("\nFP sample:",   json.dumps(dict(list(fp.items())[:3]),   indent=2))
