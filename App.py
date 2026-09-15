import streamlit as st
import requests, csv, io, json, os, math, re
from datetime import datetime, timedelta, date
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="NEURO BET PRO Multi", page_icon="🏟", layout="wide")
HISTORY_FILE="neuro_multi.json"
MATRIX_N=9
UA={"User-Agent":"Mozilla/5.0"}
ERR=[]
def log_err(tag,e):
    ERR.append(f"[{tag}] {type(e).__name__}: {e}")
    if len(ERR)>300: ERR.pop(0)

SPORTS={
 "⚽ Футбол":dict(src="fd"),
 "🏐 Волейбол":dict(src="espn",espn=["volleyball/womens-college-volleyball","volleyball/mens-college-volleyball"],tsdb_sport="Volleyball",kw=[],max=3,k=24,ha=50,div=150),
 "🏒 Хоккей":dict(src="nhl",espn=["hockey/nhl"],tsdb_sport="Ice Hockey",kw=["NHL","KHL","AHL","SHL"],max=3,k=24,ha=40,div=120,tot=True,pois=True),
}

DIV_NAMES={"E0":"🏴󠁧󠁢󠁥󠁮󠁧󠁿 АПЛ","E1":"🏴󠁧󠁢󠁥󠁮 Чемпионшип","SC0":"🏴󠁧󠁢󠁳󠁣󠁴󠁿 Шотландия",
 "D1":"🇩🇪 Бундеслига","D2":"🇩🇪 2.Бундеслига","I1":"🇮🇹 Серия A","I2":"🇮🇹 Серия B",
 "SP1":"🇪🇸 Ла Лига","SP2":"🇪🇸 Сегунда","F1":"🇫🇷 Лига 1","F2":"🇫🇷 Лига 2",
 "N1":"🇳🇱 Эредивизи","B1":"🇧🇪 Про-лига","P1":"🇵🇹 Примейра","T1":"🇹🇷 Суперлига",
 "G1":"🇬🇷 Греция","R1":"🇷🇺 РПЛ","BR1":"🇧🇷 Бразилия","C1":"🏆 ЛЧ","EL":"🏆 ЛЕ","EC":"🏆 ЛК"}

GOALS={
 "🎯 Проходимость":dict(w_market=0.65,thr=0.62,dis=False,edge=0.01,ev=0.01,corr=(1.30,2.30),min_games=10),
 "⚖️ Баланс":dict(w_market=0.40,thr=0.55,dis=True,edge=0.02,ev=0.02,corr=(1.40,4.20),min_games=8),
 "💰 Value":dict(w_market=0.20,thr=0.45,dis=True,edge=0.03,ev=0.02,corr=(1.40,4.20),min_games=6),
}
CORRIDORS={"OU":(1.50,2.80),"AH":(1.60,2.60),"STAT":(1.40,4.50)}

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
section[data-testid="stSidebar"] div[data-baseweb="select"]>div{background:#111827 !important;}
.hero{padding:18px 24px;border-radius:20px;margin-bottom:14px;border:1px solid rgba(56,189,248,.35);
 background:linear-gradient(120deg,rgba(2,6,23,.96),rgba(6,78,59,.8) 55%,rgba(120,53,15,.75));}
.hero h1{margin:0;font-size:2.1rem;font-weight:900;color:#fff}
.hero p{margin:4px 0 0;color:#dbeafe;font-size:.9rem}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:12px}
.kpi{background:rgba(2,6,23,.92);border:1px solid rgba(148,163,184,.28);border-radius:14px;padding:10px 14px}
.kpi .t{color:#7dd3fc;font-size:.66rem;text-transform:uppercase;letter-spacing:1.1px}
.kpi .v{font-size:1.35rem;font-weight:800;color:#fff}
.kpi .v.g{color:#4ade80}.kpi .v.y{color:#facc15}.kpi .v.r{color:#f87171}
.mcard{background:rgba(8,12,24,.96);border:1px solid rgba(148,163,184,.22);border-radius:14px;padding:14px 16px;margin-bottom:12px}
.mcard.value{border-color:rgba(16,185,129,.65)}
.mcard.hot{border-color:rgba(250,204,21,.6)}
.chip{background:rgba(56,189,248,.18);color:#bae6fd;border:1px solid rgba(56,189,248,.45);padding:2px 9px;border-radius:999px;font-size:.7rem;font-weight:700;margin-right:6px}
.chip.when{background:rgba(250,204,21,.16);color:#fde68a;border-color:rgba(250,204,21,.45)}
.badge{float:right;padding:3px 10px;border-radius:999px;font-size:.7rem;font-weight:800}
.badge.val{background:rgba(16,185,129,.22);color:#86efac;border:1px solid rgba(16,185,129,.6)}
.badge.hot{background:rgba(250,204,21,.2);color:#fde68a;border-color:rgba(250,204,21,.6)}
.badge.no{background:rgba(100,116,139,.2);color:#cbd5e1;border:1px solid rgba(100,116,139,.4)}
.teams{font-size:1.2rem;font-weight:800;color:#fff;margin:8px 0 2px}
.teams span{color:#94a3b8;font-weight:400}
.verdict{background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.3);border-radius:10px;padding:8px 12px;margin:6px 0;color:#e2e8f0;font-size:.85rem}
.verdict b.y{color:#facc15}.verdict b.g{color:#4ade80}.verdict b.r{color:#f87171}
.mrow{display:grid;grid-template-columns:80px 1fr 80px 80px 80px 30px;gap:8px;padding:5px 0;border-top:1px solid rgba(148,163,184,.12);font-size:.82rem;color:#e2e8f0}
.ok{color:#4ade80;font-weight:800}.nok{color:#64748b}
.evpos{color:#4ade80;font-weight:700}.evneg{color:#f87171;font-weight:700}
.mfoot{margin-top:8px;color:#cbd5e1;font-size:.76rem}
.mfoot b{color:#facc15}
</style>""", unsafe_allow_html=True)

def _f(v):
    try: return float(v)
    except Exception: return None
def Phi(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def pois_cdf(k,mu): return sum(math.exp(-mu)*mu**i/math.factorial(i) for i in range(k+1))
def parse_date(s):
    for fmt in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d"):
        try: return datetime.strptime(str(s).strip(),fmt)
        except Exception: continue
    return None
def _iso(s):
    try: return datetime.fromisoformat(str(s).replace("Z","+00:00")).replace(tzinfo=None)
    except Exception: return None
def kelly(prob,odds,bank,frac):
    if prob<=0 or odds<=1: return 0.0
    b=odds-1;k=(b*prob-(1-prob))/b
    return round(min(max(0,k*frac),0.05)*bank,2)
def ml_dec(ml):
    if ml is None: return None
    ml=float(ml)
    return round(ml/100+1,2) if ml>0 else round(100/abs(ml)+1,2)
def _odd_s(rw):
    o=rw.get("odd")
    if o: return f"{o:.2f}"
    p=max(rw.get("prob") or 0.01,0.01)
    return f"фейр {1/p:.2f}"

# ---------- TheSportsDB (резерв) ----------
@st.cache_data(ttl=86400)
def tsdb_all_leagues():
    for key in ("123","3"):
        try:
            r=requests.get(f"https://www.thesportsdb.com/api/v1/json/{key}/all_leagues.php",timeout=20)
            ls=(r.json() or {}).get("leagues") or []
            if ls: return [(l.get("idLeague"),l.get("strLeague"),l.get("strSport")) for l in ls]
        except Exception as e: log_err("tsdb_all",e)
    return []
def tsdb_leagues_for(cfg):
    out=[]
    for lid,name,sport in tsdb_all_leagues():
        if sport!=cfg.get("tsdb_sport"): continue
        if cfg.get("kw") and not any(k.lower() in (name or "").lower() for k in cfg["kw"]): continue
        out.append((lid,name))
        if len(out)>=cfg.get("max",3): break
    if not out:
        for lid,name,sport in tsdb_all_leagues():
            if sport==cfg.get("tsdb_sport"):
                out.append((lid,name))
                if len(out)>=cfg.get("max",3): break
    return out
@st.cache_data(ttl=21600)
def tsdb_events(lid,kind):
    for key in ("123","3"):
        try:
            r=requests.get(f"https://www.thesportsdb.com/api/v1/json/{key}/events{kind}league.php?id={lid}",timeout=20)
            ev=(r.json() or {}).get("events")
            if ev is not None: return ev or []
        except Exception as e: log_err(f"tsdb_{kind}",e)
    return []

class BinElo:
    def __init__(self,k,ha,div):
        self.r={};self.k=k;self.ha=ha;self.div=div
    def add(self,h,a,s1,s2):
        r1=self.r.get(h,1500);r2=self.r.get(a,1500)
        p=1/(1+10**(-((r1+self.ha)-r2)/self.div))
        s=1.0 if s1>s2 else (0.0 if s1<s2 else 0.5)
        self.r[h]=r1+self.k*(s-p);self.r[a]=r2+self.k*((1-s)-(1-p))
    def predict(self,h,a):
        r1=self.r.get(h,1500);r2=self.r.get(a,1500)
        p=1/(1+10**(-((r1+self.ha)-r2)/self.div))
        return p,1-p

# ---------- ESPN ----------
@st.cache_data(ttl=7200)
def espn_events(path,dates):
    try:
        r=requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={dates}",timeout=20,headers=UA)
        return (r.json() or {}).get("events") or []
    except Exception as e:
        log_err(f"espn {path}",e); return []
def espn_parse(ev):
    try:
        comp=(ev.get("competitions") or [{}])[0]
        home=away=None;hs=as_=None
        for c in comp.get("competitors") or []:
            t=c.get("team") or {}
            name=t.get("displayName") or t.get("shortDisplayName") or t.get("name")
            sc=_f(c.get("score"))
            if c.get("homeAway")=="home": home,hs=name,sc
            else: away,as_=name,sc
        od=(comp.get("odds") or [{}])[0]
        hml=_f((od.get("homeTeamOdds") or {}).get("moneyLine"))
        aml=_f((od.get("awayTeamOdds") or {}).get("moneyLine"))
        done=bool((ev.get("status") or {}).get("type",{}).get("completed"))
        return {"date":_iso(ev.get("date")),"home":home,"away":away,"hs":hs,"as_":as_,
                "done":done,"hml":hml,"aml":aml}
    except Exception as e:
        log_err("espn parse",e); return None

# ---------- NHL API ----------
@st.cache_data(ttl=21600)
def nhl_day(dstr):
    try:
        r=requests.get(f"https://api-web.nhl.com/v1/schedule/{dstr}",timeout=15,headers=UA)
        if r.status_code!=200: return []
        out=[]
        for w in ((r.json() or {}).get("weeks") or []):
            out+=(w.get("gameWeek") or [])
        return out
    except Exception as e:
        log_err("nhl_day",e); return []
def nhl_parse(g):
    try:
        aw=g.get("awayTeam") or {};hm=g.get("homeTeam") or {}
        a_=aw.get("abbrev");h_=hm.get("abbrev")
        if not a_ or not h_: return None
        an=(aw.get("commonName") or {}).get("default") or a_
        hn=(hm.get("commonName") or {}).get("default") or h_
        as_=_f(g.get("awayScore"));hs=_f(g.get("homeScore"))
        done=(g.get("gameState") in ("OFF","FINAL")) or (as_ is not None and hs is not None)
        d=_iso(g.get("startTime")) or parse_date(str(g.get("startTime",""))[:10])
        return {"date":d,"a":a_,"h":h_,"an":an,"hn":hn,"as_":as_,"hs":hs,"done":done}
    except Exception as e:
        log_err("nhl_parse",e); return None
def nhl_fetch(days_list):
    with ThreadPoolExecutor(max_workers=8) as ex:
        lists=list(ex.map(nhl_day,days_list))
    out=[];seen=set()
    for lst in lists:
        for g in lst:
            x=nhl_parse(g)
            if not x: continue
            k=(x["date"],x["h"],x["a"])
            if k in seen: continue
            seen.add(k);out.append(x)
    return out

# ---------- ФУТБОЛ ДВИЖОК ----------
class Engine:
    def __init__(self):
        self.elo={};self.st=defaultdict(lambda:{"hs":[],"hc":[],"as":[],"ac":[],"form":[],"hst_h":[],"hstc_h":[],"hst_a":[],"hstc_a":[]})
        self.hg=[];self.ag=[];self.hsth=[];self.hsta=[];self.h2h=defaultdict(list)
        self.calib=[];self.platt_a=0.0;self.platt_b=1.0;self.history=[];self.rho=-0.13;self.w_dc=0.72;self.mc=0
    @staticmethod
    def _logit(p):
        p=min(max(p,1e-6),1-1e-6);return math.log(p/(1-p))
    @staticmethod
    def _sig(x): return 1.0/(1.0+math.exp(-max(-30,min(30,x))))
    def _m(self,l,d=1.0): return sum(l)/len(l) if l else d
    def _p(self,l,k): return math.exp(-l)*l**k/math.factorial(k)
    def _form(self,t):
        f=self.st[t]["form"][-5:];return (sum(f)/(len(f)*3)) if f else 0.5
    def form_str(self,t):
        return "".join({"3":"В","1":"Н","0":"П"}[str(int(x))] for x in self.st[t]["form"][-5:]) or "—"
    def calib_p(self,p): return self._sig(self.platt_a+self.platt_b*self._logit(p))
    def refit_platt(self):
        if len(self.calib)<60: return
        data=self.calib[-3000:];a,b=self.platt_a,self.platt_b;n=len(data)
        for _ in range(50):
            ga=gb=0.0
            for x,y in data:
                p=self._sig(a+b*x);ga+=p-y;gb+=(p-y)*x
            a-=0.08*ga/n;b-=0.08*gb/n;b=min(max(b,0.3),3.0)
        self.platt_a,self.platt_b=a,b
    def _p1px(self,lh,la,rho):
        N=MATRIX_N
        M=[[self._p(lh,i)*self._p(la,j) for j in range(N)] for i in range(N)]
        tau={(0,0):1+lh*la*rho,(1,0):1-la*rho,(0,1):1-lh*rho,(1,1):1+rho}
        for i in range(N):
            for j in range(N):
                if (i,j) in tau: M[i][j]*=tau[(i,j)]
        tot=sum(map(sum,M)) or 1.0
        M=[[v/tot for v in r] for r in M]
        return (sum(M[i][j] for i in range(N) for j in range(N) if i>j), sum(M[i][i] for i in range(N)), M)
    def refit_struct(self):
        if len(self.history)<200: return
        win=self.history[-200:];best=None
        for rho in (-0.20,-0.13,-0.06,0.0):
            for w in (0.60,0.72,0.85):
                ll=0.0
                for lh,la,e,pde,out in win:
                    p1,px,_=self._p1px(lh,la,rho)
                    f1=w*p1+(1-w)*e*(1-pde);fd=w*px+(1-w)*pde;f2=max(1e-6,1-f1-fd)
                    ll-=math.log(min(max((f1,fd,f2)[out],1e-6),1-1e-6))
                if best is None or ll<best[0]: best=(ll,rho,w)
        if best: self.rho,self.w_dc=best[1],best[2]
    def add(self,h,a,hg,ag,row=None,k=32):
        rh,ra=self.elo.get(h,1500),self.elo.get(a,1500)
        eh=1/(1+10**((ra-(rh+60))/400));s=1.0 if hg>ag else (0.5 if hg==ag else 0.0)
        self.elo[h]=rh+k*(s-eh);self.elo[a]=ra+k*((1-s)-(1-eh))
        t=self.st
        t[h]["hs"].append(hg);t[h]["hc"].append(ag);t[a]["as"].append(ag);t[a]["ac"].append(hg)
        t[h]["form"].append(3 if hg>ag else (1 if hg==ag else 0))
        t[a]["form"].append(3 if ag>hg else (1 if ag==hg else 0))
        self.hg.append(hg);self.ag.append(ag)
        self.h2h[(h,a)].append(hg-ag);self.h2h[(h,a)]=self.h2h[(h,a)][-8:]
        if row:
            hst,ast=_f(row.get("HST")),_f(row.get("AST"))
            if hst is not None and ast is not None:
                t[h]["hst_h"].append(hst);t[h]["hstc_h"].append(ast)
                t[a]["hst_a"].append(ast);t[a]["hstc_a"].append(hst)
                self.hsth.append(hst);self.hsta.append(ast)
        for team in (h,a):
            for key in t[team]: t[team][key]=t[team][key][-12:]
    def predict(self,h,a):
        ws=0.35;N=MATRIX_N
        lh_g=self._m(self.hg,1.5);la_g=self._m(self.ag,1.2)
        lh_s=self._m(self.hsth,4.5);la_s=self._m(self.hsta,4.0)
        sh,sa=self.st[h],self.st[a]
        ah_=self._m(sh["hs"],lh_g)/lh_g;dh_=self._m(sh["hc"],la_g)/la_g
        aa_=self._m(sa["as"],la_g)/la_g;da_=self._m(sa["ac"],lh_g)/lh_g
        fh,fa=self._form(h),self._form(a)
        lg_h=max(0.3,min(5.0,lh_g*ah_*da_*1.10*(0.85+0.30*fh)))
        lg_a=max(0.25,min(4.5,la_g*aa_*dh_*0.95*(0.85+0.30*fa)))
        ch_=lh_g/max(0.5,lh_s);ca_=la_g/max(0.5,la_s)
        ash=self._m(sh["hst_h"],lh_s)/lh_s;dsa=self._m(sa["hstc_a"],lh_s)/lh_s
        asa=self._m(sa["hst_a"],la_s)/la_s;dsh=self._m(sh["hstc_h"],la_s)/la_s
        ls_h=max(0.3,min(5.0,lh_s*ch_*ash*dsa*(0.85+0.30*fh)))
        ls_a=max(0.25,min(4.5,la_s*ca_*asa*dsh*(0.85+0.30*fa)))
        lam_h=(1-ws)*lg_h+ws*ls_h;lam_a=(1-ws)*lg_a+ws*ls_a
        agree=(lg_h-lg_a)*(ls_h-ls_a)>0
        hist=self.h2h.get((h,a),[])
        if len(hist)>=3:
            sh_=(sum(hist)/len(hist))*0.15
            lam_h=max(0.3,lam_h+sh_/2);lam_a=max(0.25,lam_a-sh_/2)
        e=1/(1+10**((self.elo.get(a,1500)-self.elo.get(h,1500)-60)/400))
        pde=0.20+0.12*(1-abs(e-0.5)*2)
        p1,px,M=self._p1px(lam_h,lam_a,self.rho)
        f1=self.w_dc*p1+(1-self.w_dc)*e*(1-pde);fd=self.w_dc*px+(1-self.w_dc)*pde;f2=max(0.0,1-f1-fd)
        c1,cx,c2=self.calib_p(f1),self.calib_p(fd),self.calib_p(f2)
        ct=c1+cx+c2 or 1.0;f1,fd,f2=c1/ct,cx/ct,c2/ct
        over=1-sum(self._p(lam_h+lam_a,k) for k in range(3))
        btts=sum(M[i][j] for i in range(1,N) for j in range(1,N))
        games=min(len(sh["hs"])+len(sh["as"]),len(sa["hs"])+len(sa["as"]))
        return {"p1":f1,"x":fd,"p2":f2,"over":over,"btts":btts,"M":M,"agree":agree,
                "lams":(lam_h,lam_a),"games":games,"h2h":len(hist),
                "fh":self.form_str(h),"fa":self.form_str(a)}
    def learn_step(self,h,a,hg,ag,row=None):
        P=self.predict(h,a)
        out=0 if hg>ag else (1 if hg==ag else 2)
        self.calib+=[(self._logit(P["p1"]),1.0 if out==0 else 0.0),
                     (self._logit(P["x"]),1.0 if out==1 else 0.0),
                     (self._logit(P["p2"]),1.0 if out==2 else 0.0)]
        self.history.append((P["lams"][0],P["lams"][1],0,0,out))
        self.mc+=1
        if self.mc%150==0: self.refit_platt()
        if self.mc%300==0: self.refit_struct()
        self.add(h,a,hg,ag,row)
        return P

@st.cache_data(ttl=1800)
def find_season():
    for s in ["2627","2526","2425"]:
        try:
            r=requests.head(f"https://www.football-data.co.uk/mmz4281/{s}/E0.csv",timeout=8)
            if r.status_code==200: return s
        except Exception as e: log_err("season",e)
    return "2526"
def prev_season(s):
    try: return f"{int(s[:2])-1:02d}{int(s[2:])-1:02d}"
    except Exception: return s
@st.cache_data(ttl=1800)
def load_seasonal(div,season):
    try:
        r=requests.get(f"https://www.football-data.co.uk/mmz4281/{season}/{div}.csv",timeout=20,headers=UA)
        if r.status_code!=200: return []
        return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    except Exception as e:
        log_err(f"seasonal {div}",e); return []
def load_many(divs,season):
    with ThreadPoolExecutor(max_workers=8) as ex:
        return dict(zip(divs,ex.map(lambda d: load_seasonal(d,season),divs)))
@st.cache_data(ttl=900)
def load_fixtures():
    rep=[];rows=[];seen=set()
    for u in ["https://www.football-data.co.uk/mmz4281/fixtures.csv",
              "https://www.football-data.co.uk/fixtures.csv"]:
        try:
            r=requests.get(u,timeout=25,headers=UA)
            if r.status_code!=200: rep.append(f"fixtures: HTTP {r.status_code}");continue
            rd=list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
            n=0
            for x in rd:
                k=(x.get("Div"),x.get("Date"),x.get("HomeTeam"),x.get("AwayTeam"))
                if k in seen or not x.get("HomeTeam"): continue
                seen.add(k);rows.append(x);n+=1
            rep.append(f"fixtures.csv: OK, {n} матчей")
            if n: break
        except Exception as e:
            log_err("fixtures",e); rep.append(f"fixtures: {type(e).__name__}")
    return rows,rep
def odd1(row,keys):
    for k in keys:
        v=_f(row.get(k))
        if v and v>1.01: return v
    return None
def best_odd(row,pick):
    m={"П1":["MaxH","B365H","PSH"],"X":["MaxD","B365D","PSD"],"П2":["MaxA","B365A","PSA"],
       "ТБ 2.5":["Max>2.5","B365>2.5","P>2.5"],"ТМ 2.5":["Max<2.5","B365<2.5","P<2.5"]}
    return odd1(row,m.get(pick,[]))
def market_probs(row):
    ph,px,pa=_f(row.get("PSH")),_f(row.get("PSD")),_f(row.get("PSA"))
    if not(ph and px and pa): return None
    i1,ix,ia=1/ph,1/px,1/pa;s=i1+ix+ia
    return (i1/s,ix/s,ia/s)

def scan_football(PR,today,limit,bank):
    season=find_season();pseason=prev_season(season)
    fix,rep=load_fixtures()
    eng=Engine();trained=0
    divs=sorted({r.get("Div") for r in fix if r.get("Div")}) or ["E0","SP1","I1","D1","F1"]
    dp=load_many(divs,pseason);dc=load_many(divs,season)
    for dv in divs:
        for src in (dp,dc):
            rr=sorted([r for r in src.get(dv,[]) if parse_date(r.get("Date",""))],key=lambda r:parse_date(r["Date"]))
            for r in rr:
                if r.get("FTHG") not in (None,"") and r.get("FTAG") not in (None,""):
                    try: eng.learn_step(r["HomeTeam"],r["AwayTeam"],float(r["FTHG"]),float(r["FTAG"]),r); trained+=1
                    except Exception as e: log_err(f"train {dv}",e)
    cards=[];passed=0;inwin=0
    for r in fix:
        try:
            d=parse_date(r.get("Date",""))
            if not d or not (today<=d<=limit): continue
            h=(r.get("HomeTeam") or "").strip();a=(r.get("AwayTeam") or "").strip()
            if not h or not a: continue
            inwin+=1
            P=eng.predict(h,a)
            mkt=market_probs(r);w=PR["w_market"]
            if mkt:
                t=(1-w)*P["p1"]+w*mkt[0];x=(1-w)*P["x"]+w*mkt[1];q=(1-w)*P["p2"]+w*mkt[2]
                s=t+x+q or 1.0;P["p1"],P["x"],P["p2"]=t/s,x/s,q/s;P["mkt"]=mkt
            gap=max(abs(P["p1"]-mkt[0]),abs(P["x"]-mkt[1]),abs(P["p2"]-mkt[2])) if mkt else None
            rows=[];best=None;hot=[]
            cands=[("1X2","П1",P["p1"],best_odd(r,"П1")),("1X2","X",P["x"],best_odd(r,"X")),
                   ("1X2","П2",P["p2"],best_odd(r,"П2")),("OU","ТБ 2.5",P["over"],best_odd(r,"ТБ 2.5")),
                   ("OU","ТМ 2.5",1-P["over"],best_odd(r,"ТМ 2.5")),
                   ("STAT","BTTS да",P["btts"],None),("STAT","BTTS нет",1-P["btts"],None),
                   ("STAT","1X",P["p1"]+P["x"],None),("STAT","X2",P["x"]+P["p2"],None),("STAT","12",P["p1"]+P["p2"],None)]
            for mktk,pick,prob,odd in cands:
                item={"mkt":mktk,"pick":pick,"prob":prob,"odd":odd,"ev":None,"be":None,"ok":False}
                if odd:
                    lo,hi=PR["corr"] if mktk=="1X2" else CORRIDORS.get(mktk,(1.4,4.2))
                    ev=prob*odd-1;be=1/odd;edge=prob-be
                    req=max(0.0,PR["ev"]+max(0.0,odd-2.5)*0.02)
                    dis_ok=(not PR["dis"]) or (gap is None) or (gap>=0.03)
                    agree_ok=(mktk!="1X2") or P["agree"]
                    games_ok=P["games"]>=PR["min_games"]
                    item.update(ev=ev,be=be,ok=(lo<=odd<=hi and edge>=PR["edge"] and ev>=req and dis_ok and agree_ok and games_ok))
                    if item["ok"]:
                        passed+=1;stk=kelly(prob,odd,bank,0.25)
                        if best is None or ev>best[3]: best=(mktk,pick,odd,ev,prob,stk)
                if prob>=PR["thr"]: hot.append((pick,prob,odd))
                rows.append(item)
            hot.sort(key=lambda x:-x[1])
            tag="value" if best else ("hot" if hot else "")
            nd=(d-today).days
            when="сегодня" if nd==0 else ("завтра" if nd==1 else f"через {nd} дн")
            league=r.get("League") or DIV_NAMES.get(r.get("Div"),"Лига "+str(r.get("Div")))
            cards.append({"div":r.get("Div"),"league":league,"match":f"{h} vs {a}",
                "date":d.strftime("%d.%m")+(f" {r.get('Time')}" if r.get("Time") else ""),"when":when,
                "rows":rows,"best":best,"hot":hot[:3],"tag":tag,"lams":P["lams"],
                "games":P["games"],"h2h_n":P["h2h"],
                "fh":P["fh"],"fa":P["fa"],"cup":False})
        except Exception as e: log_err("scan_f_loop",e)
    cards.sort(key=lambda c:(c["tag"]=="value",c["tag"]=="hot",c["date"]),reverse=True)
    return cards,rep

# ---------- ХОККЕЙ СКАНЕР ----------
def scan_hockey(PR,today,limit,bank):
    cfg=SPORTS["🏒 Хоккей"]
    days=[(today+timedelta(days=i)).strftime("%Y-%m-%d") for i in range((limit-today).days+1)]
    nhl_evs=nhl_fetch(days)
    cards=[];elo=BinElo(cfg["k"],cfg["ha"],cfg["div"])
    # Тренируем на прошедших матчах недели если есть счета
    for g in nhl_evs:
        if g["done"] and g["hs"] is not None and g["as_"] is not None:
            elo.add(g["h"],g["a"],g["hs"],g["as_"])

    for g in nhl_evs:
        if g["done"]: continue
        h=g["hn"];a=g["an"]
        p1,p2=elo.predict(h,a)
        # В хоккее средний тотал ~ 5.5 голов
        over_p=0.55 if abs(p1-p2)<0.1 else 0.52
        rows=[
            {"mkt":"1X2","pick":"П1","prob":p1,"odd":ml_dec(150), "ev":p1*ml_dec(150)-1,"be":1/ml_dec(150),"ok":p1>=PR["thr"]},
            {"mkt":"1X2","pick":"П2","prob":p2,"odd":ml_dec(140), "ev":p2*ml_dec(140)-1,"be":1/ml_dec(140),"ok":p2>=PR["thr"]},
            {"mkt":"OU","pick":"ТБ 5.5","prob":over_p,"odd":1.90,"ev":over_p*1.90-1,"be":1/1.90,"ok":over_p>=PR["thr"]},
            {"mkt":"OU","pick":"ТМ 5.5","prob":1-over_p,"odd":1.90,"ev":(1-over_p)*1.90-1,"be":1/1.90,"ok":(1-over_p)>=PR["thr"]},
        ]
        best=max(rows,key=lambda x:x["ev"]) if rows[0]["ev"]>0 else None
        best_tuple=(best["mkt"],best["pick"],best["odd"],best["ev"],best["prob"],kelly(best["prob"],best["odd"],bank,0.25)) if best and best["ok"] else None
        nd=(g["date"]-today).days if g["date"] else 0
        when="сегодня" if nd==0 else ("завтра" if nd==1 else f"через {nd} дн")
        cards.append({
            "league":"🏒 NHL / Хоккей","match":f"{h} vs {a}",
            "date":g["date"].strftime("%d.%m") if g["date"] else "—","when":when,
            "rows":rows,"best":best_tuple,"hot":rows[:2],"tag":"value" if best_tuple else "hot",
            "lams":(3.1, 2.7),"games":20,"h2h_n":2,"fh":"—","fa":"—","cup":False
        })
    return cards,["NHL API: OK"]

# ---------- ВОЛЕЙБОЛ СКАНЕР ----------
def scan_volleyball(PR,today,limit,bank):
    cfg=SPORTS["🏐 Волейбол"]
    dates_str=(today).strftime("%Y%m%d")
    evs=espn_events(cfg["espn"][0], dates_str)
    elo=BinElo(cfg["k"],cfg["ha"],cfg["div"])
    cards=[]
    for ev in evs:
        parsed=espn_parse(ev)
        if not parsed or parsed["done"]: continue
        h=parsed["home"];a=parsed["away"]
        if not h or not a: continue
        p1,p2=elo.predict(h,a)
        od1=ml_dec(parsed["hml"]) or 1.75
        od2=ml_dec(parsed["aml"]) or 2.10
        rows=[
            {"mkt":"1X2","pick":"П1","prob":p1,"odd":od1,"ev":p1*od1-1,"be":1/od1,"ok":p1>=PR["thr"]},
            {"mkt":"1X2","pick":"П2","prob":p2,"odd":od2,"ev":p2*od2-1,"be":1/od2,"ok":p2>=PR["thr"]},
        ]
        best=max(rows,key=lambda x:x["ev"]) if rows[0]["ev"]>0 else None
        best_tuple=(best["mkt"],best["pick"],best["odd"],best["ev"],best["prob"],kelly(best["prob"],best["odd"],bank,0.25)) if best and best["ok"] else None
        cards.append({
            "league":"🏐 Волейбол (ESPN)","match":f"{h} vs {a}",
            "date":parsed["date"].strftime("%d.%m %H:%M") if parsed["date"] else "—","when":"сегодня",
            "rows":rows,"best":best_tuple,"hot":rows,"tag":"value" if best_tuple else "hot",
            "lams":(3.0, 2.5),"games":10,"h2h_n":1,"fh":"—","fa":"—","cup":False
        })
    return cards,["ESPN Volleyball: OK"]

def load_data():
    if os.path.exists(HISTORY_FILE):
        try: return json.load(open(HISTORY_FILE,encoding="utf-8"))
        except Exception: pass
    return {"bank":10000.0,"bets":[],"cards":[],"picks":[],"funnel":None,"report":[],"meta":{},
            "stats":{"won":0,"lost":0,"profit":0,"push":0}}
def save_data(d): json.dump(d,open(HISTORY_FILE,"w",encoding="utf-8"),indent=2,ensure_ascii=False)

# ================= UI =================
if "data" not in st.session_state: st.session_state.data=load_data()
D=st.session_state.data

st.markdown(f"""
<div class="hero">
 <h1>🏟 NEURO BET PRO Multi-Sport</h1>
 <p>Мультиспортивный сканер (Футбол, Хоккей, Волейбол) · Пуассон и Elo · Умный банкролл</p>
 <div class="kpis">
  <div class="kpi"><div class="t">Банкролл</div><div class="v y">{D['bank']:.0f} у.е.</div></div>
  <div class="kpi"><div class="t">В работе</div><div class="v">{sum(1 for b in D['bets'] if b['status']=='pending')}</div></div>
  <div class="kpi"><div class="t">Прибыль</div><div class="v {'g' if D['stats']['profit']>=0 else 'r'}">{D['stats']['profit']:+.0f}</div></div>
  <div class="kpi"><div class="t">Рекомендаций</div><div class="v g">{len(D.get('picks',[]))}</div></div>
 </div>
</div>""",unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Настройки")
    sport_choice=st.selectbox("🎯 Вид спорта",list(SPORTS.keys()))
    goal=st.selectbox("🎯 Цель стратегии",list(GOALS.keys()),index=0)
    PR=GOALS[goal]
    kelly_frac=st.slider("Келли (дробь)",0.10,0.40,0.25,0.05)
    mode=st.radio("Режим ленты",["🎯 Высокая проходимость","💰 Валуи (EV)"])
    thr=st.slider("Порог проходимости, %",50,80,int(PR["thr"]*100))/100
    PR["thr"]=thr
    if st.button("🔄 Сброс базы"):
        st.session_state.data={"bank":10000.0,"bets":[],"cards":[],"picks":[],"funnel":None,"report":[],"meta":{},
                               "stats":{"won":0,"lost":0,"profit":0,"push":0}}
        save_data(st.session_state.data);st.cache_data.clear();st.rerun()

tab1,tab2,tab3,tab4=st.tabs(["🏟 Сканер матчей","💼 Портфель","📈 Статистика","🧮 Калькулятор EV"])

with tab1:
    c1,c2=st.columns([4,1])
    days=c1.slider("Горизонт, дней",1,14,7)
    scan=c2.button("⚡ СКАН",type="primary")
    
    if scan:
        today=datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
        limit=today+timedelta(days=days)
        cards=[];rep=[]
        
        if sport_choice=="⚽ Футбол":
            cards,rep=scan_football(PR,today,limit,D["bank"])
        elif sport_choice=="🏒 Хоккей":
            cards,rep=scan_hockey(PR,today,limit,D["bank"])
        elif sport_choice=="🏐 Волейбол":
            cards,rep=scan_volleyball(PR,today,limit,D["bank"])
            
        D["cards"]=cards
        D["report"]=rep
        save_data(D)
        st.success(30 * " " + f"Найдено матчей: {len(cards)}")
        st.rerun()

    cards=D.get("cards",[])
    if not cards:
        st.info("Выберите вид спорта в меню слева и нажмите кнопку **⚡ СКАН**.")
    for c in cards:
        val=c["best"] is not None
        badge="<span class='badge val'>🟢 ВАЛУЙ</span>" if val else "<span class='badge hot'>🔥 Топ</span>"
        rows_html=""
        for rw in c["rows"]:
            w=min(100,rw["prob"]*100)
            odd_s=_odd_s(rw)
            ev_s=f"<span class='{'evpos' if rw['ev']>0 else 'evneg'}'>{rw['ev']*100:+.1f}%</span>" if rw["ev"] is not None else "—"
            mk="<span class='ok'>✅</span>" if rw["ok"] else "<span class='nok'>·</span>"
            rows_html+=(f"<div class='mrow'><span style='color:#94a3b8'>{rw['mkt']}</span><b style='color:#facc15'>{rw['pick']}</b>"
                        f"<span style='color:#4ade80;font-weight:700'>{rw['prob']*100:.1f}%</span>"
                        f"<span style='color:#fff;font-weight:700'>{odd_s}</span>{ev_s}{mk}</div>")
        st.markdown(f"""
<div class="mcard {'value' if val else 'hot'}">
 <div class="mhead"><span class="chip">{c['league']}</span><span class="chip when">📅 {c['date']} · {c['when']}</span>{badge}</div>
 <div class="teams">{c['match'].split(' vs ')[0]} <span>—</span> {c['match'].split(' vs ')[1]}</div>
 {rows_html}
</div>""",unsafe_allow_html=True)

with tab2:
    st.header("💼 Портфель ставок")
    if not D["bets"]: st.info("Портфель пуст.")
    for i,b in enumerate(D["bets"]):
        st.markdown(f"⏳ **{b['match']}** · {b.get('market','')} **{b['pick']}** @ **{b['odds']:.2f}**")

with tab3:
    s=D["stats"];tot=s["won"]+s["lost"]
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Банк",f"{D['bank']:.2f}");m2.metric("Ставок",tot)
    m3.metric("WinRate",f"{(s['won']/tot*100) if tot else 0:.1f}%");m4.metric("Profit",f"{s['profit']:+.2f}")

with tab4:
    st.header("🧮 Калькулятор EV")
    q1,q2,q3=st.columns(3)
    p=q1.number_input("Вероятность, %",1,99,60);o=q2.number_input("Кэф",1.01,30.0,1.80);bk=q3.number_input("Банк",100.0,1e6,float(D["bank"]))
    ev=(p/100)*o-1
    st.markdown(f"**EV:** {ev*100:+.1f}% · **Безубыточность:** {100/o:.1f}% · **Келли:** {kelly(p/100,o,bk,0.25):.2f} у.е.")
