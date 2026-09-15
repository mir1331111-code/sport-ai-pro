import streamlit as st
import requests, json, os, csv, io, math
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from math import comb, erf, exp, sqrt

st.set_page_config(page_title="ALL-SPORTS BET PRO", page_icon="🏟", layout="wide")
OSP_FILE="other_sports_state.json"
API="https://www.thesportsdb.com/api/v1/json/123"
ERR=[]
def log_err(tag,e):
    ERR.append(f"[{tag}] {type(e).__name__}: {e}")
    if len(ERR)>300: ERR.pop(0)

SPORTS={
 "Tennis":     dict(icon="🎾",tsdb="Tennis",     k=25,ha=0, scale=250,best_of=2,set_line=2.5,total_type="sets",handi=1.5),
 "Basketball": dict(icon="🏀",tsdb="Basketball", k=20,ha=40,scale=400,sigma=13.0,total_type="points"),
 "Volleyball": dict(icon="🏐",tsdb="Volleyball", k=25,ha=20,scale=250,best_of=3,set_line=3.5,total_type="sets",handi=1.5),
 "Ice Hockey": dict(icon="🏒",tsdb="Ice Hockey", k=25,ha=30,scale=400,goal_line=5.5,total_type="goals",handi=1.5),
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
.mcard.value{border-color:rgba(16,185,129,.6);box-shadow:0 0 22px rgba(16,185,129,.15)}
.mhead{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.chip{background:rgba(56,189,248,.18);color:#bae6fd;border:1px solid rgba(56,189,248,.45);padding:3px 10px;border-radius:999px;font-size:.72rem;font-weight:700}
.chip.when{background:rgba(250,204,21,.16);color:#fde68a;border-color:rgba(250,204,21,.45)}
.chip.src{background:rgba(16,185,129,.15);color:#86efac;border-color:rgba(16,185,129,.4)}
.badge{margin-left:auto;padding:4px 12px;border-radius:999px;font-size:.72rem;font-weight:800}
.badge.hot{background:rgba(250,204,21,.2);color:#fde68a;border:1px solid rgba(250,204,21,.6)}
.badge.no{background:rgba(100,116,139,.2);color:#cbd5e1;border:1px solid rgba(100,116,139,.4)}
.teams{font-size:1.2rem;font-weight:800;color:#fff;margin:8px 0 2px}
.teams span{color:#94a3b8;font-weight:400}
.verdict{background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.3);border-radius:12px;padding:10px 14px;margin:8px 0;color:#e2e8f0;font-size:.86rem}
.verdict b.y{color:#facc15}.verdict b.g{color:#4ade80}.verdict b.r{color:#f87171}
.meta{color:#94a3b8;font-size:.78rem;margin:4px 0}
.meta b{color:#facc15}
.mrow{display:grid;grid-template-columns:130px 1fr 80px 110px;gap:10px;align-items:center;padding:5px 0;border-top:1px solid rgba(148,163,184,.14);font-size:.85rem;color:#e2e8f0}
.mrow.hdr{color:#94a3b8;font-size:.68rem;text-transform:uppercase;border-top:none}
.bar{height:6px;background:rgba(148,163,184,.2);border-radius:99px;overflow:hidden;margin-top:4px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#38bdf8,#4ade80)}
.pos{color:#4ade80;font-weight:700}.neg{color:#f87171;font-weight:700}
.form5 b{padding:1px 5px;border-radius:4px;margin-right:2px}
.w{background:rgba(16,185,129,.3);color:#86efac}.l{background:rgba(239,68,68,.25);color:#fca5a5}
</style>""", unsafe_allow_html=True)

# ================= ИСТОЧНИКИ =================
@st.cache_data(ttl=86400)
def ts_all_leagues():
    try:
        r=requests.get(f"{API}/all_leagues.php",timeout=30)
        return (r.json() or {}).get("leagues",[]) or []
    except Exception as e:
        log_err("all_leagues",e); return []
@st.cache_data(ttl=3600)
def ts_events_day(dstr,sport):
    out=[]
    try:
        r=requests.get(f"{API}/eventsday.php?d={dstr}&s={sport}",timeout=20)
        for e in (r.json() or {}).get("events",[]) or []:
            hs,as_=e.get("intHomeScore"),e.get("intAwayScore")
            out.append({"id":e.get("idEvent"),"h":e.get("strHomeTeam") or "","a":e.get("strAwayTeam") or "",
                "date":e.get("dateEvent") or "","hs":int(hs) if hs not in (None,"") else None,
                "as":int(as_) if as_ not in (None,"") else None,"league":e.get("strLeague") or sport,"src":"api"})
    except Exception as e: log_err(f"eventsday {dstr}",e)
    return out
@st.cache_data(ttl=1800)
def ts_league_events(lid):
    out=[]
    for ep in ("eventspastleague.php","eventsnextleague.php"):
        try:
            r=requests.get(f"{API}/{ep}?id={lid}",timeout=20)
            for e in (r.json() or {}).get("events",[]) or []:
                hs,as_=e.get("intHomeScore"),e.get("intAwayScore")
                out.append({"id":f"{lid}-{e.get('idEvent')}-{ep[:4]}","h":e.get("strHomeTeam") or "",
                    "a":e.get("strAwayTeam") or "","date":e.get("dateEvent") or "",
                    "hs":int(hs) if hs not in (None,"") else None,
                    "as":int(as_) if as_ not in (None,"") else None,
                    "league":e.get("strLeague") or "","src":"api"})
        except Exception as e: log_err(f"league {lid}",e)
    return out
@st.cache_data(ttl=3600)
def tennis_data_csv():
    """Реальные результаты ATP/WTA С КОЭФФИЦИЕНТАМИ букмекеров"""
    rows=[]; rep=[]
    y=datetime.now().year
    for year in (y,y-1):
        for tour in ("atp","wta"):
            url=f"https://www.tennis-data.co.uk/{year}/{tour}.csv"
            try:
                r=requests.get(url,timeout=25,headers={"User-Agent":"Mozilla/5.0"})
                if r.status_code!=200: rep.append(f"{tour}{year}: HTTP {r.status_code}"); continue
                rd=list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig","ignore"))))
                n=0
                for x in rd:
                    m=x.get("Match") or ""
                    if " vs " not in m: continue
                    h,a=[s.strip() for s in m.split(" vs ")]
                    win,los=x.get("Winner") or "",x.get("Loser") or ""
                    try: ws,ls=int(float(x.get("Wsets") or 0)),int(float(x.get("Lsets") or 0))
                    except Exception: continue
                    if h==win: hs,as_=ws,ls
                    elif h==los: hs,as_=ls,ws
                    else: continue
                    ow=_f(x.get("B365W")) or _f(x.get("PSW")); ol=_f(x.get("B365L")) or _f(x.get("PSL"))
                    rows.append({"id":f"td{year}{tour}{n}","h":h,"a":a,"date":x.get("Date") or "",
                        "hs":hs,"as":as_,"league":("ATP" if tour=="atp" else "WTA")+f" {year}",
                        "src":"td","odds_h":ow if h==win else ol,"odds_a":ol if h==win else ow})
                    n+=1
                rep.append(f"{tour}{year}: {n} матчей с кэфами")
            except Exception as e:
                log_err(f"tennis-data {tour}{year}",e); rep.append(f"{tour}{year}: ошибка")
    return rows,rep
def _f(v):
    try: return float(v)
    except Exception: return None
def pdate(s):
    for f in ("%Y-%m-%d","%d/%m/%Y","%d.%m.%y"):
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

# ================= ДВИЖОК =================
class SportEngine:
    def __init__(self,cfg):
        self.cfg=cfg; self.elo={}; self.pts=defaultdict(lambda:{"f":[],"a":[]})
        self.form=defaultdict(list); self.h2h=defaultdict(list)
    def add(self,h,a,hs,as_):
        if hs==as_ or not h or not a: return
        k=self.cfg["k"]; ha=self.cfg["ha"]
        rh,ra=self.elo.get(h,1500),self.elo.get(a,1500)
        e=1/(1+10**(-((rh+ha)-ra)/self.cfg["scale"]))
        s=1.0 if hs>as_ else 0.0
        self.elo[h]=rh+k*(s-e); self.elo[a]=ra+k*((1-s)-(1-e))
        self.pts[h]["f"].append(hs); self.pts[h]["a"].append(as_)
        self.pts[a]["f"].append(as_); self.pts[a]["a"].append(hs)
        self.form[h].append(1 if hs>as_ else 0); self.form[a].append(1 if as_>hs else 0)
        self.h2h[(h,a)].append(f"{hs}:{as_}")
        for t in (h,a):
            for kk in self.pts[t]: self.pts[t][kk]=self.pts[t][kk][-20:]
            self.form[t]=self.form[t][-10:]
        self.h2h[(h,a)]=self.h2h[(h,a)][-6:]
    def _m(self,l,d): return sum(l)/len(l) if l else d
    def form_str(self,t):
        return "".join("В" if x else "П" for x in self.form[t][-5:]) or "—"
    def h2h_str(self,h,a):
        return ", ".join(self.h2h.get((h,a),[])[-4:]) or "—"
    def best_of(self,p,n):
        win=0.0; dist={}
        for k in range(n):
            pr=comb(n-1+k,k)*(p**n)*((1-p)**k); dist[n+k]=dist.get(n+k,0)+pr; win+=pr
        for k in range(n):
            pr=comb(n-1+k,k)*((1-p)**n)*(p**k); dist[n+k]=dist.get(n+k,0)+pr
        return win,dist
    def predict(self,h,a):
        cfg=self.cfg; tt=cfg["total_type"]
        rh,ra=self.elo.get(h,1500),self.elo.get(a,1500)
        d=(rh+cfg["ha"])-ra
        p_ml=1/(1+10**(-d/cfg["scale"]))
        mk=[]; extra=""
        if tt=="sets":
            n=cfg["best_of"]; line=cfg["set_line"]; hd=cfg["handi"]
            p_match,dist=self.best_of(p_ml,n)
            p_over=sum(v for s,v in dist.items() if s>line)
            p_handi=sum(v for s,v in dist.items() if s-n>=hd)
            mk=[("П1",p_match),("П2",1-p_match),
                (f"ТБ {line} сетов",p_over),(f"ТМ {line} сетов",1-p_over),
                (f"Ф1 (-{hd})",p_handi),(f"Ф2 (+{hd})",1-p_handi)]
            exp_sets=sum(s*v for s,v in dist.items())
            extra=f"ожидаемые сеты {exp_sets:.1f}"
        elif tt=="points":
            fh=self._m(self.pts[h]["f"],80); fa_=self._m(self.pts[h]["a"],80)
            af=self._m(self.pts[a]["f"],80); aa_=self._m(self.pts[a]["a"],80)
            mu_h=(fh+aa_)/2; mu_a=(af+fa_)/2; mu=mu_h+mu_a
            line=math.floor(mu)+0.5; sig=cfg["sigma"]
            p_over=0.5*(1-erf((line+0.5-mu)/(sig*sqrt(2))))
            diff=mu_h-mu_a; hline=math.floor(diff)+0.5
            p_cov=0.5*(1-erf((hline+0.5-diff)/(sig*sqrt(2))))
            mk=[("П1",p_ml),("П2",1-p_ml),(f"ТБ {line}",p_over),(f"ТМ {line}",1-p_over),
                (f"Ф1 ({hline:+.1f})",p_cov),(f"Ф2 ({-hline:+.1f})",1-p_cov)]
            extra=f"ожидаемые очки {mu:.0f} ({mu_h:.0f}–{mu_a:.0f})"
        else:
            fh=self._m(self.pts[h]["f"],3); fa_=self._m(self.pts[h]["a"],3)
            af=self._m(self.pts[a]["f"],3); aa_=self._m(self.pts[a]["a"],3)
            lh=max(0.5,(fh+aa_)/2); la=max(0.5,(af+fa_)/2); tot=lh+la
            line=cfg["goal_line"]; hd=cfg["handi"]
            p_over=1-sum(exp(-tot)*tot**k/math.factorial(k) for k in range(int(line)+1))
            md=lh-la; vd=lh+la
            p_cov=0.5*(1-erf((hd+0.5-md)/sqrt(vd if vd>0 else 1)))
            mk=[("П1",p_ml),("П2",1-p_ml),(f"ТБ {line}",p_over),(f"ТМ {line}",1-p_over),
                (f"Ф1 (-{hd})",p_cov),(f"Ф2 (+{hd})",1-p_cov)]
            extra=f"xG {lh:.1f}–{la:.1f}"
        out=[]
        for name,p in mk:
            p=min(max(p,0.01),0.99); fair=1/p
            out.append({"name":name,"p":p,"fair":fair,"min_ok":round(fair*1.03,2)})
        return {"markets":out,"elo":(int(rh),int(ra)),"extra":extra,
                "fh":self.form_str(h),"fa":self.form_str(a),"h2h":self.h2h_str(h,a),
                "games":min(len(self.form[h]),len(self.form[a]))}

def kelly(prob,odds,bank,frac=0.25):
    if prob<=0 or odds<=1: return 0.0
    b=odds-1; k=(b*prob-(1-prob))/b
    return round(min(max(0,k*frac),0.05)*bank,2)

# ================= СОСТОЯНИЕ =================
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

# ================= HTML =================
def mrows_html(markets):
    out="<div class='mrow hdr'><span>Рынок</span><span>Вероятность модели</span><span>Фэйр-кэф</span><span>Мин. кэф ставки</span></div>"
    for m in markets:
        w=m["p"]*100
        out+=f"<div class='mrow'><b style='color:#facc15'>{m['name']}</b><div><div class='bar'><i style='width:{w:.0f}%'></i></div><span style='color:#4ade80'>{w:.1f}%</span></div><span style='color:#fff;font-weight:700'>{m['fair']:.2f}</span><span class='pos'>&ge; {m['min_ok']:.2f}</span></div>"
    return out
def form_html(s):
    return "".join(f"<b class='{'w' if ch=='В' else 'l'}'>{ch}</b>" for ch in s)
def verdict_html(P,thr):
    mk=sorted(P["markets"],key=lambda m:-m["p"])
    main,alt,avoid=mk[0],mk[1],min(mk,key=lambda m:m["p"])
    hot=" 🔥" if main["p"]>=thr else ""
    line=(f"🤖 <b>Вердикт:</b> ✅ <b class='y'>{main['name']}</b> (P {main['p']*100:.0f}%, ставить при кэфе ≥ {main['min_ok']:.2f}){hot} · "
          f"🔁 <b class='g'>{alt['name']}</b> (P {alt['p']*100:.0f}%) · ⛔ <b class='r'>{avoid['name']}</b>")
    why=(f"Elo {P['elo'][0]} vs {P['elo'][1]} · форма {P['fh']} против {P['fa']} · H2H: {P['h2h']} · {P['extra']}")
    return f"<div class='verdict'>{line}<br><span style='color:#cbd5e1'>{why}</span></div>"
def card_html(c,thr):
    P=c.get("P",{"markets":[],"elo":(0,0),"extra":"","fh":"—","fa":"—","h2h":"—","games":0})
    hot=any(m["p"]>=thr for m in P["markets"])
    badge=f"<span class='badge hot'>🔥 P≥{thr*100:.0f}%</span>" if hot else "<span class='badge no'>фон</span>"
    src="🌐 API" if c["src"]=="api" else ("🎾 tennis-data" if c["src"]=="td" else "📁 CSV")
    return ("<div class='mcard "+("value' " if hot else "' ")+"><div class='mhead'>"
        "<span class='chip'>"+c["league"]+"</span><span class='chip when'>📅 "+c["date"]+" · "+c["when"]+"</span>"
        "<span class='chip src'>"+src+"</span>"+badge+"</div>"
        "<div class='teams'>"+c["h"]+" <span>—</span> "+c["a"]+"</div>"
        +verdict_html(P,thr)
        +f"<div class='meta'>форма: {form_html(P['fh'])} <span style='color:#475569'>vs</span> {form_html(P['fa'])} · 📚 игр в базе: <b>{P['games']}</b></div>"
        +mrows_html(P["markets"])+
        "</div>")

LEAGUES_ALL=ts_all_leagues()

# ================= ВКЛАДКА ВИДА =================
def render_sport(sport):
    cfg=SPORTS[sport]
    ALL=osp_load(); S=osp_sport(ALL,sport)
    sub=st.tabs(["🛰 Сканер","💼 Портфель","📈 Статистика","🧪 Бэктест"])
    with sub[0]:
        opts=sorted([l for l in LEAGUES_ALL if l.get("strSport")==cfg["tsdb"]],key=lambda x:x.get("strLeague",""))
        resolved=[o for o in opts if any(p.lower() in (o.get("strLeague") or "").lower() for p in PRESETS.get(sport,[]))]
        names=[f"{o['strLeague']} (id {o['idLeague']})" for o in opts]
        res_names=[f"{o['strLeague']} (id {o['idLeague']})" for o in resolved]
        st.caption("🔎 Матчи: все лиги вида по дням + расписание лиг списка. Обучение: история лиг"
                   +(" + tennis-data.co.uk (реальные кэфы)" if sport=="Tennis" else "")+" + свой CSV.")
        c1,c2=st.columns([3,1])
        sel=c1.multiselect("Лиги для обучения",names,default=(res_names or names)[:3],key=f"ms{sport}")
        days=c2.slider("Горизонт, дней",1,21,10,key=f"d{sport}")
        thr=st.slider("Порог проходимости, %",50,80,60,key=f"t{sport}")/100
        up=st.file_uploader("Свой CSV (Date,Home,Away,HS,AS)",type=["csv"],key=f"u{sport}")
        if st.button("🧹 Очистить кэш вида",key=f"clr{sport}"):
            st.session_state["cards_"+sport]=[]
            st.session_state["trained_"+sport]=0
            st.session_state["diag_"+sport]={}
            st.cache_data.clear()
            st.rerun()
        if st.button(f"⚡ СКАН {cfg['icon']}",type="primary",key=f"scan{sport}"):
            today=datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
            limit=today+timedelta(days=days)
            rows=[]; seen=set(); diag={}
            prog=st.progress(0.0,text="🔎 Матчи по дням (все лиги вида)...")
            for off in range(days):
                dstr=(today+timedelta(days=off)).strftime("%Y-%m-%d")
                for r in ts_events_day(dstr,cfg["tsdb"]):
                    if r["id"] not in seen: seen.add(r["id"]); rows.append(r)
                prog.progress((off+1)/days*0.4)
            diag["eventsday"]=len(rows)
            prog.progress(0.5,text="📅 Расписание лиг списка...")
            pool=resolved or opts[:6]
            if sport=="Tennis": pool=opts[:10]
            with ThreadPoolExecutor(max_workers=6) as ex:
                for d in ex.map(ts_league_events,[o["idLeague"] for o in pool]):
                    for r in d:
                        if r["id"] not in seen: seen.add(r["id"]); rows.append(r)
            diag["league_next"]=len(rows)-diag["eventsday"]
            prog.progress(0.65,text="📚 История для обучения...")
            ids=[o["idLeague"] for o in opts if f"{o['strLeague']} (id {o['idLeague']})" in sel]
            with ThreadPoolExecutor(max_workers=4) as ex:
                for d in ex.map(ts_league_events,ids[:4]):
                    for r in d:
                        if r["id"] not in seen: seen.add(r["id"]); rows.append(r)
            if sport=="Tennis":
                td,tdrep=tennis_data_csv()
                diag["tennis_data"]=len(td)
                for r in td:
                    if r["id"] not in seen: seen.add(r["id"]); rows.append(r)
                st.session_state["tdrep_"+sport]=tdrep
            if up is not None:
                for r in parse_upload(up):
                    r["id"]=f"{sport}-{r['id']}"
                    if r["id"] not in seen: seen.add(r["id"]); rows.append(r)
            prog.progress(0.8,text="🧠 Обучение и расчёт...")
            eng=SportEngine(cfg)
            past=sorted([r for r in rows if r["hs"] is not None and r["as"] is not None and pdate(r["date"])],key=lambda r:pdate(r["date"]))
            for r in past: eng.add(r["h"],r["a"],r["hs"],r["as"])
            cards=[]
            for r in rows:
                d=pdate(r["date"])
                if not d or not (today<=d<=limit): continue
                if r["hs"] is not None or not r["h"] or not r["a"]: continue
                nd=(d-today).days
                when="сегодня" if nd==0 else ("завтра" if nd==1 else f"через {nd} дн")
                cards.append({"eid":r["id"],"league":r["league"] or sport,"src":r["src"],
                    "h":r["h"],"a":r["a"],"date":d.strftime("%d.%m"),"when":when,
                    "P":eng.predict(r["h"],r["a"])})
            cards.sort(key=lambda c:(any(m["p"]>=thr for m in c.get("P",{"markets":[]})["markets"]),c["date"]),reverse=True)
            prog.empty()
            st.session_state["cards_"+sport]=cards
            st.session_state["trained_"+sport]=len(past)
            st.session_state["diag_"+sport]=diag
            st.rerun()
        diag=st.session_state.get("diag_"+sport,{})
        if diag:
            with st.expander("🔌 Диагностика источников"):
                for k,v in diag.items(): st.text(f"{k}: {v} событий")
                for line in st.session_state.get("tdrep_"+sport,[]): st.text(line)
        cards=[c for c in st.session_state.get("cards_"+sport,[]) if "P" in c]
        if len(cards)!=len(st.session_state.get("cards_"+sport,[])):
            st.warning("🧹 Старые данные очищены — запусти СКАН заново для актуальных карточек.")
            st.session_state["cards_"+sport]=cards
        tr=st.session_state.get("trained_"+sport,0)
        if cards:
            st.caption(f"Обучено матчей: {tr} · событий в окне: {len(cards)}")
            hot_cards=[c for c in cards if any(m["p"]>=thr for m in c.get("P",{"markets":[]})["markets"])]
            if hot_cards:
                st.markdown("### 🎯 НА ЧТО СТАВИТЬ")
                bank=S["bank"]
                for i,c in enumerate(hot_cards[:8],1):
                    P=c.get("P",{"markets":[],"elo":(0,0),"extra":"","fh":"—","fa":"—","h2h":"—","games":0})
                    mk=max(P["markets"],key=lambda m:m["p"])
                    stars="⭐⭐⭐⭐⭐" if mk["p"]>=0.70 else ("⭐⭐⭐⭐" if mk["p"]>=0.65 else "⭐⭐⭐")
                    stake=round(bank*0.01,2)
                    st.markdown(f"<div class='mcard value'><div class='mhead'><span class='chip'>{c['league']}</span>"
                        f"<span class='chip when'>📅 {c['date']} · {c['when']}</span><span class='badge hot'>{stars}</span></div>"
                        f"<div class='teams' style='font-size:1.1rem'>{i}. {c['h']} — {c['a']}</div>"
                        f"<div class='verdict'>➤ Ставь <b class='y'>{mk['name']}</b> при кэфе <b class='y'>≥ {mk['min_ok']:.2f}</b> · "
                        f"P <b class='g'>{mk['p']*100:.0f}%</b> · сумма <b class='y'>{stake:.2f} у.е.</b> (флэт 1%)<br>"
                        f"<span style='color:#cbd5e1'>Elo {P['elo'][0]} vs {P['elo'][1]} · форма {P['fh']} / {P['fa']} · H2H: {P['h2h']} · {P['extra']}</span></div></div>",
                        unsafe_allow_html=True)
            for c in cards:
                st.markdown(card_html(c,thr),unsafe_allow_html=True)
                P=c.get("P",{"markets":[],"elo":(0,0),"extra":"","fh":"—","fa":"—","h2h":"—","games":0})
                kk=f"{sport}_{c['eid']}"
                cc=st.columns([2,1,1])
                mkt=cc[0].selectbox("Рынок",[m["name"] for m in P["markets"]],key=f"m{kk}")
                odd=cc[1].number_input("Кэф букмекера",1.01,30.0,1.85,key=f"o{kk}")
                prob=next(m["p"] for m in P["markets"] if m["name"]==mkt)
                ev=prob*odd-1
                ev_cls="pos" if ev>0 else "neg"
                cc[2].markdown(f"<div style='padding-top:26px' class='{ev_cls}'>EV {ev*100:+.1f}%</div>",unsafe_allow_html=True)
                if st.button("➕ В портфель",key=f"b{kk}"):
                    if ev<=0: st.warning("⛔ EV отрицательный — не добавлено.")
                    else:
                        A2=osp_load(); S2=osp_sport(A2,sport)
                        S2["bets"].append({"match":f"{c['h']} vs {c['a']}","league":c["league"],"sport":sport,
                            "market":mkt,"pick":mkt,"odds":odd,"prob":prob,
                            "stake":kelly(prob,odd,S2["bank"]),"status":"pending"})
                        osp_save(A2); st.success("✅ Добавлено"); st.rerun()
        else:
            st.info("Матчей в окне не найдено. Увеличь горизонт или загрузи CSV. Диагностика выше покажет, что вернул каждый источник.")
    with sub[1]:
        st.header(f"💼 Портфель {cfg['icon']}")
        ALLcur=osp_load(); Sc=osp_sport(ALLcur,sport)
        if not Sc["bets"]: st.info("Пусто.")
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
        with st.expander(f"🐞 Лог ошибок ({len(ERR)})"):
            if ERR:
                for line in ERR[-30:]: st.text(line)
            else: st.text("Ошибок нет.")
    with sub[3]:
        st.header(f"🧪 Бэктест {cfg['icon']} (walk-forward)")
        st.caption("Модель учится матч за матчем по хронологии; ставка флэт 1 у.е. на ML при P≥порога."
                   +(" По теннису кэфы реальные (B365/Pinnacle из tennis-data)." if sport=="Tennis" else " Кэф = фэйр модели (оценка калибровки)."))
        b1,b2=st.columns(2)
        bt_thr=b1.slider("Порог P, %",50,80,60,key=f"bt{sport}")/100
        bt_max=b2.slider("Макс. матчей",100,2000,400,key=f"bm{sport}")
        if st.button("▶️ Прогнать",type="primary",key=f"btrun{sport}"):
            rows=[]
            if sport=="Tennis":
                td,_=tennis_data_csv(); rows=td
            else:
                ids=[o["idLeague"] for o in (resolved or opts[:4])]
                for lid in ids[:3]:
                    rows+=[r for r in ts_league_events(lid) if r["hs"] is not None]
            rows=[r for r in rows if r["hs"] is not None and r["as"] is not None and pdate(r["date"])]
            rows.sort(key=lambda r:pdate(r["date"]))[-bt_max:]
            eng=SportEngine(cfg); log=[]
            for r in rows:
                P=eng.predict(r["h"],r["a"])
                pm=P["markets"][0]
                if pm["p"]>=bt_thr:
                    odd=r.get("odds_h") or pm["fair"]
                    won=r["hs"]>r["as"]
                    log.append({"p":pm["p"],"odd":odd,"won":won,"pnl":odd-1 if won else -1})
                pa=P["markets"][1]
                if pa["p"]>=bt_thr:
                    odd=r.get("odds_a") or pa["fair"]
                    won=r["as"]>r["hs"]
                    log.append({"p":pa["p"],"odd":odd,"won":won,"pnl":odd-1 if won else -1})
                eng.add(r["h"],r["a"],r["hs"],r["as"])
            if not log: st.warning("Нет сигналов — снизь порог.")
            else:
                n=len(log); w=sum(1 for x in log if x["won"]); pr=sum(x["pnl"] for x in log)
                c1,c2,c3,c4=st.columns(4)
                c1.metric("Ставок",n); c2.metric("WinRate",f"{w/n*100:.1f}%")
                c3.metric("PnL флэт",f"{pr:+.1f}"); c4.metric("Средний кэф",f"{sum(x['odd'] for x in log)/n:.2f}")
                bins=defaultdict(lambda:[0,0])
                for x in log:
                    b0=min(4,int(x["p"]*5)); bins[b0][0]+=1; bins[b0][1]+=1 if x["won"] else 0
                rr=[{"Прогноз P":f"{b0*20}–{b0*20+20}%","Ставок":c,"Факт":f"{ww/c*100:.0f}%"} for b0,(c,ww) in sorted(bins.items()) if c>=5]
                if rr: st.dataframe(rr,use_container_width=True,hide_index=True)
                if pr>0: st.success("✅ Модель в плюсе на истории.")
                else: st.error("❌ Минус — повысь порог или не ставь этот вид.")

# ================= ГЛАВНЫЕ ВКЛАДКИ =================
ALL0=osp_load()
tot_profit=sum(v.get("stats",{}).get("profit",0) for v in ALL0.values() if isinstance(v,dict))
tot_pending=sum(1 for v in ALL0.values() if isinstance(v,dict) for b in v.get("bets",[]) if b.get("status")=="pending")
st.markdown(f"""
<div style="padding:14px 22px;border-radius:18px;margin-bottom:12px;border:1px solid rgba(56,189,248,.35);
 background:linear-gradient(120deg,rgba(2,6,23,.96),rgba(30,58,138,.6) 60%,rgba(6,78,59,.6));">
 <h1 style="margin:0;font-size:2rem;font-weight:900;color:#fff;text-shadow:0 2px 10px rgba(0,0,0,.9)">🏟 ALL-SPORTS BET PRO</h1>
 <p style="margin:4px 0 0;color:#dbeafe;font-size:.9rem">Футбол · Теннис · Баскетбол · Волейбол · Хоккей — у каждого вида своё обучение, банк, статистика и бэктест</p>
 <p style="margin:6px 0 0;color:#94a3b8;font-size:.85rem">Другие виды: ставок в работе {tot_pending} · суммарная прибыль {tot_profit:+.0f} у.е.</p>
</div>""",unsafe_allow_html=True)

top=st.tabs(["⚽ Футбол","🎾 Теннис","🏀 Баскетбол","🏐 Волейбол","🏒 Хоккей"])
with top[0]:
    try:
        exec(compile(open("football_v7.py",encoding="utf-8").read(),"football_v7.py","exec"),globals())
    except FileNotFoundError:
        st.error("Положи файл football_v7.py (твой прежний App.py без изменений) рядом с этим App.py")
with top[1]: render_sport("Tennis")
with top[2]: render_sport("Basketball")
with top[3]: render_sport("Volleyball")
with top[4]: render_sport("Ice Hockey")
