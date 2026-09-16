import streamlit as st
import json, os, re, html
from datetime import datetime, timedelta
from collections import defaultdict
import nb_engine as E

st.set_page_config(page_title="NEURO BET PRO v8.3", page_icon="🏟", layout="wide")
HISTORY_FILE="neuro_bet_pro.json"
esc=html.escape

DIV_NAMES={"E0":"🏴󠁧󠁢󠁥󠁮󠁧󠁿 АПЛ","E1":"🏴󠁢󠁮󠁿 Чемпионшип","SC0":"🏴󠁢󠁣󠁿 Шотландия",
 "D1":"🇩🇪 Бундеслига","D2":"🇩🇪 2.Бундеслига","I1":"🇮🇹 Серия A","I2":"🇮🇹 Серия B",
 "SP1":"🇪🇸 Ла Лига","SP2":"🇪🇸 Сегунда","F1":"🇫🇷 Лига 1","F2":"🇫🇷 Лига 2",
 "N1":"🇳🇱 Эредивизи","B1":"🇧🇪 Про-лига","P1":"🇵🇹 Примейра","T1":"🇹🇷 Суперлига",
 "G1":"🇬🇷 Греция","R1":"🇷🇺 РПЛ","BR1":"🇧 Бразилия","C1":"🏆 ЛЧ","EL":"🏆 ЛЕ","EC":"🏆 ЛК"}
GOALS={
 "🎯 Проходимость":dict(w_market=0.65,thr=0.62,dis=False,edge=0.01,ev=0.01,corr=(1.30,2.30),min_games=10),
 "⚖️ Баланс":dict(w_market=0.40,thr=0.55,dis=True,edge=0.02,ev=0.02,corr=(1.40,4.20),min_games=8),
 "💰 Value":dict(w_market=0.20,thr=0.45,dis=True,edge=0.03,ev=0.02,corr=(1.40,4.20),min_games=6)}

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
.hero{padding:20px 26px;border-radius:22px;margin-bottom:16px;border:1px solid rgba(56,189,248,.35);
 background:linear-gradient(120deg,rgba(2,6,23,.96),rgba(6,78,59,.80) 55%,rgba(120,53,15,.75));}
.hero h1{margin:0;font-size:2.3rem;font-weight:900;color:#fff}
.hero p{margin:4px 0 0;color:#dbeafe;font-size:.92rem}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:14px}
.kpi{background:rgba(2,6,23,.92);border:1px solid rgba(148,163,184,.28);border-radius:14px;padding:12px 16px}
.kpi .t{color:#7dd3fc;font-size:.68rem;text-transform:uppercase;letter-spacing:1.2px}
.kpi .v{font-size:1.45rem;font-weight:800;color:#fff}
.kpi .v.g{color:#4ade80}.kpi .v.y{color:#facc15}.kpi .v.r{color:#f87171}
.mcard{background:rgba(8,12,24,.96);border:1px solid rgba(148,163,184,.22);border-radius:16px;padding:16px 18px;margin-bottom:12px}
.mcard.value{border-color:rgba(16,185,129,.65)}
.mcard.hot{border-color:rgba(250,204,21,.6)}
.chip{background:rgba(56,189,248,.18);color:#bae6fd;border:1px solid rgba(56,189,248,.45);padding:3px 10px;border-radius:999px;font-size:.72rem;font-weight:700;margin-right:6px}
.chip.when{background:rgba(250,204,21,.16);color:#fde68a;border-color:rgba(250,204,21,.45)}
.chip.warn{background:rgba(248,113,113,.18);color:#fecaca;border-color:rgba(248,113,113,.5)}
.badge{float:right;padding:4px 12px;border-radius:999px;font-size:.72rem;font-weight:800}
.badge.val{background:rgba(16,185,129,.22);color:#86efac;border:1px solid rgba(16,185,129,.6)}
.badge.hot{background:rgba(250,204,21,.2);color:#fde68a;border:1px solid rgba(250,204,21,.6)}
.badge.no{background:rgba(100,116,139,.2);color:#cbd5e1;border:1px solid rgba(100,116,139,.4)}
.teams{font-size:1.25rem;font-weight:800;color:#fff;margin:8px 0 2px}
.teams span{color:#94a3b8;font-weight:400}
.verdict{background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.3);border-radius:12px;padding:10px 14px;margin:8px 0;color:#e2e8f0;font-size:.88rem}
.verdict b.y{color:#facc15}.verdict b.g{color:#4ade80}.verdict b.r{color:#f87171}
.mrow{display:grid;grid-template-columns:70px 96px 70px 70px 62px 74px 26px;gap:8px;padding:5px 0;border-top:1px solid rgba(148,163,184,.12);font-size:.82rem;color:#e2e8f0}
.ok{color:#4ade80;font-weight:800}.nok{color:#64748b}
.evpos{color:#4ade80;font-weight:700}.evneg{color:#f87171;font-weight:700}
.mfoot{margin-top:8px;color:#cbd5e1;font-size:.78rem;display:flex;gap:16px;flex-wrap:wrap}
.mfoot b{color:#facc15}
.betcard{background:rgba(8,12,24,.96);border:1px solid rgba(148,163,184,.22);border-left:4px solid rgba(148,163,184,.4);border-radius:12px;padding:10px 14px;margin-bottom:8px;font-size:.86rem;color:#e2e8f0}
.betcard.pending{border-left-color:#facc15}.betcard.won{border-left-color:#22c55e}
.betcard.lost{border-left-color:#ef4444}.betcard.push{border-left-color:#64748b}
.betcard .score{font-weight:900;padding:2px 9px;border-radius:8px;margin-left:6px}
.betcard.won .score{background:rgba(34,197,94,.25);color:#86efac}
.betcard.lost .score{background:rgba(239,68,68,.25);color:#fca5a5}
</style>""", unsafe_allow_html=True)

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
        rows_html+=(f"<div class='mrow'><span style='color:#94a3b8'>{rw['mkt']}</span><b style='color:#facc15'>{esc(rw['pick'])}</b>"
                    f"<span style='color:#4ade80;font-weight:700'>{rw['prob']*100:.1f}%</span>"
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
 <div class="verdict">🤖 <b>Вердикт:</b> {m_s} · {a_s} · {v_s}<br><span style="color:#cbd5e1">{esc(vtext)}</span></div>
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
        score=f"<span class='score' style='background:rgba(239,68,68,.3);color:#fecaca'>🔴 LIVE {esc(str(live['home']))}:{esc(str(live['away']))}{esc(prog)}</span>"
    pin=f" · 📏 {b['clv']*100:+.1f}%" if b.get("clv") is not None else ""
    return (f"<div class='betcard {st_}'>{icon} <b>{esc(b['match'])}</b>{score}{strat}<br>"
            f"<span style='color:#94a3b8'>{esc(b.get('market',''))}</span> "
            f"<b style='color:#facc15'>{esc(b['pick'])}</b> @ <b>{b['odds']:.2f}</b> · "
            f"{b['stake']:.2f} у.е. · P={b.get('prob',0)*100:.0f}%{pin}</div>")

if "data" not in st.session_state: st.session_state.data=load_data()
D=st.session_state.data

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
 <h1>🏟 NEURO BET PRO v8.3</h1>
 <p>Футбол · temperature scaling · raw до калибровки · match_date в predict · кубок внутри модели · BTTS/DC в settle · кэш движка · retry · лог в файл</p>
 <div class="kpis">
  <div class="kpi"><div class="t">Банкролл</div><div class="v y">{D['bank']:.0f} у.е.</div></div>
  <div class="kpi"><div class="t">В работе</div><div class="v">{sum(1 for b in D['bets'] if b['status']=='pending')}</div></div>
  <div class="kpi"><div class="t">Прибыль</div><div class="v {'g' if D['stats']['profit']>=0 else 'r'}">{D['stats']['profit']:+.0f}</div></div>
  <div class="kpi"><div class="t">Ошибок в логе</div><div class="v {'r' if E.ERR else 'g'}">{len(E.ERR)}</div></div>
 </div>
</div>""",unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Настройки")
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
                rows,best,hot,card_clv,gap=E.evaluate_rows(cands,Pb,mkt,PR,engine,use_dis)
                if best: passed+=1
                tag="value" if best else ("hot" if hot else "")
                nd=(d-today).days
                when="сегодня" if nd==0 else ("завтра" if nd==1 else f"через {nd} дн")
                cards.append({"div":lg,"league":league,"match":f"{h} vs {a}",
                    "date":d.strftime("%d.%m")+(f" {tm}" if tm else ""),"when":when,
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
        cards.sort(key=lambda c:(c["tag"]=="value",c["tag"]=="hot",c["date"]),reverse=True)
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
  <span style="color:#cbd5e1">{esc(p['verdict'])}</span></div>
</div>""",unsafe_allow_html=True)
    shown=0
    for c in D.get("cards",[]):
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
            if b["status"]!="pending" or b.get("div") in (None,"TSDB"): continue
            bd=E.parse_date(b.get("date_iso","")) if b.get("date_iso") else None
            h,a=b["match"].split(" vs ")
            res=find_result(b.get("div"),h,a,bd)
            if not res: continue
            rd,hg,ag=res
            out=E.determine_outcome(b.get("market"),b.get("pick"),hg,ag)
            if out:
                D2=apply_settle(D2,idx,out,score=f"{int(hg)}:{int(ag)}"); upd+=1
                if out=="won": w+=1
                elif out=="lost": l+=1
                else: pu+=1
        st.session_state.data=D2; save_data(D2)
        st.toast(f"Закрыто {upd}: ✅{w} ❌{l} ⚪{pu}",icon="🔄")
        st.rerun()
    if cbtn2.button("🧐 Перепроверить все счета"):
        D2=clone(D); fixed=checked=0
        for idx,b in enumerate(D["bets"]):
            if b.get("div") in (None,"TSDB"): continue
            bd=E.parse_date(b.get("date_iso","")) if b.get("date_iso") else None
            h,a=b["match"].split(" vs ")
            res=find_result(b.get("div"),h,a,bd)
            if not res: continue
            checked+=1
            rd,hg,ag=res; sc=f"{int(hg)}:{int(ag)}"
            if b.get("status")=="pending" or b.get("score")!=sc:
                D2=recompute_bet(D2,idx,hg,ag,sc); fixed+=1
        st.session_state.data=D2; save_data(D2)
        st.success(f"Проверено: {checked} · исправлено: {fixed}"); st.rerun()
    live=None
    if cbtn3.button("🔴 Проверить LIVE"):
        live=E.load_livescores(); st.session_state["_live"]=live
        if not live: st.caption("Live-данных сейчас нет.")
    live=live or st.session_state.get("_live")
    if not D["bets"]: st.info("Пусто.")
    for i,b in enumerate(D["bets"]):
        lv=None
        if b["status"]=="pending" and live:
            h,a=b["match"].split(" vs "); lv=E.match_live(live,h,a)
        st.markdown(bet_card_html(b,lv),unsafe_allow_html=True)
        if b["status"]=="pending" and lv and (lv.get("status") or "").strip().lower() in E.FINISHED_STATUSES \
           and lv.get("home") not in (None,"") and lv.get("away") not in (None,""):
            hg,ag=E._f(lv["home"]),E._f(lv["away"])
            if hg is not None and ag is not None:
                out=E.determine_outcome(b.get("market"),b.get("pick"),hg,ag)
                if out:
                    st.session_state.data=apply_settle(D,i,out,score=f"{int(hg)}:{int(ag)}")
                    D=st.session_state.data  # фикс stale D
                    save_data(D)
                    st.toast(f"LIVE закрыто: {b['match'][:25]}… {int(hg)}:{int(ag)}",icon="🔴")
                    st.rerun()
        if b["status"]=="pending":
            cc=st.columns([1,1,1])
            sin=cc[0].text_input("Счёт",key=f"sc{i}",label_visibility="collapsed",placeholder="2:1")
            sc=sin.strip() if re.match(r"^\d+\s*:\s*\d+$",sin.strip()) else None
            if cc[1].button("✅ Зашло",key=f"w{i}"):
                st.session_state.data=apply_settle(D,i,"won",score=sc); save_data(st.session_state.data)
                st.toast(f"🟢 {b['match'][:25]}… +{b['stake']*(b['odds']-1):.0f} у.е.",icon="✅"); st.rerun()
            if cc[2].button("❌ Мимо",key=f"l{i}"):
                st.session_state.data=apply_settle(D,i,"lost",score=sc); save_data(st.session_state.data)
                st.toast(f"🔴 {b['match'][:25]}… -{b['stake']:.0f} у.е.",icon="❌"); st.rerun()

with tab3:
    st.header("📈 Статистика")
    s=D["stats"]; tot=s["won"]+s["lost"]
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Банк",f"{D['bank']:.2f}"); m2.metric("Ставок",tot)
    m3.metric("WinRate",f"{(s['won']/tot*100) if tot else 0:.1f}%"); m4.metric("Profit",f"{s['profit']:+.2f}")
    clvs=[b["clv"] for b in D["bets"] if b.get("clv") is not None]
    if clvs:
        avg=sum(clvs)/len(clvs); pos=sum(1 for x in clvs if x>0)/len(clvs)*100
        st.markdown(f"**📏 Средний перевес над открытием Pinnacle:** {avg*100:+.2f}% · доля >0: {pos:.0f}% "
                    +"(это не closing CLV: для настоящего CLV нужны closing odds)")
    settled=[b for b in D["bets"] if b.get("status") in ("won","lost","push")]
    if settled:
        curve=[]; run=0.0
        for b in settled:
            run+= b["stake"]*(b["odds"]-1) if b["status"]=="won" else (0.0 if b["status"]=="push" else -b["stake"])
            curve.append(run)
        st.line_chart(curve,height=180)
        st.subheader("🎯 По стратегиям: VALUE vs HOT")
        ss=strat_stats(D["bets"]); cA,cB=st.columns(2)
        for col,strat in ((cA,"VALUE"),(cB,"HOT")):
            v=ss[strat]
            with col:
                st.markdown(f"**{'🟢 VALUE (Kelly)' if strat=='VALUE' else '🔥 HOT (флэт 1%)'}**")
                st.metric("Ставок",v["n"]); st.metric("WinRate",f"{v['wr']:.1f}%")
                st.metric("PnL",f"{v['pnl']:+.1f}"); st.metric("ROI",f"{v['roi']:+.2f}%")
        cal=calibration_rows(D["bets"])
        if cal:
            st.subheader("🧪 Калибровка (P vs факт WR)")
            st.dataframe(cal,use_container_width=True,hide_index=True)
        wk=weekly_rows(D["bets"])
        if wk:
            st.subheader("📅 По неделям")
            st.dataframe(wk,use_container_width=True,hide_index=True)

with tab4:
    st.header("🧮 EV-калькулятор")
    q1,q2,q3=st.columns(3)
    p=q1.number_input("Вероятность, %",1,99,60); o=q2.number_input("Кэф",1.01,30.0,1.80); bk=q3.number_input("Банк",100.0,1e6,float(D["bank"]))
    ev=(p/100)*o-1
    st.markdown(f"**EV:** {ev*100:+.1f}% · **Безубыточность:** {100/o:.1f}% · **Келли:** {E.kelly(p/100,o,bk,kelly_frac):.2f} у.е.")
    if ev>0.02: st.success("✅ Можно ставить")
    else: st.warning("⛔ EV мал")

with tab5:
    st.header("🧪 Бэктест (walk-forward, match_date внутри)")
    b1,b2,b3,b4=st.columns(4)
    bt_div=b1.selectbox("Лига",list(DIV_NAMES.keys()),format_func=lambda k:DIV_NAMES[k])
    bt_season=b2.selectbox("Сезон",["2526","2425","2324"],index=1)
    bt_edge=b3.slider("Edge, п.п.",0,8,int(PR0["edge"]*100),key="bte")/100
    bt_mode=b4.selectbox("Стейк",["Flat","Kelly"])
    if st.button("▶️ Прогнать",type="primary"):
        PRb=dict(PR0); PRb.update(thr=thr,edge=bt_edge,ev=min_ev,bank=10000.0,kelly=0.25)
        log,eng=E.backtest(bt_div,bt_season,PRb,use_dis,bt_mode)
        bl=[k for k,v in eng.market_roi.items() if v["n"]>=30 and v["profit"]<-0.02]
        D2=clone(D); D2["meta"]["blacklist"]=bl
        D2["meta"]["lp"]={k:{**v,"temp":round(eng.temp,3)} for k,v in list(eng.lp.items())[:15]}
        st.session_state.data=D2; save_data(D2)
        if not log: st.warning("Нет сигналов: снизь edge или смени цель.")
        else:
            n=len(log); wins=sum(1 for x in log if x["won"])
            profit=sum(x["pnl"] for x in log); staked=sum(x["stake"] for x in log)
            roi=profit/staked*100 if staked else 0
            curve=0; peak=0; mdd=0
            for x in log:
                curve+=x["pnl"]; peak=max(peak,curve); mdd=max(mdd,peak-curve)
            mean_p=profit/n
            std_p=(sum((x["pnl"]-mean_p)**2 for x in log)/max(1,n-1))**0.5
            sharpe=mean_p/std_p if std_p else 0
            cl=[x["clv"] for x in log if x.get("clv") is not None]
            avg_clv=sum(cl)/len(cl) if cl else 0
            k1,k2,k3,k4,k5=st.columns(5)
            k1.metric("Ставок",n); k2.metric("WinRate",f"{wins/n*100:.1f}%")
            k3.metric("ROI",f"{roi:+.2f}%"); k4.metric("MaxDD",f"{mdd:.1f}"); k5.metric("Sharpe",f"{sharpe:.2f}")
            st.markdown(f"**📏 Перевес над Pinnacle (открытие): {avg_clv*100:+.2f}%** · T={eng.temp:.2f}")
