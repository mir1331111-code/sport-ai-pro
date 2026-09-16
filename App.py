"""NEURO BET PRO v9 — LLM risk layer (Gemini/Grok) + quota >=5/day + tiers."""
import streamlit as st
import requests, csv, io, os, math, re, pickle, json
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except Exception:
    Retry=None

st.set_page_config(page_title="NEURO BET PRO v9", page_icon="🏟", layout="wide", initial_sidebar_state="expanded")
HISTORY_FILE="neuro_bet_pro.json"
esc=html_esc=__import__("html").escape
AVG_GOALS=2.75
TOTAL_MIN=95.0
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
ENGINE_CACHE_VERSION="9.0"
LIVE_MODEL_FILE="live_model.json"
UA={"User-Agent":"Mozilla/5.0"}
CORRIDORS={"OU":(1.50,2.80),"AH":(1.60,2.60),"STAT":(1.40,4.50)}
ERR=[]
ERR_FILE="neuro_errors.log"
ENGINE_CACHE="neuro_engine.pkl"
API_LG={"R1":235,"T1":203,"C1":2,"EL":3,"EC":848,"RUS_CUP":233}
API_NAMES={235:"🇷 РПЛ",203:"🇹🇷 Суперлига",2:"🏆 ЛЧ",3:"🏆 ЛЕ",848:"🏆 ЛК",233:"🏆 Кубок России"}
DIV_NAMES={"E0":"🏴󠁢 АПЛ","E1":"🏴󠁢󠁿 Чемпионшип","SC0":"🏴󠁢󠁣󠁴󠁿 Шотландия",
 "D1":"🇩🇪 Бундеслига","D2":"🇩🇪 2.Бундеслига","I1":"🇮🇹 Серия A","I2":"🇮🇹 Серия B",
 "SP1":"🇪 Ла Лига","SP2":"🇪🇸 Сегунда","F1":"🇫🇷 Лига 1","F2":"🇫🇷 Лига 2",
 "N1":"🇳🇱 Эредивизи","B1":"🇧🇪 Про-лига","P1":"🇵🇹 Примейра","T1":"🇹🇷 Суперлига",
 "G1":"🇬🇷 Греция","R1":"🇷🇺 РПЛ","BR1":"🇧🇷 Бразилия","C1":"🏆 ЛЧ","EL":"🏆 ЛЕ","EC":"🏆 ЛК"}
GOALS={
 "🎯 Проходимость":dict(w_market=0.65,thr=0.62,dis=False,edge=0.01,ev=0.01,corr=(1.30,2.30),min_games=10),
 "⚖️ Баланс":dict(w_market=0.40,thr=0.55,dis=True,edge=0.02,ev=0.02,corr=(1.40,4.20),min_games=8),
 "💰 Value":dict(w_market=0.20,thr=0.45,dis=True,edge=0.03,ev=0.02,corr=(1.40,4.20),min_games=6)}
WALLS={
 "🌃 Неон-стадион":"linear-gradient(rgba(4,8,18,.80),rgba(4,8,18,.90)),url('https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=1920&auto=format&fit=crop') center/cover",
 "🕹 Synthwave":"linear-gradient(rgba(6,3,20,.82),rgba(6,3,20,.92)),url('https://images.unsplash.com/photo-1550745165-9bc0b252726f?q=80&w=1920&auto=format&fit=crop') center/cover",
 "🌌 Aurora":"radial-gradient(1100px 620px at 10% -10%, rgba(34,211,238,.20), transparent 60%),radial-gradient(950px 540px at 90% 8%, rgba(167,139,250,.20), transparent 62%),radial-gradient(900px 640px at 50% 112%, rgba(52,211,153,.16), transparent 60%),#05070f",
 "⚫ Минимализм":"linear-gradient(180deg,#070a12 0%,#0b0f1a 55%,#070a12 100%)",
}
SORT_OPTIONS=["По EV (валуи сверху)","По вероятности","По дате (ближайшие)","По коэффициенту","По лиге (А→Я)"]
SORT_DEFAULT_DESC={"По EV (валуи сверху)":True,"По вероятности":True,"По дате (ближайшие)":False,
                   "По коэффициенту":True,"По лиге (А→Я)":False}
PORT_SORT=["⏳ Сначала активные","📅 По дате (новые сверху)","💰 По сумме ставки","📈 По PnL","🎯 По вероятности"]
PORT_DEFAULT_DESC={"⏳ Сначала активные":False,"📅 По дате (новые сверху)":True,"💰 По сумме ставки":True,
                   "📈 По PnL":True,"🎯 По вероятности":True}

def log_err(tag,e):
    line=f"[{datetime.now():%Y-%m-%d %H:%M:%S}][{tag}] {type(e).__name__}: {e}"
    ERR.append(line)
    if len(ERR)>300: ERR.pop(0)
    try:
        with open(ERR_FILE,"a",encoding="utf-8") as f: f.write(line+"\n")
    except Exception: pass

def _session():
    s=requests.Session()
    if Retry:
        r=Retry(total=3,backoff_factor=1,status_forcelist=[429,500,502,503,504])
        s.mount("https://",HTTPAdapter(max_retries=r)); s.mount("http://",HTTPAdapter(max_retries=r))
    return s
_sess=_session()

def _new_team():
    return {"hs":[],"hc":[],"as":[],"ac":[],"form":[],"cfh":[],"cah":[],"cfa":[],"caa":[],
            "yfh":[],"yah":[],"yfa":[],"yaa":[],"hst_h":[],"hstc_h":[],"hst_a":[],"hstc_a":[]}
def _new_roi(): return {"n":0,"profit":0.0}
def _new_lp(): return {"w_shots":0.35,"rho":-0.13,"w_dc":0.72,"w_ml":0.25}
def _f(v):
    try: return float(v)
    except Exception: return None
def parse_date(s):
    for fmt in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d","%Y-%m-%dT%H:%M:%S%z","%Y-%m-%dT%H:%M:%S"):
        try:
            src=str(s).strip()
            if "z" in fmt: src=src[:19]
            return datetime.strptime(src,fmt)
        except Exception: continue
    return None
def is_half_line(x):
    v=_f(x)
    return v is not None and abs((v*2)%1)<1e-9
def fmt_line(v):
    s=f"{v:+.2f}"
    if s.endswith("0"): s=s[:-1]
    if s.endswith("."): s=s[:-1]
    return s
def is_cup(row):
    if not row: return False
    dv=row.get("Div",""); lg=(row.get("League") or "").lower()
    return dv in ("C1","EL","EC") or any(x in lg for x in ["cup","champions","europa","conference","libertadores"])
def settle_ah(pick,hg,ag):
    m=re.match(r"Ф([12])\(([-+]?\d+(?:\.\d+)?)\)",pick or "")
    if not m: return None
    side,line=int(m.group(1)),float(m.group(2))
    res=((hg-ag) if side==1 else (ag-hg))+line
    if res>0.001: return True
    if abs(res)<=0.001: return "push"
    return False
def determine_outcome(market,pick,hg,ag):
    m=(market or "").upper(); p=(pick or "").strip()
    if m in ("","HOT","STAT"):
        if p in ("П1","X","П2"): m="1X2"
        elif p in ("ТБ 2.5","ТМ 2.5"): m="OU"
        elif p.startswith("Ф"): m="AH"
        elif p.startswith("BTTS"): m="BTTS"
        elif p in ("1X","X2","12"): m="DC"
        else: return None
    if m=="1X2":
        res="П1" if hg>ag else ("X" if hg==ag else "П2")
        return "won" if res==p else "lost"
    if m=="OU":
        if p=="ТБ 2.5": return "won" if hg+ag>=3 else "lost"
        if p=="ТМ 2.5": return "won" if hg+ag<=2 else "lost"
        return None
    if m=="AH":
        s=settle_ah(p,hg,ag)
        if s is None: return None
        return "push" if s=="push" else ("won" if s else "lost")
    if m=="BTTS":
        both=(hg>0 and ag>0)
        return "won" if (both==(p=="BTTS да")) else "lost"
    if m=="DC":
        if p=="1X": ok=hg>=ag
        elif p=="X2": ok=hg<=ag
        elif p=="12": ok=hg!=ag
        else: return None
        return "won" if ok else "lost"
    return None
def kelly(prob,odds,bank,frac):
    if prob<=0 or odds<=1: return 0.0
    b=odds-1; k=(b*prob-(1-prob))/b
    return round(min(max(0,k*frac),0.05)*bank,2)
def odd1(row,keys):
    for k in keys:
        v=_f(row.get(k))
        if v and v>1.01: return v
    return None
ODD_KEYS={"П1":["MaxH","B365H","PSH"],"X":["MaxD","B365D","PSD"],"П2":["MaxA","B365A","PSA"],
          "ТБ 2.5":["Max>2.5","B365>2.5","P>2.5"],"ТМ 2.5":["Max<2.5","B365<2.5","P<2.5"]}
def best_odd(row,pick): return odd1(row,ODD_KEYS.get(pick,[]))
def market_probs(row):
    ph,px,pa=_f(row.get("PSH")),_f(row.get("PSD")),_f(row.get("PSA"))
    if not(ph and px and pa): return None
    i1,ix,ia=1/ph,1/px,1/pa; s=i1+ix+ia
    return (i1/s,ix/s,ia/s)
def clv_for(pick,odd,mkt,row):
    if not odd: return None
    if mkt:
        idx={"П1":0,"X":1,"П2":2}.get(pick)
        if idx is not None: return odd*mkt[idx]-1
    if row is None: return None
    if pick.startswith("Ф1") or pick.startswith("Ф2"):
        po=_f(row.get("PAHH")) if pick.startswith("Ф1") else _f(row.get("PAHA"))
        ot=_f(row.get("PAHA")) if pick.startswith("Ф1") else _f(row.get("PAHH"))
        if po and ot:
            i1,i2=1/po,1/ot; s=i1+i2; return odd*(i1/s)-1
        return None
    po=_f(row.get("PS>2.5")) if pick=="ТБ 2.5" else (_f(row.get("PS<2.5")) if pick=="ТМ 2.5" else None)
    ot=_f(row.get("PS<2.5")) if pick=="ТБ 2.5" else (_f(row.get("PS>2.5")) if pick=="ТМ 2.5" else None)
    if po and ot:
        i1,i2=1/po,1/ot; s=i1+i2; return odd*(i1/s)-1
    return None
def blend_market(P,mkt,w):
    if not mkt: return P
    P=dict(P)
    P["p1"]=(1-w)*P["p1"]+w*mkt[0]; P["x"]=(1-w)*P["x"]+w*mkt[1]; P["p2"]=(1-w)*P["p2"]+w*mkt[2]
    t=P["p1"]+P["x"]+P["p2"] or 1.0
    P["p1"]/=t; P["x"]/=t; P["p2"]/=t; P["mkt"]=mkt
    return P

# ============= LLM RISK LAYER =============
def llm_gemini(prompt,key):
    url=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    body={"contents":[{"parts":[{"text":prompt}]}],
          "generationConfig":{"temperature":0.2,"responseMimeType":"application/json"}}
    r=_sess.post(url,json=body,timeout=25)
    if r.status_code!=200: return None
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
def llm_grok(prompt,key):
    url="https://api.x.ai/v1/chat/completions"
    hdr={"Authorization":f"Bearer {key}","Content-Type":"application/json"}
    body={"model":"grok-2-latest","messages":[{"role":"user","content":prompt}],"temperature":0.2}
    r=_sess.post(url,json=body,headers=hdr,timeout=25)
    if r.status_code!=200: return None
    return r.json()["choices"][0]["message"]["content"]
def build_risk_prompt(ctx):
    return ("Ты риск-аналитик футбольных ставок. Оцени РИСК проигрыша рекомендуемого исхода.\n"
            f"Матч: {ctx['home']} vs {ctx['away']} ({ctx['league']}).\n"
            f"Рекомендуемый исход: {ctx['pick']} @ {ctx['odd']:.2f}, наша вероятность {ctx['prob']*100:.0f}%.\n"
            f"H2H последние: {ctx['h2h']}.\nФорма хозяев: {ctx['fh']}, гостей: {ctx['fa']}.\n"
            f"xG модели: {ctx['lh']:.2f}-{ctx['la']:.2f}. Отдых: хозяева {ctx['rh']} дн, гости {ctx['ra']} дн.\n"
            f"Рыночная вероятность: {ctx['mkt_p']*100:.0f}% (расхождение {ctx['gap']*100:.0f} п.п.). Выборка: {ctx['games']} матчей.\n"
            "Верни ТОЛЬКО JSON: {\"risk_pick\":0-100,\"confidence\":0-100,\"veto\":true/false,"
            "\"veto_reason\":\"...\",\"key_factors\":[\"...\"],\"summary\":\"1-2 предложения\"}")
def llm_risk(ctx,meta):
    prompt=build_risk_prompt(ctx)
    for fn,key in ((llm_gemini,meta.get("gemini_key","")),(llm_grok,meta.get("grok_key",""))):
        if not key: continue
        try:
            txt=fn(prompt,key)
            if txt:
                d=json.loads(txt)
                return {"source":fn.__name__,"risk":int(d.get("risk_pick",50)),
                        "conf":int(d.get("confidence",50)),"veto":bool(d.get("veto",False)),
                        "veto_reason":d.get("veto_reason",""),"factors":d.get("key_factors",[]),
                        "summary":d.get("summary","")}
        except Exception as e:
            log_err("llm",e)
    return None
def heuristic_risk(ctx):
    r=30
    r+=max(0,(0.60-ctx["prob"])*100)
    r+=(1 if ctx["games"]<5 else 0)*15
    r+=max(0,(ctx["rh"]-ctx["ra"]))*3
    r+=ctx["gap"]*30
    return {"source":"heuristic","risk":int(max(5,min(95,r))),"conf":40,
            "veto":(ctx["games"]<4),"veto_reason":"мало данных" if ctx["games"]<4 else "",
            "factors":[],"summary":"Эвристическая оценка (LLM недоступен)."}

# ============= LIVE MODEL =============
DEFAULT_LIVE={"alpha":1.5,"beta":TOTAL_MIN,"temp":1.0,"signals":[],"league_pace":{},"n_learned":0}
def load_live_model():
    try:
        if os.path.exists(LIVE_MODEL_FILE):
            with open(LIVE_MODEL_FILE,"r",encoding="utf-8") as f: d=json.load(f)
            for k in DEFAULT_LIVE: d.setdefault(k,DEFAULT_LIVE[k])
            return d
    except Exception as e: log_err("load_live_model",e)
    return dict(DEFAULT_LIVE)
def save_live_model(m):
    try:
        with open(LIVE_MODEL_FILE,"w",encoding="utf-8") as f: json.dump(m,f,ensure_ascii=False,indent=2)
    except Exception as e: log_err("save_live_model",e)
def live_predict(minute,cur_total,base_lam,league=None,pressure=None,live_model=None):
    if live_model is None: live_model=load_live_model()
    alpha=float(live_model.get("alpha",1.5)); beta=float(live_model.get("beta",TOTAL_MIN))
    temp=float(live_model.get("temp",1.0))
    minute_f=max(1.0,float(minute)); remaining=max(1.0,TOTAL_MIN-minute_f)
    pace=league and live_model.get("league_pace",{}).get(league)
    lam_pace=pace[0]/pace[1] if pace else (base_lam/TOTAL_MIN)
    lam_post=(alpha+cur_total)/(beta+minute_f)
    k=(lam_post/lam_pace) if lam_pace>0.001 else 1.0
    k=max(0.4,min(3.0,k))
    if pressure is not None and pressure>0: k*=min(1.5,max(0.6,1.0+0.3*pressure))
    lam_rem=lam_pace*remaining*k
    p_goal=1.0-math.exp(-lam_rem/max(0.3,temp))
    return {"p_goal":p_goal,"proj_total":cur_total+lam_rem,"lam_rem":lam_rem,"pace":lam_pace*TOTAL_MIN,"k":k}
def live_learn_step(minute,cur_total,final_total,league=None,live_model=None):
    if live_model is None: live_model=load_live_model()
    alpha=float(live_model.get("alpha",1.5)); beta=float(live_model.get("beta",TOTAL_MIN))
    minute_f=max(1.0,float(minute))
    if final_total>cur_total: alpha+=final_total-cur_total
    beta+=TOTAL_MIN-minute_f
    live_model["alpha"]=min(alpha,50.0); live_model["beta"]=min(beta,50.0*TOTAL_MIN)
    if league:
        lp=live_model.setdefault("league_pace",{})
        lp.setdefault(league,[0.0,0.0]); lp[league][0]+=final_total; lp[league][1]+=TOTAL_MIN
    live_model["n_learned"]=int(live_model.get("n_learned",0))+1
    return live_model
def live_refit_temp(live_model,window=500):
    sigs=[s for s in live_model.get("signals",[]) if s.get("had_goal") is not None][-window:]
    if len(sigs)<20: return live_model
    def nll(T):
        s=0.0
        for sig in sigs:
            p=min(max(sig.get("p_goal",0.5),1e-6),1-1e-6)
            p_c=1.0/(1.0+math.exp(-math.log(p/(1-p))/max(0.3,T)))
            y=1.0 if sig.get("had_goal") else 0.0
            s-=math.log(min(max(p_c if y>0.5 else 1-p_c,1e-9),1-1e-9))
        return s
    best_T,best_ll=live_model.get("temp",1.0),nll(live_model.get("temp",1.0))
    T=0.5
    while T<=3.0001:
        ll=nll(T)
        if ll<best_ll-1e-9: best_ll,best_T=ll,T
        T+=0.05
    lo=max(0.5,best_T-0.05); hi=min(3.0,best_T+0.05); T=lo
    while T<=hi+1e-9:
        ll=nll(T)
        if ll<best_ll-1e-9: best_ll,best_T=ll,T
        T+=0.005
    live_model["temp"]=min(max(best_T,0.5),3.0)
    return live_model
def live_stats(live_model):
    sigs=live_model.get("signals",[])
    fin=[s for s in sigs if s.get("had_goal") is not None]
    total=len(fin)
    if total<5: return {"n":total,"hit_rate":None,"brier":None,"cal":[],"by_league":{}}
    hits=sum(1 for s in fin if s.get("had_goal"))
    brier=sum((s.get("p_goal",0.5)-(1.0 if s.get("had_goal") else 0.0))**2 for s in fin)/total
    cal=[]
    for lo,hi in [(0.3,0.5),(0.5,0.65),(0.65,0.80),(0.80,1.01)]:
        b=[s for s in fin if lo<=s.get("p_goal",0)<hi]
        if len(b)>=3:
            wr=sum(1 for s in b if s.get("had_goal"))/len(b)*100
            avg=sum(s.get("p_goal",0) for s in b)/len(b)*100
            cal.append({"bin":f"{lo*100:.0f}–{hi*100:.0f}%","n":len(b),"pred":f"{avg:.1f}%","fact":f"{wr:.1f}%"})
    by={}
    for s in fin:
        lg=s.get("league") or "—"; by.setdefault(lg,{"n":0,"hits":0}); by[lg]["n"]+=1
        if s.get("had_goal"): by[lg]["hits"]+=1
    for lg in by: by[lg]["hr"]=by[lg]["hits"]/by[lg]["n"]*100
    return {"n":total,"hit_rate":hits/total*100,"brier":brier,"cal":cal,"by_league":by}
def api_football_live(api_key,league_ids):
    if not api_key: return [],["API-Football: ключ не задан"]
    out=[]; rep=[]
    headers={"x-apisports-key":api_key,"x-rapidapi-host":"v3.football.api-sports.io"}
    for lid in league_ids:
        try:
            r=_sess.get(f"https://v3.football.api-sports.io/fixtures?live=all&league={lid}",headers=headers,timeout=15)
            if r.status_code!=200: rep.append(f"API {API_NAMES.get(lid,lid)}: HTTP {r.status_code}"); continue
            n=0
            for f in (r.json() or {}).get("response") or []:
                fix=f.get("fixture") or {}; teams=f.get("teams") or {}; goals=f.get("goals") or {}
                stat={"home":{},"away":{}}
                for side,stt in zip(("home","away"),f.get("statistics") or []):
                    for val in stt.get("statistics") or []: stat[side][val.get("type")]=val.get("value")
                out.append({"league":API_NAMES.get(lid,str(lid)),"fixture_id":fix.get("id"),
                            "home":(teams.get("home") or {}).get("name"),"away":(teams.get("away") or {}).get("name"),
                            "home_score":goals.get("home") or 0,"away_score":goals.get("away") or 0,
                            "minute":fix.get("status",{}).get("elapsed") or 0,"stats":stat})
                n+=1
            rep.append(f"API {API_NAMES.get(lid,lid)}: {n} live")
        except Exception as e:
            log_err(f"api_live {lid}",e); rep.append(f"API {API_NAMES.get(lid,lid)}: {type(e).__name__}")
    return out,rep
def api_football_fixture(api_key,fixture_id):
    if not api_key: return None
    try:
        headers={"x-apisports-key":api_key,"x-rapidapi-host":"v3.football.api-sports.io"}
        r=_sess.get(f"https://v3.football.api-sports.io/fixtures?id={fixture_id}",headers=headers,timeout=15)
        data=(r.json() or {}).get("response") or []
        if not data: return None
        f=data[0]; fix=f.get("fixture") or {}; goals=f.get("goals") or {}
        return {"finished":(fix.get("status") or {}).get("short") in ("FT","AET","PEN"),
                "home":goals.get("home") or 0,"away":goals.get("away") or 0}
    except Exception as e:
        log_err(f"api_fix {fixture_id}",e); return None

# ============= ENGINE =============
class Engine:
    def __init__(self):
        self.elo={}; self.st=defaultdict(_new_team); self.hg=[]; self.ag=[]; self.hsth=[]; self.hsta=[]
        self.h2h=defaultdict(list); self.calib=[]; self.temp=1.0
        self.lp=defaultdict(_new_lp); self.hist=defaultdict(list); self.ml_w={}; self.ml_hist=defaultdict(list)
        self.match_count=0; self.market_roi=defaultdict(_new_roi); self.last_match_date={}
    @staticmethod
    def _logit(p):
        p=min(max(p,1e-6),1-1e-6); return math.log(p/(1-p))
    @staticmethod
    def _sigmoid(x): return 1.0/(1.0+math.exp(-max(-30,min(30,x))))
    def _m(self,l,d=1.0): return sum(l)/len(l) if l else d
    def _p(self,l,k): return math.exp(-l)*l**k/math.factorial(k)
    def _form(self,t):
        f=self.st[t]["form"][-5:]; return (sum(f)/(len(f)*3)) if f else 0.5
    def form_str(self,t):
        out=""
        for x in self.st[t]["form"][-5:]: out+={"3":"В","1":"Н","0":"П"}[str(int(x))]
        return out or "—"
    def calibrate(self,p): return self._sigmoid(self._logit(p)/self.temp)
    def _nll_T(self,data,T):
        s=0.0; inv=1.0/T
        for z,y in data:
            p=self._sigmoid(z*inv); s-=math.log(min(max(p if y>0.5 else 1-p,1e-9),1-1e-9))
        return s
    def refit_temp(self):
        if len(self.calib)<60: return
        data=self.calib[-3000:]; best_T,best_ll=self.temp,self._nll_T(data,self.temp); T=0.5
        while T<=3.0001:
            ll=self._nll_T(data,T)
            if ll<best_ll-1e-9: best_ll,best_T=ll,T
            T+=0.05
        lo=max(0.5,best_T-0.05); hi=min(3.0,best_T+0.05); T=lo
        while T<=hi+1e-9:
            ll=self._nll_T(data,T)
            if ll<best_ll-1e-9: best_ll,best_T=ll,T
            T+=0.005
        self.temp=min(max(best_T,0.5),3.0)
    def _p1px(self,lh,la,rho):
        N=MATRIX_N
        M=[[self._p(lh,i)*self._p(la,j) for j in range(N)] for i in range(N)]
        tau={(0,0):1+lh*la*rho,(1,0):1-la*rho,(0,1):1-lh*rho,(1,1):1+rho}
        for i in range(N):
            for j in range(N):
                if (i,j) in tau: M[i][j]*=tau[(i,j)]
        tot=sum(map(sum,M)) or 1.0; M=[[v/tot for v in r] for r in M]
        p1=sum(M[i][j] for i in range(N) for j in range(N) if i>j); px=sum(M[i][i] for i in range(N))
        return p1,px,M
    def _probs_from(self,lh,la,rho,w,e,pde):
        p1,px,_=self._p1px(lh,la,rho); f1=w*p1+(1-w)*e*(1-pde); fd=w*px+(1-w)*pde
        return f1,fd,max(1e-6,1-f1-fd)
    def _loglik(self,rows,rho,w):
        ll=0.0
        for lh,la,e,pde,out in rows:
            f1,fd,f2=self._probs_from(lh,la,rho,w,e,pde)
            ll-=math.log(min(max((f1,fd,f2)[out],1e-6),1-1e-6))
        return ll
    def _fit_league(self,lg):
        win=self.hist[lg][-400:]
        if len(win)<200: return
        split=int(len(win)*0.8); train,hold=win[:split],win[split:]
        cur=self.lp[lg]; best_ws=None
        for ws in (0.20,0.35,0.50):
            rows=[((1-ws)*gh+ws*sh,(1-ws)*ga+ws*sa,e,pde,out) for gh,ga,sh,sa,e,pde,out in train]
            ll=self._loglik(rows,cur["rho"],cur["w_dc"])
            if best_ws is None or ll<best_ws[0]: best_ws=(ll,ws)
        ws_pick=best_ws[1]
        tr=[((1-ws_pick)*gh+ws_pick*sh,(1-ws_pick)*ga+ws_pick*sa,e,pde,out) for gh,ga,sh,sa,e,pde,out in train]
        ho=[((1-ws_pick)*gh+ws_pick*sh,(1-ws_pick)*ga+ws_pick*sa,e,pde,out) for gh,ga,sh,sa,e,pde,out in hold]
        best=None
        for rho in (-0.20,-0.13,-0.06,0.0):
            for w in (0.60,0.72,0.85):
                ll=self._loglik(tr,rho,w)
                if best is None or ll<best[0]: best=(ll,rho,w)
        if ho and self._loglik(ho,best[1],best[2])>self._loglik(ho,cur["rho"],cur["w_dc"]): return
        cur["w_shots"]=ws_pick; cur["rho"],cur["w_dc"]=best[1],best[2]
    @staticmethod
    def _softmax(sc):
        m=max(sc); ex=[math.exp(s-m) for s in sc]; t=sum(ex) or 1.0
        return tuple(v/t for v in ex)
    def _ml_probs(self,lg,feat):
        W=self.ml_w.get(lg)
        if not W: return (1/3,1/3,1/3)
        return self._softmax([sum(w*x for w,x in zip(W[c],feat)) for c in range(3)])
    def _ml_nll(self,W,rows):
        s=0.0
        for feat,out in rows:
            p=self._softmax([sum(w*x for w,x in zip(W[c],feat)) for c in range(3)])[out]
            s-=math.log(min(max(p,1e-6),1-1e-6))
        return s
    def _fit_ml(self,lg):
        data=self.ml_hist[lg][-ML_WINDOW:]
        if len(data)<ML_REFIT_MIN: return
        split=int(len(data)*0.8); train,hold=data[:split],data[split:]
        old=self.ml_w.get(lg); W=[row[:] for row in old] if old else [[0.0]*NFEAT_ML for _ in range(3)]
        n=max(1,len(train))
        for _ in range(ML_ITERS):
            grad=[[0.0]*NFEAT_ML for _ in range(3)]
            for feat,out in train:
                pr=self._softmax([sum(w*x for w,x in zip(W[c],feat)) for c in range(3)])
                for c in range(3):
                    err=pr[c]-(1.0 if c==out else 0.0)
                    for k in range(NFEAT_ML): grad[c][k]+=err*feat[k]
            for c in range(3):
                for k in range(NFEAT_ML): W[c][k]-=ML_LR*(grad[c][k]/n+ML_L2*W[c][k])
        if hold:
            if self._ml_nll(W,hold)>(self._ml_nll(old,hold) if old else float("inf")): return
        self.ml_w[lg]=W
    def record_market(self,mkt,won,odd):
        r=self.market_roi[mkt]; r["n"]+=1; r["profit"]=0.9*r["profit"]+0.1*((odd-1) if won else -1)
    def market_adjust(self,mkt):
        r=self.market_roi.get(mkt)
        if not r or r["n"]<40: return 0.0
        return max(-0.010,min(0.020,-r["profit"]*0.4))
    def add(self,h,a,hg,ag,row=None,k=None,match_num=None,total=None,match_date=None):
        if k is None:
            prog=min(1.0,match_num/total) if (match_num is not None and total) else 0.5
            k=16+32*prog
        rh,ra=self.elo.get(h,1500),self.elo.get(a,1500)
        eh=1/(1+10**((ra-(rh+60))/400)); s=1.0 if hg>ag else (0.5 if hg==ag else 0.0)
        self.elo[h]=rh+k*(s-eh); self.elo[a]=ra+k*((1-s)-(1-eh))
        t=self.st
        t[h]["hs"].append(hg); t[h]["hc"].append(ag); t[a]["as"].append(ag); t[a]["ac"].append(hg)
        t[h]["form"].append(3 if hg>ag else (1 if hg==ag else 0))
        t[a]["form"].append(3 if ag>hg else (1 if hg==ag else 0))
        self.hg.append(hg); self.ag.append(ag)
        self.h2h[(h,a)].append(hg-ag); self.h2h[(h,a)]=self.h2h[(h,a)][-8:]
        if row:
            for col,t1,k1,t2,k2 in (("HC",h,"cfh",a,"caa"),("AC",a,"cfa",h,"cah"),("HY",h,"yfh",a,"yaa"),("AY",a,"yfa",h,"yah")):
                v=_f(row.get(col))
                if v is not None: t[t1][k1].append(v); t[t2][k2].append(v)
            hst,ast=_f(row.get("HST")),_f(row.get("AST"))
            if hst is not None and ast is not None:
                t[h]["hst_h"].append(hst); t[h]["hstc_h"].append(ast); t[a]["hst_a"].append(ast); t[a]["hstc_a"].append(hst)
                self.hsth.append(hst); self.hsta.append(ast)
        for team in (h,a):
            for key in t[team]: t[team][key]=t[team][key][-12:]
        for pool in (self.hg,self.ag,self.hsth,self.hsta):
            if len(pool)>4000: del pool[:-4000]
        if match_date:
            self.last_match_date[h]=match_date; self.last_match_date[a]=match_date
    def h2h_adjust(self,h,a,lh,la):
        hist=self.h2h.get((h,a),[]); n=len(hist)
        if n<5: return lh,la,n
        shrink=min(1.0,(n-4)/6.0); shift=(sum(hist)/n)*0.08*shrink
        return max(0.3,lh+shift/2),max(0.25,la-shift/2),n
    def predict(self,h,a,lg="G",match_date=None,cup=False):
        P0=self.lp[lg]; ws=P0["w_shots"]
        lh_g=max(0.05,self._m(self.hg,1.5)); la_g=max(0.05,self._m(self.ag,1.2))
        lh_s=max(0.05,self._m(self.hsth,4.5)); la_s=max(0.05,self._m(self.hsta,4.0))
        sh,sa=self.st[h],self.st[a]
        ah_=self._m(sh["hs"],lh_g)/lh_g; dh_=self._m(sh["hc"],la_g)/la_g
        aa_=self._m(sa["as"],la_g)/la_g; da_=self._m(sa["ac"],lh_g)/lh_g
        fh,fa=self._form(h),self._form(a)
        lam_g_h=max(0.3,min(5.0,lh_g*ah_*da_*1.10*(0.85+0.30*fh)))
        lam_g_a=max(0.25,min(4.5,la_g*aa_*dh_*0.95*(0.85+0.30*fa)))
        conv_h=lh_g/max(0.5,lh_s); conv_a=la_g/max(0.5,la_s)
        ash_h=self._m(sh["hst_h"],lh_s)/lh_s; dsh_a=self._m(sa["hstc_a"],lh_s)/lh_s
        ash_a=self._m(sa["hst_a"],la_s)/la_s; dsh_h=self._m(sh["hstc_h"],la_s)/la_s
        lam_s_h=max(0.3,min(5.0,lh_s*conv_h*ash_h*dsh_a*(0.85+0.30*fh)))
        lam_s_a=max(0.25,min(4.5,la_s*conv_a*ash_a*dsh_h*(0.85+0.30*fa)))
        lam_h=(1-ws)*lam_g_h+ws*lam_s_h; lam_a=(1-ws)*lam_g_a+ws*lam_s_a
        if cup: lam_h=max(0.3,lam_h-0.15); lam_a=max(0.25,lam_a-0.15)
        lam_h,lam_a,h2h_n=self.h2h_adjust(h,a,lam_h,lam_a)
        agree=(lam_h-lam_a)*(lam_g_h-lam_g_a)>0
        e=1/(1+10**((self.elo.get(a,1500)-self.elo.get(h,1500)-60)/400))
        pde=0.20+0.12*(1-abs(e-0.5)*2)
        p1,px,M=self._p1px(lam_h,lam_a,P0["rho"])
        f1=P0["w_dc"]*p1+(1-P0["w_dc"])*e*(1-pde); fd=P0["w_dc"]*px+(1-P0["w_dc"])*pde; f2=max(0.0,1-f1-fd)
        elo_diff=self.elo.get(h,1500)-self.elo.get(a,1500)
        games=min(len(sh["hs"])+len(sh["as"]),len(sa["hs"])+len(sa["as"]))
        ref=match_date or datetime.now()
        rest_h=(ref-self.last_match_date[h]).days if h in self.last_match_date else 14
        rest_a=(ref-self.last_match_date[a]).days if a in self.last_match_date else 14
        rest_h=max(1,min(rest_h,60)); rest_a=max(1,min(rest_a,60))
        sr_h=(sum(sh["hst_h"][-5:])/max(1,sum(sh["hc"][-5:]))) if len(sh["hst_h"])>=3 else 1.5
        sr_a=(sum(sa["hst_a"][-5:])/max(1,sum(sa["ac"][-5:]))) if len(sa["hst_a"])>=3 else 1.5
        f3_h=sum(sh["form"][-3:])/max(1,len(sh["form"][-3:]))/3.0
        f3_a=sum(sa["form"][-3:])/max(1,len(sa["form"][-3:]))/3.0
        momentum=(f3_h-fh)-(f3_a-fa)
        feats=[1.0,elo_diff/400.0,lam_g_h-lam_g_a,lam_s_h-lam_s_a,fh-fa,math.log(games+1),
               1.0,math.log(rest_h+1),math.log(rest_a+1),sr_h,sr_a,momentum]
        mp1,mx,mp2=self._ml_probs(lg,feats)
        n_tr=len(self.ml_hist.get(lg,[])); w_ml=P0.get("w_ml",0.25)*min(1.0,n_tr/300.0)
        if lg in self.ml_w and w_ml>0:
            f1=(1-w_ml)*f1+w_ml*mp1; fd=(1-w_ml)*fd+w_ml*mx; f2=(1-w_ml)*f2+w_ml*mp2
        tt=f1+fd+f2 or 1.0; f1,fd,f2=f1/tt,fd/tt,f2/tt
        raw=(f1,fd,f2)
        c1,cx,c2=self.calibrate(f1),self.calibrate(fd),self.calibrate(f2)
        ct=c1+cx+c2 or 1.0; c1,cx,c2=c1/ct,cx/ct,c2/ct
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
        self.calib+=[(self._logit(P["p1_raw"]),1.0 if out==0 else 0.0),
                     (self._logit(P["x_raw"]),1.0 if out==1 else 0.0),
                     (self._logit(P["p2_raw"]),1.0 if out==2 else 0.0)]
        if len(self.calib)>6000: del self.calib[:-6000]
        self.hist[lg].append((P["lams_g"][0],P["lams_g"][1],P["lams_s"][0],P["lams_s"][1],P["e"],P["pde"],out))
        if len(self.hist[lg])>1200: del self.hist[lg][:-1200]
        self.ml_hist[lg].append((P["ml_feats"],out))
        if len(self.ml_hist[lg])>1200: del self.ml_hist[lg][:-1200]
        if row:
            for mkt,pick,prob,odd,won in [("1X2","П1",P["p1"],_f(row.get("B365H")),hg>ag),
                   ("1X2","X",P["x"],_f(row.get("B365D")),hg==ag),("1X2","П2",P["p2"],_f(row.get("B365A")),hg<ag),
                   ("OU","ТБ 2.5",P["over"],_f(row.get("B365>2.5")),hg+ag>=3),("OU","ТМ 2.5",1-P["over"],_f(row.get("B365<2.5")),hg+ag<=2)]:
                if odd and odd>1.01: self.record_market(mkt,bool(won),odd)
        self.match_count+=1
        if self.match_count%REFIT_TEMP_EVERY==0: self.refit_temp()
        if len(self.hist[lg])%REFIT_STRUCT_EVERY==0: self._fit_league(lg); self._fit_ml(lg)
        self.add(h,a,hg,ag,row,match_num=match_num,total=total,match_date=match_date)
        return P
    def h2h_text(self,h,a):
        hist=self.h2h.get((h,a),[])[-5:]
        if not hist: return "нет данных"
        return ", ".join(f"{d:+.0f}" for d in hist)

def build_candidates(P,row,PR,blacklist=()):
    probs={"П1":P["p1"],"X":P["x"],"П2":P["p2"],"ТБ 2.5":P["over"],"ТМ 2.5":1-P["over"],
           "BTTS да":P["btts"],"BTTS нет":1-P["btts"],"1X":P["p1"]+P["x"],"X2":P["x"]+P["p2"],"12":P["p1"]+P["p2"]}
    cands=[]
    for pick,prob in probs.items():
        mkt="1X2" if pick in ("П1","X","П2") else ("OU" if pick.startswith("Т") else "STAT")
        if mkt in blacklist: continue
        cands.append((mkt,pick,prob,best_odd(row,pick) if pick in ODD_KEYS else None))
    ahh=_f(row.get("AHh")) if row else None
    if is_half_line(ahh) and "AH" not in blacklist:
        ohh=odd1(row,["MaxAHH","B365AHH","PAHH"]); oha=odd1(row,["MaxAHA","B365AHA","PAHA"])
        if ohh and oha:
            pc=sum(P["M"][i][j] for i in range(MATRIX_N) for j in range(MATRIX_N) if (i-j+ahh)>0.001)
            cands.append(("AH",f"Ф1({fmt_line(ahh)})",pc,ohh)); cands.append(("AH",f"Ф2({fmt_line(-ahh)})",1-pc,oha))
    return cands
def evaluate_rows(cands,P,mkt_probs,PR,engine,use_dis,row=None):
    rows=[]; best=None; hot=[]; card_clv=None; gap=None
    if mkt_probs: gap=max(abs(P["p1"]-mkt_probs[0]),abs(P["x"]-mkt_probs[1]),abs(P["p2"]-mkt_probs[2]))
    for mkt,pick,prob,odd in cands:
        item={"mkt":mkt,"pick":pick,"prob":prob,"odd":odd,"ev":None,"be":None,"ok":False}
        if odd:
            lo,hi=PR["corr"] if mkt=="1X2" else CORRIDORS.get(mkt,(1.4,4.2))
            ev=prob*odd-1; be=1/odd; edge=prob-be
            req=max(0.0,PR["ev"]+max(0.0,odd-2.5)*0.02+engine.market_adjust(mkt))
            dis_ok=(not use_dis) or (gap is None) or (gap>=DISAGREE_MIN)
            agree_ok=(mkt!="1X2") or P["agree"]
            games_ok=P["games"]>=PR["min_games"]
            item.update(ev=ev,be=be,ok=(lo<=odd<=hi and edge>=PR["edge"] and ev>=req and dis_ok and agree_ok and games_ok))
            if item["ok"]:
                stk=kelly(prob,odd,PR["bank"],PR["kelly"])
                if best is None or ev>best[3]: best=(mkt,pick,odd,ev,prob,stk); card_clv=clv_for(pick,odd,mkt_probs,row)
        if prob>=PR["thr"]: hot.append((pick,prob,odd))
        rows.append(item)
    hot.sort(key=lambda x:-x[1])
    return rows,best,hot,card_clv,gap
def backtest(div,season,PR,use_dis=True,stake_mode="Flat"):
    rows=[r for r in load_seasonal(div,season) if r.get("FTHG") not in (None,"") and r.get("FTAG") not in (None,"") and parse_date(r.get("Date",""))]
    rows.sort(key=lambda r: parse_date(r["Date"]))
    eng=Engine(); log=[]; bank=10000.0
    for j,r in enumerate(rows):
        h=(r.get("HomeTeam") or "").strip(); a=(r.get("AwayTeam") or "").strip()
        try: hg,ag=float(r["FTHG"]),float(r["FTAG"])
        except Exception as e: log_err("bt parse",e); continue
        md=parse_date(r.get("Date",""))
        try:
            P=eng.predict(h,a,div,match_date=md,cup=is_cup(r)); mkt=market_probs(r); Pb=blend_market(P,mkt,PR["w_market"])
            if j>=BACKTEST_WARMUP:
                cands=build_candidates(Pb,r,PR)
                rows_ev,best,hot,clv,gap=evaluate_rows(cands,Pb,mkt,PR,eng,use_dis,row=r)
                for item in rows_ev:
                    if not item["ok"] or not item["odd"]: continue
                    res=determine_outcome(item["mkt"],item["pick"],hg,ag)
                    if res in (None,"push"): continue
                    won=(res=="won"); st_=1.0
                    if stake_mode=="Kelly": st_=max(1.0,kelly(item["prob"],item["odd"],bank,0.25))
                    pnl=st_*(item["odd"]-1) if won else -st_; bank+=pnl
                    log.append({"mkt":item["mkt"],"prob":item["prob"],"odd":item["odd"],"won":won,"stake":st_,"pnl":pnl,"clv":clv_for(item["pick"],item["odd"],mkt,r)})
        except Exception as e: log_err("bt loop",e)
        try: eng.learn_step(h,a,hg,ag,r,lg=div,match_num=j,total=len(rows),match_date=md)
        except Exception as e: log_err("bt learn",e)
    return log,eng
def find_season():
    for s in ["2627","2526","2425"]:
        try:
            r=_sess.head(f"https://www.football-data.co.uk/mmz4281/{s}/E0.csv",timeout=8)
            if r.status_code==200: return s
        except Exception as e: log_err("find_season",e)
    return "2526"
def prev_season(s):
    try: return f"{int(s[:2])-1:02d}{int(s[2:])-1:02d}"
    except Exception: return s
def load_seasonal(div,season):
    try:
        r=_sess.get(f"https://www.football-data.co.uk/mmz4281/{season}/{div}.csv",timeout=20,headers=UA)
        if r.status_code!=200: return []
        return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    except Exception as e: log_err(f"load_seasonal {div}",e); return []
def load_many(divs,season):
    with ThreadPoolExecutor(max_workers=8) as ex: return dict(zip(divs,ex.map(lambda d: load_seasonal(d,season),divs)))
def load_fixtures():
    rep=[]; rows=[]; seen=set()
    for u in ["https://www.football-data.co.uk/mmz4281/fixtures.csv","https://www.football-data.co.uk/fixtures.csv"]:
        try:
            r=_sess.get(u,timeout=25,headers=UA)
            if r.status_code!=200: rep.append(f"{u.split('/')[-1]}: HTTP {r.status_code}"); continue
            rd=list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")))); n=0
            for x in rd:
                k=(x.get("Div"),x.get("Date"),x.get("HomeTeam"),x.get("AwayTeam"))
                if k in seen or not x.get("HomeTeam"): continue
                seen.add(k); rows.append(x); n+=1
            rep.append(f"{u.split('/')[-1]}: OK,{n}")
            if n: break
        except Exception as e: log_err("load_fixtures",e); rep.append(f"{u.split('/')[-1]}: {type(e).__name__}")
    return rows,rep
def load_livescores():
    try:
        r=_sess.get("https://www.thesportsdb.com/api/v1/json/3/livescore.php?s=Soccer",timeout=10)
        out={}
        for e in (r.json() or {}).get("events") or []:
            hk=re.sub(r"[^a-zа-я0-9]","",(e.get("strHomeTeam","") or "").lower())
            ak=re.sub(r"[^a-zа-я0-9]","",(e.get("strAwayTeam","") or "").lower())
            out[(hk,ak)]={"home":e.get("intHomeScore"),"away":e.get("intAwayScore"),
                          "home_name":e.get("strHomeTeam",""),"away_name":e.get("strAwayTeam",""),
                          "status":(e.get("strStatus") or "").strip(),"progress":(e.get("strProgress") or "").strip(),
                          "league":e.get("strLeague") or ""}
        return out
    except Exception as e: log_err("livescores",e); return {}
def match_live(live,home,away):
    if not live: return None
    hk=re.sub(r"[^a-zа-я0-9]","",(home or "").lower()); ak=re.sub(r"[^a-zа-я0-9]","",(away or "").lower())
    for (lh,la),v in live.items():
        if (lh==hk and la==ak) or (hk in lh and ak in la) or (lh in hk and la in ak): return v
    return None
FINISHED_STATUSES={"match finished","ft","aet","ap","finished","full time"}
def engine_fingerprint(season,div_counts): return (ENGINE_CACHE_VERSION,season,tuple(sorted(div_counts.items())))
def engine_cache_get(fp):
    try:
        with open(ENGINE_CACHE,"rb") as f: d=pickle.load(f)
        if d.get("fp")==fp: return d.get("engine")
    except Exception as e: log_err("cache_get",e)
    return None
def engine_cache_put(fp,eng):
    try:
        with open(ENGINE_CACHE,"wb") as f: pickle.dump({"fp":fp,"engine":eng},f)
    except Exception as e: log_err("cache_put",e)

def new_data():
    return {"version":3,"bank":10000.0,"bets":[],"cards":[],"picks":[],"funnel":None,"report":[],
            "meta":{},"stats":{"won":0,"lost":0,"profit":0,"push":0}}
def migrate(D):
    if not isinstance(D,dict): return new_data()
    base=new_data()
    for k,v in base.items():
        if k not in D or D[k] is None: D[k]=json.loads(json.dumps(v))
    D["version"]=3
    if not isinstance(D.get("cards"),list): D["cards"]=[]
    if not isinstance(D.get("picks"),list): D["picks"]=[]
    if D["cards"] and isinstance(D["cards"][0],dict) and "lams_g" not in D["cards"][0]: D["cards"]=[]; D["picks"]=[]
    if not isinstance(D.get("bets"),list): D["bets"]=[]
    D["bets"]=[b for b in D["bets"] if isinstance(b,dict) and all(k in b for k in ("match","pick","odds","stake","status"))]
    for b in D["bets"]: b.setdefault("strat","HOT" if b.get("market")=="HOT" else "VALUE")
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

if "data" not in st.session_state: st.session_state.data=load_data()
D=st.session_state.data
wall_key=D.get("meta",{}).get("wall","🌃 Неон-стадион")
if wall_key not in WALLS: wall_key="🌃 Неон-стадион"
WALL_CSS=WALLS[wall_key]

st.markdown("<style>"+"""
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@600;800&family=Inter:wght@400;600;800&display=swap');
@media (min-width: 992px){
 section[data-testid="stSidebar"]{visibility:visible!important;transform:none!important;width:320px!important;z-index:999!important;}
 section[data-testid="stSidebar"]>div{width:320px!important;overflow-y:auto!important;height:100vh!important;}
 button[kind="header"]{display:none!important;}
 section.main{margin-left:320px!important;}
}
@media (max-width: 991px){
 .stApp{display:flex;flex-direction:column;}
 section[data-testid="stSidebar"]{position:static!important;transform:none!important;visibility:visible!important;width:100%!important;order:-1;max-height:none!important;}
 section[data-testid="stSidebar"]>div{width:100%!important;}
 button[kind="header"]{display:none!important;}
}
html,body,#root,div[data-testid="stAppViewContainer"],div[data-testid="stAppViewContainer"]>div,section.main,.stApp{
 background: __WALL__ !important;background-attachment: fixed !important;}
.stMarkdown,.stMarkdown p,.stMarkdown li{color:#e6eaf2;font-family:'Inter',sans-serif;}
.stCaption,.stCaption *{color:#8b93a7 !important;}
div[data-testid="stMetricValue"]{color:#f8fafc !important;font-family:'Unbounded',sans-serif;font-size:1.3rem;}
div[data-testid="stMetricLabel"] p{color:#8b93a7 !important;}
header,#MainMenu,footer{visibility:hidden}
section[data-testid="stSidebar"]{background:rgba(8,11,20,.72);backdrop-filter:blur(18px);border-right:1px solid rgba(255,255,255,.07);}
section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] label,section[data-testid="stSidebar"] span{color:#e6eaf2 !important;}
section.stButton>button{background:linear-gradient(135deg,#0ea5e9 0%,#8b5cf6 55%,#ec4899 110%);color:#fff;border:none;border-radius:14px;font-weight:800;font-family:'Inter',sans-serif;box-shadow:0 8px 26px rgba(139,92,246,.35);transition:.18s;}
section.stButton>button:hover{transform:translateY(-2px);box-shadow:0 12px 34px rgba(14,165,233,.45);}
div[data-baseweb="select"]>div{background:rgba(255,255,255,.05)!important;border:1px solid rgba(255,255,255,.10)!important;border-radius:12px;}
.hero{padding:26px 30px;border-radius:26px;margin-bottom:18px;border:1px solid rgba(255,255,255,.10);background:linear-gradient(130deg,rgba(14,165,233,.20),rgba(139,92,246,.16) 45%,rgba(236,72,153,.14));backdrop-filter:blur(20px);}
.hero h1{margin:0;font-size:2.5rem;font-weight:800;font-family:'Unbounded',sans-serif;background:linear-gradient(92deg,#22d3ee,#a78bfa 50%,#f472b6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.hero p{margin:6px 0 0;color:#c9d2e3;font-size:.93rem}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:16px}
.kpi{background:rgba(255,255,255,.05);backdrop-filter:blur(14px);border:1px solid rgba(255,255,255,.10);border-radius:18px;padding:14px 16px;}
.kpi .t{color:#7dd3fc;font-size:.66rem;text-transform:uppercase;letter-spacing:1.4px;font-weight:700}
.kpi .v{font-size:1.5rem;font-weight:800;font-family:'Unbounded',sans-serif;color:#fff}
.kpi .v.g{color:#34d399}.kpi .v.y{color:#fbbf24}.kpi .v.r{color:#f87171}
.mcard{background:rgba(10,14,24,.72);backdrop-filter:blur(16px);border:1px solid rgba(255,255,255,.09);border-radius:20px;padding:18px 20px;margin-bottom:14px;transition:.2s;}
.mcard:hover{border-color:rgba(34,211,238,.45);}
.mcard.value{border-color:rgba(52,211,153,.55);}
.mcard.hot{border-color:rgba(251,191,36,.5);}
.mcard.live{border-color:rgba(248,113,113,.55);}
.chip{background:rgba(34,211,238,.14);color:#a5f3fc;border:1px solid rgba(34,211,238,.35);padding:3px 11px;border-radius:999px;font-size:.72rem;font-weight:700;margin-right:6px;}
.chip.when{background:rgba(251,191,36,.14);color:#fde68a;border-color:rgba(251,191,36,.4);}
.chip.warn{background:rgba(248,113,113,.15);color:#fecaca;border-color:rgba(248,113,113,.4);}
.chip.live{background:rgba(248,113,113,.2);color:#fecaca;border-color:rgba(248,113,113,.5);}
.badge{float:right;padding:4px 13px;border-radius:999px;font-size:.72rem;font-weight:800;}
.badge.val{background:linear-gradient(135deg,rgba(52,211,153,.25),rgba(16,185,129,.15));color:#6ee7b7;border:1px solid rgba(52,211,153,.6);}
.badge.hot{background:linear-gradient(135deg,rgba(251,191,36,.25),rgba(245,158,11,.15));color:#fde68a;border:1px solid rgba(251,191,36,.55);}
.badge.no{background:rgba(148,163,184,.12);color:#cbd5e1;border:1px solid rgba(148,163,184,.3);}
.badge.live{background:linear-gradient(135deg,rgba(248,113,113,.3),rgba(239,68,68,.18));color:#fecaca;border:1px solid rgba(248,113,113,.6);}
.teams{font-size:1.3rem;font-weight:800;color:#fff;margin:9px 0 3px;}
.teams span{color:#8b93a7;font-weight:400}
.verdict{background:rgba(34,211,238,.06);border:1px solid rgba(34,211,238,.22);border-radius:14px;padding:11px 15px;margin:9px 0;color:#e6eaf2;font-size:.88rem;}
.verdict b.y{color:#fbbf24}.verdict b.g{color:#34d399}.verdict b.r{color:#f87171}
.mrow{display:grid;grid-template-columns:70px 96px 70px 70px 62px 74px 26px;gap:8px;padding:6px 0;border-top:1px solid rgba(255,255,255,.07);font-size:.83rem;color:#e6eaf2;}
.ok{color:#34d399;font-weight:800}.nok{color:#64748b}
.evpos{color:#34d399;font-weight:700}.evneg{color:#f87171;font-weight:700}
.mfoot{margin-top:9px;color:#c9d2e3;font-size:.78rem;display:flex;gap:16px;flex-wrap:wrap;}
.mfoot b{color:#fbbf24}
.betcard{background:rgba(10,14,24,.72);backdrop-filter:blur(14px);border:1px solid rgba(255,255,255,.09);border-left:4px solid rgba(148,163,184,.4);border-radius:16px;padding:11px 15px;margin-bottom:9px;font-size:.87rem;color:#e6eaf2;}
.betcard.pending{border-left-color:#fbbf24}.betcard.won{border-left-color:#34d399}
.betcard.lost{border-left-color:#f87171}.betcard.push{border-left-color:#94a3b8}
.betcard .score{font-weight:900;padding:2px 10px;border-radius:9px;margin-left:6px;}
.betcard.won .score{background:rgba(52,211,153,.25);color:#6ee7b7}
.betcard.lost .score{background:rgba(248,113,113,.25);color:#fca5a5}
.side-link{display:block;padding:8px 12px;margin:3px 0;border-radius:10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);color:#e6eaf2 !important;text-decoration:none !important;font-size:.85rem;transition:.15s;}
.side-link:hover{background:rgba(34,211,238,.12);border-color:rgba(34,211,238,.4);}
.side-section{margin-top:18px;padding-top:14px;border-top:1px solid rgba(255,255,255,.08);}
.side-section h4{margin:0 0 8px 0;color:#7dd3fc;font-size:.72rem;text-transform:uppercase;letter-spacing:1.3px;font-weight:700;}
</style>""".replace("__WALL__",WALL_CSS), unsafe_allow_html=True)

def apply_settle(D,idx,outcome,score=None):
    D2=clone(D); b=D2["bets"][idx]
    if b["status"]!="pending": return D
    if score: b["score"]=score
    if outcome=="push":
        b["status"]="push"; D2["bank"]+=b["stake"]; D2["stats"]["push"]=D2["stats"].get("push",0)+1
    elif outcome=="won":
        pr=b["stake"]*(b["odds"]-1); b["status"]="won"; D2["bank"]+=b["stake"]+pr
        D2["stats"]["won"]+=1; D2["stats"]["profit"]+=pr
    else:
        b["status"]="lost"; D2["stats"]["lost"]+=1; D2["stats"]["profit"]-=b["stake"]
    return D2
def find_result(div,home,away,bd):
    if div in (None,"TSDB",""): return None
    season=find_season(); cands=[]
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
    D2=clone(D); b=D2["bets"][idx]
    new=determine_outcome(b.get("market"),b.get("pick"),hg,ag)
    if new is None: return D
    old=b.get("status","pending")
    if old=="won":
        pr=b["stake"]*(b["odds"]-1); D2["bank"]-=b["stake"]+pr; D2["stats"]["won"]=max(0,D2["stats"]["won"]-1); D2["stats"]["profit"]-=pr
    elif old=="lost":
        D2["bank"]+=b["stake"]; D2["stats"]["lost"]=max(0,D2["stats"]["lost"]-1); D2["stats"]["profit"]+=b["stake"]
    elif old=="push":
        D2["bank"]-=b["stake"]; D2["stats"]["push"]=max(0,D2["stats"].get("push",0)-1)
    b["status"]=new; b["score"]=score_str
    if new=="won":
        pr=b["stake"]*(b["odds"]-1); D2["bank"]+=b["stake"]+pr; D2["stats"]["won"]+=1; D2["stats"]["profit"]+=pr
    elif new=="lost":
        D2["bank"]-=b["stake"]; D2["stats"]["lost"]+=1; D2["stats"]["profit"]-=b["stake"]
    elif new=="push":
        D2["bank"]+=b["stake"]; D2["stats"]["push"]=D2["stats"].get("push",0)+1
    return D2
def _odd_s(rw):
    o=rw.get("odd")
    if o: return f"{o:.2f}"
    p=max(rw.get("prob") or 0.01,0.01)
    return f"фейр {1/p:.2f}"
def ai_verdict(c):
    rows=c.get("rows",[]); scored=sorted([r for r in rows if r.get("prob")],key=lambda r:-r["prob"])
    def prep(r):
        if not r: return None
        d=dict(r); d["odd_s"]=_odd_s(d); return d
    main=prep(scored[0]) if scored else None
    alt=prep(scored[1]) if len(scored)>1 else None
    x12=[r for r in rows if r["mkt"]=="1X2"]
    avoid=prep(min(x12,key=lambda r:r["prob"])) if x12 else None
    lg=c.get("lams_g",(0,0)); ls=c.get("lams_s",(0,0)); lh,la=c.get("lams",(0,0))
    parts=[f"xG {lg[0]:.2f}–{lg[1]:.2f} (голов), удары {ls[0]:.2f}–{ls[1]:.2f}; итог {lh:.2f}–{la:.2f}."]
    if c.get("fh","—")!="—": parts.append(f"Форма: {c['fh']} vs {c['fa']}.")
    if c.get("h2h_n",0)>=5: parts.append(f"H2H: {c['h2h_n']} встреч учтены.")
    m=c.get("mkt")
    if m:
        gap=max(abs(c.get("p1",0)-m[0]),abs(c.get("px",c.get("x",0))-m[1]),abs(c.get("p2",0)-m[2]))
        parts.append(f"Расхождение с рынком {gap*100:.0f} п.п.")
    if c.get("best"): parts.append(f"Вывод: {c['best'][1]} @ {c['best'][2]:.2f} (EV {c['best'][3]*100:+.1f}%).")
    elif c.get("hot"): parts.append(f"Высокая проходимость {c['hot'][0][0]} ({c['hot'][0][1]*100:.0f}%).")
    else: parts.append("Наблюдение.")
    return main,alt,avoid," ".join(parts)
def stars_for(rw,thr):
    if rw["ok"]:
        ev=rw["ev"]
        return "⭐⭐⭐⭐⭐" if ev>=0.10 else ("⭐⭐⭐⭐" if ev>=0.06 else "⭐⭐⭐")
    if rw["prob"]>=thr:
        return "⭐⭐⭐⭐⭐" if rw["prob"]>=0.70 else ("⭐⭐⭐⭐" if rw["prob"]>=0.65 else "⭐⭐⭐")
    return ""
def strat_stats(bets):
    out={}
    for s in ("VALUE","HOT"):
        sb=[b for b in bets if b.get("strat","VALUE")==s and b.get("status") in ("won","lost","push")]
        n=len(sb); w=sum(1 for b in sb if b["status"]=="won")
        pnl=sum(b["stake"]*(b["odds"]-1) if b["status"]=="won" else (0.0 if b["status"]=="push" else -b["stake"]) for b in sb)
        staked=sum(b["stake"] for b in sb if b["status"]!="push")
        out[s]=dict(n=n,w=w,pnl=pnl,roi=(pnl/staked*100 if staked else 0.0),wr=(w/n*100 if n else 0.0))
    return out
def calibration_rows(bets):
    settled=[b for b in bets if b.get("status") in ("won","lost") and b.get("prob")]
    rows=[]
    for lo,hi in [(0.40,0.50),(0.50,0.60),(0.60,0.70),(0.70,1.01)]:
        sb=[b for b in settled if lo<=b["prob"]<hi]
        if len(sb)>=3:
            wr=sum(1 for b in sb if b["status"]=="won")/len(sb)*100
            avgp=sum(b["prob"] for b in sb)/len(sb)*100
            rows.append({"Бин P":f"{lo*100:.0f}–{hi*100:.0f}%","Ставок":len(sb),"Предсказано":f"{avgp:.1f}%","Факт WR":f"{wr:.1f}%"})
    return rows
def weekly_rows(bets):
    wk=defaultdict(lambda:[0,0,0.0])
    for b in bets:
        if b.get("status") not in ("won","lost") or not b.get("date_iso"): continue
        d=parse_date(b["date_iso"])
        if not d: continue
        iso=d.isocalendar(); pnl=b["stake"]*(b["odds"]-1) if b["status"]=="won" else -b["stake"]
        wk[(iso[0],iso[1])][0]+=1; wk[(iso[0],iso[1])][1]+=1 if b["status"]=="won" else 0; wk[(iso[0],iso[1])][2]+=pnl
    return [{"Неделя":f"{y}-W{w:02d}","Ставок":v[0],"WR":f"{v[1]/v[0]*100:.0f}%","PnL":f"{v[2]:+.1f}"} for (y,w),v in sorted(wk.items())]
def card_sort_val(c,key):
    if key.startswith("По EV"):
        if c.get("best"): return c["best"][3]
        return max([r["ev"] for r in c["rows"] if r["ev"] is not None],default=-1)
    if key.startswith("По вероятности"): return max([r["prob"] for r in c["rows"]],default=0)
    if key.startswith("По дате"): return c.get("dt","9999-99-99")
    if key.startswith("По коэффициенту"):
        if c.get("best"): return c["best"][2]
        return max([r["odd"] for r in c["rows"] if r["odd"]],default=0)
    return c.get("league","")
def pick_sort_val(p,key):
    if key.startswith("По EV"): return p.get("ev") if p.get("ev") is not None else -1
    if key.startswith("По вероятности"): return p.get("prob",0)
    if key.startswith("По дате"): return p.get("dt","9999-99-99")
    if key.startswith("По коэффициенту"): return p.get("odd") or 0
    return p.get("league","")
def bet_sort_key(pair,key):
    i,b=pair
    if key.startswith("⏳"): return (0 if b["status"]=="pending" else 1, b.get("date_iso","9999"))
    if key.startswith("📅"): return b.get("date_iso","9999")
    if key.startswith("💰"): return b.get("stake",0)
    if key.startswith("📈"):
        if b["status"]=="won": return b["stake"]*(b["odds"]-1)
        if b["status"]=="lost": return -b["stake"]
        return 0.0
    return b.get("prob",0)
def render_match_card(c,thr,PR):
    val=c.get("best") is not None
    hot=any(r["prob"]>=thr for r in c["rows"]) and not val
    badge="<span class='badge val'>🟢 ВАЛУЙ</span>" if val else ("<span class='badge hot'>🔥 P≥"+str(int(thr*100))+"%</span>" if hot else "<span class='badge no'>фон</span>")
    chips=f"<span class='chip'>{esc(c['league'])}</span><span class='chip when'>📅 {esc(c['date'])} · {esc(c['when'])}</span>"
    if c["games"]<PR["min_games"]: chips+="<span class='chip warn'>⚠️ мало данных</span>"
    if c.get("cup"): chips+="<span class='chip warn'>🏆 Кубок</span>"
    main,alt,avoid,vtext=ai_verdict(c)
    m_s=f"✅ <b class='y'>{esc(main['pick'])}</b> @ {main['odd_s']} (P {main['prob']*100:.0f}%)" if main else ""
    a_s=f"🔁 <b class='g'>{esc(alt['pick'])}</b> (P {alt['prob']*100:.0f}%)" if alt else ""
    v_s=f"⛔ <b class='r'>{esc(avoid['pick'])}</b>" if avoid else ""
    rows_html=""
    for rw in c["rows"]:
        ev_s=f"<span class='{'evpos' if rw['ev']>0 else 'evneg'}'>{rw['ev']*100:+.1f}%</span>" if rw["ev"] is not None else "<span style='color:#64748b'>—</span>"
        be_s=f"{rw['be']*100:.1f}%" if rw["be"] else "—"
        mk="<span class='ok'>✅</span>" if rw["ok"] else ("<span style='color:#fde047;font-weight:800'>🔥</span>" if rw["prob"]>=thr else "<span class='nok'>·</span>")
        odd_txt=f"{rw['odd']:.2f}" if rw["odd"] else "—"
        rows_html+=(f"<div class='mrow'><span style='color:#8b93a7'>{rw['mkt']}</span><b style='color:#fbbf24'>{esc(rw['pick'])}</b>"
                    f"<span style='color:#34d399;font-weight:700'>{rw['prob']*100:.1f}%</span><span style='color:#f87171'>{be_s}</span>"
                    f"<span style='color:#fff;font-weight:700'>{odd_txt}</span>{ev_s}{mk}</div>")
    ch,ca=c["corners"]; yh,ya=c["yellows"]
    best_html=f"<span>💰 Келли: <b>{c['best'][5]:.2f}</b> на <b>{esc(c['best'][1])}</b> @ <b>{c['best'][2]:.2f}</b></span>" if val else ""
    h,a=c["match"].split(" vs ")
    return f"""
<div class="mcard {'value' if val else ('hot' if hot else '')}">
 <div>{chips}{badge}</div>
 <div class="teams">{esc(h)} <span>—</span> {esc(a)}</div>
 <div class="verdict">🤖 <b>Вердикт:</b> {m_s} · {a_s} · {v_s}<br><span style="color:#c9d2e3">{esc(vtext)}</span></div>
 {rows_html}
 <div class="mfoot"><span>xG: <b>{c['lams'][0]:.2f}–{c['lams'][1]:.2f}</b></span>
  <span>🚩 угл <b>{ch+ca:.1f}</b></span><span>🟨 жёл <b>{yh+ya:.1f}</b></span>
  <span>📚 игр <b>{c['games']}</b></span>{best_html}</div>
</div>"""
def bet_card_html(b,live=None):
    st_=b.get("status","pending")
    icon={"pending":"⏳","won":"🟢","lost":"🔴","push":"⚪"}.get(st_,"⏳")
    score=f"<span class='score'>{esc(b['score'])}</span>" if b.get("score") else ""
    strat=f"<span style='color:#7dd3fc;font-size:.72rem;margin-left:6px'>[{esc(b.get('strat','VALUE'))}]</span>"
    if live and st_=="pending":
        lst=(live.get("status") or "").strip().lower()
        if lst not in FINISHED_STATUSES and live.get("home") not in (None,""):
            prog=f" {live['progress']}" if live.get("progress") else ""
            score=f"<span class='score' style='background:rgba(248,113,113,.3);color:#fecaca'>🔴 LIVE {esc(str(live['home']))}:{esc(str(live['away']))}{esc(prog)}</span>"
    return (f"<div class='betcard {st_}'>{icon} <b>{esc(b['match'])}</b>{score}{strat}<br>"
            f"<span style='color:#8b93a7'>{esc(b.get('market',''))}</span> <b style='color:#fbbf24'>{esc(b['pick'])}</b> @ <b>{b['odds']:.2f}</b> · "
            f"{b['stake']:.2f} у.е. · P={b.get('prob',0)*100:.0f}%</div>")

if not st.session_state.get("_auto_settled_done"):
    if sum(1 for b in D["bets"] if b["status"]=="pending")>0:
        D2=clone(D); upd=0
        for idx,b in enumerate(D["bets"]):
            if b["status"]!="pending" or b.get("div") in (None,"TSDB"): continue
            bd=parse_date(b.get("date_iso","")) if b.get("date_iso") else None
            h,a=b["match"].split(" vs ")
            res=find_result(b.get("div"),h,a,bd)
            if not res: continue
            rd,hg,ag=res
            out=determine_outcome(b.get("market"),b.get("pick"),hg,ag)
            if out: D2=apply_settle(D2,idx,out,score=f"{int(hg)}:{int(ag)}"); upd+=1
        if upd>0:
            st.session_state.data=D2; save_data(D2); D=D2
            st.toast(f"Автосинхронизация: закрыто {upd} ставок",icon="🔄")
    st.session_state["_auto_settled_done"]=True

st.markdown(f"""
<div class="hero">
 <h1>NEURO BET PRO</h1>
 <p>v9 · LLM риск-слой (Gemini→Grok→эвристика) · квота ≥5/день · ярусы T1/T2/T3 · зелёные/жёлтые · live-движок</p>
 <div class="kpis">
  <div class="kpi"><div class="t">Банкролл</div><div class="v y">{D['bank']:.0f} у.е.</div></div>
  <div class="kpi"><div class="t">В работе</div><div class="v">{sum(1 for b in D['bets'] if b['status']=='pending')}</div></div>
  <div class="kpi"><div class="t">Прибыль</div><div class="v {'g' if D['stats']['profit']>=0 else 'r'}">{D['stats']['profit']:+.0f}</div></div>
  <div class="kpi"><div class="t">Ошибок</div><div class="v {'r' if ERR else 'g'}">{len(ERR)}</div></div>
 </div>
</div>""",unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Настройки")
    new_wall=st.selectbox("🖼 Обои",list(WALLS.keys()),index=list(WALLS.keys()).index(wall_key))
    if new_wall!=wall_key:
        D.setdefault("meta",{})["wall"]=new_wall; save_data(D); st.rerun()
    st.markdown("**🔑 Ключи**")
    gk=st.text_input("Gemini key",value=D.get("meta",{}).get("gemini_key",""),type="password")
    xk=st.text_input("Grok key",value=D.get("meta",{}).get("grok_key",""),type="password")
    ak=st.text_input("API-Football key",value=D.get("meta",{}).get("api_key",""),type="password")
    if gk!=D.get("meta",{}).get("gemini_key","") or xk!=D.get("meta",{}).get("grok_key","") or ak!=D.get("meta",{}).get("api_key",""):
        D.setdefault("meta",{}).update({"gemini_key":gk,"grok_key":xk,"api_key":ak}); save_data(D); st.toast("Ключи сохранены",icon="🔑")
    refresh_choice=st.selectbox("Автообновление онлайна",["5 минут","7 минут","15 минут","Отключено"],index=0)
    refresh_sec={"5 минут":300,"7 минут":420,"15 минут":900,"Отключено":0}.get(refresh_choice,300)
    goal=st.selectbox("🎯 Цель стратегии",list(GOALS.keys()),index=0)
    PR0=GOALS[goal]
    kelly_frac=st.slider("Келли (дробь)",0.10,0.40,0.25,0.05)
    mode=st.radio("Режим ленты",["🎯 Высокая проходимость","💰 Валуи (EV)"])
    thr=st.slider("Порог проходимости, %",50,80,int(PR0["thr"]*100))/100
    min_edge=st.slider("Edge, п.п.",0,8,int(PR0["edge"]*100))/100
    min_ev=st.slider("Мин. EV, %",0,10,int(PR0["ev"]*100))/100
    use_dis=st.checkbox("Только расхождения с рынком",value=PR0["dis"])
    use_bl=st.checkbox("Блэклист рынков",value=True)
    quota_base=st.slider("Мин. событий в день",3,10,5)
    lp=D.get("meta",{}).get("lp",{})
    if lp:
        st.markdown("**🧠 Гиперпараметры лиг**")
        for k,v in list(lp.items())[:6]:
            st.caption(f"{DIV_NAMES.get(k,k)}: ws={v['w_shots']:.2f} ρ={v['rho']:.2f} DC={v['w_dc']:.2f} T={v.get('temp',1.0):.2f}")
    with st.expander(f"🐞 Лог ошибок ({len(ERR)})"):
        if ERR:
            for line in ERR[-40:]: st.text(line)
        else: st.text("Ошибок нет.")
    if st.button("🔄 Сброс"):
        st.session_state.data=new_data(); save_data(st.session_state.data); st.rerun()
    st.markdown("""
<div class="side-section"><h4>🧭 Вкладки</h4>
<a class="side-link" href="#tab-сканер">🏟 Сканер</a><a class="side-link" href="#tab-портфель">💼 Портфель</a>
<a class="side-link" href="#tab-статистика">📈 Статистика</a><a class="side-link" href="#tab-калькулятор">🧮 Калькулятор</a>
<a class="side-link" href="#tab-бэктест">🧪 Бэктест</a><a class="side-link" href="#tab-онлайн">🔴 Онлайн</a></div>
<div class="side-section"><h4>📚 Источники</h4>
<a class="side-link" href="https://www.football-data.co.uk/" target="_blank">⚽ football-data.co.uk</a>
<a class="side-link" href="https://www.api-football.com/" target="_blank">📡 api-football.com</a>
<a class="side-link" href="https://www.thesportsdb.com/" target="_blank">🌍 thesportsdb.com</a>
<a class="side-link" href="https://www.pinnacle.com/en/" target="_blank">🎯 pinnacle.com</a></div>
<div class="side-section"><h4>🛠 Инструменты</h4>
<a class="side-link" href="https://kellycriterion.com/" target="_blank">💰 Kelly Criterion</a>
<a class="side-link" href="https://understat.com/" target="_blank">📉 understat.com</a>
<a class="side-link" href="https://fbref.com/" target="_blank">📋 fbref.com</a></div>
<div class="side-section"><h4>ℹ️ О системе</h4>
<span class="side-link" style="cursor:default">🧠 Версия: <b>9.0</b></span>
<span class="side-link" style="cursor:default">🤖 LLM: Gemini→Grok→эвристика</span>
<span class="side-link" style="cursor:default">📅 Квота: ≥<b>"""+str(quota_base)+"""</b>/день</span></div>
""", unsafe_allow_html=True)

tab1,tab2,tab3,tab4,tab5,tab6=st.tabs(["🏟 Сканер","💼 Портфель","📈 Статистика","🧮 Калькулятор","🧪 Бэктест","🔴 Онлайн"])

with tab1:
    c1,c2=st.columns([4,1])
    days=c1.slider("Горизонт, дней",1,21,10)
    scan=c2.button("⚡ СКАН",type="primary")
    blacklist=set(D.get("meta",{}).get("blacklist",[])) if use_bl else set()
    if scan:
        season=find_season(); pseason=prev_season(season)
        today=datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
        now=datetime.now(); limit=today+timedelta(days=days)
        fix,rep1=load_fixtures(); rep_all=list(rep1)
        train_divs=sorted({r.get("Div") for r in fix if r.get("Div")}) or ["E0","SP1","I1","D1","F1"]
        dp=load_many(train_divs,pseason); dc=load_many(train_divs,season)
        div_counts={}
        for dv in train_divs:
            cnt=0
            for src in (dp,dc):
                for r in src.get(dv,[]):
                    if r.get("FTHG") not in (None,""): cnt+=1
            div_counts[dv]=cnt
        fp=engine_fingerprint(season,div_counts); engine=engine_cache_get(fp); trained=0
        if engine is None:
            engine=Engine(); prog=st.progress(0.0,text="Самообучение (2 сезона)...")
            for i,dv in enumerate(train_divs):
                for src in (dp,dc):
                    rr=sorted([r for r in src.get(dv,[]) if parse_date(r.get("Date",""))],key=lambda r:parse_date(r["Date"]))
                    for j,r in enumerate(rr):
                        if r.get("FTHG") not in (None,"") and r.get("FTAG") not in (None,""):
                            try:
                                engine.learn_step(r["HomeTeam"],r["AwayTeam"],float(r["FTHG"]),float(r["FTAG"]),r,lg=dv,match_num=j,total=max(1,len(rr)),match_date=parse_date(r.get("Date","")))
                                trained+=1
                            except Exception as e: log_err(f"train {dv}",e)
                prog.progress((i+1)/len(train_divs))
            prog.empty(); engine_cache_put(fp,engine)
        PR=dict(PR0); PR.update(thr=thr,edge=min_edge,ev=min_ev,bank=D["bank"],kelly=kelly_frac)
        meta={"temp":round(engine.temp,3),"blacklist":D.get("meta",{}).get("blacklist",[]),
              "wall":D.get("meta",{}).get("wall",""),"gemini_key":D.get("meta",{}).get("gemini_key",""),
              "grok_key":D.get("meta",{}).get("grok_key",""),"api_key":D.get("meta",{}).get("api_key",""),
              "lp":{k:{**v,"temp":round(engine.temp,3)} for k,v in list(engine.lp.items())[:15]}}
        # --- кандидаты за сегодня и завтра (для квоты) ---
        cands_all=[]
        for r in fix:
            d=parse_date(r.get("Date",""))
            if not d: continue
            if not (today<=d<=limit): continue
            tm=(r.get("Time") or "").strip()
            if tm:
                try:
                    hh,mm=tm.split(":")[:2]
                    if now>=d.replace(hour=int(hh),minute=int(mm))+timedelta(hours=2,minutes=15): continue
                except Exception: pass
            h=(r.get("HomeTeam") or "").strip(); a=(r.get("AwayTeam") or "").strip()
            if not h or not a: continue
            lg=r.get("Div","G")
            P=engine.predict(h,a,lg,match_date=d,cup=is_cup(r))
            mkt=market_probs(r); Pb=blend_market(P,mkt,PR["w_market"])
            league=r.get("League") or DIV_NAMES.get(lg,"Лига "+str(lg))
            cc=build_candidates(Pb,r,PR,blacklist)
            rows,best,hot,card_clv,gap=evaluate_rows(cc,Pb,mkt,PR,engine,use_dis,row=r)
            advance = d.date()>today.date()
            cands_all.append({"r":r,"d":d,"tm":tm,"h":h,"a":a,"lg":lg,"league":league,"P":Pb,"rows":rows,
                              "best":best,"hot":hot,"clv":card_clv,"gap":gap,"advance":advance})
        # --- ярусы и квота ---
        def tier_of(cand):
            b=cand["best"]
            if b and b[3]>0 and 1.6<=b[2]<=2.6 and b[4]>=0.55: return 1
            for rr in cand["rows"]:
                if rr["prob"]>=0.60 and rr["odd"] and 1.5<=rr["odd"]<=2.0: return 2
            for rr in cand["rows"]:
                if rr["odd"] and 1.45<=rr["odd"]<=1.95 and rr["prob"]>=0.52: return 3
            return 4
        for cand in cands_all: cand["tier"]=tier_of(cand)
        cands_all.sort(key=lambda c:(c["tier"], c["advance"], -(c["best"][3] if c["best"] else 0)))
        volume=len([c for c in cands_all if not c["advance"]])
        quota=max(quota_base, min(12, round(volume*0.12)))
        sel=[]; calls=0; MAXCALLS=quota+10
        for cand in cands_all:
            if cand["tier"] in (3,4) and len(sel)>=quota: break
            if calls<MAXCALLS:
                ctx={"home":cand["h"],"away":cand["a"],"league":cand["league"],
                     "pick":(cand["best"][1] if cand["best"] else (cand["hot"][0][0] if cand["hot"] else "П1")),
                     "odd":(cand["best"][2] if cand["best"] else 1.8),
                     "prob":(cand["best"][4] if cand["best"] else (cand["hot"][0][1] if cand["hot"] else 0.5)),
                     "h2h":engine.h2h_text(cand["h"],cand["a"]),"fh":cand["P"].get("fh","—") if "fh" in cand["P"] else engine.form_str(cand["h"]),
                     "fa":engine.form_str(cand["a"]),"lh":cand["P"]["lams"][0],"la":cand["P"]["lams"][1],
                     "rh":14,"ra":14,"mkt_p":(1/(cand["best"][2]) if cand["best"] else 0.5),
                     "gap":cand["gap"] or 0,"games":cand["P"]["games"]}
                risk=llm_risk(ctx,meta) or heuristic_risk(ctx); calls+=1
            else:
                risk=heuristic_risk({"prob":(cand["best"][4] if cand["best"] else 0.5),"games":cand["P"]["games"],"rh":14,"ra":14,"gap":cand["gap"] or 0})
            if risk.get("veto"): continue
            cand["risk"]=risk; sel.append(cand)
        # ставки по ярусам
        new_bets=[]; existing={b["match"]+"|"+b["pick"] for b in D["bets"]}
        for cand in sel:
            b=cand["best"]
            if not b: continue
            t=cand["tier"]
            if t==1: stake=kelly(b[4],b[2],D["bank"],kelly_frac)
            elif t==2: stake=round(0.5*kelly(b[4],b[2],D["bank"],kelly_frac),2)
            else: stake=round(D["bank"]*0.01,2)
            if stake<=0: continue
            key=f"{cand['h']} vs {cand['a']}|{b[1]}"
            if key in existing: continue
            new_bets.append({"match":f"{cand['h']} vs {cand['a']}","div":cand["lg"],"league":cand["league"],
                "market":b[0],"pick":b[1],"odds":b[2],"stake":stake,"prob":b[4],"clv":cand["clv"],
                "status":"pending","strat":("VALUE" if t in (1,2) else "HOT"),
                "tier":t,"risk":cand["risk"].get("risk"),"llm":cand["risk"].get("summary",""),
                "date":cand["d"].strftime("%d.%m.%Y"),"date_iso":cand["d"].strftime("%Y-%m-%d"),"score":None})
            existing.add(key)
        # карточки для ленты = sel (квота) + все валуи
        cards=[]
        for cand in sel:
            P=cand["P"]
            cards.append({"div":cand["lg"],"league":cand["league"],"match":f"{cand['h']} vs {cand['a']}",
                "date":cand["d"].strftime("%d.%m")+(f" {cand['tm']}" if cand["tm"] else ""),"when":("advance" if cand["advance"] else "сегодня/скоро"),
                "dt":cand["d"].strftime("%Y-%m-%d %H:%M"),"rows":cand["rows"],"best":cand["best"],
                "hot":cand["hot"][:3],"tag":("value" if cand["best"] else "hot"),"lams":P["lams"],
                "lams_g":P["lams_g"],"lams_s":P["lams_s"],"mkt":P.get("mkt"),"gap":cand["gap"],
                "agree":P["agree"],"clv":cand["clv"],"p1":P["p1"],"px":P["x"],"p2":P["p2"],
                "corners":P["corners"],"yellows":P["yellows"],"games":P["games"],
                "fh":engine.form_str(cand["h"]),"fa":engine.form_str(cand["a"]),"cup":is_cup(cand["r"]),
                "tier":cand["tier"],"risk":cand["risk"]})
        picks=build_picks(cards,thr,D["bank"],kelly_frac)
        D2=clone(D); D2["cards"]=cards; D2["picks"]=picks; D2["report"]=rep_all; D2["meta"]=meta
        D2["bets"]=D2["bets"]+new_bets
        D2["funnel"]={"trained":trained,"fix":len(fix),"inwin":volume,"passed":len(sel),"added":len(new_bets),"quota":quota}
        st.session_state.data=D2; save_data(D2); st.rerun()
    fn=D.get("funnel")
    if fn:
        st.caption(f"Обучено {fn.get('trained',0)} · в окне {fn.get('inwin',0)} · квота {fn.get('quota',5)} · отобрано {fn.get('passed',0)} · в портфель +{fn.get('added',0)}")
    with st.expander("🔌 Диагностика источников"):
        for line in D.get("report",[]): st.text(line)
    sc1,sc2=st.columns([3,1])
    sort_key=sc1.selectbox("Сортировка",SORT_OPTIONS,index=0,key="sort_key")
    invert=sc2.checkbox("🔄 Инвертировать",value=False,key="sort_inv")
    eff_desc=SORT_DEFAULT_DESC.get(sort_key,True) if not invert else (not SORT_DEFAULT_DESC.get(sort_key,True))
    picks=D.get("picks",[])
    if picks:
        st.markdown(f"### 🎯 НА ЧТО СТАВИТЬ (квота ≥{quota_base}/день)")
        pv=sorted(picks,key=lambda p: pick_sort_val(p,sort_key),reverse=eff_desc)
        for i,p in enumerate(pv,1):
            green = p["type"]=="value" or p["prob"]>=0.60
            cls="value" if green else "hot"
            btype="🟢 ВАЛУЙ" if p["type"]=="value" else ("🟢 высокая P" if green else "🟡 добивка квоты")
            m,alt,av=p["main"],p["alt"],p["avoid"]
            m_s=f"✅ <b class='y'>{esc(m['pick'])}</b> @ {m['odd_s']} (P {m['prob']*100:.0f}%)" if m else ""
            a_s=f"🔁 <b class='g'>{esc(alt['pick'])}</b>" if alt else ""
            v_s=f"⛔ <b class='r'>{esc(av['pick'])}</b>" if av else ""
            st.markdown(f"""
<div class="mcard {cls}">
 <span class='chip'>{esc(p['league'])}</span><span class='chip when'>📅 {esc(p['date'])} · {esc(p['when'])}</span>
 <span class="badge {'val' if green else 'hot'}">{p['stars']}</span>
 <div class="teams">{i}. {esc(p['match'])}</div>
 <div class="verdict">🤖 {m_s} · {a_s} · {v_s}<br>➤ Ставь <b class="y">{esc(p['pick'])}</b> @ <b class="y">{p['odd_s']}</b> ·
  P <b class="g">{p['prob']*100:.0f}%</b> · сумма <b class="y">{p['stake']:.2f} у.е.</b> · {btype}<br>
  <span style="color:#c9d2e3">{esc(p['verdict'])}</span></div>
</div>""",unsafe_allow_html=True)
    cards_view=sorted(D.get("cards",[]),key=lambda c: card_sort_val(c,sort_key),reverse=eff_desc)
    shown=0
    for c in cards_view:
        if mode=="💰 Валуи (EV)" and not c["best"]: continue
        st.markdown(render_match_card(c,thr,PR0),unsafe_allow_html=True); shown+=1
    if not shown and not picks: st.info("Нажми ⚡ СКАН.")

with tab2:
    st.header("💼 Портфель")
    auto_changed=False
    for idx,b in enumerate(D["bets"]):
        if b["status"]!="pending" or b.get("div") in (None,"TSDB"): continue
        bd=parse_date(b.get("date_iso","")) if b.get("date_iso") else None
        if not bd or bd.date()>=datetime.now().date(): continue
        h,a=b["match"].split(" vs ")
        res=find_result(b.get("div"),h,a,bd)
        if not res: continue
        rd,hg,ag=res
        out=determine_outcome(b.get("market"),b.get("pick"),hg,ag)
        if out:
            st.session_state.data=apply_settle(st.session_state.data,idx,out,score=f"{int(hg)}:{int(ag)}")
            D=st.session_state.data; auto_changed=True
    if auto_changed:
        save_data(D); st.toast("Счета подставлены автоматически",icon="🔄"); st.rerun()
    cbtn1,cbtn2,cbtn3=st.columns(3)
    if cbtn1.button("🔄 Автосинхронизация"):
        D2=clone(D); upd=w=l=pu=0
        for idx,b in enumerate(D["bets"]):
            if b["status"]!="pending" or b.get("div") in (None,"TSDB"): continue
            bd=parse_date(b.get("date_iso","")) if b.get("date_iso") else None
            h,a=b["match"].split(" vs ")
            res=find_result(b.get("div"),h,a,bd)
            if not res: continue
            rd,hg,ag=res
            out=determine_outcome(b.get("market"),b.get("pick"),hg,ag)
            if out:
                D2=apply_settle(D2,idx,out,score=f"{int(hg)}:{int(ag)}"); upd+=1
                if out=="won": w+=1
                elif out=="lost": l+=1
                else: pu+=1
        st.session_state.data=D2; save_data(D2); st.toast(f"Закрыто {upd}: ✅{w} ❌{l} ⚪{pu}",icon="🔄"); st.rerun()
    if cbtn2.button("🧐 Перепроверить все счета"):
        D2=clone(D); fixed=checked=0
        for idx,b in enumerate(D["bets"]):
            if b.get("div") in (None,"TSDB"): continue
            bd=parse_date(b.get("date_iso","")) if b.get("date_iso") else None
            h,a=b["match"].split(" vs ")
            res=find_result(b.get("div"),h,a,bd)
            if not res: continue
            checked+=1; rd,hg,ag=res; sc=f"{int(hg)}:{int(ag)}"
            if b.get("status")=="pending" or b.get("score")!=sc: D2=recompute_bet(D2,idx,hg,ag,sc); fixed+=1
        st.session_state.data=D2; save_data(D2); st.success(f"Проверено {checked}, исправлено {fixed}"); st.rerun()
    live=None
    if cbtn3.button("🔴 Проверить LIVE"):
        live=load_livescores(); st.session_state["_live"]=live
    live=live or st.session_state.get("_live")
    ps1,ps2=st.columns([3,1])
    port_sort=ps1.selectbox("Сортировка портфеля",PORT_SORT,index=0,key="port_sort")
    port_invert=ps2.checkbox("🔄 Инвертировать",value=False,key="port_inv")
    p_base=PORT_DEFAULT_DESC.get(port_sort,False); p_desc=p_base if not port_invert else (not p_base)
    if not D["bets"]: st.info("Пусто.")
    pairs=sorted(enumerate(D["bets"]),key=lambda pr: bet_sort_key(pr,port_sort),reverse=p_desc)
    for i,b in pairs:
        lv=None
        if b["status"]=="pending" and live:
            h,a=b["match"].split(" vs "); lv=match_live(live,h,a)
        st.markdown(bet_card_html(b,lv),unsafe_allow_html=True)
        if b["status"]=="pending" and lv:
            lst=(lv.get("status") or "").strip().lower()
            if lst in FINISHED_STATUSES and lv.get("home") not in (None,"") and lv.get("away") not in (None,""):
                hg,ag=_f(lv["home"]),_f(lv["away"])
                if hg is not None and ag is not None:
                    out=determine_outcome(b.get("market"),b.get("pick"),hg,ag)
                    if out:
                        st.session_state.data=apply_settle(D,i,out,score=f"{int(hg)}:{int(ag)}"); D=st.session_state.data
                        save_data(D); st.toast(f"LIVE закрыто: {b['match'][:25]}… {int(hg)}:{int(ag)}",icon="🔴"); st.rerun()
        if b["status"]=="pending":
            cc=st.columns([1,1,1])
            sin=cc[0].text_input("Счёт",key=f"sc{i}",label_visibility="collapsed",placeholder="2:1")
            sc=None
            if re.match(r"^\d+\s*:\s*\d+$",sin.strip()): sc=sin.strip()
            if cc[1].button("✅ Зашло",key=f"w{i}"):
                st.session_state.data=apply_settle(D,i,"won",score=sc); save_data(st.session_state.data); st.rerun()
            if cc[2].button("❌ Мимо",key=f"l{i}"):
                st.session_state.data=apply_settle(D,i,"lost",score=sc); save_data(st.session_state.data); st.rerun()

with tab3:
    st.header("📈 Статистика")
    s=D["stats"]; tot=s["won"]+s["lost"]
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Банк",f"{D['bank']:.2f}"); m2.metric("Ставок",tot)
    m3.metric("WinRate",f"{(s['won']/tot*100) if tot else 0:.1f}%"); m4.metric("Profit",f"{s['profit']:+.2f}")
    settled=[b for b in D["bets"] if b.get("status") in ("won","lost","push")]
    if settled:
        curve=[]; run=0.0
        for b in settled:
            run+= b["stake"]*(b["odds"]-1) if b["status"]=="won" else (-b["stake"] if b["status"]=="lost" else 0)
            curve.append(run)
        st.line_chart(curve,height=180)
        ss=strat_stats(D["bets"]); cA,cB=st.columns(2)
        for col,strat in ((cA,"VALUE"),(cB,"HOT")):
            v=ss[strat]
            with col:
                st.markdown(f"**{'🟢 VALUE' if strat=='VALUE' else '🔥 HOT'}**")
                st.metric("Ставок",v["n"]); st.metric("WinRate",f"{v['wr']:.1f}%"); st.metric("ROI",f"{v['roi']:+.2f}%")
        cal=calibration_rows(D["bets"])
        if cal: st.dataframe(cal,use_container_width=True,hide_index=True)
        wk=weekly_rows(D["bets"])
        if wk: st.dataframe(wk,use_container_width=True,hide_index=True)

with tab4:
    st.header("🧮 EV-калькулятор")
    q1,q2,q3=st.columns(3)
    p=q1.number_input("Вероятность, %",1,99,60); o=q2.number_input("Кэф",1.01,30.0,1.80); bk=q3.number_input("Банк",100.0,1e6,float(D["bank"]))
    ev=(p/100)*o-1
    st.markdown(f"**EV:** {ev*100:+.1f}% · **Безубыточность:** {100/o:.1f}% · **Келли:** {kelly(p/100,o,bk,kelly_frac):.2f} у.е.")
    if ev>0.02: st.success("✅ Можно ставить")
    else: st.warning("⛔ EV мал")

with tab5:
    st.header("🧪 Бэктест (walk-forward)")
    b1,b2,b3,b4=st.columns(4)
    bt_div=b1.selectbox("Лига",list(DIV_NAMES.keys()),format_func=lambda k:DIV_NAMES[k])
    bt_season=b2.selectbox("Сезон",["2526","2425","2324"],index=1)
    bt_edge=b3.slider("Edge, п.п.",0,8,int(PR0["edge"]*100),key="bte")/100
    bt_mode=b4.selectbox("Стейк",["Flat","Kelly"])
    if st.button("▶️ Прогнать",type="primary"):
        PRb=dict(PR0); PRb.update(thr=thr,edge=bt_edge,ev=min_ev,bank=10000.0,kelly=0.25)
        log,eng=backtest(bt_div,bt_season,PRb,use_dis,bt_mode)
        bl=[k for k,v in eng.market_roi.items() if v["n"]>=30 and v["profit"]<-0.02]
        D2=clone(D); D2["meta"]["blacklist"]=bl; D2["meta"]["lp"]={k:{**v,"temp":round(eng.temp,3)} for k,v in list(eng.lp.items())[:15]}
        st.session_state.data=D2; save_data(D2)
        if not log: st.warning("Нет сигналов.")
        else:
            n=len(log); wins=sum(1 for x in log if x["won"]); profit=sum(x["pnl"] for x in log); staked=sum(x["stake"] for x in log)
            roi=profit/staked*100 if staked else 0
            curve=0; peak=0; mdd=0
            for x in log:
                curve+=x["pnl"]; peak=max(peak,curve); mdd=max(mdd,peak-curve)
            mean_p=profit/n; std_p=(sum((x["pnl"]-mean_p)**2 for x in log)/max(1,n-1))**0.5; sharpe=mean_p/std_p if std_p else 0
            k1,k2,k3,k4,k5=st.columns(5)
            k1.metric("Ставок",n); k2.metric("WinRate",f"{wins/n*100:.1f}%"); k3.metric("ROI",f"{roi:+.2f}%")
            k4.metric("MaxDD",f"{mdd:.1f}"); k5.metric("Sharpe",f"{sharpe:.2f}")

with tab6:
    st.header("🔴 Онлайн · live + ближайшие")
    api_key=D.get("meta",{}).get("api_key","")
    if refresh_sec>0:
        import streamlit.components.v1 as components
        components.html(f'<meta http-equiv="refresh" content="{refresh_sec}">',height=0)
    if st.button("🔄 Обновить сейчас"): st.rerun()
    api_lives,api_rep=api_football_live(api_key,list(API_LG.values())) if api_key else ([],["API-Football: ключ не задан"])
    tsdb_raw=load_livescores(); tsdb_lives=[]
    for (hk,ak),v in tsdb_raw.items():
        prog=v.get("progress") or v.get("status") or ""
        mm=re.search(r"(\d+)",str(prog)); minute=int(mm.group(1)) if mm else 45
        try: hs=int(v.get("home"))
        except Exception: hs=0
        try: as_=int(v.get("away"))
        except Exception: as_=0
        tsdb_lives.append({"league":v.get("league") or "Матч","home":v.get("home_name") or hk,"away":v.get("away_name") or ak,
                           "home_score":hs,"away_score":as_,"minute":minute,"stats":{},"source":"TSDB","fixture_id":None})
    live_all=[dict(m,source="API") for m in api_lives]+tsdb_lives
    with st.expander("🔌 Диагностика"):
        for line in api_rep: st.text(line)
        st.text(f"TSDB live: {len(tsdb_lives)} · всего live: {len(live_all)}")
    live_models=load_live_model()
    existing_ids={s.get("fixture_id") for s in live_models.get("signals",[]) if s.get("had_goal") is None and s.get("fixture_id")}
    current_ids={m.get("fixture_id") for m in live_all if m.get("fixture_id")}
    learned=0
    if api_key:
        for fid in list(existing_ids-current_ids)[:20]:
            info=api_football_fixture(api_key,fid)
            if not info or not info.get("finished"): continue
            for s in live_models.get("signals",[]):
                if s.get("fixture_id")==fid and s.get("had_goal") is None:
                    ft=int(info.get("home") or 0)+int(info.get("away") or 0)
                    s["had_goal"]=ft>int(s.get("cur_total") or 0); s["final_total"]=ft
                    live_models=live_learn_step(s.get("minute",45),s.get("cur_total",0),ft,league=s.get("league"),live_model=live_models)
                    learned+=1; break
    if learned: live_models=live_refit_temp(live_models); save_live_model(live_models)
    for m in live_all:
        fid=m.get("fixture_id") or f"{m.get('home')}|{m.get('away')}|{m.get('minute')}"
        if fid not in existing_ids:
            minute=int(m.get("minute") or 0); cur=int(m.get("home_score") or 0)+int(m.get("away_score") or 0)
            sig=live_predict(minute,cur,AVG_GOALS,league=m.get("league"),live_model=live_models)
            live_models.setdefault("signals",[]).append({"fixture_id":fid,"league":m.get("league"),
                "match":f"{m.get('home','')} vs {m.get('away','')}","minute":minute,"cur_total":cur,
                "p_goal":sig["p_goal"],"proj_total":sig["proj_total"],"had_goal":None})
            existing_ids.add(fid)
    save_live_model(live_models)
    ls=live_stats(live_models)
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Сигналов",len(live_models.get("signals",[]))); m2.metric("Обучено",live_models.get("n_learned",0))
    m3.metric("T",f"{live_models.get('temp',1.0):.2f}"); m4.metric("Завершено",ls["n"])
    if ls["hit_rate"] is not None:
        st.metric("Hit-rate «будет гол»",f"{ls['hit_rate']:.1f}%")
    st.subheader(f"🔴 Live: {len(live_all)}")
    sig_count=0
    if not live_all: st.info("Живых матчей нет. Ниже ближайшие.")
    for m in live_all:
        minute=int(m.get("minute") or 0); hs=int(m.get("home_score") or 0); as_=int(m.get("away_score") or 0)
        sig=live_predict(minute,hs+as_,AVG_GOALS,league=m.get("league"),live_model=live_models)
        strong=sig["p_goal"]>=0.60
        if strong: sig_count+=1
        badge="<span class='badge live'>⚡ ВОЗМОЖЕН ГОЛ</span>" if strong else "<span class='badge no'>наблюдение</span>"
        st.markdown(f"""
<div class="mcard {'live' if strong else ''}">
 <span class='chip live'>🔴 {minute}'</span><span class='chip'>{esc(str(m.get('league','')))}</span>{badge}
 <div class="teams">{esc(str(m.get('home','')))} <span>{hs}:{as_}</span> {esc(str(m.get('away','')))}</div>
 <div class="verdict">🤖 P(ещё гол) = <b class="{'g' if strong else 'y'}">{sig['p_goal']*100:.0f}%</b> · тотал к финалу ≈ <b class="y">{sig['proj_total']:.1f}</b></div>
</div>""",unsafe_allow_html=True)
    if sig_count: st.success(f"Сигналов «возможен гол»: {sig_count}")
    if st.button("🗑 Сброс live-обучения"):
        save_live_model({"alpha":1.5,"beta":TOTAL_MIN,"temp":1.0,"signals":[],"league_pace":{},"n_learned":0})
        st.rerun()
