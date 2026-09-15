import streamlit as st
import requests, csv, io, json, os, math
from datetime import datetime, timedelta
from collections import defaultdict

st.set_page_config(page_title="NEURO BET PRO", page_icon="🛰", layout="wide")

HISTORY_FILE = "neuro_bet_pro.json"

DIV_NAMES = {
    "E0":"🏴󠁧󠁥󠁧 Англия · АПЛ","E1":"🏴󠁧󠁥󠁧 Англия · Чемпионшип","E2":"🏴󠁢󠁮󠁿 Англия · Лига 1",
    "E3":"🏴󠁢󠁮󠁿 Англия · Лига 2","EC":"🏴󠁧󠁥󠁧 Англия · Конференция",
    "SC0":"🏴󠁢󠁣 Шотландия · Премьершип","SC1":"🏴󠁧󠁢󠁣󠁿 Шотландия · Чемпионшип",
    "D1":"🇩🇪 Германия · Бундеслига","D2":"🇩🇪 Германия · 2. Бундеслига",
    "I1":"🇹 Италия · Серия A","I2":"🇮🇹 Италия · Серия B",
    "SP1":"🇪🇸 Испания · Ла Лига","SP2":"🇪 Испания · Сегунда",
    "F1":"🇫🇷 Франция · Лига 1","F2":"🇫🇷 Франция · Лига 2",
    "N1":"🇳 Нидерланды · Эредивизи","B1":"🇧🇪 Бельгия · Про-лига",
    "P1":"🇵🇹 Португалия · Примейра","T1":"🇹🇷 Турция · Суперлига","G1":"🇬🇷 Греция · Суперлига",
    "R1":"🇷🇺 Россия · РПЛ","BR1":"🇧🇷 Бразилия · Серия A","AR1":"🇦🇷 Аргентина",
    "USA1":"🇺 США · MLS","J1":"🇯🇵 Япония · J1","C1":"🏆 Лига Чемпионов","EL":"🏆 Лига Европы",
}
CORRIDORS = {"1X2": (1.40, 4.20), "OU": (1.50, 2.80), "AH": (1.60, 2.60)}

st.markdown("""
<style>
html,body{background:#070b14}
.hero{padding:18px 26px;border-radius:20px;margin-bottom:18px;
 background:linear-gradient(120deg,rgba(56,189,248,.16),rgba(16,185,129,.10) 45%,rgba(250,204,21,.08));
 border:1px solid rgba(56,189,248,.25)}
.hero h1{margin:0;font-size:2.2rem;font-weight:800;letter-spacing:.5px;
 background:linear-gradient(90deg,#38bdf8,#4ade80,#facc15);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero p{margin:4px 0 0;color:#94a3b8;font-size:.9rem}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:14px 0}
.kpi{background:rgba(15,23,42,.85);border:1px solid rgba(148,163,184,.15);border-radius:14px;padding:14px 16px}
.kpi .t{color:#64748b;font-size:.72rem;text-transform:uppercase;letter-spacing:1px}
.kpi .v{font-size:1.5rem;font-weight:800;color:#f8fafc;margin-top:2px}
.kpi .v.green{color:#4ade80}.kpi .v.gold{color:#facc15}.kpi .v.red{color:#f87171}
.mcard{background:rgba(15,23,42,.88);border:1px solid rgba(148,163,184,.14);border-radius:16px;
 padding:18px;margin-bottom:14px;transition:.2s;position:relative;overflow:hidden}
.mcard:hover{transform:translateY(-2px);border-color:rgba(56,189,248,.45)}
.mcard.value{border-color:rgba(16,185,129,.55);box-shadow:0 0 24px rgba(16,185,129,.12)}
.mhead{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.chip{background:rgba(56,189,248,.15);color:#7dd3fc;border:1px solid rgba(56,189,248,.35);
 padding:3px 10px;border-radius:999px;font-size:.72rem;font-weight:700}
.chip.when{background:rgba(250,204,21,.12);color:#fde047;border-color:rgba(250,204,21,.35)}
.badge{padding:4px 12px;border-radius:999px;font-size:.72rem;font-weight:800}
.badge.val{background:rgba(16,185,129,.18);color:#4ade80;border:1px solid rgba(16,185,129,.5)}
.badge.no{background:rgba(100,116,139,.15);color:#94a3b8;border:1px solid rgba(100,116,139,.3)}
.teams{font-size:1.35rem;font-weight:800;color:#f8fafc;margin:10px 0 4px}
.teams span{color:#64748b;font-weight:400}
.bar{height:6px;background:rgba(148,163,184,.15);border-radius:99px;overflow:hidden;margin-top:4px}
.bar i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#38bdf8,#4ade80)}
.mrow{display:grid;grid-template-columns:64px 92px 1.2fr 74px 74px 64px 78px 30px;gap:8px;align-items:center;
 padding:7px 0;border-top:1px solid rgba(148,163,184,.10);font-size:.83rem;color:#cbd5e1}
.mrow.hdr{color:#64748b;font-size:.7rem;text-transform:uppercase;letter-spacing:.6px;border-top:none}
.ok{color:#4ade80;font-weight:800}.no{color:#475569;font-weight:800}
.evpos{color:#4ade80;font-weight:700}.evneg{color:#f87171;font-weight:700}
.mfoot{margin-top:10px;padding-top:10px;border-top:1px dashed rgba(148,163,184,.2);
 color:#94a3b8;font-size:.8rem;display:flex;gap:18px;flex-wrap:wrap}
.mfoot b{color:#facc15}
</style>""", unsafe_allow_html=True)

# ================= ДВИЖОК =================
class Engine:
    def __init__(self):
        self.elo = {}
        self.st = defaultdict(lambda: {"hs":[],"hc":[],"as":[],"ac":[],"form":[],
                                       "cfh":[],"cah":[],"cfa":[],"caa":[],"yfh":[],"yah":[],"yfa":[],"yaa":[]})
        self.hg, self.ag = [], []
    def add(self, h, a, hg, ag, row=None):
        rh, ra = self.elo.get(h,1500), self.elo.get(a,1500)
        eh = 1/(1+10**((ra-(rh+60))/400))
        s = 1.0 if hg>ag else (0.5 if hg==ag else 0.0)
        self.elo[h] = rh+32*(s-eh); self.elo[a] = ra+32*((1-s)-(1-eh))
        t = self.st
        t[h]["hs"].append(hg); t[h]["hc"].append(ag); t[a]["as"].append(ag); t[a]["ac"].append(hg)
        t[h]["form"].append(3 if hg>ag else (1 if hg==ag else 0))
        t[a]["form"].append(3 if ag>hg else (1 if hg==ag else 0))
        self.hg.append(hg); self.ag.append(ag)
        if row:
            for col, key in (("HC","cfh"),("AC","cfa"),("HY","yfh"),("AY","yfa")):
                v = _f(row.get(col))
                if v is None: continue
                if key=="cfh": t[h]["cfh"].append(v); t[a]["caa"].append(v)
                elif key=="cfa": t[a]["cfa"].append(v); t[h]["cah"].append(v)
                elif key=="yfh": t[h]["yfh"].append(v); t[a]["yaa"].append(v)
                else: t[a]["yfa"].append(v); t[h]["yah"].append(v)
        for team in (h,a):
            for k in t[team]: t[team][k] = t[team][k][-12:]
    def _m(self, l, d=1.0): return sum(l)/len(l) if l else d
    def _form(self, t):
        f = self.st[t]["form"][-5:]
        return (sum(f)/(len(f)*3)) if f else 0.5
    def predict(self, h, a):
        lh, la = self._m(self.hg,1.5), self._m(self.ag,1.2)
        sh, sa = self.st[h], self.st[a]
        ah_, dh_ = self._m(sh["hs"],lh)/lh, self._m(sh["hc"],la)/la
        aa_, da_ = self._m(sa["as"],la)/la, self._m(sa["ac"],lh)/lh
        fh, fa = self._form(h), self._form(a)
        lam_h = max(0.3, min(4.0, lh*ah_*da_*1.10*(0.85+0.30*fh)))
        lam_a = max(0.25, min(3.5, la*aa_*dh_*0.95*(0.85+0.30*fa)))
        M = [[self._p(lam_h,i)*self._p(lam_a,j) for j in range(7)] for i in range(7)]
        for i in range(7):
            for j in range(7):
                if i==0 and j==0: M[i][j]*=1.08
                elif (i,j) in [(1,0),(0,1),(1,1)]: M[i][j]*=0.96
        tot = sum(map(sum,M)) or 1.0
        M = [[v/tot for v in r] for r in M]
        p1 = sum(M[i][j] for i in range(7) for j in range(7) if i>j)
        px = sum(M[i][i] for i in range(7))
        p2 = max(0.0, 1-p1-px)
        e = 1/(1+10**((self.elo.get(a,1500)-self.elo.get(h,1500)-60)/400))
        pde = 0.20+0.12*(1-abs(e-0.5)*2)
        f1, fd = 0.72*p1+0.28*e*(1-pde), 0.72*px+0.28*pde
        f2 = max(0.0, 1-f1-fd)
        lam_t = lam_h+lam_a
        over = 1-sum(self._p(lam_t,k) for k in range(3))
        games = min(len(sh["hs"])+len(sh["as"]), len(sa["hs"])+len(sa["as"]))
        corners = ((self._m(sh["cfh"],5)+self._m(sa["caa"],5))/2, (self._m(sa["cfa"],5)+self._m(sh["cah"],5))/2)
        yellows = ((self._m(sh["yfh"],2)+self._m(sa["yah"],2))/2, (self._m(sa["yfa"],2)+self._m(sh["yah"],2))/2)
        return {"p1":f1,"x":fd,"p2":f2,"over":over,"M":M,"lams":(lam_h,lam_a),
                "games":games,"corners":corners,"yellows":yellows}
    def _p(self,l,k): return math.exp(-l)*l**k/math.factorial(k)

def _f(v):
    try: return float(v)
    except Exception: return None

# ================= ДАННЫЕ =================
@st.cache_data(ttl=1800)
def find_season():
    for s in ["2627","2526","2425"]:
        try:
            r = requests.head(f"https://www.football-data.co.uk/mmz4281/{s}/E0.csv", timeout=8)
            if r.status_code==200: return s
        except Exception: continue
    return "2526"

@st.cache_data(ttl=1800)
def load_seasonal(div, season):
    try:
        r = requests.get(f"https://www.football-data.co.uk/mmz4281/{season}/{div}.csv",
                         timeout=20, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code!=200: return []
        return list(csv.DictReader(io.StringIO(r.text)))
    except Exception: return []

@st.cache_data(ttl=900)
def load_fixtures():
    urls = ["https://www.football-data.co.uk/mmz4281/fixtures.csv",
            "https://www.football-data.co.uk/mmz4281/fixtures_new.csv",
            "https://www.football-data.co.uk/fixtures.csv"]
    rows, used, seen = [], [], set()
    for u in urls:
        try:
            r = requests.get(u, timeout=25, headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code!=200: continue
            rd = list(csv.DictReader(io.StringIO(r.text)))
            if not rd or "HomeTeam" not in rd[0]: continue
            n=0
            for x in rd:
                k = (x.get("Div"),x.get("Date"),x.get("HomeTeam"),x.get("AwayTeam"))
                if k in seen: continue
                seen.add(k); rows.append(x); n+=1
            if n: used.append(u.split("/")[-1])
        except Exception: continue
    return rows, used

def parse_date(s):
    for fmt in ("%d/%m/%Y","%d/%m/%y"):
        try: return datetime.strptime(s.strip(), fmt)
        except Exception: continue
    return None

def odd1(row, keys):
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
    return {"bank":10000.0,"bets":[],"cards":[],"funnel":None,"stats":{"won":0,"lost":0,"profit":0}}
def save_data(d): json.dump(d, open(HISTORY_FILE,"w",encoding="utf-8"), indent=2, ensure_ascii=False)

if "data" not in st.session_state: st.session_state.data = load_data()
D = st.session_state.data

# ================= ШАПКА =================
st.markdown(f"""
<div class="hero">
  <h1>🛰 NEURO BET PRO</h1>
  <p>Пуассон + Elo + форма · рынки 1X2 / Тотал 2.5 / Азиатская фора · угловые и жёлтые · критерий Келли</p>
  <div class="kpis">
    <div class="kpi"><div class="t">Банкролл</div><div class="v gold">{D['bank']:.0f} у.е.</div></div>
    <div class="kpi"><div class="t">Ставок в работе</div><div class="v">{sum(1 for b in D['bets'] if b['status']=='pending')}</div></div>
    <div class="kpi"><div class="t">Прибыль</div><div class="v {'green' if D['stats']['profit']>=0 else 'red'}">{D['stats']['profit']:+.0f}</div></div>
    <div class="kpi"><div class="t">Валуев в ленте</div><div class="v green">{sum(1 for c in D.get('cards',[]) if c['best'])}</div></div>
  </div>
</div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Фильтры качества")
    kelly_frac = st.slider("Келли (дробь)", 0.10, 0.40, 0.25, 0.05)
    min_edge = st.slider("Edge над безубыточностью, п.п.", 0, 8, 2)/100
    min_ev = st.slider("Мин. EV, %", 0, 10, 2)/100
    st.caption("Коридоры кэфов: 1X2 1.40–4.20 · Тотал 1.50–2.80 · Фора 1.60–2.60")
    only_val = st.checkbox("Показывать только валуи", False)
    if st.button("🔄 Сброс системы"):
        st.session_state.data = {"bank":10000.0,"bets":[],"cards":[],"funnel":None,"stats":{"won":0,"lost":0,"profit":0}}
        save_data(st.session_state.data); st.cache_data.clear(); st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(["🛰 Сканер", "💼 Портфель", "📈 Статистика", "🧮 EV-калькулятор"])

with tab1:
    c1, c2 = st.columns([3,1])
    with c1:
        days = st.slider("Горизонт сканирования, дней", 1, 21, 10)
    with c2:
        st.write("")
        scan = st.button("⚡ СКАН", type="primary")

    if scan:
        season = find_season()
        today = datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
        limit = today+timedelta(days=days)
        fixtures, used = load_fixtures()
        if not fixtures:
            st.error("Расписание недоступно. Повтори через минуту.")
            st.stop()
        divs_avail = sorted({r.get("Div") for r in fixtures if r.get("Div")})
        D["_divs"] = divs_avail
        save_data(D)
        engine = Engine(); trained = 0
        prog = st.progress(0.0, text="Обучение модели на сыгранных матчах...")
        for i, dv in enumerate(divs_avail):
            for r in load_seasonal(dv, season):
                if r.get("FTHG") not in (None,"") and r.get("FTAG") not in (None,""):
                    try:
                        engine.add(r["HomeTeam"], r["AwayTeam"], float(r["FTHG"]), float(r["FTAG"]), r)
                        trained += 1
                    except Exception: continue
            prog.progress((i+1)/len(divs_avail))
        prog.empty()

        cards, added, passed = [], 0, 0
        existing = {b["match"]+"|"+b["pick"] for b in D["bets"]}
        for r in fixtures:
            d = parse_date(r.get("Date",""))
            if not d or not (today <= d <= limit): continue
            h, a = (r.get("HomeTeam") or "").strip(), (r.get("AwayTeam") or "").strip()
            if not h or not a: continue
            P = engine.predict(h, a)
            if P["games"] < 3: continue
            cands = []
            oh, od, oa = odd1(r,["B365H","PSH","MaxH"]), odd1(r,["B365D","PSD","MaxD"]), odd1(r,["B365A","PSA","MaxA"])
            if oh: cands.append(("1X2","П1",P["p1"],oh))
            if od: cands.append(("1X2","X",P["x"],od))
            if oa: cands.append(("1X2","П2",P["p2"],oa))
            ov, un = odd1(r,["B365>2.5","P>2.5","Max>2.5"]), odd1(r,["B365<2.5","P<2.5","Max<2.5"])
            if ov: cands.append(("OU","ТБ 2.5",P["over"],ov))
            if un: cands.append(("OU","ТМ 2.5",1-P["over"],un))
            ahh = _f(r.get("AHh")); ohh, oha = odd1(r,["B365AHH","PAHH","MaxAHH"]), odd1(r,["B365AHA","PAHA","MaxAHA"])
            if ahh is not None and abs((ahh*2)%2)==1 and ohh and oha:
                pc = sum(P["M"][i][j] for i in range(7) for j in range(7) if (i-j+ahh) > 0.001)
                cands.append(("AH", f"Ф1({ahh:+.1f})", pc, ohh))
                cands.append(("AH", f"Ф2({-ahh:+.1f})", 1-pc, oha))
            if not cands: continue
            rows, best = [], None
            for mkt, pick, prob, odd in cands:
                lo, hi = CORRIDORS[mkt]
                ev = prob*odd-1; be = 1/odd; edge = prob-be
                req = min_ev + max(0.0, odd-2.5)*0.02
                ok = (lo<=odd<=hi) and (edge>=min_edge) and (ev>=req)
                if ok:
                    passed += 1
                    stk = kelly(prob, odd, D["bank"], kelly_frac)
                    if best is None or ev > best[3]: best = (mkt, pick, odd, ev, prob, stk)
                rows.append({"mkt":mkt,"pick":pick,"prob":prob,"odd":odd,"ev":ev,"be":be,"edge":edge,"ok":ok})
            nd = (d-today).days
            when = "сегодня" if nd==0 else ("завтра" if nd==1 else f"через {nd} дн")
            cards.append({"div":r.get("Div"),"league":DIV_NAMES.get(r.get("Div"), "Лига "+str(r.get("Div"))),
                          "match":f"{h} vs {a}","date":d.strftime("%d.%m")+(f" {r['Time']}" if r.get("Time") else ""),
                          "when":when,"rows":rows,"best":best,"lams":P["lams"],
                          "corners":P["corners"],"yellows":P["yellows"],"games":P["games"]})
            if best and best[5]>0:
                key = f"{h} vs {a}|{best[1]}"
                if key not in existing:
                    D["bets"].append({"match":f"{h} vs {a}","div":r.get("Div"),
                        "league":DIV_NAMES.get(r.get("Div"),"Лига"),"market":best[0],
                        "pick":best[1],"odds":best[2],"stake":best[5],"prob":best[4],"status":"pending"})
                    existing.add(key); added += 1
        cards.sort(key=lambda c: (c["best"] is not None, c["best"][3] if c["best"] else -1), reverse=True)
        D["cards"], D["funnel"] = cards, {"trained":trained,"fix":len(fixtures),"cards":len(cards),"passed":passed,"src":used}
        save_data(D)
        st.success(f"Обучено {trained} матчей · в окне {len(cards)} событий · валуев {passed} · в портфель +{added}")
        st.rerun()

    fn = D.get("funnel")
    if fn:
        st.caption(f"Источник: {', '.join(fn['src'])} · обучено: {fn['trained']} · расписание: {fn['fix']} · в окне: {fn['cards']} · валуев: {fn['passed']}")

    divs_avail = D.get("_divs", [])
    if divs_avail:
        sel_divs = st.multiselect("Лиги (авто-список из расписания)", divs_avail,
                                  format_func=lambda x: DIV_NAMES.get(x, f"Лига {x}"), default=divs_avail)
    else:
        sel_divs = None
        st.info("Нажми ⚡ СКАН — список лиг построится автоматически из файла расписания.")

    cards = D.get("cards", [])
    shown = [c for c in cards if (c["best"] or not only_val) and (sel_divs is None or c["div"] in sel_divs)]
    if not shown:
        st.info("Лента пуста. Запусти скан — карточки матчей появятся здесь сразу для всех лиг из расписания.")
    for c in shown:
        val = c["best"] is not None
        rows_html = "<div class='mrow hdr'><span>Рынок</span><span>Выбор</span><span>Вероятность модели</span><span>P модели</span><span>Безубыт.</span><span>Кэф</span><span>EV</span><span></span></div>"
        for rw in c["rows"]:
            w = min(100, rw["prob"]*100)
            evc = "evpos" if rw["ev"]>0 else "evneg"
            mark = "<span class='ok'>✅</span>" if rw["ok"] else "<span class='no'>⛔</span>"
            rows_html += (f"<div class='mrow'><span style='color:#64748b'>{rw['mkt']}</span>"
                          f"<b style='color:#facc15'>{rw['pick']}</b>"
                          f"<div><div class='bar'><i style='width:{w:.0f}%'></i></div></div>"
                          f"<span style='color:#4ade80;font-weight:700'>{rw['prob']*100:.1f}%</span>"
                          f"<span style='color:#f87171'>{rw['be']*100:.1f}%</span>"
                          f"<span style='color:#f8fafc;font-weight:700'>{rw['odd']:.2f}</span>"
                          f"<span class='{evc}'>{rw['ev']*100:+.1f}%</span>{mark}</div>")
        ch, ca = c["corners"]; yh, ya = c["yellows"]
        best_html = ""
        if val:
            b = c["best"]
            best_html = f"<span>💰 Келли: <b>{b[5]:.2f} у.е.</b> на <b>{b[1]}</b> @ <b>{b[2]:.2f}</b></span>"
        badge = "<span class='badge val'>🟢 ВАЛУЙ</span>" if val else "<span class='badge no'>наблюдение</span>"
        st.markdown(f"""
<div class="mcard {'value' if val else ''}">
  <div class="mhead"><span class="chip">{c['league']}</span><span class="chip when">📅 {c['date']} · {c['when']}</span>{badge}</div>
  <div class="teams">{c['match'].split(' vs ')[0]} <span>—</span> {c['match'].split(' vs ')[1]}</div>
  {rows_html}
  <div class="mfoot">
    <span>xG: <b>{c['lams'][0]:.2f}–{c['lams'][1]:.2f}</b></span>
    <span>🚩 Угловые: <b>{ch:.1f}–{ca:.1f}</b> (Σ {ch+ca:.1f})</span>
    <span>🟨 Жёлтые: <b>{yh:.1f}–{ya:.1f}</b> (Σ {yh+ya:.1f})</span>
    <span>📚 игр в базе: <b>{c['games']}</b></span>
    {best_html}
  </div>
</div>""", unsafe_allow_html=True)

with tab2:
    st.header("💼 Портфель ставок")
    if st.button("🔄 Автосинхронизация результатов"):
        season = find_season(); upd = 0
        for bet in [b for b in D["bets"] if b["status"]=="pending"]:
            for r in load_seasonal(bet.get("div","E0"), season):
                if r.get("HomeTeam")==bet["match"].split(" vs ")[0] and r.get("AwayTeam")==bet["match"].split(" vs ")[1] and r.get("FTHG") not in (None,""):
                    hg, ag = float(r["FTHG"]), float(r["FTAG"])
                    res = "П1" if hg>ag else ("X" if hg==ag else "П2")
                    if bet["market"]=="1X2" and res==bet["pick"] or bet["market"]!="1X2":
                        pass
                    won = (bet["market"]=="1X2" and res==bet["pick"])
                    if bet["market"]=="OU":
                        won = (bet["pick"]=="ТБ 2.5" and hg+ag>=3) or (bet["pick"]=="ТМ 2.5" and hg+ag<=2)
                    if won:
                        bet["status"]="won"; pr = bet["stake"]*(bet["odds"]-1)
                        D["bank"] += bet["stake"]+pr; D["stats"]["won"]+=1; D["stats"]["profit"]+=pr
                    else:
                        bet["status"]="lost"; D["stats"]["lost"]+=1; D["stats"]["profit"]-=bet["stake"]
                    upd+=1; break
        save_data(D); st.success(f"Закрыто ставок: {upd}"); st.rerun()
    bets = D["bets"]
    if not bets: st.info("Портфель пуст — валуи из сканера падают сюда автоматически.")
    for b in bets:
        icon = {"pending":"⏳","won":"🟢","lost":"🔴"}[b["status"]]
        st.markdown(f"{icon} **{b['match']}** · {b.get('market','1X2')} **{b['pick']}** @ **{b['odds']:.2f}** · {b['stake']:.2f} у.е. · P={b.get('prob',0)*100:.0f}% · {b['status']}")

with tab3:
    st.header("📈 Статистика")
    s = D["stats"]; tot = s["won"]+s["lost"]
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Банк", f"{D['bank']:.2f}")
    m2.metric("Ставок", tot)
    m3.metric("WinRate", f"{(s['won']/tot*100) if tot else 0:.1f}%")
    m4.metric("Profit", f"{s['profit']:+.2f}")
    by = defaultdict(lambda: [0,0])
    for b in D["bets"]:
        if b["status"] in ("won","lost"): by[b.get("market","1X2")][0 if b["status"]=="won" else 1] += 1
    if by:
        st.subheader("По рынкам")
        for k,(w,l) in by.items():
            st.write(f"**{k}**: ✅ {w} / ❌ {l} · WR {w/(w+l)*100:.0f}%")

with tab4:
    st.header("🧮 EV-калькулятор (угловые, жёлтые, любой рынок)")
    q1,q2,q3 = st.columns(3)
    p = q1.number_input("Вероятность модели, %", 1, 99, 55)
    o = q2.number_input("Коэф букмекера", 1.01, 30.0, 1.90)
    bk = q3.number_input("Банк", 100.0, 1e6, float(D["bank"]))
    ev = (p/100)*o-1
    st.markdown(f"**EV:** {ev*100:+.1f}% · **Безубыточность:** {100/o:.1f}% · **Ставка Келли:** {kelly(p/100, o, bk, kelly_frac):.2f} у.е.")
    if ev > 0.02: st.success("✅ Матожидание положительное")
    else: st.warning("⛔ EV мал — пропускаем")
    st.caption("Как пользоваться: возьми ожидание угловых/жёлтых с карточки матча, оцени вероятность линии букмекера (например через Пуассона от ожидания), вбей сюда вместе с кэфом.")
