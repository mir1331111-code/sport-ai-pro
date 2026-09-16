import streamlit as st
import requests, csv, io, json, os, math, re
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="NEURO BET PRO v8", page_icon="🏟", layout="wide")
HISTORY_FILE="neuro_bet_pro.json"
MATRIX_N=9
REFIT_PLATT_EVERY=150
REFIT_STRUCT_EVERY=300
DISAGREE_MIN=0.03
UA={"User-Agent":"Mozilla/5.0"}

DEF_LP=lambda: {"w_shots":0.35,"rho":-0.13,"w_dc":0.72,"w_ml":0.25}
# [MODIFIED] NFEAT_ML: 6 -> 12 (добавили rest_days, shots_ratio, form_momentum, home_adv)
NFEAT_ML=12  # [bias, elo_diff/400, lam_g diff, lam_s diff, form diff, log(games+1),
             #  home_adv, log(rest_days_h+1), log(rest_days_a+1),
             #  shots_ratio_h, shots_ratio_a, form_momentum]
ML_REFIT_MIN=150
ML_WINDOW=400
ML_LR=0.05
ML_L2=0.001
ML_ITERS=300

DIV_NAMES={"E0":"🏴󠁧󠁢󠁥󠁮󠁧󠁿 АПЛ","E1":"🏴󠁧󠁢󠁥󠁮󠁧󠁿 Чемпионшип","SC0":"🏴󠁧󠁢󠁳󠁣󠁴󠁿 Шотландия",
 "D1":"🇩🇪 Бундеслига","D2":"🇩🇪 2.Бундеслига","I1":"🇮🇹 Серия A","I2":"🇮🇹 Серия B",
 "SP1":"🇪🇸 Ла Лига","SP2":"🇪🇸 Сегунда","F1":"🇫🇷 Лига 1","F2":"🇫🇷 Лига 2",
 "N1":"🇳🇱 Эредивизи","B1":"🇧🇪 Про-лига","P1":"🇵🇹 Примейра","T1":"🇹🇷 Суперлига",
 "G1":"🇬🇷 Греция","R1":"🇷🇺 РПЛ","BR1":"🇧🇷 Бразилия","C1":"🏆 ЛЧ","EL":"🏆 ЛЕ","EC":"🏆 ЛК"}
TSDB_LEAGUES={"432":"🏴󠁧󠁢󠁥󠁮󠁧󠁿 АПЛ","434":"🇪🇸 Ла Лига","435":"🇮🇹 Серия A","436":"🇩🇪 Бундеслига",
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
.betcard{background:rgba(8,12,24,.96);border:1px solid rgba(148,163,184,.22);border-left:4px solid rgba(148,163,184,.4);
 border-radius:12px;padding:10px 14px;margin-bottom:8px;font-size:.86rem;color:#e2e8f0}
.betcard.pending{border-left-color:#facc15}
.betcard.won{border-left-color:#22c55e;background:rgba(16,185,129,.08)}
.betcard.lost{border-left-color:#ef4444;background:rgba(239,68,68,.07)}
.betcard.push{border-left-color:#64748b}
.betcard .score{font-weight:900;padding:2px 9px;border-radius:8px;margin-left:6px;font-size:.9rem}
.betcard.won .score{background:rgba(34,197,94,.25);color:#86efac}
.betcard.lost .score{background:rgba(239,68,68,.25);color:#fca5a5}
.betcard.push .score{background:rgba(100,116,139,.3);color:#e2e8f0}
</style>""", unsafe_allow_html=True)

ERR=[]
def log_err(tag,e):
    ERR.append(f"[{tag}] {type(e).__name__}: {e}")
    if len(ERR)>300: ERR.pop(0)

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
        self.ml_w={};self.ml_hist=defaultdict(list)
        self.match_count=0
        self.market_roi=defaultdict(lambda:{"n":0,"profit":0.0})
        # [NEW] для расчёта rest_days
        self.last_match_date={}
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
    def _loglik(self,rows,rho,w):
        ll=0.0
        for lh,la,e,pde,out in rows:
            f1,fd,f2=self._probs_from(lh,la,rho,w,e,pde)
            ll-=math.log(min(max((f1,fd,f2)[out],1e-6),1-1e-6))
        return ll
    def _fit_league(self,lg):
        win=self.hist[lg][-400:]
        if len(win)<200: return
        split=int(len(win)*0.8)
        train,holdout=win[:split],win[split:]
        cur=self.lp[lg];best_ws=None
        for ws in (0.20,0.35,0.50):
            rows=[((1-ws)*gh+ws*sh,(1-ws)*ga+ws*sa,e,pde,out) for gh,ga,sh,sa,e,pde,out in train]
            ll=self._loglik(rows,cur["rho"],cur["w_dc"])
            if best_ws is None or ll<best_ws[0]: best_ws=(ll,ws)
        ws_pick=best_ws[1]
        train_rows=[((1-ws_pick)*gh+ws_pick*sh,(1-ws_pick)*ga+ws_pick*sa,e,pde,out) for gh,ga,sh,sa,e,pde,out in train]
        hold_rows=[((1-ws_pick)*gh+ws_pick*sh,(1-ws_pick)*ga+ws_pick*sa,e,pde,out) for gh,ga,sh,sa,e,pde,out in holdout]
        best=None
        for rho in (-0.20,-0.13,-0.06,0.0):
            for w in (0.60,0.72,0.85):
                ll=self._loglik(train_rows,rho,w)
                if best is None or ll<best[0]: best=(ll,rho,w)
        if hold_rows:
            ll_new=self._loglik(hold_rows,best[1],best[2])
            ll_old=self._loglik(hold_rows,cur["rho"],cur["w_dc"])
            if ll_new>ll_old: return
        cur["w_shots"]=ws_pick
        cur["rho"],cur["w_dc"]=best[1],best[2]
    @staticmethod
    def _softmax(scores):
        m=max(scores);exps=[math.exp(s-m) for s in scores];tot=sum(exps) or 1.0
        return tuple(v/tot for v in exps)
    def _ml_probs(self,lg,feat):
        W=self.ml_w.get(lg)
        if not W: return (1/3,1/3,1/3)
        scores=[sum(w*x for w,x in zip(W[c],feat)) for c in range(3)]
        return self._softmax(scores)
    def _ml_nll(self,W,rows):
        s=0.0
        for feat,out in rows:
            scores=[sum(w*x for w,x in zip(W[c],feat)) for c in range(3)]
            p=self._softmax(scores)[out]
            s-=math.log(min(max(p,1e-6),1-1e-6))
        return s
    def _fit_ml(self,lg):
        data=self.ml_hist[lg][-ML_WINDOW:]
        if len(data)<ML_REFIT_MIN: return
        split=int(len(data)*0.8)
        train,hold=data[:split],data[split:]
        old_W=self.ml_w.get(lg)
        W=[row[:] for row in old_W] if old_W else [[0.0]*NFEAT_ML for _ in range(3)]
        n=max(1,len(train))
        for _ in range(ML_ITERS):
            grad=[[0.0]*NFEAT_ML for _ in range(3)]
            for feat,out in train:
                scores=[sum(w*x for w,x in zip(W[c],feat)) for c in range(3)]
                probs=self._softmax(scores)
                for c in range(3):
                    err=probs[c]-(1.0 if c==out else 0.0)
                    for k in range(NFEAT_ML): grad[c][k]+=err*feat[k]
            for c in range(3):
                for k in range(NFEAT_ML):
                    W[c][k]-=ML_LR*(grad[c][k]/n+ML_L2*W[c][k])
        if hold:
            ll_new=self._ml_nll(W,hold)
            ll_old=self._ml_nll(old_W,hold) if old_W else float("inf")
            if ll_new>ll_old: return
        self.ml_w[lg]=W
    def record_market(self,mkt,won,odd):
        r=self.market_roi[mkt];r["n"]+=1;r["profit"]=0.9*r["profit"]+0.1*((odd-1) if won else -1)
    def market_adjust(self,mkt):
        r=self.market_roi.get(mkt)
        if not r or r["n"]<40: return 0.0
        roi=r["profit"]/r["n"];return max(-0.010,min(0.020,-roi*0.4))
    # [MODIFIED] добавил параметр match_date
    def add(self,h,a,hg,ag,row=None,k=None,match_num=None,total=None,match_date=None):
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
        if len(self.hg)>4000: self.hg=self.hg[-4000:]
        if len(self.ag)>4000: self.ag=self.ag[-4000:]
        if len(self.hsth)>4000: self.hsth=self.hsth[-4000:]
        if len(self.hsta)>4000: self.hsta=self.hsta[-4000:]
        # [NEW] сохраняем дату последнего матча для rest_days
        if match_date:
            self.last_match_date[h]=match_date
            self.last_match_date[a]=match_date
    def h2h_adjust(self,h,a,lh,la):
        hist=self.h2h.get((h,a),[])
        n=len(hist)
        if n<5: return lh,la,n
        shrink=min(1.0,(n-4)/6.0)
        shift=(sum(hist)/n)*0.08*shrink
        return max(0.3,lh+shift/2),max(0.25,la-shift/2),n
    def predict(self,h,a,lg="G"):
        P0=self.lp[lg];ws=P0["w_shots"];N=MATRIX_N
        lh_g=max(0.05,self._m(self.hg,1.5));la_g=max(0.05,self._m(self.ag,1.2))
        lh_s=max(0.05,self._m(self.hsth,4.5));la_s=max(0.05,self._m(self.hsta,4.0))
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
        # --- Второй движок: ML-слой с 12 фичами ---
        elo_diff=self.elo.get(h,1500)-self.elo.get(a,1500)
        games=min(len(sh["hs"])+len(sh["as"]),len(sa["hs"])+len(sa["as"]))
        # [NEW] расширенные фичи (12 вместо 6)
        home_adv=1.0
        today_ref=datetime.now()
        rest_h=(today_ref-self.last_match_date[h]).days if h in self.last_match_date else 14
        rest_a=(today_ref-self.last_match_date[a]).days if a in self.last_match_date else 14
        rest_h=max(1,min(rest_h,60))
        rest_a=max(1,min(rest_a,60))
        shots_h=len(sh["hst_h"])
        shots_ratio_h=(sum(sh["hst_h"][-5:])/max(1,sum(sh["hc"][-5:]))) if shots_h>=3 else 1.5
        shots_a=len(sa["hst_a"])
        shots_ratio_a=(sum(sa["hst_a"][-5:])/max(1,sum(sa["ac"][-5:]))) if shots_a>=3 else 1.5
        form_last3_h=sum(sh["form"][-3:])/max(1,len(sh["form"][-3:]))/3.0
        form_last5_h=fh
        form_last3_a=sum(sa["form"][-3:])/max(1,len(sa["form"][-3:]))/3.0
        form_last5_a=fa
        form_momentum=(form_last3_h-form_last5_h)-(form_last3_a-form_last5_a)
        ml_feats=[1.0, elo_diff/400.0, lam_g_h-lam_g_a, lam_s_h-lam_s_a,
                  fh-fa, math.log(games+1),
                  home_adv, math.log(rest_h+1), math.log(rest_a+1),
                  shots_ratio_h, shots_ratio_a, form_momentum]
        ml_p1,ml_x,ml_p2=self._ml_probs(lg,ml_feats)
        n_trained=len(self.ml_hist.get(lg,[]))
        w_ml=P0.get("w_ml",0.25)*min(1.0,n_trained/300.0)
        if lg in self.ml_w and w_ml>0:
            f1=(1-w_ml)*f1+w_ml*ml_p1;fd=(1-w_ml)*fd+w_ml*ml_x;f2=(1-w_ml)*f2+w_ml*ml_p2
            tt=f1+fd+f2 or 1.0;f1/=tt;fd/=tt;f2/=tt
        c1,cx,c2=self.calibrate(f1),self.calibrate(fd),self.calibrate(f2)
        ct=c1+cx+c2 or 1.0;f1,fd,f2=c1/ct,cx/ct,c2/ct
        over=1-sum(self._p(lam_h+lam_a,k) for k in range(3))
        btts=sum(M[i][j] for i in range(1,N) for j in range(1,N))
        corners=((self._m(sh["cfh"],5)+self._m(sa["caa"],5))/2,(self._m(sa["cfa"],5)+self._m(sh["cah"],5))/2)
        yellows=((self._m(sh["yfh"],2)+self._m(sa["yaa"],2))/2,(self._m(sa["yfa"],2)+self._m(sh["yah"],2))/2)
        return {"p1":f1,"x":fd,"p2":f2,"over":over,"btts":btts,"M":M,"agree":agree,
                "lams":(lam_h,lam_a),"lams_g":(lam_g_h,lam_g_a),"lams_s":(lam_s_h,lam_s_a),
                "games":games,"corners":corners,"yellows":yellows,"h2h_n":h2h_n,"e":e,"pde":pde,
                "ml_feats":ml_feats,"w_ml_eff":w_ml,
                "p1_raw":f1,"x_raw":fd,"p2_raw":f2}
    # [MODIFIED] передаём match_date в add()
    def learn_step(self,h,a,hg,ag,row=None,lg="G",match_num=None,total=None):
        P=self.predict(h,a,lg)
        out=0 if hg>ag else (1 if hg==ag else 2)
        self.calib+=[(self._logit(P["p1"]),1.0 if out==0 else 0.0),
                     (self._logit(P["x"]),1.0 if out==1 else 0.0),
                     (self._logit(P["p2"]),1.0 if out==2 else 0.0)]
        if len(self.calib)>6000: self.calib=self.calib[-6000:]
        self.hist[lg].append((P["lams_g"][0],P["lams_g"][1],P["lams_s"][0],P["lams_s"][1],P["e"],P["pde"],out))
        if len(self.hist[lg])>1200: self.hist[lg]=self.hist[lg][-1200:]
        self.ml_hist[lg].append((P["ml_feats"],out))
        if len(self.ml_hist[lg])>1200: self.ml_hist[lg]=self.ml_hist[lg][-1200:]
        if row:
            for mkt,pick,prob,odd,won in [("1X2","П1",P["p1"],_f(row.get("B365H")),hg>ag),
                                          ("1X2","X",P["x"],_f(row.get("B365D")),hg==ag),
                                          ("1X2","П2",P["p2"],_f(row.get("B365A")),hg<ag),
                                          ("OU","ТБ 2.5",P["over"],_f(row.get("B365>2.5")),hg+ag>=3),
                                          ("OU","ТМ 2.5",1-P["over"],_f(row.get("B365<2.5")),hg+ag<=2)]:
                if odd and odd>1.01: self.record_market(mkt,bool(won),odd)
        self.match_count+=1
        if self.match_count%REFIT_PLATT_EVERY==0: self.refit_platt()
        if len(self.hist[lg])%REFIT_STRUCT_EVERY==0:
            self._fit_league(lg)
            self._fit_ml(lg)
        # [NEW] извлекаем дату матча и передаём в add()
        match_date=None
        if row:
            match_date=parse_date(row.get("Date",""))
        self.add(h,a,hg,ag,row,match_num=match_num,total=total,match_date=match_date)
        return P

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
    if pick.startswith("Ф1") or pick.startswith("Ф2"):
        po=_f(row.get("PAHH")) if pick.startswith("Ф1") else _f(row.get("PAHA"))
        ot=_f(row.get("PAHA")) if pick.startswith("Ф1") else _f(row.get("PAHH"))
        if po and ot:
            i1,i2=1/po,1/ot;s=i1+i2
            return odd*(i1/s)-1
        return None
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
    if prob<=0 or odds<=1: return 0.0
    b=odds-1;k=(b*prob-(1-prob))/b
    return round(min(max(0,k*frac),0.05)*bank,2)
def settle_ah(pick,hg,ag):
    m=re.match(r"Ф([12])\(([-+]?\d+(?:\.\d+)?)\)",pick)
    if not m: return None
    side,line=int(m.group(1)),float(m.group(2))
    res=((hg-ag) if side==1 else (ag-hg))+line
    if res>0.001: return True
    if abs(res)<=0.001: return "push"
    return False

def determine_outcome(market,pick,hg,ag):
    if market=="1X2":
        return "won" if ("П1" if hg>ag else "X" if hg==ag else "П2")==pick else "lost"
    if market=="OU":
        won=(pick=="ТБ 2.5" and hg+ag>=3) or (pick=="ТМ 2.5" and hg+ag<=2)
        return "won" if won else "lost"
    if market=="AH":
        s=settle_ah(pick,hg,ag)
        return "push" if s=="push" else ("won" if s else "lost")
    return None

def find_result(div,home,away,bd):
    if div in (None,"TSDB",""): return None
    season=find_season()
    cands=[]
    for r in load_seasonal(div,season):
        if r.get("HomeTeam")==home and r.get("AwayTeam")==away and r.get("FTHG") not in (None,""):
            rd=parse_date(r.get("Date",""))
            if not rd: continue
            try: hg,ag=float(r["FTHG"]),float(r["FTAG"])
            except Exception: continue
            cands.append((rd,hg,ag))
    if not cands: return None
    if bd:
        cands=[c for c in cands if abs((c[0]-bd).days)<=2]
        if not cands: return None
        cands.sort(key=lambda c:abs((c[0]-bd).days))
    else:
        cands=[c for c in cands if c[0]<=datetime.now()]
        if not cands: return None
        cands.sort(key=lambda c:c[0],reverse=True)
    return cands[0]

def recompute_bet(D,idx,hg,ag,score_str):
    D2=clone(D);b=D2["bets"][idx]
    new_status=determine_outcome(b.get("market"),b.get("pick"),hg,ag)
    if new_status is None: return D
    old=b.get("status","pending")
    if old=="won":
        pr=b["stake"]*(b["odds"]-1);D2["bank"]-=b["stake"]+pr
        D2["stats"]["won"]=max(0,D2["stats"]["won"]-1);D2["stats"]["profit"]-=pr
    elif old=="lost":
        D2["bank"]+=b["stake"];D2["stats"]["lost"]=max(0,D2["stats"]["lost"]-1);D2["stats"]["profit"]+=b["stake"]
    elif old=="push":
        D2["bank"]-=b["stake"];D2["stats"]["push"]=max(0,D2["stats"].get("push",0)-1)
    b["status"]=new_status;b["score"]=score_str
    if new_status=="won":
        pr=b["stake"]*(b["odds"]-1);D2["bank"]+=b["stake"]+pr
        D2["stats"]["won"]+=1;D2["stats"]["profit"]+=pr
    elif new_status=="lost":
        D2["bank"]-=b["stake"];D2["stats"]["lost"]+=1;D2["stats"]["profit"]-=b["stake"]
    elif new_status=="push":
        D2["bank"]+=b["stake"];D2["stats"]["push"]=D2["stats"].get("push",0)+1
    return D2

def _norm_team(s):
    return re.sub(r"[^a-zа-я0-9]","",(s or "").lower())

@st.cache_data(ttl=60)
def load_livescores():
    try:
        r=requests.get("https://www.thesportsdb.com/api/v1/json/3/livescore.php?s=Soccer",timeout=10)
        ev=(r.json() or {}).get("events") or []
        out={}
        for e in ev:
            key=(_norm_team(e.get("strHomeTeam","")),_norm_team(e.get("strAwayTeam","")))
            out[key]={"home":e.get("intHomeScore"),"away":e.get("intAwayScore"),
                       "status":(e.get("strStatus") or "").strip(),
                       "progress":(e.get("strProgress") or "").strip()}
        return out
    except Exception as e:
        log_err("livescores",e); return {}
def match_live(live,home,away):
    if not live: return None
    hk,ak=_norm_team(home),_norm_team(away)
    for (lh,la),v in live.items():
        if (lh==hk and la==ak) or (hk in lh and ak in la) or (lh in hk and la in ak):
            return v
    return None
FINISHED_STATUSES={"match finished","ft","aet","ap","finished","full time"}

def _odd_s(rw):
    o=rw.get("odd")
    if o: return f"{o:.2f}"
    p=max(rw.get("prob") or 0.01,0.01)
    return f"фейр {1/p:.2f}"

def ai_verdict(c):
    rows=c.get("rows",[])
    scored=sorted([r for r in rows if r.get("prob")],key=lambda r:-r["prob"])
    def prep(r):
        if not r: return None
        d=dict(r);d["odd_s"]=_odd_s(d);return d
    main=prep(scored[0]) if scored else None
    alt=prep(scored[1]) if len(scored)>1 else None
    x12=[r for r in rows if r["mkt"]=="1X2"]
    avoid=prep(min(x12,key=lambda r:r["prob"])) if x12 else None
    lh,la=c.get("lams",(0,0));lg=c.get("lams_g",c.get("lams",(0,0)));ls=c.get("lams_s",c.get("lams",(0,0)))
    parts=[f"Движок голов {lg[0]:.1f}–{lg[1]:.1f}, движок ударов {ls[0]:.1f}–{ls[1]:.1f} → итог xG {lh[0] if isinstance(lh,tuple) else lh:.1f}–{lh[1] if isinstance(lh,tuple) else la:.1f}."]
    if not c.get("agree",True): parts.append("⚠️ Движки не согласны о фаворите — 1X2 пропущен.")
    if c.get("fh","—")!="—": parts.append(f"Форма {c['fh']} против {c['fa']}.")
    m=c.get("mkt");gap=None
    if m:
        gap=max(abs(c.get("p1",0)-m[0]),abs(c.get("px",c.get("x",0))-m[1]),abs(c.get("p2",0)-m[2]))
        parts.append(f"Pinnacle: П1 {m[0]*100:.0f}/X {m[1]*100:.0f}/П2 {m[2]*100:.0f}%; расхождение {gap*100:.0f} п.п. — "
                     +("модель видит alpha" if gap>=DISAGREE_MIN else "консенсус с рынком")+".")
    raw=c.get("raw")
    if raw and m:
        raw_gap=max(abs(raw[0]-m[0]),abs(raw[1]-m[1]),abs(raw[2]-m[2]))
        parts.append(f"До подмешивания рынка модель сама расходилась с Pinnacle на {raw_gap*100:.0f} п.п. "
                     "(после блендинга расхождение выше по построению, поэтому не путать с независимым edge).")
    if c.get("h2h_n",0)>=5: parts.append(f"H2H: {c['h2h_n']} встреч учтены (слабый вес).")
    if c.get("cup"): parts.append("Кубковый матч: темп ниже.")
    return main,alt,avoid," ".join(parts),gap

def stars_for(rw,thr):
    if rw["ok"]:
        ev=rw["ev"];return "⭐⭐⭐⭐⭐" if ev>=0.10 else ("⭐⭐⭐⭐" if ev>=0.06 else "⭐⭐⭐")
    if rw["prob"]>=thr:
        return "⭐⭐⭐⭐⭐" if rw["prob"]>=0.70 else ("⭐⭐⭐⭐" if rw["prob"]>=0.65 else "⭐⭐⭐")
    return ""

def build_picks(cards,thr,bank,kelly_frac):
    picks=[]
    for c in cards:
        row=None;ptype=None
        if c.get("best"):
            ok=[r for r in c["rows"] if r["ok"]]
            row=max(ok,key=lambda r:r["ev"]) if ok else None;ptype="value"
        if row is None:
            hot=[r for r in c["rows"] if r["prob"]>=thr]
            if hot: row=max(hot,key=lambda r:r["prob"]);ptype="hot"
        if row is None: continue
        main,alt,avoid,text,gap=ai_verdict(c)
        stake=kelly(row["prob"],row["odd"],bank,kelly_frac) if row["odd"] else round(bank*0.01,2)
        picks.append({"league":c["league"],"match":c["match"],"date":c["date"],"when":c["when"],
                      "pick":row["pick"],"prob":row["prob"],"odd":row["odd"],
                      "odd_s":_odd_s(row),"stake":stake,"stars":stars_for(row,thr),
                      "type":ptype,"verdict":text,"main":main,"alt":alt,"avoid":avoid,
                      "clv":c.get("clv"),
                      "score":(row["ev"] if ptype=="value" else 0)+row["prob"]})
    picks.sort(key=lambda p:(p["type"]=="value",p["score"]),reverse=True)
    return picks[:10]

def new_data():
    return {"bank":10000.0,"bets":[],"cards":[],"picks":[],"funnel":None,"report":[],"meta":{},
            "stats":{"won":0,"lost":0,"profit":0,"push":0}}
def migrate(D):
    if not isinstance(D,dict): return new_data()
    base=new_data()
    for k,v in base.items():
        if k not in D or D[k] is None: D[k]=json.loads(json.dumps(v))
    if not isinstance(D.get("cards"),list): D["cards"]=[]
    if not isinstance(D.get("picks"),list): D["picks"]=[]
    if D["cards"] and isinstance(D["cards"][0],dict) and "lams_g" not in D["cards"][0]:
        D["cards"]=[];D["picks"]=[]
    if not isinstance(D.get("bets"),list): D["bets"]=[]
    D["bets"]=[b for b in D["bets"] if isinstance(b,dict) and all(k in b for k in ("match","pick","odds","stake","status"))]
    if not isinstance(D.get("stats"),dict): D["stats"]=base["stats"]
    for s in ("won","lost","profit","push"): D["stats"].setdefault(s,0)
    if not isinstance(D.get("meta"),dict): D["meta"]={}
    if not isinstance(D.get("report"),list): D["report"]=[]
    return D
def load_data():
    if os.path.exists(HISTORY_FILE):
        try: return migrate(json.load(open(HISTORY_FILE,encoding="utf-8")))
        except Exception as e: log_err("load_data",e)
    return new_data()
def save_data(d):
    try: json.dump(d,open(HISTORY_FILE,"w",encoding="utf-8"),indent=2,ensure_ascii=False)
    except Exception as e: log_err("save_data",e)
def clone(D): return json.loads(json.dumps(D))
def apply_scan(D,cards,picks,funnel,report,meta,new_bets):
    D2=clone(D)
    D2["cards"]=cards;D2["picks"]=picks;D2["funnel"]=funnel;D2["report"]=report
    D2["meta"]=meta;D2["bets"]=D2["bets"]+new_bets
    return D2
def apply_settle(D,idx,outcome,score=None):
    D2=clone(D);b=D2["bets"][idx]
    if b["status"]!="pending": return D
    if score: b["score"]=score
    if outcome=="push":
        b["status"]="push";D2["bank"]+=b["stake"];D2["stats"]["push"]=D2["stats"].get("push",0)+1
    elif outcome=="won":
        pr=b["stake"]*(b["odds"]-1);b["status"]="won";D2["bank"]+=b["stake"]+pr
        D2["stats"]["won"]+=1;D2["stats"]["profit"]+=pr
    else:
        b["status"]="lost";D2["stats"]["lost"]+=1;D2["stats"]["profit"]-=b["stake"]
    return D2

BACKTEST_WARMUP=120

def backtest(div,season,PR,min_edge,stake_mode,use_dis=True):
    rows=[r for r in load_seasonal(div,season)
          if r.get("FTHG") not in (None,"") and r.get("FTAG") not in (None,"") and parse_date(r.get("Date",""))]
    rows.sort(key=lambda r: parse_date(r["Date"]))
    eng=Engine();log=[];bank=10000.0
    for j,r in enumerate(rows):
        h=(r.get("HomeTeam") or "").strip();a=(r.get("AwayTeam") or "").strip()
        try: hg,ag=float(r["FTHG"]),float(r["FTAG"])
        except Exception as e: log_err("backtest parse",e); continue
        try:
            P=eng.predict(h,a,div)
            mkt=market_probs(r)
            P=blend_market(P,mkt,PR["w_market"])
            gap=max(abs(P["p1"]-mkt[0]),abs(P["x"]-mkt[1]),abs(P["p2"]-mkt[2])) if mkt else None
            cands=[("1X2","П1",P["p1"],best_odd(r,"П1")),("1X2","X",P["x"],best_odd(r,"X")),
                   ("1X2","П2",P["p2"],best_odd(r,"П2")),
                   ("OU","ТБ 2.5",P["over"],best_odd(r,"ТБ 2.5")),("OU","ТМ 2.5",1-P["over"],best_odd(r,"ТМ 2.5"))]
            ahh=_f(r.get("AHh"));ohh=odd1(r,["MaxAHH","B365AHH","PAHH"]);oha=odd1(r,["MaxAHA","B365AHA","PAHA"])
            if j>=BACKTEST_WARMUP and ahh is not None and abs((ahh*2)%2)==1 and ohh and oha:
                pc=sum(P["M"][i][j2] for i in range(MATRIX_N) for j2 in range(MATRIX_N) if (i-j2+ahh)>0.001)
                cands+=[("AH",f"Ф1({ahh:+.1f})",pc,ohh),("AH",f"Ф2({-ahh:+.1f})",1-pc,oha)]
            if j>=BACKTEST_WARMUP:
                for mktk,pick,prob,o in cands:
                    if not o or not (PR["corr"][0]<=o<=PR["corr"][1] if mktk=="1X2" else CORRIDORS.get(mktk,(1.4,4.2))[0]<=o<=CORRIDORS.get(mktk,(1.4,4.2))[1]): continue
                    if mktk=="1X2" and not P["agree"]: continue
                    if use_dis and mkt and gap is not None and gap<DISAGREE_MIN: continue
                    if prob-1/o<min_edge: continue
                    won=None
                    if pick=="П1": won=hg>ag
                    elif pick=="X": won=hg==ag
                    elif pick=="П2": won=hg<ag
                    elif pick=="ТБ 2.5": won=hg+ag>=3
                    elif pick=="ТМ 2.5": won=hg+ag<=2
                    elif mktk=="AH":
                        s=settle_ah(pick,hg,ag)
                        if s=="push": continue
                        won=bool(s)
                    if won is None: continue
                    st_=1.0
                    if stake_mode=="Kelly": st_=max(1.0,kelly(prob,o,bank,0.25))
                    pnl=st_*(o-1) if won else -st_
                    bank+=pnl
                    log.append({"mkt":mktk,"prob":prob,"odd":o,"won":bool(won),"stake":st_,"pnl":pnl,
                                "clv":clv_for(pick,o,mkt,r)})
        except Exception as e: log_err("backtest loop",e)
        try: eng.learn_step(h,a,hg,ag,r,lg=div,match_num=j,total=len(rows))
        except Exception as e: log_err("backtest learn",e)
    return log,eng

def chip_html(t,kind=""): return f"<span class='chip {kind}'>{t}</span>"
def badge_html(kind,label): return f"<span class='badge {kind}'>{label}</span>"
def form_html(s):
    return "".join(f"<b class='{'w' if ch=='В' else ('d' if ch=='Н' else 'l')}'>{ch}</b>" for ch in s)
def market_rows_html(rows,thr):
    out="<div class='mrow hdr'><span>Рынок</span><span>Выбор</span><span>Вероятность</span><span>P</span><span>Безуб.</span><span>Кэф</span><span>EV</span><span></span></div>"
    for rw in rows:
        w=min(100,rw["prob"]*100)
        odd_s=f"{rw['odd']:.2f}" if rw["odd"] else f"fair {1/rw['prob']:.2f}"
        ev_s=f"<span class='{'evpos' if rw['ev']>0 else 'evneg'}'>{rw['ev']*100:+.1f}%</span>" if rw["ev"] is not None else "<span style='color:#64748b'>—</span>"
        be_s=f"{rw['be']*100:.1f}%" if rw["be"] else "—"
        mk="<span class='ok'>✅</span>" if rw["ok"] else ("<span style='color:#fde047;font-weight:800'>🔥</span>" if rw["prob"]>=thr else "<span class='nok'>·</span>")
        out+=(f"<div class='mrow'><span style='color:#94a3b8'>{rw['mkt']}</span><b style='color:#facc15'>{rw['pick']}</b>"
              f"<div><div class='bar'><i style='width:{w:.0f}%'></i></div></div>"
              f"<span style='color:#4ade80;font-weight:700'>{rw['prob']*100:.1f}%</span><span style='color:#f87171'>{be_s}</span>"
              f"<span style='color:#fff;font-weight:700'>{odd_s}</span>{ev_s}{mk}</div>")
    return out
def verdict_html(main,alt,avoid,text,pick=None,odd_s=None,prob=None,stake=None,btype=None):
    m_s=f"✅ <b class='y'>{main['pick']}</b> @ {main['odd_s']} (P {main['prob']*100:.0f}%)" if main else ""
    a_s=f"🔁 <b class='g'>{
