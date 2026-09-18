"""data/sources.py — внешние источники (football-data, TSDB, Odds API)."""
from __future__ import annotations
import csv, io, re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
    _HAS_RETRY = True
except Exception:
    _HAS_RETRY = False

from config import (CACHE_TTL, DIV_TO_TSDB, DIV_TO_ODDS)
from security import cache_get, cache_put
from storage import usage


def _session() -> requests.Session:
    s = requests.Session()
    if _HAS_RETRY:
        r = Retry(total=3, connect=3, read=3, backoff_factor=1.5,
                  status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=frozenset(["GET", "HEAD", "POST", "PATCH"]),
                  raise_on_status=False)
        ad = HTTPAdapter(max_retries=r, pool_connections=20, pool_maxsize=20)
        s.mount("https://", ad)
        s.mount("http://", ad)
    s.headers.update({"User-Agent": "Mozilla/5.0 Chrome/120.0"})
    s.trust_env = False
    s.proxies = {"http": None, "https": None}
    return s


_sess = _session()
NO_PROXY = {"http": None, "https": None, "all": None}


def _f(v):
    try:
        return float(v)
    except Exception:
        return None


def parse_date(s) -> Optional[datetime]:
    if s is None:
        return None
    src = str(s).strip()
    if not src:
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            sc = src[:19] if "%z" in fmt or "T" in fmt else src
            return datetime.strptime(sc, fmt)
        except Exception:
            continue
    return None


def season_str(year: int) -> str:
    return f"{year % 100:02d}{(year + 1) % 100:02d}"


# -------------------- football-data.co.uk --------------------
def load_seasonal(div: str, season: str) -> list[dict]:
    ck = f"fd_{div}_{season}"
    cached = cache_get(ck, CACHE_TTL["seasonal"])
    if cached is not None:
        return cached if isinstance(cached, list) else []
    url = f"https://www.football-data.co.uk/mmz4281/{season}/{div}.csv"
    try:
        r = _sess.get(url, timeout=25, proxies=NO_PROXY)
        if r.status_code != 200 or not r.content:
            return []
        text = r.content.decode("utf-8", errors="ignore").lstrip("\ufeff")
        out = []
        for row in csv.DictReader(io.StringIO(text)):
            if not isinstance(row, dict):
                continue
            if not row.get("HomeTeam") or not row.get("AwayTeam"):
                continue
            if row.get("FTHG") in (None, "") or row.get("FTAG") in (None, ""):
                continue
            out.append(row)
        cache_put(ck, out)
        return out
    except Exception:
        return []


# -------------------- TheSportsDB --------------------
_TSDB_LEAGUE_MAP = {
    "premier league": "E0", "epl": "E0",
    "championship": "E1",
    "la liga": "SP1", "laliga": "SP1",
    "segunda": "SP2",
    "bundesliga": "D1", "2. bundesliga": "D2",
    "serie a": "I1", "serie b": "I2",
    "ligue 1": "F1", "ligue 2": "F2",
    "eredivisie": "N1",
    "pro league": "B1", "first division": "B1",
    "primeira": "P1",
    "super lig": "T1", "super league": "T1",
    "super league greece": "G1",
    "russian premier": "R1",
    "champions league": "C1",
    "europa league": "EL",
}


def _match_tsdb_league(name: str) -> Optional[str]:
    if not name:
        return None
    ln = name.lower()
    for key, code in _TSDB_LEAGUE_MAP.items():
        if key in ln:
            return code
    return None


def tsdb_today_matches(days: int = 7) -> list[dict]:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for off in range(days):
        d = today + timedelta(days=off)
        dstr = d.strftime("%Y-%m-%d")
        ck = f"tsdb_day_{dstr}"
        cached = cache_get(ck, CACHE_TTL["tsdb_day"])
        if cached is not None:
            if isinstance(cached, list):
                out += cached
            continue
        try:
            r = _sess.get(
                "https://www.thesportsdb.com/api/v1/json/3/eventsday.php",
                params={"d": dstr, "s": "Soccer"},
                timeout=15, proxies=NO_PROXY)
            if r.status_code != 200:
                continue
            ev = (r.json() or {}).get("events") or []
            rows = []
            for e in ev:
                if not isinstance(e, dict):
                    continue
                h, a = e.get("strHomeTeam"), e.get("strAwayTeam")
                if not h or not a:
                    continue
                league = e.get("strLeague") or "Матч"
                rows.append({
                    "Div": _match_tsdb_league(league),
                    "League": league,
                    "Date": (e.get("dateEvent") or "")[:10],
                    "Time": (e.get("strTime") or "")[:5],
                    "HomeTeam": h, "AwayTeam": a,
                    "fixture_id": e.get("idEvent"),
                })
            out += rows
            cache_put(ck, rows)
        except Exception:
            pass
    return out


def tsdb_past_league(tsdb_id: str, limit: int = 60) -> list[dict]:
    if not tsdb_id:
        return []
    ck = f"tsdb_past_{tsdb_id}"
    cached = cache_get(ck, CACHE_TTL["tsdb_past"])
    if cached is not None:
        return cached if isinstance(cached, list) else []
    try:
        r = _sess.get(
            "https://www.thesportsdb.com/api/v1/json/3/eventspastleague.php",
            params={"id": tsdb_id}, timeout=15, proxies=NO_PROXY)
        if r.status_code != 200:
            return []
        ev = (r.json() or {}).get("events") or []
        out = []
        for e in ev[:limit]:
            h, a = e.get("strHomeTeam"), e.get("
