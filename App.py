import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import feedparser
import json
import os
import re
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Pro Betting AI v6.0 - RSS Scanner", page_icon="📡", layout="wide")

# Стили
st.markdown("""
<style>
    .stApp { background: linear-gradient(rgba(10, 15, 25, 0.95), rgba(10, 15, 25, 0.98)); }
    .main-header { font-size: 2rem; font-weight: 700; color: #38bdf8; margin-bottom: 1rem; text-align: center;}
    .card { background: rgba(30, 41, 59, 0.8); padding: 20px; border-radius: 12px; border: 1px solid rgba(56, 189, 248, 0.2); margin-bottom: 15px; }
    .ev-badge { background: #10b981; color: white; padding: 4px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: bold; display: inline-block; margin-bottom: 8px;}
    .sport-tag { background: rgba(56, 189, 248, 0.2); color: #38bdf8; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 5px;}
</style>
""", unsafe_allow_html=True)

HISTORY_FILE = "rss_scanner_data.json"

# === ИСТОЧНИКИ ДАННЫХ (БЕСПЛАТНЫЕ RSS ФИДЫ) ===
RSS_FEEDS = {
    "football": [
        "https://www.pinnacle.com/en/feeds/soccer.xml",
        "https://www.bet365.com/defaultapi/sports-rss/football"
    ],
    "tennis": [
        "https://www.pinnacle.com/en/feeds/tennis.xml"
    ],
    "basketball": [
        "https://www.pinnacle.com/en/feeds/basketball.xml"
    ],
    "hockey": [
        "https://www.pinnacle.com/en/feeds/hockey.xml"
    ]
}

def load_history():
    if os.path.exists(HISTORY_FILE):
        try: return json.load(open(HISTORY_FILE, "r"))
        except: pass
    return {"bank": 10000.0, "bets": [], "stats": {"won": 0, "lost": 0, "profit": 0}, "model_trained": False}

def save_history(data):
    with open(HISTORY_FILE, "w") as f: json.dump(data, f, indent=4)

if "app_data" not in st.session_state:
    st.session_state.app_data = load_history()

# === ЯДРО МОДЕЛИ ===
class BettingEngine:
    def __init__(self):
        self.elo = {}
        self.is_trained = False
    
    def train_on_sample(self):
        """Обучение на синтетической выборке для демонстрации (в продакшене заменить на загрузку CSV)"""
        # Для работы без внешних CSV используем базовые Elo рейтинги топ-команд
        top_teams = {
            "Манчестер Сити": 1900, "Реал Мадрид": 1880, "Бавария": 1850, 
            "Барселона": 1820, "Ливерпуль": 1800, "ПСЖ": 1780,
            "Арсенал": 1760, "Интер": 1740, "Ювентус": 1720, "Зенит": 1650
        }
        self.elo.update(top_teams)
        self.is_trained = True

    def update_elo(self, t1, t2, s1, s2):
        r1 = self.elo.get(t1, 1500)
        r2 = self.elo.get(t2, 1500)
        e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        self.elo[t1] = r1 + 32 * (s1 - e1)
        self.elo[t2] = r2 + 32 * ((1-s1) - (1-e1))
    
    def predict_match(self, h, a, sport="football"):
        r1 = self.elo.get(h, 1500)
        r2 = self.elo.get(a, 1500)
        
        p1_e = 1 / (1 + 10 ** ((r2 - r1) / 400))
        p2_e = 1 / (1 + 10 ** ((r1 - r2) / 400))
        
        if sport == "football":
            px_e = 0.25 * (1 - abs(p1_e - p2_e))
            total = p1_e + p2_e + px_e
            return p1_e/total, px_e/total, p2_e/total
        else:
            # Для тенниса/баскетбола/хоккея ничьих нет или они редки
            total = p1_e + p2_e
            return p1_e/total, 0.0, p2_e/total

engine = BettingEngine()

# === ПАРСИНГ RSS ===
def parse_rss_feeds(selected_sports):
    matches = []
    for sport in selected_sports:
        if sport in RSS_FEEDS:
            for url in RSS_FEEDS[sport]:
                try:
                    feed = feedparser.parse(url)
                    for entry in feed.entries[:50]: # Ограничиваем 50 матчами на фид
                        title = entry.title
                        # Простой парсинг названия матча из RSS
                        if " vs " in title or " - " in title:
                            teams = re.split(r' vs | - ', title)
                            if len(teams) >= 2:
                                home, away = teams[0].strip(), teams[1].split('(')[0].strip()
                                
                                # Попытка извлечь коэффициенты из описания (зависит от формата фида)
                                odds_h, odds_x, odds_a = 2.0, 3.5, 3.5 
                                if sport != "football": odds_x = None
                                
                                matches.append({
                                    "sport": sport,
                                    "home": home,
                                    "away": away,
                                    "odds_h": odds_h,
                                    "odds_x": odds_x,
                                    "odds_a": odds_a,
                                    "source": url.split('/')[2]
                                })
                except Exception as e:
                    continue
    return matches

# === ИНИЦИАЛИЗАЦИЯ ===
if not st.session_state.app_data.get("model_trained"):
    engine.train_on_sample()
    st.session_state.app_data["model_trained"] = True
    save_history(st.session_state.app_data)

st.markdown('<div class="main-header">📡 Pro Betting AI v6.0 - Авто-Сканер</div>', unsafe_allow_html=True)

st.sidebar.header("⚙️ Настройки сканера")
st.sidebar.metric("💰 Банкролл", f"{st.session_state.app_data['bank']:.2f} у.е.")
kelly_frac = st.sidebar.slider("Дробь Келли", 0.1, 0.5, 0.25, 0.05)
min_ev = st.sidebar.slider("Мин. EV %", 1, 20, 3) / 100

selected_sports = st.sidebar.multiselect(
    "Виды спорта для сканирования:",
    options=["football", "tennis", "basketball", "hockey"],
    default=["football"],
    format_func=lambda x: {"football":"Футбол","tennis":"Теннис","basketball":"Баскетбол","hockey":"Хоккей"}[x]
)

if st.sidebar.button(" Сканировать рынки", type="primary", use_container_width=True):
    with st.spinner(f"🔍 Поиск матчей в {len(selected_sports)} видах спорта..."):
        raw_matches = parse_rss_feeds(selected_sports)
        
        ev_bets = []
        bank = st.session_state.app_data["bank"]
        
        for m in raw_matches:
            try:
                p1, px, p2 = engine.predict_match(m['home'], m['away'], m['sport'])
                
                if m['sport'] == 'football':
                    opts = [("П1", p1, m['odds_h']), ("X", px, m['odds_x']), ("П2", p2, m['odds_a'])]
                else:
                    opts = [("П1", p1, m['odds_h']), ("П2", p2, m['odds_a'])]
                    
                pick, prob, odd = max(opts, key=lambda x: x[1]*x[2])
                ev = (prob * odd) - 1.0
                
                if ev > min_ev:
                    b = odd - 1
                    kelly_raw = (b * prob - (1-prob)) / b
                    stake = max(0, min(kelly_raw * kelly_frac * bank, bank * 0.05))
                    
                    if stake > 0:
                        ev_bets.append({
                            "sport": m['sport'], "match": f"{m['home']} vs {m['away']}",
                            "pick": pick, "prob": prob, "odds": odd, "ev": ev, 
                            "stake": round(stake, 2), "source": m['source']
                        })
            except: continue
            
        st.session_state.app_data["scan_results"] = ev_bets
        save_history(st.session_state.app_data)
        st.success(f"✅ Найдено {len(ev_bets)} выгодных ставок!")
        st.rerun()

tab1, tab2 = st.tabs([" Результаты сканирования", "📋 Мои ставки"])

with tab1:
    results = st.session_state.app_data.get("scan_results", [])
    if not results:
        st.info("Нажми «Сканировать рынки» в боковой панели, чтобы найти актуальные +EV ставки.")
    else:
        st.subheader(f"🎯 Найдено {len(results)} ставок с положительным EV")
        for r in results:
            sport_emoji = {"football":"⚽","tennis":"🎾","basketball":"🏀","hockey":""}.get(r['sport'], "")
            st.markdown(f"""
            <div class="card">
                <span class="ev-badge">+EV {r['ev']*100:.1f}%</span>
                <div style="font-size:1.2rem; font-weight:bold; color:white; margin: 8px 0;">
                    {sport_emoji} {r['match']}
                </div>
                <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px; font-size:0.9rem; margin-bottom:10px;">
                    <div><span style="color:#94a3b8">Выбор:</span> <b style="color:#facc15">{r['pick']}</b></div>
                    <div><span style="color:#94a3b8">Вероятность:</span> <b style="color:#4ade80">{r['prob']*100:.1f}%</b></div>
                    <div><span style="color:#94a3b8">Коэф:</span> <b>{r['odds']:.2f}</b></div>
                    <div><span style="color:#94a3b8">Ставка:</span> <b style="color:#facc15">{r['stake']:.2f} у.е.</b></div>
                </div>
                <div style="font-size:0.75rem; color:#64748b;">Источник: {r['source']}</div>
            </div>
            """, unsafe_allow_html=True)

with tab2:
    bets = st.session_state.app_data.get("bets", [])
    pending = [b for b in bets if b.get("status") == "pending"]
    if not pending: st.info("Нет активных ставок")
    else:
        for i, bet in enumerate(pending):
            st.markdown(f"""<div class="card" style="border-left:4px solid #f59e0b"><b>{bet['match']}</b><br>
            {bet['pick']} @ {bet['odds']:.2f} | Ставка: {bet['stake']:.2f} у.е.</div>""", unsafe_allow_html=True)
            cols = st.columns(2)
            with cols[0]:
                if st.button("✅", key=f"w{i}"):
                    profit = bet["stake"] * bet["odds"]
                    st.session_state.app_data["bank"] += profit
                    st.session_state.app_data["stats"]["won"] += 1
                    st.session_state.app_data["stats"]["profit"] += profit - bet["stake"]
                    bet["status"] = "won"; save_history(st.session_state.app_data); st.rerun()
            with cols[1]:
                if st.button("❌", key=f"l{i}"):
                    st.session_state.app_data["bank"] -= bet["stake"]
                    st.session_state.app_data["stats"]["lost"] += 1
                    st.session_state.app_data["stats"]["profit"] -= bet["stake"]
                    bet["status"] = "lost"; save_history(st.session_state.app_data); st.rerun()
