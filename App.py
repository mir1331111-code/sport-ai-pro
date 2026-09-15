import streamlit as st
import requests, csv, io, json, os, math
from datetime import datetime, timedelta
from collections import defaultdict

st.set_page_config(page_title="Football Betting AI Expert Pro", page_icon="🚀", layout="wide")
HISTORY_FILE = "betting_expert_data.json"

DIV_NAMES = {"E0":"🏴󠁮󠁧󠁿 АПЛ","SP1":"🇪🇸 Ла Лига","I1":"🇮🇹 Серия А","D1":"🇩🇪 Бундеслига",
             "F1":"🇫🇷 Лига 1","N1":"🇳🇱 Эредивизи","P1":"🇵🇹 Примейра","T1":"🇹🇷 Суперлига",
             "B1":"🇧🇪 Про-лига","C1":"🏆 ЛЧ"}
SEASONAL = {d: d+".csv" for d in DIV_NAMES}

# Коридоры кэфов по рынкам
CORRIDORS = {"1X2": (1.45, 3.80), "OU": (1.55, 2.70), "AH": (1.60, 2.50)}

class Engine:
    def __init__(self):
        self.elo = {}
        self.stats = defaultdict(lambda: {"hs":[],"hc":[],"as":[],"ac":[],"form":[],
                                          "cf_h":[],"ca_h":[],"cf_a":[],"ca_a":[],
                                          "yf_h":[],"ya_h":[],"yf_a":[],"ya_a":[]})
        self.home_goals, self.away_goals = [], []

    def add_result(self, h, a, hg, ag, row=None):
        rh, ra = self.elo.get(h,1500), self.elo.get(a,1500)
        eh = 1/(1+10**((ra-(rh+60))/400))
        sh = 1.0 if hg>ag else (0.5 if hg==ag else 0.0)
        self.elo[h] = rh+32*(sh-eh); self.elo[a] = ra+32*((1-sh)-(1-eh))
        s = self.stats
        s[h]["hs"].append(hg); s[h]["hc"].append(ag)
        s[a]["as"].append(ag); s[a]["ac"].append(hg)
        s[h]["form"].append(3 if hg>ag else (1 if hg==ag else 0))
        s[a]["form"].append(3 if ag>hg else (1 if hg==ag else 0))
        self.home_goals.append(hg); self.away_goals.append(ag)
        if row:
            hc, ac = _f(row.get("HC")), _f(row.get("AC"))
            hy, ay = _f(row.get("HY")), _f(row.get("AY"))
            if hc is not None: s[h]["cf_h"].append(hc); s[a]["ca_a"].append(hc)
            if ac is not None: s[a]["cf_a"].append(ac); s[h]["ca_h"].append(ac)
            if hy is not None: s[h]["yf_h"].append(hy); s[a]["ya_a"].append(hy)
            if ay is not None: s[a]["yf_a"].append(ay); s[h]["ya_h"].append(ay)
        for t in (h,a):
            for k in s[t]: s[t][k] = s[t][k][-12:]

    def _m(self, l, d=1.0): return sum(l)/len(l) if l else d
    def _form(self, t):
        f = self.stats[t]["form"][-5:]
        return (sum(f)/(len(f)*3)) if f else 0.5

    def predict(self, h, a):
        lh, la = self._m(self.home_goals,1.5), self._m(self.away_goals,1.2)
        sh, sa = self.stats[h], self.stats[a]
        att_h, def_h = self._m(sh["hs"],lh)/lh, self._m(sh["hc"],la)/la
        att_a, def_a = self._m(sa["as"],la)/la, self._m(sa["ac"],lh)/lh
        fh, fa = self._form(h), self._form(a)
        lam_h = max(0.3, min(4.0, lh*att_h*def_a*1.10*(0.85+0.30*fh)))
        lam_a = max(0.25, min(3.5, la*att_a*def_h*0.95*(0.85+0.30*fa)))
        M = [[self._p(lam_h,i)*self._p(lam_a,j) for j in range(7)] for i in range(7)]
        for i in range(7):
            for j in range(7):
                if i==0 and j==0: M[i][j]*=1.08
                elif (i,j) in [(1,0),(0,1),(1,1)]: M[i][j]*=0.96
        tot = sum(map(sum,M))
        M = [[v/tot for v in r] for r in M]
        p_h = sum(M[i][j] for i in range(7) for j in range(7) if i>j)
        p_d = sum(M[i][i] for i in range(7))
        p_a = 1-p_h-p_d
        e = 1/(1+10**((self.elo.get(a,1500)-self.elo.get(h,1500)-60)/400))
        pd_e = 0.20+0.12*(1-abs(e-0.5)*2)
        f_h, f_d = 0.72*p_h+0.28*e*(1-pd_e), 0.72*p_d+0.28*pd_e
        f_a = 1-f_h-f_d
        lam_t = lam_h+lam_a
        p_over = 1-sum(self._p(lam_t,k) for k in range(3))
        games = min(len(sh["hs"])+len(sh["as"]), len(sa["hs"])+len(sa["as"]))
        # ожидания угловых/жёлтых
        exp_c_h = (self._m(sh["cf_h"],5)+self._m(sa["ca_a"],5))/2
        exp_c_a = (self._m(sa["cf_a"],5)+self._m(sh["ca_h"],5))/2
        exp_y_h = (self._m(sh["yf_h"],2)+self._m(sa["ya_a"],2))/2
        exp_y_a = (self._m(sa["yf_a"],2)+self._m(sh["ya_h"],2))/2
        return {"p1":f_h,"x":f_d,"p2":f_a,"over":p_over,"matrix":M,
                "lams":(lam_h,lam_a),"games":games,
                "corners":(exp_c_h,exp_c_a),"yellows":(exp_y_h,exp_y_a)}

    def _p(self,l,k): return math.exp(-l)*l**k/math.factorial(k)

def _f(v):
    try: return float(v)
    except Exception: return None

@st.cache_data(ttl=1800)
def find_season():
    for s in ["2627","2526","2425"]:
        try:
            r = requests.head(f"https://www.football-data.co.uk/mmz4281/{s}/E0.csv", timeout=8)
            if r.status_code==200: return s
        except Exception: continue
    return "2526"

@st.cache_data(ttl=1800)
def load_seasonal(file, season):
    try:
        r = requests.get(f"https://www.football-data.co.uk/mmz4281/{season}/{file}",
                         timeout=20, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status(); return list(csv.DictReader(io.StringIO(r.text)))
    except Exception: return []

@st.cache_data(ttl=600)
def load_fixtures():
    try:
        r = requests.get("https://www.football-data.co.uk/fixtures.csv",
                         timeout=20, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status(); return list(csv.DictReader(io.StringIO(r.text)))
    except Exception: return []

def parse_date(s):
    for fmt in ("%d/%m/%Y","%d/%m/%y"):
        try: return datetime.strptime(s.strip(), fmt)
        except Exception: continue
    return None

def odds_pair(row, keys):
    for k in keys:
        v = _f(row.get(k))
        if v and v>1.01: return v
    return None

def kelly(prob, odds, bank, frac):
    if prob<=0 or odds<=1: return 0.0
    b = odds-1; k = (b*prob-(1-prob))/b
    return round(min(max(0,k*frac),0.05)*bank,2)

def load_data():
    if os.path.exists(HISTORY_FILE):
        try: return json.load(open(HISTORY_FILE, encoding="utf-8"))
        except Exception: pass
    return {"bank":10000.0,"bets":[],"cards":[],"stats":{"won":0,"lost":0,"profit":0}}

def save_data(d): json.dump(d, open(HISTORY_FILE,"w",encoding="utf-8"), indent=2, ensure_ascii=False)

if "data" not in st.session_state: st.session_state.data = load_data()
st.title("🚀 Football Betting AI Expert Pro")

with st.sidebar:
    st.header("⚙️ Фильтры")
    bank = st.session_state.data["bank"]
    st.metric("💰 Банк", f"{bank:.2f}")
    kelly_frac = st.slider("Келли дробь", 0.10, 0.40, 0.25, 0.05)
    min_edge = st.slider("Edge над безубыточностью (п.п.)", 0, 8, 2)/100
    min_ev = st.slider("Мин. EV (%)", 0, 10, 2)/100
    mkt_1x2 = st.checkbox("Рынок 1X2", True)
    mkt_ou = st.checkbox("Рынок Тотал 2.5", True)
    mkt_ah = st.checkbox("Рынок Азиатская фора", True)
    if st.button("🔄 Сброс"):
        st.session_state.data = {"bank":10000.0,"bets":[],"cards":[],"stats":{"won":0,"lost":0,"profit":0}}
        save_data(st.session_state.data); st.cache_data.clear(); st.rerun()

tab1, tab2, tab3 = st.tabs(["🔍 Сканер (все рынки)", "📋 Портфель", "📊 Статистика"])

with tab1:
    st.header("⚽ Сканер: 1X2 + Тотал 2.5 + Форы + стат-прогнозы")
    divs = st.multiselect("Лиги", list(DIV_NAMES.keys()), format_func=lambda d: DIV_NAMES[d],
                          default=["E0","SP1","I1","D1","F1"])
    days = st.slider("Горизонт (дней)", 1, 21, 14)

    if st.button("⚡ Сканировать", type="primary"):
        if not divs: st.warning("Выбери лиги"); st.stop()
        season = find_season()
        today = datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
        limit = today+timedelta(days=days)
        engine = Engine(); trained = 0
        prog = st.progress(0.0, text="Обучение (голы, угловые, жёлтые)...")
        for i,d in enumerate(divs):
            for r in load_seasonal(SEASONAL[d], season):
                if r.get("FTHG") not in (None,"") and r.get("FTAG") not in (None,""):
                    try:
                        engine.add_result(r["HomeTeam"], r["AwayTeam"], float(r["FTHG"]), float(r["FTAG"]), r)
                        trained += 1
                    except Exception: continue
            prog.progress((i+1)/len(divs))
        prog.empty()
        fixtures = load_fixtures()
        if not fixtures: st.error("fixtures.csv недоступен"); st.stop()

        cards, added, passed_cnt = [], 0, 0
        existing = {b["match"]+"|"+b["pick"] for b in st.session_state.data["bets"]}

        for r in fixtures:
            if r.get("Div") not in divs: continue
            d = parse_date(r.get("Date",""))
            if not d or not (today<=d<=limit): continue
            h, a = r.get("HomeTeam","").strip(), r.get("AwayTeam","").strip()
            if not h or not a: continue
            P = engine.predict(h, a)
            if P["games"] < 4: continue

            cands = []
            if mkt_1x2:
                oh, od, oa = odds_pair(r,["B365H","PSH","MaxH"]), odds_pair(r,["B365D","PSD","MaxD"]), odds_pair(r,["B365A","PSA","MaxA"])
                if oh: cands.append(("1X2","П1",P["p1"],oh))
                if od: cands.append(("1X2","X",P["x"],od))
                if oa: cands.append(("1X2","П2",P["p2"],oa))
            if mkt_ou:
                o_over = odds_pair(r,["B365>2.5","P>2.5","Max>2.5"])
                o_under = odds_pair(r,["B365<2.5","P<2.5","Max<2.5"])
                if o_over: cands.append(("OU","ТБ 2.5",P["over"],o_over))
                if o_under: cands.append(("OU","ТМ 2.5",1-P["over"],o_under))
            if mkt_ah:
                ahh = _f(r.get("AHh")); ohh = odds_pair(r,["B365AHH","PAHH"]); oha = odds_pair(r,["B365AHA","PAHA"])
                if ahh is not None and abs((ahh*2) % 2) == 1 and ohh and oha:  # только половинные форы
                    p_cover = sum(P["matrix"][i][j] for i in range(7) for j in range(7) if (i-j+ahh) > 0.001)
                    cands.append(("AH", f"Ф1 ({ahh:+.1f})", p_cover, ohh))
                    cands.append(("AH", f"Ф2 ({-ahh:+.1f})", 1-p_cover, oha))

            rows_out = []
            best_pass = None
            for mkt, pick, prob, odd in cands:
                lo, hi = CORRIDORS[mkt]
                ev = prob*odd-1; be = 1/odd; edge = prob-be
                req_ev = min_ev + max(0.0, odd-2.5)*0.02
                ok = (lo<=odd<=hi) and (edge>=min_edge) and (ev>=req_ev)
                if ok:
                    passed_cnt += 1
                    st_k = kelly(prob, odd, bank, kelly_frac)
                    if best_pass is None or ev > best_pass[3]:
                        best_pass = (mkt, pick, odd, ev, prob, st_k)
                rows_out.append({"mkt":mkt,"pick":pick,"prob":prob,"odd":odd,
                                 "ev":ev,"be":be,"edge":edge,"ok":ok})
            if not rows_out: continue

            cards.append({"league":DIV_NAMES.get(r["Div"],r["Div"]),
                          "match":f"{h} vs {a}",
                          "date":d.strftime("%d.%m")+(f" {r['Time']}" if r.get("Time") else ""),
                          "rows":rows_out,
                          "corners":P["corners"],"yellows":P["yellows"],
                          "lams":P["lams"],
                          "best":best_pass})
            if best_pass and best_pass[5] > 0:
                key = f"{h} vs {a}|{best_pass[1]}"
                if key not in existing:
                    st.session_state.data["bets"].append({"match":f"{h} vs {a}",
                        "league":DIV_NAMES.get(r["Div"],r["Div"]),"pick":best_pass[1],
                        "market":best_pass[0],"odds":best_pass[2],"stake":best_pass[5],
                        "status":"pending","prob":best_pass[4]})
                    existing.add(key); added += 1

        cards.sort(key=lambda c: (c["best"] is not None, c["best"][3] if c["best"] else -1), reverse=True)
        st.session_state.data["cards"] = cards
        save_data(st.session_state.data)
        st.success(f"✅ Обучено: {trained} матчей | событий с валуем: {passed_cnt} | в портфель: {added}")
        st.rerun()

    cards = st.session_state.data.get("cards", [])
    if not cards:
        st.info("Нажми «Сканировать»")
    for c in cards:
        has = c["best"] is not None
        color = "#10b981" if has else "#475569"
        badge = "🟢 ВАЛУЙ" if has else "⚪ без валуя"
        lines = ""
        for rw in c["rows"]:
            mark = "✅" if rw["ok"] else "⛔"
            lines += (f"<div style='display:grid;grid-template-columns:70px 90px 1fr 1fr 1fr 1fr 40px;"
                      f"gap:6px;font-size:.82rem;padding:3px 0;border-top:1px solid rgba(255,255,255,.06)'>"
                      f"<span style='color:#94a3b8'>{rw['mkt']}</span>"
                      f"<b style='color:#facc15'>{rw['pick']}</b>"
                      f"<span>P: <b style='color:#4ade80'>{rw['prob']*100:.1f}%</b></span>"
                      f"<span>Безуб: <b style='color:#f87171'>{rw['be']*100:.1f}%</b></span>"
                      f"<span>Edge: <b style='color:{'#4ade80' if rw['edge']>0 else '#f87171'}'>{rw['edge']*100:+.1f}</b></span>"
                      f"<span>Кэф <b>{rw['odd']:.2f}</b> EV <b style='color:{'#10b981' if rw['ev']>0 else '#ef4444'}'>{rw['ev']*100:+.1f}%</b></span>"
                      f"<span>{mark}</span></div>")
        ch, ca = c["corners"]; yh, ya = c["yellows"]
        st.markdown(f"""
        <div style="background:rgba(30,41,59,.75);padding:16px;border-radius:12px;margin-bottom:12px;border-left:5px solid {color}">
          <div style="display:flex;justify-content:space-between">
            <span style="background:#38bdf8;padding:3px 10px;border-radius:6px;font-size:.75rem;color:#fff;font-weight:700">{c['league']}</span>
            <span style="color:#94a3b8">📅 {c['date']} | {badge}</span>
          </div>
          <div style="font-size:1.15rem;font-weight:700;color:#f8fafc;margin:8px 0">⚽ {c['match']}</div>
          {lines}
          <div style="margin-top:10px;color:#cbd5e1;font-size:.8rem">
             Угловые ожидание: <b style="color:#facc15">{ch:.1f}–{ca:.1f}</b> (всего {ch+ca:.1f}) |
            🟨 Жёлтые: <b style="color:#facc15">{yh:.1f}–{ya:.1f}</b> (всего {yh+ya:.1f}) |
            xG: {c['lams'][0]:.2f}–{c['lams'][1]:.2f}
            {f"| 💰 Келли: <b style='color:#facc15'>{c['best'][5]:.2f}</b> на {c['best'][1]} @ {c['best'][2]:.2f}" if has else ""}
          </div>
          <div style="color:#64748b;font-size:.72rem;margin-top:4px">Угловые/жёлтые — прогноз ожидания: сравни с линией букмекера и посчитай EV в калькуляторе ниже.</div>
        </div>""", unsafe_allow_html=True)

    with st.expander("🧮 Ручной EV-калькулятор (угловые, жёлтые, любые рынки)"):
        cc1, cc2, cc3 = st.columns(3)
        p_inp = cc1.number_input("Вероятность модели (%)", 1, 99, 55)
        o_inp = cc2.number_input("Коэф букмекера", 1.01, 20.0, 1.90)
        b_inp = cc3.number_input("Банк", 100.0, 1000000.0, float(bank))
        ev_c = (p_inp/100)*o_inp-1
        cc1.write(f"EV: **{ev_c*100:+.1f}%**")
        cc2.write(f"Безубыточность: **{100/o_inp:.1f}%**")
        cc3.write(f"Келли: **{kelly(p_inp/100, o_inp, b_inp, kelly_frac):.2f}**")
        if ev_c > 0.02: st.success("✅ Положительное матожидание — ставка имеет смысл")
        else: st.warning("⛔ EV слишком мал — пропускаем")

with tab2:
    st.header("📋 Портфель")
    bets = st.session_state.data["bets"]
    if not bets: st.info("Пусто")
    for b in bets:
        icon = {"pending":"⏳","won":"🟢","lost":"🔴"}[b["status"]]
        st.markdown(f"{icon} **{b['match']}** | {b.get('market','1X2')} {b['pick']} @ {b['odds']:.2f} | {b['stake']:.2f} у.е. | P={b.get('prob',0)*100:.0f}%")

with tab3:
    s = st.session_state.data["stats"]; total = s["won"]+s["lost"]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Банк", f"{st.session_state.data['bank']:.2f}")
    c2.metric("Ставок", total)
    c3.metric("WinRate", f"{(s['won']/total*100) if total else 0:.1f}%")
    c4.metric("Profit", f"{s['profit']:+.2f}")
