import streamlit as st
import requests
import csv
import io
import json
import os
import math
from datetime import datetime, timedelta
from collections import defaultdict

st.set_page_config(page_title="Football Betting AI Expert Pro", page_icon="🚀", layout="wide")

HISTORY_FILE = "betting_expert_data.json"

DIV_NAMES = {
    "E0": "🏴󠁢󠁮󠁧󠁿 Англия (АПЛ)", "SP1": "🇪 Испания (Ла Лига)",
    "I1": "🇮 Италия (Серия А)", "D1": "🇩🇪 Германия (Бундеслига)",
    "F1": "🇫 Франция (Лига 1)", "N1": "🇳🇱 Нидерланды",
    "P1": "🇵🇹 Португалия", "T1": "🇹🇷 Турция", "B1": "🇧🇪 Бельгия",
    "C1": "🏆 Лига Чемпионов", "EL": "🏆 Лига Европы",
}
SEASONAL_FILES = {
    "E0": "E0.csv", "SP1": "SP1.csv", "I1": "I1.csv", "D1": "D1.csv",
    "F1": "F1.csv", "N1": "N1.csv", "P1": "P1.csv", "T1": "T1.csv",
    "B1": "B1.csv", "C1": "C1.csv",
}

class Engine:
    def __init__(self):
        self.elo = {}
        self.stats = defaultdict(lambda: {"hs": [], "hc": [], "as": [], "ac": [], "form": []})
        self.home_goals = []
        self.away_goals = []

    def add_result(self, h, a, hg, ag):
        rh = self.elo.get(h, 1500); ra = self.elo.get(a, 1500)
        eh = 1 / (1 + 10 ** ((ra - (rh + 60)) / 400))
        sh = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
        self.elo[h] = rh + 32 * (sh - eh); self.elo[a] = ra + 32 * ((1 - sh) - (1 - eh))
        s = self.stats
        s[h]["hs"].append(hg); s[h]["hc"].append(ag)
        s[a]["as"].append(ag); s[a]["ac"].append(hg)
        s[h]["form"].append(3 if hg > ag else (1 if hg == ag else 0))
        s[a]["form"].append(3 if ag > hg else (1 if hg == ag else 0))
        self.home_goals.append(hg); self.away_goals.append(ag)
        for t in (h, a):
            for k in s[t]: s[t][k] = s[t][k][-12:]

    def _mean(self, lst, d=1.0): return sum(lst)/len(lst) if lst else d
    def _form(self, t):
        f = self.stats[t]["form"][-5:]
        return (sum(f)/(len(f)*3)) if f else 0.5

    def predict(self, h, a):
        lh = self._mean(self.home_goals, 1.5); la = self._mean(self.away_goals, 1.2)
        sh, sa = self.stats[h], self.stats[a]
        att_h = self._mean(sh["hs"], lh)/lh; def_h = self._mean(sh["hc"], la)/la
        att_a = self._mean(sa["as"], la)/la; def_a = self._mean(sa["ac"], lh)/lh
        fh, fa = self._form(h), self._form(a)
        lam_h = max(0.3, min(4.0, lh*att_h*def_a*1.10*(0.85+0.30*fh)))
        lam_a = max(0.25, min(3.5, la*att_a*def_h*0.95*(0.85+0.30*fa)))
        p_h = p_d = p_a = 0.0
        for i in range(7):
            for j in range(7):
                p = self._pois(lam_h, i)*self._pois(lam_a, j)
                if i == 0 and j == 0: p *= 1.08
                elif (i, j) in [(1,0),(0,1),(1,1)]: p *= 0.96
                if i > j: p_h += p
                elif i == j: p_d += p
                else: p_a += p
        tot = p_h+p_d+p_a; p_h, p_d, p_a = p_h/tot, p_d/tot, p_a/tot
        e = 1/(1+10**((self.elo.get(a,1500)-self.elo.get(h,1500)-60)/400))
        pd_e = 0.20+0.12*(1-abs(e-0.5)*2)
        f_h = 0.72*p_h+0.28*e*(1-pd_e)
        f_d = 0.72*p_d+0.28*pd_e
        f_a = 0.72*p_a+0.28*(1-e)*(1-pd_e)
        tot = f_h+f_d+f_a; f_h, f_d, f_a = f_h/tot, f_d/tot, f_a/tot
        probs = {"П1": f_h, "X": f_d, "П2": f_a}
        ranked = sorted(probs.items(), key=lambda x: -x[1])
        games = min(len(sh["hs"])+len(sh["as"]), len(sa["hs"])+len(sa["as"]))
        return probs, ranked[0], ranked[0][1]-ranked[1][1], (lam_h, lam_a), games

    def _pois(self, l, k): return math.exp(-l)*l**k/math.factorial(k)

@st.cache_data(ttl=1800)
def find_season():
    for s in ["2627", "2526", "2425"]:
        try:
            r = requests.head(f"https://www.football-data.co.uk/mmz4281/{s}/E0.csv", timeout=8)
            if r.status_code == 200: return s
        except Exception: continue
    return "2526"

@st.cache_data(ttl=1800)
def load_seasonal(file, season):
    try:
        r = requests.get(f"https://www.football-data.co.uk/mmz4281/{season}/{file}",
                         timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return list(csv.DictReader(io.StringIO(r.text)))
    except Exception: return []

@st.cache_data(ttl=600)
def load_fixtures():
    try:
        r = requests.get("https://www.football-data.co.uk/fixtures.csv",
                         timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return list(csv.DictReader(io.StringIO(r.text)))
    except Exception: return []

def parse_date(s):
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try: return datetime.strptime(s.strip(), fmt)
        except Exception: continue
    return None

def get_odds(row):
    for pref in ("B365", "PS", "BS", "BW", "WH", "Max"):
        h, d, a = row.get(pref+"H"), row.get(pref+"D"), row.get(pref+"A")
        if h and d and a:
            try: return float(h), float(d), float(a)
            except Exception: continue
    return None

def kelly(prob, odds, bank, frac):
    if prob <= 0 or odds <= 1: return 0.0
    b = odds-1
    k = (b*prob-(1-prob))/b
    return round(min(max(0, k*frac), 0.05)*bank, 2)

def load_data():
    if os.path.exists(HISTORY_FILE):
        try: return json.load(open(HISTORY_FILE, encoding="utf-8"))
        except Exception: pass
    return {"bank": 10000.0, "bets": [], "forecasts": [], "stats": {"won":0,"lost":0,"profit":0}}

def save_data(d):
    json.dump(d, open(HISTORY_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

if "data" not in st.session_state: st.session_state.data = load_data()

st.title("🚀 Football Betting AI Expert Pro")

with st.sidebar:
    st.header("⚙️ Фильтры качества")
    bank = st.session_state.data["bank"]
    st.metric("💰 Банк", f"{bank:.2f} у.е.")
    kelly_frac = st.slider("Келли (дробь)", 0.10, 0.40, 0.25, 0.05)
    st.markdown("**Коридор коэффициентов**")
    min_odd = st.slider("Мин. кэф", 1.20, 2.00, 1.55, 0.05)
    max_odd = st.slider("Макс. кэф", 2.00, 6.00, 3.40, 0.10)
    st.markdown("**Требования к перевесу**")
    min_edge = st.slider("Edge над безубыточностью (п.п.)", 0, 10, 3) / 100
    min_ev = st.slider("Мин. EV базовый (%)", 0, 10, 3) / 100
    min_margin = st.slider("Мин. отрыв от 2-го исхода (%)", 0, 25, 4) / 100
    if st.button("🔄 Сброс"):
        st.session_state.data = {"bank":10000.0,"bets":[],"forecasts":[],"stats":{"won":0,"lost":0,"profit":0}}
        save_data(st.session_state.data); st.cache_data.clear(); st.rerun()

tab1, tab2, tab3 = st.tabs(["🔍 Сканер", "📋 Портфель", "📊 Статистика"])

with tab1:
    st.header("⚽ Сканирование будущих матчей")
    divs = st.multiselect("Лиги", list(DIV_NAMES.keys()),
                          format_func=lambda d: DIV_NAMES[d],
                          default=["E0","SP1","I1","D1","F1"])
    days = st.slider("Горизонт (дней)", 1, 21, 14)

    if st.button("⚡ Сканировать", type="primary"):
        if not divs:
            st.warning("Выбери лиги"); st.stop()
        season = find_season()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        limit = today + timedelta(days=days)
        funnel = {"trained":0,"fixtures":0,"in_window":0,"with_odds":0,"passed":0}
        engine = Engine()

        prog = st.progress(0.0, text="Обучение на сыгранных матчах...")
        for i, dcode in enumerate(divs):
            for r in load_seasonal(SEASONAL_FILES.get(dcode, dcode+".csv"), season):
                if r.get("FTHG") not in (None,"") and r.get("FTAG") not in (None,""):
                    try:
                        engine.add_result(r["HomeTeam"], r["AwayTeam"], float(r["FTHG"]), float(r["FTAG"]))
                        funnel["trained"] += 1
                    except Exception: continue
            prog.progress((i+1)/len(divs))
        prog.empty()

        fixtures = load_fixtures()
        funnel["fixtures"] = len(fixtures)
        if not fixtures:
            st.error("fixtures.csv недоступен"); st.stop()

        forecasts, added = [], 0
        existing = {b["match"] for b in st.session_state.data["bets"]}

        for r in fixtures:
            if r.get("Div") not in divs: continue
            d = parse_date(r.get("Date",""))
            if not d or not (today <= d <= limit): continue
            funnel["in_window"] += 1
            odds = get_odds(r)
            if not odds: continue
            funnel["with_odds"] += 1
            h, a = r.get("HomeTeam","").strip(), r.get("AwayTeam","").strip()
            if not h or not a: continue

            probs, (pick, prob), margin, lams, games = engine.predict(h, a)
            oh, od, oa = odds
            odd = {"П1":oh,"X":od,"П2":oa}[pick]
            ev = prob*odd - 1
            breakeven = 1/odd
            edge_pp = prob - breakeven
            required_ev = min_ev + max(0.0, odd-2.5)*0.02  # выше кэф → выше требование

            reasons = []
            ok = True
            if not (min_odd <= odd <= max_odd): ok = False; reasons.append(f"кэф {odd:.2f} вне коридора")
            if edge_pp < min_edge: ok = False; reasons.append(f"edge {edge_pp*100:.1f} п.п. < {min_edge*100:.0f}")
            if ev < required_ev: ok = False; reasons.append(f"EV {ev*100:.1f}% < {required_ev*100:.1f}%")
            if margin < min_margin: ok = False; reasons.append("слабый отрыв от 2-го исхода")
            if games < 4: ok = False; reasons.append(f"мало данных ({games} игр)")
            if ok: funnel["passed"] += 1

            forecasts.append({
                "league": DIV_NAMES.get(r["Div"], r["Div"]), "match": f"{h} vs {a}",
                "date": d.strftime("%d.%m")+(f" {r['Time']}" if r.get("Time") else ""),
                "pick": pick, "prob": prob, "odd": odd, "ev": ev,
                "breakeven": breakeven, "edge_pp": edge_pp, "margin": margin,
                "lams": lams, "games": games, "passed": ok,
                "reasons": reasons,
                "stake": kelly(prob, odd, bank, kelly_frac) if ok else 0.0
            })
            if ok and f"{h} vs {a}" not in existing and forecasts[-1]["stake"] > 0:
                st.session_state.data["bets"].append({"match": f"{h} vs {a}",
                    "league": DIV_NAMES.get(r["Div"], r["Div"]), "pick": pick,
                    "odds": odd, "stake": forecasts[-1]["stake"], "status": "pending", "prob": prob})
                existing.add(f"{h} vs {a}"); added += 1

        forecasts.sort(key=lambda x: (x["passed"], x["ev"]), reverse=True)
        st.session_state.data["forecasts"] = forecasts
        st.session_state.data["funnel"] = funnel
        save_data(st.session_state.data)
        st.success(f"✅ Валуйных: {funnel['passed']}. В портфель: {added}")
        st.rerun()

    funnel = st.session_state.data.get("funnel")
    if funnel:
        with st.expander("🔬 Диагностика"):
            st.write(f"Обучено матчей: **{funnel['trained']}** | В fixtures: **{funnel['fixtures']}** | "
                     f"В окне: **{funnel['in_window']}** | С кэфами: **{funnel['with_odds']}** | "
                     f"Прошли ВСЕ фильтры: **{funnel['passed']}**")

    for f in st.session_state.data.get("forecasts", []):
        color = "#10b981" if f["passed"] else "#475569"
        badge = "🟢 ВАЛУЙ" if f["passed"] else "⛔ отклонён"
        why = "" if f["passed"] else " | причины: " + "; ".join(f["reasons"])
        st.markdown(f"""
        <div style="background:rgba(30,41,59,.75);padding:16px;border-radius:12px;margin-bottom:10px;border-left:5px solid {color}">
          <div style="display:flex;justify-content:space-between">
            <span style="background:#38bdf8;padding:3px 10px;border-radius:6px;font-size:.75rem;color:#fff;font-weight:700">{f['league']}</span>
            <span style="color:#94a3b8">📅 {f['date']} | {badge}</span>
          </div>
          <div style="font-size:1.15rem;font-weight:700;color:#f8fafc;margin:8px 0">⚽ {f['match']}</div>
          <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px;font-size:.85rem">
            <div><span style="color:#94a3b8">Прогноз:</span> <b style="color:#facc15">{f['pick']}</b></div>
            <div><span style="color:#94a3b8">P модели:</span> <b style="color:#4ade80">{f['prob']*100:.1f}%</b></div>
            <div><span style="color:#94a3b8">Безубыточ.:</span> <b style="color:#f87171">{f['breakeven']*100:.1f}%</b></div>
            <div><span style="color:#94a3b8">Edge:</span> <b style="color:#4ade80">+{f['edge_pp']*100:.1f} п.п.</b></div>
            <div><span style="color:#94a3b8">Кэф:</span> <b style="color:#facc15">{f['odd']:.2f}</b></div>
            <div><span style="color:#94a3b8">EV:</span> <b style="color:{'#10b981' if f['ev']>0 else '#ef4444'}">{f['ev']*100:+.1f}%</b></div>
          </div>
          <div style="margin-top:8px;color:#cbd5e1;font-size:.8rem">xG {f['lams'][0]:.2f}–{f['lams'][1]:.2f} | игр: {f['games']} | Келли: <b style="color:#facc15">{f['stake']:.2f}</b>{why}</div>
        </div>""", unsafe_allow_html=True)

with tab2:
    st.header("📋 Портфель")
    bets = st.session_state.data["bets"]
    if not bets: st.info("Пусто")
    for b in bets:
        icon = {"pending":"⏳","won":"🟢","lost":"🔴"}[b["status"]]
        st.markdown(f"{icon} **{b['match']}** | {b['pick']} @ {b['odds']:.2f} | {b['stake']:.2f} у.е. | P={b.get('prob',0)*100:.0f}%")

with tab3:
    s = st.session_state.data["stats"]; total = s["won"]+s["lost"]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Банк", f"{st.session_state.data['bank']:.2f}")
    c2.metric("Ставок", total)
    c3.metric("WinRate", f"{(s['won']/total*100) if total else 0:.1f}%")
    c4.metric("Profit", f"{s['profit']:+.2f}")
