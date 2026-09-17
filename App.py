"""NEURO BET PRO v11.2 — API-Football primary + TheSportsDB fallback (no football-data)."""
import streamlit as st
import csv, io, os, math, re, pickle, json, html, time, hashlib, gzip, base64
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============= TRIPLE PROXY DEFENSE =============
PROXY_VARS = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
              "ALL_PROXY", "all_proxy", "FTP_PROXY", "ftp_proxy"]
for _k in PROXY_VARS:
    os.environ.pop(_k, None)

import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
    _HAS_RETRY = True
except Exception:
    _HAS_RETRY = False

st.set_page_config(page_title="NEURO BET PRO v11.2", page_icon="🏟", layout="wide",
                   initial_sidebar_state="expanded")

APP_VERSION = "11.2"
PROMPT_VERSION = "risk_v4"
HISTORY_FILE = "neuro_bet_pro.json"
ERR_FILE = "neuro_errors.log"
ENGINE_CACHE_KEY = "neuro_engine_v11_2"
ENGINE_SNAPSHOT_FILE = "engine.pkl"
DISK_CACHE_DIR = "neuro_cache"
os.makedirs(DISK_CACHE_DIR, exist_ok=True)

esc = html.escape
AVG_GOALS = 2.75
TOTAL_MIN = 95.0
MATRIX_N = 9

HYPERPARAMS = {
    "refit_temp_every": 150, "refit_struct_every": 300,
    "ml_iters": 300, "ml_lr": 0.05, "ml_l2": 0.001,
    "time_decay_tau_days": 180.0, "shr_bayes_k": 200.0,
    "steam_threshold": 0.03, "steam_multiplier": 1.3,
    "max_league_exposure": 0.15, "max_market_exposure": 0.25,
    "max_day_exposure": 0.10, "max_match_exposure": 0.02,
    "max_match_bets": 2, "max_day_bets": 10,
    "llm_mult_min": 0.5, "llm_mult_max": 1.5,
    "llm_veto_risk": 85, "llm_veto_conf": 70,
    "live_beta_cap_matches": 100,
}

# Маппинг DIV → API-Football league id
DIV_TO_APILG = {
    "E0": 39, "E1": 40, "SP1": 140, "SP2": 141,
    "I1": 135, "I2": 136, "D1": 78, "D2": 79,
    "F1": 61, "F2": 62, "N1": 88, "B1": 144,
    "P1": 94, "T1": 203, "R1": 235, "G1": 197,
    "C1": 2, "EL": 3, "EC": 848,
}

API_LG = {"R1": 235, "T1": 203, "C1": 2, "EL": 3, "EC": 848, "RUS_CUP": 233}
API_NAMES = {235: "🇷🇺 РПЛ", 203: "🇹🇷 Суперлига", 2: "🏆 ЛЧ", 3: "🏆 ЛЕ",
             848: "🏆 ЛК", 233: "🏆 Кубок России"}

DIV_NAMES = {
    "E0": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 АПЛ", "E1": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Чемпионшип",
    "D1": "🇩🇪 Бундеслига", "D2": "🇩🇪 2.Бундеслига", "I1": "🇮🇹 Серия A",
    "I2": "🇮🇹 Серия B", "SP1": "🇪🇸 Ла Лига", "SP2": "🇪🇸 Сегунда",
    "F1": "🇫🇷 Лига 1", "F2": "🇫🇷 Лига 2", "N1": "🇳🇱 Эредивизи",
    "B1": "🇧🇪 Про-лига", "P1": "🇵🇹 Примейра", "T1": "🇹🇷 Суперлига",
    "G1": "🇬🇷 Греция", "R1": "🇷🇺 РПЛ",
    "C1": "🏆 ЛЧ", "EL": "🏆 ЛЕ", "EC": "🏆 ЛК",
}
GOALS = {
    "🎯 Проходимость": dict(w_market=0.65, thr=0.62, dis=False, edge=0.01, ev=0.01,
                            corr=(1.30, 2.30), min_games=10),
    "⚖️ Баланс":      dict(w_market=0.40, thr=0.55, dis=True, edge=0.02, ev=0.02,
                            corr=(1.40, 4.20), min_games=8),
    "💰 Value":       dict(w_market=0.20, thr=0.45, dis=True, edge=0.03, ev=0.02,
                            corr=(1.40, 4.20), min_games=6),
}
WALLS = {
    "🌃 Неон-стадион": "linear-gradient(rgba(4,8,18,.80),rgba(4,8,18,.90)),url('https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=1920&auto=format&fit=crop') center/cover no-repeat",
    "🕹 Synthwave":    "linear-gradient(rgba(6,3,20,.82),rgba(6,3,20,.92)),url('https://images.unsplash.com/photo-1550745165-9bc0b252726f?q=80&w=1920&auto=format&fit=crop') center/cover no-repeat",
    "🌌 Aurora":       "radial-gradient(1100px 620px at 10% -10%, rgba(34,211,238,.20), transparent 60%),radial-gradient(950px 540px at 90% 8%, rgba(167,139,250,.20), transparent 62%),radial-gradient(900px 640px at 50% 112%, rgba(52,211,153,.16), transparent 60%),#05070f",
    "⚫ Минимализм":   "linear-gradient(180deg,#070a12 0%,#0b0f1a 55%,#070a12 100%)",
}
SORT_OPTIONS = ["По EV (валуи сверху)", "По вероятности", "По дате (ближайшие)",
                "По коэффициенту", "По лиге (А→Я)"]
SORT_DEFAULT_DESC = {"По EV (валуи сверху)": True, "По вероятности": True,
                     "По дате (ближайшие)": False, "По коэффициенту": True,
                     "По лиге (А→Я)": False}
PORT_SORT = ["⏳ Сначала активные", "📅 По дате (новые сверху)",
             "💰 По сумме ставки", "📈 По PnL", "🎯 По вероятности", "📊 По CLV"]
PORT_DEFAULT_DESC = {"⏳ Сначала активные": False, "📅 По дате (новые сверху)": True,
                     "💰 По сумме ставки": True, "📈 По PnL": True,
                     "🎯 По вероятности": True, "📊 По CLV": True}
CORRIDORS = {"OU": (1.50, 2.80), "AH": (1.60, 2.60), "STAT": (1.40, 4.50)}


def _get_secret(key, default=""):
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key, default)


CLOUD_GEMINI_KEY = _get_secret("GEMINI_KEY", "")
CLOUD_GROK_KEY = _get_secret("GROK_KEY", "")
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
    if not CLOUD_IS_CLOUD:
        try:
            with open(ERR_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


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
        "Accept": "*/*",
    })
    s.trust_env = False
    s.proxies = {"http": None, "https": None}
    return s


_sess = _session()
NO_PROXY = {"http": None, "https": None, "all": None}


def _safe_get(url, timeout=20, headers=None, retries=3):
    last_err = None
    for attempt in range(retries):
        try:
            r = _sess.get(url, timeout=timeout, headers=headers or {}, proxies=NO_PROXY)
            return r
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:80]}"
            time.sleep(1.0 * (attempt + 1))
    return None


def _disk_cache_path(key):
    h = hashlib.md5(key.encode("utf-8")).hexdigest()
    return os.path.join(DISK_CACHE_DIR, f"{h}.bin")


def disk_cache_get(key, max_age_sec):
    try:
        p = _disk_cache_path(key)
        if not os.path.exists(p):
            return None
        age = time.time() - os.path.getmtime(p)
        if age > max_age_sec:
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
    except Exception as e:
        log_err("disk_cache_put", e)


def robust_get(url, timeout=20, headers=None, cache_key=None,
               cache_max_age=900, retries=3):
    """Универсальный GET с кэшем и retry."""
    cached = None
    if cache_key:
        cached = disk_cache_get(cache_key, cache_max_age)
        if cached is not None:
            return cached, "cache", None
    r = _safe_get(url, timeout=timeout, headers=headers, retries=retries)
    if r is None:
        if cache_key:
            cached = disk_cache_get(cache_key, 86400 * 30)
            if cached is not None:
                return cached, "cache_stale", "connection_failed"
        return None, "error", "connection_failed"
    if r.status_code == 200 and r.content:
        if cache_key:
            disk_cache_put(cache_key, r.content)
        return r.content, "live", None
    if cache_key:
        cached = disk_cache_get(cache_key, 86400 * 30)
        if cached is not None:
            return cached, "cache_stale", f"HTTP {r.status_code}"
    return None, "error", f"HTTP {r.status_code}"


def _new_team():
    return {"hs": [], "hc": [], "as": [], "ac": [], "form": [], "cfh": [], "cah": [],
            "cfa": [], "caa": [], "yfh": [], "yah": [], "yfa": [], "yaa": [],
            "hst_h": [], "hstc_h": [], "hst_a": [], "hstc_a": []}


def _new_roi():
    return {"n": 0, "profit": 0.0}


def _new_lp():
    return {"w_shots": 0.35, "rho": -0.13, "w_dc": 0.72, "w_ml": 0.25, "n_train": 0}


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


def is_half_line(x):
    v = _f(x)
    return v is not None and abs((v * 2) % 1) < 1e-9


def fmt_line(v):
    s = f"{v:+.2f}"
    if s.endswith("0"):
        s = s[:-1]
    if s.endswith("."):
        s = s[:-1]
    return s


def is_cup(row):
    if not row:
        return False
    dv = row.get("Div", "")
    lg = (row.get("League") or "").lower()
    return dv in ("C1", "EL", "EC") or any(
        x in lg for x in ["cup", "champions", "europa", "conference", "libertadores"])


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


def kelly(prob, odds, bank, frac):
    if prob <= 0 or odds <= 1:
        return 0.0
    b = odds - 1
    k = (b * prob - (1 - prob)) / b
    return round(min(max(0, k * frac), 0.05) * bank, 2)


def odd1(row, keys):
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


def market_probs(row):
    ph, px, pa = _f(row.get("PSH")), _f(row.get("PSD")), _f(row.get("PSA"))
    if not (ph and px and pa):
        ph, px, pa = _f(row.get("B365H")), _f(row.get("B365D")), _f(row.get("B365A"))
    if not (ph and px and pa):
        return None
    i1, ix, ia = 1 / ph, 1 / px, 1 / pa
    s = i1 + ix + ia
    return (i1 / s, ix / s, ia / s)


def get_pin_open(row):
    if not row:
        return None
    h, x, a = _f(row.get("PSH")), _f(row.get("PSD")), _f(row.get("PSA"))
    if not (h and x and a):
        return None
    return (h, x, a)


def get_pin_current(row):
    if not row:
        return None
    h, x, a = _f(row.get("PSCH")), _f(row.get("PSCD")), _f(row.get("PSCA"))
    if not (h and x and a):
        return get_pin_open(row)
    return (h, x, a)


def clv_for(pick, odd, mkt, row):
    if not odd:
        return None
    if mkt:
        idx = {"П1": 0, "X": 1, "П2": 2}.get(pick)
        if idx is not None:
            return odd * mkt[idx] - 1
    return None


def blend_market(P, mkt, w):
    if not mkt:
        return P
    P = dict(P)
    P["p1"] = (1 - w) * P["p1"] + w * mkt[0]
    P["x"] = (1 - w) * P["x"] + w * mkt[1]
    P["p2"] = (1 - w) * P["p2"] + w * mkt[2]
    t = P["p1"] + P["x"] + P["p2"] or 1.0
    P["p1"] /= t
    P["x"] /= t
    P["p2"] /= t
    P["mkt"] = mkt
    return P


# ============= GIST I/O =============
def _gist_url(gid):
    return f"https://api.github.com/gists/{gid}"


def _gist_load(gid, filename):
    if not gid or not CLOUD_GIST_TOKEN:
        return None
    try:
        headers = {"Authorization": f"token {CLOUD_GIST_TOKEN}",
                   "Accept": "application/vnd.github+json"}
        r = _sess.get(_gist_url(gid), headers=headers, timeout=15, proxies=NO_PROXY)
        if r.status_code != 200:
            return None
        files = r.json().get("files", {})
        if filename not in files:
            return None
        content = files[filename].get("content", "")
        if not content:
            return None
        return json.loads(content)
    except Exception as e:
        log_err("gist_load", e)
        return None


def _gist_save(gid, filename, data):
    if not gid or not CLOUD_GIST_TOKEN:
        return False
    try:
        def default(o):
            if isinstance(o, datetime):
                return o.isoformat()
            raise TypeError(f"not serializable: {type(o)}")
        content = json.dumps(data, ensure_ascii=False, default=default, allow_nan=False)
        headers = {"Authorization": f"token {CLOUD_GIST_TOKEN}",
                   "Accept": "application/vnd.github+json"}
        body = {"files": {filename: {"content": content}}}
        r = _sess.patch(_gist_url(gid), headers=headers, json=body, timeout=20, proxies=NO_PROXY)
        return r.status_code in (200, 201)
    except Exception as e:
        log_err("gist_save", e)
        return False


def engine_to_gist(fp, eng):
    if not CLOUD_IS_CLOUD:
        return False
    try:
        blob = base64.b64encode(pickle.dumps({"fp": fp, "engine": eng})).decode()
        return _gist_save(CLOUD_GIST_ID, "engine.b64",
                          {"data": blob, "fp": fp,
                           "ts": datetime.now().isoformat(), "version": APP_VERSION})
    except Exception as e:
        log_err("engine_to_gist", e)
        return False


def engine_from_gist(fp):
    if not CLOUD_IS_CLOUD:
        return None
    try:
        d = _gist_load(CLOUD_GIST_ID, "engine.b64")
        if not d or d.get("fp") != fp:
            return None
        return pickle.loads(base64.b64decode(d["data"]))["engine"]
    except Exception as e:
        log_err("engine_from_gist", e)
        return None


# ============= API-FOOTBALL (ОСНОВНОЙ ИСТОЧНИК) =============
def api_football_request(api_key, endpoint, params=None, timeout=20):
    """Универсальный запрос к API-Football v3."""
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
            return None, str(data["errors"])[:100]
        return data, None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:60]}"


def api_football_season_history(api_key, div, season_year):
    """История матчей лиги за сезон через API-Football."""
    if not api_key:
        return []
    lid = DIV_TO_APILG.get(div)
    if not lid:
        return []
    ck = f"api_history_{div}_{season_year}"
    cached = disk_cache_get(ck, 86400 * 7)
    if cached is not None:
        return cached
    data, err = api_football_request(api_key, "fixtures",
                                     {"league": lid, "season": season_year, "status": "FT"})
    if err:
        log_err(f"api_history_{div}", err)
        return []
    out = []
    for f in (data or {}).get("response") or []:
        fix = f.get("fixture") or {}
        teams = f.get("teams") or {}
        goals = f.get("goals") or {}
        h = (teams.get("home") or {}).get("name")
        a = (teams.get("away") or {}).get("name")
        hg = goals.get("home")
        ag = goals.get("away")
        if not h or not a or hg is None or ag is None:
            continue
        out.append({
            "Div": div, "Date": (fix.get("date") or "")[:10],
            "HomeTeam": h, "AwayTeam": a,
            "FTHG": str(hg), "FTAG": str(ag),
        })
    disk_cache_put(ck, out)
    return out


def api_football_fixtures(api_key, d_from, d_to):
    """Ближайшие матчи через API-Football."""
    if not api_key:
        return [], ["API fixtures: нет ключа"]
    ck = f"api_fixtures_{d_from}_{d_to}"
    cached = disk_cache_get(ck, 900)
    if cached is not None:
        return cached[0], cached[1] + ["(кэш)"]
    data, err = api_football_request(api_key, "fixtures",
                                     {"from": d_from, "to": d_to, "timezone": "UTC"})
    if err:
        return [], [f"API fixtures: {err}"]
    out = []
    for f in (data or {}).get("response") or []:
        fix = f.get("fixture") or {}
        teams = f.get("teams") or {}
        lg = f.get("league") or {}
        dt = fix.get("date") or ""
        h = (teams.get("home") or {}).get("name")
        a = (teams.get("away") or {}).get("name")
        if not h or not a:
            continue
        out.append({"Div": f"API_{lg.get('id', '')}",
                    "League": lg.get("name") or "Матч",
                    "Date": dt[:10], "Time": dt[11:16],
                    "HomeTeam": h, "AwayTeam": a,
                    "fixture_id": fix.get("id")})
    disk_cache_put(ck, (out, [f"API fixtures: {len(out)}"]))
    return out, [f"API fixtures: {len(out)}"]


def api_football_live(api_key):
    if not api_key:
        return [], ["API live: нет ключа"]
    ck = "api_live_all"
    cached = disk_cache_get(ck, 300)
    if cached is not None:
        return cached[0], cached[1] + ["(кэш 5мин)"]
    data, err = api_football_request(api_key, "fixtures", {"live": "all"})
    if err:
        return [], [f"API live: {err}"]
    out = []
    for f in (data or {}).get("response") or []:
        fix = f.get("fixture") or {}
        teams = f.get("teams") or {}
        goals = f.get("goals") or {}
        lg = f.get("league") or {}
        lid = lg.get("id")
        if lid not in set(API_LG.values()) and lid not in DIV_TO_APILG.values():
            continue
        out.append({"league": lg.get("name", str(lid)),
                    "fixture_id": fix.get("id"),
                    "home": (teams.get("home") or {}).get("name"),
                    "away": (teams.get("away") or {}).get("name"),
                    "home_score": goals.get("home") or 0,
                    "away_score": goals.get("away") or 0,
                    "minute": fix.get("status", {}).get("elapsed") or 0,
                    "stats": {}, "source": "API"})
    disk_cache_put(ck, (out, [f"API live: {len(out)}"]))
    return out, [f"API live: {len(out)}"]


# ============= THESPORTSDB (РЕЗЕРВ) =============
def tsdb_day(dstr):
    ck = f"tsdb_day_{dstr}"
    content, source, err = robust_get(
        f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={dstr}&s=Soccer",
        timeout=15, cache_key=ck, cache_max_age=1800, retries=2)
    if content is None:
        return []
    try:
        out = []
        ev = (json.loads(content) or {}).get("events") or []
        for e in ev:
            h = e.get("strHomeTeam")
            a = e.get("strAwayTeam")
            if not h or not a:
                continue
            out.append({"Div": "TSDB", "League": e.get("strLeague") or "Матч",
                        "Date": (e.get("dateEvent") or "")[:10],
                        "Time": (e.get("strTime") or "")[:5],
                        "HomeTeam": h, "AwayTeam": a})
        return out
    except Exception:
        return []


def tsdb_days_parallel(days_list):
    out = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(tsdb_day, d): d for d in days_list}
        for fut in as_completed(futs):
            try:
                out += fut.result()
            except Exception:
                pass
    return out


def load_livescores():
    ck = "tsdb_livescores"
    content, _, err = robust_get(
        "https://www.thesportsdb.com/api/v1/json/3/livescore.php?s=Soccer",
        timeout=10, cache_key=ck, cache_max_age=60, retries=2)
    if content is None:
        return {}
    try:
        out = {}
        for e in (json.loads(content) or {}).get("events") or []:
            hk = re.sub(r"[^a-zа-я0-9]", "", (e.get("strHomeTeam", "") or "").lower())
            ak = re.sub(r"[^a-zа-я0-9]", "", (e.get("strAwayTeam", "") or "").lower())
            out[(hk, ak)] = {"home": e.get("intHomeScore"), "away": e.get("intAwayScore"),
                             "home_name": e.get("strHomeTeam", ""),
                             "away_name": e.get("strAwayTeam", ""),
                             "status": (e.get("strStatus") or "").strip(),
                             "progress": (e.get("strProgress") or "").strip(),
                             "league": e.get("strLeague") or ""}
        return out
    except Exception:
        return {}


def match_live(live, home, away):
    if not live:
        return None
    hk = re.sub(r"[^a-zа-я0-9]", "", (home or "").lower())
    ak = re.sub(r"[^a-zа-я0-9]", "", (away or "").lower())
    for (lh, la), v in live.items():
        if (lh == hk and la == ak) or (hk in lh and ak in la) or (lh in hk and la in ak):
            return v
    return None


FINISHED_STATUSES = {"match finished", "ft", "aet", "ap", "finished", "full time"}


# ============= CALIBRATOR =============
class Calibrator:
    def __init__(self):
        self.method = "temperature"
        self.platt_a = [1.0, 1.0, 1.0]
        self.platt_b = [0.0, 0.0, 0.0]
        self.temp = 1.0

    def fit(self, logits, outcomes):
        n = len(logits)
        if n < 60:
            self.method = "temperature"
            return
        try:
            lr = 0.01
            for c in range(3):
                zs = logits[c::3]
                ys = outcomes[c::3]
                if len(zs) < 20:
                    continue
                a, b = 1.0, 0.0
                for _ in range(500):
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
            self.method = "temperature"

    def _fit_temp(self, logits, outcomes):
        def nll(T):
            s = 0.0
            for z, y in zip(logits, outcomes):
                p = 1 / (1 + math.exp(-z / max(0.3, T)))
                s -= math.log(min(max(p if y > 0.5 else 1 - p, 1e-9), 1 - 1e-9))
            return s
        best_T, best_ll = 1.0, nll(1.0)
        T = 0.5
        while T <= 3.0001:
            ll = nll(T)
            if ll < best_ll - 1e-9:
                best_ll, best_T = ll, T
            T += 0.05
        self.temp = best_T

    def calibrate(self, p, class_idx=0):
        p = min(max(p, 1e-6), 1 - 1e-6)
        z = math.log(p / (1 - p))
        if self.method == "platt":
            a = self.platt_a[class_idx]
            b = self.platt_b[class_idx]
            return 1 / (1 + math.exp(-max(-30, min(30, a * z + b))))
        return 1 / (1 + math.exp(-max(-30, min(30, z / max(0.3, self.temp)))))


# ============= ENGINE =============
class Engine:
    def __init__(self):
        self.elo = {}
        self.st = defaultdict(_new_team)
        self.hg = []
        self.ag = []
        self.hsth = []
        self.hsta = []
        self.h2h = defaultdict(list)
        self.calib_logits = []
        self.calib_outcomes = []
        self.calibrator = Calibrator()
        self.lp = defaultdict(_new_lp)
        self.hist = defaultdict(list)
        self.ml_w = {}
        self.ml_hist = defaultdict(list)
        self.match_count = 0
        self.market_roi = defaultdict(_new_roi)
        self.last_match_date = {}
        self.global_w_shots = 0.35
        self.global_rho = -0.13
        self.global_w_dc = 0.72

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

    def calibrate(self, p, class_idx=0):
        return self.calibrator.calibrate(p, class_idx)

    def refit_calibrator(self):
        if len(self.calib_logits) < 60:
            return
        self.calibrator.fit(self.calib_logits[-3000:], self.calib_outcomes[-3000:])
        if self.calibrator.method == "temperature":
            self.calibrator._fit_temp(self.calib_logits[-3000:], self.calib_outcomes[-3000:])

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

    def _loglik(self, rows, rho, w):
        ll = 0.0
        for lh, la, e, pde, out, weight in rows:
            p1, px, _ = self._p1px(lh, la, rho)
            f1 = w * p1 + (1 - w) * e * (1 - pde)
            fd = w * px + (1 - w) * pde
            f2 = max(1e-6, 1 - f1 - fd)
            ll -= weight * math.log(min(max((f1, fd, f2)[out], 1e-6), 1 - 1e-6))
        return ll

    def _fit_league(self, lg):
        win = self.hist[lg][-400:]
        if len(win) < 200:
            return
        split = int(len(win) * 0.8)
        train, hold = win[:split], win[split:]
        cur = self.lp[lg]
        best_ws = None
        for ws in (0.20, 0.35, 0.50):
            rows = [((1 - ws) * gh + ws * sh, (1 - ws) * ga + ws * sa, e, pde, out, wt)
                    for gh, ga, sh, sa, e, pde, out, wt in train]
            ll = self._loglik(rows, cur["rho"], cur["w_dc"])
            if best_ws is None or ll < best_ws[0]:
                best_ws = (ll, ws)
        ws_pick = best_ws[1]
        tr = [((1 - ws_pick) * gh + ws_pick * sh, (1 - ws_pick) * ga + ws_pick * sa,
               e, pde, out, wt) for gh, ga, sh, sa, e, pde, out, wt in train]
        ho = [((1 - ws_pick) * gh + ws_pick * sh, (1 - ws_pick) * ga + ws_pick * sa,
               e, pde, out, wt) for gh, ga, sh, sa, e, pde, out, wt in hold]
        best = None
        for rho in (-0.20, -0.13, -0.06, 0.0, 0.06):
            for w in (0.60, 0.72, 0.85):
                ll = self._loglik(tr, rho, w)
                if best is None or ll < best[0]:
                    best = (ll, rho, w)
        if ho and self._loglik(ho, best[1], best[2]) > self._loglik(ho, cur["rho"], cur["w_dc"]):
            return
        n = len(train)
        k = HYPERPARAMS["shr_bayes_k"]
        alpha = n / (n + k)
        cur["w_shots"] = alpha * ws_pick + (1 - alpha) * self.global_w_shots
        cur["rho"] = alpha * best[1] + (1 - alpha) * self.global_rho
        cur["w_dc"] = alpha * best[2] + (1 - alpha) * self.global_w_dc
        cur["n_train"] = n

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
        if row:
            for col, t1, k1, t2, k2 in (("HC", h, "cfh", a, "caa"),
                                        ("AC", a, "cfa", h, "cah"),
                                        ("HY", h, "yfh", a, "yaa"),
                                        ("AY", a, "yfa", h, "yah")):
                v = _f(row.get(col))
                if v is not None:
                    t[t1][k1].append(v)
                    t[t2][k2].append(v)
            hst, ast = _f(row.get("HST")), _f(row.get("AST"))
            if hst is not None and ast is not None:
                t[h]["hst_h"].append(hst)
                t[h]["hstc_h"].append(ast)
                t[a]["hst_a"].append(ast)
                t[a]["hstc_a"].append(hst)
                self.hsth.append(hst)
                self.hsta.append(ast)
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
        if not hist:
            return "нет данных"
        return ", ".join(f"{d:+.0f}" for d in hist)

    def predict(self, h, a, lg="G", match_date=None, cup=False):
        P0 = self.lp[lg]
        ws = P0["w_shots"]
        lh_g = max(0.05, self._m(self.hg, 1.5))
        la_g = max(0.05, self._m(self.ag, 1.2))
        lh_s = max(0.05, self._m(self.hsth, 4.5))
        la_s = max(0.05, self._m(self.hsta, 4.0))
        sh, sa = self.st[h], self.st[a]
        ah_ = self._m(sh["hs"], lh_g) / lh_g
        dh_ = self._m(sh["hc"], la_g) / la_g
        aa_ = self._m(sa["as"], la_g) / la_g
        da_ = self._m(sa["ac"], lh_g) / lh_g
        fh, fa = self._form(h), self._form(a)
        lam_g_h = max(0.3, min(5.0, lh_g * ah_ * da_ * 1.10 * (0.85 + 0.30 * fh)))
        lam_g_a = max(0.25, min(4.5, la_g * aa_ * dh_ * 0.95 * (0.85 + 0.30 * fa)))
        conv_h = lh_g / max(0.5, lh_s)
        conv_a = la_g / max(0.5, la_s)
        ash_h = self._m(sh["hst_h"], lh_s) / lh_s
        dsh_a = self._m(sa["hstc_a"], lh_s) / lh_s
        ash_a = self._m(sa["hst_a"], la_s) / la_s
        dsh_h = self._m(sh["hstc_h"], la_s) / la_s
        lam_s_h = max(0.3, min(5.0, lh_s * conv_h * ash_h * dsh_a * (0.85 + 0.30 * fh)))
        lam_s_a = max(0.25, min(4.5, la_s * conv_a * ash_a * dsh_h * (0.85 + 0.30 * fa)))
        lam_h = (1 - ws) * lam_g_h + ws * lam_s_h
        lam_a = (1 - ws) * lam_g_a + ws * lam_s_a
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
        ref = match_date or datetime.now()
        rest_h = (ref - self.last_match_date[h]).days if h in self.last_match_date else 14
        rest_a = (ref - self.last_match_date[a]).days if a in self.last_match_date else 14
        c1 = self.calibrate(f1, 0)
        cx = self.calibrate(fd, 1)
        c2 = self.calibrate(f2, 2)
        ct = c1 + cx + c2
        if ct > 0.01:
            c1, cx, c2 = c1 / ct, cx / ct, c2 / ct
        over = 1 - sum(self._p(lam_h + lam_a, k) for k in range(3))
        btts = sum(M[i][j] for i in range(1, MATRIX_N) for j in range(1, MATRIX_N))
        corners = ((self._m(sh["cfh"], 5) + self._m(sa["caa"], 5)) / 2,
                   (self._m(sa["cfa"], 5) + self._m(sh["cah"], 5)) / 2)
        yellows = ((self._m(sh["yfh"], 2) + self._m(sa["yaa"], 2)) / 2,
                   (self._m(sa["yfa"], 2) + self._m(sh["yah"], 2)) / 2)
        return {"p1": c1, "x": cx, "p2": c2, "p1_raw": f1, "x_raw": fd, "p2_raw": f2,
                "over": over, "btts": btts, "M": M, "agree": agree,
                "lams": (lam_h, lam_a), "lams_g": (lam_g_h, lam_g_a),
                "lams_s": (lam_s_h, lam_s_a), "games": games, "corners": corners,
                "yellows": yellows, "h2h_n": h2h_n, "e": e, "pde": pde,
                "ml_feats": [], "w_ml_eff": 0.0}

    def learn_step(self, h, a, hg, ag, row=None, lg="G", match_num=None, total=None, match_date=None):
        P = self.predict(h, a, lg, match_date=match_date, cup=is_cup(row))
        out = 0 if hg > ag else (1 if hg == ag else 2)
        weight = 1.0
        if match_date:
            age_days = max(0, (datetime.now() - match_date).days)
            weight = math.exp(-age_days / HYPERPARAMS["time_decay_tau_days"])
        self.calib_logits += [self._logit(P["p1_raw"]), self._logit(P["x_raw"]),
                              self._logit(P["p2_raw"])]
        self.calib_outcomes += [1.0 if out == 0 else 0.0, 1.0 if out == 1 else 0.0,
                                1.0 if out == 2 else 0.0]
        if len(self.calib_logits) > 6000:
            del self.calib_logits[:-6000]
            del self.calib_outcomes[:-6000]
        self.match_count += 1
        if self.match_count % HYPERPARAMS["refit_temp_every"] == 0:
            self.refit_calibrator()
        if len(self.hist[lg]) > 0 and len(self.hist[lg]) % HYPERPARAMS["refit_struct_every"] == 0:
            self._fit_league(lg)
        self.hist[lg].append((P["lams_g"][0], P["lams_g"][1], P["lams_s"][0],
                              P["lams_s"][1], P["e"], P["pde"], out, weight))
        if len(self.hist[lg]) > 1200:
            del self.hist[lg][:-1200]
        self.add(h, a, hg, ag, row, match_num=match_num, total=total, match_date=match_date)
        return P


# ============= CANDIDATES & EVAL =============
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


def evaluate_rows(cands, P, mkt_probs, PR, engine, use_dis, row=None):
    rows = []
    best = None
    hot = []
    card_clv = None
    gap = None
    if mkt_probs:
        gap = max(abs(P["p1"] - mkt_probs[0]), abs(P["x"] - mkt_probs[1]), abs(P["p2"] - mkt_probs[2]))
    for mkt, pick, prob, odd in cands:
        item = {"mkt": mkt, "pick": pick, "prob": prob, "odd": odd, "ev": None,
                "be": None, "ok": False, "steam": None, "steam_mult": 1.0}
        if odd:
            lo, hi = PR["corr"] if mkt == "1X2" else CORRIDORS.get(mkt, (1.4, 4.2))
            ev = prob * odd - 1
            be = 1 / odd
            edge = prob - be
            req = max(0.0, PR["ev"] + max(0.0, odd - 2.5) * 0.02 + engine.market_adjust(mkt))
            dis_ok = (not use_dis) or (gap is None) or (gap >= 0.03)
            agree_ok = (mkt != "1X2") or P["agree"]
            games_ok = P["games"] >= PR["min_games"]
            item.update(ev=ev, be=be,
                        ok=(lo <= odd <= hi and edge >= PR["edge"] and ev >= req
                            and dis_ok and agree_ok and games_ok))
            if item["ok"]:
                stk = kelly(prob, odd, PR["bank"], PR["kelly"])
                if best is None or ev > best[3]:
                    best = (mkt, pick, odd, ev, prob, stk)
                    card_clv = clv_for(pick, odd, mkt_probs, row)
        if prob >= PR["thr"]:
            hot.append((pick, prob, odd))
        rows.append(item)
    hot.sort(key=lambda x: -x[1])
    return rows, best, hot, card_clv, gap


def apply_correlation_limits(bets, bank, new_bet):
    total_stake = sum(b["stake"] for b in bets if b["status"] == "pending") + new_bet["stake"]
    if total_stake > bank * HYPERPARAMS["max_day_exposure"] * 3:
        return 0.0, "total cap"
    league = new_bet.get("league", "")
    league_stake = sum(b["stake"] for b in bets if b.get("league") == league and b["status"] == "pending")
    if league_stake + new_bet["stake"] > bank * HYPERPARAMS["max_league_exposure"]:
        max_stake = max(0, bank * HYPERPARAMS["max_league_exposure"] - league_stake)
        if max_stake < 1.0:
            return 0.0, "league cap"
        new_bet["stake"] = round(max_stake, 2)
    match = new_bet.get("match", "")
    pending_on_match = [b for b in bets if b.get("match") == match and b["status"] == "pending"]
    if len(pending_on_match) >= HYPERPARAMS["max_match_bets"]:
        return 0.0, "match count cap"
    return new_bet["stake"], None


# ============= DATA =============
def new_data():
    return {"version": 10, "bank": 10000.0, "bets": [], "cards": [], "picks": [],
            "funnel": None, "report": [], "meta": {},
            "stats": {"won": 0, "lost": 0, "profit": 0, "push": 0},
            "mode": "paper", "clv_history": [], "decision_history": []}


def migrate(D):
    if not isinstance(D, dict):
        return new_data()
    base = new_data()
    for k in base:
        if k not in D or D[k] is None:
            D[k] = json.loads(json.dumps(base[k]))
    D["version"] = 10
    for key in ("cards", "picks", "bets", "report", "clv_history", "decision_history"):
        if not isinstance(D.get(key), list):
            D[key] = []
    D["bets"] = [b for b in D["bets"] if isinstance(b, dict)
                 and all(k in b for k in ("match", "pick", "odds", "stake", "status"))]
    for b in D["bets"]:
        b.setdefault("strat", "HOT" if b.get("market") == "HOT" else "VALUE")
        b.setdefault("mode", "paper")
    if not isinstance(D.get("stats"), dict):
        D["stats"] = base["stats"]
    for s in ("won", "lost", "profit", "push"):
        D["stats"].setdefault(s, 0)
    if not isinstance(D.get("meta"), dict):
        D["meta"] = {}
    return D


def _sanitize(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else 0.0
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def _local_save(d):
    try:
        def default(o):
            if isinstance(o, datetime):
                return o.isoformat()
            raise TypeError(f"not serializable: {type(o)}")
        clean = _sanitize(d)
        tmp = HISTORY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2, ensure_ascii=False, default=default, allow_nan=False)
        os.replace(tmp, HISTORY_FILE)
    except Exception as e:
        log_err("save_data.local", e)


def _local_load():
    if os.path.exists(HISTORY_FILE):
        try:
            return migrate(json.load(open(HISTORY_FILE, encoding="utf-8")))
        except Exception as e:
            log_err("load_data.local", e)
    return new_data()


def load_data():
    if CLOUD_IS_CLOUD:
        gd = _gist_load(CLOUD_GIST_ID, HISTORY_FILE)
        if gd:
            return migrate(gd)
    return _local_load()


def save_data(D):
    _local_save(D)
    if CLOUD_IS_CLOUD:
        _gist_save(CLOUD_GIST_ID, HISTORY_FILE, D)


def clone(D):
    try:
        return json.loads(json.dumps(_sanitize(D), default=str))
    except Exception as e:
        log_err("clone", e)
        return new_data()


def engine_cache_fp(season, div_counts):
    return (APP_VERSION, season, tuple(sorted(div_counts.items())))


def engine_cache_get(fp):
    eng = engine_from_gist(fp)
    if eng:
        return eng
    try:
        key = ENGINE_CACHE_KEY + "_" + hashlib.md5(str(fp).encode()).hexdigest()[:12]
        cached = disk_cache_get(key, 86400 * 14)
        if cached and cached.get("fp") == fp:
            return cached.get("engine")
    except Exception:
        pass
    try:
        if os.path.exists(ENGINE_SNAPSHOT_FILE):
            with open(ENGINE_SNAPSHOT_FILE, "rb") as f:
                snap = pickle.load(f)
            if snap.get("fp") == fp:
                return snap.get("engine")
    except Exception:
        pass
    return None


def engine_cache_put(fp, eng):
    try:
        key = ENGINE_CACHE_KEY + "_" + hashlib.md5(str(fp).encode()).hexdigest()[:12]
        disk_cache_put(key, {"fp": fp, "engine": eng})
    except Exception:
        pass
    try:
        tmp = ENGINE_SNAPSHOT_FILE + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump({"fp": fp, "engine": eng, "ts": datetime.now().isoformat()}, f)
        os.replace(tmp, ENGINE_SNAPSHOT_FILE)
    except Exception:
        pass
    engine_to_gist(fp, eng)


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
    else:
        b["status"] = "lost"
        D2["stats"]["lost"] += 1
        D2["stats"]["profit"] -= b["stake"]
    return D2


def auto_settle(D, force=False):
    D2 = clone(D)
    changed = 0
    now = datetime.now()
    today = now.date()
    for idx, b in enumerate(D2["bets"]):
        if b["status"] != "pending":
            continue
        if b.get("div") in (None, "TSDB") or (isinstance(b.get("div"), str) and b["div"].startswith("API_")):
            continue
        bd = parse_date(b.get("date_iso", "")) if b.get("date_iso") else None
        if not bd:
            continue
        if not force and bd.date() >= today:
            continue
        if force and bd.date() > today:
            continue
        h, a = b["match"].split(" vs ")
        res = find_result(b.get("div"), h, a, bd)
        if not res:
            continue
        hg, ag = res[0], res[1]
        out = determine_outcome(b.get("market"), b.get("pick"), hg, ag)
        if out:
            D2 = apply_settle(D2, idx, out, score=f"{int(hg)}:{int(ag)}")
            changed += 1
    return D2, changed


def find_result(div, home, away, bd):
    """Ищет результат через API-Football."""
    api_key = CLOUD_API_FOOTBALL_KEY or st.session_state.get("data", {}).get("meta", {}).get("api_key", "")
    if not api_key or not bd:
        return None
    lid = DIV_TO_APILG.get(div)
    if not lid:
        return None
    year = bd.year if bd.month >= 7 else bd.year - 1
    data, err = api_football_request(api_key, "fixtures",
                                     {"league": lid, "season": year, "status": "FT"})
    if err:
        return None
    for f in (data or {}).get("response") or []:
        teams = f.get("teams") or {}
        fix = f.get("fixture") or {}
        goals = f.get("goals") or {}
        h = (teams.get("home") or {}).get("name")
        a = (teams.get("away") or {}).get("name")
        if h != home or a != away:
            continue
        fd = parse_date((fix.get("date") or "")[:10])
        if fd and abs((fd - bd).days) <= 3:
            return (goals.get("home") or 0, goals.get("away") or 0)
    return None


# ============= LIVE MODEL =============
DEFAULT_LIVE = {"alpha": 1.5, "beta": TOTAL_MIN, "temp": 1.0, "signals": [],
                "league_pace": {}, "n_learned": 0}


def load_live_model():
    try:
        if os.path.exists("live_model.json"):
            with open("live_model.json", "r", encoding="utf-8") as f:
                d = json.load(f)
            for k in DEFAULT_LIVE:
                d.setdefault(k, DEFAULT_LIVE[k])
            return d
    except Exception:
        pass
    return dict(DEFAULT_LIVE)


def save_live_model(m):
    try:
        tmp = "live_model.json.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
        os.replace(tmp, "live_model.json")
    except Exception:
        pass


def live_predict(minute, cur_total, base_lam, league=None, live_model=None):
    if live_model is None:
        live_model = load_live_model()
    alpha = float(live_model.get("alpha", 1.5))
    beta = float(live_model.get("beta", TOTAL_MIN))
    temp = float(live_model.get("temp", 1.0))
    minute_f = max(1.0, float(minute))
    remaining = max(1.0, TOTAL_MIN - minute_f)
    pace = league and live_model.get("league_pace", {}).get(league)
    lam_pace = pace[0] / pace[1] if pace else (base_lam / TOTAL_MIN)
    lam_post = (alpha + cur_total) / (beta + minute_f)
    k = (lam_post / lam_pace) if lam_pace > 0.001 else 1.0
    k = max(0.4, min(3.0, k))
    phase = (minute_f % 45) / 45.0
    u_shape = 0.85 + 0.4 * (abs(phase - 0.5) * 2) ** 1.5
    lam_rem = lam_pace * remaining * k * u_shape
    p_goal = 1.0 - math.exp(-lam_rem / max(0.3, temp))
    return {"p_goal": p_goal, "proj_total": cur_total + lam_rem,
            "lam_rem": lam_rem, "pace": lam_pace * TOTAL_MIN, "k": k}


def live_stats(live_model):
    sigs = live_model.get("signals", [])
    fin = [s for s in sigs if s.get("had_goal") is not None]
    total = len(fin)
    if total < 5:
        return {"n": total, "hit_rate": None, "brier": None, "by_league": {}}
    hits = sum(1 for s in fin if s.get("had_goal"))
    brier = sum((s.get("p_goal", 0.5) - (1.0 if s.get("had_goal") else 0.0)) ** 2
                for s in fin) / total
    return {"n": total, "hit_rate": hits / total * 100, "brier": brier, "by_league": {}}


# ============= LLM =============
def llm_gemini(prompt, key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
    try:
        r = _sess.post(url, json=body, timeout=10, proxies=NO_PROXY)
        if r.status_code != 200:
            return None
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None


def llm_risk(ctx, meta):
    gemini_key = meta.get("gemini_key", "")
    if not gemini_key:
        return None
    prompt = f"Match: {ctx['home']} vs {ctx['away']}. Pick: {ctx['pick']} @ {ctx['odd']:.2f}. P={ctx['prob'] * 100:.0f}%. JSON: {{risk_pick:0-100,confidence:0-100,veto:bool,summary:string}}"
    ph = hashlib.md5((PROMPT_VERSION + prompt).encode()).hexdigest()[:16]
    cached = disk_cache_get(f"llm_{ph}", 3600)
    if cached is not None:
        return cached
    try:
        txt = llm_gemini(prompt, gemini_key)
        if txt:
            d = json.loads(txt)
            result = {"source": "gemini", "risk": int(d.get("risk_pick", 50)),
                      "conf": int(d.get("confidence", 50)),
                      "veto": bool(d.get("veto", False)),
                      "mult": float(d.get("suggested_stake_multiplier", 1.0)),
                      "summary": d.get("summary", "")}
            disk_cache_put(f"llm_{ph}", result)
            return result
    except Exception as e:
        log_err("llm", e)
    return None


def heuristic_risk(ctx):
    r = 30 + max(0.0, (0.60 - ctx.get("prob", 0.5))) * 100
    if ctx.get("games", 0) < 5:
        r += 10
    return {"source": "heuristic", "risk": int(max(5, min(95, r))), "conf": 40,
            "veto": (ctx.get("games", 0) < 2), "mult": 1.0,
            "summary": "Эвристика."}


def should_veto(risk):
    if not risk:
        return False
    if risk.get("source") == "heuristic" and risk.get("veto"):
        return True
    if risk.get("veto") and risk.get("risk", 0) >= 85 and risk.get("conf", 0) >= 70:
        return True
    return False


def apply_llm_to_stake(stake, risk):
    if not risk:
        return stake, None
    if should_veto(risk):
        return 0.0, "veto"
    mult = max(0.5, min(1.5, risk.get("mult", 1.0)))
    return round(stake * mult, 2), f"x{mult:.2f}"


# ============= UI HELPERS =============
def _odd_s(rw):
    o = rw.get("odd")
    if o:
        return f"{o:.2f}"
    p = max(rw.get("prob") or 0.01, 0.01)
    return f"фейр {1 / p:.2f}"


def ai_verdict(c):
    rows = c.get("rows", [])
    scored = sorted([r for r in rows if r.get("prob")], key=lambda r: -r["prob"])

    def prep(r):
        if not r:
            return None
        d = dict(r)
        d["odd_s"] = _odd_s(d)
        return d

    main = prep(scored[0]) if scored else None
    alt = prep(scored[1]) if len(scored) > 1 else None
    x12 = [r for r in rows if r["mkt"] == "1X2"]
    avoid = prep(min(x12, key=lambda r: r["prob"])) if x12 else None
    lg = c.get("lams_g", (0, 0))
    lh, la = c.get("lams", (0, 0))
    parts = [f"xG {lg[0]:.2f}–{lg[1]:.2f}, итог {lh:.2f}–{la:.2f}."]
    if c.get("fh", "—") != "—":
        parts.append(f"Форма: {c['fh']} vs {c['fa']}.")
    if c.get("best"):
        parts.append(f"Вывод: {c['best'][1]} @ {c['best'][2]:.2f} (EV {c['best'][3] * 100:+.1f}%).")
    return main, alt, avoid, " ".join(parts)


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
        row = None
        ptype = None
        best = c.get("best")
        if best:
            mkt, pick, odd, ev, prob, stk = best
            row = {"mkt": mkt, "pick": pick, "odd": odd, "ev": ev, "prob": prob,
                   "steam_mult": 1.0, "steam": None}
            ptype = "value"
        if row is None:
            hot = [r for r in c["rows"] if r["prob"] >= thr and r.get("odd")]
            if hot:
                row = max(hot, key=lambda r: r["prob"])
                ptype = "hot"
        if row is None:
            continue
        main, alt, avoid, text = ai_verdict(c)
        stake = kelly(row["prob"], row["odd"], bank, kf) if row["odd"] else round(bank * 0.01, 2)
        picks.append({"league": c["league"], "match": c["match"], "date": c["date"],
                      "when": c["when"], "pick": row["pick"], "prob": row["prob"],
                      "odd": row["odd"], "odd_s": _odd_s(row), "stake": stake,
                      "stars": stars_for(row, thr), "type": ptype, "verdict": text,
                      "main": main, "alt": alt, "avoid": avoid,
                      "clv": c.get("clv"), "ev": row.get("ev"),
                      "score": (row.get("ev") or 0 if ptype == "value" else 0) + row["prob"],
                      "steam": row.get("steam")})
    picks.sort(key=lambda p: (p["type"] == "value", p["score"]), reverse=True)
    return picks[:10]


def strat_stats(bets):
    out = {}
    for s in ("VALUE", "HOT"):
        sb = [b for b in bets if b.get("strat", "VALUE") == s
              and b.get("status") in ("won", "lost", "push")]
        n = len(sb)
        w = sum(1 for b in sb if b["status"] == "won")
        pnl = sum(b["stake"] * (b["odds"] - 1) if b["status"] == "won"
                  else (0.0 if b["status"] == "push" else -b["stake"]) for b in sb)
        staked = sum(b["stake"] for b in sb if b["status"] != "push")
        out[s] = dict(n=n, w=w, pnl=pnl,
                      roi=(pnl / staked * 100 if staked else 0.0),
                      wr=(w / n * 100 if n else 0.0))
    return out


def clv_stats(bets):
    out = {}
    for s in ("VALUE", "HOT"):
        clvs = [b["clv"] for b in bets
                if b.get("strat") == s and b.get("clv") is not None
                and b.get("status") in ("won", "lost", "push")]
        if not clvs:
            out[s] = {"n": 0}
            continue
        pos = sum(1 for c in clvs if c > 0)
        out[s] = {"n": len(clvs), "mean": sum(clvs) / len(clvs),
                  "median": sorted(clvs)[len(clvs) // 2],
                  "pos_pct": pos / len(clvs) * 100}
    return out


def card_sort_val(c, key):
    if key.startswith("По EV"):
        if c.get("best"):
            return c["best"][3]
        return max([r["ev"] for r in c["rows"] if r["ev"] is not None], default=-1)
    if key.startswith("По вероятности"):
        return max([r["prob"] for r in c["rows"]], default=0)
    if key.startswith("По дате"):
        return c.get("dt", "9999-99-99")
    if key.startswith("По коэффициенту"):
        if c.get("best"):
            return c["best"][2]
        return max([r["odd"] for r in c["rows"] if r["odd"]], default=0)
    return c.get("league", "")


def pick_sort_val(p, key):
    if key.startswith("По EV"):
        return p.get("ev") if p.get("ev") is not None else -1
    if key.startswith("По вероятности"):
        return p.get("prob", 0)
    if key.startswith("По дате"):
        return p.get("dt", "9999-99-99")
    if key.startswith("По коэффициенту"):
        return p.get("odd") or 0
    return p.get("league", "")


def bet_sort_key(pair, key):
    i, b = pair
    if key.startswith("⏳"):
        return (0 if b["status"] == "pending" else 1, b.get("date_iso", "9999"))
    if key.startswith("📅"):
        return b.get("date_iso", "9999")
    if key.startswith("💰"):
        return b.get("stake", 0)
    if key.startswith("📈"):
        if b["status"] == "pending":
            return (0, 0.0)
        if b["status"] == "won":
            return (1, b["stake"] * (b["odds"] - 1))
        if b["status"] == "lost":
            return (1, -b["stake"])
        return (1, 0.0)
    if key.startswith("📊"):
        return b.get("clv") if b.get("clv") is not None else -999
    return (0, b.get("prob", 0))


def render_match_card(c, thr, PR):
    val = c.get("best") is not None
    hot = any(r["prob"] >= thr for r in c["rows"]) and not val
    badge = ("<span class='badge val'>🟢 ВАЛУЙ</span>" if val
             else (f"<span class='badge hot'>🔥 P≥{int(thr * 100)}%</span>" if hot
                   else "<span class='badge no'>фон</span>"))
    chips = (f"<span class='chip'>{esc(c['league'])}</span>"
             f"<span class='chip when'>📅 {esc(c['date'])} · {esc(c['when'])}</span>")
    if c["games"] < PR["min_games"]:
        chips += "<span class='chip warn'>⚠️ мало данных</span>"
    main, alt, avoid, vtext = ai_verdict(c)
    m_s = (f"✅ <b class='y'>{esc(main['pick'])}</b> @ {main['odd_s']} "
           f"(P {main['prob'] * 100:.0f}%)") if main else ""
    rows_html = ""
    for rw in c["rows"]:
        ev_s = (f"<span class='{'evpos' if rw['ev'] > 0 else 'evneg'}'>"
                f"{rw['ev'] * 100:+.1f}%</span>") if rw["ev"] is not None else (
            "<span style='color:#64748b'>—</span>")
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
    best_html = (f"<span>💰 Келли: <b>{c['best'][5]:.2f}</b></span>") if val else ""
    h, a = c["match"].split(" vs ")
    return f"""
<div class="mcard {'value' if val else ('hot' if hot else '')}">
 <div>{chips}{badge}</div>
 <div class="teams">{esc(h)} <span>—</span> {esc(a)}</div>
 <div class="verdict">🤖 <b>Вердикт:</b> {m_s}<br>
  <span style="color:#c9d2e3">{esc(vtext)}</span></div>
 {rows_html}
 <div class="mfoot"><span>xG: <b>{c['lams'][0]:.2f}–{c['lams'][1]:.2f}</b></span>
  <span>🚩 угл <b>{ch + ca:.1f}</b></span><span>🟨 жёл <b>{yh + ya:.1f}</b></span>
  <span>📚 игр <b>{c['games']}</b></span>{best_html}</div>
</div>"""


def bet_card_html(b, live=None):
    st_ = b.get("status", "pending")
    icon = {"pending": "⏳", "won": "🟢", "lost": "🔴", "push": "⚪"}.get(st_, "⏳")
    score = f"<span class='score'>{esc(b['score'])}</span>" if b.get("score") else ""
    strat = f"<span style='color:#7dd3fc;font-size:.72rem'>[{esc(b.get('strat', 'VALUE'))}]</span>"
    odds_s = f"{b['odds']:.2f}" if b.get("odds") is not None else "—"
    stake_s = f"{b['stake']:.2f}" if b.get("stake") is not None else "0.00"
    prob_s = f"{b.get('prob', 0) * 100:.0f}%"
    return (f"<div class='betcard {st_}'>{icon} <b>{esc(b['match'])}</b>{score}{strat}<br>"
            f"<b style='color:#fbbf24'>{esc(b['pick'])}</b> @ <b>{odds_s}</b> · "
            f"{stake_s} у.е. · P={prob_s}</div>")


# ============= UI =============
if "data" not in st.session_state:
    st.session_state.data = load_data()
D = st.session_state.data
if "meta" not in D:
    D["meta"] = {}
if CLOUD_GEMINI_KEY and not D["meta"].get("gemini_key"):
    D["meta"]["gemini_key"] = CLOUD_GEMINI_KEY
if CLOUD_API_FOOTBALL_KEY and not D["meta"].get("api_key"):
    D["meta"]["api_key"] = CLOUD_API_FOOTBALL_KEY

wall_key = D.get("meta", {}).get("wall", "🌃 Неон-стадион")
if wall_key not in WALLS:
    wall_key = "🌃 Неон-стадион"
WALL_CSS = WALLS[wall_key]

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@600;800&family=Inter:wght@400;600;800&display=swap');
html,body,#root,.stApp,.stApp>div,
[data-testid="stAppViewContainer"],[data-testid="stAppViewContainer"]>div,
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stBottom"],
[data-testid="stBottom"]>div,[data-testid="stBottomBlockContainer"],
[data-testid="stAppViewBlockContainer"],[data-testid="stVerticalBlock"],
section.main,section.main>div,.main,.main>div,.block-container{
background-color:#05070f!important;background-image:__WALL__!important;
background-attachment:scroll!important;background-size:cover!important;
background-position:center!important;background-repeat:no-repeat!important;}
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stBottom"]>div,
[data-testid="stBottomBlockContainer"]{background:transparent!important;}
.stMarkdown,.stMarkdown p,.stMarkdown li{color:#e6eaf2;font-family:'Inter',sans-serif;}
div[data-testid="stMetricValue"]{color:#f8fafc!important;font-family:'Unbounded',sans-serif;font-size:1.3rem;}
header,#MainMenu{visibility:hidden}
section[data-testid="stSidebar"]{background:rgba(8,11,20,.72);border-right:1px solid rgba(255,255,255,.07);}
section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] label,section[data-testid="stSidebar"] span{color:#e6eaf2!important;}
section.stButton>button{background:linear-gradient(135deg,#0ea5e9,#8b5cf6,#ec4899);color:#fff;border:none;border-radius:14px;font-weight:800;}
.hero{padding:26px 30px;border-radius:26px;margin-bottom:18px;border:1px solid rgba(255,255,255,.10);background:linear-gradient(130deg,rgba(14,165,233,.20),rgba(139,92,246,.16),rgba(236,72,153,.14));}
.hero h1{margin:0;font-size:2.5rem;font-weight:800;background:linear-gradient(92deg,#22d3ee,#a78bfa,#f472b6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:16px;}
.kpi{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.10);border-radius:18px;padding:14px 16px;}
.kpi .t{color:#7dd3fc;font-size:.66rem;text-transform:uppercase;font-weight:700;}
.kpi .v{font-size:1.5rem;font-weight:800;color:#fff;}
.kpi .v.g{color:#34d399;}.kpi .v.y{color:#fbbf24;}.kpi .v.r{color:#f87171;}
.mcard{background:rgba(10,14,24,.72);border:1px solid rgba(255,255,255,.09);border-radius:20px;padding:18px 20px;margin-bottom:14px;}
.mcard.value{border-color:rgba(52,211,153,.55);}.mcard.hot{border-color:rgba(251,191,36,.5);}
.chip{background:rgba(34,211,238,.14);color:#a5f3fc;border:1px solid rgba(34,211,238,.35);padding:3px 11px;border-radius:999px;font-size:.72rem;font-weight:700;margin-right:6px;}
.chip.when{background:rgba(251,191,36,.14);color:#fde68a;}
.chip.warn{background:rgba(248,113,113,.15);color:#fecaca;}
.badge{float:right;padding:4px 13px;border-radius:999px;font-size:.72rem;font-weight:800;}
.badge.val{background:rgba(52,211,153,.25);color:#6ee7b7;}
.badge.hot{background:rgba(251,191,36,.25);color:#fde68a;}
.badge.no{background:rgba(148,163,184,.12);color:#cbd5e1;}
.teams{font-size:1.3rem;font-weight:800;color:#fff;margin:9px 0 3px;}
.teams span{color:#8b93a7;font-weight:400;}
.verdict{background:rgba(34,211,238,.06);border:1px solid rgba(34,211,238,.22);border-radius:14px;padding:11px 15px;margin:9px 0;color:#e6eaf2;font-size:.88rem;}
.mrow{display:grid;grid-template-columns:70px 96px 70px 70px 62px 74px 26px;gap:8px;padding:6px 0;border-top:1px solid rgba(255,255,255,.07);font-size:.83rem;color:#e2e8f0;}
.ok{color:#34d399;font-weight:800;}.nok{color:#64748b;}
.evpos{color:#34d399;font-weight:700;}.evneg{color:#f87171;font-weight:700;}
.mfoot{margin-top:9px;color:#c9d2e3;font-size:.78rem;display:flex;gap:16px;flex-wrap:wrap;}
.mfoot b{color:#fbbf24;}
.betcard{background:rgba(10,14,24,.72);border:1px solid rgba(255,255,255,.09);border-left:4px solid rgba(148,163,184,.4);border-radius:16px;padding:11px 15px;margin-bottom:9px;font-size:.87rem;color:#e6eaf2;}
.betcard.pending{border-left-color:#fbbf24;}.betcard.won{border-left-color:#34d399;}
.betcard.lost{border-left-color:#f87171;}.betcard.push{border-left-color:#94a3b8;}
.betcard .score{font-weight:900;padding:2px 10px;border-radius:9px;margin-left:6px;}
</style>""".replace("__WALL__", WALL_CSS), unsafe_allow_html=True)

cloud_badge = "☁️ CLOUD" if CLOUD_IS_CLOUD else "💾 LOCAL"
mode_label = "📄 PAPER" if D.get("mode") == "paper" else "💰 REAL"
st.markdown(f"""
<div class="hero">
 <h1>NEURO BET PRO</h1>
 <p>v{APP_VERSION} · {cloud_badge} · {mode_label} · 🔗 API-Football + TheSportsDB + Gist</p>
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
        st.warning("💾 Local mode (нет Secrets)", icon="⚠️")
    if st.checkbox("🔬 Network test"):
        import socket
        for host in ["api.github.com", "www.thesportsdb.com", "v3.football.api-sports.io"]:
            try:
                ip = socket.gethostbyname(host)
                st.text(f"✅ {host} → {ip}")
            except Exception as e:
                st.text(f"❌ {host} → {type(e).__name__}")
        ak_ = D.get("meta", {}).get("api_key", "")
        if ak_:
            d, err = api_football_request(ak_, "status")
            st.text(f"📡 API-Football: {'OK' if not err else err}")
        else:
            st.text("📡 API-Football: нет ключа")

    new_wall = st.selectbox("🖼 Обои", list(WALLS.keys()), index=list(WALLS.keys()).index(wall_key))
    if new_wall != wall_key:
        D.setdefault("meta", {})["wall"] = new_wall
        save_data(D)
        st.rerun()

    st.markdown("**🔑 Ключи**")
    gk = st.text_input("Gemini", value=D.get("meta", {}).get("gemini_key", ""), type="password")
    ak = st.text_input("API-Football", value=D.get("meta", {}).get("api_key", ""), type="password")
    if gk != D.get("meta", {}).get("gemini_key", "") or ak != D.get("meta", {}).get("api_key", ""):
        D.setdefault("meta", {}).update({"gemini_key": gk, "api_key": ak})
        save_data(D)
        st.toast("Ключи сохранены", icon="🔑")

    goal = st.selectbox("🎯 Цель", list(GOALS.keys()), index=0)
    PR0 = GOALS[goal]
    kelly_frac = st.slider("Келли", 0.10, 0.40, 0.25, 0.05)
    mode = st.radio("Лента", ["🎯 Проходимость", "💰 Валуи (EV)"])
    thr = st.slider("Порог, %", 30, 90, int(PR0["thr"] * 100)) / 100
    min_edge = st.slider("Edge", 0, 8, int(PR0["edge"] * 100)) / 100
    min_ev = st.slider("EV", 0, 10, int(PR0["ev"] * 100)) / 100
    quota_base = st.slider("Мин событий", 3, 10, 5)

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

tab1, tab2, tab3, tab_clv, tab4, tab6 = st.tabs(
    ["🏟 Сканер", "💼 Портфель", "📈 Статистика", "📊 CLV", "🧮 Калькулятор", "🔴 Онлайн"])

with tab1:
    c1, c2 = st.columns([4, 1])
    days = c1.slider("Горизонт", 1, 21, 7)
    scan = c2.button("⚡ СКАН", type="primary")

    if scan:
        ak_ = D.get("meta", {}).get("api_key", "")
        if not ak_:
            st.error("❌ Нужен API-Football ключ. Введи в сайдбаре.")
        else:
            with st.spinner("Сканирование..."):
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                limit = today + timedelta(days=days)
                d_from = today.strftime("%Y-%m-%d")
                d_to = limit.strftime("%Y-%m-%d")

                # ИСТОЧНИК 1: API-Football fixtures
                api_rows, api_rep = api_football_fixtures(ak_, d_from, d_to)
                # ИСТОЧНИК 2: TheSportsDB day
                day_list = [(today + timedelta(days=off)).strftime("%Y-%m-%d")
                            for off in range(0, min(days, 7))]
                tsdb_rows = tsdb_days_parallel(day_list)

                rep_all = api_rep + [f"TSDB-day: {len(tsdb_rows)}"]

                seen = set()
                src_rows = []
                for r in (api_rows + tsdb_rows):
                    k = (r.get("HomeTeam"), r.get("AwayTeam"), r.get("Date"))
                    if k in seen:
                        continue
                    seen.add(k)
                    src_rows.append(r)

                # Загрузка истории через API-Football
                train_divs = ["E0", "SP1", "I1", "D1", "F1", "E1", "SP2", "I2", "D2", "F2",
                              "N1", "B1", "P1", "T1", "R1"]
                cur_year = today.year if today.month >= 7 else today.year - 1
                prev_year = cur_year - 1

                prog = st.progress(0.0, text="Загрузка истории...")
                dp = {}
                dc = {}
                for i, dv in enumerate(train_divs):
                    dp[dv] = api_football_season_history(ak_, dv, prev_year)
                    dc[dv] = api_football_season_history(ak_, dv, cur_year)
                    prog.progress((i + 1) / len(train_divs))
                prog.empty()

                div_counts = {}
                for dv in train_divs:
                    div_counts[dv] = len(dp.get(dv, [])) + len(dc.get(dv, []))

                fp = engine_cache_fp(f"{cur_year}", div_counts)
                engine = engine_cache_get(fp)
                trained = 0
                if engine is None:
                    engine = Engine()
                    prog = st.progress(0.0, text="Обучение...")
                    for i, dv in enumerate(train_divs):
                        for src in (dp.get(dv, []), dc.get(dv, [])):
                            for j, r in enumerate(src):
                                try:
                                    engine.learn_step(r["HomeTeam"], r["AwayTeam"],
                                                      float(r["FTHG"]), float(r["FTAG"]), r,
                                                      lg=dv, match_num=j, total=max(1, len(src)),
                                                      match_date=parse_date(r.get("Date", "")))
                                    trained += 1
                                except Exception as e:
                                    log_err(f"train {dv}", e)
                        prog.progress((i + 1) / len(train_divs))
                    prog.empty()
                    engine_cache_put(fp, engine)

                PR = dict(PR0)
                PR.update(thr=thr, edge=min_edge, ev=min_ev, bank=D["bank"], kelly=kelly_frac)
                meta = {"temp": engine.calibrator.temp,
                        "api_key": ak_,
                        "gemini_key": D.get("meta", {}).get("gemini_key", "")}

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
                    mkt = market_probs(r)
                    Pb = blend_market(P, mkt, PR["w_market"])
                    league = r.get("League") or DIV_NAMES.get(lg, "Лига " + str(lg))
                    cc = build_candidates(Pb, r, PR)
                    rows, best, hot, card_clv, gap = evaluate_rows(cc, Pb, mkt, PR, engine, False, row=r)
                    advance = d.date() > today.date()
                    cands_all.append({"r": r, "d": d, "tm": (r.get("Time") or "").strip(),
                                      "h": h, "a": a, "lg": lg, "league": league, "P": Pb,
                                      "rows": rows, "best": best, "hot": hot, "clv": card_clv,
                                      "gap": gap, "advance": advance})

                sel = []
                for cand in cands_all:
                    ctx = {"home": cand["h"], "away": cand["a"], "league": cand["league"],
                           "pick": (cand["best"][1] if cand["best"] else "П1"),
                           "odd": (cand["best"][2] if cand["best"] else 1.8),
                           "prob": (cand["best"][4] if cand["best"] else 0.5),
                           "games": cand["P"]["games"]}
                    risk = llm_risk(ctx, meta) or heuristic_risk(ctx)
                    if should_veto(risk):
                        continue
                    cand["risk"] = risk
                    sel.append(cand)

                new_bets = []
                existing = {b["match"] + "|" + b["pick"] for b in D["bets"]}
                for cand in sel:
                    b = cand["best"]
                    if not b:
                        continue
                    mkt, pick, odd, ev, prob = b[0], b[1], b[2], b[3], b[4]
                    stake = kelly(prob, odd, D["bank"], kelly_frac)
                    stake, _ = apply_llm_to_stake(stake, cand.get("risk"))
                    if stake <= 0:
                        continue
                    key = f"{cand['h']} vs {cand['a']}|{pick}"
                    if key in existing:
                        continue
                    dt_full = cand["d"].strftime("%Y-%m-%d %H:%M") if cand["tm"] else cand["d"].strftime("%Y-%m-%d")
                    bet = {"match": f"{cand['h']} vs {cand['a']}", "div": cand["lg"],
                           "league": cand["league"], "market": mkt, "pick": pick,
                           "odds": odd, "stake": stake, "prob": prob,
                           "clv": cand["clv"], "status": "pending",
                           "strat": "VALUE", "tier": 1,
                           "mode": D.get("mode", "paper"),
                           "date": cand["d"].strftime("%d.%m.%Y"),
                           "date_iso": cand["d"].strftime("%Y-%m-%d"),
                           "date_time": dt_full, "score": None}
                    new_stake, _ = apply_correlation_limits(D["bets"] + new_bets, D["bank"], bet)
                    if new_stake <= 0:
                        continue
                    bet["stake"] = new_stake
                    new_bets.append(bet)
                    existing.add(key)

                cards = []
                for cand in sel:
                    P = cand["P"]
                    cards.append({"div": cand["lg"], "league": cand["league"],
                                  "match": f"{cand['h']} vs {cand['a']}",
                                  "date": cand["d"].strftime("%d.%m") + (f" {cand['tm']}" if cand["tm"] else ""),
                                  "when": ("advance" if cand["advance"] else "сегодня"),
                                  "dt": cand["d"].strftime("%Y-%m-%d %H:%M"),
                                  "rows": cand["rows"], "best": cand["best"],
                                  "hot": cand["hot"][:3],
                                  "lams": P["lams"], "lams_g": P["lams_g"],
                                  "lams_s": P["lams_s"], "mkt": P.get("mkt"),
                                  "gap": cand["gap"], "agree": P["agree"],
                                  "clv": cand["clv"], "p1": P["p1"], "px": P["x"],
                                  "p2": P["p2"], "corners": P["corners"],
                                  "yellows": P["yellows"], "games": P["games"],
                                  "fh": engine.form_str(cand["h"]),
                                  "fa": engine.form_str(cand["a"]),
                                  "cup": is_cup(cand["r"]), "tier": 1,
                                  "risk": cand["risk"]})
                picks = build_picks(cards, thr, D["bank"], kelly_frac)
                D2 = clone(D)
                D2["cards"] = cards
                D2["picks"] = picks
                D2["report"] = rep_all
                D2["meta"] = meta
                D2["bets"] = D2["bets"] + new_bets
                D2["funnel"] = {"trained": trained, "src": len(src_rows),
                                "passed": len(sel), "added": len(new_bets)}
                st.session_state.data = D2
                save_data(D2)
                st.rerun()

    fn = D.get("funnel")
    if fn:
        st.caption(f"Обучено {fn.get('trained', 0)} · источников {fn.get('src', 0)} · "
                   f"отобрано {fn.get('passed', 0)} · +{fn.get('added', 0)}")
    with st.expander("🔌 Диагностика"):
        for line in D.get("report", []):
            st.text(line)

    sc1, sc2 = st.columns([3, 1])
    sort_key = sc1.selectbox("Сортировка", SORT_OPTIONS, index=0, key="sort_key")
    invert = sc2.checkbox("🔄", value=False, key="sort_inv")
    eff_desc = SORT_DEFAULT_DESC.get(sort_key, True) if not invert else (not SORT_DEFAULT_DESC.get(sort_key, True))

    picks = D.get("picks", [])
    if picks:
        st.markdown(f"### 🎯 НА ЧТО СТАВИТЬ")
        pv = sorted(picks, key=lambda p: pick_sort_val(p, sort_key), reverse=eff_desc)
        for i, p in enumerate(pv, 1):
            green = p["type"] == "value" or p["prob"] >= 0.60
            cls = "value" if green else "hot"
            m = p["main"]
            m_s = f"✅ <b>{esc(m['pick'])}</b> @ {m['odd_s']}" if m else ""
            st.markdown(f"""<div class='mcard {cls}'>
<span class='chip'>{esc(p['league'])}</span>
<span class='chip when'>📅 {esc(p['date'])}</span>
<div class='teams'>{i}. {esc(p['match'])}</div>
<div class='verdict'>🤖 {m_s}<br>➤ Ставь <b>{esc(p['pick'])}</b> @ <b>{p['odd_s']}</b> · P {p['prob'] * 100:.0f}% · сумма <b>{p['stake']:.2f} у.е.</b></div>
</div>""", unsafe_allow_html=True)

    cards_view = sorted(D.get("cards", []), key=lambda c: card_sort_val(c, sort_key), reverse=eff_desc)
    shown = 0
    for c in cards_view:
        if mode == "💰 Валуи (EV)" and not c["best"]:
            continue
        st.markdown(render_match_card(c, thr, PR0), unsafe_allow_html=True)
        shown += 1
    if not shown and not picks:
        st.info("Нажми ⚡ СКАН.")

with tab2:
    st.header("💼 Портфель")
    if st.button("🔄 Автосинхронизация"):
        D2, n = auto_settle(D, force=True)
        st.session_state.data = D2
        save_data(D2)
        st.toast(f"Закрыто {n}")
        st.rerun()
    if not D["bets"]:
        st.info("Пусто.")
    pairs = sorted(enumerate(D["bets"]), key=lambda pr: bet_sort_key(pr, PORT_SORT[0]),
                   reverse=PORT_DEFAULT_DESC[PORT_SORT[0]])
    for i, b in pairs:
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
    settled = [b for b in D["bets"] if b.get("status") in ("won", "lost", "push")]
    if settled:
        curve = []
        run = 0.0
        for b in settled:
            run += b["stake"] * (b["odds"] - 1) if b["status"] == "won" else (-b["stake"] if b["status"] == "lost" else 0)
            curve.append(run)
        st.line_chart(curve, height=180)

with tab_clv:
    st.header("📊 CLV")
    st.info("Требуется больше ставок")

with tab4:
    st.header("🧮 EV-калькулятор")
    q1, q2, q3 = st.columns(3)
    p = q1.number_input("P, %", 1, 99, 60)
    o = q2.number_input("Кэф", 1.01, 30.0, 1.80)
    bk = q3.number_input("Банк", 100.0, 1e6, float(D["bank"]))
    ev = (p / 100) * o - 1
    st.markdown(f"**EV:** {ev * 100:+.1f}% · **Келли:** {kelly(p / 100, o, bk, kelly_frac):.2f}")

with tab6:
    st.header("🔴 Онлайн")
    api_key = D.get("meta", {}).get("api_key", "")
    if st.button("🔄 Обновить"):
        st.rerun()
    api_lives, api_rep = (api_football_live(api_key) if api_key else ([], ["Нет ключа"]))
    tsdb_raw = load_livescores()
    tsdb_lives = []
    for (hk, ak), v in tsdb_raw.items():
        try:
            hs = int(v.get("home") or 0)
            as_ = int(v.get("away") or 0)
        except Exception:
            hs, as_ = 0, 0
        tsdb_lives.append({"league": v.get("league") or "Матч",
                           "home": v.get("home_name") or hk,
                           "away": v.get("away_name") or ak,
                           "home_score": hs, "away_score": as_, "minute": 45,
                           "stats": {}, "source": "TSDB", "fixture_id": None})
    live_all = api_lives + tsdb_lives
    with st.expander("🔌 Диагностика"):
        for line in api_rep:
            st.text(line)
        st.text(f"Всего live: {len(live_all)}")
    live_models = load_live_model()
    sig_count = 0
    for m in live_all:
        minute = int(m.get("minute") or 0)
        hs = int(m.get("home_score") or 0)
        as_ = int(m.get("away_score") or 0)
        sig = live_predict(minute, hs + as_, AVG_GOALS, league=m.get("league"), live_model=live_models)
        strong = sig["p_goal"] >= 0.60
        if strong:
            sig_count += 1
        st.markdown(f"""<div class='mcard {'value' if strong else ''}'>
<span class='chip'>🔴 {minute}'</span>
<span class='chip'>{esc(str(m.get('league', '')))}</span>
<div class='teams'>{esc(str(m.get('home', '')))} <span>{hs}:{as_}</span> {esc(str(m.get('away', '')))}</div>
<div class='verdict'>P(ещё гол) = <b>{sig['p_goal'] * 100:.0f}%</b> · тотал ≈ <b>{sig['proj_total']:.1f}</b></div>
</div>""", unsafe_allow_html=True)
    if sig_count:
        st.success(f"Сигналов: {sig_count}")
    if not live_all:
        st.info("Живых матчей нет.")
