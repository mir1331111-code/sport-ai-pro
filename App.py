import streamlit as st
import requests
import csv
import io
import json
import os
import math
import time
from datetime import datetime, timedelta
from collections import defaultdict

st.set_page_config(page_title="Football Betting AI Expert Pro", page_icon="🚀", layout="wide")

HISTORY_FILE = "betting_expert_data.json"

LEAGUES = {
    "🏴󠁧󠁥󠁧 Англия (АПЛ)": "E0.csv",
    "🇪🇸 Испания (Ла Лига)": "SP1.csv",
    "🇮 Италия (Серия А)": "I1.csv",
    "🇩🇪 Германия (Бундеслига)": "D1.csv",
    "🇫 Франция (Лига 1)": "F1.csv",
    "🇳🇱 Нидерланды": "N1.csv",
    "🇵🇹 Португалия": "P1.csv",
    "🇹🇷 Турция": "T1.csv",
    "🇧🇪 Бельгия": "B1.csv",
    "🇷🇺 Россия": "R1.csv"
}

# ============================================================
# ИСПРАВЛЕННЫЙ ДВИЖОК
# ============================================================
class Engine:
    def __init__(self):
        self.elo = {}
        self.stats = defaultdict(lambda: {"hs": [], "hc": [], "as": [], "ac": [], "form": []})
        self.home_goals = []
        self.away_goals = []

    def add_result(self, h, a, hg, ag):
        # Elo с домашним бонусом
        rh = self.elo.get(h, 1500)
        ra = self.elo.get(a, 1500)
        eh = 1 / (1 + 10 ** ((ra - (rh + 60)) / 400))
        sh = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
        self.elo[h] = rh + 32 * (sh - eh)
        self.elo[a] = ra + 32 * ((1 - sh) - (1 - eh))

        s = self.stats
        s[h]["hs"].append(hg); s[h]["hc"].append(ag)
        s[a]["as"].append(ag); s[a]["ac"].append(hg)
        s[h]["form"].append(3 if hg > ag else (1 if hg == ag else 0))
        s[a]["form"].append(3 if ag > hg else (1 if hg == ag else 0))
        self.home_goals.append(hg); self.away_goals.append(ag)

        for t in (h, a):
            for k in s[t]:
                s[t][k] = s[t][k][-12:]  # храним последние 12

    def _mean(self, lst, default=1.0):
        return sum(lst) / len(lst) if lst else default

    def _form(self, team):
        f = self.stats[team]["form"][-5:]
        return (sum(f) / (len(f) * 3)) if f else 0.5

    def predict(self, h, a):
        """ИСПРАВЛЕНО: сила атаки/обороны как ОТНОШЕНИЕ к среднему по лиге"""
        lh = self._mean(self.home_goals, 1.5)
        la = self._mean(self.away_goals, 1.2)

        sh, sa = self.stats[h], self.stats[a]

        att_h = self._mean(sh["hs"], lh) / lh      # атака дома относительно лиги
        def_h = self._mean(sh["hc"], la) / la      # оборона дома (пропускает)
        att_a = self._mean(sa["as"], la) / la      # атака гостей
        def_a = self._mean(sa["ac"], lh) / lh      # оборона гостей (пропускает)

        form_h, form_a = self._form(h), self._form(a)

        # ПРАВИЛЬНАЯ формула: свои голы * чужая дыра в обороне
        lam_h = max(0.3, min(4.0, lh * att_h * def_a * 1.10 * (0.85 + 0.30 * form_h)))
        lam_a = max(0.25, min(3.5, la * att_a * def_h * 0.95 * (0.85 + 0.30 * form_a)))

        # Пуассон + Dixon-Coles поправка
        p_h = p_d = p_a = 0.0
        for i in range(7):
            for j in range(7):
                p = self._pois(lam_h, i) * self._pois(lam_a, j)
                if i == 0 and j == 0: p *= 1.08
                elif (i, j) in [(1, 0), (0, 1), (1, 1)]: p *= 0.96
                if i > j: p_h += p
                elif i == j: p_d += p
                else: p_a += p
        tot = p_h + p_d + p_a
        p_h, p_d, p_a = p_h / tot, p_d / tot, p_a / tot

        # Elo-смесь
        e = 1 / (1 + 10 ** ((self.elo.get(a, 1500) - self.elo.get(h, 1500) - 60) / 400))
        pd_e = 0.20 + 0.12 * (1 - abs(e - 0.5) * 2)
        pe_h, pe_a = e * (1 - pd_e), (1 - e) * (1 - pd_e)

        f_h = 0.72 * p_h + 0.28 * pe_h
        f_d = 0.72 * p_d + 0.28 * pd_e
        f_a = 0.72 * p_a + 0.28 * pe_a
        tot = f_h + f_d + f_a
        f_h, f_d, f_a = f_h / tot, f_d / tot, f_a / tot

        probs = {"П1": f_h, "X": f_d, "П2": f_a}
        ranked = sorted(probs.items(), key=lambda x: -x[1])
        margin = ranked[0][1] - ranked[1][1]  # отрыв от 2-го исхода
        data_games = min(len(sh["hs"]) + len(sh["as"]), len(sa["hs"]) + len(sa["as"]))

        return probs, ranked[0], margin, (lam_h, lam_a), data_games

    def _pois(self, l, k):
        return math.exp(-l) * l ** k / math.factorial(k)

# ============================================================
# ДАННЫЕ (CSV с РЕАЛЬНЫМИ коэффициентами, без API-ключа)
# ============================================================
@st.cache_data(ttl=1800)
def find_season():
    for s in ["2627", "2526", "2425"]:
        try:
            r = requests.head(f"https://www.football-data.co.uk/mmz4281/{s}/E0.csv", timeout=8)
            if r.status_code == 200:
                return s
        except Exception:
            continue
    return "2526"

@st.cache_data(ttl=1800)
def load_league(file, season):
    try:
        r = requests.get(f"https://www.football-data.co.uk/mmz4281/{season}/{file}",
                         timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return list(csv.DictReader(io.StringIO(r.text)))
    except Exception:
        return []

def parse_date(s):
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except Exception:
            continue
    return None

def get_odds(row):
    for pref in ("B365", "PS", "Max", "WH"):
        h, d, a = row.get(pref + "H"), row.get(pref + "D"), row.get(pref + "A")
        if h and d and a:
            try:
                return float(h), float(d), float(a)
            except Exception:
                continue
    return None

# ============================================================
# КЕЛЛИ + РИСКИ
# ============================================================
def kelly(prob, odds, bank, frac):
    if prob <= 0 or odds <= 1:
        return 0.0
    b = odds - 1
    k = (b * prob - (1 - prob)) / b
    return round(min(max(0, k * frac), 0.05) * bank, 2)

def load_data():
    if os.path.exists(HISTORY_FILE):
        try:
            return json.load(open(HISTORY_FILE, encoding="utf-8"))
        except Exception:
            pass
    return {"bank": 10000.0, "bets": [], "forecasts": [], "funnel": None,
            "stats": {"won": 0, "lost": 0, "profit": 0}}

def save_data(d):
    json.dump(d, open(HISTORY_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

if "data" not in st.session_state:
    st.session_state.data = load_data()

st.title("🚀 Football Betting AI Expert Pro")

with st.sidebar:
    st.header("⚙️ Управление")
    bank = st.session_state.data["bank"]
    st.metric("💰 Банк", f"{bank:.2f} у.е.")
    kelly_frac = st.slider("Келли (дробь)", 0.10, 0.40, 0.25, 0.05)
    min_ev = st.slider("Мин. EV (%)", 0, 15, 3) / 100
    min_prob = st.slider("Мин. вероятность (%)", 35, 75, 45) / 100
    min_margin = st.slider("Мин. отрыв от 2-го исхода (%)", 0, 25, 6) / 100
    if st.button("🔄 Сброс"):
        st.session_state.data = load_data.__wrapped__() if hasattr(load_data, "__wrapped__") else {
            "bank": 10000.0, "bets": [], "forecasts": [], "funnel": None,
            "stats": {"won": 0, "lost": 0, "profit": 0}}
        save_data(st.session_state.data)
        st.cache_data.clear()
        st.rerun()

tab1, tab2, tab3 = st.tabs(["🔍 Сканер матчей", "📋 Портфель", "📊 Статистика"])

with tab1:
    st.header("Поиск валуйных ставок с РЕАЛЬНЫМИ коэффициентами")
    sel = st.multiselect("Лиги", list(LEAGUES.keys()), default=list(LEAGUES.keys())[:5])
    days = st.slider("Горизонт (дней)", 1, 21, 10)
    show_all = st.checkbox("Показать все матчи окна (даже без EV)", value=True)

    if st.button("⚡ Сканировать", type="primary"):
        if not sel:
            st.warning("Выбери лиги")
            st.stop()

        season = find_season()
        st.session_state.data["season"] = season
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        limit = today + timedelta(days=days)

        funnel = {"loaded": 0, "played": 0, "in_window": 0, "with_odds": 0, "passed": 0}
        engine = Engine()
        all_rows = []

        prog = st.progress(0.0, text="Обучение модели на сыгранных матчах...")
        for i, name in enumerate(sel):
            rows = load_league(LEAGUES[name], season)
            funnel["loaded"] += len(rows)
            parsed = []
            for r in rows:
                r["_date"] = parse_date(r.get("Date", ""))
                r["_league"] = name
                parsed.append(r)
            # хронологически для обучения
            for r in sorted([x for x in parsed if x["_date"]], key=lambda x: x["_date"]):
                if r.get("FTHG") not in (None, "") and r.get("FTAG") not in (None, ""):
                    try:
                        engine.add_result(r["HomeTeam"], r["AwayTeam"],
                                          float(r["FTHG"]), float(r["FTAG"]))
                        funnel["played"] += 1
                    except Exception:
                        continue
            all_rows.extend(parsed)
            prog.progress((i + 1) / len(sel), text=f"Обучение: {name}")
        prog.empty()

        forecasts = []
        existing = {b["match"] for b in st.session_state.data["bets"]}
        added = 0

        for r in all_rows:
            d = r["_date"]
            if not d or not (today <= d <= limit):
                continue
            funnel["in_window"] += 1
            if r.get("FTHG") not in (None, ""):
                continue  # сыграно
            odds = get_odds(r)
            if not odds:
                continue
            funnel["with_odds"] += 1

            h, a = r.get("HomeTeam", ""), r.get("AwayTeam", "")
            if not h or not a:
                continue

            probs, (pick, prob), margin, lams, games = engine.predict(h, a)
            oh, od, oa = odds
            odd = {"П1": oh, "X": od, "П2": oa}[pick]
            ev = prob * odd - 1

            passed = (prob >= min_prob) and (margin >= min_margin) and (ev >= min_ev) and games >= 3
            if passed:
                funnel["passed"] += 1

            if passed or show_all:
                stake = kelly(prob, odd, bank, kelly_frac) if passed else 0.0
                forecasts.append({
                    "league": r["_league"], "match": f"{h} vs {a}",
                    "date": d.strftime("%d.%m %H:%M") if r.get("Time") else d.strftime("%d.%m"),
                    "pick": pick, "prob": prob, "odd": odd, "ev": ev,
                    "margin": margin, "lams": lams, "games": games,
                    "stake": stake, "passed": passed
                })

                if passed and prob >= 0.55 and f"{h} vs {a}" not in existing and stake > 0:
                    st.session_state.data["bets"].append({
                        "match": f"{h} vs {a}", "league": r["_league"],
                        "pick": pick, "odds": odd, "stake": stake,
                        "status": "pending", "prob": prob})
                    existing.add(f"{h} vs {a}")
                    added += 1

        forecasts.sort(key=lambda x: (x["passed"], x["ev"]), reverse=True)
        st.session_state.data["forecasts"] = forecasts
        st.session_state.data["funnel"] = funnel
        save_data(st.session_state.data)
        st.success(f"✅ Готово. Валуйных: {funnel['passed']}. В портфель добавлено: {added}")
        st.rerun()

    # ДИАГНОСТИКА ВОРОНКИ
    funnel = st.session_state.data.get("funnel")
    if funnel:
        with st.expander("🔬 Почему столько матчей прошло фильтр (диагностика)"):
            st.write(f"- Загружено строк: **{funnel['loaded']}**")
            st.write(f"- Сыгранных (обучение): **{funnel['played']}**")
            st.write(f"- Матчей в окне дат: **{funnel['in_window']}**")
            st.write(f"- Из них с коэффициентами: **{funnel['with_odds']}**")
            st.write(f"- Прошли фильтры EV/вероятность/отрыв: **{funnel['passed']}**")

    forecasts = st.session_state.data.get("forecasts", [])
    if forecasts:
        st.subheader(f"📊 Матчи в окне: {len(forecasts)}")
        for f in forecasts:
            color = "#10b981" if f["passed"] else "#64748b"
            badge = "🟢 ВАЛУЙ" if f["passed"] else "⚪ наблюдение"
            st.markdown(f"""
            <div style="background:rgba(30,41,59,.75);padding:16px;border-radius:12px;margin-bottom:10px;border-left:5px solid {color}">
              <div style="display:flex;justify-content:space-between">
                <span style="background:#38bdf8;padding:3px 10px;border-radius:6px;font-size:.75rem;color:#fff;font-weight:700">{f['league']}</span>
                <span style="color:#94a3b8">📅 {f['date']} | {badge}</span>
              </div>
              <div style="font-size:1.15rem;font-weight:700;color:#f8fafc;margin:8px 0">⚽ {f['match']}</div>
              <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;font-size:.9rem">
                <div><span style="color:#94a3b8">Прогноз:</span> <b style="color:#facc15">{f['pick']}</b></div>
                <div><span style="color:#94a3b8">P:</span> <b style="color:#4ade80">{f['prob']*100:.1f}%</b></div>
                <div><span style="color:#94a3b8">Кэф:</span> <b style="color:#facc15">{f['odd']:.2f}</b></div>
                <div><span style="color:#94a3b8">EV:</span> <b style="color:{'#10b981' if f['ev']>0 else '#ef4444'}">{f['ev']*100:+.1f}%</b></div>
                <div><span style="color:#94a3b8">Отрыв:</span> <b>{f['margin']*100:.1f}%</b></div>
              </div>
              <div style="margin-top:8px;color:#cbd5e1;font-size:.85rem">xG: {f['lams'][0]:.2f}–{f['lams'][1]:.2f} | данных матчей: {f['games']} | ставка Келли: <b style="color:#facc15">{f['stake']:.2f}</b></div>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("Нажми «Сканировать». Диагностика покажет, на каком этапе отсеиваются матчи.")

with tab2:
    st.header("📋 Портфель")
    if st.button("🔄 Синхронизировать результаты"):
        season = st.session_state.data.get("season", find_season())
        upd = 0
        for bet in [b for b in st.session_state.data["bets"] if b["status"] == "pending"]:
            rows = load_league(LEAGUES.get(bet["league"], "E0.csv"), season)
            h_t, a_t = bet["match"].split(" vs ")
            for r in rows:
                if r.get("HomeTeam") == h_t and r.get("AwayTeam") == a_t and r.get("FTHG") not in (None, ""):
                    hg, ag = float(r["FTHG"]), float(r["FTAG"])
                    res = "П1" if hg > ag else ("X" if hg == ag else "П2")
                    if res == bet["pick"]:
                        bet["status"] = "won"
                        profit = bet["stake"] * (bet["odds"] - 1)
                        st.session_state.data["bank"] += bet["stake"] + profit
                        st.session_state.data["stats"]["won"] += 1
                        st.session_state.data["stats"]["profit"] += profit
                    else:
                        bet["status"] = "lost"
                        st.session_state.data["stats"]["lost"] += 1
                        st.session_state.data["stats"]["profit"] -= bet["stake"]
                    upd += 1
                    break
        save_data(st.session_state.data)
        st.success(f"Обновлено: {upd}")
        st.rerun()

    bets = st.session_state.data["bets"]
    if not bets:
        st.info("Портфель пуст")
    for b in bets:
        icon = {"pending": "⏳", "won": "🟢", "lost": "🔴"}[b["status"]]
        st.markdown(f"{icon} **{b['match']}** | {b['pick']} @ {b['odds']:.2f} | {b['stake']:.2f} у.е. | P={b.get('prob',0)*100:.0f}%")

with tab3:
    s = st.session_state.data["stats"]
    total = s["won"] + s["lost"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Банк", f"{st.session_state.data['bank']:.2f}")
    c2.metric("Ставок", total)
    c3.metric("WinRate", f"{(s['won']/total*100) if total else 0:.1f}%")
    c4.metric("Profit", f"{s['profit']:+.2f}")
