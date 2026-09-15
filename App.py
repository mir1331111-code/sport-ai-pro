import streamlit as st
import csv
import io
import requests
import json
import os
from datetime import datetime, timedelta
from scipy.stats import poisson
import numpy as np

st.set_page_config(page_title="Multi-Sport Betting AI", page_icon="🎯", layout="wide")

HISTORY_FILE = "multi_sport_data.json"

def load_data():
    if os.path.exists(HISTORY_FILE):
        try:
            return json.load(open(HISTORY_FILE, "r"))
        except:
            pass
    return {"bank": 10000.0, "bets": [], "forecasts": [], "stats": {"won": 0, "lost": 0, "profit": 0}}

def save_data(data):
    json.dump(data, open(HISTORY_FILE, "w"), indent=4)

def load_csv(url):
    """Загрузка CSV без pandas"""
    try:
        r = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        return list(csv.DictReader(io.StringIO(r.text)))
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
        return []

def find_active_season(sport_code):
    """Автоопределение активного сезона"""
    base_urls = {
        "football": "https://www.football-data.co.uk/mmz4281/",
        "tennis": "https://www.tennis-data.co.uk/",
        "basketball": "https://www.basketball-data.co.uk/"
    }
    
    seasons = ["2627", "2526", "2425", "2025", "2024"]
    
    for season in seasons:
        test_url = f"{base_urls.get('football', '')}{season}/E0.csv"
        try:
            r = requests.head(test_url, timeout=5)
            if r.status_code == 200:
                return season
        except:
            continue
    
    return "2526"  # fallback

def parse_date(date_str):
    """Парсинг даты"""
    formats = ["%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except:
            continue
    return None

def calculate_elo(data, home_col='HomeTeam', away_col='AwayTeam', score1_col='FTHG', score2_col='FTAG'):
    """Расчёт Elo рейтингов"""
    elo = {}
    for row in data:
        h = row.get(home_col, '')
        a = row.get(away_col, '')
        s1 = row.get(score1_col)
        s2 = row.get(score2_col)
        
        if not h or not a or not s1 or not s2:
            continue
        
        try:
            s1, s2 = float(s1), float(s2)
        except:
            continue
        
        if h not in elo: elo[h] = 1500
        if a not in elo: elo[a] = 1500
        
        r1, r2 = elo[h], elo[a]
        e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        result = 1 if s1 > s2 else (0.5 if s1 == s2 else 0)
        
        elo[h] = r1 + 32 * (result - e1)
        elo[a] = r2 + 32 * ((1-result) - (1-e1))
    
    return elo

def predict_match(elo, home, away, sport="football"):
    """Предсказание вероятностей"""
    r1 = elo.get(home, 1500)
    r2 = elo.get(away, 1500)
    
    if sport in ["basketball", "hockey"]:
        # Для баскетбола/хоккея - бинарный исход (без ничьей)
        p_home = 1 / (1 + 10 ** ((r2 - r1) / 400))
        p_away = 1 - p_home
        return [("П1", p_home), ("П2", p_away)]
    else:
        # Для футбола/тенниса - с ничьей
        p_home = 1 / (1 + 10 ** ((r2 - r1) / 400))
        p_away = 1 / (1 + 10 ** ((r1 - r2) / 400))
        p_draw = 0.25 * (1 - abs(p_home - p_away))
        
        total = p_home + p_draw + p_away
        return [
            ("П1", p_home/total),
            ("X", p_draw/total),
            ("П2", p_away/total)
        ]

def kelly_stake(prob, odds, bank, fraction=0.25):
    """Расчёт ставки по Келли"""
    if prob <= 0 or odds <= 1:
        return 0
    b = odds - 1
    kelly = (b * prob - (1 - prob)) / b
    stake = max(0, kelly * fraction) * bank
    return round(min(stake, bank * 0.05), 2)

# Инициализация
if "data" not in st.session_state:
    st.session_state.data = load_data()

st.title("🎯 Multi-Sport Betting AI")

# Боковая панель
with st.sidebar:
    st.header("⚙️ Настройки")
    bank = st.session_state.data["bank"]
    st.metric("💰 Банк", f"{bank:.2f} у.е.")
    
    kelly_frac = st.slider("Дробь Келли", 0.1, 0.5, 0.25, 0.05)
    min_ev = st.slider("Мин EV %", 1, 15, 5) / 100
    
    if st.button("🔄 Сброс системы"):
        st.session_state.data = {"bank": 10000.0, "bets": [], "forecasts": [], "stats": {"won": 0, "lost": 0, "profit": 0}}
        save_data(st.session_state.data)
        st.rerun()

# Вкладки
tab1, tab2, tab3 = st.tabs(["🎯 Прогнозы", "📋 Ставки", "📊 Статистика"])

with tab1:
    st.header("Анализ матчей")
    
    # Выбор вида спорта
    sport = st.selectbox("Вид спорта", ["⚽ Футбол", "🎾 Теннис", "🏀 Баскетбол", "🏒 Хоккей"])
    
    # Лиги в зависимости от спорта
    leagues = {
        "⚽ Фут
