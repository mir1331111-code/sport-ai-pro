
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta
import io
import json
import math
import os
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="NEURO BET PRO v7", page_icon="🏟", layout="wide")
HISTORY_FILE = "neuro_bet_pro.json"
MATRIX_N = 9
UA = {"User-Agent": "Mozilla/5.0"}

DEF_LP = lambda: {"w_shots": 0.35, "rho": -0.13, "w_dc": 0.72}

DIV_NAMES = {
    "E0": "🏴󠁢󠁥󠁮󠁧󠁿 АПЛ",
    "E1": "🏴󠁢󠁮󠁿 Чемпионшип",
    "SC0": "🏴󠁢󠁣󠁿 Шотландия",
    "D1": "🇩🇪 Бундеслига",
    "D2": "🇩🇪 2.Бундеслига",
    "I1": "🇮🇹 Серия A",
    "I2": "🇮🇹 Серия B",
    "SP1": "🇪🇸 Ла Лига",
    "SP2": "🇪🇸 Сегунда",
    "F1": "🇫🇷 Лига 1",
    "F2": "🇫🇷 Лига 2",
    "N1": "🇳🇱 Эредивизи",
    "B1": "🇧🇪 Про-лига",
    "P1": "🇵🇹 Примейра",
    "T1": "🇹🇷 Суперлига",
    "G1": "🇬🇷 Греция",
    "R1": "🇷🇺 РПЛ",
    "BR1": "🇧🇷 Бразилия",
    "C1": "🏆 ЛЧ",
    "EL": "🏆 ЛЕ",
    "EC": "🏆 ЛК",
}
TSDB_LEAGUES = {
    "432": "🏴󠁢󠁥󠁮󠁧󠁿 АПЛ",
    "434": "🇪🇸 Ла Лига",
    "435": "🇮🇹 Серия A",
    "436": "🇩🇪 Бундеслига",
    "437": "🇫🇷 Лига 1",
    "448": "🏆 ЛЧ",
    "442": "🇺🇸 MLS",
    "439": "🇵🇹 Примейра",
}
GOALS = {
    "🎯 Проходимость": dict(
        w_market=0.65,
        thr=0.62,
        dis=False,
        edge=0.01,
        ev=0.01,
        min_games=10,
    ),
    "⚖️ Баланс": dict(
        w_market=0.40,
        thr=0.55,
        dis=True,
        edge=0.02,
        ev=0.02,
        min_games=8,
    ),
    "💰 Value": dict(
        w_market=0.20,
        thr=0.45,
        dis=True,
        edge=0.03,
        ev=0.02,
        min_games=6,
    ),
}

st.markdown(
    """
<style>
html,body,.stApp{background:#070b14 !important;}
.stApp{background-image:none !important;}
.stMarkdown,.stMarkdown p,.stMarkdown li,.stMarkdown ul{color:#e2e8f0;}
.stCaption,.stCaption *,div[data-testid="stCaptionContainer"]{color:#94a3b8 !important;}
div[data-testid="stMetricValue"]{color:#f8fafc !important;}
div[data-testid="stMetricLabel"] p{color:#94a3b8 !important;}
.stTabs button p{color:#cbd5e1 !important;}
header,#MainMenu,footer{visibility:hidden}
section[data-testid="stSidebar"]{background:#0b0f1a !important;border-right:1px solid rgba(148,163,184,.2)}
section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span,section[data-testid="stSidebar"] .stMarkdown{color:#e2e8f0 !important;}
section[data-testid="stSidebar"] h1,section[data-testid="stSidebar"] h2,section[data-testid="stSidebar"] h3{color:#f8fafc !important;}
section[data-testid="stSidebar"] div[data-testid="stMetricValue"]{color:#facc15 !important;}
section[data-testid="stSidebar"] div[data-testid="stMetricLabel"] p{color:#94a3b8 !important;}
section[data-testid="stSidebar"] div[data-baseweb="select"]>div{background:#111827 !important;border:1px solid rgba(148,163,184,.35)}
section[data-testid="stSidebar"] div[data-baseweb="select"] span{color:#e2e8f0 !important;}
.hero{padding:20px 26px;border-radius:22px;margin-bottom:16px;border:1px solid rgba(56,189,248,.35);
 background:linear-gradient(120deg,rgba(2,6,23,.96),rgba(6,78,59,.80) 55%,rgba(120,53,15,.75)),
 url('https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=1600&auto=format&fit=crop') center/cover;}
.hero h1{margin:0;font-size:2.3rem;font-weight:900;color:#fff;text-shadow:0 2px 10px rgba(0,0,0,.9)}
.hero p{margin:4px 0 0;color:#dbeafe;font-size:.92rem;text-shadow:0 1px 6px rgba(0,0,0,.9)}
</style>""",
    unsafe_allow_html=True,
)

ERR = []


def log_err(tag, e):
  ERR.append(f"[{tag}] {type(e).__name__}: {e}")
  if len(ERR) > 300:
    ERR.pop(0)


class Engine:

  def __init__(self):
    self.elo = {}
    self.st = defaultdict(
        lambda: {
            "hs": [],
            "hc": [],
            "as": [],
            "ac": [],
            "form": [],
            "cfh": [],
            "caa": [],
            "cfa": [],
            "cah": [],
            "yfh": [],
            "yaa": [],
            "yfa": [],
            "yah": [],
            "hst_h": [],
            "hstc_h": [],
            "hst_a": [],
            "hstc_a": [],
        }
    )
    self.hg = []
    self.ag = []
    self.hsth = []
    self.hsta = []
    self.h2h = defaultdict(list)
    self.calib = []
    self.platt_a = 0.0
    self.platt_b = 1.0
    self.lp = defaultdict(DEF_LP)
    self.hist = defaultdict(list)
    self.match_count = 0
    self.market_roi = defaultdict(lambda: {"n": 0, "profit": 0.0})

  def save_state(self):
    data = {
        "elo": self.elo,
        "platt_a": self.platt_a,
        "platt_b": self.platt_b,
        "lp": {k: dict(v) for k, v in self.lp.items()},
        "match_count": self.match_count,
        "market_roi": {k: dict(v) for k, v in self.market_roi.items()},
        "hist": {k: list(v) for k, v in self.hist.items()},
    }
    try:
      with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    except Exception as e:
      log_err("save_state", e)

  @classmethod
  def load_state(cls):
    eng = cls()
    if not os.path.exists(HISTORY_FILE):
      return eng
    try:
      with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
      eng.elo = data.get("elo", {})
      eng.platt_a = data.get("platt_a", 0.0)
      eng.platt_b = data.get("platt_b", 1.0)
      eng.match_count = data.get("match_count", 0)
      for k, v in data.get("lp", {}).items():
        eng.lp[k] = v
      for k, v in data.get("market_roi", {}).items():
        eng.market_roi[k] = v
      for k, v in data.get("hist", {}).items():
        eng.hist[k] = [tuple(x) for x in v]
    except Exception as e:
      log_err("load_state", e)
    return eng

  @staticmethod
  def _logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))

  @staticmethod
  def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-max(-30, min(30, x))))

  def _m(self, l, d=1.0):
    return sum(l) / len(l) if l else d

  def _p(self, l, k):
    return math.exp(-l) * l**k / math.factorial(k)

  def _form(self, t):
    f = self.st[t]["form"][-5:]
    return (sum(f) / (len(f) * 3)) if f else 0.5

  def form_str(self, t):
    return (
        "".join(
            {"3": "В", "1": "Н", "0": "П"}[str(int(x))]
            for x in self.st[t]["form"][-5:]
        )
        or "—"
    )

  def calibrate(self, p):
    return self._sigmoid(self.platt_a + self.platt_b * self._logit(p))

  def _p1px(self, lh, la, rho):
    N = MATRIX_N
    M = [
        [self._p(lh, i) * self._p(la, j) for j in range(N)] for i in range(N)
    ]
    tau = {
        (0, 0): 1 + lh * la * rho,
        (1, 0): 1 - la * rho,
        (0, 1): 1 - lh * rho,
        (1, 1): 1 + rho,
    }
    for i in range(N):
      for j in range(N):
        if (i, j) in tau:
          M[i][j] *= tau[(i, j)]
    tot = sum(map(sum, M)) or 1.0
    M = [[v / tot for v in r] for r in M]
    p1 = sum(M[i][j] for i in range(N) for j in range(N) if i > j)
    px = sum(M[i][i] for i in range(N))
    return p1, px, M

  def _probs_from(self, lh, la, rho, w, e, pde):
    p1, px, _ = self._p1px(lh, la, rho)
    f1 = w * p1 + (1 - w) * e * (1 - pde)
    fd = w * px + (1 - w) * pde
    f2 = max(1e-6, 1 - f1 - fd)
    return f1, fd, f2

  def record_market(self, mkt, won, odd):
    r = self.market_roi[mkt]
    r["n"] += 1
    r["profit"] = 0.9 * r["profit"] + 0.1 * ((odd - 1) if won else -1)

  def market_adjust(self, mkt):
    r = self.market_roi.get(mkt)
    if not r or r["n"] < 40:
      return 0.0
    roi = r["profit"] / r["n"]
    return max(-0.010, min(0.020, -roi * 0.4))

  def add(self, h, a, hg, ag, row=None, k=None, match_num=None, total=None):
    if k is None:
      k = (
          (48 - 32 * min(1.0, match_num / total))
          if (match_num is not None and total)
          else 32
      )
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
    t[a]["form"].append(3 if ag > hg else (1 if ag == hg else 0))
    self.hg.append(hg)
    self.ag.append(ag)
    self.h2h[(h, a)].append(hg - ag)
    self.h2h[(h, a)] = self.h2h[(h, a)][-8:]
    if row:
      for col, t1, k1, t2, k2 in (
          ("HC", h, "cfh", a, "caa"),
          ("AC", a, "cfa", h, "cah"),
          ("HY", h, "yfh", a, "yaa"),
          ("AY", a, "yfa", h, "yah"),
      ):
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

  def h2h_adjust(self, h, a, lh, la):
    hist = self.h2h.get((h, a), [])
    if len(hist) < 3:
      return lh, la, 0
    shift = (sum(hist) / len(hist)) * 0.15
    return max(0.3, lh + shift / 2), max(0.25, la - shift / 2), len(hist)

  def predict(self, h, a, lg="G"):
    P0 = self.lp[lg]
    ws = P0["w_shots"]
    N = MATRIX_N
    lh_g = self._m(self.hg, 1.5)
    la_g = self._m(self.ag, 1.2)
    lh_s = self._m(self.hsth, 4.5)
    la_s = self._m(self.hsta, 4.0)
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
    att_sh_h = self._m(sh["hst_h"], lh_s) / lh_s
    def_sh_a = self._m(sa["hstc_a"], lh_s) / lh_s
    att_sh_a = self._m(sa["hst_a"], la_s) / la_s
    def_sh_h = self._m(sh["hstc_h"], la_s) / la_s
    lam_s_h = max(
        0.3,
        min(5.0, lh_s * conv_h * att_sh_h * def_sh_a * (0.85 + 0.30 * fh)),
    )
    lam_s_a = max(
        0.25,
        min(4.5, la_s * conv_a * att_sh_a * def_sh_h * (0.85 + 0.30 * fa)),
    )
    lam_h = (1 - ws) * lam_g_h + ws * lam_s_h
    lam_a = (1 - ws) * lam_g_a + ws * lam_s_a
    agree = (lam_g_h - lam_g_a) * (lam_s_h - lam_s_a) > 0
    lam_h, lam_a, h2h_n = self.h2h_adjust(h, a, lam_h, lam_a)
    e = 1 / (
        1 + 10 ** ((self.elo.get(a, 1500) - self.elo.get(h, 1500) - 60) / 400)
    )
    pde = 0.20 + 0.12 * (1 - abs(e - 0.5) * 2)
    p1, px, M = self._p1px(lam_h, lam_a, P0["rho"])
    f1 = P0["w_dc"] * p1 + (1 - P0["w_dc"]) * e * (1 - pde)
    fd = P0["w_dc"] * px + (1 - P0["w_dc"]) * pde
    f2 = max(0.0, 1 - f1 - fd)
    c1, cx, c2 = self.calibrate(f1), self.calibrate(fd), self.calibrate(f2)
    ct = c1 + cx + c2 or 1.0
    f1, fd, f2 = c1 / ct, cx / ct, c2 / ct
    over = 1 - sum(self._p(lam_h + lam_a, k) for k in range(3))
    btts = sum(M[i][j] for i in range(1, N) for j in range(1, N))
    games = min(len(sh["hs"]) + len(sh["as"]), len(sa["hs"]) + len(sa["as"]))
    corners = (
        (self._m(sh["cfh"], 5) + self._m(sa["caa"], 5)) / 2,
        (self._m(sa["cfa"], 5) + self._m(sh["cah"], 5)) / 2,
    )
    yellows = (
        (self._m(sh["yfh"], 2) + self._m(sa["yaa"], 2)) / 2,
        (self._m(sa["yfa"], 2) + self._m(sh["yah"], 2)) / 2,
    )
    return {
        "p1": f1,
        "x": fd,
        "p2": f2,
        "over": over,
        "btts": btts,
        "M": M,
        "agree": agree,
        "lams": (lam_h, lam_a),
        "lams_g": (lam_g_h, lam_g_a),
        "lams_s": (lam_s_h, lam_s_a),
        "games": games,
        "corners": corners,
        "yellows": yellows,
        "h2h_n": h2h_n,
        "e": e,
        "pde": pde,
    }


def _f(v):
  try:
    return float(v)
  except Exception:
    return None


@st.cache_data(ttl=1800)
def find_season():
  for s in ["2627", "2526", "2425"]:
    try:
      r = requests.head(
          f"https://www.football-data.co.uk/mmz4281/{s}/E0.csv", timeout=8
      )
      if r.status_code == 200:
        return s
    except Exception as e:
      log_err("find_season", e)
  return "2526"


def prev_season(s):
  try:
    return f"{int(s[:2])-1:02d}{int(s[2:])-1:02d}"
  except Exception:
    return s


@st.cache_data(ttl=1800)
def load_seasonal(div, season):
  try:
    r = requests.get(
        f"https://www.football-data.co.uk/mmz4281/{season}/{div}.csv",
        timeout=20,
        headers=UA,
    )
    if r.status_code != 200:
      return []
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
  except Exception as e:
    log_err(f"load_seasonal {div}", e)
    return []


def load_many(divs, season):
  with ThreadPoolExecutor(max_workers=8) as ex:
    return dict(zip(divs, ex.map(lambda d: load_seasonal(d, season), divs)))


@st.cache_data(ttl=900)
def load_fixtures():
  rep = []
  rows = []
  seen = set()
  for u in [
      "https://www.football-data.co.uk/mmz4281/fixtures.csv",
      "https://www.football-data.co.uk/fixtures.csv",
      "http://www.football-data.co.uk/mmz4281/fixtures.csv",
  ]:
    try:
      r = requests.get(u, timeout=25, headers=UA)
      if r.status_code != 200:
        rep.append(f"{u.split('/')[-1]}: HTTP {r.status_code}")
        continue
      rd = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
      n = 0
      for x in rd:
        k = (x.get("Div"), x.get("Date"), x.get("HomeTeam"), x.get("AwayTeam"))
        if k in seen or not x.get("HomeTeam"):
          continue
        seen.add(k)
        rows.append(x)
        n += 1
      rep.append(f"{u.split('/')[-1]}: OK,{n}")
      if n:
        break
    except Exception as e:
      log_err("load_fixtures", e)
      rep.append(f"{u.split('/')[-1]}: {type(e).__name__}")
  return rows, rep


def parse_date(s):
  for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
    try:
      return datetime.strptime(str(s).strip(), fmt)
    except Exception:
      continue
  return None


def odd1(row, keys):
  for k in keys:
    v = _f(row.get(k))
    if v and v > 1.01:
      return v
  return None


def best_odd(row, pick):
  m = {
      "П1": ["MaxH", "B365H", "PSH"],
      "X": ["MaxD", "B365D", "PSD"],
      "П2": ["MaxA", "B365A", "PSA"],
      "ТБ 2.5": ["Max>2.5", "B365>2.5", "P>2.5"],
      "ТМ 2.5": ["Max<2.5", "B365<2.5", "P<2.5"],
  }
  return odd1(row, m.get(pick, []))


def market_probs(row):
  ph, px, pa = _f(row.get("PSH")), _f(row.get("PSD")), _f(row.get("PSA"))
  if not (ph and px and pa):
    return None
  i1, ix, ia = 1 / ph, 1 / px, 1 / pa
  s = i1 + ix + ia
  return (i1 / s, ix / s, ia / s)


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


def kelly(prob, odds, bank=10000.0, fraction=0.25):
  if prob <= 0 or odds <= 1.01:
    return 0.0
  b = odds - 1.0
  q = 1.0 - prob
  f = (b * prob - q) / b
  if f <= 0:
    return 0.0
  return min(bank * f * fraction, bank * 0.05)


def render_score_heatmap(M):
  fig = px.imshow(
      M,
      labels=dict(x="Голы гостей", y="Голы хозяев", color="Вероятность"),
      x=list(range(MATRIX_N)),
      y=list(range(MATRIX_N)),
      color_continuous_scale="Tealgrn",
      aspect="auto",
  )
  fig.update_layout(
      margin=dict(l=10, r=10, t=10, b=10),
      paper_bgcolor="rgba(0,0,0,0)",
      plot_bgcolor="rgba(0,0,0,0)",
      font=dict(color="#e2e8f0"),
      height=260,
  )
  st.plotly_chart(fig, use_container_width=True)


engine = Engine.load_state()

st.sidebar.title("🏟 NEURO BET PRO v7")
mode = st.sidebar.selectbox(
    "Режим работы", ["🎯 Прогнозы на матчи", "📊 Бэктест и Аналитика"]
)

if mode == "🎯 Прогнозы на матчи":
  st.markdown(
      """
    <div class="hero">
        <h1>NEURO BET PRO v7</h1>
        <p>Нейро-пуассоновский движок с поправками Диксона-Коулза, калибровкой Платта и CLV-фильтрацией</p>
    </div>
    """,
      unsafe_allow_html=True,
  )

  season = find_season()
  divs = list(DIV_NAMES.keys())
  with st.spinner("🔄 Обновление моделей и расчет коэффициентов лиг..."):
    data_dict = load_many(divs[:15], season)
    for div, rows in data_dict.items():
      if not rows:
        prev_s = prev_season(season)
        rows = load_seasonal(div, prev_s)
      total = len(rows)
      for idx, r in enumerate(rows):
        h, a = r.get("HomeTeam"), r.get("AwayTeam")
        hg, ag = _f(r.get("FTHG")), _f(r.get("FTAG"))
        if h and a and hg is not None and ag is not None:
          engine.add(h, a, int(hg), int(ag), row=r, match_num=idx, total=total)

  st.sidebar.header("⚙️ Фильтры прогнозов")
  selected_goal = st.sidebar.selectbox("Цель стратегии", list(GOALS.keys()))
  gconf = GOALS[selected_goal]

  fixtures, _ = load_fixtures()
  tab_matches, tab_all = st.tabs(["🔥 Отобранные матчи", "📋 Все матчи туров"])

  with tab_matches:
    st.subheader(f"Сигналы под стратегию: {selected_goal}")
    count = 0
    for row in fixtures[:50]:
      h, a = row.get("HomeTeam"), row.get("AwayTeam")
      div = row.get("Div", "G")
      if not h or not a:
        continue

      P = engine.predict(h, a, div if div in DIV_NAMES else "G")
      mkt = market_probs(row)
      if mkt:
        adj = engine.market_adjust("1X2")
        P = blend_market(
            P, (mkt[0] + adj, mkt[1], mkt[2] - adj), gconf["w_market"]
        )

      max_p = max(P["p1"], P["x"], P["p2"])
      pick = "П1" if max_p == P["p1"] else ("X" if max_p == P["x"] else "П2")
      odd = best_odd(row, pick)

      if P["games"] < gconf["min_games"]:
        continue
      if max_p < gconf["thr"]:
        continue
      if gconf["dis"] and not P["agree"]:
        continue

      count += 1
      with st.expander(f"🏟 {h} vs {a} ({DIV_NAMES.get(div, div)})"):
        col1, col2 = st.columns([2, 1])
        with col1:
          st.write(
              f"**Вероятности:** П1: `{P['p1']*100:.1f}%` | Х:"
              f" `{P['x']*100:.1f}%` | П2: `{P['p2']*100:.1f}%`"
          )
          st.write(
              f"**Ожидаемые голы ($\lambda$):** Хозяева `{P['lams'][0]:.2f}` -"
              f" Гости `{P['lams'][1]:.2f}`"
          )
          if odd:
            st.write(
                f"**Рекомендация:** `{pick}` по коэффициенту `{odd}`. Рекомендуемая"
                f" ставка по Келли:"
                f" `{kelly(max_p, odd, 10000.0, 0.25):.2f} руб.`"
            )
        with col2:
          render_score_heatmap(P["M"])

    if count == 0:
      st.info(
          "Нет матчей, полностью удовлетворяющих жестким фильтрам текущей"
          " стратегии. Попробуйте изменить параметры в сайдбаре."
      )

  with tab_all:
    st.subheader("Полный список ближайших матчей")
    for row in fixtures[:30]:
      h, a = row.get("HomeTeam"), row.get("AwayTeam")
      div = row.get("Div", "G")
      if h and a:
        st.text(
            f"{row.get('Date','')} | {DIV_NAMES.get(div, div)}: {h} — {a}"
        )

  engine.save_state()

else:
  st.subheader("📊 Анализ доходности по рынкам и CLV")
  if engine.market_roi:
    roi_data = []
    for mkt, stats in engine.market_roi.items():
      n = stats["n"]
      prof = stats["profit"]
      roi = (prof / n) * 100 if n > 0 else 0
      roi_data.append({
          "Рынок": mkt,
          "Ставок": n,
          "Прибыль": round(prof, 2),
          "ROI (%)": round(roi, 2),
      })
    st.dataframe(roi_data, use_container_width=True)
  else:
    st.info(
        "Пока недостаточно исторических данных для формирования отчета. Данные"
        " собираются автоматически по мере просчета матчей."
    )
