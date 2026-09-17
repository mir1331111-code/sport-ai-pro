"""NEURO BET PRO v12.1 — throttle auto-settle + fp-checked engine + full settle."""
import streamlit as st
import csv, io, os, math, re, pickle, json, html, time, hashlib, gzip, base64
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

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

st.set_page_config(page_title="NEURO BET PRO v12.1", page_icon="🏟", layout="wide",
                   initial_sidebar_state="expanded")

APP_VERSION = "12.1"
DATA_VERSION = 14
HISTORY_FILE = "neuro_bet_pro.json"
ENGINE_GIST_FILE = "engine.b64"
API_USAGE_FILE = "api_usage.json"
SETTLE_USAGE_FILE = "settle_usage.json"
DISK_CACHE_DIR = "neuro_cache"
os.makedirs(DISK_CACHE_DIR, exist_ok=True)

esc = html.escape
MATRIX_N = 9
API_LIMIT_DAILY = 100
AUTO_SETTLE_LIMIT = 20
AUTO_SETTLE_THROTTLE_SEC = 1800

DIV_TO_APILG = {
    "E0": 39, "E1": 40, "SP1": 140, "SP2": 141,
    "I1": 135, "I2": 136, "D1": 78, "D2": 79,
    "F1": 61, "F2": 62, "N1": 88, "B1": 144,
    "P1": 94, "T1": 203, "R1": 235, "G1": 197,
}

DIV_NAMES = {
    "E0": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 АПЛ", "E1": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Чемпионшип",
    "D1": "🇩🇪 Бундеслига", "D2": "🇩🇪 2.Бундеслига", "I1": "🇮🇹 Серия A",
    "I2": "🇮🇹 Серия B", "SP1": "🇪🇸 Ла Лига", "SP2": "🇪🇸 Сегунда",
    "F1": "🇫🇷 Лига 1", "F2": "🇫🇷 Лига 2", "N1": "🇳🇱 Эредивизи",
    "B1": "🇧🇪 Про-лига", "P1": "🇵🇹 Примейра", "T1": "🇹🇷 Суперлига",
    "G1": "🇬🇷 Греция", "R1": "🇷🇺 РПЛ",
}

STADIUM_WALLS = {
    "E0": "https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=1200",
    "E1": "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?q=80&w=1200",
    "SP1": "https://images.unsplash.com/photo-1551958219-acbc608c6377?q=80&w=1200",
    "SP2": "https://images.unsplash.com/photo-1574629810360-716ae0165608?q=80&w=1200",
    "I1": "https://images.unsplash.com/photo-1518604666860-9ed391f76460?q=80&w=1200",
    "I2": "https://images.unsplash.com/photo-1489944440615-453fc2b6a9a9?q=80&w=1200",
    "D1": "https://images.unsplash.com/photo-1599394022918-6c2776530abb?q=80&w=1200",
    "D2": "https://images.unsplash.com/photo-1517466787929-bc90951d0974?q=80&w=1200",
    "F1": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=1200",
    "F2": "https://images.unsplash.com/photo-1431324155629-1a6deb1dec8d?q=80&w=1200",
    "N1": "https://images.unsplash.com/photo-1587329310686-91414b8e3cb7?q=80&w=1200",
    "B1": "https://images.unsplash.com/photo-1556056504-5c7697c04123?q=80&w=1200",
    "P1": "https://images.unsplash.com/photo-1577223625816-7546f13df25d?q=80&w=1200",
    "T1": "https://images.unsplash.com/photo-1529909968552-3a578e7f7fba?q=80&w=1200",
    "G1": "https://images.unsplash.com/photo-1523739194632-4c3241bfc8e1?q=80&w=1200",
    "R1": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?q=80&w=1200",
    "DEFAULT": "https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=1200",
}


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
        r = Retry(total=3, connect=3, read=3, backoff_factor=1.5,
                  status_forcelist=[429, 500, 502, 503, 504, 520, 521, 522, 524],
                  allowed_methods=frozenset(["GET", "HEAD", "POST", "PATCH"]),
                  raise_on_status=False)
        adapter = HTTPAdapter(max_retries=r, pool_connections=20, pool_maxsize=20)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
    s.headers.update({"User-Agent": "Mozilla/5.0 Chrome/120.0"})
    s.trust_env = False
    s.proxies = {"http": None, "https": None}
    return s


_sess = _session()
NO_PROXY = {"http": None, "https": None, "all": None}


def _disk_cache_path(key):
    return os.path.join(DISK_CACHE_DIR, f"{hashlib.md5(key.encode()).hexdigest()}.bin")


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


def _gist_load_raw(gid, filename):
    if not gid or not CLOUD_GIST_TOKEN:
        return None
    try:
        headers = {"Authorization": f"token {CLOUD_GIST_TOKEN}",
                   "Accept": "application/vnd.github+json"}
        r = _sess.get(f"https://api.github.com/gists/{gid}",
                      headers=headers, timeout=20, proxies=NO_PROXY)
        if r.status_code != 200:
            return None
        files = r.json().get("files", {})
        if filename not in files:
            return None
        return files[filename].get("content", "")
    except Exception as e:
        log_err("gist_load_raw", e)
        return None


def _gist_save_raw(gid, filename, content):
    if not gid or not CLOUD_GIST_TOKEN:
        return False
    try:
        headers = {"Authorization": f"token {CLOUD_GIST_TOKEN}",
                   "Accept": "application/vnd.github+json"}
        body = {"files": {filename: {"content": content}}}
        r = _sess.patch(f"https://api.github.com/gists/{gid}",
                        headers=headers, json=body, timeout=25, proxies=NO_PROXY)
        return r.status_code in (200, 201)
    except Exception as e:
        log_err("gist_save_raw", e)
        return False


def gist_load_json(gid, filename):
    content = _gist_load_raw(gid, filename)
    if not content:
        return None
    try:
        return json.loads(content)
    except Exception:
        return None


def gist_save_json(gid, filename, data):
    try:
        def _d(o):
            if isinstance(o, datetime):
                return o.isoformat()
            raise TypeError("not serializable")
        content = json.dumps(data, ensure_ascii=False, default=_d, allow_nan=False)
        return _gist_save_raw(gid, filename, content)
    except Exception as e:
        log_err("gist_save_json", e)
        return False


def engine_save_gist(fp, engine):
    if not CLOUD_IS_CLOUD:
        return False
    try:
        blob = base64.b64encode(gzip.compress(pickle.dumps({
            "fp": fp, "engine": engine,
            "version": APP_VERSION,
            "ts": datetime.now().isoformat(),
        }))).decode()
        if len(blob) > 900000:
            log_err("engine_save_gist", f"engine too big: {len(blob)} bytes")
            return False
        return _gist_save_raw(CLOUD_GIST_ID, ENGINE_GIST_FILE, blob)
    except Exception as e:
        log_err("engine_save_gist", e)
        return False


def engine_load_gist(fp):
    if not CLOUD_IS_CLOUD:
        return None
    try:
        blob = _gist_load_raw(CLOUD_GIST_ID, ENGINE_GIST_FILE)
        if not blob:
            return None
        data = pickle.loads(gzip.decompress(base64.b64decode(blob)))
        if not isinstance(data, dict):
            return None
        saved_fp = data.get("fp")
        if saved_fp != fp:
            log_err("engine_load_gist",
                    f"fp mismatch: saved={saved_fp} requested={fp}")
            return None
        return data.get("engine")
    except Exception as e:
        log_err("engine_load_gist", e)
        return None


def engine_clear_gist():
    if not CLOUD_IS_CLOUD:
        return False
    return _gist_save_raw(CLOUD_GIST_ID, ENGINE_GIST_FILE, "")


def _today_str():
    return datetime.now().strftime("%Y-%m-%d")


def _usage_load(filename):
    default = {"date": _today_str(), "count": 0}
    if CLOUD_IS_CLOUD:
        d = gist_load_json(CLOUD_GIST_ID, filename)
        if d and isinstance(d, dict):
            if d.get("date") != _today_str():
                return default
            return d
    return default


def _usage_increment(filename, n=1):
    d = _usage_load(filename)
    d["count"] = int(d.get("count", 0)) + n
    if CLOUD_IS_CLOUD:
        gist_save_json(CLOUD_GIST_ID, filename, d)
    return d


def _usage_remaining(filename, limit):
    d = _usage_load(filename)
    return max(0, limit - int(d.get("count", 0)))


def _usage_reset(filename):
    d = {"date": _today_str(), "count": 0}
    if CLOUD_IS_CLOUD:
        gist_save_json(CLOUD_GIST_ID, filename, d)
    return d


def api_usage_load():
    return _usage_load(API_USAGE_FILE)


def api_usage_increment(n=1):
    return _usage_increment(API_USAGE_FILE, n)


def api_usage_remaining():
    return _usage_remaining(API_USAGE_FILE, API_LIMIT_DAILY)


def api_usage_reset():
    return _usage_reset(API_USAGE_FILE)


def settle_usage_load():
    return _usage_load(SETTLE_USAGE_FILE)


def settle_usage_increment(n=1):
    return _usage_increment(SETTLE_USAGE_FILE, n)


def settle_usage_remaining():
    return _usage_remaining(SETTLE_USAGE_FILE, AUTO_SETTLE_LIMIT)


def settle_usage_reset():
    return _usage_reset(SETTLE_USAGE_FILE)


def _new_team():
    return {"hs": [], "hc": [], "as": [], "ac": [], "form": []}


def _new_lp():
    return {"rho": -0.13, "w_dc": 0.72}


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
    return row.get("Div", "") in ("C1", "EL", "EC")


def kelly(prob, odds, bank, frac):
    if prob <= 0 or odds <= 1:
        return 0.0
    b = odds - 1
    k = (b * prob - (1 - prob)) / b
    return round(min(max(0, k * frac), 0.05) * bank, 2)


def settle_ah(pick, hg, ag):
    m = re.match(r"Ф([12])\(([-+]?\d+(?:\.\d+)?)\)", pick or "")
    if not m:
        return None
    side, line = int(m.group(1)), float(m.group(2))
    res = ((hg - ag) if side == 1 else (ag - hg)) + line
    if res > 0.001:
        return True
    if abs(res) <= 0.001:
        return "push"
    return False


def determine_outcome(market, pick, hg, ag):
    m = (market or "").upper()
    p = (pick or "").strip()
    if m in ("", "HOT", "STAT"):
        if p in ("П1", "X", "П2"):
            m = "1X2"
        elif p in ("ТБ 2.5", "ТМ 2.5"):
            m = "OU"
        elif p.startswith("Ф"):
            m = "AH"
        elif p.startswith("BTTS"):
            m = "BTTS"
        elif p in ("1X", "X2", "12"):
            m = "DC"
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
    if m == "AH":
        s = settle_ah(p, hg, ag)
        if s is None:
            return None
        return "push" if s == "push" else ("won" if s else "lost")
    if m == "BTTS":
        both = (hg > 0 and ag > 0)
        return "won" if (both == (p == "BTTS да")) else "lost"
    if m == "DC":
        if p == "1X":
            ok = hg >= ag
        elif p == "X2":
            ok = hg <= ag
        elif p == "12":
            ok = hg != ag
        else:
            return None
        return "won" if ok else "lost"
    return None


def api_request(api_key, endpoint, params=None, timeout=15, count_usage=True):
    if not api_key:
        return None, "no_key"
    if count_usage and api_usage_remaining() <= 0:
        return None, "limit_reached"
    headers = {"x-apisports-key": api_key, "x-rapidapi-host": "v3.football.api-sports.io"}
    url = f"https://v3.football.api-sports.io/{endpoint}"
    if params:
        url = f"{url}?" + "&".join(f"{k}={v}" for k, v in params.items())
    try:
        r = _sess.get(url, headers=headers, timeout=timeout, proxies=NO_PROXY)
        if count_usage:
            api_usage_increment(1)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        data = r.json()
        if data.get("errors"):
            return None, str(data["errors"])[:120]
        return data, None
    except Exception as e:
        return None, f"{type(e).__name__}"


def _validate_matches(raw_list):
    out = []
    seen = set()
    for f in raw_list:
        if not isinstance(f, dict):
            continue
        fix = f.get("fixture") or {}
        teams = f.get("teams") or {}
        goals = f.get("goals") or {}
        status = (fix.get("status") or {}).get("short", "")
        if status not in ("FT", "AET", "PEN"):
            continue
        h = (teams.get("home") or {}).get("name")
        a = (teams.get("away") or {}).get("name")
        hg = goals.get("home")
        ag = goals.get("away")
        if not h or not a or hg is None or ag is None:
            continue
        try:
            hg_i, ag_i = int(hg), int(ag)
        except Exception:
            continue
        if hg_i < 0 or ag_i < 0 or hg_i > 20 or ag_i > 20:
            continue
        date = (fix.get("date") or "")[:10]
        key = (h, a, date)
        if key in seen:
            continue
        seen.add(key)
        out.append({"Div": None, "Date": date, "HomeTeam": h, "AwayTeam": a,
                    "FTHG": str(hg_i), "FTAG": str(ag_i)})
    return out


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
    out = _validate_matches((data or {}).get("response") or [])
    for r in out:
        r["Div"] = div
    disk_cache_put(ck, out)
    return out


def api_fixtures_by_league(api_key, d_from, d_to, progress_cb=None):
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
        if api_usage_remaining() <= 0:
            rep.append(f"API {name}: лимит")
            continue
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


def api_fixture_result(api_key, fixture_id):
    if not api_key or not fixture_id:
        return None
    ck = f"api_result_{fixture_id}"
    cached = disk_cache_get(ck, 86400)
    if cached is not None:
        return cached
    data, err = api_request(api_key, "fixtures", {"id": fixture_id}, timeout=10)
    if err:
        return None
    resp = (data or {}).get("response") or []
    if not resp:
        return None
    f = resp[0]
    fix = f.get("fixture") or {}
    status = (fix.get("status") or {}).get("short", "")
    if status not in ("FT", "AET", "PEN"):
        return None
    goals = f.get("goals") or {}
    hg = goals.get("home")
    ag = goals.get("away")
    if hg is None or ag is None:
        return None
    result = {"home": int(hg), "away": int(ag)}
    disk_cache_put(ck, result)
    return result


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


class Engine:
    def __init__(self):
        self.elo = {}
        self.st = defaultdict(_new_team)
        self.hg, self.ag = [], []
        self.h2h = defaultdict(list)
        self.calib_logits, self.calib_outcomes = [], []
        self.calibrator = Calibrator()
        self.lp = defaultdict(_new_lp)
        self.match_count = 0
        self.last_match_date = {}
        self.trained_n = 0

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

    def predict(self, h, a, lg="G", match_date=None, cup=False):
        P0 = self.lp[lg]
        lh_g = max(0.05, self._m(self.hg, 1.5))
        la_g = max(0.05, self._m(self.ag, 1.2))
        sh, sa = self.st[h], self.st[a]
        ah_ = self._m(sh["hs"], lh_g) / lh_g
        dh_ = self._m(sh["hc"], la_g) / la_g
        aa_ = self._m(sa["as"], la_g) / la_g
        da_ = self._m(sa["ac"], lh_g) / lh_g
        fh, fa = self._form(h), self._form(a)
        lam_h = max(0.3, min(5.0, lh_g * ah_ * da_ * 1.10 * (0.85 + 0.30 * fh)))
        lam_a = max(0.25, min(4.5, la_g * aa_ * dh_ * 0.95 * (0.85 + 0.30 * fa)))
        if cup:
            lam_h = max(0.3, lam_h - 0.15)
            lam_a = max(0.25, lam_a - 0.15)
        lam_h, lam_a, h2h_n = self.h2h_adjust(h, a, lam_h, lam_a)
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
                "over": over, "btts": btts, "M": M, "agree": True,
                "lams": (lam_h, lam_a), "lams_g": (lam_h, lam_a),
                "lams_s": (lam_h, lam_a), "games": games,
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
        if self.match_count % 150 == 0:
            self.refit_calibrator()
        self.add(h, a, hg, ag, row, match_num=match_num, total=total, match_date=match_date)
        return P


def build_verdict(P, thr, bank, kelly_frac, h_name, a_name, fh, fa, h2h_n):
    probs = {
        "П1": P["p1"], "X": P["x"], "П2": P["p2"],
        "ТБ 2.5": P["over"], "ТМ 2.5": 1 - P["over"],
        "BTTS да": P["btts"], "BTTS нет": 1 - P["btts"],
    }
    pick_names = {
        "П1": f"Победа {h_name}", "X": "Ничья", "П2": f"Победа {a_name}",
        "ТБ 2.5": "Тотал Больше 2.5", "ТМ 2.5": "Тотал Меньше 2.5",
        "BTTS да": "Обе забьют — Да", "BTTS нет": "Обе забьют — Нет",
    }
    rows = []
    for pick, prob in probs.items():
        prob = float(prob or 0.0)
        prob = min(max(prob, 0.01), 0.99)
        fair_odd = 1.0 / prob
        est_odd = fair_odd * 0.94
        rows.append({"pick": pick, "label": pick_names[pick], "prob": prob,
                     "odd": est_odd, "fair_odd": fair_odd})
    rows.sort(key=lambda r: -r["prob"])
    top = rows[0]
    second = rows[1] if len(rows) > 1 else None

    reasons = []
    lh, la = P["lams"]
    total_goals = lh + la
    reasons.append(f"Модель ожидает {total_goals:.2f} голов за матч (xG {lh:.2f}–{la:.2f})")

    if P["p1"] > 0.45:
        reasons.append(f"{h_name} имеет преимущество дома — форма: {fh}")
    elif P["p2"] > 0.45:
        reasons.append(f"{a_name} сильнее на выезде — форма: {fa}")
    else:
        reasons.append(f"Команды близки по силе — форма: {fh} vs {fa}")

    if total_goals > 3.0:
        reasons.append("Ожидается результативный матч — ТБ 2.5 фаворит")
    elif total_goals < 2.3:
        reasons.append("Ожидается низовой матч — ТМ 2.5 фаворит")

    if h2h_n >= 5:
        reasons.append(f"Учтены последние {h2h_n} личных встреч")

    if top["prob"] >= 0.80:
        confidence = "очень высокая"
        conf_color = "#34d399"
    elif top["prob"] >= 0.72:
        confidence = "высокая"
        conf_color = "#34d399"
    elif top["prob"] >= 0.65:
        confidence = "хорошая"
        conf_color = "#fbbf24"
    elif top["prob"] >= 0.55:
        confidence = "средняя"
        conf_color = "#fbbf24"
    else:
        confidence = "низкая"
        conf_color = "#f87171"

    verdict = {
        "pick": top["pick"], "label": top["label"], "prob": top["prob"],
        "odd": top["odd"], "fair_odd": top["fair_odd"],
        "confidence": confidence, "conf_color": conf_color,
        "reasons": reasons, "top2": rows[:2],
        "is_action": top["prob"] >= thr, "second": second,
    }
    best = None
    if top["prob"] >= thr:
        stake = kelly(top["prob"], top["odd"], bank, kelly_frac)
        best = ("STAT", top["pick"], top["odd"],
                top["prob"] * top["odd"] - 1, top["prob"], stake)
    return verdict, rows, best


def new_data():
    return {"version": DATA_VERSION, "bank": 10000.0, "bets": [], "cards": [],
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
    for key in ("cards", "bets", "report"):
        if not isinstance(D.get(key), list):
            D[key] = []
    D["cards"] = [c for c in D["cards"]
                  if isinstance(c, dict) and isinstance(c.get("verdict"), dict)]
    if not isinstance(D.get("stats"), dict):
        D["stats"] = base["stats"]
    for s in ("won", "lost", "profit", "push"):
        D["stats"].setdefault(s, 0)
    if not isinstance(D.get("meta"), dict):
        D["meta"] = {}
    D["version"] = DATA_VERSION
    return D


def load_data():
    if CLOUD_IS_CLOUD:
        gd = gist_load_json(CLOUD_GIST_ID, HISTORY_FILE)
        if gd:
            return migrate(gd)
    return new_data()


def save_data(D):
    if CLOUD_IS_CLOUD:
        gist_save_json(CLOUD_GIST_ID, HISTORY_FILE, D)


def clone(D):
    return json.loads(json.dumps(D, default=str))


def engine_cache_fp(season, div_counts):
    return (APP_VERSION, season, tuple(sorted(div_counts.items())))


def engine_cache_get(fp):
    eng = engine_load_gist(fp)
    if eng:
        return eng
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
    engine_save_gist(fp, eng)


def cancel_bet(D, idx):
    D2 = clone(D)
    if idx < 0 or idx >= len(D2["bets"]):
        return D2
    b = D2["bets"][idx]
    if b.get("status") != "pending":
        return D2
    stake = float(b.get("stake") or 0.0)
    D2["bank"] = D2["bank"] + stake
    D2["bets"].pop(idx)
    return D2


def apply_settle(D, idx, outcome, score=None):
    D2 = clone(D)
    if idx < 0 or idx >= len(D2["bets"]):
        return D2
    b = D2["bets"][idx]
    if b["status"] != "pending":
        return D2
    if score:
        b["score"] = score
    if outcome == "push":
        b["status"] = "push"
        D2["bank"] += b["stake"]
        D2["stats"]["push"] = D2["stats"].get("push", 0) + 1
    elif outcome == "won":
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


def auto_settle(D):
    api_key = D.get("meta", {}).get("api_key", "")
    if not api_key:
        return D, 0
    if settle_usage_remaining() <= 0:
        return D, 0
    D2 = clone(D)
    changed = 0
    now = datetime.now()
    for idx, b in enumerate(D2["bets"][:]):
        if settle_usage_remaining() <= 0:
            break
        if b.get("status") != "pending":
            continue
        fid = b.get("fixture_id")
        if not fid:
            continue
        dt_iso = b.get("date_iso") or b.get("date")
        bd = parse_date(dt_iso) if dt_iso else None
        if bd and bd > now:
            continue
        ck = f"api_result_{fid}"
        cached = disk_cache_get(ck, 3600)
        if cached:
            res = cached
        else:
            res = api_fixture_result(api_key, fid)
            settle_usage_increment(1)
        if not res:
            continue
        hg, ag = res["home"], res["away"]
        outcome = determine_outcome(b.get("market"), b.get("pick"), hg, ag)
        if outcome:
            D2 = apply_settle(D2, idx, outcome, score=f"{hg}:{ag}")
            changed += 1
    return D2, changed


def stadium_bg(div):
    return STADIUM_WALLS.get(div, STADIUM_WALLS["DEFAULT"])


def render_verdict_card(c, thr):
    v = c.get("verdict") or {}
    if not v:
        return ""
    pick = v.get("label", "—")
    prob = v.get("prob", 0)
    odd = v.get("odd", 1)
    conf = v.get("confidence", "средняя")
    conf_color = v.get("conf_color", "#fbbf24")
    reasons = v.get("reasons", [])
    is_action = v.get("is_action", False)
    top2 = v.get("top2", [])

    match_str = c.get("match", "— vs —")
    parts = match_str.split(" vs ")
    h = parts[0] if len(parts) > 0 else "—"
    a = parts[1] if len(parts) > 1 else "—"
    bg = stadium_bg(c.get("div", ""))

    if is_action:
        main_bg = "linear-gradient(135deg,rgba(52,211,153,.25),rgba(16,185,129,.10))"
        main_border = "rgba(52,211,153,.7)"
        main_title = f"🎯 СТАВЬ: {pick}"
    else:
        main_bg = "linear-gradient(135deg,rgba(148,163,184,.15),rgba(100,116,139,.08))"
        main_border = "rgba(148,163,184,.4)"
        main_title = f"👀 ФОН: {pick}"

    fh = c.get("fh", "—")
    fa = c.get("fa", "—")

    top2_html = ""
    for i, t in enumerate(top2):
        icon = "🥇" if i == 0 else "🥈"
        t_prob = t.get("prob", 0)
        t_odd = t.get("odd", 1)
        t_label = t.get("label", "—")
        top2_html += (
            f"<div style='display:flex;justify-content:space-between;padding:6px 0;"
            f"border-top:1px solid rgba(255,255,255,.06);font-size:.85rem;'>"
            f"<span>{icon} {esc(t_label)}</span>"
            f"<span><b style='color:#34d399'>{t_prob * 100:.1f}%</b> "
            f"<span style='color:#8b93a7'>· кэф ~{t_odd:.2f}</span></span>"
            f"</div>"
        )

    reasons_html = "".join(f"<li>{esc(r)}</li>" for r in reasons)

    return f"""
<div class="vcard" style="background-image:linear-gradient(rgba(10,14,24,.85),rgba(10,14,24,.95)),url('{bg}');background-size:cover;background-position:center;border:1px solid rgba(255,255,255,.10);border-radius:20px;padding:0;margin-bottom:14px;overflow:hidden;">
  <div style="padding:16px 20px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <div>
        <span style="background:rgba(34,211,238,.14);color:#a5f3fc;padding:3px 10px;border-radius:999px;font-size:.7rem;font-weight:700;">{esc(c.get('league','—'))}</span>
        <span style="background:rgba(251,191,36,.14);color:#fde68a;padding:3px 10px;border-radius:999px;font-size:.7rem;font-weight:700;margin-left:6px;">{esc(c.get('date','—'))}</span>
      </div>
      <div style="font-size:.75rem;color:#8b93a7;">📚 {c.get('games', 0)} игр</div>
    </div>
    <div style="font-size:1.4rem;font-weight:800;color:#fff;margin-bottom:6px;text-shadow:0 2px 8px rgba(0,0,0,.8);">
      {esc(h)} <span style="color:#8b93a7;font-weight:400;">—</span> {esc(a)}
    </div>
    <div style="font-size:.78rem;color:#8b93a7;margin-bottom:14px;">
      Форма: <b style="color:#34d399;">{esc(fh)}</b> · <b style="color:#f87171;">{esc(fa)}</b>
    </div>
  </div>

  <div style="background:{main_bg};border-top:1px solid {main_border};border-bottom:1px solid {main_border};padding:14px 20px;">
    <div style="font-size:1.15rem;font-weight:900;color:#fff;margin-bottom:8px;">{esc(main_title)}</div>
    <div style="display:flex;gap:20px;font-size:.9rem;color:#e6eaf2;">
      <div>Вероятность: <b style="color:#34d399;font-size:1.1rem;">{prob * 100:.0f}%</b></div>
      <div>Кэф фейр: <b style="color:#a5f3fc;font-size:1.1rem;">{odd:.2f}</b></div>
      <div>Уверенность: <b style="color:{conf_color};">{esc(conf)}</b></div>
    </div>
  </div>

  <div style="padding:14px 20px;">
    <div style="color:#7dd3fc;font-size:.72rem;text-transform:uppercase;font-weight:700;margin-bottom:8px;letter-spacing:1px;">Почему</div>
    <ul style="margin:0 0 14px 0;padding-left:18px;color:#c9d2e3;font-size:.85rem;line-height:1.6;">
      {reasons_html}
    </ul>

    <div style="color:#7dd3fc;font-size:.72rem;text-transform:uppercase;font-weight:700;margin-bottom:6px;letter-spacing:1px;">Топ-2 исхода</div>
    {top2_html}
  </div>
</div>"""


st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
html,body,#root,.stApp,.stApp>div,
[data-testid="stAppViewContainer"],[data-testid="stAppViewContainer"]>div,
[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stBottom"],[data-testid="stBottom"]>div,
[data-testid="stAppViewBlockContainer"],[data-testid="stVerticalBlock"],
section.main,section.main>div,.main,.main>div,.block-container{
background-color:#05070f!important;
background-image:linear-gradient(180deg,#05070f 0%,#0b0f1a 50%,#05070f 100%)!important;}
[data-testid="stHeader"],[data-testid="stToolbar"]{background:transparent!important;}
.stMarkdown,.stMarkdown p,.stMarkdown li{color:#e6eaf2;}
header,#MainMenu{visibility:hidden}
section[data-testid="stSidebar"]{background:rgba(8,11,20,.85)!important;border-right:1px solid rgba(255,255,255,.07);}
section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] label,section[data-testid="stSidebar"] span{color:#e6eaf2!important;}
section.stButton>button{background:linear-gradient(135deg,#0ea5e9,#8b5cf6,#ec4899);color:#fff;border:none;border-radius:14px;font-weight:800;}
.hero{padding:24px 28px;border-radius:22px;margin-bottom:16px;border:1px solid rgba(255,255,255,.10);background:linear-gradient(130deg,rgba(14,165,233,.20),rgba(139,92,246,.16),rgba(236,72,153,.14));}
.hero h1{margin:0;font-size:2.2rem;font-weight:800;background:linear-gradient(92deg,#22d3ee,#a78bfa,#f472b6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:14px;}
.kpi{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.10);border-radius:16px;padding:12px 14px;}
.kpi .t{color:#7dd3fc;font-size:.65rem;text-transform:uppercase;font-weight:700;}
.kpi .v{font-size:1.4rem;font-weight:800;color:#fff;}
.kpi .v.g{color:#34d399;}.kpi .v.y{color:#fbbf24;}.kpi .v.r{color:#f87171;}
.betcard{background:rgba(10,14,24,.72);border:1px solid rgba(255,255,255,.09);border-left:4px solid rgba(148,163,184,.4);border-radius:14px;padding:12px 16px;margin-bottom:8px;font-size:.87rem;color:#e6eaf2;}
.betcard.pending{border-left-color:#fbbf24;}
.betcard.won{border-left-color:#34d399;}
.betcard.lost{border-left-color:#f87171;}
.betcard.push{border-left-color:#94a3b8;}
.betcard .score{font-weight:900;padding:2px 10px;border-radius:9px;margin-left:6px;background:rgba(52,211,153,.25);color:#6ee7b7;}
.nbr-loader{display:flex;align-items:center;gap:14px;padding:18px;background:rgba(10,14,24,.72);border:1px solid rgba(34,211,238,.35);border-radius:16px;margin-bottom:12px;}
.nbr-ring{width:36px;height:36px;border-radius:50%;border:3px solid rgba(34,211,238,.2);border-top-color:#22d3ee;animation:nbr-spin 1s linear infinite;flex-shrink:0;}
@keyframes nbr-spin{to{transform:rotate(360deg);}}
.nbr-text{flex:1;color:#a5f3fc;font-size:.95rem;}
.nbr-text b{color:#fff;}
.nbr-dots::after{content:'';animation:nbr-dots 1.4s steps(4,end) infinite;}
@keyframes nbr-dots{0%{content:'';}25%{content:'.';}50%{content:'..';}75%{content:'...';}}
.nbr-bar{height:6px;background:rgba(255,255,255,.08);border-radius:3px;overflow:hidden;margin-top:8px;}
.nbr-bar-fill{height:100%;background:linear-gradient(90deg,#22d3ee,#a78bfa,#f472b6);background-size:200% 100%;animation:nbr-bar-move 2s linear infinite;border-radius:3px;transition:width .4s ease;}
@keyframes nbr-bar-move{0%{background-position:0% 0%;}100%{background-position:200% 0%;}}
</style>""", unsafe_allow_html=True)


if "data" not in st.session_state:
    st.session_state.data = load_data()
D = st.session_state.data
if "meta" not in D:
    D["meta"] = {}
if CLOUD_API_FOOTBALL_KEY and not D["meta"].get("api_key"):
    D["meta"]["api_key"] = CLOUD_API_FOOTBALL_KEY

# [v12.1] THROTTLE для auto_settle — раз в 30 минут
_now_ts = time.time()
_last_auto_ts = st.session_state.get("_last_auto_settle_ts", 0)
if _now_ts - _last_auto_ts > AUTO_SETTLE_THROTTLE_SEC:
    D2, n = auto_settle(D)
    if n > 0:
        st.session_state.data = D2
        save_data(D2)
        D = D2
        st.toast(f"Авто-закрыто {n} ставок", icon="🔄")
    st.session_state["_last_auto_settle_ts"] = _now_ts

pending_count = sum(1 for b in D["bets"] if isinstance(b, dict) and b.get("status") == "pending")

st.markdown(f"""
<div class="hero">
 <h1>NEURO BET PRO</h1>
 <p>v{APP_VERSION} · 🤖 AI-вердикт с объяснением · 🛡 fp-checked engine · ⏱ throttle auto-settle</p>
 <div class="kpis">
  <div class="kpi"><div class="t">Банкролл</div><div class="v y">{D['bank']:.0f} у.е.</div></div>
  <div class="kpi"><div class="t">В работе</div><div class="v">{pending_count}</div></div>
  <div class="kpi"><div class="t">Всего ставок</div><div class="v">{len(D['bets'])}</div></div>
  <div class="kpi"><div class="t">Ошибок</div><div class="v {'r' if ERR else 'g'}">{len(ERR)}</div></div>
 </div>
</div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Настройки")

    usage = api_usage_load()
    used = int(usage.get("count", 0))
    remaining = max(0, API_LIMIT_DAILY - used)
    st.markdown(f"""
<div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.10);border-radius:12px;padding:10px 14px;margin-bottom:10px;">
<div style="color:#7dd3fc;font-size:.7rem;text-transform:uppercase;font-weight:700;">API-Football</div>
<div style="font-size:1.3rem;font-weight:800;color:{'#34d399' if remaining > 30 else ('#fbbf24' if remaining > 10 else '#f87171')};">{remaining} / {API_LIMIT_DAILY}</div>
<div style="color:#8b93a7;font-size:.75rem;">осталось запросов сегодня</div>
</div>""", unsafe_allow_html=True)

    settle_used = int(settle_usage_load().get("count", 0))
    settle_remaining = max(0, AUTO_SETTLE_LIMIT - settle_used)
    st.markdown(f"""
<div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.10);border-radius:12px;padding:10px 14px;margin-bottom:10px;">
<div style="color:#7dd3fc;font-size:.7rem;text-transform:uppercase;font-weight:700;">Auto-settle</div>
<div style="font-size:1.3rem;font-weight:800;color:{'#34d399' if settle_remaining > 10 else ('#fbbf24' if settle_remaining > 3 else '#f87171')};">{settle_remaining} / {AUTO_SETTLE_LIMIT}</div>
<div style="color:#8b93a7;font-size:.75rem;">авто-проверок ставок сегодня</div>
</div>""", unsafe_allow_html=True)

    if st.button("♻️ Сбросить счётчики"):
        api_usage_reset()
        settle_usage_reset()
        st.toast("Счётчики сброшены", icon="♻️")
        st.rerun()

    if CLOUD_IS_CLOUD:
        st.success("☁️ Cloud mode", icon="✅")
    else:
        st.warning("💾 Local mode", icon="⚠️")

    st.markdown("**🔑 Ключи**")
    ak = st.text_input("API-Football", value=D.get("meta", {}).get("api_key", ""), type="password")
    if ak != D.get("meta", {}).get("api_key", ""):
        D["meta"]["api_key"] = ak
        save_data(D)

    st.markdown("**🎯 Минимальная вероятность**")
    min_prob = st.slider("", 50, 85, 60, 1, label_visibility="collapsed") / 100
    st.caption(f"Порог: **{min_prob * 100:.0f}%** — зеленым будут только матчи с этой P")

    kelly_frac = st.slider("Келли (доля)", 0.10, 0.40, 0.25, 0.05)

    if st.button("🧠 Force retrain", help="Стереть engine и обучить заново"):
        engine_clear_gist()
        try:
            for f in os.listdir(DISK_CACHE_DIR):
                if f.startswith("neuro_engine_"):
                    os.remove(os.path.join(DISK_CACHE_DIR, f))
        except Exception:
            pass
        st.toast("Engine будет переобучен при следующем СКАНе", icon="🧠")
        st.rerun()

    with st.expander(f"🐞 Ошибки ({len(ERR)})"):
        for line in ERR[-15:]:
            st.text(line)
    if st.button("🧹 Очистить лог"):
        ERR.clear()
        st.rerun()

    if "confirm_clear" not in st.session_state:
        st.session_state.confirm_clear = False
    if not st.session_state.confirm_clear:
        if st.button("🗑 Очистить портфель"):
            st.session_state.confirm_clear = True
            st.rerun()
    else:
        st.warning("⚠️ Удалить ВСЕ ставки и сбросить банк?")
        cc1, cc2 = st.columns(2)
        if cc1.button("✅ Да", key="confirm_yes"):
            D["bets"] = []
            D["cards"] = []
            D["bank"] = 10000.0
            D["stats"] = {"won": 0, "lost": 0, "profit": 0, "push": 0}
            save_data(D)
            st.session_state.confirm_clear = False
            st.rerun()
        if cc2.button("❌ Нет", key="confirm_no"):
            st.session_state.confirm_clear = False
            st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(
    ["🏟 Сканер", "💼 Портфель", "📈 Статистика", "🧮 Калькулятор"])

with tab1:
    c1, c2 = st.columns([4, 1])
    days = c1.slider("Горизонт, дней", 1, 21, 7)
    scan_disabled = st.session_state.get("_scan_in_progress", False)
    scan = c2.button("⚡ СКАН", type="primary", disabled=scan_disabled)

    if scan:
        st.session_state["_scan_in_progress"] = True
        try:
            ak_ = D.get("meta", {}).get("api_key", "")
            if not ak_:
                st.error("❌ Нужен API-Football ключ")
            elif api_usage_remaining() <= 5:
                st.error(f"⚠️ Осталось {api_usage_remaining()} запросов API.")
            else:
                loader_ph = st.empty()
                log_ph = st.empty()

                def update_loader(text, pct, logs=None):
                    loader_ph.markdown(f"""
<div class="nbr-loader">
 <div class="nbr-ring"></div>
 <div class="nbr-text"><b>{text}</b><span class="nbr-dots"></span>
   <div class="nbr-bar"><div class="nbr-bar-fill" style="width:{pct * 100:.0f}%"></div></div>
 </div>
</div>""", unsafe_allow_html=True)
                    if logs:
                        log_ph.markdown(
                            f"<div style='color:#8b93a7;font-size:.8rem;background:rgba(10,14,24,.6);padding:10px;border-radius:10px;max-height:180px;overflow-y:auto'>"
                            + "<br>".join(logs[-10:]) + "</div>",
                            unsafe_allow_html=True)

                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                limit = today + timedelta(days=days)
                d_from = today.strftime("%Y-%m-%d")
                d_to = limit.strftime("%Y-%m-%d")
                logs = []

                def safe_filter(rows):
                    if not isinstance(rows, list):
                        return []
                    return [r for r in rows if isinstance(r, dict) and r.get("HomeTeam") and r.get("AwayTeam")]

                def fixture_progress(idx, total, name):
                    update_loader(f"Сбор матчей [{idx + 1}/{total}] — {name}",
                                  (idx + 1) / total * 0.3, logs)

                update_loader("Запуск...", 0.0, logs)
                api_rows_raw, api_rep = api_fixtures_by_league(ak_, d_from, d_to, fixture_progress)
                api_rows = safe_filter(api_rows_raw)
                for line in api_rep:
                    logs.append(f"📡 {line}")

                day_list = [(today + timedelta(days=off)).strftime("%Y-%m-%d") for off in range(0, min(days, 7))]
                tsdb_rows = safe_filter(tsdb_days_parallel(day_list))
                logs.append(f"📡 TSDB-day: {len(tsdb_rows)}")

                seen = set()
                src_rows = []
                for r in (api_rows + tsdb_rows):
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

                cur_year = today.year if today.month >= 7 else today.year - 1
                prev_year = cur_year - 1
                fp = engine_cache_fp(f"{cur_year}", {"all": len(src_rows)})
                engine = engine_cache_get(fp)
                trained = 0
                if engine is None:
                    train_divs = ["E0", "SP1", "I1", "D1", "F1", "E1", "SP2", "I2", "D2", "F2", "N1", "B1", "P1", "T1", "R1"]
                    engine = Engine()
                    dp, dc = {}, {}
                    for i, dv in enumerate(train_divs):
                        pct = 0.3 + (i + 1) / len(train_divs) * 0.35
                        update_loader(f"История [{i + 1}/{len(train_divs)}] — {DIV_NAMES.get(dv, dv)}", pct, logs)
                        dp[dv] = api_season_history(ak_, dv, prev_year)
                        dc[dv] = api_season_history(ak_, dv, cur_year)
                        n = len(dp[dv]) + len(dc[dv])
                        logs.append(f"✅ {DIV_NAMES.get(dv, dv)}: {n}")
                    total_matches = sum(len(dp.get(dv, [])) + len(dc.get(dv, [])) for dv in train_divs)
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
                                    pct = 0.65 + processed / max(1, total_matches) * 0.30
                                    update_loader(f"Обучение [{processed}/{total_matches}]", pct, logs)
                    engine.trained_n = trained
                    engine_cache_put(fp, engine)
                    logs.append(f"🧠 Обучено: {trained}")
                else:
                    logs.append(f"💾 Engine из кэша (обучено {getattr(engine, 'trained_n', '?')})")

                update_loader("Анализ матчей...", 0.97, logs)

                cards = []
                matches_with_best = 0
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
                    fh = engine.form_str(h)
                    fa = engine.form_str(a)
                    verdict, rows, best = build_verdict(
                        P, min_prob, D["bank"], kelly_frac, h, a, fh, fa, P.get("h2h_n", 0))
                    if best and best[4] >= min_prob:
                        matches_with_best += 1
                    else:
                        best = None
                    cards.append({
                        "div": lg,
                        "league": r.get("League") or DIV_NAMES.get(lg, "Лига"),
                        "match": f"{h} vs {a}",
                        "date": d.strftime("%d.%m") + (f" {r.get('Time', '')}" if r.get("Time") else ""),
                        "when": "сегодня" if d.date() == today.date() else "скоро",
                        "verdict": verdict,
                        "best": best,
                        "games": P["games"],
                        "fh": fh, "fa": fa,
                        "fixture_id": r.get("fixture_id"),
                        "date_iso": d.strftime("%Y-%m-%d"),
                    })

                logs.append(f"🎯 Найдено с P≥{min_prob * 100:.0f}%: {matches_with_best}")

                new_bets = []
                existing = {f"{b['match']}|{b['pick']}" for b in D["bets"]
                            if isinstance(b, dict) and b.get("status") == "pending"}
                for c in cards:
                    b = c.get("best")
                    if not b:
                        continue
                    mkt, pick, odd, ev, prob, stake = b
                    stake = round(min(max(stake, 1.0), D["bank"] * 0.05), 2)
                    if stake <= 0:
                        continue
                    bet_key = f"{c['match']}|{pick}"
                    if bet_key in existing:
                        continue
                    new_bets.append({
                        "match": c["match"],
                        "div": c["div"],
                        "league": c["league"],
                        "market": "STAT",
                        "pick": pick,
                        "odds": odd,
                        "stake": stake,
                        "prob": prob,
                        "status": "pending",
                        "strat": "HOT",
                        "mode": D.get("mode", "paper"),
                        "date": datetime.now().strftime("%d.%m.%Y"),
                        "date_iso": c.get("date_iso", datetime.now().strftime("%Y-%m-%d")),
                        "date_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "fixture_id": c.get("fixture_id"),
                        "score": None,
                    })
                    existing.add(bet_key)

                D2 = clone(D)
                D2["cards"] = cards
                D2["report"] = api_rep + [f"TSDB: {len(tsdb_rows)}"]
                D2["bets"] = D2["bets"] + new_bets
                total_stake = sum(b["stake"] for b in new_bets)
                D2["bank"] = max(0.0, D2["bank"] - total_stake)
                D2["funnel"] = {
                    "trained": trained, "src": len(src_rows),
                    "found": matches_with_best, "added": len(new_bets),
                    "frozen": total_stake,
                }
                st.session_state.data = D2
                save_data(D2)

                update_loader(f"✅ Готово! +{len(new_bets)} ставок", 1.0, logs)
                time.sleep(1.5)
                loader_ph.empty()
                log_ph.empty()
        finally:
            st.session_state["_scan_in_progress"] = False
        st.rerun()

    fn = D.get("funnel")
    if fn:
        st.success(f"🧠 Обучено {fn.get('trained', 0)} · "
                   f"🔗 источников {fn.get('src', 0)} · "
                   f"🎯 найдено {fn.get('found', 0)} · "
                   f"➕ в портфель {fn.get('added', 0)} · "
                   f"💰 заморожено {fn.get('frozen', 0):.0f}")
    with st.expander("🔌 Диагностика"):
        for line in D.get("report", []):
            st.text(line)

    cards_view = sorted(
        D.get("cards", []),
        key=lambda c: (c.get("verdict", {}).get("prob") or 0),
        reverse=True,
    )
    shown = 0
    for c in cards_view:
        if not isinstance(c, dict):
            continue
        st.markdown(render_verdict_card(c, min_prob), unsafe_allow_html=True)
        shown += 1
    if not shown:
        st.info("Нажми ⚡ СКАН.")

with tab2:
    st.header("💼 Портфель")
    if not D["bets"]:
        st.warning("Пусто. После СКАНа ставки появятся здесь автоматически.")
    else:
        st.caption(f"Всего: {len(D['bets'])} · В работе: {pending_count}")

        if st.button("📥 Экспорт CSV"):
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["Match", "League", "Pick", "Odds", "Stake", "Prob", "Status", "Score", "Date"])
            for b in D["bets"]:
                if not isinstance(b, dict):
                    continue
                w.writerow([b.get("match", ""), b.get("league", ""), b.get("pick", ""),
                            b.get("odds", ""), b.get("stake", ""), b.get("prob", ""),
                            b.get("status", ""), b.get("score", ""), b.get("date", "")])
            st.download_button("⬇️ Скачать neuro_bets.csv", buf.getvalue(),
                               file_name=f"neuro_bets_{datetime.now():%Y%m%d_%H%M}.csv",
                               mime="text/csv")

        for i, b in enumerate(D["bets"]):
            if not isinstance(b, dict):
                continue
            st_ = b.get("status", "pending")
            icon = {"pending": "⏳", "won": "🟢", "lost": "🔴", "push": "⚪"}.get(st_, "⏳")
            score = f" — счёт {b.get('score', '')}" if b.get("score") else ""
            prob = float(b.get("prob") or 0)
            odds = float(b.get("odds") or 1.0)
            stake = float(b.get("stake") or 0.0)
            pick_label = b.get("pick", "—")
            st.markdown(f"""
<div class="betcard {st_}" style="padding:14px 18px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div style="font-size:1rem;font-weight:800;color:#fff;">{icon} {esc(str(b.get('match', '—')))}{score}</div>
      <div style="color:#8b93a7;font-size:.78rem;margin-top:4px;">{esc(str(b.get('league', '—')))} · {esc(str(b.get('date', '—')))}</div>
    </div>
    <div style="text-align:right;">
      <div style="color:#fbbf24;font-size:1.1rem;font-weight:800;">{esc(str(pick_label))}</div>
      <div style="color:#34d399;font-weight:700;">P {prob * 100:.0f}%</div>
    </div>
  </div>
  <div style="color:#c9d2e3;font-size:.82rem;margin-top:8px;">
    Кэф: <b>{odds:.2f}</b> · Ставка: <b>{stake:.2f} у.е.</b>
  </div>
</div>""", unsafe_allow_html=True)
            if b.get("status") == "pending":
                cc = st.columns([1, 1, 1, 1])
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
                if cc[3].button("🚫", key=f"c{i}"):
                    st.session_state.data = cancel_bet(D, i)
                    save_data(st.session_state.data)
                    st.toast("Ставка отменена, stake возвращён", icon="🚫")
                    st.rerun()

with tab3:
    st.header("📈 Статистика")
    s = D["stats"]
    tot = s["won"] + s["lost"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Банк", f"{D['bank']:.2f}")
    m2.metric("Ставок всего", len(D["bets"]))
    m3.metric("WinRate", f"{(s['won'] / tot * 100) if tot else 0:.1f}%")
    m4.metric("Profit", f"{s['profit']:+.2f}")
    if s.get("push", 0) > 0:
        st.caption(f"🔄 Возвратов (push): {s['push']} — stake возвращён")

with tab4:
    st.header("🧮 EV-калькулятор")
    q1, q2, q3 = st.columns(3)
    p = q1.number_input("P, %", 1, 99, 60)
    o = q2.number_input("Кэф", 1.01, 30.0, 1.80)
    bk = q3.number_input("Банк", 100.0, 1e6, float(D["bank"]))
    ev = (p / 100) * o - 1
    st.markdown(f"**EV:** {ev * 100:+.1f}% · **Келли:** {kelly(p / 100, o, bk, kelly_frac):.2f}")
