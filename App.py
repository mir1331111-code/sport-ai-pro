import streamlit as st
import requests, csv, io, json, os, math, re
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="NEURO BET PRO v7", page_icon="🏟", layout="wide")
HISTORY_FILE="neuro_bet_pro.json"
MATRIX_N=9
REFIT_PLATT_EVERY=150
REFIT_STRUCT_EVERY=300
DISAGREE_MIN=0.03
UA={"User-Agent":"Mozilla/5.0"}

DEF_LP=lambda: {"w_shots":0.35,"rho":-0.13,"w_dc":0.72}

DIV_NAMES={"E0":"🏴󠁢󠁥󠁧󠁿 АПЛ","E1":"🏴󠁢󠁮󠁿 Чемпионшип","SC0":"🏴󠁢󠁣󠁿 Шотландия",
 "D1":"🇩🇪 Бундеслига","D2":"🇩🇪 2.Бундеслига","I1":"🇮🇹 Серия A","I2":"🇮🇹 Серия B",
 "SP1":"🇪 Ла Лига","SP2":"🇪🇸 Сегунда","F1":"🇫 Лига 1","F2":"🇫🇷 Лига 2",
 "N1":"🇳🇱 Эредивизи","B1":"🇧🇪 Про-лига","P1":"🇵🇹 Примейра","T1":"🇹🇷 Суперлига",
 "G1":"🇬 Греция","R1":"🇷🇺 РПЛ","BR1":"🇧🇷 Бразилия","C1":"🏆 ЛЧ","EL":"🏆 ЛЕ","EC":"🏆 ЛК"}
TSDB_LEAGUES={"432":"🏴󠁢󠁥󠁧󠁿 АПЛ","434":"🇪 Ла Лига","435":"🇮🇹 Серия A","436":"🇩 Бундеслига",
 "437":"🇫🇷 Лига 1","448":"🏆 ЛЧ","442":"🇺🇸 MLS","439":"🇵🇹 Примейра"}
GOALS={
 "🎯 Проходимость":dict(w_market=0.65,thr=0.62,dis=False,edge=0.01,ev=0.01,corr=(1.30,2.30),min_games=10),
 "⚖️ Баланс":dict(w_market=0.40,thr=0.55,dis=True,edge=0.02,ev=0.02,corr=(1.40,4.20),min_games=8),
 "💰 Value":dict(w_market=0.20,thr=0.45,dis=True,edge=0.03,ev=0.02,corr=(1.40,4.20),min_games=6),
}
CORRIDORS={"OU":(1.50,2.80),"AH":(1.60,2.60),"STAT":(1.40,4.50)}

st.markdown("""
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
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:14px}
.kpi{background:rgba(2,6,23,.92);border:1px solid rgba(148,163,184,.28);border-radius:14px;padding:12px 16px}
.kpi .t{color:#7dd3fc;font-size:.68rem;text-transform:uppercase;letter-spacing:1.2px}
.kpi .v{font-size:1.45rem;font-weight:800;color:#fff}
.kpi .v.g{color:#4ade80}.kpi .v.y{color:#facc15}.kpi .v.r{color:#f87171}
.mcard{background:rgba(8,12,24,.96);border:1px solid rgba(148,163,184,.22);border-radius:16px;padding:16px 18px;margin-bottom:14px}
.mcard.value{border-color:rgba(16,185,129,.65);box-shadow:0 0 26px rgba(16,185,129,.18)}
.mcard.hot{border-color:rgba(250,204,21,.6);box-shadow:0 0 26px rgba(250,204,21,.15)}
.mhead{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.chip{background:rgba(56,189,248,.18);color:#bae6fd;border:1px solid rgba(56,189,248,.45);padding:3px 10px;border-radius:999px;font-size:.72rem;font-weight:700}
.chip.when{background:rgba(250,204,21,.16);color:#fde68a;border-color:rgba(250,204,21,.45)}
.chip.warn{background:rgba(248,113,113,.18);color:#fecaca;border-color:rgba(248,113,113,.5)}
.badge{margin-left:auto;padding:4px 12px;border-radius:999px;font-size:.72rem;font-weight:800}
.badge.val{background:rgba(16,185,129,.22);color:#86efac;border:1px solid rgba(16,185,129,.6)}
.badge.hot{background:rgba(250,204,21,.2);color:#fde68a;border:1px solid rgba(250,204,21,.6)}
.badge.no{background:rgba(100,116,139,.2);color:#cbd5e1;border:1px solid rgba(100,116,139,.4)}
.teams{font-size:1.3rem;font-weight:800;color:#fff;margin:10px 0 2px}
.teams span{color:#94a3b8;font-weight:400}
.verdict{background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.3);border-radius:12px;padding:10px 14px;margin:8px 0;color:#e2e8f0;font-size:.88rem}
.verdict b.y{color:#facc15}.verdict b.g{color:#4ade80}.verdict b.r{color:#f87171}
.form5{font-size:.72rem;letter-spacing:2px;margin-bottom:6px;color:#cbd5e1}
.form5 b{padding:1px 5px;border-radius:4px;margin-right:2px}
.w{background:rgba(16,185,129,.3);color:#86efac}.d{background:rgba(148,163,184,.25);color:#e2e8f0}.l{background:rgba(239,68,68,.25);color:#fca5a5}
.bar{height:6px;background:rgba(148,163,184,.2);border-radius:99px;overflow:hidden;margin-top:4px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#38bdf8,#4ade80)}
.mrow{display:grid;grid-template-columns:70px 96px 1.1fr 70px 70px 62px 74px 26px;gap:8px;align-items:center;padding:6px 0;border-top:1px solid rgba(148,163,184,.14);font-size:.82rem;color:#e2e8f0}
.mrow.hdr{color:#94a3b8;font-size:.68rem;text-transform:uppercase;border-top:none}
.ok{color:#4ade80;font-weight:800}.nok{color:#64748b;font-weight:800}
.evpos{color:#4ade80;font-weight:700}.evneg{color:#f87171;font-weight:700}
.mfoot{margin-top:10px;padding-top:10px;border-top:1px dashed rgba(148,163,184,.3);color:#cbd5e1;font-size:.78rem;display:flex;gap:16px;flex-wrap:wrap}
.mfoot b{color:#facc15}
</style>""", unsafe_allow_html=True)

ERR=[]
def log_err(tag,e):
    ERR.append(f"[{tag}] {type(e).__name__}: {e}")
    if len(ERR)>300: ERR.pop(0)

# ================= ДВИЖОК (пер-лига параметры, 2 движка λ) =================
class Engine:
    def __init__(self):
        self.elo={}
        self.st=defaultdict(lambda:{"hs":[],"hc":[],"as":[],"ac":[],"form":[],
            "cfh":[],"cah":[],"cfa":[],"caa":[],"yfh":[],"yah":[],"yfa":[],"yaa":[],
            "hst_h":[],"hstc_h":[],"hst_a":[],"hstc_a":[]})
        self.hg=[];self.ag=[];self.hsth=[];self.hsta=[]
        self.h2h=defaultdict(list)
        self.calib=[];self.platt_a=0.0;self.platt_b=1.0
        self.lp=defaultdict(DEF_LP);self.hist=defaultdict(list)
        self.match_count=0
        self.market_roi=defaultdict(lambda:{"n":0,"profit":0.0})
    @staticmethod
    def _logit(p):
        p=min(max(p,1e-6),1-1e-6);return math.log(p/(1-p))
    @staticmethod
    def _sigmoid(x): return 1.0/(1.0+math.exp(-max(-30,min(30,x))))
    def _m(self,l,d=1.0): return sum(l)/len(l) if l else d
    def _p(self,l,k): return math.exp(-l)*l**k/math.factorial(k)
    def _form(self,t):
        f=self.st[t]["form"][-5:];return (sum(f)/(len(f)*3)) if f else 0.5
    def form_str(self,t):
        return "".join({"3":"В","1":"Н","0":"П"}[str(int(x))] for x in self.st[t]["form"][-5:]) or "—"
    def calibrate(self,p): return self._sigmoid(self.platt_a+self.platt_b*self._logit(p))
    def refit_platt(self):
        if len(self.calib)<60: return
        data=self.calib[-3000:];a,b=self.platt_a,self.platt_b;n=len(data)
        for _ in range(60):
            ga=gb=0.0
            for x,y in data:
                p=self._sigmoid(a+b*x);err=p-y;ga+=err;gb+=err*x
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
        p1=sum(M[i][j] for i in range(N) for j in range(N) if i>j)
        px=sum(M[i][i] for i in range(N))
        return p1,px,M
    def _probs_from(self,lh,la,rho,w,e,pde):
        p1,px,_=self._p1px(lh,la,rho)
        f1=w*p1+(1-w)*e*(1-pde);fd=w*px+(1-w)*pde;f2=max(1e-6,1-f1-fd)
        return f1,fd,f2
    def _fit_league(self,lg):
        win=self.hist[lg][-150:]
        if len(win)<120: return
        cur=self.lp[lg];best_ws=None
        for ws in (0.20,0.35,0.50):
            ll=0.0
            for gh,ga,sh,sa,e,pde,out in win:
                lh=(1-ws)*gh+ws*sh;la=(1-ws)*ga+ws*sa
                f1,fd,f2=self._probs_from(lh,la,cur["rho"],cur["w_dc"],e,pde)
                ll-=math.log(min(max((f1,fd,f2)[out],1e-6),1-1e-6))
            if best_ws is None or ll<best_ws[0]: best_ws=(ll,ws)
        cur["w_shots"]=best_ws[1]
        data=[]
        for gh,ga,sh,sa,e,pde,out in win:
            lh=(1-best_ws[1])*gh+best_ws[1]*sh;la=(1-best_ws[1])*ga+best_ws[1]*sa
            data.append(({r:self._p1px(lh,la,r)[0:2] for r in (-0.20,-0.13,-0.06,0.0)},e,pde,out))
        best=None
        for rho in (-0.20,-0.13,-0.06,0.0):
            for w in (0.60,0.72,0.85):
                ll=0.0
                for rowm,e,pde,out in data:
                    p1,px=rowm[rho]
                    f1=w*p1+(1-w)*e*(1-pde);fd=w*px+(1-w)*pde;f2=max(1e-6,1-f1-fd)
                    ll-=math.log(min(max((f1,fd,f2)[out],1e-6),1-1e-6))
                if best is None or ll<best[0]: best=(ll,rho,w)
        cur["rho"],cur["w_dc"]=best[1],best[2]
    def record_market(self,mkt,won,odd):
        r=self.market_roi[mkt];r["n"]+=1;r["profit"]=0.9*r["profit"]+0.1*((odd-1) if won else -1)
    def market_adjust(self,mkt):
        r=self.market_roi.get(mkt)
        if not r or r["n"]<40: return 0.0
        roi=r["profit"]/r["n"];return max(-0.010,min(0.020,-roi*0.4))
    def add(self,h,a,hg,ag,row=None,k=None,match_num=None,total=None):
        if k is None:
            k=(48-32*min(1.0,match_num/total)) if (match_num is not None and total) else 32
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
            for col,t1,k1,t2,k2 in (("HC",h,"cfh",a,"caa"),("AC",a,"cfa",h,"cah"),
                                    ("HY",h,"yfh",a,"yaa"),("AY",a,"yfa",h,"yah")):
                v=_f(row.get(col))
                if v is not None: t[t1][k1].append(v);t[t2][k2].append(v)
            hst,ast=_f(row.get("HST")),_f(row.get("AST"))
            if hst is not None and ast is not None:
                t[h]["hst_h"].append(hst);t[h]["hstc_h"].append(ast)
                t[a]["hst_a"].append(ast);t[a]["hstc_a"].append(hst)
                self.hsth.append(hst);self.hsta.append(ast)
        for team in (h,a):
            for key in t[team]: t[team][key]=t[team][key][-12:]
    def h2h_adjust(self,h,a,lh,la):
        hist=self.h2h.get((h,a),[])
        if len(hist)<3: return lh,la,0
        shift=(sum(hist)/len(hist))*0.15
        return max(0.3,lh+shift/2),max(0.25,la-shift/2),len(hist)
    def predict(self,h,a,lg="G"):
        P0=self.lp[lg];ws=P0["w_shots"];N=MATRIX_N
        lh_g=self._m(self.hg,1.5);la_g=self._m(self.ag,1.2)
        lh_s=self._m(self.hsth,4.5);la_s=self._m(self.hsta,4.0)
        sh,sa=self.st[h],self.st[a]
        ah_=self._m(sh["hs"],lh_g)/lh_g;dh_=self._m(sh["hc"],la_g)/la_g
        aa_=self._m(sa["as"],la_g)/la_g;da_=self._m(sa["ac"],lh_g)/lh_g
        fh,fa=self._form(h),self._form(a)
        lam_g_h=max(0.3,min(5.0,lh_g*ah_*da_*1.10*(0.85+0.30*fh)))
        lam_g_a=max(0.25,min(4.5,la_g*aa_*dh_*0.95*(0.85+0.30*fa)))
        conv_h=lh_g/max(0.5,lh_s);conv_a=la_g/max(0.5,la_s)
        att_sh_h=self._m(sh["hst_h"],lh_s)/lh_s;def_sh_a=self._m(sa["hstc_a"],lh_s)/lh_s
        att_sh_a=self._m(sa["hst_a"],la_s)/la_s;def_sh_h=self._m(sh["hstc_h"],la_s)/la_s
        lam_s_h=max(0.3,min(5.0,lh_s*conv_h*att_sh_h*def_sh_a*(0.85+0.30*fh)))
        lam_s_a=max(0.25,min(4.5,la_s*conv_a*att_sh_a*def_sh_h*(0.85+0.30*fa)))
        lam_h=(1-ws)*lam_g_h+ws*lam_s_h;lam_a=(1-ws)*lam_g_a+ws*lam_s_a
        agree=(lam_g_h-lam_g_a)*(lam_s_h-lam_s_a)>0
        lam_h,lam_a,h2h_n=self.h2h_adjust(h,a,lam_h,lam_a)
        e=1/(1+10**((self.elo.get(a,1500)-self.elo.get(h,1500)-60)/400))
        pde=0.20+0.12*(1-abs(e-0.5)*2)
        p1,px,M=self._p1px(lam_h,lam_a,P0["rho"])
        f1=P0["w_dc"]*p1+(1-P0["w_dc"])*e*(1-pde)
        fd=P0["w_dc"]*px+(1-P0["w_dc"])*pde
        f2=max(0.0,1-f1-fd)
        c1,cx,c2=self.calibrate(f1),self.calibrate(fd),self.calibrate(f2)
        ct=c1+cx+c2 or 1.0;f1,fd,f2=c1/ct,cx/ct,c2/ct
        over=1-sum(self._p(lam_h+lam_a,k) for k in range(3))
        btts=sum(M[i][j] for i in range(1,N) for j in range(1,N))
        games=min(len(sh["hs"])+len(sh["as"]),len(sa["hs"])+len(sa["as"]))
        corners=((self._m(sh["cfh"],5)+self._m(sa["caa"],5))/2,(self._m(sa["cfa"],5)+self._m(sh["cah"],5))/2)
        yellows=((self._m(sh["yfh"],2)+self._m(sa["yaa"],2))/2,(self._m(sa["yfa"],2)+self._m(sh["yah"],2))/2)
        return {"p1":f1,"x":fd,"p2":f2,"over":over,"btts":btts,"M":M,"agree":agree,
                "lams":(lam_h,lam_a),"lams_g":(lam_g_h,lam_g_a),"lams_s":(lam_s_h,lam_s_a),
                "games":games,"corners":corners,"yellows":yellows,"h2h_n":h2h_n,"e":e,"pde":pde}
    def learn_step(self,h,a,hg,ag,row=None,lg="G",match_num=None,total=None):
        P=self.predict(h,a,lg)
        out=0 if hg>ag else (1 if hg==ag else 2)
        self.calib+=[(self._logit(P["p1"]),1.0 if out==0 else 0.0),
                     (self._logit(P["x"]),1.0 if out==1 else 0.0),
                     (self._logit(P["p2"]),1.0 if out==2 else 0.0)]
        self.hist[lg].append((P["lams_g"][0],P["lams_g"][1],P["lams_s"][0],P["lams_s"][1],P["e"],P["pde"],out))
        if row:
            for mkt,pick,prob,odd,won in [("1X2","П1",P["p1"],_f(row.get("B365H")),hg>ag),
                                          ("1X2","X",P["x"],_f(row.get("B365D")),hg==ag),
                                          ("1X2","П2",P["p2"],_f(row.get("B365A")),hg<ag),
                                          ("OU","ТБ 2.5",P["over"],_f(row.get("B365>2.5")),hg+ag>=3),
                                          ("OU","ТМ 2.5",1-P["over"],_f(row.get("B365<2.5")),hg+ag<=2)]:
                if odd and odd>1.01: self.record_market(mkt,bool(won),odd)
        self.match_count+=1
        if self.match_count%REFIT_PLATT_EVERY==0: self.refit_platt()
        if len(self.hist[lg])%REFIT_STRUCT_EVERY==0: self._fit_league(lg)
        self.add(h,a,hg,ag,row,match_num=match_num,total=total)
        return P

# ================= УТИЛИТЫ =================
def _f(v):
    try: return float(v)
    except Exception: return None
def is_cup(row):
    dv=row.get("Div","");lg=(row.get("League") or "").lower()
    return dv in ("C1","EL","EC") or any(x in lg for x in ["cup","champions","europa","conference","libertadores"])
@st.cache_data(ttl=1800)
def find_season():
    for s in ["2627","2526","2425"]:
        try:
            r=requests.head(f"https://www.football-data.co.uk/mmz4281/{s}/E0.csv",timeout=8)
            if r.status_code==200: return s
        except Exception as e: log_err("find_season",e)
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
        log_err(f"load_seasonal {div}",e); return []
def load_many(divs,season):
    with ThreadPoolExecutor(max_workers=8) as ex:
        return dict(zip(divs,ex.map(lambda d: load_seasonal(d,season),divs)))
@st.cache_data(ttl=900)
def load_fixtures():
    rep=[];rows=[];seen=set()
    for u in ["https://www.football-data.co.uk/mmz4281/fixtures.csv",
              "https://www.football-data.co.uk/fixtures.csv",
              "http://www.football-data.co.uk/mmz4281/fixtures.csv"]:
        try:
            r=requests.get(u,timeout=25,headers=UA)
            if r.status_code!=200: rep.append(f"{u.split('/')[-1]}: HTTP {r.status_code}");continue
            rd=list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
            n=0
            for x in rd:
                k=(x.get("Div"),x.get("Date"),x.get("HomeTeam"),x.get("AwayTeam"))
                if k in seen or not x.get("HomeTeam"): continue
                seen.add(k);rows.append(x);n+=1
            rep.append(f"{u.split('/')[-1]}: OK,{n}")
            if n: break
        except Exception as e:
            log_err("load_fixtures",e); rep.append(f"{u.split('/')[-1]}: {type(e).__name__}")
    return rows,rep
@st.cache_data(ttl=900)
def load_tsdb():
    rep=[];rows=[]
    for lid,name in TSDB_LEAGUES.items():
        try:
            r=requests.get(f"https://www.thesportsdb.com/api/v1/json/3/eventsnextleague.php?id={lid}",timeout=15)
            ev=(r.json() or {}).get("events") or []
            for e in ev:
                rows.append({"Div":"TSDB","League":name,"Date":e.get("dateEvent",""),
                             "Time":(e.get("strTime") or "")[:5],"HomeTeam":e.get("strHomeTeam",""),
                             "AwayTeam":e.get("strAwayTeam","")})
            rep.append(f"TSDB {name}: {len(ev)}")
        except Exception as e:
            log_err(f"tsdb {name}",e); rep.append(f"TSDB {name}: ошибка")
    return rows,rep
def parse_date(s):
    for fmt in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d"):
        try: return datetime.strptime(str(s).strip(),fmt)
        except Exception: continue
    return None
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
def clv_for(pick,odd,mkt,row):
    if not odd: return None
    if mkt:
        idx={"П1":0,"X":1,"П2":2}.get(pick)
        if idx is not None: return odd*mkt[idx]-1
    po=_f(row.get("PS>2.5")) if pick=="ТБ 2.5" else (_f(row.get("PS<2.5")) if pick=="ТМ 2.5" else None)
    ot=_f(row.get("PS<2.5")) if pick=="ТБ 2.5" else (_f(row.get("PS>2.5")) if pick=="ТМ 2.5" else None)
    if po and ot:
        i1,i2=1/po,1/ot;s=i1+i2
        return odd*(i1/s)-1
    return None
def blend_market(P,mkt,w):
    if not mkt: return P
    P=dict(P)
    P["p1"]=(1-w)*P["p1"]+w*mkt[0];P["x"]=(1-w)*P["x"]+w*mkt[1];P["p2"]=(1-w)*P["p2"]+w*mkt[2]
    t=P["p1"]+P["x"]+P["p2"] or 1.0
    P["p1"]/=t;P["x"]/=t;P["p2"]/=t;P["mkt"]=mkt
    return P
def kelly(prob,odds,bank,frac):
    if prob<=0 or odds<
