import streamlit as st
import json, os, re, html
from datetime import datetime, timedelta
from collections import defaultdict
import nb_engine as E

st.set_page_config(page_title="NEURO BET PRO v8.5", page_icon="🏟", layout="wide")
HISTORY_FILE="neuro_bet_pro.json"
esc=html.escape

DIV_NAMES={"E0":"🏴󠁥󠁧 АПЛ","E1":"🏴󠁢󠁥󠁮󠁿 Чемпионшип","SC0":"🏴󠁳󠁣󠁴󠁿 Шотландия",
 "D1":"🇩🇪 Бундеслига","D2":"🇩🇪 2.Бундеслига","I1":"🇮🇹 Серия A","I2":"🇮🇹 Серия B",
 "SP1":"🇪🇸 Ла Лига","SP2":"🇪🇸 Сегунда","F1":"🇫🇷 Лига 1","F2":"🇫🇷 Лига 2",
 "N1":"🇳🇱 Эредивизи","B1":"🇧🇪 Про-лига","P1":"🇵 Примейра","T1":"🇹🇷 Суперлига",
 "G1":"🇬🇷 Греция","R1":"🇷🇺 РПЛ","BR1":"🇧 Бразилия","C1":"🏆 ЛЧ","EL":"🏆 ЛЕ","EC":"🏆 ЛК"}
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

# ---------- данные (раньше стилей, чтобы обои читались из meta) ----------
def new_data():
    return {"version":3,"bank":10000.0,"bets":[],"cards":[],"picks":[],"funnel":None,
            "report":[],"meta":{},"stats":{"won":0,"lost":0,"profit":0,"push":0}}
def migrate(D):
    if not isinstance(D,dict): return new_data()
    base=new_data()
    for k,v in base.items():
        if k not in D or D[k] is None: D[k]=json.loads(json.dumps(v))
    D["version"]=3
    if not isinstance(D.get("cards"),list): D["cards"]=[]
    if not isinstance(D.get("picks"),list): D["picks"]=[]
    if D["cards"] and isinstance(D["cards"][0],dict) and "lams_g" not in D["cards"][0]:
        D["cards"]=[]; D["picks"]=[]
    if not isinstance(D.get("bets"),list): D["bets"]=[]
    D["bets"]=[b for b in D["bets"] if isinstance(b,dict) and all(k in b for k in ("match","pick","odds","stake","status"))]
    for b in D["bets"]:
        b.setdefault("strat","HOT" if b.get("market")=="HOT" else "VALUE")
    if not isinstance(D.get("stats"),dict): D["stats"]=base["stats"]
    for s in ("won","lost","profit","push"): D["stats"].setdefault(s,0)
    if not isinstance(D.get("meta"),dict): D["meta"]={}
    if not isinstance(D.get("report"),list): D["report"]=[]
    return D
def load_data():
    if os.path.exists(HISTORY_FILE):
        try: return migrate(json.load(open(HISTORY_FILE,encoding="utf-8")))
        except Exception as e: E.log_err("load_data",e)
    return new_data()
def save_data(d):
    try: json.dump(d,open(HISTORY_FILE,"w",encoding="utf-8"),indent=2,ensure_ascii=False)
    except Exception as e: E.log_err("save_data",e)
def clone(D): return json.loads(json.dumps(D))

if "data" not in st.session_state: st.session_state.data=load_data()
D=st.session_state.data

wall_key=D.get("meta",{}).get("wall","🌃 Неон-стадион")
if wall_key not in WALLS: wall_key="🌃 Неон-стадион"
WALL_CSS=WALLS[wall_key]

st.markdown("<style>"+"""
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@600;800&family=Inter:wght@400;600;800&display=swap');
html,body,#root,
div[data-testid="stAppViewContainer"],
div[data-testid="stAppViewContainer"]>div,
section.main,.stApp{
 background: __WALL__ !important;
 background-attachment: fixed !important;
}
.stMarkdown,.stMarkdown p,.stMarkdown li{color:#e6eaf2;font-family:'Inter',sans-serif;}
.stCaption,.stCaption *{color:#8b93a7 !important;}
div[data-testid="stMetricValue"]{color:#f8fafc !important;font-family:'Unbounded',sans-serif;font-size:1.3rem;}
div[data-testid="stMetricLabel"] p{color:#8b93a7 !important;}
header,#MainMenu,footer{visibility:hidden}
section[data-testid="stSidebar"]{background:rgba(8,11,20,.72);backdrop-filter:blur(18px);
 border-right:1px solid rgba(255,255,255,.07);}
section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] label,section[data-testid="stSidebar"] span{color:#e6eaf2 !important;}
section.stButton>button{
 background:linear-gradient(135deg,#0ea5e9 0%,#8b5cf6 55%,#ec4899 110%);
 color:#fff;border:none;border-radius:14px;font-weight:800;font-family:'Inter',sans-serif;
 box-shadow:0 8px 26px rgba(139,92,246,.35);transition:.18s;}
section.stButton>button:hover{transform:translateY(-2px);box-shadow:0 12px 34px rgba(14,165,233,.45);}
div[data-baseweb="select"]>div{background:rgba(255,255,255,.05)!important;
 border:1px solid rgba(255,255,255,.10)!important;border-radius:12px;}
.hero{padding:26px 30px;border-radius:26px;margin-bottom:18px;position:relative;overflow:hidden;
 border:1px solid rgba(255,255,255,.10);
 background:linear-gradient(130deg,rgba(14,165,233,.20),rgba(139,92,246,.16) 45%,rgba(236,72,153,.14));
 backdrop-filter:blur(20px);}
.hero h1{margin:0;font-size:2.5rem;font-weight:800;font-family:'Unbounded',sans-serif;
 background:linear-gradient(92deg,#22d3ee,#a78bfa 50%,#f472b6);
 -webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.hero p{margin:6px 0 0;color:#c9d2e3;font-size:.93rem}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:16px}
.kpi{background:rgba(255,255,255,.05);backdrop-filter:blur(14px);border:1px solid rgba(255,255,255,.10);
 border-radius:18px;padding:14px 16px;}
.kpi .t{color:#7dd3fc;font-size:.66rem;text-transform:uppercase;letter-spacing:1.4px;font-weight:700}
.kpi .v{font-size:1.5rem;font-weight:800;font-family:'Unbounded',sans-serif;color:#fff}
.kpi .v.g{color:#34d399}.kpi .v.y{color:#fbbf24}.kpi .v.r{color:#f87171}
.mcard{background:rgba(10,14,24,.72);backdrop-filter:blur(16px);border:1px solid rgba(255,255,255,.09);
 border-radius:20px;padding:18px 20px;margin-bottom:14px;transition:.2s;}
.mcard:hover{border-color:rgba(34,211,238,.45);box-shadow:0 10px 40px rgba(34,211,238,.12);}
.mcard.value{border-color:rgba(52,211,153,.55);box-shadow:0 0 34px rgba(52,211,153,.14);}
.mcard.hot{border-color:rgba(251,191,36,.5);box-shadow:0 0 30px rgba(251,191,36,.10);}
.chip{background:rgba(34,211,238,.14);color:#a5f3fc;border:1px solid rgba(34,211,238,.35);
 padding:3px 11px;border-radius:999px;font-size:.72rem;font-weight:700;margin-right:6px;}
.chip.when{background:rgba(251,191,36,.14);color:#fde68a;border-color:rgba(251,191,36,.4);}
.chip.warn{background:rgba(248,113,113,.15);color:#fecaca;border-color:rgba(248,113,113,.4);}
.badge{float:right;padding:4px 13px;border-radius:999px;font-size:.72rem;font-weight:800;}
.badge.val{background:linear-gradient(135deg,rgba(52,211,153,.25),rgba(16,185,129,.15));color:#6ee7b7;border:1px solid rgba(52,211,153,.6);}
.badge.hot{background:linear-gradient(135deg,rgba(251,191,36,.25),rgba(245,158,11,.15));color:#fde68a;border:1px solid rgba(251,191,36,.55);}
.badge.no{background:rgba(148,163,184,.12);color:#cbd5e1;border:1px solid rgba(148,163,184,.3);}
.teams{font-size:1.3rem;font-weight:800;color:#fff;margin:9px 0 3px;}
.teams span{color:#8b93a7;font-weight:400}
.verdict{background:rgba(34,211,238,.06);border:1px solid rgba(34,211,238,.22);border-radius:14px;
 padding:11px 15px;margin:9px 0;color:#e6eaf2;font-size:.88rem;}
.verdict b.y{color:#fbbf24}.verdict b.g{color:#34d399}.verdict b.r{color:#f87171}
.mrow{display:grid;grid-template-columns:70px 96px 70px 70px 62px 74px 26px;gap:8px;padding:6px 0;
 border-top:1px solid rgba(255,255,255,.07);font-size:.83rem;color:#e6eaf2;}
.ok{color:#34d399;font-weight:800}.nok{color:#64748b}
.evpos{color:#34d399;font-weight:700}.evneg{color:#f87171;font-weight:700}
.mfoot{margin-top:9px;color:#c9d2e3;font-size:.78rem;display:flex;gap:16px;flex-wrap:wrap;}
.mfoot b{color:#fbbf24}
.betcard{background:rgba(10,14,24,.72);backdrop-filter:blur(14px);border:1px solid rgba(255,255,255,.09);
 border-left:4px solid rgba(148,163,184,.4);border-radius:16px;padding:11px 15px;margin-bottom:9px;
 font-size:.87rem;color:#e6eaf2;}
.betcard.pending{border-left-color:#fbbf24}.betcard.won{border-left-color:#34d399}
.betcard.lost{border-left-color:#f87171}.betcard.push{border-left-color:#94a3b8}
.betcard .score{font-weight:900;padding:2px 10px;border-radius:9px;margin-left:6px;}
.betcard.won .score{background:rgba(52,211,153,.25);color:#6ee7b7}
.betcard.lost .score{background:rgba(248,113,113,.25);color:#fca5a5}
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
    season=E.find_season(); cands=[]
    for r in E.load_seasonal(div,season):
        if r.get("HomeTeam")==home and r.get("AwayTeam")==away and r.get("FTHG") not in (None,""):
            rd=E.parse_date(r.get("Date",""))
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
    new=E.determine_outcome(b.get("market"),b.get("pick"),hg,ag)
    if new is None: return D
    old=b.get("status","pending")
    if old=="won":
        pr=b["stake"]*(b["odds"]-1); D2["bank"]-=b["stake"]+pr
        D2["stats"]["won"]=max(0,D2["stats"]["won"]-1); D2["stats"]["profit"]-=pr
    elif old=="lost":
        D2["bank"]+=b["stake"]; D2["stats"]["lost"]=max(0,D2["stats"]["lost"]-1); D2["stats"]["profit"]+=b["stake"]
    elif old=="push":
        D2["bank"]-=b["stake"]; D2["stats"]["push"]=max(0,D2["stats"].get("push",0)-1)
    b["status"]=new; b["score"]=score_str
    if new=="won":
        pr=b["stake"]*(b["odds"]-1); D2["bank"]+=b["stake"]+pr
        D2["stats"]["won"]+=1; D2["stats"]["profit"]+=pr
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
    rows=c.get("rows",[])
    scored=sorted([r for r in rows if r.get("prob")],key=lambda r:-r["prob"])
    def prep(r):
        if not r: return None
        d=dict(r); d["odd_s"]=_odd_s(d); return d
    main=prep(scored[0]) if scored else None
    alt=prep(scored[1]) if len(scored)>1 else None
    x12=[r for r in rows if r["mkt"]=="1X2"]
    avoid=prep(min(x12,key=lambda r:r["prob"])) if x12 else None
    lg=c.get("lams_g",(0,0)); ls=c.get("lams_s",(0,0)); lh,la=c.get("lams",(0,0))
    parts=[f"Движок голов {lg[0]:.1f}–{lg[1]:.1f}, движок ударов {ls[0]:.1f}–{ls[1]:.1f} → итог xG {lh:.1f}–{la:.1f}."]
    if not c.get("agree",True): parts.append("⚠️ Движки не согласны о фаворите — 1X2 пропущен.")
    if c.get("fh","—")!="—": parts.append(f"Форма {c['fh']} против {c['fa']}.")
    m=c.get("mkt")
    if m:
        gap=max(abs(c.get("p1",0)-m[0]),abs(c.get("px",c.get("x",0))-m[1]),abs(c.get("p2",0)-m[2]))
        parts.append(f"Pinnacle: П1 {m[0]*100:.0f}/X {m[1]*100:.0f}/П2 {m[2]*100:.0f}%; расхождение {gap*100:.0f} п.п.")
    if c.get("cup"): parts.append("Кубковый матч: λ снижены внутри модели.")
    return main,alt,avoid," ".join(parts)
def stars_for(rw,thr):
    if rw["ok"]:
        ev=rw["ev"]; return "⭐⭐⭐⭐⭐" if ev>=0.10 else ("⭐⭐⭐⭐" if ev>=0.06 else "⭐⭐⭐")
    if rw["prob"]>=thr:
        return "⭐⭐⭐⭐⭐" if rw["prob"]>=0.70 else ("⭐⭐⭐⭐" if rw["prob"]>=0.65 else "⭐⭐⭐")
    return ""
def build_picks(cards,thr,bank,kf):
    picks=[]
    for c in cards:
        row=None; ptype=None
        if c.get("best"):
            ok=[r for r in c["rows"] if r["ok"]]
            row=max(ok,key=lambda r:r["ev"]) if ok else None; ptype="value"
        if row is None:
            hot=[r for r in c["rows"] if r["prob"]>=thr]
            if hot: row=max(hot,key=lambda r:r["prob"]); ptype="hot"
        if row is None: continue
        main,alt,avoid,text=ai_verdict(c)
        stake=E.kelly(row["prob"],row["odd"],bank,kf) if row["odd"] else round(bank*0.01,2)
        picks.append({"league":c["league"],"match":c["match"],"date":c["date"],"when":c["when"],
                      "pick":row["pick"],"prob":row["prob"],"odd":row["odd"],"odd_s":_odd_s(row),
                      "stake":stake,"stars":stars_for(row,thr),"type":ptype,"verdict":text,
                      "main":main,"alt":alt,"avoid":avoid,"clv":c.get("clv"),
                      "score":(row["ev"] if ptype=="value" else 0)+row["prob"]})
    picks.sort(key=lambda p:(p["type"]=="value",p["score"]),reverse=True)
    return picks[:10]
def strat_stats(bets):
    out={}
    for s in ("VALUE","HOT"):
        sb=[b for b in bets if b.get("strat","VALUE")==s and b.get("status") in ("won","lost","push")]
        n=len(sb); w=sum(1 for b in sb if b["status"]=="won")
        pnl=sum(b["stake"]*(b["odds"]-1) if b["status"]=="won" else (0.0 if b["status"]=="push" else -b["stake"]) for b in sb)
        staked=sum(b["stake"] for b in sb if b["status"]!="push")
        clv=[b["clv"] for b in sb if b.get("clv") is not None]
        out[s]=dict(n=n,w=w,pnl=pnl,roi=(pnl/staked*100 if staked else 0.0),
                    wr=(w/n*100 if n else 0.0),clv=(sum(clv)/len(clv) if clv else None))
    return out
def calibration_rows(bets):
    settled=[b for b in bets if b.get("status") in ("won","lost") and b.get("prob")]
    rows=[]
    for lo,hi in [(0.40,0.50),(0.50,0.60),(0.60,0.70),(0.70,1.01)]:
        sb=[b for b in settled if lo<=b["prob"]<hi]
        if len(sb)>=3:
            wr=sum(1 for b in sb if b["status"]=="won")/len(sb)*100
            avgp=sum(b["prob"] for b in sb)/len(sb)*100
            rows.append({"Бин P":f"{lo*100:.0f}–{hi*100:.0f}%","Ставок":len(sb),
                         "Предсказано":f"{avgp:.1f}%","Факт WR":f"{wr:.1f}%","Откл.":f"{wr-avgp:+.1f}"})
    return rows
def weekly_rows(bets):
    wk=defaultdict(lambda:[0,0,0.0])
    for b in bets:
        if b.get("status") not in ("won","lost") or not b.get("date_iso"): continue
        d=E.parse_date(b["date_iso"])
        if not d: continue
        iso=d.isocalendar()
        pnl=b["stake"]*(b["odds"]-1) if b["status"]=="won" else -b["stake"]
        wk[(iso[0],iso[1])][0]+=1
        wk[(iso[0],iso[1])][1]+=1 if b["status"]=="won" else 0
        wk[(iso[0],iso[1])][2]+=pnl
    return [{"Неделя":f"{y}-W{w:02d}","Ставок":v[0],"WR":f"{v[1]/v[0]*100:.0f}%","PnL":f"{v[2]:+.1f}"}
            for (y,w),v in sorted(wk.items())]

SORT_OPTIONS=["По EV (валуи сверху)","По вероятности","По дате (ближайшие)","По коэффициенту","По лиге (А→Я)"]
def card_sort_val(c,key):
    if key.startswith("По EV"):
        if c.get("best"): return c["best"][3]
        return max([r["ev"] for r in c["rows"] if r["ev"] is not None],default=-1)
    if key.startswith("По вероятности"):
        return max([r["prob"] for r in c["rows"]],default=0)
    if key.startswith("По дате"):
        return c.get("dt","9999-99-99")
    if key.startswith("По коэффициенту"):
        if c.get("best"): return c["best"][2]
        return max([r["odd"] for r in c["rows"] if r["odd"]],default=0)
    return c.get("league","")

def render_match_card(c,thr,PR):
    val=c.get("best") is not None
    hot=any(r["prob"]>=thr for r in c["rows"]) and not val
    badge=f"<span class='badge {'val' if val else ('hot' if hot else 'no')}'>{'🟢 ВАЛУЙ' if val else ('🔥 P≥'+str(int(thr*100))+'%' if hot else 'фон')}</span>"
    chips=f"<span class='chip'>{esc(c['league'])}</span><span class='chip when'>📅 {esc(c['date'])} · {esc(c['when'])}</span>"
    if c["games"]<PR["min_games"]: chips+="<span class='chip warn'>⚠️ мало данных</span>"
    if c.get("cup"): chips+="<span class='chip warn'>🏆 Кубок</span>"
    if not c.get("agree",True): chips+="<span class='chip warn'>⚠️ движки не согласны</span>"
    main,alt,avoid,vtext=ai_verdict(c)
    m_s=f"✅ <b class='y'>{esc(main['pick'])}</b> @ {main['odd_s']} (P {main['prob']*100:.0f}%)" if main else ""
    a_s=f"🔁 <b class='g'>{esc(alt['pick'])}</b> (P {alt['prob']*100:.0f}%)" if alt else ""
    v_s=f"⛔ <b class='r'>{esc(avoid['pick'])}</b>" if avoid else ""
    rows_html=""
    for rw in c["rows"]:
        ev_s=f"<span class='{'evpos' if rw['ev']>0 else 'evneg'}'>{rw['ev']*100:+.1f}%</span>" if rw["ev"] is not None else "<span style='color:#64748b'>—</span>"
        be_s=f"{rw['be']*100:.1f}%" if rw["be"] else "—"
        mk="<span class='ok'>✅</span>" if rw["ok"] else ("<span style='color:#fde047;font-weight:800'>🔥</span>" if rw["prob"]>=thr else "<span class='nok'>·</span>")
        rows_html+=(f"<div class='mrow'><span style='color:#8b93a7'>{rw['mkt']}</span><b style='color:#fbbf24'>{esc(rw['pick'])}</b>"
                    f"<span style='color:#34d399;font-weight:700'>{rw['prob']*100:.1f}%</span>"
                    f"<span style='color:#f87171'>{be_s}</span>"
                    f"<span style='color:#fff;font-weight:700'>{rw['odd'] if rw['odd'] else '—'}</span>{ev_s}{mk}</div>")
    ch,ca=c["corners"]; yh,ya=c["yellows"]
    best_html=f"<span>💰 Келли: <b>{c['best'][5]:.2f}</b> на <b>{esc(c['best'][1])}</b> @ <b>{c['best'][2]:.2f}</b></span>" if val else ""
    pin=f"<span>📏 Перевес над Pinnacle: <b>{c['clv']*100:+.1f}%</b></span>" if c.get("clv") is not None else ""
    h,a=c["match"].split(" vs ")
    return f"""
<div class="mcard {'value' if val else ('hot' if hot else '')}">
 <div>{chips}{badge}</div>
 <div class="teams">{esc(h)} <span>—</span> {esc(a)}</div>
 <div class="verdict">🤖 <b>Вердикт:</b> {m_s} · {a_s} · {v_s}<br><span style="color:#c9d2e3">{esc(vtext)}</span></div>
 {rows_html}
 <div class="mfoot"><span>xG: <b>{c['lams'][0]:.2f}–{c['lams'][1]:.2f}</b></span>
  <span>🚩 угл <b>{ch+ca:.1f}</b></span><span>🟨 жёл <b>{yh+ya:.1f}</b></span>
  <span>📚 игр <b>{c['games']}</b></span>{pin}{best_html}</div>
</div>"""
def bet_card_html(b,live=None):
    st_=b.get("status","pending")
    icon={"pending":"⏳","won":"🟢","lost":"🔴","push":"⚪"}.get(st_,"⏳")
    score=f"<span class='score'>{esc(b['score'])}</span>" if b.get("score") else ""
    strat=f"<span style='color:#7dd3fc;font-size:.72rem;margin-left:6px'>[{esc(b.get('strat','VALUE'))}]</span>"
    if live and st_=="pending" and (live.get("status") or "").strip().lower() not in E.FINISHED_STATUSES and live.get("home") not in (None,""):
        prog=f" {live['progress']}" if live.get("progress") else ""
        score=f"<span class='score' style='background:rgba(248,113,113,.3);color:#fecaca'>🔴 LIVE {esc(str(live['home']))}:{esc(str(live['away']))}{esc(prog)}</span>"
    pin=f" · 📏 {b['clv']*100:+.1f}%" if b.get("clv") is not None else ""
    return (f"<div class='betcard {st_}'>{icon} <b>{esc(b['match'])}</b>{score}{strat}<br>"
            f"<span style='color:#8b93a7'>{esc(b.get('market',''))}</span> "
            f"<b style='color:#fbbf24'>{esc(b['pick'])}</b> @ <b>{b['odds']:.2f}</b> · "
            f"{b['stake']:.2f} у.е. · P={b.get('prob',0)*100:.0f}%{pin}</div>")

if not st.session_state.get("_auto_settled_done"):
    if sum(1 for b in D["bets"] if b["status"]=="pending")>0:
        D2=clone(D); upd=0
        for idx,b in enumerate(D["bets"]):
            if b["status"]!="pending" or b.get("div") in (None,"TSDB"): continue
            bd=E.parse_date(b.get("date_iso","")) if b.get("date_iso") else None
            h,a=b["match"].split(" vs ")
            res=find_result(b.get("div"),h,a,bd)
            if not res: continue
            rd,hg,ag=res
            out=E.determine_outcome(b.get("market"),b.get("pick"),hg,ag)
            if out:
                D2=apply_settle(D2,idx,out,score=f"{int(hg)}:{int(ag)}"); upd+=1
        if upd>0:
            st.session_state.data=D2; save_data(D2); D=D2
            st.toast(f"Автосинхронизация: закрыто {upd} ставок",icon="🔄")
    st.session_state["_auto_settled_done"]=True

st.markdown(f"""
<div class="hero">
 <h1>NEURO BET PRO</h1>
 <p>v8.5 · футбол · temperature scaling · match_date в predict · кубок внутри модели · BTTS/DC в settle · кэш движка · сортировка ленты · переключаемые обои</p>
 <div class="kpis">
  <div class="kpi"><div class="t">Банкролл</div><div class="v y">{D['bank']:.0f} у.е.</div></div>
  <div class="kpi"><div class="t">В работе</div><div class="v">{sum(1 for b in D['bets'] if b['status']=='pending')}</div></div>
  <div class="kpi"><div class="t">Прибыль</div><div class="v {'g' if D['stats']['profit']>=0 else 'r'}">{D['stats']['profit']:+.0f}</div></div>
  <div class="kpi"><div class="t">Ошибок в логе</div><div class="v {'r' if E.ERR else 'g'}">{len(E.ERR)}</div></div>
 </div>
</div>""",unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Настройки")
    new_wall=st.selectbox("🖼 Обои",list(WALLS.keys()),index=list(WALLS.keys()).index(wall_key))
    if new_wall!=wall_key:
        D.setdefault("meta",{})["wall"]=new_wall
        save_data(D); st.rerun()
    goal=st.selectbox("🎯 Цель стратегии",list(GOALS.keys()),index=0)
    PR0=GOALS[goal]
    kelly_frac=st.slider("Келли (дробь)",0.10,0.40,0.25,0.05)
    mode=st.radio("Режим ленты",["🎯 Высокая проходимость","💰 Валуи (EV)"])
    thr=st.slider("Порог проходимости, %",50,80,int(PR0["thr"]*100))/100
    min_edge=st.slider("Edge, п.п.",0,8,int(PR0["edge"]*100))/100
    min_ev=st.slider("Мин. EV, %",0,10,int(PR0["ev"]*100))/100
    use_dis=st.checkbox("Только расхождения с рынком (alpha)",value=PR0["dis"])
    use_bl=st.checkbox("Блэклист рынков из бэктеста",value=True)
    auto_hot=st.checkbox("🔥 Автодобавлять hot-ставки (флэт 1%)",value=False)
    lp=D.get("meta",{}).get("lp",{})
    if lp:
        st.markdown("**🧠 Гиперпараметры лиг**")
        for k,v in list(lp.items())[:6]:
            st.caption(f"{DIV_NAMES.get(k,k)}: ws={v['w_shots']:.2f} ρ={v['rho']:.2f} DC={v['w_dc']:.2f} T={v.get('temp',1.0):.2f}")
    with st.expander(f"🐞 Лог ошибок ({len(E.ERR)})"):
        if E.ERR:
            for line in E.ERR[-40:]: st.text(line)
        else: st.text("Ошибок нет.")
    if st.button("🔄 Сброс"):
        st.session_state.data=new_data(); save_data(st.session_state.data)
        st.rerun()

tab1,tab2,tab3,tab4,tab5=st.tabs(["🏟 Сканер","💼 Портфель","📈 Статистика","🧮 Калькулятор","🧪 Бэктест"])

with tab1:
    c1,c2=st.columns([4,1]); days=c1.slider("Горизонт, дней",1,21,10); scan=c2.button("⚡ СКАН",type="primary")
    blacklist=set(D.get("meta",{}).get("blacklist",[])) if use_bl else set()
    if scan:
        season=E.find_season(); pseason=E.prev_season(season)
        today=datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
        now=datetime.now(); limit=today+timedelta(days=days)
        fix,rep1=E.load_fixtures(); tsd,rep2=E.load_tsdb()
        train_divs=sorted({r.get("Div") for r in fix if r.get("Div")}) or ["E0","SP1","I1","D1","F1"]
        dp=E.load_many(train_divs,pseason); dc=E.load_many(train_divs,season)
        div_counts={}
        for dv in train_divs:
            cnt=sum(1 for src in (dp,dc) for r in src.get(dv,[]) if r.get("FTHG") not in (None,""))
            div_counts[dv]=cnt
        fp=E.engine_fingerprint(season,div_counts)
        engine=E.engine_cache_get(fp)
        trained=0
        if engine is None:
            engine=E.Engine()
            prog=st.progress(0.0,text="Самообучение (2 сезона)...")
            for i,dv in enumerate(train_divs):
                for src in (dp,dc):
                    rr=sorted([r for r in src.get(dv,[]) if E.parse_date(r.get("Date",""))],key=lambda r:E.parse_date(r["Date"]))
                    for j,r in enumerate(rr):
                        if r.get("FTHG") not in (None,"") and r.get("FTAG") not in (None,""):
                            try:
                                engine.learn_step(r["HomeTeam"],r["AwayTeam"],float(r["FTHG"]),float(r["FTAG"]),
                                                  r,lg=dv,match_num=j,total=max(1,len(rr)),match_date=E.parse_date(r.get("Date","")))
                                trained+=1
                            except Exception as e: E.log_err(f"train {dv}",e)
                prog.progress((i+1)/len(train_divs))
            prog.empty()
            E.engine_cache_put(fp,engine)
        PR=dict(PR0); PR.update(thr=thr,edge=min_edge,ev=min_ev,bank=D["bank"],kelly=kelly_frac)
        meta={"temp":round(engine.temp,3),"blacklist":D.get("meta",{}).get("blacklist",[]),
              "wall":D.get("meta",{}).get("wall","🌃 Неон-стадион"),
              "lp":{k:{**v,"temp":round(engine.temp,3)} for k,v in list(engine.lp.items())[:15]}}
        cards=[]; passed=0; inwin=0; withodds=0; new_bets=[]
        existing={b["match"]+"|"+b["pick"] for b in D["bets"]}
        for r in fix+tsd:
            try:
                d=E.parse_date(r.get("Date",""))
                if not d or not (today<=d<=limit): continue
                tm=(r.get("Time") or "").strip()
                if tm:
                    try:
                        hh,mm=tm.split(":")[:2]
                        if now>=d.replace(hour=int(hh),minute=int(mm))+timedelta(hours=2,minutes=15): continue
                    except Exception: pass
                h=(r.get("HomeTeam") or "").strip(); a=(r.get("AwayTeam") or "").strip()
                if not h or not a: continue
                inwin+=1
                lg=r.get("Div","G")
                P=engine.predict(h,a,lg,match_date=d,cup=E.is_cup(r))
                raw=(P["p1_raw"],P["x_raw"],P["p2_raw"])
                mkt=E.market_probs(r); Pb=E.blend_market(P,mkt,PR["w_market"])
                league=r.get("League") or DIV_NAMES.get(lg,"Лига "+str(lg))
                if any(E.best_odd(r,p) for p in ("П1","ТБ 2.5")): withodds+=1
                cands=E.build_candidates(Pb,r,PR,blacklist)
                rows,best,hot,card_clv,gap=E.evaluate_rows(cands,Pb,mkt,PR,engine,use_dis,row=r)
                if best: passed+=1
                tag="value" if best else ("hot" if hot else "")
                nd=(d-today).days
                when="сегодня" if nd==0 else ("завтра" if nd==1 else f"через {nd} дн")
                cards.append({"div":lg,"league":league,"match":f"{h} vs {a}",
                    "date":d.strftime("%d.%m")+(f" {tm}" if tm else ""),"when":when,
                    "dt":d.strftime("%Y-%m-%d %H:%M"),
                    "rows":rows,"best":best,"hot":hot[:3],"tag":tag,"lams":Pb["lams"],
                    "lams_g":Pb["lams_g"],"lams_s":Pb["lams_s"],"mkt":mkt,"raw":raw,"gap":gap,
                    "agree":Pb["agree"],"clv":card_clv,"p1":Pb["p1"],"px":Pb["x"],"p2":Pb["p2"],
                    "corners":Pb["corners"],"yellows":Pb["yellows"],"games":Pb["games"],
                    "fh":engine.form_str(h),"fa":engine.form_str(a),"cup":E.is_cup(r)})
                if best and best[5]>0:
                    key=f"{h} vs {a}|{best[1]}"
                    if key not in existing:
                        new_bets.append({"match":f"{h} vs {a}","div":lg,"league":league,"market":best[0],
                            "pick":best[1],"odds":best[2],"stake":best[5],"prob":best[4],"clv":card_clv,
                            "status":"pending","strat":"VALUE","date":d.strftime("%d.%m.%Y"),
                            "date_iso":d.strftime("%Y-%m-%d"),"score":None})
                        existing.add(key)
                elif auto_hot and hot and len(new_bets)<25:
                    hp=max(hot,key=lambda x:x[1]); key=f"{h} vs {a}|{hp[0]}"
                    if key not in existing:
                        new_bets.append({"match":f"{h} vs {a}","div":lg,"league":league,"market":"HOT",
                            "pick":hp[0],"odds":hp[2] or round(1/hp[1],2),"stake":round(D["bank"]*0.01,2),
                            "prob":hp[1],"clv":card_clv,"status":"pending","strat":"HOT",
                            "date":d.strftime("%d.%m.%Y"),"date_iso":d.strftime("%Y-%m-%d"),"score":None})
                        existing.add(key)
            except Exception as e: E.log_err("scan row",e)
        picks=build_picks(cards,thr,D["bank"],kelly_frac)
        D2=clone(D)
        D2["cards"]=cards; D2["picks"]=picks; D2["report"]=rep1+rep2; D2["meta"]=meta
        D2["bets"]=D2["bets"]+new_bets
        D2["funnel"]={"trained":trained,"fix":len(fix),"tsdb":len(tsd),"inwin":inwin,
                      "odds":withodds,"passed":passed,"added":len(new_bets)}
        st.session_state.data=D2; save_data(D2); st.rerun()
    fn=D.get("funnel")
    if fn: st.caption(f"Обучено {fn['trained']} · расписание {fn['fix']}+{fn['tsdb']} · в окне {fn['inwin']} · валуев {fn['passed']} · в портфель +{fn['added']}")
    with st.expander("🔌 Диагностика источников"):
        for line in D.get("report",[]): st.text(line)

    sc1,sc2=st.columns([3,1])
    sort_key=sc1.selectbox("Сортировка ленты",SORT_OPTIONS,index=0)
    sort_desc=sc2.checkbox("Обратный порядок",value=False)

    picks=D.get("picks",[])
    if picks:
        st.markdown("### 🎯 НА ЧТО СТАВИТЬ")
        for i,p in enumerate(picks,1):
            cls="value" if p["type"]=="value" else "hot"
            btype="🟢 ВАЛУЙ" if p["type"]=="value" else "🔥 Проходимость"
            m,alt,av=p["main"],p["alt"],p["avoid"]
            m_s=f"✅ <b class='y'>{esc(m['pick'])}</b> @ {m['odd_s']} (P {m['prob']*100:.0f}%)" if m else ""
            a_s=f"🔁 <b class='g'>{esc(alt['pick'])}</b> (P {alt['prob']*100:.0f}%)" if alt else ""
            v_s=f"⛔ <b class='r'>{esc(av['pick'])}</b>" if av else ""
            pin=f" · 📏 {p['clv']*100:+.1f}%" if p.get("clv") is not None else ""
            st.markdown(f"""
<div class="mcard {cls}">
 <span class='chip'>{esc(p['league'])}</span><span class='chip when'>📅 {esc(p['date'])} · {esc(p['when'])}</span>
 <span class="badge {'val' if p['type']=='value' else 'hot'}">{p['stars']}</span>
 <div class="teams">{i}. {esc(p['match'])}</div>
 <div class="verdict">🤖 {m_s} · {a_s} · {v_s}<br>➤ Ставь <b class="y">{esc(p['pick'])}</b> @ <b class="y">{p['odd_s']}</b> ·
  P <b class="g">{p['prob']*100:.0f}%</b> · сумма <b class="y">{p['stake']:.2f} у.е.</b> · {btype}{pin}<br>
  <span style="color:#c9d2e3">{esc(p['verdict'])}</span></div>
</div>""",unsafe_allow_html=True)
    cards_view=sorted(D.get("cards",[]),key=lambda c: card_sort_val(c,sort_key),reverse=sort_desc)
    shown=0
    for c in cards_view:
        if mode=="🎯 Высокая проходимость" and not (c["hot"] or c["tag"]): continue
        if mode=="💰 Валуи (EV)" and not c["best"]: continue
        st.markdown(render_match_card(c,thr,PR0),unsafe_allow_html=True); shown+=1
    if not shown and not picks: st.info("Нажми ⚡ СКАН.")

with tab2:
    st.header("💼 Портфель")
    cbtn1,cbtn2,cbtn3=st.columns(3)
    if cbtn1.button("🔄 Автосинхронизация"):
        D2=clone(D); upd=w=l=pu=0
        for idx,b in enumerate(D["bets"]):
            if b["status"]!="pending" or b.get("div") in (None,"TSDB"):
