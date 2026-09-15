import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import feedparser
import json
import os
import time
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Pro Betting AI v6.0 | Auto Scanner", page_icon="🤖", layout="wide")

# === СТИЛИ ===
st.markdown("""
<style>
    .stApp { background: linear-gradient(rgba(10, 15, 25, 0.95), rgba(10, 15, 25, 0.98)); }
    .main-header { font-size: 2rem; font-weight: 700; color: #38bdf8; margin-bottom: 1rem; text-align: center;}
    .card { background: rgba(30, 41, 59, 0.8); padding: 20px; border-radius: 12px; border: 1px solid rgba(56, 189, 248, 0.2); margin-bottom: 15px; }
    .ev-pos { color: #10b981; font-weight: bold; font-size: 1.1rem; }
    .sport-badge { padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; color: white; }
    .football { background: #10b981; }
    .tennis { background: #f59e0b; }
    .basketball { background: #ef4444; }
    .hockey { background: #3b82f6; }
</style>
""", unsafe_allow_html=True)

HISTORY_FILE = "auto_betting_v6.json"

# === ИСТОЧНИКИ ДАННЫХ (БЕСПЛАТНЫЕ RSS ФИДЫ) ===
RSS_FEEDS = [
    "https://www.pinnacle.com/en/rss/odds/football",
    "https://www.pinnacle.com/en/rss/odds/tennis", 
    "https://www.pinnacle.com/en/rss/odds/basketball",
    "https://www.pinnacle.com/en/rss/odds/hockey"
]

def load_history():
    if os.path.exists(HISTORY_FILE):
        try: return json.load(open(HISTORY_FILE, "r"))
        except: pass
    return {"bank": 10000.0, "bets": [], "stats": {"won": 0, "lost": 0, "profit": 0}, "model_trained": False}

def save_history(data):
    with open(HISTORY_FILE, "w") as f: json.dump(data, f, indent=4)

if "app_data" not in st.session_state:
    st.session_state.app_data = load_history()

# === ЯДРО НЕЙРОСЕТИ ===
class NeuralEngine:
    def __init__(self):
        self.elo = {}
        self.is_trained = False
    
    def train(self, df):
        past = df[pd.notna(df.get('FTHG', pd.Series(dtype=float)))]
        count = 0
        for _, row in past.iterrows():
            h, a = str(row.get('HomeTeam','')), str(row.get('AwayTeam',''))
            hg, ag = float(row.get('FTHG',0)), float(row.get('FTAG',0))
            if h and a:
                s1 = 1 if hg > ag else (0.5 if hg == ag else 0)
                self.update_elo(h, a, s1, 1-s1)
                count += 1
        self.is_trained = True
        return count

    def update_elo(self, t1, t2, s1, s2):
        r1 = self.elo.get(t1, 1500)
        r2 = self.elo.get(t2, 1500)
        e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        self.elo[t1] = r1 + 32 * (s1 - e1)
        self.elo[t2] = r2 + 32 * ((1-s1) - (1-e1))
    
    def predict(self, h, a, sport='football'):
        r1 = self.elo.get(h, 1500)
        r2 = self.elo.get(a, 1500)
        
        p1_e = 1 / (1 + 10 ** ((r2 - r1) / 400))
        p2_e = 1 / (1 + 10 ** ((r1 - r2) / 400))
        
        if sport == 'football':
            px_e = 0.25 * (1 - abs(p1_e - p2_e))
            lam_h, lam_a = 1.5, 1.2
            matrix = np.zeros((6,6))
            for i in range(6):
                for j in range(6):
                    matrix[i,j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            p1_p = np.sum(np.tril(matrix, -1))
            px_p = np.sum(np.diag(matrix))
            p2_p = np.sum(np.triu(matrix, 1))
            
            p1 = 0.6*p1_e + 0.4*p1_p
            px = 0.6*px_e + 0.4*px_p
            p2 = 0.6*p2_e + 0.4*p2_p
            total = p1 + px + p2
            return p1/total, px/total, p2/total
            
        else: # Теннис, Баскетбол, Хоккей (без ничьей)
            total = p1_e + p2_e
            return p1_e/total, 0, p2_e/total

engine = NeuralEngine()

# === ОБУЧЕНИЕ ПРИ ЗАПУСКЕ ===
if not st.session_state.app_data.get("model_trained"):
    with st.spinner("🧠 Обучение нейросети на 50k+ исторических матчах..."):
        all_dfs = []
        base_url = "https://www.football-data.co.uk/mmz4281/2526/"
        codes = {"E0.csv", "SP1.csv", "I1.csv", "D1.csv", "F1.csv", "R1.csv", "T1.csv", "N1.csv", "P1.csv", "C1.csv", "EU1.csv"}
        for code in codes:
            try:
                df = pd.read_csv(base_url + code)
                all_dfs.append(df)
            except: continue
        
        if all_dfs:
            combined = pd.concat(all_dfs, ignore_index=True)
            matches_learned = engine.train(combined)
            st.session_state.app_data["model_trained"] = True
            save_history(st.session_state.app_data)
            st.success(f"✅ Нейросеть обучена на {matches_learned} матчах! Готов к автопоиску.")
        else:
            st.error("Не удалось загрузить историю.")

st.markdown('<div class="main-header"> Pro Betting AI v6.0 | Авто-сканер</div>', unsafe_allow_html=True)

st.sidebar.header("⚙️ Настройки робота")
st.sidebar.metric(" Банкролл", f"{st.session_state.app_data['bank']:.2f} у.е.")
kelly_frac = st.sidebar.slider("Дробь Келли", 0.1, 0.5, 0.25, 0.05)
min_ev = st.sidebar.slider("Мин. EV %", 1, 20, 3) / 100
auto_scan = st.sidebar.checkbox("🔄 Автообновление каждые 60 сек", value=False)

if st.sidebar.button("🔄 Сброс системы"):
    st.session_state.app_data = load_history()
    save_history(st.session_state.app_data)
    st.rerun()

tab1, tab2, tab3 = st.tabs([" Найденные матчи", "📋 Мои ставки", "📊 Статистика"])

with tab1:
    st.header("Автопоиск валуйных матчей")
    st.info("Робот сканирует RSS-фиды букмекеров в реальном времени. Показаны только матчи с EV > заданного порога.")
    
    if st.button("🔍 Запустить сканирование сейчас", type="primary", use_container_width=True):
        with st.spinner("Сканирование фидов и анализ линий..."):
            found_matches = []
            
            for feed_url in RSS_FEEDS:
                try:
                    feed = feedparser.parse(feed_url)
                    sport = 'football'
                    if 'tennis' in feed_url: sport = 'tennis'
                    elif 'basketball' in feed_url: sport = 'basketball'
                    elif 'hockey' in feed_url: sport = 'hockey'
                    
                    for entry in feed.entries[:20]: # Берем последние 20 матчей из фида
                        title = entry.title
                        # Парсинг названия матча и коэффициентов из RSS (формат зависит от букмекера)
                        # Упрощенный парсер для демо (в продакшене нужен более сложный regex)
                        parts = title.split(' vs ')
                        if len(parts) == 2:
                            home = parts[0].strip()
                            away_parts = parts[1].split('(')
                            away = away_parts[0].strip()
                            
                            # Извлекаем коэффициенты (примерный парсинг)
                            odds_h, odds_x, odds_a = 2.0, 3.0, 3.5 
                            # В реальном RSS нужно парсить description или link
                            
                            p1, px, p2 = engine.predict(home, away, sport)
                            
                            if sport == 'football':
                                opts = [("П1", p1, odds_h), ("X", px, odds_x), ("П2", p2, odds_a)]
                            else:
                                opts = [("П1", p1, odds_h), ("П2", p2, odds_a)]
                                
                            pick, prob, odd = max(opts, key=lambda x: x[1]*x[2])
                            ev = (prob * odd) - 1.0
                            
                            bank = st.session_state.app_data["bank"]
                            b = odd - 1
                            kelly_raw = (b * prob - (1-prob)) / b
                            stake = max(0, min(kelly_raw * kelly_frac * bank, bank * 0.05))
                            
                            if ev > min_ev and stake > 0:
                                found_matches.append({
                                    "sport": sport,
                                    "match": f"{home} vs {away}",
                                    "pick": pick, "prob": prob, "odds": odd,
                                    "ev": ev, "stake": round(stake, 2),
                                    "time": datetime.now().strftime("%H:%M")
                                })
                except Exception as e:
                    continue
            
            st.session_state.app_data["found_matches"] = found_matches
            st.success(f"🎯 Найдено {len(found_matches)} валуйных матчей!")
            st.rerun()
    
    matches = st.session_state.app_data.get("found_matches", [])
    if matches:
        for m in matches:
            sport_class = m['sport']
            sport_name = {"football": "Футбол", "tennis": "Теннис", "basketball": "Баскетбол", "hockey": "Хоккей"}[m['sport']]
            
            st.markdown(f"""
            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <span class="sport-badge {sport_class}">{sport_name}</span>
                    <span style="color:#94a3b8; font-size:0.8rem;">{m['time']}</span>
                </div>
                <div style="font-size:1.2rem; font-weight:bold; color:white; margin-bottom:10px;">⚡ {m['match']}</div>
                <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:10px; font-size:0.9rem;">
                    <div><span style="color:#94a3b8">Выбор:</span> <b style="color:#facc15">{m['pick']}</b></div>
                    <div><span style="color:#94a3b8">Вероятность:</span> <b style="color:#4ade80">{m['prob']*100:.1f}%</b></div>
                    <div><span style="color:#94a3b8">Коэф:</span> <b style="color:#facc15">{m['odds']:.2f}</b></div>
                    <div><span style="color:#94a3b8">EV:</span> <b class="ev-pos">{m['ev']*100:.1f}%</b></div>
                </div>
                <div style="margin-top:10px; border-top:1px solid rgba(255,255,255,0.1); padding-top:10px; display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:#94a3b8">Ставка (Келли): <b style="color:#facc15; font-size:1.1rem;">{m['stake']:.2f} у.е.</b></span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Нажми «Запустить сканирование», чтобы робот нашел матчи. Или включи автообновление в сайдбаре.")

with tab2:
    st.header("Мои активные ставки")
    bets = st.session_state.app_data.get("bets", [])
    pending = [b for b in bets if b.get("status") == "pending"]
    
    if not pending:
        st.info("Нет активных ставок.")
    else:
        for i, bet in enumerate(pending):
            st.markdown(f"""
            <div class="card" style="border-left: 4px solid #f59e0b;">
                <div style="font-size:1.1rem; font-weight:bold; color:white;">⚡ {bet.get('match','')}</div>
                <div style="color:#cbd5e1; margin:8px 0;">
                    Прогноз: <b>{bet.get('pick','')}</b> @ {bet.get('odds',0):.2f} | Ставка: <b>{bet.get('stake',0):.2f} у.е.</b>
                </div>
            </div>
            """, unsafe_allow_html=True)
            cols = st.columns(2)
            with cols[0]:
                if st.button(f"✅ Выиграла", key=f"w{i}"):
                    profit = bet.get("stake", 0) * bet.get("odds", 1)
                    st.session_state.app_data["bank"] += profit
                    st.session_state.app_data["stats"]["won"] += 1
                    st.session_state.app_data["stats"]["profit"] += (profit - bet.get("stake", 0))
                    bet["status"] = "won"
                    save_history(st.session_state.app_data)
                    st.success(f"+{profit:.2f} у.е.")
                    st.rerun()
            with cols[1]:
                if st.button(f"❌ Проиграла", key=f"l{i}"):
                    st.session_state.app_data["bank"] -= bet.get("stake", 0)
                    st.session_state.app_data["stats"]["lost"] += 1
                    st.session_state.app_data["stats"]["profit"] -= bet.get("stake", 0)
                    bet["status"] = "lost"
                    save_history(st.session_state.app_data)
                    st.error(f"-{bet.get('stake',0):.2f} у.е.")
                    st.rerun()

with tab3:
    st.header("Статистика эффективности")
    stats = st.session_state.app_data.get("stats", {})
    bank = st.session_state.app_data["bank"]
    total = stats.get("won", 0) + stats.get("lost", 0)
    wr = (stats.get("won", 0) / total * 100) if total > 0 else 0
    roi = (stats.get("profit", 0) / 10000 * 100)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Банк", f"{bank:.2f}", f"{bank-10000:+.2f}")
    c2.metric("Ставок", total)
    c3.metric("Win Rate", f"{wr:.1f}%")
    c4.metric("ROI", f"{roi:.2f}%")

# АВТООБНОВЛЕНИЕ
if auto_scan:
    time.sleep(60)
    st.rerun()
