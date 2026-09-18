"""NEURO BET PRO v12.9.7 — every prediction goes to portfolio + 100% free sources."""
import streamlit as st
import csv, io, os, math, re, pickle, json, html, time, hashlib, gzip, base64, hmac, sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

for _k in ["HTTP_PROXY","HTTPS_PROXY","http_proxy","https_proxy",
           "ALL_PROXY","all_proxy","FTP_PROXY","ftp_proxy"]:
    os.environ.pop(_k, None)

import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
    _HAS_RETRY = True
except Exception:
    _HAS_RETRY = False

st.set_page_config(page_title="NEURO BET PRO v12.9.7", page_icon="🏟", layout="wide",
                   initial_sidebar_state="expanded")

APP_VERSION = "12.9.7"
DATA_VERSION = 16
LOCAL_FILE = "neuro_local.json"
DISK_CACHE_DIR = "neuro_cache"
os.makedirs(DISK_CACHE_DIR, exist_ok=True)

try:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _APP_DIR = os.getcwd()
DB_FILE = os.path.join(_APP_DIR, "neuro.db")
LOCAL_PATH = os.path.join(_APP_DIR, LOCAL_FILE)

esc = html.escape
AUTO_SETTLE_LIMIT = 20
AUTO_SETTLE_THROTTLE_SEC = 21600
LLM_DAILY_LIMIT = 20
LLM_TOP_N = 8
ODDS_LIMIT_DAILY = 25

LLM_PROVIDERS = {
    "Groq (бесплатно, быстро)": {"base":"https://api.groq.com/openai/v1","model":"llama-3.3-70b-versatile","key_url":"https://console.groq.com/keys"},
    "Gemini (Google, бесплатно)": {"base":"https://generativelanguage.googleapis.com/v1beta/openai","model":"gemini-2.0-flash","key_url":"https://aistudio.google.com/apikey"},
    "Grok (x.ai)": {"base":"https://api.x.ai/v1","model":"grok-beta","key_url":"https://console.x.ai"},
    "OpenRouter (Llama 3.3)": {"base":"https://openrouter.ai/api/v1","model":"meta-llama/llama-3.3-70b-instruct:free","key_url":"https://openrouter.ai/keys"},
    "OpenAI (gpt-4o-mini)": {"base":"https://api.openai.com/v1","model":"gpt-4o-mini","key_url":"https://platform.openai.com/api-keys"},
    "DeepSeek (дёшево)": {"base":"https://api.deepseek.com/v1","model":"deepseek-chat","key_url":"https://platform.deepseek.com/api_keys"},
}

DIV_NAMES = {"E0":"🏴󠁧󠁢󠁥󠁮󠁧󠁿 АПЛ","E1":"🏴󠁧󠁢󠁥󠁮󠁧󠁿 Чемпионшип","D1":"🇩🇪 Бундеслига",
 "D2":"🇩🇪 2.Бундеслига","I1":"🇮🇹 Серия A","I2":"🇮🇹 Серия B","SP1":"🇪🇸 Ла Лига",
 "SP2":"🇪 Сегунда","F1":"🇫🇷 Лига 1","F2":"🇫🇷 Лига 2","N1":"🇳🇱 Эредивизи",
 "B1":"🇧🇪 Про-лига","P1":"🇵🇹 Примейра","T1":"🇹🇷 Суперлига","G1":"🇬🇷 Греция",
 "R1":"🇷🇺 РПЛ","C1":"🏆 Лига Чемпионов","EL":"🏆 Лига Европы","EC":"🏆 Лига Конференций"}

DIV_TO_TSDB = {"E0":"4328","E1":"4386","D1":"4331","D2":"4389","I1":"4332","I2":"4388",
 "SP1":"4335","SP2":"4340","F1":"4334","F2":"4387","N1":"4337",
 "B1":"4355","P1":"4344","T1":"4339","G1":"4356","R1":"4357",
 "C1":"4480","EL":"4481"}

DIV_TO_ODDS = {"E0":"soccer_epl","E1":"soccer_efl_champ","D1":"soccer_germany_bundesliga",
 "D2":"soccer_germany_bundesliga2","I1":"soccer_italy_serie_a","I2":"soccer_italy_serie_b",
 "SP1":"soccer_spain_la_liga","SP2":"soccer_spain_segunda","F1":"soccer_france_ligue_one",
 "F2":"soccer_france_ligue_two","N1":"soccer_netherlands_eredivisie","B1":"soccer_belgium_first_div",
 "P1":"soccer_portugal_primeira_liga","T1":"soccer_turkey_super_league","G1":"soccer_greece_super_league",
 "C1":"soccer_uefa_champs_league","EL":"soccer_uefa_europa_league"}

STADIUM_WALLS = {
 "E0":"linear-gradient(135deg, rgba(30,64,175,.55), rgba(15,23,42,.95))",
 "E1":"linear-gradient(135deg, rgba(37,99,235,.45), rgba(15,23,42,.95))",
 "SP1":"linear-gradient(135deg, rgba(220,38,38,.55), rgba(15,23,42,.95))",
 "SP2":"linear-gradient(135deg, rgba(239,68,68,.45), rgba(15,23,42,.95))",
 "I1":"linear-gradient(135deg, rgba(22,163,74,.55), rgba(15,23,42,.95))",
 "I2":"linear-gradient(135deg, rgba(34,197,94,.45), rgba(15,23,42,.95))",
 "D1":"linear-gradient(135deg, rgba(202,138,4,.55), rgba(15,23,42,.95))",
 "D2":"linear-gradient(135deg, rgba(234,179,8,.45), rgba(15,23,42,.95))",
 "F1":"linear-gradient(135deg, rgba(37,99,235,.55), rgba(30,58,138,.55))",
 "F2":"linear-gradient(135deg, rgba(59,130,246,.45), rgba(30,58,138,.45))",
 "N1":"linear-gradient(135deg, rgba(249,115,22,.55), rgba(15,23,42,.95))",
 "B1":"linear-gradient(135deg, rgba(202,138,4,.45), rgba(120,53,15,.55))",
 "P1":"linear-gradient(135deg, rgba(22,163,74,.55), rgba(220,38,38,.45))",
 "T1":"linear-gradient(135deg, rgba(220,38,38,.55), rgba(202,138,4,.45))",
 "G1":"linear-gradient(135deg, rgba(59,130,246,.55), rgba(15,23,42,.95))",
 "R1":"linear-gradient(135deg, rgba(220,38,38,.55), rgba(30,58,138,.55))",
 "C1":"linear-gradient(135deg, rgba(139,92,246,.55), rgba(15,23,42,.95))",
 "EL":"linear-gradient(135deg, rgba(249,115,22,.55), rgba(15,23,42,.95))",
 "EC":"linear-gradient(135deg, rgba(34,197,94,.55), rgba(15,23,42,.95))",
 "DEFAULT":"linear-gradient(135deg, rgba(71,85,105,.55), rgba(15,23,42,.95))"}

TEAM_TRANSLATIONS = {
 "Manchester United":"Манчестер Юнайтед","Manchester City":"Манчестер Сити","Liverpool":"Ливерпуль",
 "Arsenal":"Арсенал","Chelsea":"Челси","Tottenham":"Тоттенхэм","Newcastle":"Ньюкасл",
 "Aston Villa":"Астон Вилла","Brighton":"Брайтон","West Ham":"Вест Хэм","Everton":"Эвертон",
 "Fulham":"Фулхэм","Crystal Palace":"Кристал Пэлас","Brentford":"Брентфорд",
 "Nottingham Forest":"Ноттингем Форест","Wolverhampton":"Вулверхэмптон","Wolves":"Вулверхэмптон",
 "Bournemouth":"Борнмут","Leicester":"Лестер","Southampton":"Саутгемптон","Ipswich":"Ипсвич",
 "Leeds":"Лидс","Burnley":"Бёрнли","Watford":"Уотфорд","Norwich":"Норвич",
 "Real Madrid":"Реал Мадрид","Barcelona":"Барселона","Atletico Madrid":"Атлетико Мадрид",
 "Sevilla":"Севилья","Real Betis":"Бетис","Real Sociedad":"Реал Сосьедад",
 "Athletic Bilbao":"Атлетик Бильбао","Valencia":"Валенсия","Villarreal":"Вильярреал","Girona":"Жирона",
 "Inter":"Интер","Inter Milan":"Интер","AC Milan":"Милан","Juventus":"Ювентус","Napoli":"Наполи",
 "Roma":"Рома","Lazio":"Лацио","Atalanta":"Аталанта","Fiorentina":"Фиорентина",
 "Bayern Munich":"Бавария","Borussia Dortmund":"Боруссия Дортмунд","RB Leipzig":"РБ Лейпциг",
 "Bayer Leverkusen":"Байер Леверкузен","PSG":"ПСЖ","Paris Saint-Germain":"ПСЖ","Marseille":"Марсель",
 "Lyon":"Лион","Monaco":"Монако","Lille":"Лилль","Zenit":"Зенит","Spartak Moscow":"Спартак",
 "CSKA Moscow":"ЦСКА","Lokomotiv Moscow":"Локомотив","Dynamo Moscow":"Динамо","Krasnodar":"Краснодар",
 "Rostov":"Ростов","FC Porto":"Порту","Benfica":"Бенфика","Sporting CP":"Спортинг",
 "Ajax":"Аякс","PSV":"ПСВ","Feyenoord":"Фейеноорд"}

def translate_team(name):
    if not name: return name
    name = str(name).strip()
    if name in TEAM_TRANSLATIONS: return TEAM_TRANSLATIONS[name]
    low = name.lower()
    for eng, rus in TEAM_TRANSLATIONS.items():
        if low == eng.lower(): return rus
    for eng, rus in TEAM_TRANSLATIONS.items():
        e = eng.lower()
        if low.startswith(e+" ") or low.endswith(" "+e) or low==e: return rus
    return name

def translate_match(match_str):
    if not match_str or " vs " not in match_str: return match_str or "—"
    parts = match_str.split(" vs ")
    if len(parts)==2: return f"{translate_team(parts[0])} — {translate_team(parts[1])}"
    return match_str

def _get_secret(key, default=""):
    try:
        if key in st.secrets: return str(st.secrets[key])
    except Exception: pass
    return os.environ.get(key, default)

CLOUD_LLM_API_KEY = _get_secret("LLM_API_KEY","")
CLOUD_LLM_PROVIDER = _get_secret("LLM_PROVIDER","Groq (бесплатно, быстро)")
CLOUD_ODDS_KEY = _get_secret("ODDS_API_KEY","")
ERR = []

def log_err(tag,e):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}][{tag}] {type(e).__name__}: {str(e)[:200]}"
    ERR.append(line)
    if len(ERR)>100: ERR.pop(0)

def _session():
    s = requests.Session()
    if _HAS_RETRY:
        r = Retry(total=3,connect=3,read=3,backoff_factor=1.5,
                  status_forcelist=[429,500,502,503,504],
                  allowed_methods=frozenset(["GET","HEAD","POST","PATCH"]),raise_on_status=False)
        ad = HTTPAdapter(max_retries=r,pool_connections=20,pool_maxsize=20)
        s.mount("https://",ad); s.mount("http://",ad)
    s.headers.update({"User-Agent":"Mozilla/5.0 Chrome/120.0"})
    s.trust_env=False; s.proxies={"http":None,"https":None}
    return s
_sess = _session()
NO_PROXY = {"http":None,"https":None,"all":None}

SQLITE_BOOT_OK = False; SQLITE_BOOT_ERROR = ""
def _db_conn():
    conn = sqlite3.connect(DB_FILE,timeout=10,isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL"); conn.execute("PRAGMA synchronous=NORMAL")
    return conn
@contextmanager
def _db():
    conn = _db_conn()
    try: yield conn
    finally: conn.close()
def db_init():
    global SQLITE_BOOT_OK, SQLITE_BOOT_ERROR
    try:
        with _db() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS bets (id INTEGER PRIMARY KEY AUTOINCREMENT,
              match TEXT NOT NULL, match_ru TEXT, div TEXT, league TEXT, market TEXT,
              pick TEXT NOT NULL, odds REAL NOT NULL, closing_odds REAL, stake REAL NOT NULL,
              prob REAL, status TEXT DEFAULT 'pending', score TEXT, strat TEXT,
              odds_source TEXT, mode TEXT, fixture_id TEXT, date TEXT, date_iso TEXT,
              date_time TEXT, ev REAL, clv REAL, settled_at TEXT,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE INDEX IF NOT EXISTS idx_bets_status ON bets(status);
            CREATE INDEX IF NOT EXISTS idx_bets_date ON bets(date_iso);
            CREATE INDEX IF NOT EXISTS idx_bets_fixture ON bets(fixture_id);
            CREATE TABLE IF NOT EXISTS bank_history (id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts TEXT DEFAULT CURRENT_TIMESTAMP, bank REAL NOT NULL, event TEXT,
              bet_id INTEGER, pnl REAL);
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);""")
        db_set_meta("schema_version","2")
        SQLITE_BOOT_OK=True; SQLITE_BOOT_ERROR=""; return True
    except Exception as e:
        SQLITE_BOOT_OK=False; SQLITE_BOOT_ERROR=f"{type(e).__name__}: {e}"
        log_err("db_init",e); return False
def db_set_meta(key,value):
    with _db() as c: c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",(str(key),str(value)))
def db_get_meta(key,default=None):
    with _db() as c:
        row = c.execute("SELECT value FROM meta WHERE key=?",(str(key),)).fetchone()
    return row[0] if row else default
def db_insert_bet(bet):
    with _db() as c:
        cur = c.execute("""INSERT INTO bets (match,match_ru,div,league,market,pick,odds,
          closing_odds,stake,prob,status,score,strat,odds_source,mode,fixture_id,date,
          date_iso,date_time,ev,clv,settled_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (bet.get("match"),bet.get("match_ru"),bet.get("div"),bet.get("league"),
           bet.get("market"),bet.get("pick"),float(bet.get("odds") or 0),bet.get("closing_odds"),
           float(bet.get("stake") or 0),bet.get("prob"),bet.get("status","pending"),
           bet.get("score"),bet.get("strat"),bet.get("odds_source"),bet.get("mode"),
           str(bet.get("fixture_id")) if bet.get("fixture_id") else None,
           bet.get("date"),bet.get("date_iso"),bet.get("date_time"),
           bet.get("ev"),bet.get("clv"),bet.get("settled_at")))
        return cur.lastrowid
def db_update_bet(bet_id,**fields):
    allowed = {"odds","closing_odds","stake","prob","status","score","ev","clv","settled_at","fixture_id","market"}
    safe = {k:v for k,v in fields.items() if k in allowed}
    if not safe: return
    set_sql = ", ".join(f"{k}=?" for k in safe)
    with _db() as c: c.execute(f"UPDATE bets SET {set_sql} WHERE id=?",(*safe.values(),bet_id))
def db_fetch_bets(status=None,limit=None):
    q = "SELECT * FROM bets"; params = []
    if status: q += " WHERE status=?"; params.append(status)
    q += " ORDER BY id DESC"
    if limit: q += f" LIMIT {int(limit)}"
    with _db() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(q,params).fetchall()
    return [dict(r) for r in rows]
def db_log_bank(bank,event="",bet_id=None,pnl=None):
    try:
        with _db() as c:
            c.execute("INSERT INTO bank_history(bank,event,bet_id,pnl) VALUES(?,?,?,?)",
                      (float(bank),event,bet_id,pnl))
    except Exception as e: log_err("db_log_bank",e)
def db_bank_history(limit=2000):
    with _db() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT ts,bank,event,pnl FROM bank_history ORDER BY id DESC LIMIT ?",
                         (int(limit),)).fetchall()
    return [dict(r) for r in reversed(rows)]
def compute_clv(placed,closing):
    if not placed or not closing: return None
    if placed<=1 or closing<=1: return None
    return (placed/closing)-1
def clv_summary():
    try:
        with _db() as c:
            c.row_factory = sqlite3.Row
            rows = c.execute("SELECT clv FROM bets WHERE clv IS NOT NULL").fetchall()
    except Exception: return {"n":0,"avg_clv":0.0,"positive_share":0.0}
    vals = [float(r["clv"]) for r in rows if r["clv"] is not None]
    if not vals: return {"n":0,"avg_clv":0.0,"positive_share":0.0}
    return {"n":len(vals),"avg_clv":sum(vals)/len(vals),
            "positive_share":sum(1 for v in vals if v>0)/len(vals)}
def drawdown_stats(initial_bank=10000.0):
    try: hist = db_bank_history(limit=100000)
    except Exception: hist = []
    banks = [initial_bank]+[h["bank"] for h in hist if h.get("bank") is not None]
    if len(banks)<2:
        return {"peak":initial_bank,"max_dd":0.0,"max_dd_pct":0.0,"current_dd":0.0,
                "current_dd_pct":0.0,"n_points":len(banks)}
    peak = banks[0]; max_dd = 0.0; max_dd_pct = 0.0
    for b in banks:
        if b>peak: peak = b
        dd = peak-b; dd_pct = dd/peak if peak>0 else 0.0
        if dd>max_dd: max_dd = dd; max_dd_pct = dd_pct
    cur = banks[-1]; cp = max(banks)
    cd = cp-cur; cd_pct = cd/cp if cp>0 else 0.0
    return {"peak":cp,"max_dd":max_dd,"max_dd_pct":max_dd_pct,"current_dd":cd,
            "current_dd_pct":cd_pct,"n_points":len(banks)}
def sharpe_ratio(initial_bank=10000.0,periods_per_year=252):
    try: hist = db_bank_history(limit=100000)
    except Exception: hist = []
    banks = [initial_bank]+[h["bank"] for h in hist if h.get("bank") is not None]
    if len(banks)<3: return 0.0
    rets = []
    for i in range(1,len(banks)):
        prev = banks[i-1]
        if prev<=0: continue
        rets.append((banks[i]-prev)/prev)
    if not rets: return 0.0
    mu = sum(rets)/len(rets)
    var = sum((r-mu)**2 for r in rets)/len(rets)
    sigma = var**0.5
    if sigma<=1e-12: return 0.0
    return (mu/sigma)*(periods_per_year**0.5)
def use_sqlite_enabled(): return SQLITE_BOOT_OK
def sync_bets_to_sqlite(D):
    if not SQLITE_BOOT_OK: return 0
    try:
        if len(db_fetch_bets(limit=100000))>=len(D.get("bets",[])): return 0
        for b in D.get("bets",[]):
            if not isinstance(b,dict): continue
            with _db() as c:
                cur = c.execute("SELECT id FROM bets WHERE match=? AND pick=? AND date_iso=? LIMIT 1",
                                (b.get("match"),b.get("pick"),b.get("date_iso")))
                if cur.fetchone(): continue
            db_insert_bet(b)
        db_log_bank(D.get("bank",10000.0),event="sync")
        return 1
    except Exception as e:
        log_err("sync_bets_to_sqlite",e); return 0
def sqlite_status():
    if not SQLITE_BOOT_OK:
        return {"bets":0,"pending":0,"size_kb":0,"path":DB_FILE,
                "exists":os.path.exists(DB_FILE),"error":SQLITE_BOOT_ERROR}
    try:
        nb = len(db_fetch_bets(limit=100000)); np_ = len(db_fetch_bets(status="pending"))
        sz = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0
        return {"bets":nb,"pending":np_,"size_kb":sz/1024,"path":DB_FILE,
                "exists":os.path.exists(DB_FILE),"error":""}
    except Exception as e:
        log_err("sqlite_status",e)
        return {"bets":0,"pending":0,"size_kb":0,"path":DB_FILE,
                "exists":os.path.exists(DB_FILE),"error":str(e)}

def _disk_cache_path(key):
    return os.path.join(DISK_CACHE_DIR,f"{hashlib.md5(key.encode()).hexdigest()}.bin")
def disk_cache_get(key,max_age):
    try:
        p = _disk_cache_path(key)
        if not os.path.exists(p): return None
        if time.time()-os.path.getmtime(p)>max_age: return None
        with open(p,"rb") as f: raw = f.read()
        try: return pickle.loads(gzip.decompress(raw))
        except Exception: return pickle.loads(raw)
    except Exception: return None
def disk_cache_put(key,value):
    try:
        p = _disk_cache_path(key); tmp = p+".tmp"
        with open(tmp,"wb") as f: f.write(gzip.compress(pickle.dumps(value)))
        os.replace(tmp,p)
    except Exception: pass

def _today_str(): return datetime.now().strftime("%Y-%m-%d")
def _usage_load(fn):
    d = {"date":_today_str(),"count":0}
    try:
        if os.path.exists(LOCAL_PATH):
            with open(LOCAL_PATH,"r",encoding="utf-8") as f:
                ld = json.load(f)
            u = (ld.get("usage") or {}).get(fn)
            if isinstance(u,dict) and u.get("date")==_today_str():
                return u
    except Exception: pass
    return d
def _usage_save_local(fn,d):
    try:
        ld = {}
        if os.path.exists(LOCAL_PATH):
            try:
                with open(LOCAL_PATH,"r",encoding="utf-8") as f: ld = json.load(f)
            except Exception: ld = {}
        ld.setdefault("usage",{})[fn] = d
        with open(LOCAL_PATH,"w",encoding="utf-8") as f:
            json.dump(ld,f,ensure_ascii=False,indent=2,default=str)
    except Exception as e: log_err("usage_save_local",e)
def _usage_increment(fn,n=1):
    d = _usage_load(fn); d["count"] = int(d.get("count",0))+n
    _usage_save_local(fn,d)
    return d
def _usage_remaining(fn,limit):
    return max(0,limit-int(_usage_load(fn).get("count",0)))
def _usage_reset(fn):
    d = {"date":_today_str(),"count":0}
    _usage_save_local(fn,d)
    return d
def settle_usage_load(): return _usage_load("settle_usage")
def settle_usage_increment(n=1): return _usage_increment("settle_usage",n)
def settle_usage_remaining(): return _usage_remaining("settle_usage",AUTO_SETTLE_LIMIT)
def settle_usage_reset(): return _usage_reset("settle_usage")
def llm_usage_load(): return _usage_load("llm_usage")
def llm_usage_increment(n=1): return _usage_increment("llm_usage",n)
def llm_usage_remaining(): return _usage_remaining("llm_usage",LLM_DAILY_LIMIT)
def llm_usage_reset(): return _usage_reset("llm_usage")
def odds_usage_load(): return _usage_load("odds_usage")
def odds_usage_increment(n=1): return _usage_increment("odds_usage",n)
def odds_usage_remaining(): return _usage_remaining("odds_usage",ODDS_LIMIT_DAILY)
def odds_usage_reset(): return _usage_reset("odds_usage")

def _new_team():
    return {"hs":[],"hc":[],"as":[],"ac":[],"form":[]}
def _new_lp(): return {"rho":-0.13,"w_dc":0.72}
def _f(v):
    try: return float(v)
    except Exception: return None
def parse_date(s):
    if s is None: return None
    src = str(s).strip()
    if not src: return None
    for fmt in ("%d/%m/%Y %H:%M","%d/%m/%Y","%d/%m/%y","%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S%z","%Y-%m-%dT%H:%M:%S","%Y-%m-%d %H:%M:%S","%Y-%m-%d %H:%M"):
        try:
            sc = src[:19] if "%z" in fmt or "T" in fmt else src
            return datetime.strptime(sc,fmt)
        except Exception: continue
    return None
def _season_str(y):
    return f"{y%100:02d}{(y+1)%100:02d}"
def is_cup(div):
    return div in ("C1","EL","EC")
def kelly(prob,odds,bank,frac):
    if prob<=0 or odds<=1: return 0.0
    b = odds-1; k = (b*prob-(1-prob))/b
    return round(min(max(0,k*frac),0.05)*bank,2)
def _market_type(pick):
    if pick in ("П1","X","П2"): return "1X2"
    if pick in ("ТБ 2.5","ТМ 2.5"): return "OU"
    if pick.startswith("BTTS"): return "BTTS"
    if pick.startswith("Ф"): return "AH"
    if pick in ("1X","X2","12"): return "DC"
    return "OTHER"
def settle_ah(pick,hg,ag):
    m = re.match(r"Ф([12])\(([-+]?\d+(?:\.\d+)?)\)",pick or "")
    if not m: return None
    side,line = int(m.group(1)),float(m.group(2))
    res = ((hg-ag) if side==1 else (ag-hg))+line
    if res>0.001: return True
    if abs(res)<=0.001: return "push"
    return False
def determine_outcome(market,pick,hg,ag):
    m = (market or "").upper(); p = (pick or "").strip()
    if m in ("","HOT","STAT","OTHER"):
        if p in ("П1","X","П2"): m = "1X2"
        elif p in ("ТБ 2.5","ТМ 2.5"): m = "OU"
        elif p.startswith("Ф"): m = "AH"
        elif p.startswith("BTTS"): m = "BTTS"
        elif p in ("1X","X2","12"): m = "DC"
        else: return None
    if m=="1X2":
        res = "П1" if hg>ag else ("X" if hg==ag else "П2")
        return "won" if res==p else "lost"
    if m=="OU":
        if p=="ТБ 2.5": return "won" if hg+ag>=3 else "lost"
        if p=="ТМ 2.5": return "won" if hg+ag<=2 else "lost"
        return None
    if m=="AH":
        s = settle_ah(p,hg,ag)
        if s is None: return None
        return "push" if s=="push" else ("won" if s else "lost")
    if m=="BTTS":
        both = (hg>0 and ag>0)
        return "won" if (both==(p=="BTTS да")) else "lost"
    if m=="DC":
        if p=="1X": ok = hg>=ag
        elif p=="X2": ok = hg<=ag
        elif p=="12": ok = hg!=ag
        else: return None
        return "won" if ok else "lost"
    return None

# ============================================================
# Бесплатные источники
# ============================================================
def load_seasonal(div,season):
    ck = f"fd_{div}_{season}"
    cached = disk_cache_get(ck,86400*3)
    if cached is not None: return cached if isinstance(cached,list) else []
    url = f"https://www.football-data.co.uk/mmz4281/{season}/{div}.csv"
    try:
        r = _sess.get(url,timeout=25,proxies=NO_PROXY)
        if r.status_code!=200 or not r.content:
            log_err("load_seasonal",f"HTTP {r.status_code} {url}"); return []
        text = r.content.decode("utf-8",errors="ignore").lstrip("\ufeff")
        out = []
        for row in csv.DictReader(io.StringIO(text)):
            if not isinstance(row,dict): continue
            if not row.get("HomeTeam") or not row.get("AwayTeam"): continue
            if row.get("FTHG") in (None,"") or row.get("FTAG") in (None,""): continue
            out.append(row)
        disk_cache_put(ck,out); return out
    except Exception as e:
        log_err("load_seasonal",e); return []

def _match_tsdb_league(league_name):
    if not league_name: return None
    ln = league_name.lower()
    mapping = {
        "english premier league":"E0","premier league":"E0",
        "english championship":"E1","championship":"E1",
        "spanish la liga":"SP1","la liga":"SP1","laliga":"SP1",
        "spanish segunda":"SP2","segunda":"SP2",
        "german bundesliga":"D1","bundesliga":"D1",
        "german 2. bundesliga":"D2","2. bundesliga":"D2",
        "italian serie a":"I1","serie a":"I1",
        "italian serie b":"I2","serie b":"I2",
        "french ligue 1":"F1","ligue 1":"F1",
        "french ligue 2":"F2","ligue 2":"F2",
        "dutch eredivisie":"N1","eredivisie":"N1",
        "belgian first division":"B1","belgian pro league":"B1",
        "portuguese primeira liga":"P1","primeira liga":"P1",
        "turkish super lig":"T1","turkish super league":"T1",
        "greek super league":"G1",
        "russian premier league":"R1","russian football":"R1",
        "uefa champions league":"C1","champions league":"C1",
        "uefa europa league":"EL","europa league":"EL",
    }
    for key,code in mapping.items():
        if key in ln: return code
    return None

def tsdb_today_matches(days=7):
    today = datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
    out = []
    for off in range(0,days):
        d = today + timedelta(days=off)
        dstr = d.strftime("%Y-%m-%d")
        ck = f"tsdb_day_{dstr}"
        cached = disk_cache_get(ck,1800)
        if cached is not None:
            if isinstance(cached,list): out += cached
            continue
        try:
            r = _sess.get("https://www.thesportsdb.com/api/v1/json/3/eventsday.php",
                          params={"d":dstr,"s":"Soccer"},timeout=15,proxies=NO_PROXY)
            if r.status_code!=200: continue
            ev = (r.json() or {}).get("events") or []
            rows = []
            for e in ev:
                if not isinstance(e,dict): continue
                h = e.get("strHomeTeam"); a = e.get("strAwayTeam")
                if not h or not a: continue
                league = e.get("strLeague") or "Матч"
                div_code = _match_tsdb_league(league)
                rows.append({"Div":div_code,"League":league,
                             "Date":(e.get("dateEvent") or "")[:10],
                             "Time":(e.get("strTime") or "")[:5],
                             "HomeTeam":h,"AwayTeam":a,
                             "fixture_id":e.get("idEvent")})
            out += rows
            disk_cache_put(ck,rows)
        except Exception as e_:
            log_err("tsdb_today",e_)
    return out

def tsdb_past_league(tsdb_id,limit=60):
    if not tsdb_id: return []
    ck = f"tsdb_past_{tsdb_id}"
    cached = disk_cache_get(ck,86400*3)
    if cached is not None: return cached if isinstance(cached,list) else []
    try:
        r = _sess.get("https://www.thesportsdb.com/api/v1/json/3/eventspastleague.php",
                      params={"id":tsdb_id},timeout=15,proxies=NO_PROXY)
        if r.status_code!=200: return []
        ev = (r.json() or {}).get("events") or []
        out = []
        for e in ev[:limit]:
            h = e.get("strHomeTeam"); a = e.get("strAwayTeam")
            hg = _f(e.get("intHomeScore")); ag = _f(e.get("intAwayScore"))
            if not h or not a or hg is None or ag is None: continue
            out.append({"HomeTeam":h,"AwayTeam":a,
                        "FTHG":str(int(hg)),"FTAG":str(int(ag)),
                        "Date":(e.get("dateEvent") or "")[:10]})
        disk_cache_put(ck,out); return out
    except Exception: return []

def tsdb_match_result(fixture_id):
    if not fixture_id: return None
    ck = f"tsdb_result_{fixture_id}"
    cached = disk_cache_get(ck,86400)
    if cached is not None: return cached or None
    try:
        r = _sess.get(f"https://www.thesportsdb.com/api/v1/json/3/lookupevent.php",
                      params={"id":fixture_id},timeout=15,proxies=NO_PROXY)
        if r.status_code!=200: return None
        ev = ((r.json() or {}).get("events") or [None])[0]
        if not ev: return None
        status = ev.get("strStatus") or ""
        hg = _f(ev.get("intHomeScore")); ag = _f(ev.get("intAwayScore"))
        if hg is None or ag is None:
            disk_cache_put(ck,None); return None
        result = {"home":int(hg),"away":int(ag),"status":status}
        disk_cache_put(ck,result); return result
    except Exception as e_:
        log_err("tsdb_result",e_); return None

def _norm_team_name(s): return re.sub(r"[^a-zа-я0-9]","",(s or "").lower())

def odds_api_fixture(sport_key,home,away,api_key):
    if not api_key or not sport_key: return None
    if odds_usage_remaining()<=0: return None
    ck = f"odds_{sport_key}_{_norm_team_name(home)}_{_norm_team_name(away)}"
    cached = disk_cache_get(ck,7200)
    if cached is not None: return cached or None
    try:
        r = _sess.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds",
                      params={"apiKey":api_key,"regions":"eu","markets":"h2h,totals,btts",
                              "oddsFormat":"decimal"},timeout=20,proxies=NO_PROXY)
        if r.status_code!=200:
            log_err("odds_api",f"HTTP {r.status_code}"); return None
        odds_usage_increment(1)
        events = r.json() or []
        hn = _norm_team_name(home); an = _norm_team_name(away)
        target = None
        for ev in events:
            eh = _norm_team_name(ev.get("home_team",""))
            ea = _norm_team_name(ev.get("away_team",""))
            if eh==hn and ea==an:
                target = ev; break
            if (eh in hn or hn in eh) and (ea in an or an in ea):
                target = ev; break
        if not target: return None
        acc = defaultdict(list)
        for bmk in target.get("bookmakers") or []:
            for mkt in bmk.get("markets") or []:
                name = mkt.get("key")
                for out in mkt.get("outcomes") or []:
                    on = out.get("name") or ""
                    odd = _f(out.get("price"))
                    if odd is None or odd<=1.0: continue
                    if name=="h2h":
                        if on==target.get("home_team"): acc["П1"].append(odd)
                        elif on==target.get("away_team"): acc["П2"].append(odd)
                        elif on=="Draw": acc["X"].append(odd)
                    elif name=="totals":
                        pt = _f(out.get("point"))
                        if pt is not None and abs(pt-2.5)<0.01:
                            if on=="Over": acc["ТБ 2.5"].append(odd)
                            elif on=="Under": acc["ТМ 2.5"].append(odd)
                    elif name=="btts":
                        if on=="Yes": acc["BTTS да"].append(odd)
                        elif on=="No": acc["BTTS нет"].append(odd)
        out = {}
        for k,v in acc.items():
            if v: out[k] = sum(v)/len(v)
        if not (("П1" in out and "X" in out and "П2" in out) or
                ("ТБ 2.5" in out and "ТМ 2.5" in out) or
                ("BTTS да" in out and "BTTS нет" in out)):
            out = {}
        disk_cache_put(ck,out or None); return out or None
    except Exception as e:
        log_err("odds_api",e); return None

# ============================================================
# LLM Analyst
# ============================================================
LLM_SYSTEM_PROMPT = """Ты — эксперт-аналитик футбола и ставок. Отвечай на русском.
Тебе дают данные о матче: команды, лига, модельные xG, вероятности, форма, вердикт ML-модели.
Твоя задача:
1. Дать КРАТКОЕ мнение (1-3 предложения) по этому матчу.
2. Согласиться или возразить модели, если видишь что-то упущенное.
3. Указать главные факторы (форма, травмы, мотивация, стиль).
4. Предупредить о рисках если есть.

Формат ответа СТРОГО: JSON с полями:
{"opinion": "краткое мнение 1-3 предложения", "agree": true/false, "risks": "короткий список рисков или пусто"}

НЕ добавляй пояснений, markdown, код. Только валидный JSON."""

def llm_analyze_match(match_ctx):
    api_key = match_ctx.get("api_key") or CLOUD_LLM_API_KEY
    if not api_key: return None
    if llm_usage_remaining()<=0: return None
    provider = match_ctx.get("provider") or CLOUD_LLM_PROVIDER
    if provider not in LLM_PROVIDERS: provider = "Groq (бесплатно, быстро)"
    cfg = LLM_PROVIDERS[provider]
    model = match_ctx.get("model") or cfg["model"]
    base = cfg["base"]
    ctx_hash = hashlib.md5(json.dumps(match_ctx,sort_keys=True,default=str).encode()).hexdigest()
    ck = f"llm_{ctx_hash}"
    cached = disk_cache_get(ck,86400*3)
    if cached is not None: return cached
    user_msg = (
        f"Матч: {match_ctx.get('home','')} — {match_ctx.get('away','')}\n"
        f"Лига: {match_ctx.get('league','')}\n"
        f"Дата: {match_ctx.get('date','')}\n"
        f"Модельный xG: хозяева {match_ctx.get('lam_h',0):.2f}, гости {match_ctx.get('lam_a',0):.2f}\n"
        f"Вероятности: П1 {match_ctx.get('p1',0)*100:.0f}%, X {match_ctx.get('px',0)*100:.0f}%, П2 {match_ctx.get('p2',0)*100:.0f}%\n"
        f"ТБ 2.5: {match_ctx.get('over',0)*100:.0f}%, BTTS: {match_ctx.get('btts',0)*100:.0f}%\n"
        f"Форма хозяев: {match_ctx.get('fh','—')}, гостей: {match_ctx.get('fa','—')}\n"
        f"Вердикт ML-модели: {match_ctx.get('pick','')} с P={match_ctx.get('prob',0)*100:.0f}% (уверенность: {match_ctx.get('confidence','')})\n"
        f"EV: {match_ctx.get('ev',0)*100:+.1f}%\n"
    )
    try:
        r = _sess.post(f"{base}/chat/completions",
            headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},
            json={"model":model,
                  "messages":[{"role":"system","content":LLM_SYSTEM_PROMPT},
                              {"role":"user","content":user_msg}],
                  "temperature":0.3,"max_tokens":300},
            timeout=30,proxies=NO_PROXY)
        llm_usage_increment(1)
        if r.status_code!=200:
            log_err("llm_request",f"HTTP {r.status_code}: {r.text[:150]}"); return None
        data = r.json()
        content = data.get("choices",[{}])[0].get("message",{}).get("content","")
        content = content.strip()
        if content.startswith("```"): content = re.sub(r"^```(?:json)?\s*|\s*```$","",content).strip()
        parsed = None
        try: parsed = json.loads(content)
        except Exception:
            m = re.search(r"\{[^{}]*\}",content)
            if m:
                try: parsed = json.loads(m.group(0))
                except Exception: parsed = None
        if parsed and "opinion" in parsed:
            opinion = str(parsed["opinion"]).strip()
            agree = parsed.get("agree"); risks = parsed.get("risks")
            tag = "✅ Согласен" if agree else "🤔 Спорно"
            result = f"{tag}. {opinion}"
            if risks: result += f" · Риски: {risks}"
            disk_cache_put(ck,result); return result
        disk_cache_put(ck,content[:300]); return content[:300] if content else None
    except Exception as e:
        log_err("llm_analyze",e); return None

# ============================================================
# ML Engine
# ============================================================
class Calibrator:
    def __init__(self):
        self.platt_a = [1.0,1.0,1.0]; self.platt_b = [0.0,0.0,0.0]; self.method = "identity"
    def fit(self,logits,outcomes):
        if len(logits)<60: return
        try:
            lr = 0.01; reg = 0.01
            for c in range(3):
                zs = logits[c::3]; ys = outcomes[c::3]
                if len(zs)<20: continue
                zm = sum(zs)/len(zs)
                zs_std = (sum((z-zm)**2 for z in zs)/len(zs))**0.5 or 1.0
                zn = [(z-zm)/zs_std for z in zs]
                a,b = 1.0,0.0
                for _ in range(300):
                    ga,gb = 0.0,0.0
                    for z,y in zip(zn,ys):
                        p = 1/(1+math.exp(-max(-30,min(30,a*z+b))))
                        err = p-y; ga += err*z; gb += err
                    ga = ga/max(1,len(zn))+reg*a; gb = gb/max(1,len(zn))
                    a -= lr*ga; b -= lr*gb
                self.platt_a[c] = a/zs_std; self.platt_b[c] = b-a*zm/zs_std
            self.method = "platt_reg"
        except Exception as e: log_err("calibrator_fit",e)
    def calibrate(self,p,ci=0):
        p = min(max(p,1e-6),1-1e-6)
        if self.method in ("platt","platt_reg"):
            z = math.log(p/(1-p)); a = self.platt_a[ci]; b = self.platt_b[ci]
            return 1/(1+math.exp(-max(-30,min(30,a*z+b))))
        return p

class Engine:
    def __init__(self,matrix_n=12):
        self.matrix_n = int(matrix_n); self.elo = {}; self.st = defaultdict(_new_team)
        self.hg = []; self.ag = []; self.lg_hg = defaultdict(list); self.lg_ag = defaultdict(list)
        self.h2h = defaultdict(list); self.calib_logits = []; self.calib_outcomes = []
        self.calibrator = Calibrator(); self.lp = defaultdict(_new_lp)
        self.match_count = 0; self.last_match_date = {}; self.trained_n = 0
    @staticmethod
    def _logit(p):
        p = min(max(p,1e-6),1-1e-6); return math.log(p/(1-p))
    def _m(self,l,d=1.0): return sum(l)/len(l) if l else d
    def _p(self,l,k):
        try: return math.exp(-l)*l**k/math.factorial(k)
        except Exception: return 0.0
    def _form(self,t):
        f = self.st[t]["form"][-5:]; return (sum(f)/(len(f)*3)) if f else 0.5
    def form_str(self,t):
        out = ""
        for x in self.st[t]["form"][-5:]: out += {"3":"В","1":"Н","0":"П"}[str(int(x))]
        return out or "—"
    def calibrate(self,p,ci=0): return self.calibrator.calibrate(p,ci)
    def refit_calibrator(self):
        if len(self.calib_logits)<60: return
        self.calibrator.fit(self.calib_logits[-3000:],self.calib_outcomes[-3000:])
    def _p1px(self,lh,la,rho):
        N = self.matrix_n
        M = [[self._p(lh,i)*self._p(la,j) for j in range(N)] for i in range(N)]
        tau = {(0,0):1+lh*la*rho,(1,0):1-la*rho,(0,1):1-lh*rho,(1,1):1+rho}
        for i in range(N):
            for j in range(N):
                if (i,j) in tau: M[i][j] *= tau[(i,j)]
        tot = sum(map(sum,M)) or 1.0
        M = [[v/tot for v in r] for r in M]
        p1 = sum(M[i][j] for i in range(N) for j in range(N) if i>j)
        px = sum(M[i][i] for i in range(N))
        return p1,px,M
    def add(self,h,a,hg,ag,row=None,match_num=None,total=None,match_date=None):
        k = 48-32*min(1.0,(match_num or 0)/max(1,total or 1))
        rh,ra = self.elo.get(h,1500),self.elo.get(a,1500)
        eh = 1/(1+10**((ra-(rh+60))/400)); s = 1.0 if hg>ag else (0.5 if hg==ag else 0.0)
        self.elo[h] = rh+k*(s-eh); self.elo[a] = ra+k*((1-s)-(1-eh))
        t = self.st
        t[h]["hs"].append(hg); t[h]["hc"].append(ag); t[a]["as"].append(ag); t[a]["ac"].append(hg)
        t[h]["form"].append(3 if hg>ag else (1 if hg==ag else 0))
        t[a]["form"].append(3 if ag>hg else (1 if hg==ag else 0))
        self.hg.append(hg); self.ag.append(ag)
        div = (row or {}).get("Div") or "G" if isinstance(row,dict) else "G"
        self.lg_hg[div].append(hg); self.lg_ag[div].append(ag)
        self.h2h[(h,a)].append(hg-ag); self.h2h[(h,a)] = self.h2h[(h,a)][-8:]
        for team in (h,a):
            for key in t[team]: t[team][key] = t[team][key][-12:]
        if match_date:
            self.last_match_date[h] = match_date; self.last_match_date[a] = match_date
    def h2h_adjust(self,h,a,lh,la):
        hist = self.h2h.get((h,a),[]); n = len(hist)
        if n<6: return lh,la,n
        shrink = min(1.0,(n-5)/8.0); shift = (sum(hist)/n)*0.04*shrink
        return max(0.3,lh+shift/2),max(0.25,la-shift/2),n
    def predict(self,h,a,lg="G",match_date=None,cup=False):
        P0 = self.lp[lg]
        if len(self.lg_hg.get(lg,[]))>=20:
            lh_g = max(0.05,self._m(self.lg_hg[lg],1.5)); la_g = max(0.05,self._m(self.lg_ag[lg],1.2))
        else:
            lh_g = max(0.05,self._m(self.hg,1.5)); la_g = max(0.05,self._m(self.ag,1.2))
        sh,sa = self.st[h],self.st[a]
        ah_ = self._m(sh["hs"],lh_g)/lh_g; dh_ = self._m(sh["hc"],la_g)/la_g
        aa_ = self._m(sa["as"],la_g)/la_g; da_ = self._m(sa["ac"],lh_g)/lh_g
        fh,fa = self._form(h),self._form(a)
        lam_g_h = max(0.3,min(5.0,lh_g*ah_*da_*1.10*(0.85+0.30*fh)))
        lam_g_a = max(0.25,min(4.5,la_g*aa_*dh_*0.95*(0.85+0.30*fa)))
        lam_h,lam_a,h2h_n = self.h2h_adjust(h,a,lam_g_h,lam_g_a)
        gh = len(sh["hs"])+len(sh["as"]); ga = len(sa["hs"])+len(sa["as"])
        eh_eff = 1500+(self.elo.get(h,1500)-1500)*min(1.0,gh/10.0)
        ea_eff = 1500+(self.elo.get(a,1500)-1500)*min(1.0,ga/10.0)
        e = 1/(1+10**((ea_eff-eh_eff-60)/400))
        pde = 0.20+0.12*(1-abs(e-0.5)*2)
        p1,px,M = self._p1px(lam_h,lam_a,P0["rho"])
        f1 = P0["w_dc"]*p1+(1-P0["w_dc"])*e*(1-pde)
        fd = P0["w_dc"]*px+(1-P0["w_dc"])*pde
        f2 = max(0.0,1-f1-fd)
        games = min(gh,ga)
        c1 = self.calibrate(f1,0); cx = self.calibrate(fd,1); c2 = self.calibrate(f2,2)
        ct = c1+cx+c2 or 1.0; c1 /= ct; cx /= ct; c2 /= ct
        N = self.matrix_n
        over = 1-sum(self._p(lam_h+lam_a,k) for k in range(3))
        btts = sum(M[i][j] for i in range(1,N) for j in range(1,N))
        return {"p1":c1,"x":cx,"p2":c2,"p1_raw":f1,"x_raw":fd,"p2_raw":f2,"over":over,
                "btts":btts,"M":M,"agree":True,"lams":(lam_h,lam_a),
                "lams_g":(lam_g_h,lam_g_a),"games":games,
                "h2h_n":h2h_n,"e":e,"pde":pde}
    def learn_step(self,h,a,hg,ag,row=None,lg="G",match_num=None,total=None,match_date=None):
        P = self.predict(h,a,lg,match_date=match_date,cup=is_cup(lg))
        out = 0 if hg>ag else (1 if hg==ag else 2)
        self.calib_logits += [self._logit(P["p1_raw"]),self._logit(P["x_raw"]),self._logit(P["p2_raw"])]
        self.calib_outcomes += [1.0 if out==0 else 0.0,1.0 if out==1 else 0.0,1.0 if out==2 else 0.0]
        if len(self.calib_logits)>6000:
            del self.calib_logits[:-6000]; del self.calib_outcomes[:-6000]
        self.match_count += 1
        if self.match_count%150==0: self.refit_calibrator()
        if row is None: row = {}
        row["Div"] = lg
        self.add(h,a,hg,ag,row,match_num=match_num,total=total,match_date=match_date)
        return P

def manual_poisson(ha,hd,hf,he,aa,ad,af,ae,max_goals):
    LG_H,LG_A = 1.45,1.20
    lam_h = LG_H*(1+ha*0.25)*max(0.3,1-ad*0.20)*(1+hf*0.10)*(1+(he-1500)/1000*0.15)+0.25
    lam_a = LG_A*(1+aa*0.25)*max(0.3,1-hd*0.20)*(1+af*0.10)*(1+(ae-1500)/1000*0.15)
    lam_h = max(0.2,min(4.5,lam_h)); lam_a = max(0.2,min(4.5,lam_a))
    N = int(max_goals)
    M = [[math.exp(-lam_h)*lam_h**i/math.factorial(i)*math.exp(-lam_a)*lam_a**j/math.factorial(j)
         for j in range(N)] for i in range(N)]
    tot = sum(map(sum,M)) or 1.0
    p1 = sum(M[i][j] for i in range(N) for j in range(N) if i>j)/tot
    px = sum(M[i][i] for i in range(N))/tot
    p2 = max(0.0,1-p1-px)
    over = 1-sum(M[i][j] for i in range(N) for j in range(N) if i+j<=2)/tot
    btts = sum(M[i][j] for i in range(1,N) for j in range(1,N))/tot
    return {"p1":p1,"px":px,"p2":p2,"over":over,"btts":btts,"lam_h":lam_h,"lam_a":lam_a}
def evaluate_manual(prob,odd,bankroll,max_kelly,min_ev):
    fair = 1.0/max(prob,0.01); ev = prob*odd-1
    k = (prob*(odd-1)-(1-prob))/(odd-1) if odd>1 else 0.0
    k = max(0.0,min(k,max_kelly)); stake = round(k*bankroll,2)
    return {"probability":prob,"fair_odds":fair,"market_odds":odd,"ev":ev,
            "kelly":k,"stake":stake,"is_value":ev>=min_ev}
def build_alternatives(rows,main_pick):
    alt = []
    if main_pick in ("П1","X","П2"):
        for r in rows:
            if r["pick"] in ("П1","X","П2") and r["pick"]!=main_pick: alt.append(r)
            if len(alt)==2: break
    elif main_pick in ("ТБ 2.5","ТМ 2.5"):
        for r in rows:
            if r["pick"] in ("ТБ 2.5","ТМ 2.5") and r["pick"]!=main_pick: alt.append(r)
            elif r["pick"] in ("BTTS да","BTTS нет"): alt.append(r)
            if len(alt)==2: break
    elif main_pick in ("BTTS да","BTTS нет"):
        for r in rows:
            if r["pick"] in ("BTTS да","BTTS нет") and r["pick"]!=main_pick: alt.append(r)
            elif r["pick"] in ("ТБ 2.5","ТМ 2.5"): alt.append(r)
            if len(alt)==2: break
    return alt[:2]
def build_verdict(P,thr,bank,kelly_frac,h_name,a_name,fh,fa,h2h_n):
    probs = {"П1":P["p1"],"X":P["x"],"П2":P["p2"],"ТБ 2.5":P["over"],"ТМ 2.5":1-P["over"],
           "BTTS да":P["btts"],"BTTS нет":1-P["btts"]}
    names = {"П1":f"Победа {h_name}","X":"Ничья","П2":f"Победа {a_name}",
           "ТБ 2.5":"Тотал Больше 2.5","ТМ 2.5":"Тотал Меньше 2.5",
           "BTTS да":"Обе забьют — Да","BTTS нет":"Обе забьют — Нет"}
    rows = []
    for pick,prob in probs.items():
        prob = min(max(float(prob or 0.0),0.01),0.99)
        fair = 1.0/prob; est = fair*0.94
        rows.append({"pick":pick,"label":names[pick],"prob":prob,"odd":est,"fair_odd":fair})
    rows.sort(key=lambda r:-r["prob"])
    top = rows[0]; alt = build_alternatives(rows,top["pick"])
    reasons = []; lh,la = P["lams"]; tg = lh+la
    reasons.append(f"Модель ожидает {tg:.2f} голов (xG {lh:.2f}–{la:.2f})")
    if P["p1"]>0.45: reasons.append(f"{h_name} сильнее дома — форма: {fh}")
    elif P["p2"]>0.45: reasons.append(f"{a_name} сильнее на выезде — форма: {fa}")
    else: reasons.append(f"Команды близки — форма: {fh} vs {fa}")
    if tg>3.0: reasons.append("Результативный матч — ТБ 2.5 фаворит")
    elif tg<2.3: reasons.append("Низовой матч — ТМ 2.5 фаворит")
    if h2h_n>=6: reasons.append(f"Учтены {h2h_n} личных встреч")
    if top["prob"]>=0.80: conf,cc = "очень высокая","#34d399"
    elif top["prob"]>=0.72: conf,cc = "высокая","#34d399"
    elif top["prob"]>=0.65: conf,cc = "хорошая","#fbbf24"
    elif top["prob"]>=0.55: conf,cc = "средняя","#fbbf24"
    else: conf,cc = "низкая","#f87171"
    verdict = {"pick":top["pick"],"label":top["label"],"prob":top["prob"],"odd":top["odd"],
             "fair_odd":top["fair_odd"],"confidence":conf,"conf_color":cc,
             "reasons":reasons,"alternatives":alt,"is_action":top["prob"]>=thr}
    best = None
    if top["prob"]>=thr:
        stake = kelly(top["prob"],top["odd"],bank,kelly_frac)
        best = (_market_type(top["pick"]),top["pick"],top["odd"],top["prob"]*top["odd"]-1,top["prob"],stake)
    return verdict,rows,best

def refine_with_real_odds(verdict,rows,real_odds,bank,kelly_frac):
    for r in rows:
        ro = (real_odds or {}).get(r["pick"])
        if ro: r["odd"] = ro; r["real"] = True
        else: r["real"] = False
    pick = verdict["pick"]; real_odd = (real_odds or {}).get(pick)
    if not real_odd:
        verdict["real_odds"] = False; verdict["odd"] = None; verdict["ev"] = None
        return verdict,None
    prob = verdict["prob"]; ev = prob*real_odd-1
    verdict["odd"] = real_odd; verdict["real_odds"] = True; verdict["ev"] = ev
    best = None
    if verdict.get("is_action"):
        stake = kelly(prob,real_odd,bank,kelly_frac)
        if stake>0: best = (_market_type(pick),pick,real_odd,ev,prob,stake)
    return verdict,best

# ============================================================
# Data + Save
# ============================================================
def new_data():
    return {"version":DATA_VERSION,"bank":10000.0,"bets":[],"cards":[],"funnel":None,
            "report":[],"meta":{},"stats":{"won":0,"lost":0,"profit":0,"push":0,"void":0},
            "mode":"paper"}
def migrate(D):
    if not isinstance(D,dict): return new_data()
    base = new_data()
    for k in base:
        if k not in D or D[k] is None: D[k] = json.loads(json.dumps(base[k]))
    for key in ("cards","bets","report"):
        if not isinstance(D.get(key),list): D[key] = []
    D["cards"] = [c for c in D["cards"] if isinstance(c,dict) and isinstance(c.get("verdict"),dict)]
    if not isinstance(D.get("stats"),dict): D["stats"] = base["stats"]
    for s in ("won","lost","profit","push","void"): D["stats"].setdefault(s,0)
    if not isinstance(D.get("meta"),dict): D["meta"] = {}
    if "initial_bank" not in D["meta"]: D["meta"]["initial_bank"] = float(D.get("bank",10000.0))
    D["version"] = DATA_VERSION
    return D
def load_data():
    try:
        if os.path.exists(LOCAL_PATH):
            with open(LOCAL_PATH,"r",encoding="utf-8") as f:
                ld = json.load(f)
            if isinstance(ld,dict):
                data_part = ld.get("data") or ld
                return migrate(data_part)
    except Exception as e: log_err("load_data",e)
    return new_data()
def save_data(D):
    try:
        ld = {}
        if os.path.exists(LOCAL_PATH):
            try:
                with open(LOCAL_PATH,"r",encoding="utf-8") as f: ld = json.load(f)
            except Exception: ld = {}
        ld["data"] = json.loads(json.dumps(D,default=str))
        with open(LOCAL_PATH,"w",encoding="utf-8") as f:
            json.dump(ld,f,ensure_ascii=False,indent=2,default=str)
        return True
    except Exception as e:
        log_err("save_data",e); return True
def clone(D): return json.loads(json.dumps(D,default=str))

def cancel_bet(D,idx):
    D2 = clone(D)
    if idx<0 or idx>=len(D2["bets"]): return D2
    b = D2["bets"][idx]
    if b.get("status")!="pending": return D2
    D2["bank"] += float(b.get("stake") or 0.0); D2["bets"].pop(idx)
    return D2
def apply_settle(D,idx,outcome,score=None):
    D2 = clone(D)
    if idx<0 or idx>=len(D2["bets"]): return D2
    b = D2["bets"][idx]
    if b["status"]!="pending": return D2
    if score: b["score"] = score
    if outcome=="push":
        b["status"] = "push"; D2["bank"] += b["stake"]; D2["stats"]["push"] = D2["stats"].get("push",0)+1
    elif outcome=="void":
        b["status"] = "void"; D2["bank"] += b["stake"]; D2["stats"]["void"] = D2["stats"].get("void",0)+1
    elif outcome=="won":
        pr = b["stake"]*(b["odds"]-1); b["status"] = "won"; D2["bank"] += b["stake"]*b["odds"]
        D2["stats"]["won"] += 1; D2["stats"]["profit"] += pr
    elif outcome=="lost":
        b["status"] = "lost"; D2["stats"]["lost"] += 1; D2["stats"]["profit"] -= b["stake"]
    return D2

def auto_settle(D):
    D2 = clone(D); changed = 0; now = datetime.now()
    for idx,b in enumerate(D2["bets"][:]):
        if b.get("status")!="pending": continue
        fid = b.get("fixture_id"); dt_iso = b.get("date_iso") or b.get("date")
        bd = parse_date(dt_iso) if dt_iso else None
        if bd and bd>now: continue
        if not fid: continue
        res = tsdb_match_result(fid)
        if not res: continue
        hg,ag = res["home"],res["away"]
        status = res.get("status","")
        if status not in ("Match Finished","FT","AET","PEN"):
            continue
        outcome = determine_outcome(b.get("market"),b.get("pick"),hg,ag)
        if outcome is None: continue
        D2 = apply_settle(D2,idx,outcome,score=f"{hg}:{ag}"); changed += 1
    for idx,b in enumerate(D2["bets"][:]):
        if b.get("status")!="pending": continue
        dt_iso = b.get("date_iso") or b.get("date")
        bd = parse_date(dt_iso) if dt_iso else None
        if bd and now-bd>timedelta(hours=48):
            D2 = apply_settle(D2,idx,"void",score="void (no result)"); changed += 1
    return D2,changed

def stadium_bg(div): return STADIUM_WALLS.get(div,STADIUM_WALLS["DEFAULT"])
def render_verdict_card(c,thr):
    v = c.get("verdict") or {}
    if not v: return ""
    pick = v.get("label","—"); prob = v.get("prob",0); odd = v.get("odd")
    has_real = v.get("real_odds",False) and odd is not None
    conf = v.get("confidence","средняя"); cc = v.get("conf_color","#fbbf24")
    reasons = v.get("reasons",[]); is_action = v.get("is_action",False); alt = v.get("alternatives",[])
    parts = c.get("match","— vs —").split(" vs ")
    h = translate_team(parts[0]) if len(parts)>0 else "—"
    a = translate_team(parts[1]) if len(parts)>1 else "—"
    bg = stadium_bg(c.get("div",""))
    if is_action and has_real:
        mb = "linear-gradient(135deg,rgba(52,211,153,.25),rgba(16,185,129,.10))"; mbd = "rgba(52,211,153,.7)"
        mt = esc(f"🎯 СТАВЬ: {pick}")
    elif is_action:
        mb = "linear-gradient(135deg,rgba(251,191,36,.20),rgba(202,138,4,.08))"; mbd = "rgba(251,191,36,.6)"
        mt = esc(f"🤔 ВЫСОКАЯ P, НО БЕЗ КЭФА: {pick}")
    else:
        mb = "linear-gradient(135deg,rgba(148,163,184,.15),rgba(100,116,139,.08))"; mbd = "rgba(148,163,184,.4)"
        mt = esc(f"👀 ФОН: {pick}")
    fh = c.get("fh","—"); fa = c.get("fa","—")
    alt_html = ""
    for i,t in enumerate(alt):
        icon = "🥈" if i==0 else "🥉"
        alt_html += (f"<div style='display:flex;justify-content:space-between;padding:6px 0;"
                     f"border-top:1px solid rgba(255,255,255,.06);font-size:.85rem;'>"
                     f"<span>{icon} {esc(t.get('label','—'))}</span>"
                     f"<span><b style='color:#34d399'>{t.get('prob',0)*100:.1f}%</b> "
                     f"<span style='color:#8b93a7'>· кэф ~{t.get('odd',1):.2f}</span></span></div>")
    reasons_html = "".join(f"<li>{esc(r)}</li>" for r in reasons)
    warn = ""
    if is_action and not has_real:
        warn = ("<div style='color:#fde68a;font-size:.78rem;margin-top:8px;'>⚠️ Реального кэфа нет — "
                "estimate odd (fair × 0.94). Добавь ключ The Odds API для реальных кэфов.</div>")
    llm_opinion = c.get("llm_opinion") or ""
    llm_html = ""
    if llm_opinion:
        llm_html = (f"<div style='background:rgba(139,92,246,.12);border:1px solid rgba(139,92,246,.35);"
                    f"border-radius:10px;padding:10px 14px;margin-top:10px;'>"
                    f"<div style='color:#c4b5fd;font-size:.72rem;text-transform:uppercase;font-weight:700;"
                    f"margin-bottom:4px;letter-spacing:1px;'>🤖 Мнение ИИ-аналитика</div>"
                    f"<div style='color:#e9d5ff;font-size:.88rem;line-height:1.5;'>{esc(llm_opinion)}</div></div>")
    return f"""
<div class="vcard" style="background:{bg};border:1px solid rgba(255,255,255,.10);border-radius:20px;padding:0;margin-bottom:14px;overflow:hidden;">
  <div style="padding:16px 20px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <div><span style="background:rgba(34,211,238,.14);color:#a5f3fc;padding:3px 10px;border-radius:999px;font-size:.7rem;font-weight:700;">{esc(c.get('league','—'))}</span>
        <span style="background:rgba(251,191,36,.14);color:#fde68a;padding:3px 10px;border-radius:999px;font-size:.7rem;font-weight:700;margin-left:6px;">{esc(c.get('date','—'))}</span></div>
      <div style="font-size:.75rem;color:#8b93a7;">📚 {c.get('games',0)} игр</div></div>
    <div style="font-size:1.4rem;font-weight:800;color:#fff;margin-bottom:6px;text-shadow:0 2px 8px rgba(0,0,0,.8);">{esc(h)} <span style="color:#8b93a7;font-weight:400;">—</span> {esc(a)}</div>
    <div style="font-size:.78rem;color:#8b93a7;margin-bottom:14px;">Форма: <b style="color:#34d399;">{esc(fh)}</b> · <b style="color:#f87171;">{esc(fa)}</b></div></div>
  <div style="background:{mb};border-top:1px solid {mbd};border-bottom:1px solid {mbd};padding:14px 20px;">
    <div style="font-size:1.15rem;font-weight:900;color:#fff;margin-bottom:8px;">{mt}</div>
    <div style="display:flex;gap:20px;font-size:.9rem;color:#e6eaf2;">
      <div>Вероятность: <b style="color:#34d399;font-size:1.1rem;">{prob*100:.0f}%</b></div>
      <div>Кэф букмекера: <b style="color:#a5f3fc;font-size:1.1rem;">{f"{odd:.2f}" if has_real else "нет данных"}</b></div>
      <div>Уверенность: <b style="color:{cc};">{esc(conf)}</b></div></div>{warn}</div>
  <div style="padding:14px 20px;">
    <div style="color:#7dd3fc;font-size:.72rem;text-transform:uppercase;font-weight:700;margin-bottom:8px;letter-spacing:1px;">Почему</div>
    <ul style="margin:0 0 14px 0;padding-left:18px;color:#c9d2e3;font-size:.85rem;line-height:1.6;">{reasons_html}</ul>
    <div style="color:#7dd3fc;font-size:.72rem;text-transform:uppercase;font-weight:700;margin-bottom:6px;letter-spacing:1px;">Альтернативы</div>{alt_html}{llm_html}</div></div>"""

# ============================================================
# UI
# ============================================================
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
html,body,#root,.stApp,.stApp>div,[data-testid="stAppViewContainer"],[data-testid="stAppViewContainer"]>div,
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stBottom"],[data-testid="stBottom"]>div,
[data-testid="stAppViewBlockContainer"],[data-testid="stVerticalBlock"],section.main,section.main>div,.main,.main>div,.block-container{
background-color:#05070f!important;background-image:linear-gradient(180deg,#05070f 0%,#0b0f1a 50%,#05070f 100%)!important;}
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
.betcard.pending{border-left-color:#fbbf24;}.betcard.won{border-left-color:#34d399;}
.betcard.lost{border-left-color:#f87171;}.betcard.push{border-left-color:#94a3b8;}
.betcard.void{border-left-color:#64748b;opacity:.7;}
.betcard .score{font-weight:900;padding:2px 10px;border-radius:9px;margin-left:6px;background:rgba(52,211,153,.25);color:#6ee7b7;}
.nbr-loader{display:flex;align-items:center;gap:14px;padding:18px;background:rgba(10,14,24,.72);border:1px solid rgba(34,211,238,.35);border-radius:16px;margin-bottom:12px;}
.nbr-ring{width:36px;height:36px;border-radius:50%;border:3px solid rgba(34,211,238,.2);border-top-color:#22d3ee;animation:nbr-spin 1s linear infinite;flex-shrink:0;}
@keyframes nbr-spin{to{transform:rotate(360deg);}}
.nbr-text{flex:1;color:#a5f3fc;font-size:.95rem;}.nbr-text b{color:#fff;}
.nbr-dots::after{content:'';animation:nbr-dots 1.4s steps(4,end) infinite;}
@keyframes nbr-dots{0%{content:'';}25%{content:'.';}50%{content:'..';}75%{content:'...';}}
.nbr-bar{height:6px;background:rgba(255,255,255,.08);border-radius:3px;overflow:hidden;margin-top:8px;}
.nbr-bar-fill{height:100%;background:linear-gradient(90deg,#22d3ee,#a78bfa,#f472b6);background-size:200% 100%;animation:nbr-bar-move 2s linear infinite;border-radius:3px;transition:width .4s ease;}
@keyframes nbr-bar-move{0%{background-position:0% 0%;}100%{background-position:200% 0%;}}
</style>""",unsafe_allow_html=True)

@st.cache_data(ttl=30,show_spinner=False)
def cached_sqlite_status(): return sqlite_status()
@st.cache_data(ttl=30,show_spinner=False)
def cached_clv_summary(): return clv_summary()
@st.cache_data(ttl=30,show_spinner=False)
def cached_drawdown_stats(ib): return drawdown_stats(initial_bank=ib)
@st.cache_data(ttl=30,show_spinner=False)
def cached_sharpe_ratio(ib): return sharpe_ratio(initial_bank=ib)
@st.cache_data(ttl=30,show_spinner=False)
def cached_db_fetch_bets(status=None,limit=100000): return db_fetch_bets(status=status,limit=limit)
@st.cache_data(ttl=30,show_spinner=False)
def cached_db_bank_history(limit=5000): return db_bank_history(limit=limit)

_db_ok = db_init()
if not _db_ok:
    st.error(f"❌ SQLite не инициализирована: {SQLITE_BOOT_ERROR}")
if "data" not in st.session_state: st.session_state.data = load_data()
D = st.session_state.data
if "meta" not in D: D["meta"] = {}
if CLOUD_LLM_API_KEY and not D["meta"].get("llm_api_key"): D["meta"]["llm_api_key"] = CLOUD_LLM_API_KEY
if CLOUD_LLM_PROVIDER and not D["meta"].get("llm_provider"): D["meta"]["llm_provider"] = CLOUD_LLM_PROVIDER
if CLOUD_ODDS_KEY and not D["meta"].get("odds_api_key"): D["meta"]["odds_api_key"] = CLOUD_ODDS_KEY
if "initial_bank" not in D["meta"]:
    D["meta"]["initial_bank"] = float(D.get("bank",10000.0)); save_data(D)
_now_ts = time.time(); _last_auto = st.session_state.get("_last_auto_settle_ts",0)
if _now_ts-_last_auto>AUTO_SETTLE_THROTTLE_SEC:
    D2,n = auto_settle(D)
    if n>0:
        st.session_state.data = D2; save_data(D2)
        if use_sqlite_enabled():
            sync_bets_to_sqlite(D2); db_log_bank(D2.get("bank",10000.0),event="auto_settle")
            for f_ in (cached_sqlite_status,cached_clv_summary,cached_drawdown_stats,
                       cached_sharpe_ratio,cached_db_fetch_bets,cached_db_bank_history): f_.clear()
        D = D2; st.toast(f"Авто-закрыто {n} ставок",icon="🔄")
    st.session_state["_last_auto_settle_ts"] = _now_ts
pending_count = sum(1 for b in D["bets"] if isinstance(b,dict) and b.get("status")=="pending")
st.markdown(f"""
<div class="hero"><h1>NEURO BET PRO</h1>
<p>v{APP_VERSION} · 🆓 100% БЕСПЛАТНО · 🤖 ИИ-аналитик · 📥 прогнозы→портфель · 🗄 SQLite</p>
<div class="kpis">
 <div class="kpi"><div class="t">Банкролл</div><div class="v y">{D['bank']:.0f} у.е.</div></div>
 <div class="kpi"><div class="t">В работе</div><div class="v">{pending_count}</div></div>
 <div class="kpi"><div class="t">Всего ставок</div><div class="v">{len(D['bets'])}</div></div>
 <div class="kpi"><div class="t">Ошибок</div><div class="v {'r' if ERR else 'g'}">{len(ERR)}</div></div>
</div></div>""",unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Настройки")
    st.markdown(f"""
<div style="background:rgba(34,197,94,.10);border:1px solid rgba(34,197,94,.4);border-radius:12px;padding:10px 14px;margin-bottom:10px;">
<div style="color:#86efac;font-size:.7rem;text-transform:uppercase;font-weight:700;">🆓 Источники (ВСЕ БЕСПЛАТНЫЕ)</div>
<div style="font-size:.78rem;color:#e6eaf2;line-height:1.5;">
✅ football-data.co.uk — история + кэфы Pinnacle<br>
✅ TheSportsDB — матчи дня + авто-сеттл<br>
✅ The Odds API — 500 запросов/мес бесплатно<br>
🤖 LLM-аналитик — Gemini/Grok/Groq (бесплатно)</div></div>""",unsafe_allow_html=True)
    st.markdown(f"""
<div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.10);border-radius:12px;padding:10px 14px;margin-bottom:10px;">
<div style="color:#7dd3fc;font-size:.7rem;text-transform:uppercase;font-weight:700;">🗄 SQLite</div>
<div style="font-size:.75rem;color:#e6eaf2;">Status: <b style="color:{'#34d399' if SQLITE_BOOT_OK else '#f87171'};">{'OK' if SQLITE_BOOT_OK else 'FAIL'}</b> · exists: <b>{os.path.exists(DB_FILE)}</b></div></div>""",unsafe_allow_html=True)
    o_used = int(odds_usage_load().get("count",0)); o_rem = max(0,ODDS_LIMIT_DAILY-o_used)
    st.markdown(f"""
<div style="background:rgba(34,197,94,.10);border:1px solid rgba(34,197,94,.35);border-radius:12px;padding:10px 14px;margin-bottom:10px;">
<div style="color:#86efac;font-size:.7rem;text-transform:uppercase;font-weight:700;">📊 The Odds API</div>
<div style="font-size:1.3rem;font-weight:800;color:{'#86efac' if o_rem>10 else '#fbbf24'};">{o_rem} / {ODDS_LIMIT_DAILY}</div>
<div style="color:#8b93a7;font-size:.75rem;">реальных кэфов букмекеров сегодня</div></div>""",unsafe_allow_html=True)
    s_used = int(settle_usage_load().get("count",0)); s_rem = max(0,AUTO_SETTLE_LIMIT-s_used)
    st.markdown(f"""
<div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.10);border-radius:12px;padding:10px 14px;margin-bottom:10px;">
<div style="color:#7dd3fc;font-size:.7rem;text-transform:uppercase;font-weight:700;">Auto-settle (TheSportsDB)</div>
<div style="font-size:1.3rem;font-weight:800;color:{'#34d399' if s_rem>10 else '#fbbf24'};">{s_rem} / {AUTO_SETTLE_LIMIT}</div></div>""",unsafe_allow_html=True)
    llm_used = int(llm_usage_load().get("count",0)); llm_rem = max(0,LLM_DAILY_LIMIT-llm_used)
    st.markdown(f"""
<div style="background:rgba(139,92,246,.10);border:1px solid rgba(139,92,246,.35);border-radius:12px;padding:10px 14px;margin-bottom:10px;">
<div style="color:#c4b5fd;font-size:.7rem;text-transform:uppercase;font-weight:700;">🤖 LLM-аналитик</div>
<div style="font-size:1.3rem;font-weight:800;color:{'#c4b5fd' if llm_rem>5 else '#fbbf24'};">{llm_rem} / {LLM_DAILY_LIMIT}</div></div>""",unsafe_allow_html=True)
    if use_sqlite_enabled():
        s = cached_sqlite_status(); clv = cached_clv_summary()
        ib = float(D.get("meta",{}).get("initial_bank",10000.0))
        dd = cached_drawdown_stats(ib); shp = cached_sharpe_ratio(ib)
        st.markdown(f"""
<div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.10);border-radius:12px;padding:10px 14px;margin-bottom:10px;">
<div style="color:#7dd3fc;font-size:.7rem;text-transform:uppercase;font-weight:700;">📈 CLV / 📉 DD</div>
<div style="font-size:.85rem;color:#e6eaf2;">CLV: <b style="color:{'#34d399' if clv['avg_clv']>0 else '#f87171'}">{clv['avg_clv']*100:+.2f}%</b> (N={clv['n']})</div>
<div style="font-size:.85rem;color:#e6eaf2;">Max DD: <b style="color:#f87171">-{dd['max_dd_pct']*100:.1f}%</b> · Sharpe: <b>{shp:.2f}</b></div></div>""",unsafe_allow_html=True)
    if st.button("♻️ Сбросить все счётчики"):
        settle_usage_reset(); llm_usage_reset(); odds_usage_reset()
        st.toast("Счётчики сброшены",icon="♻️"); st.rerun()
    st.success("💾 Local mode",icon="💾")
    st.markdown("**🔑 Ключи (всё бесплатно)**")
    odds_key = st.text_input("The Odds API (500/мес бесплатно)",
                             value=D.get("meta",{}).get("odds_api_key",""),type="password",
                             help="Получи на the-odds-api.com → Dashboard → API Key")
    if odds_key!=D.get("meta",{}).get("odds_api_key",""):
        D["meta"]["odds_api_key"] = odds_key; save_data(D)
    st.caption("Без ключа кэфы = estimate (fair × 0.94)")
    st.markdown("**🤖 ИИ-аналитик**")
    _prov_keys = list(LLM_PROVIDERS.keys())
    _cur = D.get("meta",{}).get("llm_provider","Groq (бесплатно, быстро)")
    llm_prov = st.selectbox("Провайдер",_prov_keys,index=_prov_keys.index(_cur) if _cur in _prov_keys else 0)
    cur_prov = LLM_PROVIDERS[llm_prov]
    st.caption(f"Получить ключ: [{cur_prov['key_url']}]({cur_prov['key_url']})")
    llm_key = st.text_input("LLM API Key",value=D.get("meta",{}).get("llm_api_key",""),type="password")
    llm_model = st.text_input("Модель (override)",value=D.get("meta",{}).get("llm_model",""),
                              placeholder=cur_prov["model"])
    if llm_prov!=D.get("meta",{}).get("llm_provider") or llm_key!=D.get("meta",{}).get("llm_api_key") or llm_model!=D.get("meta",{}).get("llm_model",""):
        D["meta"]["llm_provider"] = llm_prov
        D["meta"]["llm_api_key"] = llm_key
        D["meta"]["llm_model"] = llm_model
        save_data(D)
    st.markdown("**🎯 Минимальная вероятность**")
    min_prob = st.slider("",50,85,55,1,label_visibility="collapsed")/100
    st.caption(f"Порог: **{min_prob*100:.0f}%**")
    kelly_frac = st.slider("Келли (доля)",0.10,0.40,0.25,0.05)
    matrix_n = st.slider("🧮 Матрица голов",6,15,12,1)
    st.info("⚠️ Используйте проверенные кэфы. Модель не гарантирует прибыль.")
    with st.expander(f"🐞 Ошибки ({len(ERR)})"):
        for line in ERR[-15:]: st.text(line)
    if st.button("🧹 Очистить лог"):
        ERR.clear(); st.rerun()
    if "confirm_clear" not in st.session_state: st.session_state.confirm_clear = False
    if not st.session_state.confirm_clear:
        if st.button("🗑 Очистить портфель"):
            st.session_state.confirm_clear = True; st.rerun()
    else:
        st.warning("⚠️ Удалить ВСЕ ставки и сбросить банк?")
        cc1,cc2 = st.columns(2)
        if cc1.button("✅ Да",key="confirm_yes"):
            D["bets"] = []; D["cards"] = []; D["bank"] = 10000.0
            D["stats"] = {"won":0,"lost":0,"profit":0,"push":0,"void":0}
            D["meta"]["initial_bank"] = 10000.0; save_data(D)
            for f_ in (cached_sqlite_status,cached_clv_summary,cached_drawdown_stats,
                       cached_sharpe_ratio,cached_db_fetch_bets,cached_db_bank_history): f_.clear()
            st.session_state.confirm_clear = False; st.rerun()
        if cc2.button("❌ Нет",key="confirm_no"):
            st.session_state.confirm_clear = False; st.rerun()

tab1,tab2,tab3,tab4,tab5 = st.tabs(["🏟 Сканер","💼 Портфель","📈 Статистика","🧮 Калькулятор PRO","🧪 Бэктест"])

with tab1:
    c1,c2 = st.columns([4,1])
    days = c1.slider("Горизонт, дней",1,14,7)
    scan = c2.button("⚡ СКАН",type="primary",disabled=st.session_state.get("_scan_in_progress",False))
    if scan:
        st.session_state["_scan_in_progress"] = True
        try:
            loader_ph = st.empty(); log_ph = st.empty()
            def update_loader(text,pct,logs=None):
                loader_ph.markdown(f"""
<div class="nbr-loader"><div class="nbr-ring"></div>
<div class="nbr-text"><b>{text}</b><span class="nbr-dots"></span>
<div class="nbr-bar"><div class="nbr-bar-fill" style="width:{pct*100:.0f}%"></div></div></div></div>""",unsafe_allow_html=True)
                if logs:
                    log_ph.markdown("<div style='color:#8b93a7;font-size:.8rem;background:rgba(10,14,24,.6);padding:10px;border-radius:10px;max-height:180px;overflow-y:auto'>"+"<br>".join(logs[-10:])+"</div>",unsafe_allow_html=True)
            today = datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
            logs = []
            def safe_filter(rows):
                if not isinstance(rows,list): return []
                return [r for r in rows if isinstance(r,dict) and r.get("HomeTeam") and r.get("AwayTeam")]
            update_loader("📡 Сбор матчей...",0.05,logs)
            tsdb_rows = safe_filter(tsdb_today_matches(days))
            logs.append(f"📡 TheSportsDB (дней {days}): {len(tsdb_rows)} матчей")
            seen = set(); src_rows = []
            for r in tsdb_rows:
                h = r.get("HomeTeam"); a = r.get("AwayTeam")
                if not h or not a: continue
                k = (h,a,r.get("Date"))
                if k in seen: continue
                seen.add(k); src_rows.append(r)
            logs.append(f"🔗 Уникальных: {len(src_rows)}")
            cur_year = today.year if today.month>=7 else today.year-1
            prev_year = cur_year-1
            trained = 0
            engine = None
            try:
                eng_key = "neuro_engine_v1297"
                eng_cached = disk_cache_get(eng_key,86400*14)
                if eng_cached and eng_cached.get("fp")==APP_VERSION:
                    engine = eng_cached.get("engine")
                    trained = getattr(engine,"trained_n",0)
                    logs.append(f"💾 Engine из кэша (обучено {trained})")
            except Exception: engine = None
            if engine is None:
                train_divs = ["E0","SP1","I1","D1","F1","E1","SP2","I2","D2","F2","N1","B1","P1","T1","R1"]
                engine = Engine(matrix_n=matrix_n); dp,dc = {},{}
                for i,dv in enumerate(train_divs):
                    pct = 0.1+(i+1)/len(train_divs)*0.4
                    update_loader(f"История [{i+1}/{len(train_divs)}] — {DIV_NAMES.get(dv,dv)}",pct,logs)
                    dp[dv] = load_seasonal(dv,_season_str(prev_year))
                    dc[dv] = load_seasonal(dv,_season_str(cur_year))
                    if len(dp[dv])<20:
                        dp[dv] = dp[dv] + tsdb_past_league(DIV_TO_TSDB.get(dv,""),limit=60)
                    if len(dc[dv])<20:
                        dc[dv] = dc[dv] + tsdb_past_league(DIV_TO_TSDB.get(dv,""),limit=60)
                    logs.append(f"✅ {DIV_NAMES.get(dv,dv)}: {len(dp[dv])+len(dc[dv])}")
                total_matches = sum(len(dp.get(dv,[]))+len(dc.get(dv,[])) for dv in train_divs)
                processed = 0
                for dv in train_divs:
                    for src in (dp.get(dv,[]),dc.get(dv,[])):
                        for r in src:
                            try:
                                hg = float(r.get("FTHG",0)); ag = float(r.get("FTAG",0))
                                engine.learn_step(r["HomeTeam"],r["AwayTeam"],hg,ag,r,
                                                  lg=dv,match_num=processed,total=total_matches,
                                                  match_date=parse_date(r.get("Date","")))
                                trained += 1
                            except Exception as e: log_err(f"train {dv}",e)
                            processed += 1
                            if processed%50==0:
                                update_loader(f"Обучение [{processed}/{total_matches}]",
                                              0.5+processed/max(1,total_matches)*0.3,logs)
                engine.trained_n = trained
                try: disk_cache_put("neuro_engine_v1297",{"fp":APP_VERSION,"engine":engine})
                except Exception: pass
                logs.append(f"🧠 Обучено: {trained}")
            update_loader("Анализ матчей...",0.85,logs)
            cards = []; matches_with_best = 0
            odds_key = D.get("meta",{}).get("odds_api_key","")
            for r in src_rows:
                d = parse_date(r.get("Date",""))
                if not d or not (today<=d<=today+timedelta(days=days)): continue
                h_en = (r.get("HomeTeam") or "").strip(); a_en = (r.get("AwayTeam") or "").strip()
                if not h_en or not a_en: continue
                h_ru = translate_team(h_en); a_ru = translate_team(a_en)
                lg = r.get("Div") or "G"
                P = engine.predict(h_en,a_en,lg,match_date=d,cup=is_cup(lg))
                fh = engine.form_str(h_en); fa = engine.form_str(a_en)
                verdict,rows,_ = build_verdict(P,min_prob,D["bank"],kelly_frac,h_ru,a_ru,fh,fa,P.get("h2h_n",0))
                best = None
                if verdict.get("is_action"):
                    sport_key = DIV_TO_ODDS.get(lg)
                    real_odds = None
                    if sport_key and odds_key and odds_usage_remaining()>0 and matches_with_best<15:
                        real_odds = odds_api_fixture(sport_key,h_en,a_en,odds_key)
                    if real_odds:
                        verdict,best = refine_with_real_odds(verdict,rows,real_odds,D["bank"],kelly_frac)
                    # [FIX v12.9.7] Прогноз ВСЕГДА идёт в портфель:
                    # если Kelly=0 (EV мал) или нет кэфов — минимальная ставка 1%
                    if best is None:
                        est_odd = (real_odds or {}).get(verdict["pick"]) or verdict.get("odd") or verdict.get("fair_odd")
                        if est_odd and est_odd>1.01:
                            prob_ = verdict["prob"]
                            ev_ = prob_*est_odd-1
                            min_stake = round(D["bank"]*0.01,2)
                            stake_ = max(kelly(prob_,est_odd,D["bank"],kelly_frac), min_stake)
                            verdict["real_odds"] = bool(real_odds)
                            verdict["odd"] = est_odd; verdict["ev"] = ev_
                            verdict["odds_source"] = ("market" if real_odds else "estimated")
                            best = (_market_type(verdict["pick"]),verdict["pick"],est_odd,ev_,prob_,stake_)
                            logs.append(f"📥 {h_ru} vs {a_ru}: прогноз в портфель @ {est_odd:.2f} · stake {stake_:.2f}")
                if best: matches_with_best += 1
                cards.append({"div":lg,"league":r.get("League") or DIV_NAMES.get(lg,"Лига"),
                    "match":f"{h_en} vs {a_en}","match_ru":f"{h_ru} — {a_ru}",
                    "date":d.strftime("%d.%m")+(f" {r.get('Time','')}" if r.get("Time") else ""),
                    "when":"сегодня" if d.date()==today.date() else "скоро","verdict":verdict,
                    "best":best,"games":P["games"],"fh":fh,"fa":fa,
                    "fixture_id":r.get("fixture_id"),"date_iso":d.strftime("%Y-%m-%d"),
                    "lam_h":P["lams"][0],"lam_a":P["lams"][1],
                    "p1":P["p1"],"px":P["x"],"p2":P["p2"],"over":P["over"],"btts":P["btts"]})
            logs.append(f"🎯 Найдено с P≥{min_prob*100:.0f}%: {matches_with_best}")
            llm_key_ = D.get("meta",{}).get("llm_api_key","")
            llm_prov_ = D.get("meta",{}).get("llm_provider","Groq (бесплатно, быстро)")
            llm_model_ = D.get("meta",{}).get("llm_model","")
            action_cards = [c for c in cards if c.get("best") is not None]
            action_cards.sort(key=lambda c:-(c.get("verdict",{}).get("prob") or 0))
            llm_done = 0
            for i_,card in enumerate(action_cards[:LLM_TOP_N]):
                if llm_usage_remaining()<=0:
                    logs.append(f"🤖 LLM: лимит запросов ({LLM_DAILY_LIMIT}/день)"); break
                if not llm_key_: break
                update_loader(f"🤖 ИИ-анализ [{i_+1}/{min(LLM_TOP_N,len(action_cards))}]",
                              0.90+0.08*(i_+1)/LLM_TOP_N, logs)
                v_ = card.get("verdict",{})
                ctx = {"api_key":llm_key_,"provider":llm_prov_,"model":llm_model_,
                       "home":card.get("match_ru","").split(" — ")[0] if " — " in card.get("match_ru","") else "",
                       "away":card.get("match_ru","").split(" — ")[1] if " — " in card.get("match_ru","") else "",
                       "league":card.get("league",""),"date":card.get("date",""),
                       "lam_h":card.get("lam_h",0),"lam_a":card.get("lam_a",0),
                       "p1":card.get("p1",0),"px":card.get("px",0),"p2":card.get("p2",0),
                       "over":card.get("over",0),"btts":card.get("btts",0),
                       "fh":card.get("fh","—"),"fa":card.get("fa","—"),
                       "h2h_n":0,"pick":v_.get("label",""),"prob":v_.get("prob",0),
                       "confidence":v_.get("confidence",""),"ev":v_.get("ev",0)}
                opinion = llm_analyze_match(ctx)
                if opinion:
                    card["llm_opinion"] = opinion; llm_done += 1
                    logs.append(f"🤖 {card.get('match_ru','')}: {opinion[:50]}...")
            if llm_done>0: logs.append(f"✅ LLM: {llm_done} мнений")
            elif not llm_key_: logs.append("🤖 LLM: ключ не задан — пропущено")
            # [FIX v12.9.7] Ставки из ВСЕХ прогнозов
            new_bets = []
            existing = {f"{b['match']}|{b['pick']}" for b in D["bets"] if isinstance(b,dict) and b.get("status")=="pending"}
            for c in cards:
                b = c.get("best")
                if not b: continue
                mkt,pick,odd,ev,prob,stake = b
                # [FIX] минимум 0.5% банка, максимум 5%
                stake = round(min(max(stake, D["bank"]*0.005), D["bank"]*0.05),2)
                if stake<=0: continue
                bk_ = f"{c['match']}|{pick}"
                if bk_ in existing: continue
                new_bets.append({"match":c["match"],"match_ru":c["match_ru"],"div":c["div"],
                    "league":c["league"],"market":mkt,"pick":pick,"odds":odd,"stake":stake,
                    "prob":prob,"status":"pending","strat":"value",
                    "odds_source":c.get("verdict",{}).get("odds_source","") or ("market" if c.get("verdict",{}).get("real_odds") else "estimated"),
                    "mode":D.get("mode","paper"),"date":datetime.now().strftime("%d.%m.%Y"),
                    "date_iso":c.get("date_iso",datetime.now().strftime("%Y-%m-%d")),
                    "date_time":datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "fixture_id":c.get("fixture_id"),"score":None,"ev":ev})
                existing.add(bk_)
            D2 = clone(D); D2["cards"] = cards; D2["report"] = logs
            D2["bets"] = D2["bets"]+new_bets
            total_stake = sum(b["stake"] for b in new_bets)
            D2["bank"] = max(0.0,D2["bank"]-total_stake)
            D2["funnel"] = {"trained":trained,"src":len(src_rows),"found":matches_with_best,
                          "added":len(new_bets),"frozen":total_stake,"llm":llm_done}
            st.session_state.data = D2; save_data(D2)
            if use_sqlite_enabled():
                sync_bets_to_sqlite(D2); db_log_bank(D2.get("bank",10000.0),event="scan")
                for f_ in (cached_sqlite_status,cached_clv_summary,cached_drawdown_stats,
                           cached_sharpe_ratio,cached_db_fetch_bets,cached_db_bank_history): f_.clear()
            update_loader(f"✅ Готово! +{len(new_bets)} ставок · 🤖 {llm_done} LLM",1.0,logs)
            time.sleep(1.5); loader_ph.empty(); log_ph.empty()
        finally:
            st.session_state["_scan_in_progress"] = False
        st.rerun()
    fn = D.get("funnel")
    if fn:
        st.success(f"🧠 Обучено {fn.get('trained',0)} · 🔗 источников {fn.get('src',0)} · "
                   f"🎯 найдено {fn.get('found',0)} · ➕ в портфель {fn.get('added',0)} · "
                   f"💰 заморожено {fn.get('frozen',0):.0f} · 🤖 LLM: {fn.get('llm',0)}")
    with st.expander("🔌 Диагностика"):
        for line in D.get("report",[]): st.text(line)
    all_cards = D.get("cards",[])
    cards_view = sorted([c for c in all_cards if isinstance(c,dict)],
                        key=lambda c:(c.get("verdict",{}).get("prob") or 0),reverse=True)
    shown = 0; hidden = 0
    for c in cards_view:
        v = c.get("verdict") or {}
        if not v.get("is_action",False): hidden += 1; continue
        st.markdown(render_verdict_card(c,min_prob),unsafe_allow_html=True); shown += 1
    if shown==0 and hidden==0: st.info("Нажми ⚡ СКАН.")
    elif shown==0 and hidden>0:
        st.warning(f"⚠️ Ни один матч не прошёл порог **{min_prob*100:.0f}%**. Скрыто **{hidden}**. Понизь порог до 50%.")
        with st.expander(f"👀 Показать {hidden} скрытых"):
            for c in cards_view:
                v = c.get("verdict") or {}
                if v.get("is_action",False): continue
                st.markdown(render_verdict_card(c,min_prob),unsafe_allow_html=True)
    elif hidden>0:
        st.caption(f"✅ Показано **{shown}** с P ≥ {min_prob*100:.0f}% · скрыто **{hidden}**")

with tab2:
    st.header("💼 Портфель")
    if not D["bets"]: st.warning("Пусто. После СКАНа ставки появятся здесь.")
    else:
        st.caption(f"Всего: {len(D['bets'])} · В работе: {pending_count}")
        if st.button("📥 Экспорт CSV"):
            buf = io.StringIO(); w = csv.writer(buf)
            w.writerow(["Match","League","Pick","Market","Odds","OddsSource","Stake","Prob","EV","Status","Score","Date"])
            for b in D["bets"]:
                if not isinstance(b,dict): continue
                md_ = b.get("match_ru") or translate_match(b.get("match",""))
                w.writerow([md_,b.get("league",""),b.get("pick",""),b.get("market",""),
                            b.get("odds",""),b.get("odds_source",""),b.get("stake",""),
                            b.get("prob",""),b.get("ev",""),b.get("status",""),
                            b.get("score",""),b.get("date","")])
            st.download_button("⬇️ Скачать",buf.getvalue(),
                               file_name=f"neuro_bets_{datetime.now():%Y%m%d_%H%M}.csv",mime="text/csv")
        for i,b in enumerate(D["bets"]):
            if not isinstance(b,dict): continue
            st_ = b.get("status","pending")
            icon = {"pending":"⏳","won":"🟢","lost":"🔴","push":"⚪","void":"⬜"}.get(st_,"⏳")
            score = f" — счёт {b.get('score','')}" if b.get("score") else ""
            prob = float(b.get("prob") or 0); odds = float(b.get("odds") or 1.0); stake = float(b.get("stake") or 0.0)
            ev_ = float(b.get("ev") or 0)
            md_ = b.get("match_ru") or translate_match(b.get("match","—"))
            odds_src = b.get("odds_source","")
            src_badge = "🎯 market" if odds_src=="market" else ("📐 estimate" if odds_src=="estimated" else "—")
            st.markdown(f"""
<div class="betcard {st_}" style="padding:14px 18px;">
 <div style="display:flex;justify-content:space-between;align-items:flex-start;">
  <div><div style="font-size:1rem;font-weight:800;color:#fff;">{icon} {esc(md_)}{score}</div>
   <div style="color:#8b93a7;font-size:.78rem;margin-top:4px;">{esc(str(b.get('league','—')))} · {esc(str(b.get('date','—')))} · {src_badge}</div></div>
  <div style="text-align:right;"><div style="color:#fbbf24;font-size:1.1rem;font-weight:800;">{esc(str(b.get('pick','—')))}</div>
   <div style="color:#34d399;font-weight:700;">P {prob*100:.0f}% · EV {ev_*100:+.1f}%</div></div></div>
 <div style="color:#c9d2e3;font-size:.82rem;margin-top:8px;">Кэф: <b>{odds:.2f}</b> · Ставка: <b>{stake:.2f} у.е.</b></div></div>""",unsafe_allow_html=True)
            if b.get("status")=="pending":
                cc = st.columns([1,1,1,1])
                sin = cc[0].text_input("Счёт",key=f"sc{i}",label_visibility="collapsed",placeholder="2:1")
                sc = sin.strip() if re.match(r"^\d+\s*:\s*\d+$",sin.strip()) else None
                if cc[1].button("✅",key=f"w{i}"):
                    st.session_state.data = apply_settle(D,i,"won",score=sc); save_data(st.session_state.data)
                    if use_sqlite_enabled():
                        sync_bets_to_sqlite(st.session_state.data)
                        db_log_bank(st.session_state.data.get("bank",10000.0),event="manual_settle")
                        for f_ in (cached_sqlite_status,cached_clv_summary,cached_drawdown_stats,cached_sharpe_ratio,cached_db_fetch_bets,cached_db_bank_history): f_.clear()
                    st.rerun()
                if cc[2].button("❌",key=f"l{i}"):
                    st.session_state.data = apply_settle(D,i,"lost",score=sc); save_data(st.session_state.data)
                    if use_sqlite_enabled():
                        sync_bets_to_sqlite(st.session_state.data)
                        db_log_bank(st.session_state.data.get("bank",10000.0),event="manual_settle")
                        for f_ in (cached_sqlite_status,cached_clv_summary,cached_drawdown_stats,cached_sharpe_ratio,cached_db_fetch_bets,cached_db_bank_history): f_.clear()
                    st.rerun()
                if cc[3].button("🚫",key=f"c{i}"):
                    st.session_state.data = cancel_bet(D,i); save_data(st.session_state.data)
                    if use_sqlite_enabled():
                        sync_bets_to_sqlite(st.session_state.data)
                        db_log_bank(st.session_state.data.get("bank",10000.0),event="cancel")
                        for f_ in (cached_sqlite_status,cached_clv_summary,cached_drawdown_stats,cached_sharpe_ratio,cached_db_fetch_bets,cached_db_bank_history): f_.clear()
                    st.toast("Ставка отменена",icon="🚫"); st.rerun()

with tab3:
    st.header("📈 Статистика")
    s = D["stats"]; tot = s["won"]+s["lost"]
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Банк",f"{D['bank']:.2f}"); m2.metric("Ставок всего",len(D["bets"]))
    m3.metric("WinRate",f"{(s['won']/tot*100) if tot else 0:.1f}%")
    m4.metric("Profit",f"{s['profit']:+.2f}")
    if use_sqlite_enabled():
        st.divider(); st.subheader("🗄 SQLite + CLV + Drawdown")
        sb_ = cached_db_fetch_bets(status=None,limit=100000)
        if sb_:
            st.caption(f"SQLite: {len(sb_)} ставок")
        clv = cached_clv_summary(); ib = float(D.get("meta",{}).get("initial_bank",10000.0))
        dd = cached_drawdown_stats(ib); shp = cached_sharpe_ratio(ib)
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("CLV avg",f"{clv['avg_clv']*100:+.2f}%"); c2.metric("CLV N",clv["n"])
        c3.metric("Max DD",f"-{dd['max_dd_pct']*100:.1f}%"); c4.metric("Sharpe",f"{shp:.2f}")
        hist = cached_db_bank_history(limit=5000)
        if len(hist)>1:
            try:
                import pandas as pd
                df = pd.DataFrame(hist); st.line_chart(df.set_index("ts")["bank"])
            except Exception: pass

with tab4:
    st.header("🧮 Калькулятор PRO")
    ca,cb = st.columns(2)
    with ca:
        hn = st.text_input("Хозяева","Home FC")
        ha = st.slider("Атака хозяев",-2.0,2.0,0.25,0.05)
        hd = st.slider("Защита хозяев",-2.0,2.0,0.0,0.05)
        hf = st.slider("Форма хозяев",-1.0,1.0,0.1,0.05)
        he = st.number_input("Elo хозяев",1000,2200,1500,10)
    with cb:
        an = st.text_input("Гости","Away FC")
        aa = st.slider("Атака гостей",-2.0,2.0,0.0,0.05)
        ad = st.slider("Защита гостей",-2.0,2.0,0.15,0.05)
        af = st.slider("Форма гостей",-1.0,1.0,-0.05,0.05)
        ae = st.number_input("Elo гостей",1000,2200,1500,10)
    st.subheader("Рыночные коэффициенты 1X2")
    c1,c2,c3 = st.columns(3)
    o1 = c1.number_input("П1",1.01,100.0,2.10,0.01)
    ox = c2.number_input("X",1.01,100.0,3.30,0.01)
    o2 = c3.number_input("П2",1.01,100.0,3.40,0.01)
    mk_ = st.slider("Лимит Kelly",0.01,0.20,0.05,0.01)
    mev = st.slider("Минимальный EV",0.00,0.30,0.03,0.01)
    if st.button("Рассчитать",type="primary"):
        p = manual_poisson(ha,hd,hf,he,aa,ad,af,ae,matrix_n)
        m1,m2,m3,m4,m5 = st.columns(5)
        m1.metric("xG хозяев",f"{p['lam_h']:.2f}"); m2.metric("xG гостей",f"{p['lam_a']:.2f}")
        m3.metric("Тотал xG",f"{p['lam_h']+p['lam_a']:.2f}")
        m4.metric("Обе забьют",f"{p['btts']*100:.1f}%"); m5.metric("ТБ 2.5",f"{p['over']*100:.1f}%")
        rows = []
        for key,label,od in [("p1","П1",o1),("px","X",ox),("p2","П2",o2)]:
            v = evaluate_manual(p[key],od,D["bank"],mk_,mev)
            rows.append({"Исход":label,"Вероятность":f"{v['probability']*100:.1f}%",
                         "Fair":f"{v['fair_odds']:.2f}","Рынок":f"{v['market_odds']:.2f}",
                         "EV":f"{v['ev']*100:+.1f}%","Kelly":f"{v['kelly']*100:.1f}%","Ставка":f"{v['stake']:.2f}"})
        st.dataframe(rows,use_container_width=True,hide_index=True)

with tab5:
    st.header("🧪 Бэктест (walk-forward, кэфы Pinnacle)")
    st.caption("Источник: football-data.co.uk (бесплатно). EV против Pinnacle/B365.")
    b1,b2,b3,b4 = st.columns(4)
    bt_div = b1.selectbox("Лига",list(DIV_NAMES.keys()),format_func=lambda k:DIV_NAMES[k])
    bt_season = b2.selectbox("Сезон",["2526","2425","2324"],index=1)
    bt_edge = b3.slider("Мин. edge",0.00,0.15,0.03,0.01)
    bt_mode = b4.selectbox("Стейк",["Flat","Kelly"])
    if st.button("▶️ Прогнать",type="primary"):
        rows_all = load_seasonal(bt_div,bt_season)
        rows_all = [r for r in rows_all if r.get("FTHG") not in (None,"") and parse_date(r.get("Date",""))]
        rows_all.sort(key=lambda r:parse_date(r.get("Date","")))
        if len(rows_all)<150: st.error("Мало матчей для бэктеста.")
        else:
            engine = Engine(matrix_n=matrix_n); log = []; bank = 10000.0
            prog = st.progress(0.0); total_bt = len(rows_all)
            for j,r in enumerate(rows_all):
                h = (r.get("HomeTeam") or "").strip(); a = (r.get("AwayTeam") or "").strip()
                hg,ag = float(r["FTHG"]),float(r["FTAG"]); md = parse_date(r.get("Date",""))
                if j>=120:
                    P = engine.predict(h,a,bt_div,match_date=md,cup=is_cup(bt_div))
                    for pick,prob,odd in (("П1",P["p1"],_f(r.get("PSH")) or _f(r.get("B365H"))),
                                          ("X",P["x"],_f(r.get("PSD")) or _f(r.get("B365D"))),
                                          ("П2",P["p2"],_f(r.get("PSA")) or _f(r.get("B365A")))):
                        if not odd or odd<=1.01: continue
                        edge = prob-1.0/odd
                        if edge<bt_edge: continue
                        stake = kelly(prob,odd,bank,0.25) if bt_mode=="Kelly" else round(bank*0.01,2)
                        if stake<=0: continue
                        won = (pick=="П1" and hg>ag) or (pick=="X" and hg==ag) or (pick=="П2" and hg<ag)
                        pnl = stake*(odd-1) if won else -stake
                        bank += pnl
                        log.append({"pick":pick,"prob":round(prob,3),"odd":odd,"edge":round(edge,3),
                                    "stake":stake,"won":won,"pnl":round(pnl,2)})
                engine.learn_step(h,a,hg,ag,r,lg=bt_div,match_num=j,total=total_bt,match_date=md)
                if j%25==0: prog.progress(j/total_bt)
            prog.progress(1.0)
            if not log: st.warning("Сигналов нет (edge выше порога не встретился).")
            else:
                n = len(log); wins = sum(1 for x in log if x["won"]); profit = sum(x["pnl"] for x in log)
                staked = sum(x["stake"] for x in log)
                k1,k2,k3,k4 = st.columns(4)
                k1.metric("Ставок",n); k2.metric("WinRate",f"{wins/n*100:.1f}%")
                k3.metric("PnL",f"{profit:+.1f}")
                k4.metric("ROI",f"{profit/staked*100:+.2f}%" if staked else "0.00%")
                st.dataframe(log[-30:],use_container_width=True,hide_index=True)
