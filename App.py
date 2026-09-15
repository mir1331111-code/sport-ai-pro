import streamlit as st
import requests, csv, io, json, os, math, re
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="NEURO BET PRO v4", page_icon="🏟", layout="wide")
HISTORY_FILE = "neuro_bet_pro.json"
MATRIX_N = 9
REFIT_PLATT_EVERY = 150
REFIT_STRUCT_EVERY = 300

DIV_NAMES = {
    "E0":"🏴󠁢󠁮󠁿 АПЛ","E1":"🏴󠁢󠁮󠁿 Чемпионшип","SC0":"🏴󠁢󠁣󠁿 Шотландия",
    "D1":"🇩🇪 Бундеслига","D2":"🇩🇪 2. Бундеслига","I1":"🇮🇹 Серия A","I2":"🇮🇹 Серия B",
    "SP1":"🇪🇸 Ла Лига","SP2":"🇪🇸 Сегунда","F1":"🇫🇷 Лига 1","F2":"🇫🇷 Лига 2",
    "N1":"🇳 Эредивизи","B1":"🇧🇪 Про-лига","P1":"🇵 Примейра","T1":"🇹🇷 Суперлига",
    "G1":"🇬🇷 Греция","R1":"🇷🇺 РПЛ","BR1":"🇧 Бразилия","C1":"🏆 Лига Чемпионов","EL":"🏆 Лига Европы",
    "EC":"🏆 Лига Конференций"
}
TSDB_LEAGUES = {
    "432":"🏴󠁢󠁥󠁧 АПЛ","434":"🇪🇸 Ла Лига","435":"🇮🇹 Серия A","436":"🇩🇪 Бундеслига",
    "437":"🇫🇷 Лига 1","448":"🏆 Лига Чемпионов","442":"🇺🇸 MLS","439":"🇵 Примейра"
}
CORRIDORS = {"1X2":(1.40,4.20),"OU":(1.50,2.80),"AH":(1.60,2.60),"STAT":(1.40,4.50)}

# ===== ЧИТАЕМЫЙ UI: сплошной тёмный фон, явные цвета, без светлых пятен =====
st.markdown("""
<style>
html,body,.stApp{background:#070b14 !important;}
.stApp{background-image:none !important;}
.stMarkdown,.stMarkdown p,.stMarkdown li,.stMarkdown ul{color:#e2e8f0;}
.stCaption,.stCaption *,div[data-testid="stCaptionContainer"]{color:#94a3b8 !important;}
div[data-testid="stMetricValue"]{color:#f8fafc !important;}
div[data-testid="stMetricLabel"] p{color:#94a3b8 !important;}
div[data-testid="stMetricDelta"]{color:#4ade80 !important;}
.stTabs button p{color:#cbd5e1 !important;}
.stInfo,.stWarning,.stError,.stSuccess{color:#e2e8f0 !important;}
header,#MainMenu,footer{visibility:hidden}
.hero{padding:20px 26px;border-radius:22px;margin-bottom:16px;border:1px solid rgba(56,189,248,.35);
 background:linear-gradient(120deg,rgba(2,6,23,.96),rgba(6,78,59,.80) 55%,rgba(120,53,15,.75)),
 url('https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=1600&auto=format&fit=crop') center/cover;}
.hero h1{margin:0;font-size:2.3rem;font-weight:900;letter-spacing:1px;color:#ffffff;text-shadow:0 2px 10px rgba(0,0,0,.9)}
.hero p{margin:4px 0 0;color:#dbeafe;font-size:.92rem;text-shadow:0 1px 6px rgba(0,0,0,.9)}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:14px}
.kpi{background:rgba(2,6,23,.92);border:1px solid rgba(148,163,184,.28);border-radius:14px;padding:12px 16px}
.kpi .t{color:#7dd3fc;font-size:.68rem;text-transform:uppercase;letter-spacing:1.2px}
.kpi .v{font-size:1.45rem;font-weight:800;color:#ffffff}
.kpi .v.g{color:#4ade80}.kpi .v.y{color:#facc15}.kpi .v.r{color:#f87171}
.mcard{background:rgba(8,12,24,.96);border:1px solid rgba(148,163,184,.22);border-radius:16px;
 padding:16px 18px;margin-bottom:14px;transition:.2s}
.mcard:hover{border-color:rgba(56,189,248,.55);transform:translateY(-2px)}
.mcard.value{border-color:rgba(16,185,129,.65);box-shadow:0 0 26px rgba(16,185,129,.18)}
.mcard.hot{border-color:rgba(250,204,21,.6);box-shadow:0 0 26px rgba(250,204,21,.15)}
.mhead{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.chip{background:rgba(56,189,248,.18);color:#bae6fd;border:1px solid rgba(56,189,248,.45);
 padding:3px 10px;border-radius:999px;font-size:.72rem;font-weight:700}
.chip.when{background:rgba(250,204,21,.16);color:#fde68a;border-color:rgba(250,204,21,.45)}
.chip.warn{background:rgba(248,113,113,.18);color:#fecaca;border-color:rgba(248,113,113,.5)}
.badge{margin-left:auto;padding:4px 12px;border-radius:999px;font-size:.72rem;font-weight:800}
.badge.val{background:rgba(16,185,129,.22);color:#86efac;border:1px solid rgba(16,185,129,.6)}
.badge.hot{background:rgba(250,204,21,.2);color:#fde68a;border:1px solid rgba(250,204,21,.6)}
.badge.no{background:rgba(100,116,139,.2);color:#cbd5e1;border:1px solid rgba(100,116,139,.4)}
.teams{font-size:1.3rem;font-weight:800;color:#ffffff;margin:10px 0 2px}
.teams span{color:#94a3b8;font-weight:400}
.form5{font-size:.72rem;letter-spacing:2px;margin-bottom:6px;color:#cbd5e1}
.form5 b{padding:1px 5px;border-radius:4px;margin-right:2px}
.w{background:rgba(16,185,129,.3);color:#86efac}.d{background:rgba(148,163,184,.25);color:#e2e8f0}.l{background:rgba(239,68,68,.25);color:#fca5a5}
.bar{height:6px;background:rgba(148,163,184,.2);border-radius:99px;overflow:hidden;margin-top:4px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#38bdf8,#4ade80)}
.mrow{display:grid;grid-template-columns:70px 96px 1.1fr 70px 70px 62px 74px 26px;gap:8px;align-items:center;
 padding:6px 0;border-top:1px solid rgba(148,163,184,.14);font-size:.82rem;color:#e2e8f0}
.mrow.hdr{color:#94a3b8;font-size:.68rem;text-transform:uppercase;letter-spacing:.6px;border-top:none}
.ok{color:#4ade80;font-weight:800}.nok{color:#64748b;font-weight:800}
.evpos{color:#4ade80;font-weight:700}.evneg{color:#f87171;font-weight:700}
.mfoot{margin-top:10px;padding-top:10px;border-top:1px dashed rgba(148,163,184,.3);
 color:#cbd5e1;font-size:.78rem;display:flex;gap:16px;flex-wrap:wrap}
.mfoot b{color:#facc15}
.pickline{color:#f8fafc;font-size:.98rem;margin:6px 0}
.pickline b.y{color:#facc15}.pickline b.g{color:#4ade80}
.why{color:#cbd5e1;font-size:.82rem}
</style>""", unsafe_allow_html=True)

# ============ САМООБУЧАЮЩИЙСЯ ДВИЖОК ============
class Engine:
    def __init__(self):
        self.elo = {}
        self.st = defaultdict(lambda: {
            "hs":[], "hc":[], "as":[], "ac":[], "form":[],
            "cfh":[], "cah":[], "cfa":[], "caa":[],
            "yfh":[], "yah":[], "yfa":[], "yaa":[]
        })
        self.hg = []; self.ag = []
        self.h2h = defaultdict(list)
        # --- блоки самообучения ---
        self.calib = []            # (logit_p, outcome) для Platt
        self.platt_a = 0.0
        self.platt_b = 1.0
        self.history = []          # (lam_h, lam_a, e, pde, outcome) для refit rho/w
        self.rho = -0.13
        self.w_dc = 0.72
        self.match_count = 0
        self.market_roi = defaultdict(lambda: {"n":0, "profit":0.0})

    # ---------- математика ----------
    @staticmethod
    def _logit(p):
        p = min(max(p, 1e-6), 1 - 1e-6)
        return math.log(p / (1 - p))
    @staticmethod
    def _sigmoid(x):
        return 1.0 / (1.0 + math.exp(-max(-30, min(30, x))))
    def _m(self, l, d=1.0): return sum(l)/len(l) if l else d
    def _p(self, l, k): return math.exp(-l) * l**k / math.factorial(k)
    def _form(self, t):
        f = self.st[t]["form"][-5:]
        return (sum(f)/(len(f)*3)) if f else 0.5
    def form_str(self, t):
        return "".join({"3":"В","1":"Н","0":"П"}[str(int(x))] for x in self.st[t]["form"][-5:]) or "—"

    # ---------- Platt-калибровка (уровень 1) ----------
    def calibrate(self, p):
        return self._sigmoid(self.platt_a + self.platt_b * self._logit(p))
    def refit_platt(self):
        if len(self.calib) < 60: return
        data = self.calib[-3000:]
        a, b = self.platt_a, self.platt_b
        n = len(data)
        for _ in range(60):
            ga = gb = 0.0
            for x, y in data:
                p = self._sigmoid(a + b * x)
                err = p - y
                ga += err; gb += err * x
            a -= 0.08 * ga / n
            b -= 0.08 * gb / n
            b = min(max(b, 0.3), 3.0)
        self.platt_a, self.platt_b = a, b

    # ---------- walk-forward retraining rho и веса ансамбля (уровень 2) ----------
    def _probs_from(self, lam_h, lam_a, rho, w, e, pde):
        N = MATRIX_N
        M = [[self._p(lam_h, i) * self._p(lam_a, j) for j in range(N)] for i in range(N)]
        tau = {(0,0):1+lam_h*lam_a*rho, (1,0):1-lam_a*rho, (0,1):1-lam_h*rho, (1,1):1+rho}
        for i in range(N):
            for j in range(N):
                if (i,j) in tau: M[i][j] *= tau[(i,j)]
        tot = sum(map(sum, M)) or 1.0
        M = [[v/tot for v in r] for r in M]
        p1 = sum(M[i][j] for i in range(N) for j in range(N) if i>j)
        px = sum(M[i][i] for i in range(N))
        f1 = w*p1 + (1-w)*e*(1-pde)
        fd = w*px + (1-w)*pde
        f2 = max(1e-6, 1-f1-fd)
        return f1, fd, f2
    def refit_struct(self):
        if len(self.history) < 200: return
        win = self.history[-200:]
        best = None
        for rho in (-0.20, -0.13, -0.06, 0.0):
            for w in (0.60, 0.72, 0.85):
                ll = 0.0
                for lam_h, lam_a, e, pde, out in win:
                    f1, fd, f2 = self._probs_from(lam_h, lam_a, rho, w, e, pde)
                    ps = (f1, fd, f2)
                    ll -= math.log(min(max(ps[out], 1e-6), 1-1e-6))
                if best is None or ll < best[0]:
                    best = (ll, rho, w)
        if best:
            self.rho, self.w_dc = best[1], best[2]

    # ---------- multi-armed bandit по рынкам (уровень 4) ----------
    def record_market(self, mkt, won, odd):
        r = self.market_roi[mkt]
        profit = (odd - 1) if won else -1
        r["n"] += 1
        r["profit"] = 0.9 * r["profit"] + 0.1 * profit
    def market_adjust(self, mkt):
        r = self.market_roi.get(mkt)
        if not r or r["n"] < 40: return 0.0
        roi = r["profit"] / r["n"]
        return max(-0.010, min(0.020, -roi * 0.4))

    # ---------- обновление состояния ----------
    def add(self, h, a, hg, ag, row=None, k=None, match_num=None, total=None):
        if k is None:
            if match_num is not None and total:
                k = 48 - 32 * min(1.0, match_num / total)   # динамический k (уровень 3)
            else:
                k = 32
        rh, ra = self.elo.get(h,1500), self.elo.get(a,1500)
        eh = 1 / (1 + 10 ** ((ra - (rh + 60)) / 400))
        s = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
        self.elo[h] = rh + k * (s - eh)
        self.elo[a] = ra + k * ((1 - s) - (1 - eh))
        t = self.st
        t[h]["hs"].append(hg); t[h]["hc"].append(ag)
        t[a]["as"].append(ag); t[a]["ac"].append(hg)
        t[h]["form"].append(3 if hg>ag else (1 if hg==ag else 0))
        t[a]["form"].append(3 if ag>hg else (1 if hg==ag else 0))
        self.hg.append(hg); self.ag.append(ag)
        self.h2h[(h,a)].append(hg - ag)
        self.h2h[(h,a)] = self.h2h[(h,a)][-8:]
        if row:
            for col,t1,k1,t2,k2 in (("HC",h,"cfh",a,"caa"),("AC",a,"cfa",h,"cah"),
                                    ("HY",h,"yfh",a,"yaa"),("AY",a,"yfa",h,"yah")):
                v = _f(row.get(col))
                if v is not None:
                    t[t1][k1].append(v); t[t2][k2].append(v)
        for team in (h,a):
            for key in t[team]:
                t[team][key] = t[team][key][-12:]

    def h2h_adjust(self, h, a, lam_h, lam_a):
        hist = self.h2h.get((h,a), [])
        if len(hist) < 3: return lam_h, lam_a, 0
        avg_diff = sum(hist) / len(hist)
        shift = avg_diff * 0.15
        return max(0.3, lam_h + shift/2), max(0.25, lam_a - shift/2), len(hist)

    def predict(self, h, a):
        N = MATRIX_N
        lh = self._m(self.hg, 1.5); la = self._m(self.ag, 1.2)
        sh, sa = self.st[h], self.st[a]
        ah_ = self._m(sh["hs"], lh)/lh; dh_ = self._m(sh["hc"], la)/la
        aa_ = self._m(sa["as"], la)/la; da_ = self._m(sa["ac"], lh)/lh
        fh, fa = self._form(h), self._form(a)
        lam_h = max(0.3, min(5.0, lh*ah_*da_*1.10*(0.85+0.30*fh)))
        lam_a = max(0.25, min(4.5, la*aa_*dh_*0.95*(0.85+0.30*fa)))
        lam_h, lam_a, h2h_n = self.h2h_adjust(h, a, lam_h, lam_a)

        e = 1 / (1 + 10 ** ((self.elo.get(a,1500) - self.elo.get(h,1500) - 60) / 400))
        pde = 0.20 + 0.12 * (1 - abs(e - 0.5) * 2)

        M = [[self._p(lam_h,i)*self._p(lam_a,j) for j in range(N)] for i in range(N)]
        tau = {(0,0):1+lam_h*lam_a*self.rho, (1,0):1-lam_a*self.rho,
               (0,1):1-lam_h*self.rho, (1,1):1+self.rho}
        for i in range(N):
            for j in range(N):
                if (i,j) in tau: M[i][j] *= tau[(i,j)]
        tot = sum(map(sum,M)) or 1.0
        M = [[v/tot for v in r] for r in M]
        p1 = sum(M[i][j] for i in range(N) for j in range(N) if i>j)
        px = sum(M[i][i] for i in range(N))

        f1 = self.w_dc*p1 + (1-self.w_dc)*e*(1-pde)
        fd = self.w_dc*px + (1-self.w_dc)*pde
        f2 = max(0.0, 1-f1-fd)
        # Platt-калибровка финальных вероятностей 1X2
        c1, cx, c2 = self.calibrate(f1), self.calibrate(fd), self.calibrate(f2)
        ct = c1 + cx + c2 or 1.0
        f1, fd, f2 = c1/ct, cx/ct, c2/ct

        over = 1 - sum(self._p(lam_h+lam_a, k) for k in range(3))
        btts = sum(M[i][j] for i in range(1,N) for j in range(1,N))
        games = min(len(sh["hs"])+len(sh["as"]), len(sa["hs"])+len(sa["as"]))
        corners = ((self._m(sh["cfh"],5)+self._m(sa["caa"],5))/2, (self._m(sa["cfa"],5)+self._m(sh["cah"],5))/2)
        yellows = ((self._m(sh["yfh"],2)+self._m(sa["yaa"],2))/2, (self._m(sa["yfa"],2)+self._m(sh["yah"],2))/2)
        return {"p1":f1,"x":fd,"p2":f2,"over":over,"btts":btts,"M":M,
                "lams":(lam_h,lam_a),"games":games,"corners":corners,
                "yellows":yellows,"h2h_n":h2h_n,"e":e,"pde":pde}

    # ---------- единый шаг обучения (walk-forward) ----------
    def learn_step(self, h, a, hg, ag, row=None, match_num=None, total=None):
        P = self.predict(h, a)
        out = 0 if hg > ag else (1 if hg == ag else 2)
        # калибровочные точки (pooled binary per class)
        self.calib.append((self._logit(P["p1"]), 1.0 if out==0 else 0.0))
        self.calib.append((self._logit(P["x"]),  1.0 if out==1 else 0.0))
        self.calib.append((self._logit(P["p2"]), 1.0 if out==2 else 0.0))
        self.history.append((P["lams"][0], P["lams"][1], P["e"], P["pde"], out))
        # bandit: фиксируем P/L по рынкам с реальными кэфами
        if row:
            cands = [("1X2","П1",P["p1"],_f(row.get("B365H")) or _f(row.get("PSH")), hg>ag),
                     ("1X2","X", P["x"], _f(row.get("B365D")) or _f(row.get("PSD")), hg==ag),
                     ("1X2","П2",P["p2"],_f(row.get("B365A")) or _f(row.get("PSA")), hg<ag),
                     ("OU","ТБ 2.5",P["over"],_f(row.get("B365>2.5")) or _f(row.get("P>2.5")), hg+ag>=3),
                     ("OU","ТМ 2.5",1-P["over"],_f(row.get("B365<2.5")) or _f(row.get("P<2.5")), hg+ag<=2)]
            for mkt, pick, prob, odd, won in cands:
                if odd and odd > 1.01:
                    self.record_market(mkt, bool(won), odd)
        self.match_count += 1
        if self.match_count % REFIT_PLATT_EVERY == 0: self.refit_platt()
        if self.match_count % REFIT_STRUCT_EVERY == 0: self.refit_struct()
        self.add(h, a, hg, ag, row, match_num=match_num, total=total)

# ============ УТИЛИТЫ ============
def _f(v):
    try: return float(v)
    except Exception: return None

def is_cup_match(row):
    div = row.get("Div","")
    league = (row.get("League") or "").lower()
    return div in ("C1","EL","EC") or any(x in league for x in ["cup","champions","europa","conference","libertadores"])

@st.cache_data(ttl=1800)
def find_season():
    for s in ["2627","2526","2425"]:
        try:
            r = requests.head(f"https://www.football-data.co.uk/mmz4281/{s}/E0.csv", timeout=8)
            if r.status_code == 200: return s
        except Exception: continue
    return "2526"

def prev_season(s):
    try: return f"{int(s[:2])-1:02d}{int(s[2:])-1:02d}"
    except Exception: return s

@st.cache_data(ttl=1800)
def load_seasonal(div, season):
    try:
        r = requests.get(f"https://www.football-data.co.uk/mmz4281/{season}/{div}.csv",
                         timeout=20, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code != 200: return []
        return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    except Exception: return []

def load_many(divs, season):
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda d: load_seasonal(d, season), divs))
    return dict(zip(divs, results))

@st.cache_data(ttl=900)
def load_fixtures():
    rep=[]; rows=[]; seen=set()
    for u in ["https://www.football-data.co.uk/mmz4281/fixtures.csv",
              "https://www.football-data.co.uk/fixtures.csv",
              "http://www.football-data.co.uk/mmz4281/fixtures.csv"]:
        try:
            r = requests.get(u, timeout=25, headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code != 200:
                rep.append(f"{u.split('/')[-1]}: HTTP {r.status_code}"); continue
            rd = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
            n=0
            for x in rd:
                k=(x.get("Div"),x.get("Date"),x.get("HomeTeam"),x.get("AwayTeam"))
                if k in seen or not x.get("HomeTeam"): continue
                seen.add(k); x["_src"]="fixtures"; rows.append(x); n+=1
            rep.append(f"{u.split('/')[-1]}: OK, {n} строк")
            if n: break
        except Exception as ex:
            rep.append(f"{u.split('/')[-1]}: ошибка {type(ex).__name__}")
    return rows, rep

@st.cache_data(ttl=900)
def load_tsdb():
    rep=[]; rows=[]
    for lid,name in TSDB_LEAGUES.items():
        try:
            r = requests.get(f"https://www.thesportsdb.com/api/v1/json/3/eventsnextleague.php?id={lid}", timeout=15)
            ev = (r.json() or {}).get("events") or []
            for e in ev:
                rows.append({"Div":"TSDB","League":name,"Date":e.get("dateEvent",""),
                             "Time":(e.get("strTime") or "")[:5],
                             "HomeTeam":e.get("strHomeTeam",""),"AwayTeam":e.get("strAwayTeam",""),
                             "_src":"tsdb"})
            rep.append(f"TSDB {name}: {len(ev)}")
        except Exception:
            rep.append(f"TSDB {name}: ошибка")
    return rows, rep

def parse_date(s):
    for fmt in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d"):
        try: return datetime.strptime(s.strip(), fmt)
        except Exception: continue
    return None

def odd1(row, keys):
    for k in keys:
        v = _f(row.get(k))
        if v and v > 1.01: return v
    return None

def kelly(prob, odds, bank, frac):
    if prob <= 0 or odds <= 1: return 0.0
    b = odds - 1
    k = (b*prob - (1-prob)) / b
    return round(min(max(0, k*frac), 0.05) * bank, 2)

def settle_ah(pick, hg, ag):
    m = re.match(r"Ф([12])\(([-+]?\d+(?:\.\d+)?)\)", pick)
    if not m: return None
    side, line = int(m.group(1)), float(m.group(2))
    diff = (hg-ag) if side==1 else (ag-hg)
    res = diff + line
    if res > 0.001: return True
    if abs(res) <= 0.001: return "push"
    return False

def make_reason(c, rw):
    parts=[]; lh,la=c["lams"]; pick=rw["pick"]; prob=rw["prob"]
    if rw["mkt"]=="1X2":
        if pick=="П1": parts.append(f"xG {lh:.1f} против {la:.1f} в пользу хозяев")
        elif pick=="П2": parts.append(f"xG {la:.1f} против {lh:.1f} в пользу гостей")
        else: parts.append(f"равный матч, ничья в {prob*100:.0f}% симуляций")
        if c.get("fh","—")!="—" and c.get("fa","—")!="—":
            parts.append(f"форма {c['fh']} vs {c['fa']}")
    elif rw["mkt"]=="OU":
        tot=lh+la
        parts.append(f"ожидаемый тотал {tot:.1f} — "+("выше линии 2.5" if pick=="ТБ 2.5" else "ниже линии 2.5"))
    elif rw["mkt"]=="STAT":
        if pick.startswith("BTTS"): parts.append(f"обе забьют с вероятностью {prob*100:.0f}% по матрице голов")
        else: parts.append("двойной шанс перекрывает 2 исхода из 3")
    elif rw["mkt"]=="AH":
        parts.append("фора покрывается матрицей счёта с запасом")
    if c.get("h2h_n",0)>=3: parts.append(f"H2H: {c['h2h_n']} последних встреч")
    if rw["odd"]: parts.append(f"кэф {rw['odd']:.2f} выше фейр-кэфа {1/prob:.2f} (EV {rw['ev']*100:+.0f}%)")
    else: parts.append(f"фейр-кэф {1/prob:.2f} — ищи у букмекера коэффициент выше")
    return " · ".join(parts[:3])

def stars_for(rw, thr):
    if rw["ok"]:
        ev=rw["ev"]
        return "⭐⭐⭐⭐⭐" if ev>=0.10 else ("⭐⭐⭐⭐" if ev>=0.06 else "⭐⭐⭐")
    if rw["prob"]>=thr:
        return "⭐⭐⭐⭐⭐" if rw["prob"]>=0.70 else ("⭐⭐⭐⭐" if rw["prob"]>=0.65 else "⭐⭐⭐")
    return ""

def build_picks(cards, thr, bank, kelly_frac):
    picks=[]
    for c in cards:
        row=None; ptype=None
        if c["best"]:
            ok_rows=[r for r in c["rows"] if r["ok"]]
            row=max(ok_rows,key=lambda r:r["ev"]) if ok_rows else None
            ptype="value"
        if row is None:
            hotr=[r for r in c["rows"] if r["prob"]>=thr]
            if hotr:
                row=max(hotr,key=lambda r:r["prob"]); ptype="hot"
        if row is None: continue
        stake=kelly(row["prob"],row["odd"],bank,kelly_frac) if row["odd"] else round(bank*0.01,2)
        picks.append({"league":c["league"],"match":c["match"],"date":c["date"],"when":c["when"],
                      "pick":row["pick"],"mkt":row["mkt"],"prob":row["prob"],"odd":row["odd"],
                      "odd_s":f"{row['odd']:.2f}" if row["odd"] else f"фейр {1/row['prob']:.2f}+",
                      "stake":stake,"stars":stars_for(row,thr),"type":ptype,
                      "reason":make_reason(c,row),
                      "score":(row["ev"] if ptype=="value" else 0)+row["prob"]})
    picks.sort(key=lambda p:(p["type"]=="value",p["score"]),reverse=True)
    return picks[:10]

def load_data():
    if os.path.exists(HISTORY_FILE):
        try: return json.load(open(HISTORY_FILE, encoding="utf-8"))
        except Exception: pass
    return {"bank":10000.0,"bets":[],"cards":[],"picks":[],"funnel":None,"report":[],
            "meta":{},"stats":{"won":0,"lost":0,"profit":0,"push":0}}
def save_data(d): json.dump(d, open(HISTORY_FILE,"w",encoding="utf-8"), indent=2, ensure_ascii=False)

def backtest(div, season, min_edge=0.02, min_odd=1.4, max_odd=4.2):
    rows=[r for r in load_seasonal(div,season)
          if r.get("FTHG") not in (None,"") and r.get("FTAG") not in (None,"") and parse_date(r.get("Date",""))]
    rows.sort(key=lambda r: parse_date(r["Date"]))
    eng=Engine(); log=[]
    for j,r in enumerate(rows):
        h=(r.get("HomeTeam") or "").strip(); a=(r.get("AwayTeam") or "").strip()
        try: hg,ag=float(r["FTHG"]),float(r["FTAG"])
        except Exception: continue
        try:
            P=eng.predict(h,a)
            cands=[("1X2","П1",P["p1"],odd1(r,["B365H","PSH","MaxH"])),
                   ("1X2","X",P["x"],odd1(r,["B365D","PSD","MaxD"])),
                   ("1X2","П2",P["p2"],odd1(r,["B365A","PSA","MaxA"])),
                   ("OU","ТБ 2.5",P["over"],odd1(r,["B365>2.5","P>2.5","Max>2.5"])),
                   ("OU","ТМ 2.5",1-P["over"],odd1(r,["B365<2.5","P<2.5","Max<2.5"]))]
            for mkt,pick,prob,o in cands:
                if not o or not (min_odd<=o<=max_odd): continue
                req = min_edge + eng.market_adjust(mkt)
                if prob - 1/o < req: continue
                won=False
                if pick=="П1": won=hg>ag
                elif pick=="X": won=hg==ag
                elif pick=="П2": won=hg<ag
                elif pick=="ТБ 2.5": won=hg+ag>=3
                elif pick=="ТМ 2.5": won=hg+ag<=2
                log.append({"mkt":mkt,"prob":prob,"odd":o,"won":bool(won)})
        except Exception: pass
        try: eng.learn_step(h,a,hg,ag,r,match_num=j,total=len(rows))
        except Exception: pass
    return log, eng

# ============ UI ============
if "data" not in st.session_state: st.session_state.data=load_data()
D=st.session_state.data

st.markdown(f"""
<div class="hero">
 <h1>🏟 NEURO BET PRO v4</h1>
 <p>Самообучение: Platt-калибровка · walk-forward retraining · динамический Elo-k · bandit по рынкам · H2H · Dixon-Coles 9×9</p>
 <div class="kpis">
  <div class="kpi"><div class="t">Банкролл</div><div class="v y">{D['bank']:.0f} у.е.</div></div>
  <div class="kpi"><div class="t">В работе</div><div class="v">{sum(1 for b in D['bets'] if b['status']=='pending')}</div></div>
  <div class="kpi"><div class="t">Прибыль</div><div class="v {'g' if D['stats']['profit']>=0 else 'r'}">{D['stats']['profit']:+.0f}</div></div>
  <div class="kpi"><div class="t">Рекомендаций</div><div class="v g">{len(D.get('picks',[]))}</div></div>
 </div>
</div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Настройки")
    kelly_frac=st.slider("Келли (дробь)",0.10,0.40,0.25,0.05)
    mode=st.radio("Режим ленты",["🎯 Высокая проходимость","💰 Валуи (EV)"])
    thr=st.slider("Порог проходимости, %",50,80,60)/100
    min_edge=st.slider("Edge для валуев, п.п.",0,8,2)/100
    min_ev=st.slider("Мин. EV для валуев, %",0,10,2)/100
    meta=D.get("meta",{})
    if meta:
        st.markdown("**🧠 Состояние самообучения**")
        st.caption(f"Platt a={meta.get('platt_a',0):.2f} b={meta.get('platt_b',1):.2f} · rho={meta.get('rho',-0.13):.2f} · вес DC={meta.get('w_dc',0.72):.2f}")
        mr=meta.get("market_roi",{})
        if mr:
            best_m=max(mr.items(), key=lambda kv: kv[1]["profit"]/max(1,kv[1]["n"]))
            worst_m=min(mr.items(), key=lambda kv: kv[1]["profit"]/max(1,kv[1]["n"]))
            st.caption(f"🟢 Лучший рынок: {best_m[0]} ({best_m[1]['profit']/max(1,best_m[1]['n'])*100:+.1f}% ROI) · 🔴 Худший: {worst_m[0]} ({worst_m[1]['profit']/max(1,worst_m[1]['n'])*100:+.1f}%)")
    if st.button("🔄 Сброс"):
        st.session_state.data={"bank":10000.0,"bets":[],"cards":[],"picks":[],"funnel":None,"report":[],
                               "meta":{},"stats":{"won":0,"lost":0,"profit":0,"push":0}}
        save_data(st.session_state.data); st.cache_data.clear(); st.rerun()

tab1,tab2,tab3,tab4,tab5=st.tabs(["🏟 Сканер","💼 Портфель","📈 Статистика","🧮 Калькулятор","🧪 Бэктест"])

with tab1:
    c1,c2=st.columns([4,1]); days=c1.slider("Горизонт, дней",1,21,10); scan=c2.button("⚡ СКАН",type="primary")
    if scan:
        season=find_season(); pseason=prev_season(season)
        today=datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
        limit=today+timedelta(days=days)
        fix,rep1=load_fixtures(); tsd,rep2=load_tsdb()
        allrows=fix+tsd
        engine=Engine(); trained=0
        train_divs=sorted({r.get("Div") for r in fix if r.get("Div")}) or ["E0","SP1","I1","D1","F1"]
        prog=st.progress(0.0,text=f"Самообучение на 2 сезонах ({pseason}+{season})...")
        data_prev=load_many(train_divs,pseason); data_curr=load_many(train_divs,season)
        n=len(train_divs)
        for i,dv in enumerate(train_divs):
            prev_rows=sorted([r for r in data_prev.get(dv,[]) if parse_date(r.get("Date",""))],key=lambda r:parse_date(r["Date"]))
            curr_rows=sorted([r for r in data_curr.get(dv,[]) if parse_date(r.get("Date",""))],key=lambda r:parse_date(r["Date"]))
            for j,r in enumerate(prev_rows):
                if r.get("FTHG") not in (None,"") and r.get("FTAG") not in (None,""):
                    try:
                        engine.learn_step(r["HomeTeam"],r["AwayTeam"],float(r["FTHG"]),float(r["FTAG"]),r,match_num=j,total=max(1,len(prev_rows)))
                        trained+=1
                    except Exception: continue
            for j,r in enumerate(curr_rows):
                if r.get("FTHG") not in (None,"") and r.get("FTAG") not in (None,""):
                    try:
                        engine.learn_step(r["HomeTeam"],r["AwayTeam"],float(r["FTHG"]),float(r["FTAG"]),r,match_num=j,total=max(1,len(curr_rows)))
                        trained+=1
                    except Exception: continue
            prog.progress((i+1)/n)
        prog.empty()
        D["meta"]={"platt_a":round(engine.platt_a,3),"platt_b":round(engine.platt_b,3),
                   "rho":round(engine.rho,3),"w_dc":round(engine.w_dc,3),
                   "market_roi":{k:v for k,v in engine.market_roi.items()}}
        cards=[]; passed=0; inwin=0; withodds=0; added=0
        existing={b["match"]+"|"+b["pick"] for b in D["bets"]}
        for r in allrows:
            try:
                d=parse_date(r.get("Date",""))
                if not d or not (today<=d<=limit): continue
                h=(r.get("HomeTeam") or "").strip(); a=(r.get("AwayTeam") or "").strip()
                if not h or not a: continue
                inwin+=1
                P=engine.predict(h,a)
                league=r.get("League") or DIV_NAMES.get(r.get("Div"),"Лига "+str(r.get("Div")))
                oh=odd1(r,["B365H","PSH","MaxH"]); od=odd1(r,["B365D","PSD","MaxD"]); oa=odd1(r,["B365A","PSA","MaxA"])
                ov=odd1(r,["B365>2.5","P>2.5","Max>2.5"]); un=odd1(r,["B365<2.5","P<2.5","Max<2.5"])
                if oh or ov: withodds+=1
                if is_cup_match(r):
                    P["lams"]=(max(0.3,P["lams"][0]-0.15),max(0.25,P["lams"][1]-0.15))
                rows=[]; best=None; hot=[]
                cands=[("1X2","П1",P["p1"],oh),("1X2","X",P["x"],od),("1X2","П2",P["p2"],oa),
                       ("OU","ТБ 2.5",P["over"],ov),("OU","ТМ 2.5",1-P["over"],un),
                       ("STAT","BTTS да",P["btts"],None),("STAT","BTTS нет",1-P["btts"],None),
                       ("STAT","1X",P["p1"]+P["x"],None),("STAT","X2",P["x"]+P["p2"],None),("STAT","12",P["p1"]+P["p2"],None)]
                ahh=_f(r.get("AHh")); ohh=odd1(r,["B365AHH","PAHH"]); oha=odd1(r,["B365AHA","PAHA"])
                if ahh is not None and abs((ahh*2)%2)==1 and ohh and oha:
                    pc=sum(P["M"][i][j] for i in range(MATRIX_N) for j in range(MATRIX_N) if (i-j+ahh)>0.001)
                    cands+=[("AH",f"Ф1({ahh:+.1f})",pc,ohh),("AH",f"Ф2({-ahh:+.1f})",1-pc,oha)]
                for mkt,pick,prob,odd in cands:
                    item={"mkt":mkt,"pick":pick,"prob":prob,"odd":odd,"ev":None,"be":None,"edge":None,"ok":False}
                    if odd:
                        lo,hi=CORRIDORS.get(mkt,(1.4,4.2))
                        ev=prob*odd-1; be=1/odd; edge=prob-be
                        req=max(0.0, min_ev + max(0.0,odd-2.5)*0.02 + engine.market_adjust(mkt))
                        item.update(ev=ev,be=be,edge=edge,ok=(lo<=odd<=hi and edge>=min_edge and ev>=req))
                        if item["ok"]:
                            passed+=1; stk=kelly(prob,odd,D["bank"],kelly_frac)
                            if best is None or ev>best[3]: best=(mkt,pick,odd,ev,prob,stk)
                    if prob>=thr: hot.append((pick,prob,odd))
                    rows.append(item)
                hot.sort(key=lambda x:-x[1])
                tag="value" if best else ("hot" if hot else "")
                nd=(d-today).days
                when="сегодня" if nd==0 else ("завтра" if nd==1 else f"через {nd} дн")
                cards.append({"div":r.get("Div"),"league":league,"match":f"{h} vs {a}",
                    "date":d.strftime("%d.%m")+(f" {r.get('Time')}" if r.get("Time") else ""),"when":when,
                    "rows":rows,"best":best,"hot":hot[:3],"tag":tag,"lams":P["lams"],
                    "corners":P["corners"],"yellows":P["yellows"],"games":P["games"],"h2h_n":P["h2h_n"],
                    "fh":engine.form_str(h),"fa":engine.form_str(a),"cup":is_cup_match(r)})
                if best and best[5]>0:
                    key=f"{h} vs {a}|{best[1]}"
                    if key not in existing:
                        D["bets"].append({"match":f"{h} vs {a}","div":r.get("Div"),"league":league,
                            "market":best[0],"pick":best[1],"odds":best[2],"stake":best[5],
                            "prob":best[4],"status":"pending"})
                        existing.add(key); added+=1
            except Exception: continue
        cards.sort(key=lambda c:(c["tag"]=="value",c["tag"]=="hot",c["date"]),reverse=True)
        D["cards"]=cards; D["report"]=rep1+rep2
        D["picks"]=build_picks(cards,thr,D["bank"],kelly_frac)
        D["funnel"]={"trained":trained,"fix":len(fix),"tsdb":len(tsd),"inwin":inwin,"odds":withodds,"passed":passed,"added":added}
        save_data(D); st.rerun()

    fn=D.get("funnel")
    if fn:
        st.caption(f"Обучено {fn['trained']} (2 сезона, самообучение) · расписание {fn['fix']}+{fn['tsdb']} · в окне {fn['inwin']} · с кэфами {fn['odds']} · валуев {fn['passed']} · в портфель +{fn['added']}")
    with st.expander("🔌 Диагностика источников"):
        for line in D.get("report",[]): st.text(line)

    picks=D.get("picks",[])
    if picks:
        st.markdown("### 🎯 НА ЧТО СТАВИТЬ — краткие рекомендации")
        txt=["NEURO BET PRO v4 — "+datetime.now().strftime("%d.%m.%Y %H:%M"),""]
        for i,p in enumerate(picks,1):
            cls="value" if p["type"]=="value" else "hot"
            btype="🟢 ВАЛУЙ" if p["type"]=="value" else "🔥 Высокая проходимость"
            st.markdown(f"""
<div class="mcard {cls}" style="padding:14px 18px">
 <div class="mhead"><span class="chip">{p['league']}</span><span class="chip when">📅 {p['date']} · {p['when']}</span>
  <span class="badge {'val' if p['type']=='value' else 'hot'}">{p['stars']}</span></div>
 <div class="teams" style="font-size:1.15rem;margin:8px 0 2px">{i}. {p['match']}</div>
 <div class="pickline">➤ Ставь: <b class="y">{p['pick']}</b> @ <b class="y">{p['odd_s']}</b> ·
  вероятность <b class="g">{p['prob']*100:.0f}%</b> · сумма <b class="y">{p['stake']:.2f} у.е.</b> · {btype}</div>
 <div class="why">💡 {p['reason']}</div>
</div>""",unsafe_allow_html=True)
            txt+= [f"{i}. {p['match']} ({p['league']}, {p['date']})",
                   f"   Ставка: {p['pick']} @ {p['odd_s']} | P={p['prob']*100:.0f}% | {p['stake']:.2f} у.е. | {p['stars']}",
                   f"   Почему: {p['reason']}",""]
        st.download_button("📥 Скачать рекомендации (.txt)","\n".join(txt),file_name="picks.txt")
    else:
        st.info("Рекомендации появятся после ⚡ СКАН.")

    st.markdown("### 📋 Полная лента матчей")
    for c in D.get("cards",[]):
        if mode=="🎯 Высокая проходимость" and not (c["hot"] or c["tag"]): continue
        if mode=="💰 Валуи (EV)" and not c["best"]: continue
        val=c["best"] is not None
        hot=any(r["prob"]>=thr for r in c["rows"]) and not val
        badge="<span class='badge val'>🟢 ВАЛУЙ</span>" if val else ("<span class='badge hot'>🔥 P≥{:.0f}%</span>".format(thr*100) if hot else "<span class='badge no'>фон</span>")
        lowdata="<span class='chip warn'>⚠️ мало данных</span>" if c["games"]<8 else ""
        cupchip="<span class='chip warn'>🏆 Кубок</span>" if c.get("cup") else ""
        h2hchip=f"<span class='chip'>⚔ H2H: {c['h2h_n']}</span>" if c.get("h2h_n",0)>=3 else ""
        def fr(s): return "".join(f"<b class='{'w' if ch=='В' else ('d' if ch=='Н' else 'l')}'>{ch}</b>" for ch in s)
        rows_html="<div class='mrow hdr'><span>Рынок</span><span>Выбор</span><span>Вероятность</span><span>P</span><span>Безуб.</span><span>Кэф</span><span>EV</span><span></span></div>"
        for rw in c["rows"]:
            w=min(100,rw["prob"]*100)
            odd_s=f"{rw['odd']:.2f}" if rw["odd"] else f"fair {1/rw['prob']:.2f}"
            ev_s=f"<span class='{'evpos' if rw['ev']>0 else 'evneg'}'>{rw['ev']*100:+.1f}%</span>" if rw["ev"] is not None else "<span style='color:#64748b'>—</span>"
            be_s=f"{rw['be']*100:.1f}%" if rw["be"] else "—"
            mk="<span class='ok'>✅</span>" if rw["ok"] else ("<span style='color:#fde047;font-weight:800'>🔥</span>" if rw["prob"]>=thr else "<span class='nok'>·</span>")
            rows_html+=(f"<div class='mrow'><span style='color:#94a3b8'>{rw['mkt']}</span><b style='color:#facc15'>{rw['pick']}</b>"
                        f"<div><div class='bar'><i style='width:{w:.0f}%'></i></div></div>"
                        f"<span style='color:#4ade80;font-weight:700'>{rw['prob']*100:.1f}%</span><span style='color:#f87171'>{be_s}</span>"
                        f"<span style='color:#ffffff;font-weight:700'>{odd_s}</span>{ev_s}{mk}</div>")
        ch,ca=c["corners"]; yh,ya=c["yellows"]
        best_html=f"<span>💰 Келли: <b>{c['best'][5]:.2f}</b> на <b>{c['best'][1]}</b> @ <b>{c['best'][2]:.2f}</b></span>" if val else ""
        hot_html="".join(f"<span>🔥 <b>{p}</b> {pr*100:.0f}%</span>" for p,pr,_ in c["hot"]) if not val else ""
        st.markdown(f"""
<div class="mcard {'value' if val else ('hot' if hot else '')}">
 <div class="mhead"><span class="chip">{c['league']}</span><span class="chip when">📅 {c['date']} · {c['when']}</span>{lowdata}{cupchip}{h2hchip}{badge}</div>
 <div class="teams">{c['match'].split(' vs ')[0]} <span>—</span> {c['match'].split(' vs ')[1]}</div>
 <div class="form5">форма: {fr(c['fh'])} <span style='color:#64748b'>vs</span> {fr(c['fa'])}</div>
 {rows_html}
 <div class="mfoot"><span>xG: <b>{c['lams'][0]:.2f}–{c['lams'][1]:.2f}</b></span>
  <span>🚩 угловые <b>{ch+ca:.1f}</b></span><span>🟨 жёлтые <b>{yh+ya:.1f}</b></span>
  <span>📚 игр: <b>{c['games']}</b></span>{best_html}{hot_html}</div>
</div>""",unsafe_allow_html=True)
    if not D.get("cards"):
        st.info("Нажми ⚡ СКАН.")

with tab2:
    st.header("💼 Портфель")
    if st.button("🔄 Автосинхронизация"):
        season=find_season(); upd=0
        for bet in [b for b in D["bets"] if b["status"]=="pending" and b.get("div") not in (None,"TSDB")]:
            for r in load_seasonal(bet["div"],season):
                if r.get("HomeTeam")==bet["match"].split(" vs ")[0] and r.get("AwayTeam")==bet["match"].split(" vs ")[1] and r.get("FTHG") not in (None,""):
                    try: hg,ag=float(r["FTHG"]),float(r["FTAG"])
                    except Exception: continue
                    won=False
                    if bet["market"]=="1X2":
                        won=("П1" if hg>ag else "X" if hg==ag else "П2")==bet["pick"]
                    elif bet["market"]=="OU":
                        won=(bet["pick"]=="ТБ 2.5" and hg+ag>=3) or (bet["pick"]=="ТМ 2.5" and hg+ag<=2)
                    elif bet["market"]=="AH":
                        won=settle_ah(bet["pick"],hg,ag)
                    if won=="push":
                        bet["status"]="push"; D["bank"]+=bet["stake"]; D["stats"]["push"]=D["stats"].get("push",0)+1
                    elif won:
                        bet["status"]="won"; pr=bet["stake"]*(bet["odds"]-1)
                        D["bank"]+=bet["stake"]+pr; D["stats"]["won"]+=1; D["stats"]["profit"]+=pr
                    else:
                        bet["status"]="lost"; D["stats"]["lost"]+=1; D["stats"]["profit"]-=bet["stake"]
                    upd+=1; break
        save_data(D); st.success(f"Закрыто: {upd}"); st.rerun()
    if not D["bets"]: st.info("Пусто.")
    for i,b in enumerate(D["bets"]):
        icon={"pending":"⏳","won":"🟢","lost":"🔴","push":"⚪"}.get(b["status"],"⏳")
        st.markdown(f"{icon} **{b['match']}** · {b.get('market','')} **{b['pick']}** @ **{b['odds']:.2f}** · {b['stake']:.2f} у.е. · P={b.get('prob',0)*100:.0f}%")
        if b["status"]=="pending":
            cc=st.columns(2)
            if cc[0].button("✅ Зашло",key=f"w{i}"):
                b["status"]="won"; pr=b["stake"]*(b["odds"]-1); D["bank"]+=b["stake"]+pr
                D["stats"]["won"]+=1; D["stats"]["profit"]+=pr; save_data(D); st.rerun()
            if cc[1].button("❌ Мимо",key=f"l{i}"):
                b["status"]="lost"; D["stats"]["lost"]+=1; D["stats"]["profit"]-=b["stake"]; save_data(D); st.rerun()

with tab3:
    s=D["stats"]; tot=s["won"]+s["lost"]
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Банк",f"{D['bank']:.2f}"); m2.metric("Ставок",tot)
    m3.metric("WinRate",f"{(s['won']/tot*100) if tot else 0:.1f}%"); m4.metric("Profit",f"{s['profit']:+.2f}")

with tab4:
    st.header("🧮 EV-калькулятор")
    q1,q2,q3=st.columns(3)
    p=q1.number_input("Вероятность, %",1,99,60); o=q2.number_input("Кэф",1.01,30.0,1.80); bk=q3.number_input("Банк",100.0,1e6,float(D["bank"]))
    ev=(p/100)*o-1
    st.markdown(f"**EV:** {ev*100:+.1f}% · **Безубыточность:** {100/o:.1f}% · **Келли:** {kelly(p/100,o,bk,kelly_frac):.2f} у.е.")
    if ev>0.02: st.success("✅ Можно ставить")
    else: st.warning("⛔ EV мал")
    if st.button("➕ Добавить ставку вручную"):
        D["bets"].append({"match":"Ручная ставка","div":None,"league":"✍️","market":"MANUAL",
                          "pick":f"P{p:.0f}%","odds":o,"stake":kelly(p/100,o,bk,kelly_frac),
                          "prob":p/100,"status":"pending"})
        save_data(D); st.rerun()

with tab5:
    st.header("🧪 Walk-forward бэктест с самообучением")
    st.caption("Модель учится матч за матчем: калибрует вероятности (Platt), подбирает rho и веса, адаптирует k, отслеживает ROI рынков.")
    b1,b2,b3=st.columns(3)
    bt_div=b1.selectbox("Лига",list(DIV_NAMES.keys()),format_func=lambda k:DIV_NAMES[k])
    bt_season=b2.selectbox("Сезон",["2526","2425","2324"],index=1)
    bt_edge=b3.slider("Edge, п.п.",0,8,2)/100
    if st.button("▶️ Прогнать",type="primary"):
        log,eng=backtest(bt_div,bt_season,bt_edge)
        if not log:
            st.warning("Ни одной ставки не прошло фильтр — попробуй меньший edge.")
        else:
            n=len(log); wins=sum(1 for x in log if x["won"])
            profits=[(x["odd"]-1) if x["won"] else -1 for x in log]
            profit=sum(profits); roi=profit/n*100
            curve=0;peak=0;mdd=0
            for p_ in profits:
                curve+=p_; peak=max(peak,curve); mdd=max(mdd,peak-curve)
            mean_p=sum(profits)/n
            std_p=(sum((x-mean_p)**2 for x in profits)/max(1,n-1))**0.5
            sharpe=mean_p/std_p if std_p>0 else 0
            k1,k2,k3,k4,k5=st.columns(5)
            k1.metric("Ставок",n); k2.metric("WinRate",f"{wins/n*100:.1f}%")
            k3.metric("ROI флэт",f"{roi:+.2f}%"); k4.metric("Max просадка",f"{mdd:.1f}")
            k5.metric("Sharpe",f"{sharpe:.2f}")
            st.markdown(f"**Чистыми:** {profit:+.1f} у.е. · **Platt:** a={eng.platt_a:.2f} b={eng.platt_b:.2f} · **rho:** {eng.rho:.2f} · **вес DC:** {eng.w_dc:.2f}")
            bins=defaultdict(lambda:[0,0])
            for x in log:
                b0=min(4,int(x["prob"]*5)); bins[b0][0]+=1; bins[b0][1]+=1 if x["won"] else 0
            rows=[{"Прогноз P":f"{b0*20}–{b0*20+20}%","Ставок":c,"Факт":f"{w/c*100:.0f}%"} for b0,(c,w) in sorted(bins.items()) if c>=5]
            if rows:
                st.subheader("Калибровка"); st.dataframe(rows,use_container_width=True,hide_index=True)
            by=defaultdict(lambda:[0,0,0.0])
            for x in log:
                by[x["mkt"]][0]+=1; by[x["mkt"]][1]+=1 if x["won"] else 0; by[x["mkt"]][2]+=(x["odd"]-1) if x["won"] else -1
            mrows=[{"Рынок":k,"Ставок":v[0],"WinRate":f"{v[1]/v[0]*100:.0f}%","Profit":f"{v[2]:+.1f}","ROI":f"{v[2]/v[0]*100:+.1f}%"} for k,v in sorted(by.items())]
            if mrows:
                st.subheader("ROI по рынкам"); st.dataframe(mrows,use_container_width=True,hide_index=True)
            if roi>0 and sharpe>0.1: st.success(f"✅ Плюс и стабильность (Sharpe {sharpe:.2f}).")
            elif roi>0: st.warning(f"⚠️ Плюс, но волатильно (Sharpe {sharpe:.2f}).")
            else: st.error("❌ Минус — не ставь по этой конфигурации.")
