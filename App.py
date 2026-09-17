"""NEURO BET PRO v12.4 — RU translations + CSS gradients + card filter."""
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

st.set_page_config(page_title="NEURO BET PRO v12.4", page_icon="🏟", layout="wide",
                   initial_sidebar_state="expanded")

APP_VERSION = "12.4"
DATA_VERSION = 15
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

# CSS-градиенты по лигам
STADIUM_WALLS = {
    "E0":  "linear-gradient(135deg, rgba(30,64,175,.55), rgba(15,23,42,.95))",
    "E1":  "linear-gradient(135deg, rgba(37,99,235,.45), rgba(15,23,42,.95))",
    "SP1": "linear-gradient(135deg, rgba(220,38,38,.55), rgba(15,23,42,.95))",
    "SP2": "linear-gradient(135deg, rgba(239,68,68,.45), rgba(15,23,42,.95))",
    "I1":  "linear-gradient(135deg, rgba(22,163,74,.55), rgba(15,23,42,.95))",
    "I2":  "linear-gradient(135deg, rgba(34,197,94,.45), rgba(15,23,42,.95))",
    "D1":  "linear-gradient(135deg, rgba(202,138,4,.55), rgba(15,23,42,.95))",
    "D2":  "linear-gradient(135deg, rgba(234,179,8,.45), rgba(15,23,42,.95))",
    "F1":  "linear-gradient(135deg, rgba(37,99,235,.55), rgba(30,58,138,.55))",
    "F2":  "linear-gradient(135deg, rgba(59,130,246,.45), rgba(30,58,138,.45))",
    "N1":  "linear-gradient(135deg, rgba(249,115,22,.55), rgba(15,23,42,.95))",
    "B1":  "linear-gradient(135deg, rgba(202,138,4,.45), rgba(120,53,15,.55))",
    "P1":  "linear-gradient(135deg, rgba(22,163,74,.55), rgba(220,38,38,.45))",
    "T1":  "linear-gradient(135deg, rgba(220,38,38,.55), rgba(202,138,4,.45))",
    "G1":  "linear-gradient(135deg, rgba(59,130,246,.55), rgba(15,23,42,.95))",
    "R1":  "linear-gradient(135deg, rgba(220,38,38,.55), rgba(30,58,138,.55))",
    "C1":  "linear-gradient(135deg, rgba(139,92,246,.55), rgba(15,23,42,.95))",
    "EL":  "linear-gradient(135deg, rgba(249,115,22,.55), rgba(15,23,42,.95))",
    "EC":  "linear-gradient(135deg, rgba(34,197,94,.55), rgba(15,23,42,.95))",
    "DEFAULT": "linear-gradient(135deg, rgba(71,85,105,.55), rgba(15,23,42,.95))",
}

# ============= [v12.4] ПЕРЕВОД КОМАНД =============
TEAM_TRANSLATIONS = {
    # АПЛ
    "Manchester United": "Манчестер Юнайтед",
    "Manchester City": "Манчестер Сити",
    "Liverpool": "Ливерпуль",
    "Liverpool FC": "Ливерпуль",
    "Arsenal": "Арсенал",
    "Arsenal FC": "Арсенал",
    "Chelsea": "Челси",
    "Chelsea FC": "Челси",
    "Tottenham": "Тоттенхэм",
    "Tottenham Hotspur": "Тоттенхэм",
    "Newcastle": "Ньюкасл",
    "Newcastle United": "Ньюкасл",
    "Aston Villa": "Астон Вилла",
    "Brighton": "Брайтон",
    "Brighton & Hove Albion": "Брайтон",
    "Brighton and Hove Albion": "Брайтон",
    "West Ham": "Вест Хэм",
    "West Ham United": "Вест Хэм",
    "Everton": "Эвертон",
    "Everton FC": "Эвертон",
    "Fulham": "Фулхэм",
    "Fulham FC": "Фулхэм",
    "Crystal Palace": "Кристал Пэлас",
    "Brentford": "Брентфорд",
    "Brentford FC": "Брентфорд",
    "Nottingham Forest": "Ноттингем Форест",
    "Wolverhampton": "Вулверхэмптон",
    "Wolverhampton Wanderers": "Вулверхэмптон",
    "Wolves": "Вулверхэмптон",
    "Bournemouth": "Борнмут",
    "AFC Bournemouth": "Борнмут",
    "Leicester": "Лестер",
    "Leicester City": "Лестер",
    "Southampton": "Саутгемптон",
    "Ipswich": "Ипсвич",
    "Ipswich Town": "Ипсвич",
    "Sheffield United": "Шеффилд Юнайтед",
    "Sheffield Wednesday": "Шеффилд Уэнсдей",
    "Leeds United": "Лидс Юнайтед",
    "Leeds": "Лидс",
    "Burnley": "Бёрнли",
    "Watford": "Уотфорд",
    "Norwich": "Норвич",
    "Norwich City": "Норвич",
    "Middlesbrough": "Мидлсбро",
    "Sunderland": "Сандерленд",
    "West Bromwich Albion": "Вест Бромвич",
    "West Brom": "Вест Бромвич",
    "Stoke City": "Сток Сити",
    "Stoke": "Сток",
    "Hull City": "Халл Сити",
    "Hull": "Халл",
    "Coventry": "Ковентри",
    "Coventry City": "Ковентри",
    "Preston": "Престон",
    "Preston North End": "Престон",
    "Blackburn": "Блэкберн",
    "Blackburn Rovers": "Блэкберн",
    "Bristol City": "Бристоль Сити",
    "Swansea": "Суонси",
    "Swansea City": "Суонси",
    "Cardiff": "Кардифф",
    "Cardiff City": "Кардифф",
    
    # Ла Лига
    "Real Madrid": "Реал Мадрид",
    "Real Madrid CF": "Реал Мадрид",
    "Barcelona": "Барселона",
    "FC Barcelona": "Барселона",
    "Atletico Madrid": "Атлетико Мадрид",
    "Atletico de Madrid": "Атлетико Мадрид",
    "Sevilla": "Севилья",
    "Sevilla FC": "Севилья",
    "Real Betis": "Бетис",
    "Real Sociedad": "Реал Сосьедад",
    "Athletic Bilbao": "Атлетик Бильбао",
    "Athletic Club": "Атлетик Бильбао",
    "Valencia": "Валенсия",
    "Valencia CF": "Валенсия",
    "Villarreal": "Вильярреал",
    "Villarreal CF": "Вильярреал",
    "Celta Vigo": "Сельта",
    "Rayo Vallecano": "Райо Вальекано",
    "Getafe": "Хетафе",
    "Getafe CF": "Хетафе",
    "Osasuna": "Осасуна",
    "Mallorca": "Мальорка",
    "Girona": "Жирона",
    "Las Palmas": "Лас-Пальмас",
    "Alaves": "Алавес",
    "Deportivo Alaves": "Алавес",
    "Espanyol": "Эспаньол",
    "Leganes": "Леганес",
    "Valladolid": "Вальядолид",
    "Real Valladolid": "Вальядолид",
    
    # Серия A
    "Inter": "Интер",
    "Inter Milan": "Интер",
    "Internazionale": "Интер",
    "AC Milan": "Милан",
    "Milan": "Милан",
    "Juventus": "Ювентус",
    "Napoli": "Наполи",
    "Roma": "Рома",
    "AS Roma": "Рома",
    "Lazio": "Лацио",
    "SS Lazio": "Лацио",
    "Atalanta": "Аталанта",
    "Fiorentina": "Фиорентина",
    "Bologna": "Болонья",
    "Torino": "Торино",
    "Udinese": "Удинезе",
    "Sassuolo": "Сассуоло",
    "Empoli": "Эмполи",
    "Verona": "Верона",
    "Hellas Verona": "Верона",
    "Lecce": "Лечче",
    "Cagliari": "Кальяри",
    "Genoa": "Дженоа",
    "Monza": "Монца",
    "Frosinone": "Фрозиноне",
    "Salernitana": "Салернитана",
    
    # Бундеслига
    "Bayern Munich": "Бавария",
    "Bayern München": "Бавария",
    "FC Bayern München": "Бавария",
    "Borussia Dortmund": "Боруссия Дортмунд",
    "RB Leipzig": "РБ Лейпциг",
    "Bayer Leverkusen": "Байер Леверкузен",
    "Bayer 04 Leverkusen": "Байер Леверкузен",
    "Eintracht Frankfurt": "Айнтрахт Франкфурт",
    "Borussia Mönchengladbach": "Боруссия Мёнхенгладбах",
    "VfB Stuttgart": "Штутгарт",
    "VfL Wolfsburg": "Вольфсбург",
    "SC Freiburg": "Фрайбург",
    "Union Berlin": "Унион Берлин",
    "1. FC Union Berlin": "Унион Берлин",
    "Werder Bremen": "Вердер",
    "Mainz 05": "Майнц",
    "1. FSV Mainz 05": "Майнц",
    "FC Augsburg": "Аугсбург",
    "TSG Hoffenheim": "Хоффенхайм",
    "VfL Bochum": "Бохум",
    "1. FC Köln": "Кёльн",
    "FC Cologne": "Кёльн",
    "1. FC Heidenheim": "Хайденхайм",
    "SV Darmstadt 98": "Дармштадт",
    
    # Лига 1
    "Paris Saint-Germain": "Пари Сен-Жермен",
    "Paris Saint Germain": "Пари Сен-Жермен",
    "PSG": "Пари Сен-Жермен",
    "Marseille": "Марсель",
    "Olympique Marseille": "Марсель",
    "Lyon": "Лион",
    "Olympique Lyonnais": "Лион",
    "Monaco": "Монако",
    "AS Monaco": "Монако",
    "Lille": "Лилль",
    "LOSC Lille": "Лилль",
    "Nice": "Ницца",
    "OGC Nice": "Ницца",
    "Rennes": "Ренн",
    "Stade Rennais": "Ренн",
    "Lens": "Ланс",
    "RC Lens": "Ланс",
    "Nantes": "Нант",
    "Strasbourg": "Страсбург",
    "Montpellier": "Монпелье",
    "Toulouse": "Тулуза",
    "Reims": "Реймс",
    "Brest": "Брест",
    "Le Havre": "Гавр",
    "Metz": "Мец",
    "Lorient": "Лорьян",
    "Clermont": "Клермон",
    "Clermont Foot": "Клермон",
    
    # РПЛ
    "Zenit": "Зенит",
    "Zenit St. Petersburg": "Зенит",
    "Spartak Moscow": "Спартак Москва",
    "Spartak": "Спартак",
    "CSKA Moscow": "ЦСКА Москва",
    "CSKA": "ЦСКА",
    "Lokomotiv Moscow": "Локомотив Москва",
    "Lokomotiv": "Локомотив",
    "Dynamo Moscow": "Динамо Москва",
    "Dinamo Moscow": "Динамо Москва",
    "Krasnodar": "Краснодар",
    "FC Krasnodar": "Краснодар",
    "Rostov": "Ростов",
    "FC Rostov": "Ростов",
    "Rubin Kazan": "Рубин",
    "Krylia Sovetov": "Крылья Советов",
    "Akhmat": "Ахмат",
    "Akhmat Grozny": "Ахмат",
    "Sochi": "Сочи",
    "PFC Sochi": "Сочи",
    "Ural": "Урал",
    "Orenburg": "Оренбург",
    "Fakel": "Факел",
    "Baltika": "Балтика",
    "Pari NN": "Пари НН",
    "Nizhny Novgorod": "Пари НН",
    "Torpedo Moscow": "Торпедо Москва",
    "Khimki": "Химки",
    
    # ЛЧ / ЛЕ — популярные
    "Real Madrid CF": "Реал Мадрид",
    "Manchester City FC": "Манчестер Сити",
    "Paris Saint-Germain FC": "Пари Сен-Жермен",
    "Inter": "Интер",
    "AC Milan": "Милан",
    "Bayern": "Бавария",
    "FC Porto": "Порту",
    "Porto": "Порту",
    "Benfica": "Бенфика",
    "SL Benfica": "Бенфика",
    "Ajax": "Аякс",
    "Ajax Amsterdam": "Аякс",
    "PSV": "ПСВ",
    "PSV Eindhoven": "ПСВ",
    "Feyenoord": "Фейеноорд",
    "Celtic": "Селтик",
    "Rangers": "Рейнджерс",
    "Galatasaray": "Галатасарай",
    "Fenerbahce": "Фенербахче",
    "Besiktas": "Бешикташ",
    "Olympiacos": "Олимпиакос",
    "Panathinaikos": "Панатинаикос",
    "AEK Athens": "АЕК Афины",
    "Shakhtar Donetsk": "Шахтёр Донецк",
    "Shakhtar": "Шахтёр",
    "Dinamo Zagreb": "Динамо Загреб",
    "Red Star Belgrade": "Црвена Звезда",
    "Crvena Zvezda": "Црвена Звезда",
    "Salzburg": "Зальцбург",
    "RB Salzburg": "Зальцбург",
    "Young Boys": "Янг Бойз",
    "Copenhagen": "Копенгаген",
    "FC Copenhagen": "Копенгаген",
}


def translate_team(name):
    """Переводит название команды на русский."""
    if not name:
        return name
    name = str(name).strip()
    # Точное совпадение
    if name in TEAM_TRANSLATIONS:
        return TEAM_TRANSLATIONS[name]
    # Без учёта регистра
    low = name.lower()
    for eng, rus in TEAM_TRANSLATIONS.items():
        if low == eng.lower():
            return rus
    # Частичное совпадение (префикс или суффикс)
    for eng, rus in TEAM_TRANSLATIONS.items():
        e = eng.lower()
        if low.startswith(e + " ") or low.endswith(" " + e):
            return rus
    return name


def translate_match(match_str):
    """'Team A vs Team B' → 'Команда А — Команда Б'."""
    if not match_str or " vs " not in match_str:
        return match_str
    parts = match_str.split(" vs ")
    if len(parts) == 2:
        return f"{translate_team(parts[0])} — {translate_team(parts[1])}"
    return match_str


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
            "fp": fp, "engine": engine, "version": APP_VERSION,
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


def api_usage_load(): return _usage_load(API_USAGE_FILE)
def api_usage_increment(n=1): return _usage_increment(API_USAGE_FILE, n)
def api_usage_remaining(): return _usage_remaining(API_USAGE_FILE, API_LIMIT_DAILY)
def api_usage_reset(): return _usage_reset(API_USAGE_FILE)
def settle_usage_load(): return _usage_load(SETTLE_USAGE_FILE)
def settle_usage_increment(n=1): return _usage_increment(SETTLE_USAGE_FILE, n)
def settle_usage_remaining(): return _usage_remaining(SETTLE_USAGE_FILE, AUTO_SETTLE_LIMIT)
def settle_usage_reset(): return _usage_reset(SETTLE_USAGE_FILE)


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
       
