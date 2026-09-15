import streamlit as st
import requests, json, os, csv, io, math
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from math import comb, erf, exp

st.set_page_config(page_title="ALL-SPORTS BET PRO", page_icon="🏟", layout="wide")
OSP_FILE="other_sports_state.json"
API="https://www.thesportsdb.com/api/v1/json/123"
ERR=[]
def log_err(tag,e):
    ERR.append(f"[{tag}] {type(e).__name__}: {e}")
    if len(ERR)>200: ERR.pop(0)

SPORTS={
 "Tennis":     dict(icon="🎾",tsdb="Tennis",     k=25,ha=0, scale=250,best_of=2,set_line=2.5,total_type="sets"),
 "Basketball": dict(icon="🏀",tsdb="Basketball", k=20,ha=40,scale=400,sigma=13.0,total_type="points"),
 "Volleyball": dict(icon="🏐",tsdb="Volleyball", k=25,ha=20,scale=250,best_of=3,set_line=3.5,total_type="sets"),
 "Ice Hockey": dict(icon="🏒",tsdb="Ice Hockey", k=25,ha=30,scale=400,goal_line=5.5,total_type="goals"),
}
PRESETS={
 "Basketball":["NBA","EuroLeague","EuroCup","VTB United","ACB","Super League Turkey","ABA League","Greek Basket","LNB Pro A"],
 "Volleyball":["Italian Volleyball","SuperLega","Polish Volleyball","PlusLiga","Russian Volleyball","Super League","CEV Champions","Nations League","Korean V-League"],
 "Tennis":["ATP","WTA","Davis Cup","Challenger"],
 "Ice Hockey":["NHL","KHL","SHL","Liiga","Extraliga","DEL","Champions Hockey"],
}

st.markdown("""
<style>
html,body,.stApp{background:#070b14 !important;}
.stMarkdown,.stMarkdown p,.stMarkdown li{color:#e2e8f0;}
.stCaption,.stCaption *{color:#94a3b8 !important;}
div[data-testid="stMetricValue"]{color:#f8fafc !important;}
div[data-testid="stMetricLabel"] p{color:#94a3b8 !important;}
header,#MainMenu,footer{visibility:hidden}
section[data-testid="stSidebar"]{background:#0b0f1a !important;}
section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] label,section[data-testid="stSidebar"] span{color:#e2e8f0 !important;}
.mcard{background:rgba(8,12,24,.96);border:1px solid rgba(148,163,184,.22);border-radius:16px;padding:14px 16px;margin-bottom:12px}
.mhead{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.chip{background:rgba(56,189,248,.18);color:#bae6fd;border:1px solid rgba(56,189,248,.45);padding:3px 10px;border-radius:999px;font-size:.72rem;font-weight:700}
.chip.when{background:rgba(250,204,21,.16);color:#fde68a;border-color:rgba(250,204,21,.45)}
.chip.src{background:rgba(16,185,129,.15);color:#86efac;border-color:rgba(16,185,129,.4)}
.teams{font-size:1.2rem;font-weight:800;color:#fff;margin:8px 0 2px}
.teams span{color:#94a3b8;font-weight:400}
.mrow{display:grid;grid-template-columns:120px 1fr 90px 120px;gap:10px;align-items:center;padding:5px 0;border-top:1px solid rgba(148,163,184,.14);font-size:.85rem;color:#e2e8f0}
.mrow.hdr{color:#94a3b8;font-size:.68rem;text-transform:uppercase;border-top:none}
.bar{height:6px;background:rgba(148,163,184,.2);border-radius:99px;overflow:hidden;margin-top:4px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#38bdf8,#4ade80)}
.pos{color:#4ade80;font-weight:700}.neg{color:#f87171;font-weight:700}
</style>""", unsafe_allow_html=True)

# ================= ДАННЫЕ (другие виды) =================
@st.cache_data(ttl=86400)
def ts_all_leagues():
    try:
        r=requests.get(f"{API}/all_leagues.php",timeout=30)
        return (r.json() or {}).get("leagues",[]) or []
    except Exception as e:
        log_err("all_leagues",e); return []
@st.cache_data(ttl=1800)
def ts_events(lid):
    out=[]
    for ep in ("eventspastleague.php","eventsnextleague.php"):
        try:
            r=requests.get(f"{API}/{ep}?id={lid}",timeout=20)
            for e in (r.json() or {}).get("events",[]) or []:
                hs,as_=e.get("intHomeScore"),e.get("intAwayScore")
                out.append({"id":e.get("idEvent"),"h":e.get("strHomeTeam") or "",
                    "a":e.get("strAwayTeam") or "","date":e.get("dateEvent") or "",
                    "hs":int(hs) if hs not in (None,"") else None,
                    "as":int(as_) if as_ not in (None,"") else None,
                    "league":e.get("strLeague") or "","src":"api"})
        except Exception as e: log_err(f"events {lid}",e)
    return out
def pdate(s):
    for f in ("%Y-%m-%d","%d/%m/%Y","%d.%m.%Y"):
        try: return datetime.strptime((s or "").strip(),f)
        except Exception: continue
    return None
def parse_upload(buf):
    rows=[]
    try:
        rd=csv.DictReader(io.StringIO(buf.getvalue().decode("utf-8-sig")))
        mp={}
        for c in (rd.fieldnames or []):
            cl=c.strip().lower()
            if cl in ("date","d","дата"): mp["date"]=c
            elif cl in ("home","h","hometeam","хозяева"): mp["h"]=c
            elif cl in ("away","a","awayteam","гости"): mp["a"]=c
            elif cl in ("hs","home_score","hgoals"): mp["hs"]=c
            elif cl in ("as","away_score","agoals"): mp["as"]=c
        for r in rd:
            try: hs=int(float(r.get(mp.get("hs",""),"") or "")); as_=int(float(r.get(mp.get("as",""),"") or ""))
            except Exception: hs=as_=None
            rows.append({"id":f"up{len(rows)}","h":(r.get(mp.get("h","")) or "").strip(),
                "a":(r.get(mp.get("a","")) or "").strip(),"date":(r.get(mp.get("date","")) or "").strip(),
                "hs":hs,"as":as_,"league":"📁 CSV","src":"file"})
    except Exception as e: log_err("upload",e)
    return rows

# ================= МОДЕЛЬ =================
class SportEngine:
    def __init__(self,cfg):
        self.cfg=cfg; self.elo={}; self.pts=defaultdict(lambda:{"f":[],"a":[]})
    def add(self,h,a,hs,as_):
        if hs==as_ or not h or not a: return
        k=self.cfg["k"]; ha=self.cfg["ha"]
        rh,ra=self.elo.get(h,1500),self.elo.get(a,1500)
        e=1/(1+10**(-((rh+ha)-ra)/self.cfg["scale"]))
        s=1.0 if hs>as_ else 0.0
        self.elo[h]=rh+k*(s-e); self.elo[a]=ra+k*((1-s)-(1-e))
        self.pts[h]["f"].append(hs); self.pts[h]["a"].append(as_)
        self.pts[a]["f"].append(as_); self.pts[a]["a"].append(hs)
        for t in (h,a):
            for kk in self.pts[t]: self.pts[t][kk]=self.pts[t][kk][-20:]
    def _m(self,l,d): return sum(l)/len(l) if l else d
    def best_of(self,p,n):
        win=0.0; dist={}
        for k in range(n):
            pr=comb(n-1+k,k)*(p**n)*((1-p)**k); dist[n+k]=dist.get(n+k,0)+pr; win+=pr
        for k in range(n):
            pr=comb(n-1+k,k)*((1-p)**n)*(p**k); dist[n+k]=dist.get(n+k,0)+pr
        return win,dist
    def predict(self,h,a):
        cfg=self.cfg; tt=cfg["total_type"]
        d=(self.elo.get(h,1500)+cfg["ha"])-self.elo.get(a,1500)
        p_ml=1/(1+10**(-d/cfg["scale"]))
        if tt=="sets":
            p_match,dist=self.best_of(p_ml,cfg["best_of"])
            line=cfg["set_line"]
            p_over=sum(v for s,v in dist.items() if s>line)
            mk=[("П1",p_match),("П2",1-p_match),(f"ТБ {line} сетов",p_over),(f"ТМ {line} сетов",1-p_over)]
        elif tt=="points":
            fh=self._m(self.pts[h]["f"],80); fa_=self._m(self.pts[h]["a"],80)
            af=self._m(self.pts[a]["f"],80); aa_=self._m(self.pts[a]["a"],80)
            mu=(fh+aa_)/2+(af+fa_)/2; line=math.floor(mu)+0.5; sig=cfg["sigma"]
            p_over=0.5*(1-erf((line+0.5-mu)/(sig*math.sqrt(2))))
            mk=[("П1",p_ml),("П2",1-p_ml),(f"ТБ {line}",p_over),(f"ТМ {line}",1-p_over)]
        else:
            fh=self._m(self.pts[h]["f"],3); fa_=self._m(self.pts[h]["a"],3)
            af=self._m(self.pts[a]["f"],3); aa_=self._m(self.pts[a]["a"],3)
            tot=max(0.5,(fh+aa_)/2)+max(0.5,(af+fa_)/2); line=cfg["goal_line"]
            p_over=1-sum(exp(-tot)*tot**k/math.factorial(k) for k in range(int(line)+1))
            mk=[("П1",p_ml),("П2",1-p_ml),(f"ТБ {line}",p_over),(f"ТМ {line}",1-p_over)]
        out=[]
        for name,p in mk:
            p=min(max(p,0.01),0.99); fair=1/p
            out.append({"name":name,"p":p,"fair":fair,"min_ok":round(fair*1.03,2)})
        return out

def kelly(prob,odds,bank,frac=0.25):
    if prob<=0 or odds<=1: return 0.0
    b=odds-1; k=(b*prob-(1-prob))/b
    return round(min(max(0,k*frac),0.05)*bank,2)

# ================= СОСТОЯНИЕ ПО ВИДАМ =================
def osp_load():
    if os.path.exists(OSP_FILE):
        try: return json.load(open(OSP_FILE,encoding="utf-8"))
        except Exception as e: log_err("osp_load",e)
    return {}
def osp_save(d):
    try: json.dump(d,open(OSP_FILE,"w",encoding="utf-8"),indent=2,ensure_ascii=False)
    except Exception as e: log_err("osp_save",e)
def osp_sport(allst,sport):
    if sport not in allst:
        allst[sport]={"bank":5000.0,"bets":[],"stats":{"won":0,"lost":0,"profit":0}}
    return allst[sport]

LEAGUES_ALL=ts_all_leagues()

def render_sport(sport):
    cfg=SPORTS[sport]
    ALL=osp_load(); S=osp_sport(ALL,sport)
    sub=st.tabs(["🛰 Сканер","💼 Портфель","📈 Статистика"])
    with sub[0]:
        opts=sorted([l for l in LEAGUES_ALL if l.get("strSport")==cfg["tsdb"]],key=lambda x:x.get("strLeague",""))
        resolved=[o for o in opts if any(p.lower() in (o.get("strLeague") or "").lower() for p in PRESETS.get(sport,[]))]
        names=[f"{o['strLeague']} (id {o['idLeague']})" for o in opts]
        res_names=[f"{o['strLeague']} (id {o['idLeague']})" for o in resolved]
        c1,c2,c3=st.columns([2,1,1])
        sel=c1.multiselect("Лиги (авто-поиск TheSportsDB)",names,default=res_names[:3])
        man=c2.text_input("ID лиги вручную","")
        days=c3.slider("Горизонт, дней",1,14,7,key=f"d{sport}")
        up=st.file_uploader("Свой CSV (Date,Home,Away,HS,AS) — для лиг вне API",type=["csv"],key=f"u{sport}")
        if st.button(f"⚡ СКАН {cfg['icon']}",type="primary",key=f"scan{sport}"):
            ids=[o["idLeague"] for o in opts if f"{o['strLeague']} (id {o['idLeague']})" in sel]
            if man.strip().isdigit(): ids.append(man.strip())
            ids=list(dict.fromkeys(ids))[:6]
            rows=[]
            if ids:
                with ThreadPoolExecutor(max_workers=4) as ex:
                    for d in ex.map(ts_events,ids): rows+=d
            if up is not None: rows+=parse_upload(up)
            eng=SportEngine(cfg)
            past=sorted([r for r in rows if r["hs"] is not None and r["as"] is not None and pdate(r["date"])],key=lambda r:pdate(r["date"]))
            for r in past: eng.add(r["h"],r["a"],r["hs"],r["as"])
            today=datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
            limit=today+timedelta(days=days)
            cards=[]
            for r in rows:
                d=pdate(r["date"])
                if not d or not (today<=d<=limit): continue
                if r["hs"] is not None or not r["h"] or not r["a"]: continue
                nd=(d-today).days
                cards.append({"eid":r["id"],"league":r["league"] or sport,"src":r["src"],
                    "h":r["h"],"a":r["a"],"date":d.strftime("%d.%m"),
                    "when":"сегодня" if nd==0 else ("завтра" if nd==1 else f"через {nd} дн"),
                    "markets":eng.predict(r["h"],r["a"])})
            cards.sort(key=lambda c:c["date"])
            st.session_state["cards_"+sport]=cards
            st.session_state["trained_"+sport]=len(past)
            st.rerun()
        cards=st.session_state.get("cards_"+sport,[])
        tr=st.session_state.get("trained_"+sport,0)
        if cards: st.caption(f"Обучено матчей: {tr} · событий в окне: {len(cards)}")
        for c in cards:
            st.markdown(f"""
<div class="mcard">
 <div class="mhead"><span class="chip">{c['league']}</span><span class="chip when">📅 {c['date']} · {c['when']}</span>
  <span class="chip src">{'🌐 API' if c['src']=='api' else '📁 CSV'}</span></div>
 <div class="teams">{c['h']} <span>—</span> {c['a']}</div>
 <div class="mrow hdr"><span>Рынок</span><span>Вероятность модели</span><span>Фэйр-кэф</span><span>Мин. кэф ставки</span></div>
 {''.join(f"<div class='mrow'><b style='color:#facc15'>{m['name']}</b><div><div class='bar'><i style='width:{m['p']*100:.0f}%'></i></div><span style='color:#4ade80'>{m['p']*100:.1f}%</span></div><span style='color:#fff;font-weight:700'>{m['fair']:.2f}</span><span class='pos'>≥ {m['min_ok']:.2f}</span></div>" for m in c['markets'])}
</div>""",unsafe_allow_html=True)
            k=c["eid"]
            cc=st.columns([2,1,1])
            mkt=cc[0].selectbox("Рынок",[m["name"] for m in c["markets"]],key=f"m{k}")
            odd=cc[1].number_input("Кэф букмекера",1.01,30.0,1.85,key=f"o{k}")
            prob=next(m["p"] for m in c["markets"] if m["name"]==mkt)
            ev=prob*odd-1
            cc[2].markdown(f"<div style='padding-top:26px' class='{'pos' if ev>0 else 'neg'}'>EV {ev*100:+.1f}%</div>",unsafe_allow_html=True)
            if st.button("➕ В портфель",key=f"b{k}"):
                if ev<=0: st.warning("⛔ EV отрицательный — не добавлено.")
                else:
                    ALL2=osp_load(); S2=osp_sport(ALL2,sport)
                    S2["bets"].append({"match":f"{c['h']} vs {c['a']}","league":c["league"],"sport":sport,
                        "market":mkt,"pick":mkt,"odds":odd,"prob":prob,
                        "stake":kelly(prob,odd,S2["bank"]),"status":"pending"})
                    osp_save(ALL2); st.success("✅ Добавлено"); st.rerun()
        if not cards: st.info("Выбери лиги (или загрузи CSV) и нажми СКАН.")
    with sub[1]:
        st.header(f"💼 Портфель {cfg['icon']}")
        if not S["bets"]: st.info("Пусто.")
        ALLcur=osp_load(); Sc=osp_sport(ALLcur,sport)
        for i,b in enumerate(Sc["bets"]):
            icon={"pending":"⏳","won":"🟢","lost":"🔴"}.get(b["status"],"⏳")
            st.markdown(f"{icon} **{b['match']}** · {b['market']} @ **{b['odds']:.2f}** · {b['stake']:.2f} у.е. · P={b.get('prob',0)*100:.0f}%")
            if b["status"]=="pending":
                cc=st.columns(2)
                if cc[0].button("✅ Зашло",key=f"w{sport}{i}"):
                    A=osp_load(); SS=osp_sport(A,sport); bb=SS["bets"][i]
                    pr=bb["stake"]*(bb["odds"]-1); bb["status"]="won"
                    SS["bank"]+=bb["stake"]+pr; SS["stats"]["won"]+=1; SS["stats"]["profit"]+=pr
                    osp_save(A); st.rerun()
                if cc[1].button("❌ Мимо",key=f"l{sport}{i}"):
                    A=osp_load(); SS=osp_sport(A,sport); bb=SS["bets"][i]
                    bb["status"]="lost"; SS["stats"]["lost"]+=1; SS["stats"]["profit"]-=bb["stake"]
                    osp_save(A); st.rerun()
    with sub[2]:
        st.header(f"📈 Статистика {cfg['icon']}")
        s=S["stats"]; tot=s["won"]+s["lost"]
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Банк вида",f"{S['bank']:.2f}"); m2.metric("Ставок",tot)
        m3.metric("WinRate",f"{(s['won']/tot*100) if tot else 0:.1f}%")
        m4.metric("Profit",f"{s['profit']:+.2f}")
        st.caption(f"Обучено матчей на последнем скане: {st.session_state.get('trained_'+sport,0)}")
        with st.expander(f"🐞 Лог ошибок ({len(ERR)})"):
            for line in ERR[-30:]: st.text(line)

# ================= ВКЛАДКИ ВСЕГО ПРИЛОЖЕНИЯ =================
top=st.tabs(["⚽ Футбол","🎾 Теннис","🏀 Баскетбол","🏐 Волейбол","🏒 Хоккей"])
with top[0]:
    try:
        exec(compile(open("football_v7.py",encoding="utf-8").read(),"football_v7.py","exec"),globals())
    except FileNotFoundError:
        st.error("Положи файл football_v7.py (твой прежний App.py, без изменений) рядом с этим App.py")
with top[1]: render_sport("Tennis")
with top[2]: render_sport("Basketball")
with top[3]: render_sport("Volleyball")
with top[4]: render_sport("Ice Hockey")
