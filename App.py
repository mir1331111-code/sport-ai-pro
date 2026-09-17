"""NEURO BET PRO v11.4 — fixed dict check + animated loader + stadium cards."""
import streamlit as st
import csv, io, os, math, re, pickle, json, html, time, hashlib, gzip
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============= PROXY CLEANUP =============
for _k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
           "ALL_PROXY", "all_proxy", "FTP_PROXY", "ftp_proxy"]:
    os.environ.pop(_k, None)

import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
    _HAS_RETRY = True
except Exception:
    _HAS_RETRY = False

st.set_page_config(page_title="NEURO BET PRO v11.4", page_icon="🏟", layout="wide",
                   initial_sidebar_state="expanded")

APP_VERSION = "11.4"
HISTORY_FILE = "neuro_bet_pro.json"
DISK_CACHE_DIR = "neuro_cache"
os.makedirs(DISK_CACHE_DIR, exist_ok=True)

esc = html.escape
AVG_GOALS = 2.75
TOTAL_MIN = 95.0
MATRIX_N = 9

HYPERPARAMS = {
    "refit_temp_every": 150,
    "refit_struct_every": 300,
    "time_decay_tau_days": 180.0,
    "shr_bayes_k": 200.0,
    "max_league_exposure": 0.15,
    "max_market_exposure": 0.25,
    "max_day_exposure": 0.10,
    "max_match_exposure": 0.02,
    "max_match_bets": 2,
    "max_day_bets": 10,
}

DIV_TO_APILG = {
    "E0": 39, "E1": 40, "SP1": 140, "SP2": 141,
    "I1": 135, "I2": 136, "D1": 78, "D2": 79,
    "F1": 61, "F2": 62, "N1": 88, "B1": 144,
    "P1": 94, "T1": 203, "R1": 235, "G1": 197,
}

API_NAMES = {2: "🏆 ЛЧ", 3: "🏆 ЛЕ", 848: "🏆 ЛК", 235: "🇷🇺 РПЛ", 203: "🇹🇷 Суперлига"}

DIV_NAMES = {
    "E0": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 АПЛ", "E1": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Чемпионшип",
    "D1": "🇩🇪 Бундеслига", "D2": "🇩🇪 2.Бундеслига", "I1": "🇮🇹 Серия A",
    "I2": "🇮🇹 Серия B", "SP1": "🇪🇸 Ла Лига", "SP2": "🇪🇸 Сегунда",
    "F1": "🇫🇷 Лига 1", "F2": "🇫🇷 Лига 2", "N1": "🇳🇱 Эредивизи",
    "B1": "🇧🇪 Про-лига", "P1": "🇵🇹 Примейра", "T1": "🇹🇷 Суперлига",
    "G1": "🇬🇷 Греция", "R1": "🇷🇺 РПЛ",
}

GOALS = {
    "🎯 Проходимость": dict(w_market=0.65, thr=0.62, dis=False, edge=0.01, ev=0.01,
                            corr=(1.30, 2.30), min_games=10),
    "⚖️ Баланс":      dict(w_market=0.40, thr=0.55, dis=True, edge=0.02, ev=0.02,
                            corr=(1.40, 4.20), min_games=8),
    "💰 Value":       dict(w_market=0.20, thr=0.45, dis=True, edge=0.03, ev=0.02,
                            corr=(1.40, 4.20), min_games=6),
}

STADIUM_WALLS = {
    "E0":  "https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=1200",
    "SP1": "https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=1200",
    "I1":  "https://images.unsplash.com/photo-1518604666860-9ed391f76460?q=80&w=1200",
    "D1":  "https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=1200",
    "F1":  "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=1200",
    "R1":  "https://images.unsplash.com/photo-1551958219-acbc608c6377?q=80&w=1200",
    "DEFAULT": "https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=1200",
}

SORT_OPTIONS = ["По EV (валуи сверху)", "По вероятности", "По дате (ближайшие)",
                "По коэффициенту", "По лиге (А→Я)"]
SORT_DEFAULT_DESC = {"По EV (валуи сверху)": True, "По вероятности": True,
                     "По дате (ближайшие)": False, "По коэффициенту": True,
                     "По лиге (А→Я)": False}
CORRIDORS = {"OU": (1.50, 2.80), "AH": (1.60, 2.60), "STAT": (1.40, 4.50)}


def _get_secret(key, default=""):
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key, default)


CLOUD_API_FOOTBALL_KEY = _get_secret("API_FOOTBALL_KEY", "")
CLOUD_GIST_ID = _get_secret("GIST_ID", "")
CLOUD_GIST_TOKEN = _get_secret("GIST_TOKEN", "")
CLOUD_IS_CLOUD = bool(CLOUD_GIST_ID and CLOUD_GIST_TOKEN)

ERR = []


def log_err(tag, e):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}][{tag}] {type(e).__name__}: {str(e)[:200]}"
    ERR.append(line)
    if len(ERR) > 100:
        ERR.pop(0)


def _session():
    s = requests.Session()
    if _HAS_RETRY:
        r = Retry(total=4, connect=3, read=3, backoff_factor=1.5,
                  status_forcelist=[429, 500, 502, 503, 504, 520, 521, 522, 524],
                  allowed_methods=frozenset(["GET", "HEAD", "POST", "PATCH"]),
                  raise_on_status=False)
        adapter = HTTPAdapter(max_retries=r, pool_connections=20, pool_maxsize=20)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    })
    s.trust_env = False
    s.proxies = {"http": None, "https": None}
    return s


_sess = _session()
NO_PROXY = {"http": None, "https": None, "all": None}


def _disk_cache_path(key):
    h = hashlib.md5(key.encode("utf-8")).hexdigest()
    return os.path.join(DISK_CACHE_DIR, f"{h}.bin")


def disk_cache_get(key, max_age_sec):
    try:
        p = _disk_cache_path(key)
        if not os.path.exists(p):
            return None
        if time.time() - os.path.getmtime(p) > max_age_sec:
            return None
        with open(p, "rb") as f:
            raw = f.read()
        try:
            return pickle.loads(gzip.decompress(raw))
        except Exception:
            return pickle.loads(raw)
    except Exception:
        return None


def disk_cache_put(key, value):
    try:
        p = _disk_cache_path(key)
        tmp = p + ".tmp"
        with open(tmp, "wb") as f:
            f.write(gzip.compress(pickle.dumps(value)))
        os.replace(tmp, p)
    except Exception:
        pass


# ============= GIST =============
def _gist_load(gid, filename):
    if not gid or not CLOUD_GIST_TOKEN:
        return None
    try:
        headers = {"Authorization": f"token {CLOUD_GIST_TOKEN}",
                   "Accept": "application/vnd.github+json"}
        r = _sess.get(f"https://api.github.com/gists/{gid}",
                      headers=headers, timeout=15, proxies=NO_PROXY)
        if r.status_code != 200:
            return None
        files = r.json().get("files", {})
        if filename not in files:
            return None
        content = files[filename].get("content", "")
        return json.loads(content) if content else None
    except Exception as e:
        log_err("gist_load", e)
        return None


def _gist_save(gid, filename, data):
    if not gid or not CLOUD_GIST_TOKEN:
        return False
    try:
        def _d(o):
            if isinstance(o, datetime):
                return o.isoformat()
            raise TypeError("not serializable")
        content = json.dumps(data, ensure_ascii=False, default=_d, allow_nan=False)
        headers = {"Authorization": f"token {CLOUD_GIST_TOKEN}",
                   "Accept": "application/vnd.github+json"}
        body = {"files": {filename: {"content": content}}}
        r = _sess.patch(f"https://api.github.com/gists/{gid}",
                        headers=headers, json=body, timeout=20, proxies=NO_PROXY)
        return r.status_code in (200, 201)
    except Exception as e:
        log_err("gist_save", e)
        return False


# ============= HELPERS =============
def _new_team():
    return {"hs": [], "hc": [], "as": [], "ac": [], "form": [],
            "cfh": [], "cah": [], "cfa": [], "caa": [],
            "yfh": [], "yah": [], "yfa": [], "yaa": []}


def _new_lp():
    return {"w_shots": 0.35, "rho": -0.13, "w_dc": 0.72, "n_train": 0}


def _f(v):
    try:
        return float(v)
    except Exception:
        return None


def parse_date(s):
    if s is None:
        return None
    src = str(s).strip()
    if not src:
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            src_c = src[:19] if "%z" in fmt or "T" in fmt else src
            return datetime.strptime(src_c, fmt)
        except Exception:
            continue
    return None


def is_cup(row):
    if not isinstance(row, dict):
        return False
    dv = row.get("Div", "")
    lg = (row.get("League") or "").lower()
    return dv in ("C1", "EL", "EC") or any(x in lg for x in ["cup", "champions", "europa"])


def kelly(prob, odds, bank, frac):
    if prob <= 0 or odds <= 1:
        return 0.0
    b = odds - 1
    k = (b * prob - (1 - prob)) / b
    return round(min(max(0, k * frac), 0.05) * bank, 2)


def odd1(row, keys):
    if not isinstance(row, dict):
        return None
    for k in keys:
        v = _f(row.get(k))
        if v and v > 1.01:
            return v
    return None


ODD_KEYS = {
    "П1": ["MaxH", "B365H", "PSH", "PSCH"],
    "X": ["MaxD", "B365D", "PSD", "PSCD"],
    "П2": ["MaxA", "B365A", "PSA", "PSCA"],
    "ТБ 2.5": ["Max>2.5", "B365>2.5", "P>2.5"],
    "ТМ 2.5": ["Max<2.5", "B365<2.5", "P<2.5"],
}


def best_odd(row, pick):
    return odd1(row, ODD_KEYS.get(pick, []))


def determine_outcome(market, pick, hg, ag):
    m = (market or "").upper()
    p = (pick or "").strip()
    if m in ("", "HOT", "STAT"):
        if p in ("П1", "X", "П2"):
            m = "1X2"
        elif p in ("ТБ 2.5", "ТМ 2.5"):
            m = "OU"
        else:
            return None
    if m == "1X2":
        res = "П1" if hg > ag else ("X" if hg == ag else "П2")
        return "won" if res == p else "lost"
    if m == "OU":
        if p == "ТБ 2.5":
            return "won" if hg + ag >= 3 else "lost"
        if p == "ТМ 2.5":
            return "won" if hg + ag <= 2 else "lost"
    return None


# ============= API-FOOTBALL =============
def api_request(api_key, endpoint, params=None, timeout=15):
    if not api_key:
        return None, "no_key"
    headers = {"x-apisports-key": api_key, "x-rapidapi-host": "v3.football.api-sports.io"}
    url = f"https://v3.football.api-sports.io/{endpoint}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    try:
        r = _sess.get(url, headers=headers, timeout=timeout, proxies=NO_PROXY)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        data = r.json()
        if data.get("errors"):
            return None, str(data["errors"])[:120]
        return data, None
    except Exception as e:
        return None, f"{type(e).__name__}"


def api_season_history(api_key, div, season_year):
    if not api_key:
        return []
    lid = DIV_TO_APILG.get(div)
    if not lid:
        return []
    ck = f"api_hist_{div}_{season_year}"
    cached = disk_cache_get(ck, 86400 * 7)
    if cached is not None:
        return cached if isinstance(cached, list) else []
    data, err = api_request(api_key, "fixtures",
                            {"league": lid, "season": season_year, "status": "FT"},
                            timeout=25)
    if err:
        log_err(f"api_hist_{div}", err)
        return []
    out = []
    for f in (data or {}).get("response") or []:
        if not isinstance(f, dict):
            continue
        fix = f.get("fixture") or {}
        teams = f.get("teams") or {}
        goals = f.get("goals") or {}
        h = (teams.get("home") or {}).get("name")
        a = (teams.get("away") or {}).get("name")
        hg = goals.get("home")
        ag = goals.get("away")
        if not h or not a or hg is None or ag is None:
            continue
        out.append({"Div": div, "Date": (fix.get("date") or "")[:10],
                    "HomeTeam": h, "AwayTeam": a,
                    "FTHG": str(hg), "FTAG": str(ag)})
    disk_cache_put(ck, out)
    return out


def api_fixtures_by_league(api_key, d_from, d_to, progress_cb=None):
    """Fixtures по каждой лиге отдельно (API-Football Free требует league)."""
    if not api_key:
        return [], ["API: нет ключа"]
    out = []
    rep = []
    leagues = [(39, "АПЛ"), (140, "Ла Лига"), (135, "Серия A"),
               (78, "Бундеслига"), (61, "Лига 1"), (2, "ЛЧ"),
               (3, "ЛЕ"), (848, "ЛК"), (235, "РПЛ"), (203, "Суперлига")]
    total = len(leagues)
    for idx, (lid, name) in enumerate(leagues):
        if progress_cb:
            progress_cb(idx, total, name)
        ck = f"api_fx_{lid}_{d_from}_{d_to}"
        cached = disk_cache_get(ck, 900)
        if cached is not None and isinstance(cached, list):
            out += cached
            rep.append(f"API {name}: {len(cached)} (кэш)")
            continue
        data, err = api_request(api_key, "fixtures",
                                {"league": lid, "from": d_from, "to": d_to, "timezone": "UTC"})
        if err:
            rep.append(f"API {name}: {err[:50]}")
            disk_cache_put(ck, [])
            continue
        rows = []
        for f in (data or {}).get("response") or []:
            if not isinstance(f, dict):
                continue
            fix = f.get("fixture") or {}
            teams = f.get("teams") or {}
            lg = f.get("league") or {}
            dt = fix.get("date") or ""
            h = (teams.get("home") or {}).get("name")
            a = (teams.get("away") or {}).get("name")
            if not h or not a:
                continue
            rows.append({"Div": f"API_{lid}",
                         "League": lg.get("name") or name,
                         "Date": dt[:10], "Time": dt[11:16],
                         "HomeTeam": h, "AwayTeam": a,
                         "fixture_id": fix.get("id")})
        out += rows
        disk_cache_put(ck, rows)
        rep.append(f"API {name}: {len(rows)}")
    return out, rep


def api_live(api_key):
    if not api_key:
        return [], ["API live: нет ключа"]
    ck = "api_live_all"
    cached = disk_cache_get(ck, 300)
    if cached is not None:
        return cached[0], cached[1] + ["(кэш)"]
    data, err = api_request(api_key, "fixtures", {"live": "all"})
    if err:
        return [], [f"API live: {err}"]
    out = []
    for f in (data or {}).get("response") or []:
        if not isinstance(f, dict):
            continue
        fix = f.get("fixture") or {}
        teams = f.get("teams") or {}
        goals = f.get("goals") or {}
        lg = f.get("league") or {}
        out.append({"league": lg.get("name", "Матч"),
                    "fixture_id": fix.get("id"),
                    "home": (teams.get("home") or {}).get("name"),
                    "away": (teams.get("away") or {}).get("name"),
                    "home_score": goals.get("home") or 0,
                    "away_score": goals.get("away") or 0,
                    "minute": fix.get("status", {}).get("elapsed") or 0,
                    "source": "API"})
    disk_cache_put(ck, (out, [f"API live: {len(out)}"]))
    return out, [f"API live: {len(out)}"]


# ============= THESPORTSDB =============
def tsdb_day(dstr):
    ck = f"tsdb_day_{dstr}"
    cached = disk_cache_get(ck, 1800)
    if cached is not None:
        return cached if isinstance(cached, list) else []
    try:
        r = _sess.get(f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={dstr}&s=Soccer",
                      timeout=15, proxies=NO_PROXY)
        if r.status_code != 200:
            return []
        ev = (r.json() or {}).get("events") or []
        out = []
        for e in ev:
            if not isinstance(e, dict):
                continue
            h = e.get("strHomeTeam")
            a = e.get("strAwayTeam")
            if not h or not a:
                continue
            out.append({"Div": "TSDB", "League": e.get("strLeague") or "Матч",
                        "Date": (e.get("dateEvent") or "")[:10],
                        "Time": (e.get("strTime") or "")[:5],
                        "HomeTeam": h, "AwayTeam": a})
        disk_cache_put(ck, out)
        return out
    except Exception:
        return []


def tsdb_days_parallel(days_list):
    out = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(tsdb_day, d): d for d in days_list}
        for fut in as_completed(futs):
            try:
                result = fut.result()
                if isinstance(result, list):
                    out += result
            except Exception:
                pass
    return out


# ============= CALIBRATOR =============
class Calibrator:
    def __init__(self):
        self.platt_a = [1.0, 1.0, 1.0]
        self.platt_b = [0.0, 0.0, 0.0]
        self.method = "temperature"

    def fit(self, logits, outcomes):
        if len(logits) < 60:
            return
        try:
            lr = 0.01
            for c in range(3):
                zs = logits[c::3]
                ys = outcomes[c::3]
                if len(zs) < 20:
                    continue
                a, b = 1.0, 0.0
                for _ in range(300):
                    ga, gb = 0.0, 0.0
                    for z, y in zip(zs, ys):
                        p = 1 / (1 + math.exp(-max(-30, min(30, a * z + b))))
                        err = p - y
                        ga += err * z
                        gb += err
                    a -= lr * ga / max(1, len(zs))
                    b -= lr * gb / max(1, len(zs))
                self.platt_a[c], self.platt_b[c] = a, b
            self.method = "platt"
        except Exception:
            pass

    def calibrate(self, p, ci=0):
        p = min(max(p, 1e-6), 1 - 1e-6)
        if self.method == "platt":
            z = math.log(p / (1 - p))
            a = self.platt_a[ci]
            b = self.platt_b[ci]
            return 1 / (1 + math.exp(-max(-30, min(30, a * z + b))))
        return p


# ============= ENGINE =============
class Engine:
    def __init__(self):
        self.elo = {}
        self.st = defaultdict(_new_team)
        self.hg, self.ag = [], []
        self.h2h = defaultdict(list)
        self.calib_logits, self.calib_outcomes = [], []
        self.calibrator = Calibrator()
        self.lp = defaultdict(_new_lp)
        self.hist = defaultdict(list)
        self.match_count = 0
        self.last_match_date = {}

    @staticmethod
    def _logit(p):
        p = min(max(p, 1e-6), 1 - 1e-6)
        return math.log(p / (1 - p))

    def _m(self, l, d=1.0):
        return sum(l) / len(l) if l else d

    def _p(self, l, k):
        try:
            return math.exp(-l) * l ** k / math.factorial(k)
        except Exception:
            return 0.0

    def _form(self, t):
        f = self.st[t]["form"][-5:]
        return (sum(f) / (len(f) * 3)) if f else 0.5

    def form_str(self, t):
        out = ""
        for x in self.st[t]["form"][-5:]:
            out += {"3": "В", "1": "Н", "0": "П"}[str(int(x))]
        return out or "—"

    def calibrate(self, p, ci=0):
        return self.calibrator.calibrate(p, ci)

    def refit_calibrator(self):
        if len(self.calib_logits) < 60:
            return
        self.calibrator.fit(self.calib_logits[-3000:], self.calib_outcomes[-3000:])

    def _p1px(self, lh, la, rho):
        N = MATRIX_N
        M = [[self._p(lh, i) * self._p(la, j) for j in range(N)] for i in range(N)]
        tau = {(0, 0): 1 + lh * la * rho, (1, 0): 1 - la * rho,
               (0, 1): 1 - lh * rho, (1, 1): 1 + rho}
        for i in range(N):
            for j in range(N):
                if (i, j) in tau:
                    M[i][j] *= tau[(i, j)]
        tot = sum(map(sum, M)) or 1.0
        M = [[v / tot for v in r] for r in M]
        p1 = sum(M[i][j] for i in range(N) for j in range(N) if i > j)
        px = sum(M[i][i] for i in range(N))
        return p1, px, M

    def add(self, h, a, hg, ag, row=None, match_num=None, total=None, match_date=None):
        k = 16 + 32 * min(1.0, (match_num or 0) / max(1, total or 1))
        rh, ra = self.elo.get(h, 1500), self.elo.get(a, 1500)
        eh = 1 / (1 + 10 ** ((ra - (rh + 60)) / 400))
        s = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
        self.elo[h] = rh + k * (s - eh)
        self.elo[a] = ra + k * ((1 - s) - (1 - eh))
        t = self.st
        t[h]["hs"].append(hg)
        t[h]["hc"].append(ag)
        t[a]["as"].append(ag)
        t[a]["ac"].append(hg)
        t[h]["form"].append(3 if hg > ag else (1 if hg == ag else 0))
        t[a]["form"].append(3 if ag > hg else (1 if hg == ag else 0))
        self.hg.append(hg)
        self.ag.append(ag)
        self.h2h[(h, a)].append(hg - ag)
        self.h2h[(h, a)] = self.h2h[(h, a)][-8:]
        for team in (h, a):
            for key in t[team]:
                t[team][key] = t[team][key][-12:]
        if match_date:
            self.last_match_date[h] = match_date
            self.last_match_date[a] = match_date

    def h2h_adjust(self, h, a, lh, la):
        hist = self.h2h.get((h, a), [])
        n = len(hist)
        if n < 5:
            return lh, la, n
        shrink = min(1.0, (n - 4) / 6.0)
        shift = (sum(hist) / n) * 0.08 * shrink
        return max(0.3, lh + shift / 2), max(0.25, la - shift / 2), n

    def h2h_text(self, h, a):
        hist = self.h2h.get((h, a), [])[-5:]
        return ", ".join(f"{d:+.0f}" for d in hist) if hist else "нет данных"

    def predict(self, h, a, lg="G", match_date=None, cup=False):
        P0 = self.lp[lg]
        ws = P0["w_shots"]
        lh_g = max(0.05, self._m(self.hg, 1.5))
        la_g = max(0.05, self._m(self.ag, 1.2))
        sh, sa = self.st[h], self.st[a]
        ah_ = self._m(sh["hs"], lh_g) / lh_g
        dh_ = self._m(sh["hc"], la_g) / la_g
        aa_ = self._m(sa["as"], la_g) / la_g
        da_ = self._m(sa["ac"], lh_g) / lh_g
        fh, fa = self._form(h), self._form(a)
        lam_g_h = max(0.3, min(5.0, lh_g * ah_ * da_ * 1.10 * (0.85 + 0.30 * fh)))
        lam_g_a = max(0.25, min(4.5, la_g * aa_ * dh_ * 0.95 * (0.85 + 0.30 * fa)))
        lam_h = (1 - ws) * lam_g_h + ws * lam_g_h
        lam_a = (1 - ws) * lam_g_a + ws * lam_g_a
        if cup:
            lam_h = max(0.3, lam_h - 0.15)
            lam_a = max(0.25, lam_a - 0.15)
        lam_h, lam_a, h2h_n = self.h2h_adjust(h, a, lam_h, lam_a)
        agree = (lam_h - lam_a) * (lam_g_h - lam_g_a) > 0
        e = 1 / (1 + 10 ** ((self.elo.get(a, 1500) - self.elo.get(h, 1500) - 60) / 400))
        pde = 0.20 + 0.12 * (1 - abs(e - 0.5) * 2)
        p1, px, M = self._p1px(lam_h, lam_a, P0["rho"])
        f1 = P0["w_dc"] * p1 + (1 - P0["w_dc"]) * e * (1 - pde)
        fd = P0["w_dc"] * px + (1 - P0["w_dc"]) * pde
        f2 = max(0.0, 1 - f1 - fd)
        games = min(len(sh["hs"]) + len(sh["as"]), len(sa["hs"]) + len(sa["as"]))
        c1 = self.calibrate(f1, 0)
        cx = self.calibrate(fd, 1)
        c2 = self.calibrate(f2, 2)
        ct = c1 + cx + c2 or 1.0
        c1 /= ct
        cx /= ct
        c2 /= ct
        over = 1 - sum(self._p(lam_h + lam_a, k) for k in range(3))
        btts = sum(M[i][j] for i in range(1, MATRIX_N) for j in range(1, MATRIX_N))
        return {"p1": c1, "x": cx, "p2": c2, "p1_raw": f1, "x_raw": fd, "p2_raw": f2,
                "over": over, "btts": btts, "M": M, "agree": agree,
                "lams": (lam_h, lam_a), "lams_g": (lam_g_h, lam_g_a),
                "lams_s": (lam_g_h, lam_g_a), "games": games,
                "corners": (5.0, 5.0), "yellows": (2.0, 2.0),
                "h2h_n": h2h_n, "e": e, "pde": pde}

    def learn_step(self, h, a, hg, ag, row=None, lg="G", match_num=None, total=None, match_date=None):
        P = self.predict(h, a, lg, match_date=match_date, cup=is_cup(row))
        out = 0 if hg > ag else (1 if hg == ag else 2)
        self.calib_logits += [self._logit(P["p1_raw"]), self._logit(P["x_raw"]), self._logit(P["p2_raw"])]
        self.calib_outcomes += [1.0 if out == 0 else 0.0, 1.0 if out == 1 else 0.0, 1.0 if out == 2 else 0.0]
        if len(self.calib_logits) > 6000:
            del self.calib_logits[:-6000]
            del self.calib_outcomes[:-6000]
        self.match_count += 1
        if self.match_count % HYPERPARAMS["refit_temp_every"] == 0:
            self.refit_calibrator()
        self.hist[lg].append((P["lams_g"][0], P["lams_g"][1], P["lams_s"][0],
                              P["lams_s"][1], P["e"], P["pde"], out, 1.0))
        self.add(h, a, hg, ag, row, match_num=match_num, total=total, match_date=match_date)
        return P


# ============= CANDIDATES =============
def build_candidates(P, row, PR, blacklist=()):
    probs = {"П1": P["p1"], "X": P["x"], "П2": P["p2"], "ТБ 2.5": P["over"],
             "ТМ 2.5": 1 - P["over"], "BTTS да": P["btts"], "BTTS нет": 1 - P["btts"],
             "1X": P["p1"] + P["x"], "X2": P["x"] + P["p2"], "12": P["p1"] + P["p2"]}
    cands = []
    for pick, prob in probs.items():
        mkt = "1X2" if pick in ("П1", "X", "П2") else ("OU" if pick.startswith("Т") else "STAT")
        if mkt in blacklist:
            continue
        cands.append((mkt, pick, prob, best_odd(row, pick) if pick in ODD_KEYS else None))
    return cands


def evaluate_rows(cands, P, mkt_probs, PR, engine, use_dis=False, row=None):
    rows = []
    best = None
    hot = []
    for mkt, pick, prob, odd in cands:
        item = {"mkt": mkt, "pick": pick, "prob": prob, "odd": odd,
                "ev": None, "be": None, "ok": False}
        if odd:
            lo, hi = PR["corr"] if mkt == "1X2" else CORRIDORS.get(mkt, (1.4, 4.2))
            ev = prob * odd - 1
            be = 1 / odd
            edge = prob - be
            ok = (lo <= odd <= hi and edge >= PR["edge"] and ev >= PR["ev"]
                  and P["games"] >= PR["min_games"])
            item.update(ev=ev, be=be, ok=ok)
            if ok:
                stk = kelly(prob, odd, PR["bank"], PR["kelly"])
                if best is None or ev > best[3]:
                    best = (mkt, pick, odd, ev, prob, stk)
        if prob >= PR["thr"]:
            hot.append((pick, prob, odd))
        rows.append(item)
    hot.sort(key=lambda x: -x[1])
    return rows, best, hot, None, None


# ============= DATA =============
def new_data():
    return {"version": 10, "bank": 10000.0, "bets": [], "cards": [], "picks": [],
            "funnel": None, "report": [], "meta": {},
            "stats": {"won": 0, "lost": 0, "profit": 0, "push": 0},
            "mode": "paper"}


def migrate(D):
    if not isinstance(D, dict):
        return new_data()
    base = new_data()
    for k in base:
        if k not in D or D[k] is None:
            D[k] = json.loads(json.dumps(base[k]))
    for key in ("cards", "picks", "bets", "report"):
        if not isinstance(D.get(key), list):
            D[key] = []
    if not isinstance(D.get("stats"), dict):
        D["stats"] = base["stats"]
    for s in ("won", "lost", "profit", "push"):
        D["stats"].setdefault(s, 0)
    if not isinstance(D.get("meta"), dict):
        D["meta"] = {}
    return D


def load_data():
    if CLOUD_IS_CLOUD:
        gd = _gist_load(CLOUD_GIST_ID, HISTORY_FILE)
        if gd:
            return migrate(gd)
    return new_data()


def save_data(D):
    if CLOUD_IS_CLOUD:
        _gist_save(CLOUD_GIST_ID, HISTORY_FILE, D)


def clone(D):
    return json.loads(json.dumps(D, default=str))


def engine_cache_fp(season, div_counts):
    return (APP_VERSION, season, tuple(sorted(div_counts.items())))


def engine_cache_get(fp):
    try:
        key = "neuro_engine_" + hashlib.md5(str(fp).encode()).hexdigest()[:12]
        cached = disk_cache_get(key, 86400 * 14)
        if cached and cached.get("fp") == fp:
            return cached.get("engine")
    except Exception:
        pass
    return None


def engine_cache_put(fp, eng):
    try:
        key = "neuro_engine_" + hashlib.md5(str(fp).encode()).hexdigest()[:12]
        disk_cache_put(key, {"fp": fp, "engine": eng})
    except Exception:
        pass


def apply_settle(D, idx, outcome, score=None):
    D2 = clone(D)
    if idx < 0 or idx >= len(D2["bets"]):
        return D2
    b = D2["bets"][idx]
    if b["status"] != "pending":
        return D2
    if score:
        b["score"] = score
    if outcome == "won":
        pr = b["stake"] * (b["odds"] - 1)
        b["status"] = "won"
        D2["bank"] += b["stake"] * b["odds"]
        D2["stats"]["won"] += 1
        D2["stats"]["profit"] += pr
    elif outcome == "lost":
        b["status"] = "lost"
        D2["stats"]["lost"] += 1
        D2["stats"]["profit"] -= b["stake"]
    return D2


# ============= UI HELPERS =============
def _odd_s(rw):
    o = rw.get("odd")
    return f"{o:.2f}" if o else f"фейр {1 / max(rw.get('prob') or 0.01, 0.01):.2f}"


def ai_verdict(c):
    rows = c.get("rows", [])
    scored = sorted([r for r in rows if r.get("prob")], key=lambda r: -r["prob"])

    def prep(r):
        d = dict(r) if r else None
        if d:
            d["odd_s"] = _odd_s(d)
        return d

    main = prep(scored[0]) if scored else None
    alt = prep(scored[1]) if len(scored) > 1 else None
    lg = c.get("lams_g", (0, 0))
    lh, la = c.get("lams", (0, 0))
    parts = [f"xG {lg[0]:.2f}–{lg[1]:.2f}, итог {lh:.2f}–{la:.2f}."]
    if c.get("fh", "—") != "—":
        parts.append(f"Форма: {c['fh']} vs {c['fa']}.")
    if c.get("best"):
        parts.append(f"Вывод: {c['best'][1]} @ {c['best'][2]:.2f} (EV {c['best'][3] * 100:+.1f}%).")
    return main, alt, None, " ".join(parts)


def stars_for(rw, thr):
    if rw["ok"]:
        if rw["ev"] >= 0.10:
            return "⭐⭐⭐⭐⭐"
        if rw["ev"] >= 0.06:
            return "⭐⭐⭐⭐"
        return "⭐⭐⭐"
    if rw["prob"] >= thr:
        return "⭐⭐⭐⭐⭐" if rw["prob"] >= 0.70 else ("⭐⭐⭐⭐" if rw["prob"] >= 0.65 else "⭐⭐⭐")
    return ""


def build_picks(cards, thr, bank, kf):
    picks = []
    for c in cards:
        best = c.get("best")
        if not best:
            continue
        mkt, pick, odd, ev, prob, stk = best
        main, alt, avoid, text = ai_verdict(c)
        stake = kelly(prob, odd, bank, kf)
        picks.append({"league": c["league"], "match": c["match"], "date": c["date"],
                      "when": c["when"], "pick": pick, "prob": prob,
                      "odd": odd, "odd_s": f"{odd:.2f}", "stake": stake,
                      "stars": stars_for({"ok": True, "ev": ev, "prob": prob}, thr),
                      "type": "value", "verdict": text,
                      "main": main, "alt": alt, "avoid": avoid,
                      "ev": ev, "score": ev + prob})
    picks.sort(key=lambda p: p["score"], reverse=True)
    return picks[:10]


def card_sort_val(c, key):
    if key.startswith("По EV"):
        return c["best"][3] if c.get("best") else -1
    if key.startswith("По вероятности"):
        return max([r["prob"] for r in c["rows"]], default=0)
    if key.startswith("По дате"):
        return c.get("dt", "9999")
    if key.startswith("По коэффициенту"):
        return c["best"][2] if c.get("best") else 0
    return c.get("league", "")


def pick_sort_val(p, key):
    if key.startswith("По EV"):
        return p.get("ev") or -1
    if key.startswith("По вероятности"):
        return p.get("prob", 0)
    if key.startswith("По дате"):
        return p.get("dt", "9999")
    if key.startswith("По коэффициенту"):
        return p.get("odd") or 0
    return p.get("league", "")


def stadium_bg(div):
    return STADIUM_WALLS.get(div, STADIUM_WALLS["DEFAULT"])


def render_match_card(c, thr, PR):
    val = c.get("best") is not None
    badge = ("<span class='badge val'>🟢 ВАЛУЙ</span>" if val
             else "<span class='badge no'>фон</span>")
    chips = (f"<span class='chip'>{esc(c['league'])}</span>"
             f"<span class='chip when'>📅 {esc(c['date'])} · {esc(c['when'])}</span>")
    if c["games"] < PR["min_games"]:
        chips += "<span class='chip warn'>⚠️ мало данных</span>"
    main, alt, avoid, vtext = ai_verdict(c)
    m_s = (f"✅ <b>{esc(main['pick'])}</b> @ {main['odd_s']} (P {main['prob'] * 100:.0f}%)") if main else ""
    rows_html = ""
    for rw in c["rows"]:
        ev_s = (f"<span class='{'evpos' if rw['ev'] > 0 else 'evneg'}'>{rw['ev'] * 100:+.1f}%</span>"
                if rw["ev"] is not None else "<span style='color:#64748b'>—</span>")
        be_s = f"{rw['be'] * 100:.1f}%" if rw["be"] else "—"
        mk = ("<span class='ok'>✅</span>" if rw["ok"]
              else ("<span style='color:#fde047;font-weight:800'>🔥</span>"
                    if rw["prob"] >= thr else "<span class='nok'>·</span>"))
        odd_txt = f"{rw['odd']:.2f}" if rw["odd"] else "—"
        rows_html += (f"<div class='mrow'><span style='color:#8b93a7'>{rw['mkt']}</span>"
                      f"<b style='color:#fbbf24'>{esc(rw['pick'])}</b>"
                      f"<span style='color:#34d399;font-weight:700'>{rw['prob'] * 100:.1f}%</span>"
                      f"<span style='color:#f87171'>{be_s}</span>"
                      f"<span style='color:#fff;font-weight:700'>{odd_txt}</span>"
                      f"{ev_s}{mk}</div>")
    ch, ca = c["corners"]
    yh, ya = c["yellows"]
    h, a = c["match"].split(" vs ")
    bg = stadium_bg(c.get("div", ""))
    return f"""
<div class="mcard {'value' if val else ''}" style="background-image:linear-gradient(rgba(10,14,24,.80),rgba(10,14,24,.92)),url('{bg}');background-size:cover;background-position:center;">
 <div>{chips}{badge}</div>
 <div class="teams">{esc(h)} <span>—</span> {esc(a)}</div>
 <div class="verdict">🤖 {m_s}<br>
  <span style="color:#c9d2e3">{esc(vtext)}</span></div>
 {rows_html}
 <div class="mfoot"><span>xG: <b>{c['lams'][0]:.2f}–{c['lams'][1]:.2f}</b></span>
  <span>🚩 угл <b>{ch + ca:.1f}</b></span><span>🟨 жёл <b>{yh + ya:.1f}</b></span>
  <span>📚 игр <b>{c['games']}</b></span></div>
</div>"""


def bet_card_html(b):
    st_ = b.get("status", "pending")
    icon = {"pending": "⏳", "won": "🟢", "lost": "🔴"}.get(st_, "⏳")
    score = f"<span class='score'>{esc(b['score'])}</span>" if b.get("score") else ""
    return (f"<div class='betcard {st_}'>{icon} <b>{esc(b['match'])}</b>{score}<br>"
            f"<b style='color:#fbbf24'>{esc(b['pick'])}</b> @ {b['odds']:.2f} · "
            f"{b['stake']:.2f} у.е.</div>")


# ============= CSS =============
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@600;800&family=Inter:wght@400;600;800&display=swap');
html,body,#root,.stApp,.stApp>div,
[data-testid="stAppViewContainer"],[data-testid="stAppViewContainer"]>div,
[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stBottom"],[data-testid="stBottom"]>div,
[data-testid="stAppViewBlockContainer"],[data-testid="stVerticalBlock"],
section.main,section.main>div,.main,.main>div,.block-container{
background-color:#05070f!important;
background-image:linear-gradient(180deg,#05070f 0%,#0b0f1a 50%,#05070f 100%)!important;
background-attachment:fixed!important;}
[data-testid="stHeader"],[data-testid="stToolbar"]{background:transparent!important;}
.stMarkdown,.stMarkdown p,.stMarkdown li{color:#e6eaf2;font-family:'Inter',sans-serif;}
header,#MainMenu{visibility:hidden}
section[data-testid="stSidebar"]{background:rgba(8,11,20,.85)!important;backdrop-filter:blur(18px);border-right:1px solid rgba(255,255,255,.07);}
section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] label,section[data-testid="stSidebar"] span{color:#e6eaf2!important;}
section.stButton>button{background:linear-gradient(135deg,#0ea5e9,#8b5cf6,#ec4899);color:#fff;border:none;border-radius:14px;font-weight:800;padding:10px 20px;transition:all .25s ease;}
section.stButton>button:hover{transform:translateY(-2px) scale(1.02);box-shadow:0 12px 40px rgba(139,92,246,.5);}
.hero{padding:26px 30px;border-radius:26px;margin-bottom:18px;border:1px solid rgba(255,255,255,.10);background:linear-gradient(130deg,rgba(14,165,233,.20),rgba(139,92,246,.16),rgba(236,72,153,.14));}
.hero h1{margin:0;font-size:2.5rem;font-weight:800;background:linear-gradient(92deg,#22d3ee,#a78bfa 50%,#f472b6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-size:200% 200%;animation:shine 6s ease infinite;}
@keyframes shine{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:16px;}
.kpi{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.10);border-radius:18px;padding:14px 16px;}
.kpi .t{color:#7dd3fc;font-size:.66rem;text-transform:uppercase;font-weight:700;letter-spacing:1.2px;}
.kpi .v{font-size:1.5rem;font-weight:800;color:#fff;}
.kpi .v.g{color:#34d399;}.kpi .v.y{color:#fbbf24;}.kpi .v.r{color:#f87171;}
.mcard{background:rgba(10,14,24,.72);border:1px solid rgba(255,255,255,.09);border-radius:20px;padding:20px 22px;margin-bottom:14px;transition:all .3s ease;}
.mcard:hover{transform:translateY(-2px);box-shadow:0 20px 60px rgba(0,0,0,.5);}
.mcard.value{border-color:rgba(52,211,153,.55);}
.chip{background:rgba(34,211,238,.14);color:#a5f3fc;border:1px solid rgba(34,211,238,.35);padding:3px 11px;border-radius:999px;font-size:.72rem;font-weight:700;margin-right:6px;}
.chip.when{background:rgba(251,191,36,.14);color:#fde68a;border-color:rgba(251,191,36,.4);}
.chip.warn{background:rgba(248,113,113,.15);color:#fecaca;}
.badge{float:right;padding:4px 13px;border-radius:999px;font-size:.72rem;font-weight:800;}
.badge.val{background:rgba(52,211,153,.25);color:#6ee7b7;border:1px solid rgba(52,211,153,.6);}
.badge.no{background:rgba(148,163,184,.12);color:#cbd5e1;border:1px solid rgba(148,163,184,.3);}
.teams{font-size:1.4rem;font-weight:800;color:#fff;margin:12px 0 6px;text-shadow:0 2px 8px rgba(0,0,0,.8);}
.teams span{color:#8b93a7;font-weight:400;}
.verdict{background:rgba(34,211,238,.08);border:1px solid rgba(34,211,238,.22);border-radius:14px;padding:12px 16px;margin:10px 0;color:#e6eaf2;font-size:.9rem;}
.mrow{display:grid;grid-template-columns:70px 96px 70px 70px 62px 74px 26px;gap:8px;padding:7px 0;border-top:1px solid rgba(255,255,255,.07);font-size:.83rem;color:#e2e8f0;}
.ok{color:#34d399;font-weight:800;}.nok{color:#64748b;}
.evpos{color:#34d399;font-weight:700;}.evneg{color:#f87171;font-weight:700;}
.mfoot{margin-top:12px;color:#c9d2e3;font-size:.78rem;display:flex;gap:16px;flex-wrap:wrap;}
.mfoot b{color:#fbbf24;}
.betcard{background:rgba(10,14,24,.72);border:1px solid rgba(255,255,255,.09);border-left:4px solid rgba(148,163,184,.4);border-radius:16px;padding:12px 16px;margin-bottom:9px;font-size:.87rem;color:#e6eaf2;}
.betcard.pending{border-left-color:#fbbf24;}
.betcard.won{border-left-color:#34d399;}
.betcard.lost{border-left-color:#f87171;}
.betcard .score{font-weight:900;padding:2px 10px;border-radius:9px;margin-left:6px;background:rgba(52,211,153,.25);color:#6ee7b7;}
.nbr-loader{display:flex;align-items:center;gap:14px;padding:20px;background:rgba(10,14,24,.72);border:1px solid rgba(34,211,238,.35);border-radius:16px;margin-bottom:14px;}
.nbr-ring{width:38px;height:38px;border-radius:50%;border:3px solid rgba(34,211,238,.2);border-top-color:#22d3ee;animation:nbr-spin 1s linear infinite;flex-shrink:0;}
@keyframes nbr-spin{to{transform:rotate(360deg);}}
.nbr-text{flex:1;color:#a5f3fc;font-family:'Inter',sans-serif;font-size:.95rem;}
.nbr-text b{color:#fff;}
.nbr-dots::after{content:'';animation:nbr-dots 1.4s steps(4,end) infinite;}
@keyframes nbr-dots{0%{content:'';}25%{content:'.';}50%{content:'..';}75%{content:'...';}}
.nbr-bar{height:6px;background:rgba(255,255,255,.08);border-radius:3px;overflow:hidden;margin-top:8px;}
.nbr-bar-fill{height:100%;background:linear-gradient(90deg,#22d3ee,#a78bfa,#f472b6);background-size:200% 100%;animation:nbr-bar-move 2s linear infinite;border-radius:3px;transition:width .4s ease;}
@keyframes nbr-bar-move{0%{background-position:0% 0%;}100%{background-position:200% 0%;}}
</style>""", unsafe_allow_html=True)


# ============= UI =============
if "data" not in st.session_state:
    st.session_state.data = load_data()
D = st.session_state.data
if "meta" not in D:
    D["meta"] = {}
if CLOUD_API_FOOTBALL_KEY and not D["meta"].get("api_key"):
    D["meta"]["api_key"] = CLOUD_API_FOOTBALL_KEY

st.markdown(f"""
<div class="hero">
 <h1>NEURO BET PRO</h1>
 <p>v{APP_VERSION} · {'☁️ CLOUD' if CLOUD_IS_CLOUD else '💾 LOCAL'} · 🏟 Stadium · 🎬 Animated loader</p>
 <div class="kpis">
  <div class="kpi"><div class="t">Банкролл</div><div class="v y">{D['bank']:.0f} у.е.</div></div>
  <div class="kpi"><div class="t">В работе</div><div class="v">{sum(1 for b in D['bets'] if b['status'] == 'pending')}</div></div>
  <div class="kpi"><div class="t">Прибыль</div><div class="v {'g' if D['stats']['profit'] >= 0 else 'r'}">{D['stats']['profit']:+.0f}</div></div>
  <div class="kpi"><div class="t">Ошибок</div><div class="v {'r' if ERR else 'g'}">{len(ERR)}</div></div>
 </div>
</div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Настройки")
    if CLOUD_IS_CLOUD:
        st.success("☁️ Cloud mode", icon="✅")
    else:
        st.warning("💾 Local mode", icon="⚠️")
    st.markdown("**🔑 Ключи**")
    ak = st.text_input("API-Football", value=D.get("meta", {}).get("api_key", ""), type="password")
    if ak != D.get("meta", {}).get("api_key", ""):
        D["meta"]["api_key"] = ak
        save_data(D)

    goal = st.selectbox("🎯 Цель", list(GOALS.keys()), index=0)
    PR0 = GOALS[goal]
    kelly_frac = st.slider("Келли", 0.10, 0.40, 0.25, 0.05)
    thr = st.slider("Порог", 30, 90, int(PR0["thr"] * 100)) / 100
    min_edge = st.slider("Edge", 0, 8, int(PR0["edge"] * 100)) / 100
    min_ev = st.slider("EV", 0, 10, int(PR0["ev"] * 100)) / 100

    with st.expander(f"🐞 Ошибки ({len(ERR)})"):
        for line in ERR[-20:]:
            st.text(line)
    if st.button("🧹 Очистить лог"):
        ERR.clear()
        st.rerun()
    if st.button("🔄 Сброс данных"):
        st.session_state.data = new_data()
        save_data(st.session_state.data)
        st.rerun()

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["🏟 Сканер", "💼 Портфель", "📈 Статистика", "🧮 Калькулятор", "🔴 Онлайн"])

with tab1:
    c1, c2 = st.columns([4, 1])
    days = c1.slider("Горизонт, дней", 1, 21, 7)
    scan = c2.button("⚡ СКАН", type="primary")

    if scan:
        ak_ = D.get("meta", {}).get("api_key", "")
        if not ak_:
            st.error("❌ Нужен API-Football ключ")
        else:
            loader_ph = st.empty()
            log_ph = st.empty()

            def update_loader(text, pct, logs=None):
                loader_ph.markdown(f"""
<div class="nbr-loader">
 <div class="nbr-ring"></div>
 <div class="nbr-text">
   <b>{text}</b><span class="nbr-dots"></span>
   <div class="nbr-bar"><div class="nbr-bar-fill" style="width:{pct * 100:.0f}%"></div></div>
 </div>
</div>""", unsafe_allow_html=True)
                if logs:
                    log_ph.markdown(
                        f"<div style='color:#8b93a7;font-family:Inter,sans-serif;"
                        f"font-size:.8rem;background:rgba(10,14,24,.6);padding:12px;"
                        f"border-radius:10px;max-height:200px;overflow-y:auto'>"
                        + "<br>".join(logs[-10:]) + "</div>",
                        unsafe_allow_html=True)

            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            limit = today + timedelta(days=days)
            d_from = today.strftime("%Y-%m-%d")
            d_to = limit.strftime("%Y-%m-%d")
            logs = []

            # ФИКС: двойная защита от не-словарей
            def safe_filter(rows):
                out = []
                if not isinstance(rows, list):
                    return out
                for r in rows:
                    if not isinstance(r, dict):
                        continue
                    if not r.get("HomeTeam") or not r.get("AwayTeam"):
                        continue
                    out.append(r)
                return out

            def fixture_progress(idx, total, name):
                update_loader(f"Сбор матчей [{idx + 1}/{total}] — {name}",
                              (idx + 1) / total * 0.3, logs)

            update_loader("Запуск сканирования...", 0.0, logs)
            api_rows_raw, api_rep = api_fixtures_by_league(ak_, d_from, d_to, fixture_progress)
            api_rows = safe_filter(api_rows_raw)
            for line in api_rep:
                logs.append(f"📡 {line}")
            update_loader("Fixtures собраны", 0.3, logs)

            day_list = [(today + timedelta(days=off)).strftime("%Y-%m-%d") for off in range(0, min(days, 7))]
            tsdb_rows_raw = tsdb_days_parallel(day_list)
            tsdb_rows = safe_filter(tsdb_rows_raw)
            logs.append(f"📡 TSDB-day: {len(tsdb_rows)}")
            update_loader("Дополнительные источники", 0.4, logs)

            seen = set()
            src_rows = []
            for r in (api_rows + tsdb_rows):
                if not isinstance(r, dict):
                    continue
                h = r.get("HomeTeam")
                a = r.get("AwayTeam")
                if not h or not a:
                    continue
                k = (h, a, r.get("Date"))
                if k in seen:
                    continue
                seen.add(k)
                src_rows.append(r)
            logs.append(f"🔗 Уникальных: {len(src_rows)}")

            train_divs = ["E0", "SP1", "I1", "D1", "F1", "E1", "SP2", "I2", "D2", "F2", "N1", "B1", "P1", "T1", "R1"]
            cur_year = today.year if today.month >= 7 else today.year - 1
            prev_year = cur_year - 1

            dp, dc = {}, {}
            for i, dv in enumerate(train_divs):
                pct = 0.4 + (i + 1) / len(train_divs) * 0.3
                update_loader(f"История [{i + 1}/{len(train_divs)}] — {DIV_NAMES.get(dv, dv)}", pct, logs)
                dp[dv] = api_season_history(ak_, dv, prev_year)
                dc[dv] = api_season_history(ak_, dv, cur_year)
                n = len(dp[dv]) + len(dc[dv])
                logs.append(f"✅ {DIV_NAMES.get(dv, dv)}: {n} матчей")

            div_counts = {dv: len(dp.get(dv, [])) + len(dc.get(dv, [])) for dv in train_divs}
            fp = engine_cache_fp(f"{cur_year}", div_counts)
            engine = engine_cache_get(fp)
            trained = 0
            if engine is None:
                engine = Engine()
                total_matches = sum(div_counts.values())
                processed = 0
                for dv in train_divs:
                    for src in (dp.get(dv, []), dc.get(dv, [])):
                        for r in src:
                            try:
                                engine.learn_step(r["HomeTeam"], r["AwayTeam"],
                                                  float(r["FTHG"]), float(r["FTAG"]), r,
                                                  lg=dv, match_num=processed,
                                                  total=total_matches,
                                                  match_date=parse_date(r.get("Date", "")))
                                trained += 1
                            except Exception as e:
                                log_err(f"train {dv}", e)
                            processed += 1
                            if processed % 50 == 0:
                                pct = 0.7 + processed / max(1, total_matches) * 0.25
                                update_loader(f"Обучение [{processed}/{total_matches}]", pct, logs)
                engine_cache_put(fp, engine)
                logs.append(f"🧠 Обучено: {trained}")

            update_loader("Поиск валуев...", 0.97, logs)
            PR = dict(PR0)
            PR.update(thr=thr, edge=min_edge, ev=min_ev, bank=D["bank"], kelly=kelly_frac)

            cands_all = []
            for r in src_rows:
                d = parse_date(r.get("Date", ""))
                if not d or not (today <= d <= limit):
                    continue
                h = (r.get("HomeTeam") or "").strip()
                a = (r.get("AwayTeam") or "").strip()
                if not h or not a:
                    continue
                lg = r.get("Div", "G")
                P = engine.predict(h, a, lg, match_date=d, cup=is_cup(r))
                cc = build_candidates(P, r, PR)
                rows, best, hot, _, _ = evaluate_rows(cc, P, None, PR, engine, False, row=r)
                cands_all.append({"r": r, "d": d, "h": h, "a": a, "lg": lg,
                                  "league": r.get("League") or DIV_NAMES.get(lg, "Лига"),
                                  "P": P, "rows": rows, "best": best})

            new_bets = []
            existing = {b["match"] + "|" + b["pick"] for b in D["bets"]}
            for cand in cands_all:
                b = cand["best"]
                if not b:
                    continue
                mkt, pick, odd, ev, prob, _ = b
                stake = kelly(prob, odd, D["bank"], kelly_frac)
                if stake <= 0:
                    continue
                key = f"{cand['h']} vs {cand['a']}|{pick}"
                if key in existing:
                    continue
                tm = (cand["r"].get("Time") or "").strip()
                dt_full = (cand["d"].strftime("%Y-%m-%d %H:%M") if tm else cand["d"].strftime("%Y-%m-%d"))
                new_bets.append({"match": f"{cand['h']} vs {cand['a']}", "div": cand["lg"],
                                 "league": cand["league"], "market": mkt, "pick": pick,
                                 "odds": odd, "stake": stake, "prob": prob,
                                 "status": "pending", "strat": "VALUE", "tier": 1,
                                 "mode": D.get("mode", "paper"),
                                 "date": cand["d"].strftime("%d.%m.%Y"),
                                 "date_iso": cand["d"].strftime("%Y-%m-%d"),
                                 "date_time": dt_full, "score": None})
                existing.add(key)

            cards = []
            for cand in cands_all:
                P = cand["P"]
                cards.append({"div": cand["lg"], "league": cand["league"],
                              "match": f"{cand['h']} vs {cand['a']}",
                              "date": cand["d"].strftime("%d.%m") + (f" {cand['r'].get('Time', '')}" if cand["r"].get("Time") else ""),
                              "when": "сегодня" if cand["d"].date() == today.date() else "скоро",
                              "dt": cand["d"].strftime("%Y-%m-%d %H:%M"),
                              "rows": cand["rows"], "best": cand["best"],
                              "lams": P["lams"], "lams_g": P["lams_g"],
                              "lams_s": P["lams_s"], "games": P["games"],
                              "corners": P["corners"], "yellows": P["yellows"],
                              "fh": engine.form_str(cand["h"]),
                              "fa": engine.form_str(cand["a"]),
                              "cup": is_cup(cand["r"])})
            picks = build_picks(cards, thr, D["bank"], kelly_frac)
            D2 = clone(D)
            D2["cards"] = cards
            D2["picks"] = picks
            D2["report"] = api_rep + [f"TSDB: {len(tsdb_rows)}"]
            D2["bets"] = D2["bets"] + new_bets
            D2["funnel"] = {"trained": trained, "src": len(src_rows), "added": len(new_bets)}
            st.session_state.data = D2
            save_data(D2)

            update_loader("✅ Готово!", 1.0, logs)
            time.sleep(1.0)
            loader_ph.empty()
            log_ph.empty()
            st.rerun()

    fn = D.get("funnel")
    if fn:
        st.caption(f"Обучено {fn.get('trained', 0)} · источников {fn.get('src', 0)} · +{fn.get('added', 0)}")
    with st.expander("🔌 Диагностика"):
        for line in D.get("report", []):
            st.text(line)

    sort_key = st.selectbox("Сортировка", SORT_OPTIONS, index=0, key="sort_key")
    picks = D.get("picks", [])
    if picks:
        st.markdown("### 🎯 НА ЧТО СТАВИТЬ")
        pv = sorted(picks, key=lambda p: pick_sort_val(p, sort_key), reverse=True)
        for i, p in enumerate(pv, 1):
            m = p["main"]
            m_s = f"✅ <b>{esc(m['pick'])}</b> @ {m['odd_s']}" if m else ""
            st.markdown(f"""<div class='mcard value'>
<span class='chip'>{esc(p['league'])}</span>
<span class='badge val'>{p['stars']}</span>
<div class='teams'>{i}. {esc(p['match'])}</div>
<div class='verdict'>🤖 {m_s}<br>➤ <b>{esc(p['pick'])}</b> @ <b>{p['odd_s']}</b> · P {p['prob'] * 100:.0f}% · сумма <b>{p['stake']:.2f} у.е.</b></div>
</div>""", unsafe_allow_html=True)

    cards_view = sorted(D.get("cards", []), key=lambda c: card_sort_val(c, sort_key), reverse=True)
    shown = 0
    for c in cards_view:
        st.markdown(render_match_card(c, thr, PR0), unsafe_allow_html=True)
        shown += 1
    if not shown and not picks:
        st.info("Нажми ⚡ СКАН.")

with tab2:
    st.header("💼 Портфель")
    if not D["bets"]:
        st.info("Пусто.")
    for i, b in enumerate(D["bets"]):
        st.markdown(bet_card_html(b), unsafe_allow_html=True)
        if b["status"] == "pending":
            cc = st.columns([1, 1, 1])
            sin = cc[0].text_input("Счёт", key=f"sc{i}", label_visibility="collapsed", placeholder="2:1")
            sc = sin.strip() if re.match(r"^\d+\s*:\s*\d+$", sin.strip()) else None
            if cc[1].button("✅", key=f"w{i}"):
                st.session_state.data = apply_settle(D, i, "won", score=sc)
                save_data(st.session_state.data)
                st.rerun()
            if cc[2].button("❌", key=f"l{i}"):
                st.session_state.data = apply_settle(D, i, "lost", score=sc)
                save_data(st.session_state.data)
                st.rerun()

with tab3:
    st.header("📈 Статистика")
    s = D["stats"]
    tot = s["won"] + s["lost"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Банк", f"{D['bank']:.2f}")
    m2.metric("Ставок", tot)
    m3.metric("WinRate", f"{(s['won'] / tot * 100) if tot else 0:.1f}%")
    m4.metric("Profit", f"{s['profit']:+.2f}")

with tab4:
    st.header("🧮 EV-калькулятор")
    q1, q2, q3 = st.columns(3)
    p = q1.number_input("P, %", 1, 99, 60)
    o = q2.number_input("Кэф", 1.01, 30.0, 1.80)
    bk = q3.number_input("Банк", 100.0, 1e6, float(D["bank"]))
    ev = (p / 100) * o - 1
    st.markdown(f"**EV:** {ev * 100:+.1f}% · **Келли:** {kelly(p / 100, o, bk, kelly_frac):.2f}")

with tab5:
    st.header("🔴 Онлайн")
    api_key = D.get("meta", {}).get("api_key", "")
    api_lives, api_rep = (api_live(api_key) if api_key else ([], ["Нет ключа"]))
    for line in api_rep:
        st.text(line)
    for m in api_lives:
        st.markdown(f"""<div class='mcard'>
<span class='chip'>🔴 {m.get('minute', 0)}'</span>
<span class='chip'>{esc(str(m.get('league', '')))}</span>
<div class='teams'>{esc(str(m.get('home', '')))} <span>{m.get('home_score', 0)}:{m.get('away_score', 0)}</span> {esc(str(m.get('away', '')))}</div>
</div>""", unsafe_allow_html=True)
    if not api_lives:
        st.info("Живых матчей нет.")
