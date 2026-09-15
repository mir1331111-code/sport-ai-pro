import streamlit as st
import requests, csv, io, json, os, math
from datetime import datetime, timedelta
from collections import defaultdict

st.set_page_config(page_title="NEURO BET PRO", page_icon="🏟", layout="wide")
HISTORY_FILE = "neuro_bet_pro.json"

DIV_NAMES = {"E0":"🏴󠁢󠁥󠁮󠁧 АПЛ","E1":"🏴󠁢󠁥󠁮󠁧󠁿 Чемпионшип","SC0":"🏴󠁧󠁳󠁣 Шотландия",
 "D1":"🇩🇪 Бундеслига","D2":"🇩🇪 2. Бундеслига","I1":"🇮🇹 Серия A","I2":"🇮🇹 Серия B",
 "SP1":"🇪 Ла Лига","SP2":"🇪🇸 Сегунда","F1":"🇫🇷 Лига 1","F2":"🇫🇷 Лига 2",
 "N1":"🇳 Эредивизи","B1":"🇧🇪 Про-лига","P1":"🇵🇹 Примейра","T1":"🇹🇷 Суперлига",
 "G1":"🇬🇷 Греция","R1":"🇷🇺 РПЛ","BR1":"🇧 Бразилия","C1":"🏆 Лига Чемпионов","EL":"🏆 Лига Европы"}
TSDB_LEAGUES = {"432":"🏴󠁢󠁮󠁿 АПЛ","434":"🇪🇸 Ла Лига","435":"🇮🇹 Серия A","436":"🇩🇪 Бундеслига",
 "437":"🇫🇷 Лига 1","448":"🏆 Лига Чемпионов","442":"🇺 MLS","439":"🇵🇹 Примейра"}
CORRIDORS = {"1X2":(1.40,4.20),"OU":(1.50,2.80),"AH":(1.60,2.60)}

st.markdown("""
<style>
.stApp{background:linear-gradient(rgba(4,10,20,.86),rgba(4,10,20,.94)),
 url('https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=1920&auto=format&fit=crop') center/cover fixed;}
header,#MainMenu,footer{visibility:hidden}
.hero{padding:20px 26px;border-radius:22px;margin-bottom:16px;border:1px solid rgba(56,189,248,.3);
 background:linear-gradient(120deg,rgba(2,6,23,.9),rgba(6,78,59,.55) 55%,rgba(120,53,15,.45)),
 url('https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=1600&auto=format&fit=crop') center/cover;}
.hero h1{margin:0;font-size:2.3rem;font-weight:900;letter-spacing:1px;color:#f8fafc;
 text-shadow:0 0 24px rgba(56,189,248,.6)}
.hero p{margin:4px 0 0;color:#cbd5e1;font-size:.9rem}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:14px}
.kpi{background:rgba(2,6,23,.72);border:1px solid rgba(148,163,184,.2);border-radius:14px;padding:12px 16px;backdrop-filter:blur(6px)}
.kpi .t{color:#7dd3fc;font-size:.68rem;text-transform:uppercase;letter-spacing:1.2px}
.kpi .v{font-size:1.45rem;font-weight:800;color:#f8fafc}
.kpi .v.g{color:#4ade80}.kpi .v.y{color:#facc15}.kpi .v.r{color:#f87171}
.mcard{background:rgba(2,6,23,.82);border:1px solid rgba(148,163,184,.16);border-radius:16px;
 padding:16px 18px;margin-bottom:14px;backdrop-filter:blur(8px);transition:.2s}
.mcard:hover{border-color:rgba(56,189,248,.5);transform:translateY(-2px)}
.mcard.value{border-color:rgba(16,185,129,.6);box-shadow:0 0 26px rgba(16,185,129,.15)}
.mcard.hot{border-color:rgba(250,204,21,.55);box-shadow:0 0 26px rgba(250,204,21,.12)}
.mhead{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.chip{background:rgba(56,189,248,.14);color:#7dd3fc;border:1px solid rgba(56,189,248,.35);
 padding:3px 10px;border-radius:999px;font-size:.72rem;font-weight:700}
.chip.when{background:rgba(250,204,21,.12);color:#fde047;border-color:rgba(250,204,21,.35)}
.badge{margin-left:auto;padding:4px 12px;border-radius:999px;font-size:.72rem;font-weight:800}
.badge.val{background:rgba(16,185,129,.18);color:#4ade80;border:1px solid rgba(16,185,129,.5)}
.badge.hot{background:rgba(250,204,21,.15);color:#fde047;border:1px solid rgba(250,204,21,.5)}
.badge.no{background:rgba(100,116,139,.15);color:#94a3b8;border:1px solid rgba(100,116,139,.3)}
.teams{font-size:1.3rem;font-weight:800;color:#f8fafc;margin:10px 0 2px}
.teams span{color:#64748b;font-weight:400}
.form5{font-size:.72rem;letter-spacing:2px;margin-bottom:6px}
.form5 b{padding:1px 5px;border-radius:4px;margin-right:2px}
.w{background:rgba(16,185,129,.25);color:#4ade80}.d{background:rgba(148,163,184,.2);color:#cbd5e1}.l{background:rgba(239,68,68,.2);color:#f87171}
.bar{height:6px;background:rgba(148,163,184,.15);border-radius:99px;overflow:hidden;margin-top:4px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#38bdf8,#4ade80)}
.mrow{display:grid;grid-template-columns:70px 96px 1.1fr 70px 70px 62px 74px 26px;gap:8px;align-items:center;
 padding:6px 0;border-top:1px solid rgba(148,163,184,.1);font-size:.82rem;color:#cbd5e1}
.mrow.hdr{color:#64748b;font-size:.68rem;text-transform:uppercase;letter-spacing:.6px;border-top:none}
.ok{color:#4ade80;font-weight:800}.nok{color:#475569;font-weight:800}
.evpos{color:#4ade80;font-weight:700}.evneg{color:#f87171;font-weight:700}
.mfoot{margin-top:10px;padding-top:10px;border-top:1px dashed rgba(148,163,184,.25);
 color:#94a3b8;font-size:.78rem;display:flex;gap:16px;flex-wrap:wrap}
.mfoot b{color:#facc15}
</style>""", unsafe_allow_html=True)

class Engine:
    def __init__(self):
        self.elo={}; self.st=defaultdict(lambda:{"hs":[],"hc":[],"as":[],"ac":[],"form":[],
            "cfh":[],"cah":[],"cfa":[],"caa":[],"yfh":[],"yah":[],"yfa":[],"yaa":[]})
        self.hg=[]; self.ag=[]
    def add(self,h,a,hg,ag,row=None):
        rh,ra=self.elo.get(h,1500),self.elo.get(a,1500)
        eh=1/(1+10**((ra-(rh+60))/400)); s=1.0 if hg>ag else (0.5 if hg==ag else 0.0)
        self.elo[h]=rh+32*(s-eh); self.elo[a]=ra+32*((1-s)-(1-eh))
        t=self.st
        t[h]["hs"].append(hg); t[h]["hc"].append(ag); t[a]["as"].append(ag); t[a]["ac"].append(hg)
        t[h]["form"].append(3 if hg>ag else (1 if hg==ag else 0))
        t[a]["form"].append(3 if ag>hg else (1 if hg==ag else 0))
        self.hg.append(hg); self.ag.append(ag)
        if row:
            pairs=(("HC",h,"cfh",a,"caa"),("AC",a,"cfa",h,"cah"),("HY",h,"yfh",a,"yaa"),("AY",a,"yfa",h,"yah"))
            for col,t1,k1,t2,k2 in pairs:
                v=_f(row.get(col))
                if v is not None: t[t1][k1].append(v); t[t2][k2].append(v)
        for team in (h,a):
            for k in t[team]: t[team][k]=t[team][k][-12:]
    def _m(self,l,d=1.0): return sum(l)/len(l) if l else d
    def form_str(self,t):
        return "".join({"3":"В","1":"Н","0":"П"}[str(int(x))] for x in self.st[t]["form"][-5:]) or "—"
    def predict(self,h,a):
        lh,la=self._m(self.hg,1.5),self._m(self.ag,1.2)
        sh,sa=self.st[h],self.st[a]
        ah_,dh_=self._m(sh["hs"],lh)/lh,self._m(sh["hc"],la)/la
        aa_,da_=self._m(sa["as"],la)/la,self._m(sa["ac"],lh)/lh
        fh,fa=self._form(h),self._form(a)
        lam_h=max(0.3,min(4.0,lh*ah_*da_*1.10*(0.85+0.30*fh)))
        lam_a=max(0.25,min(3.5,la*aa_*dh_*0.95*(0.85+0.30*fa)))
        M=[[self._p(lam_h,i)*self._p(lam_a,j) for j in range(7)] for i in range(7)]
        for i in range(7):
            for j in range(7):
                if i==0 and j==0: M[i][j]*=1.08
                elif (i,j) in [(1,0),(0,1),(1,1)]: M[i][j]*=0.96
        tot=sum(map(sum,M)) or 1.0
        M=[[v/tot for v in r] for r in M]
        p1=sum(M[i][j] for i in range(7) for j in range(7) if i>j)
        px=sum(M[i][i] for i in range(7)); p2=max(0.0,1-p1-px)
        e=1/(1+10**((self.elo.get(a,1500)-self.elo.get(h,1500)-60)/400))
        pde=0.20+0.12*(1-abs(e-0.5)*2)
        f1,fd=0.72*p1+0.28*e*(1-pde),0.72*px+0.28*pde; f2=max(0.0,1-f1-fd)
        over=1-sum(self._p(lam_h+lam_a,k) for k in range(3))
        btts=sum(M[i][j] for i in range(1,7) for j in range(1,7))
        games=min(len(sh["hs"])+len(sh["as"]),len(sa["hs"])+len(sa["as"]))
        corners=((self._m(sh["cfh"],5)+self._m(sa["caa"],5))/2,(self._m(sa["cfa"],5)+self._m(sh["cah"],5))/2)
        yellows=((self._m(sh["yfh"],2)+self._m(sa["yah"],2))/2,(self._m(sa["yfa"],2)+self._m(sh["yah"],2))/2)
        return {"p1":f1,"x":fd,"p2":f2,"over":over,"btts":btts,"M":M,"lams":(lam_h,lam_a),
                "games":games,"corners":corners,"yellows":yellows}
    def _form(self,t):
        f=self.st[t]["form"][-5:]
        return (sum(f)/(len(f)*3)) if f else 0.5
    def _p(self,l,k): return math.exp(-l)*l**k/math.factorial(k)

def _f(v):
    try: return float(v)
    except Exception: return None

@st.cache_data(ttl=1800)
def find_season():
    for s in ["2627","2526","2425"]:
        try:
            r=requests.head(f"https://www.football-data.co.uk/mmz4281/{s}/E0.csv",timeout=8)
            if r.status_code==200: return s
        except Exception: continue
    return "2526"

@st.cache_data(ttl=1800)
def load_seasonal(div,season):
    try:
        r=requests.get(f"https://www.football-data.co.uk/mmz4281/{season}/{div}.csv",
                       timeout=20,headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code!=200: return []
        return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    except Exception: return []

@st.cache_data(ttl=900)
def load_fixtures():
    rep=[]; rows=[]; seen=set()
    for u in ["https://www.football-data.co.uk/mmz4281/fixtures.csv",
              "https://www.football-data.co.uk/fixtures.csv",
              "http://www.football-data.co.uk/mmz4281/fixtures.csv"]:
        try:
            r=requests.get(u,timeout=25,headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code!=200: rep.append(f"{u.split('/')[-1]}: HTTP {r.status_code}"); continue
            rd=list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
            n=0
            for x in rd:
                k=(x.get("Div"),x.get("Date"),x.get("HomeTeam"),x.get("AwayTeam"))
                if k in seen or not x.get("HomeTeam"): continue
                seen.add(k); x["_src"]="fixtures"; rows.append(x); n+=1
            rep.append(f"{u.split('/')[-1]}: OK, {n} строк")
            if n: break
        except Exception as ex: rep.append(f"{u.split('/')[-1]}: ошибка {type(ex).__name__}")
    return rows, rep

@st.cache_data(ttl=900)
def load_tsdb():
    rep=[]; rows=[]
    for lid,name in TSDB_LEAGUES.items():
        try:
            r=requests.get(f"https://www.thesportsdb.com/api/v1/json/3/eventsnextleague.php?id={lid}",timeout=15)
            ev=(r.json() or {}).get("events") or []
            for e in ev:
                rows.append({"Div":"TSDB","League":name,"Date":e.get("dateEvent",""),
                             "Time":(e.get("strTime") or "")[:5],"HomeTeam":e.get("strHomeTeam",""),
                             "AwayTeam":e.get("strAwayTeam",""),"_src":"tsdb"})
            rep.append(f"TSDB {name}: {len(ev)}")
        except Exception as ex: rep.append(f"TSDB {name}: ошибка")
    return rows, rep

def parse_date(s):
    for fmt in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d"):
        try: return datetime.strptime(s.strip(),fmt)
        except Exception: continue
    return None

def odd1(row,keys):
    for k in keys:
        v=_f(row.get(k))
        if v and v>1.01: return v
    return None

def kelly(prob,odds,bank,frac):
    if prob<=0 or odds<=1: return 0.0
    b=odds-1; k=(b*prob-(1-prob))/b
    return round(min(max(0,k*frac),0.05)*bank,2)

def load_data():
    if os.path.exists(HISTORY_FILE):
        try: return json.load(open(HISTORY_FILE,encoding="utf-8"))
        except Exception: pass
    return {"bank":10000.0,"bets":[],"cards":[],"funnel":None,"report":[],"stats":{"won":0,"lost":0,"profit":0}}
def save_data(d): json.dump(d,open(HISTORY_FILE,"w",encoding="utf-8"),indent=2,ensure_ascii=False)

if "data" not in st.session_state: st.session_state.data=load_data()
D=st.session_state.data

st.markdown(f"""
<div class="hero">
 <h1>🏟 NEURO BET PRO</h1>
 <p>Пуассон + Elo + форма · 1X2 / Тотал / BTTS / Двойной шанс / Форы / Угловые / Жёлтые · Келли · 3 источника данных</p>
 <div class="kpis">
  <div class="kpi"><div class="t">Банкролл</div><div class="v y">{D['bank']:.0f} у.е.</div></div>
  <div class="kpi"><div class="t">В работе</div><div class="v">{sum(1 for b in D['bets'] if b['status']=='pending')}</div></div>
  <div class="kpi"><div class="t">Прибыль</div><div class="v {'g' if D['stats']['profit']>=0 else 'r'}">{D['stats']['profit']:+.0f}</div></div>
  <div class="kpi"><div class="t">Сигналов в ленте</div><div class="v g">{sum(1 for c in D.get('cards',[]) if c['tag'])}</div></div>
 </div>
</div>""",unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Настройки")
    kelly_frac=st.slider("Келли (дробь)",0.10,0.40,0.25,0.05)
    mode=st.radio("Режим ленты",["🎯 Высокая проходимость","💰 Валуи (EV)"])
    thr=st.slider("Порог проходимости, %",50,80,60)/100
    min_edge=st.slider("Edge для валуев, п.п.",0,8,2)/100
    min_ev=st.slider("Мин. EV для валуев, %",0,10,2)/100
    if st.button("🔄 Сброс"):
        st.session_state.data={"bank":10000.0,"bets":[],"cards":[],"funnel":None,"report":[],"stats":{"won":0,"lost":0,"profit":0}}
        save_data(st.session_state.data); st.cache_data.clear(); st.rerun()

tab1,tab2,tab3,tab4=st.tabs(["🏟 Сканер","💼 Портфель","📈 Статистика","🧮 Калькулятор"])

with tab1:
    c1,c2=st.columns([4,1]); days=c1.slider("Горизонт, дней",1,21,10); scan=c2.button("⚡ СКАН",type="primary")
    if scan:
        season=find_season()
        today=datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
        limit=today+timedelta(days=days)
        fix,rep1=load_fixtures(); tsd,rep2=load_tsdb()
        allrows=fix+tsd
        engine=Engine(); trained=0
        train_divs=sorted({r.get("Div") for r in fix if r.get("Div")}) or ["E0","SP1","I1","D1","F1"]
        prog=st.progress(0.0,text="Обучение на сыгранных матчах...")
        for i,dv in enumerate(train_divs):
            for r in load_seasonal(dv,season):
                if r.get("FTHG") not in (None,"") and r.get("FTAG") not in (None,""):
                    try: engine.add(r["HomeTeam"],r["AwayTeam"],float(r["FTHG"]),float(r["FTAG"]),r); trained+=1
                    except Exception: continue
            prog.progress((i+1)/len(train_divs))
        prog.empty()
        cards=[]; passed=0; inwin=0; withodds=0
        existing={b["match"]+"|"+b["pick"] for b in D["bets"]}; added=0
        for r in allrows:
            try:
                d=parse_date(r.get("Date",""))
                if not d or not (today<=d<=limit): continue
                h,a=(r.get("HomeTeam") or "").strip(),(r.get("AwayTeam") or "").strip()
                if not h or not a: continue
                inwin+=1
                P=engine.predict(h,a)
                league=r.get("League") or DIV_NAMES.get(r.get("Div"),"Лига "+str(r.get("Div")))
                oh,od,oa=odd1(r,["B365H","PSH","MaxH"]),odd1(r,["B365D","PSD","MaxD"]),odd1(r,["B365A","PSA","MaxA"])
                ov,un=odd1(r,["B365>2.5","P>2.5","Max>2.5"]),odd1(r,["B365<2.5","P<2.5","Max<2.5"])
                if oh or ov: withodds+=1
                rows=[]; best=None; hot=[]
                cands=[("1X2","П1",P["p1"],oh),("1X2","X",P["x"],od),("1X2","П2",P["p2"],oa),
                       ("OU","ТБ 2.5",P["over"],ov),("OU","ТМ 2.5",1-P["over"],un),
                       ("STAT","BTTS да",P["btts"],None),("STAT","BTTS нет",1-P["btts"],None),
                       ("STAT","1X",P["p1"]+P["x"],None),("STAT","X2",P["x"]+P["p2"],None),("STAT","12",P["p1"]+P["p2"],None)]
                ahh=_f(r.get("AHh")); ohh,oha=odd1(r,["B365AHH","PAHH"]),odd1(r,["B365AHA","PAHA"])
                if ahh is not None and abs((ahh*2)%2)==1 and ohh and oha:
                    pc=sum(P["M"][i][j] for i in range(7) for j in range(7) if (i-j+ahh)>0.001)
                    cands+= [("AH",f"Ф1({ahh:+.1f})",pc,ohh),("AH",f"Ф2({-ahh:+.1f})",1-pc,oha)]
                for mkt,pick,prob,odd in cands:
                    item={"mkt":mkt,"pick":pick,"prob":prob,"odd":odd,"ev":None,"be":None,"edge":None,"ok":False}
                    if odd:
                        lo,hi=CORRIDORS.get(mkt,(1.4,4.2))
                        ev=prob*odd-1; be=1/odd; edge=prob-be
                        req=min_ev+max(0.0,odd-2.5)*0.02
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
                    "corners":P["corners"],"yellows":P["yellows"],"games":P["games"],
                    "fh":engine.form_str(h),"fa":engine.form_str(a)})
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
        D["funnel"]={"trained":trained,"fix":len(fix),"tsdb":len(tsd),"inwin":inwin,"odds":withodds,"passed":passed,"added":added}
        save_data(D); st.rerun()

    fn=D.get("funnel")
    if fn:
        st.caption(f"Обучено {fn['trained']} · расписание {fn['fix']}+{fn['tsdb']} · в окне {fn['inwin']} · с кэфами {fn['odds']} · валуев {fn['passed']} · в портфель +{fn['added']}")
    with st.expander("🔌 Диагностика источников"):
        for line in D.get("report",[]): st.text(line)

    for c in D.get("cards",[]):
        if mode=="🎯 Высокая проходимость" and not (c["hot"] or c["tag"]): continue
        if mode=="💰 Валуи (EV)" and not c["best"]: continue
        val=c["best"] is not None
        badge="<span class='badge val'>🟢 ВАЛУЙ</span>" if val else ("<span class='badge hot'>🔥 P≥{:.0f}%</span>".format(thr*100) if c["hot"] else "<span class='badge no'>фон</span>")
        def fr(s): return "".join(f"<b class='{'w' if ch=='В' else ('d' if ch=='Н' else 'l')}'>{ch}</b>" for ch in s)
        rows_html="<div class='mrow hdr'><span>Рынок</span><span>Выбор</span><span>Вероятность</span><span>P</span><span>Безуб.</span><span>Кэф</span><span>EV</span><span></span></div>"
        for rw in c["rows"]:
            w=min(100,rw["prob"]*100)
            odd_s=f"{rw['odd']:.2f}" if rw["odd"] else f"fair {1/rw['prob']:.2f}"
            ev_s=f"<span class='{'evpos' if rw['ev']>0 else 'evneg'}'>{rw['ev']*100:+.1f}%</span>" if rw["ev"] is not None else "<span style='color:#475569'>—</span>"
            be_s=f"{rw['be']*100:.1f}%" if rw["be"] else "—"
            mk="<span class='ok'>✅</span>" if rw["ok"] else ("<span class='ok' style='color:#fde047'>🔥</span>" if rw["prob"]>=thr else "<span class='nok'>·</span>")
            rows_html+=(f"<div class='mrow'><span style='color:#64748b'>{rw['mkt']}</span><b style='color:#facc15'>{rw['pick']}</b>"
                        f"<div><div class='bar'><i style='width:{w:.0f}%'></i></div></div>"
                        f"<span style='color:#4ade80;font-weight:700'>{rw['prob']*100:.1f}%</span><span style='color:#f87171'>{be_s}</span>"
                        f"<span style='color:#f8fafc;font-weight:700'>{odd_s}</span>{ev_s}{mk}</div>")
        ch,ca=c["corners"]; yh,ya=c["yellows"]
        best_html=f"<span>💰 Келли: <b>{c['best'][5]:.2f}</b> на <b>{c['best'][1]}</b> @ <b>{c['best'][2]:.2f}</b></span>" if val else ""
        hot_html="".join(f"<span>🔥 <b>{p}</b> {pr*100:.0f}%</span>" for p,pr,_ in c["hot"]) if not val else ""
        st.markdown(f"""
<div class="mcard {'value' if val else ('hot' if c['hot'] else '')}">
 <div class="mhead"><span class="chip">{c['league']}</span><span class="chip when">📅 {c['date']} · {c['when']}</span>{badge}</div>
 <div class="teams">{c['match'].split(' vs ')[0]} <span>—</span> {c['match'].split(' vs ')[1]}</div>
 <div class="form5">форма: {fr(c['fh'])} <span style='color:#475569'>vs</span> {fr(c['fa'])}</div>
 {rows_html}
 <div class="mfoot"><span>xG: <b>{c['lams'][0]:.2f}–{c['lams'][1]:.2f}</b></span>
  <span>🚩 угловые <b>{ch+ca:.1f}</b></span><span>🟨 жёлтые <b>{yh+ya:.1f}</b></span>
  <span>📚 игр: <b>{c['games']}</b></span>{best_html}{hot_html}</div>
</div>""",unsafe_allow_html=True)
    if not D.get("cards"):
        st.info("Нажми ⚡ СКАН. Лента соберётся из 3 источников — матчи появятся даже если один источник молчит.")

with tab2:
    st.header("💼 Портфель")
    if st.button("🔄 Автосинхронизация"):
        season=find_season(); upd=0
        for bet in [b for b in D["bets"] if b["status"]=="pending" and b.get("div") not in (None,"TSDB")]:
            for r in load_seasonal(bet["div"],season):
                if r.get("HomeTeam")==bet["match"].split(" vs ")[0] and r.get("AwayTeam")==bet["match"].split(" vs ")[1] and r.get("FTHG") not in (None,""):
                    hg,ag=float(r["FTHG"]),float(r["FTAG"]); won=False
                    if bet["market"]=="1X2": won=("П1" if hg>ag else "X" if hg==ag else "П2")==bet["pick"]
                    elif bet["market"]=="OU": won=(bet["pick"]=="ТБ 2.5" and hg+ag>=3) or (bet["pick"]=="ТМ 2.5" and hg+ag<=2)
                    elif bet["market"]=="AH": won=False
                    if won:
                        bet["status"]="won"; pr=bet["stake"]*(bet["odds"]-1)
                        D["bank"]+=bet["stake"]+pr; D["stats"]["won"]+=1; D["stats"]["profit"]+=pr
                    else:
                        bet["status"]="lost"; D["stats"]["lost"]+=1; D["stats"]["profit"]-=bet["stake"]
                    upd+=1; break
        save_data(D); st.success(f"Закрыто: {upd}"); st.rerun()
    if not D["bets"]: st.info("Пусто. Валуи падают сюда автоматически; ставки 🔥-режима добавляй вручную через калькулятор.")
    for i,b in enumerate(D["bets"]):
        icon={"pending":"⏳","won":"🟢","lost":"🔴"}[b["status"]]
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
        D["bets"].append({"match":"Ручная ставка","div":None,"league":"✍️","market":"MANUAL","pick":f"P{p:.0f}%",
                          "odds":o,"stake":kelly(p/100,o,bk,kelly_frac),"prob":p/100,"status":"pending"})
        save_data(D); st.rerun()
