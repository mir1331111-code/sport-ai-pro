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

# ТОЛЬКО ФУТБОЛ + ВОЛЕЙБОЛ + ХОККЕЙ
SPORTS={
 "⚽ Футбол":dict(src="fd"),
 "🏐 Волейбол":dict(src="espn",espn=["volleyball/womens-college-volleyball"],tsdb_sport="Volleyball",kw=[],max=3,k=24,ha=50,div=150),
 "🏒 Хоккей":dict(src="espn",espn=["hockey/nhl","hockey/ahl"],tsdb_sport="Ice Hockey",kw=["NHL","KHL","AHL"],max=3,k=24,ha=40,div=120,tot=True,pois=True),
}
DIV_NAMES={"E0":"🏴󠁧󠁢󠁥󠁮󠁧󠁿 АПЛ","E1":"🏴󠁥󠁮󠁿 Чемпионшип","SC0":"🏴󠁢󠁳󠁣󠁴󠁿 Шотландия",
 "D1":"🇩🇪 Бундеслига","D2":"🇩🇪 2.Бундеслига","I1":"🇮🇹 Серия A","I2":"🇮🇹 Серия B",
 "SP1":"🇪🇸 Ла Лига","SP2":"🇪🇸 Сегунда","F1":"🇫🇷 Лига 1","F2":"🇫🇷 Лига 2",
 "N1":"🇳🇱 Эредивизи","B1":"🇧🇪 Про-лига","P1":"🇵🇹 Примейра","T1":"🇹🇷 Суперлига",
 "G1":"🇬 Греция","R1":"🇷 РПЛ","BR1":"🇧🇷 Бразилия","C1":"🏆 ЛЧ","EL":"🏆 ЛЕ","EC":"🏆 ЛК"}

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
.badge.hot{background:rgba(250,204,21,.2);color:#fde68a;border:1px solid rgba(250,204,21,.6)}
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

# ---------- ФУТБОЛ: ДВИЖОК И СКАН НЕ ТРОНУТЫ ----------
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
        t[a]["form"].append(3 if ag>hg else (1 if hg==ag else 0))
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
    cards=[];bets=[];passed=0;inwin=0
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
            rows=[];best=None
            for pick,prob,odd in [("П1",P["p1"],best_odd(r,"П1")),("X",P["x"],best_odd(r,"X")),
                                  ("П2",P["p2"],best_odd(r,"П2")),("ТБ 2.5",P["over"],best_odd(r,"ТБ 2.5")),
                                  ("ТМ 2.5",1-P["over"],best_odd(r,"ТМ 2.5")),
                                  ("BTTS да",P["btts"],None),("1X",P["p1"]+P["x"],None),("X2",P["x"]+P["p2"],None)]:
                it={"pick":pick,"prob":prob,"odd":odd,"ev":None,"ok":False}
                if odd:
                    ev=prob*odd-1;edge=prob-1/odd
                    dis_ok=(not PR["dis"]) or (gap is None) or (gap>=0.03)
                    agree_ok=(pick not in ("П1","X","П2")) or P["agree"]
                    it["ev"]=ev
                    it["ok"]=(1.30<=odd<=4.20 and edge>=PR["edge"] and ev>=PR["ev"] and dis_ok and agree_ok and P["games"]>=PR["min_games"])
                    if it["ok"]:
                        passed+=1
                        if best is None or ev>best[2]: best=(pick,odd,ev,prob)
                rows.append(it)
            hot=[r_ for r_ in rows if r_["prob"]>=PR["thr"]]
            tag="value" if best else ("hot" if hot else "")
            nd=(d-today).days
            cards.append({"sport":"⚽ Футбол","league":DIV_NAMES.get(r.get("Div"),r.get("Div","")),
                "match":f"{h} vs {a}","date":d.strftime("%d.%m"),"date_iso":d.strftime("%Y-%m-%d"),
                "when":"сегодня" if nd==0 else ("завтра" if nd==1 else f"через {nd} дн"),
                "rows":rows,"best":best,"tag":tag,"lams":P["lams"],"games":P["games"],
                "fh":P["fh"],"fa":P["fa"],"agree":P["agree"],"h2h":P["h2h"],
                "verdict":f"xG {P['lams'][0]:.2f}–{P['lams'][1]:.2f} · форма {P['fh']} vs {P['fa']}"
                          +("" if P["agree"] else " · ⚠️ движки не согласны")
                          +(f" · расхождение с Pinnacle {gap*100:.0f} п.п." if gap else "")})
            if best and len(bets)<25:
                stk=kelly(best[3],best[1],bank,PR["kelly"])
                if stk>0:
                    bets.append({"sport":"⚽ Футбол","div":r.get("Div"),"league":DIV_NAMES.get(r.get("Div"),""),
                        "match":f"{h} vs {a}","pick":best[0],"odds":best[1],"stake":stk,
                        "prob":best[3],"status":"pending","date_iso":d.strftime("%Y-%m-%d"),
                        "market":"1X2/OU","src":["fd",r.get("Div")]})
            elif hot and len(bets)<25:
                hp=max(hot,key=lambda r_:r_["prob"])
                bets.append({"sport":"⚽ Футбол","div":r.get("Div"),"league":DIV_NAMES.get(r.get("Div"),""),
                    "match":f"{h} vs {a}","pick":hp["pick"],"odds":hp["odd"] or round(1/hp["prob"],2),
                    "stake":round(bank*0.01,2),"prob":hp["prob"],"status":"pending",
                    "date_iso":d.strftime("%Y-%m-%d"),"market":"HOT","src":["fd",r.get("Div")]})
        except Exception as e: log_err("scan fd row",e)
    cards.sort(key=lambda c:(c["tag"]=="value",c["tag"]=="hot",c["date"]),reverse=True)
    return cards,bets,{"trained":trained,"inwin":inwin,"passed":passed},rep

def scan_sport(sport,cfg,PR,today,limit,bank):
    rep=[];cards=[];bets=[];trained=0;inwin=0;passed=0
    pf=(today-timedelta(days=60)).strftime("%Y%m%d");pt=(today-timedelta(days=1)).strftime("%Y%m%d")
    ff=today.strftime("%Y%m%d");ft=limit.strftime("%Y%m%d")
    train_ev=[];fut_ev=[];src=None
    for path in cfg.get("espn",[]):
        pe=[x for x in (espn_parse(e) for e in espn_events(path,f"{pf}-{pt}"))
            if x and x["done"] and x["hs"] is not None and x["as_"] is not None and x["home"] and x["away"]]
        fe=[x for x in (espn_parse(e) for e in espn_events(path,f"{ff}-{ft}"))
            if x and x["home"] and x["away"] and x["date"]]
        rep.append(f"ESPN {path}: история {len(pe)} · расписание {len(fe)}")
        if pe or fe:
            train_ev+=pe;fut_ev+=fe;src=["espn",path]
    if not train_ev and not fut_ev:
        for lid,lname in tsdb_leagues_for(cfg):
            past=tsdb_events(lid,"past");nxt=tsdb_events(lid,"next")
            rep.append(f"TSDB {lname}: история {len(past)} · расписание {len(nxt)}")
            pe=[];fe=[]
            for e in past:
                d=parse_date(e.get("dateEvent",""));s1,s2=_f(e.get("intHomeScore")),_f(e.get("intAwayScore"))
                if d and s1 is not None and s2 is not None:
                    pe.append({"date":d,"home":e.get("strHomeTeam"),"away":e.get("strAwayTeam"),"hs":s1,"as_":s2,"done":True,"hml":None,"aml":None})
            for e in nxt:
                d=parse_date(e.get("dateEvent",""))
                if d: fe.append({"date":d,"home":e.get("strHomeTeam"),"away":e.get("strAwayTeam"),"hs":None,"as_":None,"done":False,"hml":None,"aml":None})
            if pe or fe:
                train_ev+=pe;fut_ev+=fe;src=["tsdb",lid]
    if not train_ev and not fut_ev:
        rep.append("❌ Источники недоступны или лиги в межсезонье — смотри лог ошибок")
        return cards,bets,{"trained":0,"inwin":0,"passed":0},rep
    eng=BinElo(cfg.get("k",24),cfg.get("ha",0),cfg.get("div",150))
    totals=[]
    for x in sorted(train_ev,key=lambda z:z["date"]):
        eng.add(x["home"],x["away"],x["hs"],x["as_"]);trained+=1
        if cfg.get("tot"): totals.append(x["hs"]+x["as_"])
    mu=sum(totals)/len(totals) if totals else None
    line=math.floor(mu)+0.5 if mu else None
    if trained>0 and not fut_ev:
        rep.append("⚠️ Межсезонье: в окне дат нет запланированных матчей")
    for x in fut_ev:
        try:
            d=x["date"]
            if not d or not (today<=d<=limit): continue
            h=(x["home"] or "").strip();a=(x["away"] or "").strip()
            if not h or not a: continue
            inwin+=1
            p1,p2=eng.predict(h,a)
            hd,ad=ml_dec(x["hml"]),ml_dec(x["aml"])
            if hd and ad:
                i1,i2=1/hd,1/ad;s=i1+i2;m1,m2=i1/s,i2/s
                w=PR["w_market"]
                q1=(1-w)*p1+w*m1;q2=(1-w)*p2+w*m2;s2=q1+q2 or 1.0;p1,p2=q1/s2,q2/s2
            rows=[];best=None
            cands=[("П1",p1,hd),("П2",p2,ad)]
            if cfg.get("tot") and mu:
                over=1-pois_cdf(int(line),mu) if cfg.get("pois") else 1-Phi((line-mu)/cfg.get("sigma",12))
                cands+=[(f"ТБ {line}",over,None),(f"ТМ {line}",1-over,None)]
            for pick,prob,odd in cands:
                it={"pick":pick,"prob":prob,"odd":odd,"ev":None,"ok":False}
                if odd:
                    ev=prob*odd-1;edge=prob-1/odd
                    it["ev"]=ev
                    it["ok"]=(1.20<=odd<=4.50 and edge>=PR["edge"] and ev>=PR["ev"])
                    if it["ok"]:
                        passed+=1
                        if best is None or ev>best[2]: best=(pick,odd,ev,prob)
                elif prob>=PR["thr"]:
                    it["ok"]=True;passed+=1
                rows.append(it)
            hot=[r_ for r_ in rows if r_["prob"]>=PR["thr"]]
            tag="value" if best else ("hot" if hot else "")
            nd=(d-today).days
            cards.append({"sport":sport,"league":src[1] if src else "","match":f"{h} vs {a}",
                "date":d.strftime("%d.%m"),"date_iso":d.strftime("%Y-%m-%d"),
                "when":"сегодня" if nd==0 else ("завтра" if nd==1 else f"через {nd} дн"),
                "rows":rows,"best":best,"tag":tag,"lams":(0,0),"games":trained,
                "fh":"","fa":"","agree":True,"h2h":0,
                "verdict":f"Elo+рынок: П1 {p1*100:.0f}% / П2 {p2*100:.0f}%"
                          +(f" · тотал-му {mu:.1f}, линия {line}" if mu else "")
                          +f" · обучено на {trained} матчах"})
            if best and len(bets)<25:
                stk=kelly(best[3],best[1],bank,PR["kelly"])
                if stk>0:
                    bets.append({"sport":sport,"div":None,"league":src[1] if src else "",
                        "match":f"{h} vs {a}","pick":best[0],"odds":best[1],"stake":stk,
                        "prob":best[3],"status":"pending","date_iso":d.strftime("%Y-%m-%d"),
                        "market":"ML","src":src})
            elif hot and len(bets)<25:
                hp=max(hot,key=lambda r_:r_["prob"])
                bets.append({"sport":sport,"div":None,"league":src[1] if src else "",
                    "match":f"{h} vs {a}","pick":hp["pick"],"odds":hp["odd"] or round(1/hp["prob"],2),
                    "stake":round(bank*0.01,2),"prob":hp["prob"],"status":"pending",
                    "date_iso":d.strftime("%Y-%m-%d"),"market":"FAIR","src":src})
        except Exception as e: log_err(f"scan {sport} row",e)
    cards.sort(key=lambda c:(c["tag"]=="value",c["tag"]=="hot",c["date"]),reverse=True)
    return cards,bets,{"trained":trained,"inwin":inwin,"passed":passed},rep

# ---------- состояние ----------
def new_data():
    return {"bank":10000.0,"bets":[],"cards":{},"funnel":{},"report":{},"meta":{},
            "stats":{"won":0,"lost":0,"profit":0,"push":0}}
def normalize(D):
    if not isinstance(D,dict): return new_data()
    base=new_data()
    for k,v in base.items():
        if k not in D or D[k] is None:
            D[k]=json.loads(json.dumps(v))
    if not isinstance(D.get("cards"),dict): D["cards"]={}
    if not isinstance(D.get("funnel"),dict): D["funnel"]={}
    if not isinstance(D.get("report"),dict): D["report"]={}
    if not isinstance(D.get("bets"),list): D["bets"]=[]
    if not isinstance(D.get("stats"),dict): D["stats"]=base["stats"]
    for b in D["bets"]:
        if not isinstance(b,dict): continue
        b.setdefault("status","pending");b.setdefault("stake",0.0)
        b.setdefault("odds",1.0);b.setdefault("prob",0.0);b.setdefault("match","?")
    return D
def load_data():
    if os.path.exists(HISTORY_FILE):
        try:
            return normalize(json.load(open(HISTORY_FILE,encoding="utf-8")))
        except Exception as e: log_err("load",e)
    return new_data()
def save_data(d):
    try: json.dump(d,open(HISTORY_FILE,"w",encoding="utf-8"),indent=2,ensure_ascii=False)
    except Exception as e: log_err("save",e)
def clone(D): return json.loads(json.dumps(D))
def apply_settle(D,idx,outcome):
    D2=clone(D);b=D2["bets"][idx]
    if b["status"]!="pending": return D
    if outcome=="push":
        b["status"]="push";D2["bank"]+=b["stake"];D2["stats"]["push"]=D2["stats"].get("push",0)+1
    elif outcome=="won":
        pr=b["stake"]*(b["odds"]-1);b["status"]="won";D2["bank"]+=b["stake"]+pr
        D2["stats"]["won"]+=1;D2["stats"]["profit"]+=pr
    else:
        b["status"]="lost";D2["stats"]["lost"]+=1;D2["stats"]["profit"]-=b["stake"]
    return D2

def auto_settle(D):
    D2=clone(D);upd=0;today=date.today()
    season=find_season();cache={}
    for idx,b in enumerate(D["bets"]):
        if b["status"]!="pending": continue
        bd=parse_date(b.get("date_iso",""))
        if not bd or bd.date()>=today: continue
        src=b.get("src") or []
        kind=src[0] if src else ("fd" if b["sport"]=="⚽ Футбол" else None)
        out=None
        if kind=="fd":
            div=src[1] if len(src)>1 else b.get("div")
            if not div: continue
            if div not in cache: cache[div]=load_seasonal(div,season)
            for r in cache[div]:
                rd=parse_date(r.get("Date",""))
                if not rd or abs((rd-bd).days)>1: continue
                if r.get("HomeTeam")==b["match"].split(" vs ")[0] and r.get("AwayTeam")==b["match"].split(" vs ")[1] and r.get("FTHG") not in (None,""):
                    hg,ag=float(r["FTHG"]),float(r["FTAG"])
                    if b["pick"]=="П1": out="won" if hg>ag else "lost"
                    elif b["pick"]=="X": out="won" if hg==ag else "lost"
                    elif b["pick"]=="П2": out="won" if hg<ag else "lost"
                    elif b["pick"]=="ТБ 2.5": out="won" if hg+ag>=3 else "lost"
                    elif b["pick"]=="ТМ 2.5": out="won" if hg+ag<=2 else "lost"
                    break
        elif kind=="espn":
            path=src[1]
            for e in espn_events(path,bd.strftime("%Y%m%d")):
                x=espn_parse(e)
                if not x or not x["done"] or x["hs"] is None or x["as_"] is None: continue
                if x["home"]==b["match"].split(" vs ")[0] and x["away"]==b["match"].split(" vs ")[1]:
                    s1,s2=x["hs"],x["as_"]
                    if b["pick"]=="П1": out="won" if s1>s2 else ("push" if s1==s2 else "lost")
                    elif b["pick"]=="П2": out="won" if s2>s1 else ("push" if s1==s2 else "lost")
                    elif b["pick"].startswith("ТБ"): out="won" if s1+s2>float(b["pick"].split()[1]) else "lost"
                    elif b["pick"].startswith("ТМ"): out="won" if s1+s2<float(b["pick"].split()[1]) else "lost"
                    break
        elif kind=="tsdb":
            cfg=SPORTS.get(b["sport"])
            if cfg:
                for lid,lname in tsdb_leagues_for(cfg):
                    done=False
                    for e in tsdb_events(lid,"past"):
                        ed=parse_date(e.get("dateEvent",""))
                        if not ed or abs((ed-bd).days)>1: continue
                        if e.get("strHomeTeam")==b["match"].split(" vs ")[0] and e.get("strAwayTeam")==b["match"].split(" vs ")[1]:
                            s1,s2=_f(e.get("intHomeScore")),_f(e.get("intAwayScore"))
                            if s1 is None or s2 is None: continue
                            if b["pick"]=="П1": out="won" if s1>s2 else ("push" if s1==s2 else "lost")
                            elif b["pick"]=="П2": out="won" if s2>s1 else ("push" if s1==s2 else "lost")
                            done=True;break
                    if done: break
        if out: D2=apply_settle(D2,idx,out); upd+=1
    return D2,upd

# ---------- рендер ----------
def render_card(c,PR):
    val=c["best"] is not None; hot=c["tag"]=="hot" and not val
    badge=f"<span class='badge {'val' if val else ('hot' if hot else 'no')}'>{'🟢 ВАЛУЙ' if val else ('🔥 P≥'+str(int(PR['thr']*100))+'%' if hot else 'фон')}</span>"
    rows=""
    for rw in c["rows"]:
        ev_s=f"<span class='{'evpos' if rw['ev']>0 else 'evneg'}'>{rw['ev']*100:+.1f}%</span>" if rw["ev"] is not None else "<span style='color:#64748b'>—</span>"
        mk="<span class='ok'>✅</span>" if rw["ok"] else "<span class='nok'>·</span>"
        rows+=(f"<div class='mrow'><span style='color:#94a3b8'>{rw['pick']}</span>"
               f"<div style='height:6px;background:rgba(148,163,184,.2);border-radius:99px;overflow:hidden;margin-top:6px'>"
               f"<i style='display:block;height:100%;width:{min(100,rw['prob']*100):.0f}%;background:linear-gradient(90deg,#38bdf8,#4ade80)'></i></div>"
               f"<span style='color:#4ade80;font-weight:700'>{rw['prob']*100:.1f}%</span>"
               f"<span style='color:#fff;font-weight:700'>{rw['odd'] if rw['odd'] else '—'}</span>{ev_s}{mk}</div>")
    best_html=""
    if val:
        best_html=f"💰 Ставка: <b>{c['best'][0]}</b> @ <b>{c['best'][1]:.2f}</b> (EV {c['best'][2]*100:+.1f}%)"
    return f"""
<div class="mcard {'value' if val else ('hot' if hot else '')}">
 {badge}<span class="chip">{c['sport']} · {c['league']}</span><span class="chip when">📅 {c['date']} · {c['when']}</span>
 <div class="teams">{c['match'].split(' vs ')[0]} <span>—</span> {c['match'].split(' vs ')[1]}</div>
 <div class="verdict">🤖 {c['verdict']}</div>
 {rows}
 <div class="mfoot">📚 игр в базе: <b>{c['games']}</b>{' · '+best_html if best_html else ''}</div>
</div>"""

# ---------- блок «НА ЧТО СТАВИТЬ» (вернул из футбольной версии) ----------
def build_picks(cards,thr,bank,kf):
    picks=[]
    for c in cards:
        row=None;ptype=None
        if c["best"]:
            ok=[r for r in c["rows"] if r["ok"] and r["odd"]]
            if ok: row=max(ok,key=lambda r:r["ev"]);ptype="value"
        if row is None:
            hot=[r for r in c["rows"] if r["prob"]>=thr]
            if hot: row=max(hot,key=lambda r:r["prob"]);ptype="hot"
        if row is None: continue
        ev=row["ev"] or 0.0
        if ptype=="value":
            stars="⭐⭐⭐⭐⭐" if ev>=0.10 else ("⭐⭐⭐⭐" if ev>=0.06 else "⭐⭐⭐")
        else:
            stars="⭐⭐⭐⭐⭐" if row["prob"]>=0.70 else ("⭐⭐⭐⭐" if row["prob"]>=0.65 else "⭐⭐⭐")
        stake=kelly(row["prob"],row["odd"],bank,kf) if row["odd"] else round(bank*0.01,2)
        picks.append({"league":c["league"],"match":c["match"],"date":c["date"],"when":c["when"],
                      "pick":row["pick"],"prob":row["prob"],"odd_s":_odd_s(row),"stake":stake,
                      "stars":stars,"type":ptype,"reason":c["verdict"],
                      "score":(ev if ptype=="value" else 0)+row["prob"]})
    picks.sort(key=lambda p:(p["type"]=="value",p["score"]),reverse=True)
    return picks[:8]
def render_pick(p,i):
    cls="value" if p["type"]=="value" else "hot"
    btype="🟢 ВАЛУЙ" if p["type"]=="value" else "🔥 Проходимость"
    return f"""
<div class="mcard {cls}" style="padding:12px 16px">
 <span class="badge {'val' if p['type']=='value' else 'hot'}">{p['stars']}</span>
 <span class="chip">{p['league']}</span><span class="chip when">📅 {p['date']} · {p['when']}</span>
 <div class="teams" style="font-size:1.1rem;margin:6px 0 2px">{i}. {p['match']}</div>
 <div class="verdict">➤ Ставь: <b class="y">{p['pick']}</b> @ <b class="y">{p['odd_s']}</b> ·
  P <b class="g">{p['prob']*100:.0f}%</b> · сумма <b class="y">{p['stake']:.2f} у.е.</b> · {btype}<br>
  <span style="color:#cbd5e1">💡 {p['reason']}</span></div>
</div>"""

LEGEND="""
**🟢 ВАЛУЙ** — EV>0 против кэфа, ставка ушла в портфель · **🔥 P≥N%** — ставка по проходимости ·
**✅ в строке рынка** — прошёл все фильтры · **·** — не прошёл · **⭐** — уверенность (5⭐ = EV≥10% или P≥70%) ·
**P / EV** — вероятность модели / перевес над кэфом · **фейр X.XX** — кэфа нет, это честная цена модели ·
**⏳🔴** — ожидает / выиграла / проиграла / возврат · **📚 игр** — объём обучения по командам
"""

# ================= UI =================
if "data" not in st.session_state: st.session_state.data=normalize(load_data())
D=st.session_state.data
pend=sum(1 for b in D["bets"] if b["status"]=="pending")
st.markdown(f"""
<div class="hero">
 <h1>🏟 NEURO BET PRO Multi</h1>
 <p>Футбол (football-data, движок не тронут) · Волейбол и Хоккей (ESPN + резерв TheSportsDB) · общий банк и портфель</p>
 <div class="kpis">
  <div class="kpi"><div class="t">Банкролл</div><div class="v y">{D['bank']:.0f} у.е.</div></div>
  <div class="kpi"><div class="t">В работе</div><div class="v">{pend}</div></div>
  <div class="kpi"><div class="t">Прибыль</div><div class="v {'g' if D['stats']['profit']>=0 else 'r'}">{D['stats']['profit']:+.0f}</div></div>
  <div class="kpi"><div class="t">Ошибок</div><div class="v {'r' if ERR else 'g'}">{len(ERR)}</div></div>
 </div>
</div>""",unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Настройки")
    kelly_frac=st.slider("Келли (дробь)",0.10,0.40,0.25,0.05)
    thr=st.slider("Порог проходимости, %",50,85,60)/100
    min_edge=st.slider("Edge, п.п.",0,8,2)/100
    min_ev=st.slider("Мин. EV, %",0,10,2)/100
    use_dis=st.checkbox("Футбол: только расхождения с рынком",value=True)
    PR=dict(thr=thr,edge=min_edge,ev=min_ev/100,dis=use_dis,w_market=0.40,min_games=8,kelly=kelly_frac)
    with st.expander("📖 Легенда значков"):
        st.markdown(LEGEND)
    with st.expander("🐞 Лог ошибок"):
        if ERR:
            for line in ERR[-40:]: st.text(line)
        else: st.text("Ошибок нет.")
    if st.button("🔄 Полный сброс"):
        st.session_state.data=new_data();save_data(st.session_state.data);st.cache_data.clear();st.rerun()

tab1,tab2,tab3,tab4,tab5=st.tabs(["🛰 Сканер","💼 Портфель","📈 Статистика","🧮 Калькулятор","🧪 Бэктест"])

with tab1:
    sport=st.selectbox("Вид спорта",list(SPORTS.keys()),index=0)
    cfg=SPORTS[sport]
    c1,c2=st.columns([4,1])
    days=c1.slider("Горизонт, дней",1,21,10)
    scan_btn=c2.button(f"⚡ СКАН {sport.split()[0]}",type="primary")
    if scan_btn:
        today=datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
        limit=today+timedelta(days=days)
        with st.spinner(f"Обучение и скан: {sport}..."):
            if cfg["src"]=="fd":
                cards,new_bets,funnel,rep=scan_football(PR,today,limit,D["bank"])
            else:
                cards,new_bets,funnel,rep=scan_sport(sport,cfg,PR,today,limit,D["bank"])
        D2=normalize(clone(D))
        D2["cards"][sport]=cards;D2["funnel"][sport]=funnel;D2["report"][sport]=rep
        exist={b["match"]+"|"+b["pick"] for b in D2["bets"]}
        add=[b for b in new_bets if b["match"]+"|"+b["pick"] not in exist]
        D2["bets"]=D2["bets"]+add
        st.session_state.data=D2;save_data(D2)
        st.success(f"Матчей в окне: {funnel['inwin']} · сигналов: {funnel['passed']} · в портфель: {len(add)}")
        st.rerun()
    fn=D.get("funnel",{}).get(sport)
    if fn: st.caption(f"Обучено матчей: {fn['trained']} · в окне дат: {fn['inwin']} · сигналов: {fn['passed']}")
    with st.expander("🔌 Диагностика источников"):
        for line in D.get("report",{}).get(sport,[]): st.text(line)
    picks=build_picks(D.get("cards",{}).get(sport,[]),thr,D["bank"],kelly_frac)
    if picks:
        st.markdown("### 🎯 НА ЧТО СТАВИТЬ")
        for i,p in enumerate(picks,1):
            st.markdown(render_pick(p,i),unsafe_allow_html=True)
    for c in D.get("cards",{}).get(sport,[]):
        st.markdown(render_card(c,PR),unsafe_allow_html=True)
    if not D.get("cards",{}).get(sport):
        st.info("Нажми ⚡ СКАН. Пусто? Открой диагностику: там причина (межсезонье / источник / лог).")

with tab2:
    st.header("💼 Портфель (все виды)")
    if st.button("🔄 Автосинхронизация результатов"):
        D2,upd=auto_settle(normalize(D))
        st.session_state.data=D2;save_data(D2)
        st.success(f"Закрыто СЫГРАННЫХ: {upd}");st.rerun()
    st.caption("⚠️ Закрываются только матчи с датой < сегодня и найденным счётом. Идущие/будущие не трогаются.")
    fs=st.selectbox("Фильтр по виду",["Все"]+list(SPORTS.keys()))
    bets=[(i,b) for i,b in enumerate(D["bets"]) if fs=="Все" or b["sport"]==fs]
    if not bets: st.info("Пусто.")
    for i,b in bets:
        icon={"pending":"⏳","won":"🟢","lost":"🔴","push":"⚪"}.get(b["status"],"⏳")
        st.markdown(f"{icon} **{b['sport']} · {b['match']}** · **{b['pick']}** @ **{b['odds']:.2f}** · {b['stake']:.2f} у.е. · P={b.get('prob',0)*100:.0f}% · {b.get('date_iso','')}")
        if b["status"]=="pending":
            cc=st.columns(2)
            if cc[0].button("✅ Зашло",key=f"w{i}"):
                st.session_state.data=apply_settle(D,i,"won");save_data(st.session_state.data);st.rerun()
            if cc[1].button("❌ Мимо",key=f"l{i}"):
                st.session_state.data=apply_settle(D,i,"lost");save_data(st.session_state.data);st.rerun()

with tab3:
    st.header("📈 Статистика")
    s=D["stats"];tot=s["won"]+s["lost"]
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Банк",f"{D['bank']:.2f}");m2.metric("Ставок",tot)
    m3.metric("WinRate",f"{(s['won']/tot*100) if tot else 0:.1f}%");m4.metric("Profit",f"{s['profit']:+.2f}")
    by=defaultdict(lambda:[0,0,0.0])
    for b in D["bets"]:
        if b["status"] in ("won","lost"):
            by[b["sport"]][0]+=1
            by[b["sport"]][1]+=1 if b["status"]=="won" else 0
            by[b["sport"]][2]+= b["stake"]*(b["odds"]-1) if b["status"]=="won" else -b["stake"]
    if by:
        rows=[{"Вид":k,"Ставок":v[0],"WR":f"{v[1]/v[0]*100:.0f}%","PnL":f"{v[2]:+.1f}"} for k,v in by.items()]
        st.dataframe(rows,use_container_width=True,hide_index=True)

with tab4:
    st.header("🧮 EV-калькулятор")
    q1,q2,q3=st.columns(3)
    p=q1.number_input("Вероятность, %",1,99,60)
    o=q2.number_input("Кэф",1.01,30.0,1.80)
    bk=q3.number_input("Банк",100.0,1e6,float(D["bank"]))
    ev=(p/100)*o-1
    st.markdown(f"**EV:** {ev*100:+.1f}% · **Безубыточность:** {100/o:.1f}% · **Келли:** {kelly(p/100,o,bk,kelly_frac):.2f} у.е.")
    if ev>0.02: st.success("✅ Можно ставить")
    else: st.warning("⛔ EV мал")

with tab5:
    st.header("🧪 Бэктест (walk-forward)")
    bs=st.selectbox("Вид",list(SPORTS.keys()),key="bt")
    if st.button("▶️ Прогнать",type="primary"):
        cfg=SPORTS[bs];log=[]
        today=datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
        if cfg["src"]=="fd":
            rows_=[r for r in load_seasonal("E0",find_season()) if r.get("FTHG") not in (None,"") and parse_date(r.get("Date",""))]
            rows_.sort(key=lambda r: parse_date(r["Date"]))
            eng=Engine()
            for r in rows_:
                h,a=r["HomeTeam"],r["AwayTeam"];hg,ag=float(r["FTHG"]),float(r["FTAG"])
                P=eng.predict(h,a);o=best_odd(r,"П1")
                if o: log.append({"prob":P["p1"],"won":hg>ag})
                eng.learn_step(h,a,hg,ag,r)
        else:
            pf=(today-timedelta(days=60)).strftime("%Y%m%d");pt=(today-timedelta(days=1)).strftime("%Y%m%d")
            evs=[]
            for path in cfg.get("espn",[]):
                evs+=[x for x in (espn_parse(e) for e in espn_events(path,f"{pf}-{pt}"))
                      if x and x["done"] and x["hs"] is not None and x["as_"] is not None]
            if not evs:
                for lid,lname in tsdb_leagues_for(cfg):
                    for e in tsdb_events(lid,"past"):
                        d=parse_date(e.get("dateEvent",""));s1,s2=_f(e.get("intHomeScore")),_f(e.get("intAwayScore"))
                        if d and s1 is not None and s2 is not None:
                            evs.append({"date":d,"home":e.get("strHomeTeam"),"away":e.get("strAwayTeam"),"hs":s1,"as_":s2})
            evs.sort(key=lambda x:x["date"])
            eng=BinElo(cfg.get("k",24),cfg.get("ha",0),cfg.get("div",150))
            for x in evs:
                p1,p2=eng.predict(x["home"],x["away"])
                log.append({"prob":max(p1,p2),"won":(x["hs"]>x["as_"])==(p1>=p2)})
                eng.add(x["home"],x["away"],x["hs"],x["as_"])
        if not log: st.warning("Нет данных для бэктеста (межсезонье?).")
        else:
            n=len(log);w=sum(1 for x in log if x["won"]);avg=sum(x["prob"] for x in log)/n
            st.metric("Ставок",n)
            st.markdown(f"**WinRate:** {w/n*100:.1f}% · **Средняя предсказанная P:** {avg*100:.1f}%")
            if abs(w/n-avg)<0.05: st.success("✅ Калибровка в порядке: прогноз совпадает с фактом.")
            else: st.warning("⚠️ Калибровка смещена.")
