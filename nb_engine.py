"""NEURO BET engine v8.8 — + live engine с Bayesian update + temperature scaling."""
import requests, csv, io, os, math, re, pickle, json
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except Exception:
    Retry=None

MATRIX_N=9
REFIT_TEMP_EVERY=150
REFIT_STRUCT_EVERY=300
DISAGREE_MIN=0.03
BACKTEST_WARMUP=120
ML_REFIT_MIN=150
ML_WINDOW=400
ML_LR=0.05
ML_L2=0.001
ML_ITERS=300
NFEAT_ML=12
ENGINE_CACHE_VERSION="8.8"
TOTAL_MIN=95.0
LIVE_MODEL_FILE="live_model.json"
UA={"User-Agent":"Mozilla/5.0"}
CORRIDORS={"OU":(1.50,2.80),"AH":(1.60,2.60),"STAT":(1.40,4.50)}
ERR=[]
ERR_FILE="neuro_errors.log"
ENGINE_CACHE="neuro_engine.pkl"

# ID лиг API-Football (v3)
API_LG={"R1":235,"T1":203,"C1":2,"EL":3,"EC":848,"RUS_CUP":233}
API_NAMES={235:"🇷🇺 РПЛ",203:"🇹🇷 Суперлига",2:"🏆 ЛЧ",3:"🏆 ЛЕ",848:"🏆 ЛК",233:"🏆 Кубок России"}

def log_err(tag,e):
    line=f"[{datetime.now():%Y-%m-%d %H:%M:%S}][{tag}] {type(e).__name__}: {e}"
    ERR.append(line)
    if len(ERR)>300:
        ERR.pop(0)
    try:
        with open(ERR_FILE,"a",encoding="utf-8") as f:
            f.write(line+"\n")
    except Exception:
        pass

def _session():
    s=requests.Session()
    if Retry:
        r=Retry(total=3,backoff_factor=1,status_forcelist=[429,500,502,503,504])
        s.mount("https://",HTTPAdapter(max_retries=r))
        s.mount("http://",HTTPAdapter(max_retries=r))
    return s
_sess=_session()

def _new_team():
    return {"hs":[],"hc":[],"as":[],"ac":[],"form":[],"cfh":[],"cah":[],"cfa":[],"caa":[],
            "yfh":[],"yah":[],"yfa":[],"yaa":[],"hst_h":[],"hstc_h":[],"hst_a":[],"hstc_a":[]}
def _new_roi():
    return {"n":0,"profit":0.0}
def _new_lp():
    return {"w_shots":0.35,"rho":-0.13,"w_dc":0.72,"w_ml":0.25}

def _f(v):
    try:
        return float(v)
    except Exception:
        return None

def parse_date(s):
    for fmt in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d","%Y-%m-%dT%H:%M:%S%z","%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(s).strip()[:19],fmt[:19] if "z" in fmt else fmt)
        except Exception:
            continue
    return None

def is_half_line(x):
    v=_f(x)
    return v is not None and abs((v*2)%1)<1e-9

def fmt_line(v):
    s=f"{v:+.2f}"
    if s.endswith("0"):
        s=s[:-1]
    if s.endswith("."):
        s=s[:-1]
    return s

def is_cup(row):
    if not row:
        return False
    dv=row.get("Div","")
    lg=(row.get("League") or "").lower()
    return dv in ("C1","EL","EC") or any(x in lg for x in ["cup","champions","europa","conference","libertadores"])

def settle_ah(pick,hg,ag):
    m=re.match(r"Ф([12])\(([-+]?\d+(?:\.\d+)?)\)",pick or "")
    if not m:
        return None
    side,line=int(m.group(1)),float(m.group(2))
    res=((hg-ag) if side==1 else (ag-hg))+line
    if res>0.001:
        return True
    if abs(res)<=0.001:
        return "push"
    return False

def determine_outcome(market,pick,hg,ag):
    m=(market or "").upper()
    p=(pick or "").strip()
    if m in ("","HOT","STAT"):
        if p in ("П1","X","П2"):
            m="1X2"
        elif p in ("ТБ 2.5","ТМ 2.5"):
            m="OU"
        elif p.startswith("Ф"):
            m="AH"
        elif p.startswith("BTTS"):
            m="BTTS"
        elif p in ("1X","X2","12"):
            m="DC"
        else:
            return None
    if m=="1X2":
        res="П1" if hg>ag else ("X" if hg==ag else "П2")
        return "won" if res==p else "lost"
    if m=="OU":
        if p=="ТБ 2.5":
            return "won" if hg+ag>=3 else "lost"
        if p=="ТМ 2.5":
            return "won" if hg+ag<=2 else "lost"
        return None
    if m=="AH":
        s=settle_ah(p,hg,ag)
        if s is None:
            return None
        return "push" if s=="push" else ("won" if s else "lost")
    if m=="BTTS":
        both=(hg>0 and ag>0)
        return "won" if (both==(p=="BTTS да")) else "lost"
    if m=="DC":
        if p=="1X":
            ok=hg>=ag
        elif p=="X2":
            ok=hg<=ag
        elif p=="12":
            ok=hg!=ag
        else:
            return None
        return "won" if ok else "lost"
    return None

def kelly(prob,odds,bank,frac):
    if prob<=0 or odds<=1:
        return 0.0
    b=odds-1
    k=(b*prob-(1-prob))/b
    return round(min(max(0,k*frac),0.05)*bank,2)

def odd1(row,keys):
    for k in keys:
        v=_f(row.get(k))
        if v and v>1.01:
            return v
    return None

ODD_KEYS={"П1":["MaxH","B365H","PSH"],"X":["MaxD","B365D","PSD"],"П2":["MaxA","B365A","PSA"],
          "ТБ 2.5":["Max>2.5","B365>2.5","P>2.5"],"ТМ 2.5":["Max<2.5","B365<2.5","P<2.5"]}

def best_odd(row,pick):
    return odd1(row,ODD_KEYS.get(pick,[]))

def market_probs(row):
    ph,px,pa=_f(row.get("PSH")),_f(row.get("PSD")),_f(row.get("PSA"))
    if not(ph and px and pa):
        return None
    i1,ix,ia=1/ph,1/px,1/pa
    s=i1+ix+ia
    return (i1/s,ix/s,ia/s)

def clv_for(pick,odd,mkt,row):
    if not odd:
        return None
    if mkt:
        idx={"П1":0,"X":1,"П2":2}.get(pick)
        if idx is not None:
            return odd*mkt[idx]-1
    if row is None:
        return None
    if pick.startswith("Ф1") or pick.startswith("Ф2"):
        po=_f(row.get("PAHH")) if pick.startswith("Ф1") else _f(row.get("PAHA"))
        ot=_f(row.get("PAHA")) if pick.startswith("Ф1") else _f(row.get("PAHH"))
        if po and ot:
            i1,i2=1/po,1/ot
            s=i1+i2
            return odd*(i1/s)-1
        return None
    po=_f(row.get("PS>2.5")) if pick=="ТБ 2.5" else (_f(row.get("PS<2.5")) if pick=="ТМ 2.5" else None)
    ot=_f(row.get("PS<2.5")) if pick=="ТБ 2.5" else (_f(row.get("PS>2.5")) if pick=="ТМ 2.5" else None)
    if po and ot:
        i1,i2=1/po,1/ot
        s=i1+i2
        return odd*(i1/s)-1
    return None

def blend_market(P,mkt,w):
    if not mkt:
        return P
    P=dict(P)
    P["p1"]=(1-w)*P["p1"]+w*mkt[0]
    P["x"]=(1-w)*P["x"]+w*mkt[1]
    P["p2"]=(1-w)*P["p2"]+w*mkt[2]
    t=P["p1"]+P["x"]+P["p2"] or 1.0
    P["p1"]/=t
    P["x"]/=t
    P["p2"]/=t
    P["mkt"]=mkt
    return P

# ============== LIVE MODEL (persistent) ==============
DEFAULT_LIVE={"alpha":1.5,"beta":TOTAL_MIN,"temp":1.0,"signals":[],"league_pace":{},"n_learned":0}
def load_live_model():
    try:
        if os.path.exists(LIVE_MODEL_FILE):
            with open(LIVE_MODEL_FILE,"r",encoding="utf-8") as f:
                d=json.load(f)
            for k in DEFAULT_LIVE:
                d.setdefault(k,DEFAULT_LIVE[k])
            return d
    except Exception as e:
        log_err("load_live_model",e)
    return dict(DEFAULT_LIVE)

def save_live_model(m):
    try:
        with open(LIVE_MODEL_FILE,"w",encoding="utf-8") as f:
            json.dump(m,f,ensure_ascii=False,indent=2)
    except Exception as e:
        log_err("save_live_model",e)

def live_predict(minute,cur_total,base_lam,league=None,pressure=None,live_model=None):
    """Bayesian update (Gamma-Poisson) + momentum/pressure + temperature scaling."""
    if live_model is None:
        live_model=load_live_model()
    alpha=float(live_model.get("alpha",1.5))
    beta=float(live_model.get("beta",TOTAL_MIN))
    temp=float(live_model.get("temp",1.0))
    minute_f=max(1.0,float(minute))
    remaining=max(1.0,TOTAL_MIN-minute_f)
    pace=league and live_model.get("league_pace",{}).get(league)
    lam_pace=pace[0]/pace[1] if pace else (base_lam/TOTAL_MIN)
    lam_prior=lam_pace*minute_f
    alpha_post=alpha+cur_total
    beta_post=beta+minute_f
    lam_post=alpha_post/beta_post
    k=(lam_post/lam_pace) if lam_pace>0.001 else 1.0
    k=max(0.4,min(3.0,k))
    if pressure is not None and pressure>0:
        k*=min(1.5,max(0.6,1.0+0.3*pressure))
    lam_rem=lam_pace*remaining*k
    p_goal=1.0-math.exp(-lam_rem/temp)
    proj=cur_total+lam_rem
    return {"p_goal":p_goal,"proj_total":proj,"lam_rem":lam_rem,"pace":lam_pace*TOTAL_MIN,"k":k}

def live_learn_step(minute,cur_total,final_total,league=None,live_model=None):
    """Дообучение по завершённому матчу: обновляет α/β темпа + лигу."""
    if live_model is None:
        live_model=load_live_model()
    alpha=float(live_model.get("alpha",1.5))
    beta=float(live_model.get("beta",TOTAL_MIN))
    minute_f=max(1.0,float(minute))
    if final_total>cur_total:
        alpha+=final_total-cur_total
    beta+=TOTAL_MIN-minute_f
    live_model["alpha"]=min(alpha,50.0)
    live_model["beta"]=min(beta,50.0*TOTAL_MIN)
    if league:
        lp=live_model.setdefault("league_pace",{})
        if league not in lp:
            lp[league]=[0.0,0.0]
        lp[league][0]+=final_total
        lp[league][1]+=TOTAL_MIN
    live_model["n_learned"]=int(live_model.get("n_learned",0))+1
    return live_model

def live_refit_temp(live_model,window=500):
    """Temperature scaling по сигналам с исходом (был гол / не был)."""
    sigs=[s for s in live_model.get("signals",[]) if s.get("had_goal") is not None][-window:]
    if len(sigs)<30:
        return live_model
    def nll(T):
        s=0.0
        for sig in sigs:
            p=sig.get("p_goal",0.5)/T
            p=1.0-math.exp(-max(0.001,-math.log(1-min(max(p,0.001),0.999))))
            y=1.0 if sig.get("had_goal") else 0.0
            s-=math.log(min(max(p if y>0.5 else 1-p,1e-9),1-1e-9))
        return s
    best_T,best_ll=live_model.get("temp",1.0),nll(live_model.get("temp",1.0))
    T=0.5
    while T<=3.0001:
        ll=nll(T)
        if ll<best_ll-1e-9:
            best_ll,best_T=ll,T
        T+=0.05
    lo=max(0.5,best_T-0.05)
    hi=min(3.0,best_T+0.05)
    T=lo
    while T<=hi+1e-9:
        ll=nll(T)
        if ll<best_ll-1e-9:
            best_ll,best_T=ll,T
        T+=0.005
    live_model["temp"]=min(max(best_T,0.5),3.0)
    return live_model

def live_stats(live_model):
    sigs=live_model.get("signals",[])
    finished=[s for s in sigs if s.get("had_goal") is not None]
    total=len(finished)
    if total<5:
        return {"n":total,"hit_rate":None,"brier":None,"cal":[]}
    hits=sum(1 for s in finished if s.get("had_goal"))
    brier=sum((s.get("p_goal",0.5)-(1.0 if s.get("had_goal") else 0.0))**2 for s in finished)/total
    cal=[]
    for lo,hi in [(0.3,0.5),(0.5,0.65),(0.65,0.80),(0.80,1.01)]:
        bin_=[s for s in finished if lo<=s.get("p_goal",0)<hi]
        if len(bin_)>=3:
            wr=sum(1 for s in bin_ if s.get("had_goal"))/len(bin_)*100
            avg=sum(s.get("p_goal",0) for s in bin_)/len(bin_)*100
            cal.append({"bin":f"{lo*100:.0f}–{hi*100:.0f}%","n":len(bin_),
                        "pred":f"{avg:.1f}%","fact":f"{wr:.1f}%"})
    return {"n":total,"hit_rate":hits/total*100,"brier":brier,"cal":cal}

# ============== API-FOOTBALL LIVE ==============
def api_football_live(api_key,league_ids):
    """Вернёт список live-матчей с API-Football (если ключ есть)."""
    if not api_key:
        return [],["API-Football: ключ не задан"]
    out=[]
    rep=[]
    headers={"x-apisports-key":api_key,"x-rapidapi-host":"v3.football.api-sports.io"}
    for lid in league_ids:
        try:
            r=_sess.get(f"https://v3.football.api-sports.io/fixtures?live=all&league={lid}",
                        headers=headers,timeout=15)
            if r.status_code!=200:
                rep.append(f"API {API_NAMES.get(lid,lid)}: HTTP {r.status_code}")
                continue
            data=(r.json() or {}).get("response") or []
            n=0
            for f in data:
                fix=f.get("fixture") or {}
                teams=f.get("teams") or {}
                goals=f.get("goals") or {}
                stats_raw=f.get("statistics") or []
                stat={"home":{},"away":{}}
                for side,st in zip(("home","away"),stats_raw):
                    for val in st.get("statistics") or []:
                        stat[side][val.get("type")]=(val.get("value"))
                out.append({"league":API_NAMES.get(lid,str(lid)),"league_id":lid,
                            "fixture_id":fix.get("id"),
                            "home":(teams.get("home") or {}).get("name"),
                            "away":(teams.get("away") or {}).get("name"),
                            "home_score":goals.get("home") or 0,
                            "away_score":goals.get("away") or 0,
                            "minute":fix.get("status",{}).get("elapsed") or 0,
                            "progress":f"{fix.get('status',{}).get('elapsed') or 0}'",
                            "status":(fix.get("status") or {}).get("short") or "",
                            "stats":stat})
                n+=1
            rep.append(f"API {API_NAMES.get(lid,lid)}: {n} live")
        except Exception as e:
            log_err(f"api_live {lid}",e)
            rep.append(f"API {API_NAMES.get(lid,lid)}: {type(e).__name__}")
    return out,rep

class Engine:
    def __init__(self):
        self.elo={}
        self.st=defaultdict(_new_team)
        self.hg=[]
        self.ag=[]
        self.hsth=[]
        self.hsta=[]
        self.h2h=defaultdict(list)
        self.calib=[]
        self.temp=1.0
        self.lp=defaultdict(_new_lp)
        self.hist=defaultdict(list)
        self.ml_w={}
        self.ml_hist=defaultdict(list)
        self.match_count=0
        self.market_roi=defaultdict(_new_roi)
        self.last_match_date={}
    @staticmethod
    def _logit(p):
        p=min(max(p,1e-6),1-1e-6)
        return math.log(p/(1-p))
    @staticmethod
    def _sigmoid(x):
        return 1.0/(1.0+math.exp(-max(-30,min(30,x))))
    def _m(self,l,d=1.0):
        return sum(l)/len(l) if l else d
    def _p(self,l,k):
        return math.exp(-l)*l**k/math.factorial(k)
    def _form(self,t):
        f=self.st[t]["form"][-5:]
        return (sum(f)/(len(f)*3)) if f else 0.5
    def form_str(self,t):
        out=""
        for x in self.st[t]["form"][-5:]:
            out+={"3":"В","1":"Н","0":"П"}[str(int(x))]
        return out or "—"
    def calibrate(self,p):
        return self._sigmoid(self._logit(p)/self.temp)
    def _nll_T(self,data,T):
        s=0.0
        inv=1.0/T
        for z,y in data:
            p=self._sigmoid(z*inv)
            s-=math.log(min(max(p if y>0.5 else 1-p,1e-9),1-1e-9))
        return s
    def refit_temp(self):
        if len(self.calib)<60:
            return
        data=self.calib[-3000:]
        best_T,best_ll=self.temp,self._nll_T(data,self.temp)
        T=0.5
        while T<=3.0001:
            ll=self._nll_T(data,T)
            if ll<best_ll-1e-9:
                best_ll,best_T=ll,T
            T+=0.05
        lo=max(0.5,best_T-0.05)
        hi=min(3.0,best_T+0.05)
        T=lo
        while T<=hi+1e-9:
            ll=self._nll_T(data,T)
            if ll<best_ll-1e-9:
                best_ll,best_T=ll,T
            T+=0.005
        self.temp=min(max(best_T,0.5),3.0)
    def _p1px(self,lh,la,rho):
        N=MATRIX_N
        M=[[self._p(lh,i)*self._p(la,j) for j in range(N)] for i in range(N)]
        tau={(0,0):1+lh*la*rho,(1,0):1-la*rho,(0,1):1-lh*rho,(1,1):1+rho}
        for i in range(N):
            for j in range(N):
                if (i,j) in tau:
                    M[i][j]*=tau[(i,j)]
        tot=sum(map(sum,M)) or 1.0
        M=[[v/tot for v in r] for r in M]
        p1=sum(M[i][j] for i in range(N) for j in range(N) if i>j)
        px=sum(M[i][i] for i in range(N))
        return p1,px,M
    def _probs_from(self,lh,la,rho,w,e,pde):
        p1,px,_=self._p1px(lh,la,rho)
        f1=w*p1+(1-w)*e*(1-pde)
        fd=w*px+(1-w)*pde
        f2=max(1e-6,1-f1-fd)
        return f1,fd,f2
    def _loglik(self,rows,rho,w):
        ll=0.0
        for lh,la,e,pde,out in rows:
            f1,fd,f2=self._probs_from(lh,la,rho,w,e,pde)
            ll-=math.log(min(max((f1,fd,f2)[out],1e-6),1-1e-6))
        return ll
    def _fit_league(self,lg):
        win=self.hist[lg][-400:]
        if len(win)<200:
            return
        split=int(len(win)*0.8)
        train,hold=win[:split],win[split:]
        cur=self.lp[lg]
        best_ws=None
        for ws in (0.20,0.35,0.50):
            rows=[((1-ws)*gh+ws*sh,(1-ws)*ga+ws*sa,e,pde,out) for gh,ga,sh,sa,e,pde,out in train]
            ll=self._loglik(rows,cur["rho"],cur["w_dc"])
            if best_ws is None or ll<best_ws[0]:
                best_ws=(ll,ws)
        ws_pick=best_ws[1]
        tr=[((1-ws_pick)*gh+ws_pick*sh,(1-ws_pick)*ga+ws_pick*sa,e,pde,out) for gh,ga,sh,sa,e,pde,out in train]
        ho=[((1-ws_pick)*gh+ws_pick*sh,(1-ws_pick)*ga+ws_pick*sa,e,pde,out) for gh,ga,sh,sa,e,pde,out in hold]
        best=None
        for rho in (-0.20,-0.13,-0.06,0.0):
            for w in (0.60,0.72,0.85):
                ll=self._loglik(tr,rho,w)
                if best is None or ll<best[0]:
                    best=(ll,rho,w)
        if ho:
            if self._loglik(ho,best[1],best[2])>self._loglik(ho,cur["rho"],cur["w_dc"]):
                return
        cur["w_shots"]=ws_pick
        cur["rho"],cur["w_dc"]=best[1],best[2]
    @staticmethod
    def _softmax(sc):
        m=max(sc)
        ex=[math.exp(s-m) for s in sc]
        t=sum(ex) or 1.0
        return tuple(v/t for v in ex)
    def _ml_probs(self,lg,feat):
        W=self.ml_w.get(lg)
        if not W:
            return (1/3,1/3,1/3)
        return self._softmax([sum(w*x for w,x in zip(W[c],feat)) for c in range(3)])
    def _ml_nll(self,W,rows):
        s=0.0
        for feat,out in rows:
            p=self._softmax([sum(w*x for w,x in zip(W[c],feat)) for c in range(3)])[out]
            s-=math.log(min(max(p,1e-6),1-1e-6))
        return s
    def _fit_ml(self,lg):
        data=self.ml_hist[lg][-ML_WINDOW:]
        if len(data)<ML_REFIT_MIN:
            return
        split=int(len(data)*0.8)
        train,hold=data[:split],data[split:]
        old=self.ml_w.get(lg)
        W=[row[:] for row in old] if old else [[0.0]*NFEAT_ML for _ in range(3)]
        n=max(1,len(train))
        for _ in range(ML_ITERS):
            grad=[[0.0]*NFEAT_ML for _ in range(3)]
            for feat,out in train:
                pr=self._softmax([sum(w*x for w,x in zip(W[c],feat)) for c in range(3)])
                for c in range(3):
                    err=pr[c]-(1.0 if c==out else 0.0)
                    for k in range(NFEAT_ML):
                        grad[c][k]+=err*feat[k]
            for c in range(3):
                for k in range(NFEAT_ML):
                    W[c][k]-=ML_LR*(grad[c][k]/n+ML_L2*W[c][k])
        if hold:
            ll_new=self._ml_nll(W,hold)
            ll_old=self._ml_nll(old,hold) if old else float("inf")
            if ll_new>ll_old:
                return
        self.ml_w[lg]=W
    def record_market(self,mkt,won,odd):
        r=self.market_roi[mkt]
        r["n"]+=1
        r["profit"]=0.9*r["profit"]+0.1*((odd-1) if won else -1)
    def market_adjust(self,mkt):
        r=self.market_roi.get(mkt)
        if not r or r["n"]<40:
            return 0.0
        return max(-0.010,min(0.020,-r["profit"]*0.4))
    def add(self,h,a,hg,ag,row=None,k=None,match_num=None,total=None,match_date=None):
        if k is None:
            prog=min(1.0,match_num/total) if (match_num is not None and total) else 0.5
            k=16+32*prog
        rh,ra=self.elo.get(h,1500),self.elo.get(a,1500)
        eh=1/(1+10**((ra-(rh+60))/400))
        s=1.0 if hg>ag else (0.5 if hg==ag else 0.0)
        self.elo[h]=rh+k*(s-eh)
        self.elo[a]=ra+k*((1-s)-(1-eh))
        t=self.st
        t[h]["hs"].append(hg)
        t[h]["hc"].append(ag)
        t[a]["as"].append(ag)
        t[a]["ac"].append(hg)
        t[h]["form"].append(3 if hg>ag else (1 if hg==ag else 0))
        t[a]["form"].append(3 if ag>hg else (1 if hg==ag else 0))
        self.hg.append(hg)
        self.ag.append(ag)
        self.h2h[(h,a)].append(hg-ag)
        self.h2h[(h,a)]=self.h2h[(h,a)][-8:]
        if row:
            for col,t1,k1,t2,k2 in (("HC",h,"cfh",a,"caa"),("AC",a,"cfa",h,"cah"),
                                    ("HY",h,"yfh",a,"yaa"),("AY",a,"yfa",h,"yah")):
                v=_f(row.get(col))
                if v is not None:
                    t[t1][k1].append(v)
                    t[t2][k2].append(v)
            hst,ast=_f(row.get("HST")),_f(row.get("AST"))
            if hst is not None and ast is not None:
                t[h]["hst_h"].append(hst)
                t[h]["hstc_h"].append(ast)
                t[a]["hst_a"].append(ast)
                t[a]["hstc_a"].append(hst)
                self.hsth.append(hst)
                self.hsta.append(ast)
        for team in (h,a):
            for key in t[team]:
                t[team][key]=t[team][key][-12:]
        for pool in (self.hg,self.ag,self.hsth,self.hsta):
            if len(pool)>4000:
                del pool[:-4000]
        if match_date:
            self.last_match_date[h]=match_date
            self.last_match_date[a]=match_date
    def h2h_adjust(self,h,a,lh,la):
        hist=self.h2h.get((h,a),[])
        n=len(hist)
        if n<5:
            return lh,la,n
        shrink=min(1.0,(n-4)/6.0)
        shift=(sum(hist)/n)*0.08*shrink
        return max(0.3,lh+shift/2),max(0.25,la-shift/2),n
    def predict(self,h,a,lg="G",match_date=None,cup=False):
        P0=self.lp[lg]
        ws=P0["w_shots"]
        lh_g=max(0.05,self._m(self.hg,1.5))
        la_g=max(0.05,self._m(self.ag,1.2))
        lh_s=max(0.05,self._m(self.hsth,4.5))
        la_s=max(0.05,self._m(self.hsta,4.0))
        sh,sa=self.st[h],self.st[a]
        ah_=self._m(sh["hs"],lh_g)/lh_g
        dh_=self._m(sh["hc"],la_g)/la_g
        aa_=self._m(sa["as"],la_g)/la_g
        da_=self._m(sa["ac"],lh_g)/lh_g
        fh,fa=self._form(h),self._form(a)
        lam_g_h=max(0.3,min(5.0,lh_g*ah_*da_*1.10*(0.85+0.30*fh)))
        lam_g_a=max(0.25,min(4.5,la_g*aa_*dh_*0.95*(0.85+0.30*fa)))
        conv_h=lh_g/max(0.5,lh_s)
        conv_a=la_g/max(0.5,la_s)
        ash_h=self._m(sh["hst_h"],lh_s)/lh_s
        dsh_a=self._m(sa["hstc_a"],lh_s)/lh_s
        ash_a=self._m(sa["hst_a"],la_s)/la_s
        dsh_h=self._m(sh["hstc_h"],la_s)/la_s
        lam_s_h=max(0.3,min(5.0,lh_s*conv_h*ash_h*dsh_a*(0.85+0.30*fh)))
        lam_s_a=max(0.25,min(4.5,la_s*conv_a*ash_a*dsh_h*(0.85+0.30*fa)))
        lam_h=(1-ws)*lam_g_h+ws*lam_s_h
        lam_a=(1-ws)*lam_g_a+ws*lam_s_a
        if cup:
            lam_h=max(0.3,lam_h-0.15)
            lam_a=max(0.25,lam_a-0.15)
        lam_h,lam_a,h2h_n=self.h2h_adjust(h,a,lam_h,lam_a)
        agree=(lam_h-lam_a)*(lam_g_h-lam_g_a)>0
        e=1/(1+10**((self.elo.get(a,1500)-self.elo.get(h,1500)-60)/400))
        pde=0.20+0.12*(1-abs(e-0.5)*2)
        p1,px,M=self._p1px(lam_h,lam_a,P0["rho"])
        f1=P0["w_dc"]*p1+(1-P0["w_dc"])*e*(1-pde)
        fd=P0["w_dc"]*px+(1-P0["w_dc"])*pde
        f2=max(0.0,1-f1-fd)
        elo_diff=self.elo.get(h,1500)-self.elo.get(a,1500)
        games=min(len(sh["hs"])+len(sh["as"]),len(sa["hs"])+len(sa["as"]))
        ref=match_date or datetime.now()
        rest_h=(ref-self.last_match_date[h]).days if h in self.last_match_date else 14
        rest_a=(ref-self.last_match_date[a]).days if a in self.last_match_date else 14
        rest_h=max(1,min(rest_h,60))
        rest_a=max(1,min(rest_a,60))
        sr_h=(sum(sh["hst_h"][-5:])/max(1,sum(sh["hc"][-5:]))) if len(sh["hst_h"])>=3 else 1.5
        sr_a=(sum(sa["hst_a"][-5:])/max(1,sum(sa["ac"][-5:]))) if len(sa["hst_a"])>=3 else 1.5
        f3_h=sum(sh["form"][-3:])/max(1,len(sh["form"][-3:]))/3.0
        f3_a=sum(sa["form"][-3:])/max(1,len(sa["form"][-3:]))/3.0
        momentum=(f3_h-fh)-(f3_a-fa)
        feats=[1.0,elo_diff/400.0,lam_g_h-lam_g_a,lam_s_h-lam_s_a,fh-fa,math.log(games+1),
               1.0,math.log(rest_h+1),math.log(rest_a+1),sr_h,sr_a,momentum]
        mp1,mx,mp2=self._ml_probs(lg,feats)
        n_tr=len(self.ml_hist.get(lg,[]))
        w_ml=P0.get("w_ml",0.25)*min(1.0,n_tr/300.0)
        if lg in self.ml_w and w_ml>0:
            f1=(1-w_ml)*f1+w_ml*mp1
            fd=(1-w_ml)*fd+w_ml*mx
            f2=(1-w_ml)*f2+w_ml*mp2
        tt=f1+fd+f2 or 1.0
        f1,fd,f2=f1/tt,fd/tt,f2/tt
        raw=(f1,fd,f2)
        c1,cx,c2=self.calibrate(f1),self.calibrate(fd),self.calibrate(f2)
        ct=c1+cx+c2 or 1.0
        c1,cx,c2=c1/ct,cx/ct,c2/ct
        over=1-sum(self._p(lam_h+lam_a,k) for k in range(3))
        btts=sum(M[i][j] for i in range(1,MATRIX_N) for j in range(1,MATRIX_N))
        corners=((self._m(sh["cfh"],5)+self._m(sa["caa"],5))/2,(self._m(sa["cfa"],5)+self._m(sh["cah"],5))/2)
        yellows=((self._m(sh["yfh"],2)+self._m(sa["yaa"],2))/2,(self._m(sa["yfa"],2)+self._m(sh["yah"],2))/2)
        return {"p1":c1,"x":cx,"p2":c2,"p1_raw":raw[0],"x_raw":raw[1],"p2_raw":raw[2],
                "over":over,"btts":btts,"M":M,"agree":agree,"lams":(lam_h,lam_a),
                "lams_g":(lam_g_h,lam_g_a),"lams_s":(lam_s_h,lam_s_a),"games":games,
                "corners":corners,"yellows":yellows,"h2h_n":h2h_n,"e":e,"pde":pde,
                "ml_feats":feats,"w_ml_eff":w_ml}
    def learn_step(self,h,a,hg,ag,row=None,lg="G",match_num=None,total=None,match_date=None):
        P=self.predict(h,a,lg,match_date=match_date,cup=is_cup(row))
        out=0 if hg>ag else (1 if hg==ag else 2)
        self.calib.append((self._logit(P["p1_raw"]),1.0 if out==0 else 0.0))
        self.calib.append((self._logit(P["x_raw"]),1.0 if out==1 else 0.0))
        self.calib.append((self._logit(P["p2_raw"]),1.0 if out==2 else 0.0))
        if len(self.calib)>6000:
            del self.calib[:-6000]
        self.hist[lg].append((P["lams_g"][0],P["lams_g"][1],P["lams_s"][0],P["lams_s"][1],P["e"],P["pde"],out))
        if len(self.hist[lg])>1200:
            del self.hist[lg][:-1200]
        self.ml_hist[lg].append((P["ml_feats"],out))
        if len(self.ml_hist[lg])>1200:
            del self.ml_hist[lg][:-1200]
        if row:
            pairs=[("1X2","П1",P["p1"],_f(row.get("B365H")),hg>ag),
                   ("1X2","X",P["x"],_f(row.get("B365D")),hg==ag),
                   ("1X2","П2",P["p2"],_f(row.get("B365A")),hg<ag),
                   ("OU","ТБ 2.5",P["over"],_f(row.get("B365>2.5")),hg+ag>=3),
                   ("OU","ТМ 2.5",1-P["over"],_f(row.get("B365<2.5")),hg+ag<=2)]
            for mkt,pick,prob,odd,won in pairs:
                if odd and odd>1.01:
                    self.record_market(mkt,bool(won),odd)
        self.match_count+=1
        if self.match_count%REFIT_TEMP_EVERY==0:
            self.refit_temp()
        if len(self.hist[lg])%REFIT_STRUCT_EVERY==0:
            self._fit_league(lg)
            self._fit_ml(lg)
        self.add(h,a,hg,ag,row,match_num=match_num,total=total,match_date=match_date)
        return P

def build_candidates(P,row,PR,blacklist=()):
    probs={"П1":P["p1"],"X":P["x"],"П2":P["p2"],
           "ТБ 2.5":P["over"],"ТМ 2.5":1-P["over"],
           "BTTS да":P["btts"],"BTTS нет":1-P["btts"],
           "1X":P["p1"]+P["x"],"X2":P["x"]+P["p2"],"12":P["p1"]+P["p2"]}
    cands=[]
    for pick,prob in probs.items():
        if pick in ("П1","X","П2"):
            mkt="1X2"
        elif pick.startswith("Т"):
            mkt="OU"
        else:
            mkt="STAT"
        if mkt in blacklist:
            continue
        odd=best_odd(row,pick) if pick in ODD_KEYS else None
        cands.append((mkt,pick,prob,odd))
    ahh=_f(row.get("AHh")) if row else None
    if is_half_line(ahh) and "AH" not in blacklist:
        ohh=odd1(row,["MaxAHH","B365AHH","PAHH"])
        oha=odd1(row,["MaxAHA","B365AHA","PAHA"])
        if ohh and oha:
            pc=sum(P["M"][i][j] for i in range(MATRIX_N) for j in range(MATRIX_N) if (i-j+ahh)>0.001)
            cands.append(("AH",f"Ф1({fmt_line(ahh)})",pc,ohh))
            cands.append(("AH",f"Ф2({fmt_line(-ahh)})",1-pc,oha))
    return cands

def evaluate_rows(cands,P,mkt_probs,PR,engine,use_dis,row=None):
    rows=[]
    best=None
    hot=[]
    card_clv=None
    gap=None
    if mkt_probs:
        gap=max(abs(P["p1"]-mkt_probs[0]),abs(P["x"]-mkt_probs[1]),abs(P["p2"]-mkt_probs[2]))
    for mkt,pick,prob,odd in cands:
        item={"mkt":mkt,"pick":pick,"prob":prob,"odd":odd,"ev":None,"be":None,"ok":False}
        if odd:
            lo,hi=PR["corr"] if mkt=="1X2" else CORRIDORS.get(mkt,(1.4,4.2))
            ev=prob*odd-1
            be=1/odd
            edge=prob-be
            req=max(0.0,PR["ev"]+max(0.0,odd-2.5)*0.02+engine.market_adjust(mkt))
            dis_ok=(not use_dis) or (gap is None) or (gap>=DISAGREE_MIN)
            agree_ok=(mkt!="1X2") or P["agree"]
            games_ok=P["games"]>=PR["min_games"]
            item.update(ev=ev,be=be,ok=(lo<=odd<=hi and edge>=PR["edge"] and ev>=req and dis_ok and agree_ok and games_ok))
            if item["ok"]:
                stk=kelly(prob,odd,PR["bank"],PR["kelly"])
                if best is None or ev>best[3]:
                    best=(mkt,pick,odd,ev,prob,stk)
                    card_clv=clv_for(pick,odd,mkt_probs,row)
        if prob>=PR["thr"]:
            hot.append((pick,prob,odd))
        rows.append(item)
    hot.sort(key=lambda x:-x[1])
    return rows,best,hot,card_clv,gap

def backtest(div,season,PR,use_dis=True,stake_mode="Flat"):
    rows=[r for r in load_seasonal(div,season)
          if r.get("FTHG") not in (None,"") and r.get("FTAG") not in (None,"") and parse_date(r.get("Date",""))]
    rows.sort(key=lambda r: parse_date(r["Date"]))
    eng=Engine()
    log=[]
    bank=10000.0
    for j,r in enumerate(rows):
        h=(r.get("HomeTeam") or "").strip()
        a=(r.get("AwayTeam") or "").strip()
        try:
            hg,ag=float(r["FTHG"]),float(r["FTAG"])
        except Exception as e:
            log_err("bt parse",e)
            continue
        md=parse_date(r.get("Date",""))
        try:
            P=eng.predict(h,a,div,match_date=md,cup=is_cup(r))
            mkt=market_probs(r)
            Pb=blend_market(P,mkt,PR["w_market"])
            if j>=BACKTEST_WARMUP:
                cands=build_candidates(Pb,r,PR)
                rows_ev,best,hot,clv,gap=evaluate_rows(cands,Pb,mkt,PR,eng,use_dis,row=r)
                for item in rows_ev:
                    if not item["ok"] or not item["odd"]:
                        continue
                    res=determine_outcome(item["mkt"],item["pick"],hg,ag)
                    if res in (None,"push"):
                        continue
                    won=(res=="won")
                    st_=1.0
                    if stake_mode=="Kelly":
                        st_=max(1.0,kelly(item["prob"],item["odd"],bank,0.25))
                    pnl=st_*(item["odd"]-1) if won else -st_
                    bank+=pnl
                    log.append({"mkt":item["mkt"],"prob":item["prob"],"odd":item["odd"],
                                "won":won,"stake":st_,"pnl":pnl,
                                "clv":clv_for(item["pick"],item["odd"],mkt,r)})
        except Exception as e:
            log_err("bt loop",e)
        try:
            eng.learn_step(h,a,hg,ag,r,lg=div,match_num=j,total=len(rows),match_date=md)
        except Exception as e:
            log_err("bt learn",e)
    return log,eng

def find_season():
    for s in ["2627","2526","2425"]:
        try:
            r=_sess.head(f"https://www.football-data.co.uk/mmz4281/{s}/E0.csv",timeout=8)
            if r.status_code==200:
                return s
        except Exception as e:
            log_err("find_season",e)
    return "2526"

def prev_season(s):
    try:
        return f"{int(s[:2])-1:02d}{int(s[2:])-1:02d}"
    except Exception:
        return s

def load_seasonal(div,season):
    try:
        r=_sess.get(f"https://www.football-data.co.uk/mmz4281/{season}/{div}.csv",timeout=20,headers=UA)
        if r.status_code!=200:
            return []
        return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    except Exception as e:
        log_err(f"load_seasonal {div}",e)
        return []

def load_many(divs,season):
    with ThreadPoolExecutor(max_workers=8) as ex:
        return dict(zip(divs,ex.map(lambda d: load_seasonal(d,season),divs)))

def load_fixtures():
    rep=[]
    rows=[]
    seen=set()
    for u in ["https://www.football-data.co.uk/mmz4281/fixtures.csv",
              "https://www.football-data.co.uk/fixtures.csv"]:
        try:
            r=_sess.get(u,timeout=25,headers=UA)
            if r.status_code!=200:
                rep.append(f"{u.split('/')[-1]}: HTTP {r.status_code}")
                continue
            rd=list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
            n=0
            for x in rd:
                k=(x.get("Div"),x.get("Date"),x.get("HomeTeam"),x.get("AwayTeam"))
                if k in seen or not x.get("HomeTeam"):
                    continue
                seen.add(k)
                rows.append(x)
                n+=1
            rep.append(f"{u.split('/')[-1]}: OK,{n}")
            if n:
                break
        except Exception as e:
            log_err("load_fixtures",e)
            rep.append(f"{u.split('/')[-1]}: {type(e).__name__}")
    return rows,rep

def load_livescores():
    try:
        r=_sess.get("https://www.thesportsdb.com/api/v1/json/3/livescore.php?s=Soccer",timeout=10)
        out={}
        for e in (r.json() or {}).get("events") or []:
            hk=re.sub(r"[^a-zа-я0-9]","",(e.get("strHomeTeam","") or "").lower())
            ak=re.sub(r"[^a-zа-я0-9]","",(e.get("strAwayTeam","") or "").lower())
            out[(hk,ak)]={"home":e.get("intHomeScore"),"away":e.get("intAwayScore"),
                          "status":(e.get("strStatus") or "").strip(),
                          "progress":(e.get("strProgress") or "").strip(),
                          "league":e.get("strLeague") or ""}
        return out
    except Exception as e:
        log_err("livescores",e)
        return {}

def match_live(live,home,away):
    if not live:
        return None
    hk=re.sub(r"[^a-zа-я0-9]","",(home or "").lower())
    ak=re.sub(r"[^a-zа-я0-9]","",(away or "").lower())
    for (lh,la),v in live.items():
        if (lh==hk and la==ak) or (hk in lh and ak in la) or (lh in hk and la in ak):
            return v
    return None

FINISHED_STATUSES={"match finished","ft","aet","ap","finished","full time"}

def engine_fingerprint(season,div_counts):
    return (ENGINE_CACHE_VERSION,season,tuple(sorted(div_counts.items())))

def engine_cache_get(fp):
    try:
        with open(ENGINE_CACHE,"rb") as f:
            d=pickle.load(f)
        if d.get("fp")==fp:
            return d.get("engine")
    except Exception as e:
        log_err("cache_get",e)
    return None

def engine_cache_put(fp,eng):
    try:
        with open(ENGINE_CACHE,"wb") as f:
            pickle.dump({"fp":fp,"engine":eng},f)
    except Exception as e:
        log_err("cache_put",e)
