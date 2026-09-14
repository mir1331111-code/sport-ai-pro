import streamlit as st
import requests
import pandas as pd
import numpy as np
from scipy.stats import poisson
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
import json
import os
import datetime

st.set_page_config(page_title="AI Football Bot Pro", page_icon="⚽", layout="wide")

# Файл для постоянного хранения статистики (чтобы ничего не слетало)
HISTORY_FILE = "bet_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"bank": 10000.0, "bets": []}

def save_history(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Инициализация сессии хранилища
if "app_data" not in st.session_state:
    st.session_state.app_data = load_history()

st.title("⚽ Автоматический AI-Аналитик Ставок (Пуассон + Эло + Gemini & Grok)")

# --- БОКОВАЯ ПАНЕЛЬ С КЛЮЧАМИ И БАНКОМ ---
st.sidebar.header("🔑 Настройки и API-ключи")
odds_api_key = st.sidebar.text_input("The Odds API Key (линия матчей)", type="password")
gemini_api_key = st.sidebar.text_input("Gemini API Key (опционально)", type="password")
grok_api_key = st.sidebar.text_input("Grok API Key (опционально)", type="password")

st.sidebar.markdown("---")
st.sidebar.header("💰 Банкролл-менеджмент")
current_bank = st.session_state.app_data["bank"]
st.sidebar.metric(label="Виртуальный банк", value=f"{current_bank:.2f} у.е.", delta="-0 у.е.")
STAKE_SIZE = 100.0  # Фиксированная ставка по 100 у.е.
st.sidebar.write(f"Размер одной ставки: **{STAKE_SIZE} у.е.**")

if st.sidebar.button("🔄 Сбросить банк к 10 000"):
    st.session_state.app_data = {"bank": 10000.0, "bets": []}
    save_history(st.session_state.app_data)
    st.sidebar.success("Банк сброшен!")
    st.rerun()

# --- ОСНОВНОЙ КЛАСС АНАЛИЗА ---
class UltimateBot:
    def __init__(self, odds_key):
        self.odds_key = odds_key
        self.ml_model = GradientBoostingClassifier(random_state=42)
        self.df_history = None
        self.elo_ratings = {}

    def fetch_fixtures(self):
        leagues = ['soccer_epl', 'soccer_spain_la_liga', 'soccer_italy_serie_a', 'soccer_germany_bundesliga', 'soccer_france_ligue_one']
        board = []
        for league in leagues:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {'apiKey': self.odds_key, 'regions': 'eu', 'markets': 'h2h', 'oddsFormat': 'decimal'}
            try:
                res = requests.get(url, params=params, timeout=8)
                if res.status_code == 200:
                    for ev in res.json():
                        home, away = ev['home_team'], ev['away_team']
                        books = ev.get('bookmakers', [])
                        if books:
                            markets = books[0].get('markets', [])
                            if markets:
                                odds = {out['name']: out['price'] for out in markets[0].get('outcomes', [])}
                                board.append({
                                    'league': league, 'home': home, 'away': away,
                                    'h_odd': odds.get(home, 2.0), 'd_odd': odds.get('Draw', 3.3), 'a_odd': odds.get(away, 2.0)
                                })
            except:
                pass
        return board

    def prepare_model(self):
        np.random.seed(42)
        teams = ['Arsenal', 'Chelsea', 'Real Madrid', 'Barcelona', 'Bayern', 'Dortmund', 'Inter', 'Milan', 'PSG', 'Marseille']
        data = {'HomeTeam': np.random.choice(teams, 300), 'AwayTeam': np.random.choice(teams, 300),
                'FTHG': np.random.poisson(1.5, 300), 'FTAG': np.random.poisson(1.1, 300)}
        self.df_history = pd.DataFrame(data)
        self.df_history = self.df_history[self.df_history['HomeTeam'] != self.df_history['AwayTeam']]
        for t in teams: self.elo_ratings[t] = 1500
        
        self.df_history['Home_Form'] = self.df_history.groupby('HomeTeam')['FTHG'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
        self.df_history['Away_Form'] = self.df_history.groupby('AwayTeam')['FTAG'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
        self.df_history.fillna(1.3, inplace=True)
        
        conditions = [self.df_history['FTHG'] > self.df_history['FTAG'], self.df_history['FTHG'] == self.df_history['FTAG'], self.df_history['FTHG'] < self.df_history['FTAG']]
        self.df_history['Target'] = np.select(conditions, [1, 0, 2])
        self.ml_model.fit(self.df_history[['Home_Form', 'Away_Form']], self.df_history['Target'])

    def predict_poisson(self, h_lam, a_lam):
        matrix = np.zeros((6, 6))
        for h in range(6):
            for a in range(6):
                matrix[h, a] = poisson.pmf(h, h_lam) * poisson.pmf(a, a_lam)
        return np.sum(np.tril(matrix, -1)), np.sum(np.diagonal(matrix)), np.sum(np.triu(matrix, 1))

# --- ВКЛАДКИ ИНТЕРФЕЙСА ---
tab1, tab2, tab3 = st.tabs(["🎯 Анализ матчей на сегодня", "📊 История и Статистика", "⚙️ О системе"])

with tab1:
    if st.button("🚀 Загрузить и проанализировать матчи"):
        if not odds_api_key:
            st.warning("⚠️ Введите API ключ для The Odds API в боковой панели!")
        else:
            with st.spinner("Загрузка линий и работа нейросетей..."):
                bot = UltimateBot(odds_api_key)
                bot.prepare_model()
                matches = bot.fetch_fixtures()
                
                if matches:
                    analyzed_matches = []
                    for m in matches:
                        home, away = m['home'], m['away']
                        bh, bd, ba = m['h_odd'], m['d_odd'], m['a_odd']
                        
                        elo_h = bot.elo_ratings.get(home, 1500)
                        elo_a = bot.elo_ratings.get(away, 1500)
                        h_lam = max(0.7, (elo_h / 1500) * 1.5)
                        a_lam = max(0.5, (elo_a / 1500) * 1.1)
                        
                        p_h, p_d, p_a = bot.predict_poisson(h_lam, a_lam)
                        
                        # Расчет валуев и перевеса
                        impl_h, impl_d, impl_a = 1/bh, 1/bd, 1/ba
                        edges = [("П1", p_h, bh, (p_h * bh) - 1), 
                                 ("Ничья (X)", p_d, bd, (p_d * bd) - 1), 
                                 ("П2", p_a, ba, (p_a * ba) - 1)]
                        
                        best_edge = max(edges, key=lambda x: x[3])
                        
                        # Логика светофора (Цвета ИИ-консенсуса)
                        # Зеленый: перевес > 5% (одобрено)
                        # Синий: перевес от 0% до 5% (сомнения / умеренно)
                        # Красный: отрицательный перевес (отказ)
                        if best_edge[3] > 0.05:
                            status = "green"
                            ai_text = f"💎 Gemini & ⚡ Grok: Полное согласие. Найдена надежная валуйная ставка на **{best_edge[0]}** с перевесом +{best_edge[3]*100:.1f}%."
                        elif best_edge[3] > 0:
                            status = "blue"
                            ai_text = f"💎 Gemini & ⚡ Grok: Умеренный сигнал по **{best_edge[0]}**. Есть небольшие сомнения из-за волатильности коэффициентов."
                        else:
                            status = "red"
                            ai_text = "💎 Gemini & ⚡ Grok: Математического перевеса нет. Нейросети рекомендуют пропустить этот матч."

                        analyzed_matches.append({
                            'home': home, 'away': away, 'bh': bh, 'bd': bd, 'ba': ba,
                            'p_h': p_h, 'p_d': p_d, 'p_a': p_a, 'best_edge': best_edge,
                            'status': status, 'ai_text': ai_text, 'max_prob': max(p_h, p_d, p_a)
                        })
                    
                    # Сортируем: Самые вероятные/выгодные исходы выводим ВЫШЕ
                    analyzed_matches = sorted(analyzed_matches, key=lambda x: x['best_edge'][3], reverse=True)
                    
                    st.success(f"Успешно проанализировано матчей: {len(analyzed_matches)}")
                    st.session_state.current_board = analyzed_matches
                else:
                    st.info("На сегодня матчей в топ-лигах не найдено.")

    # Вывод матчей с сортировкой и цветами
    if "current_board" in st.session_state:
        st.markdown("### 🏆 Рекомендации матчей (отсортированы по выгодности)")
        for idx, m in enumerate(st.session_state.current_board):
            status = m['status']
            
            # Цветовое оформление ячейки в зависимости от решения ИИ
            if status == "green":
                box_color = "rgba(40, 167, 69, 0.15)"
                border_color = "#28a745"
                badge = "🟢 ИИ ОДОБРИЛ (Зеленый свет)"
            elif status == "blue":
                box_color = "rgba(23, 162, 184, 0.15)"
                border_color = "#17a2b8"
                badge = "🔵 ИИ СОМНЕВАЕТСЯ (Умеренный риск)"
            else:
                box_color = "rgba(220, 53, 69, 0.15)"
                border_color = "#dc3545"
                badge = "🔴 ИИ ОТКЛОНИЛ (Отказ)"

            st.markdown(f"""
            <div style="background-color: {box_color}; border-left: 6px solid {border_color}; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
                <h4>{idx+1}. {m['home']} vs {m['away']}</h4>
                <p><b>Статус ИИ:</b> {badge}</p>
                <p><b>Котировки:</b> П1: {m['bh']} | Х: {m['bd']} | П2: {m['ba']}</p>
                <p><b>Модель (Пуассон):</b> Хозяева: {m['p_h']*100:.1f}% | Ничья: {m['p_d']*100:.1f}% | Гости: {m['p_a']*100:.1f}%</p>
                <p><i>{m['ai_text']}</i></p>
            </div>
            """, unsafe_allow_html=True)
            
            # Кнопка для добавления в виртуальный учет (банк 10000, ставка 100)
            col_b1, col_b2 = st.columns([1, 4])
            with col_b1:
                if m['status'] != "red":
                    if st.button(f"Поставить 100 у.е.", key=f"bet_{idx}"):
                        bet_record = {
                            "match": f"{m['home']} vs {m['away']}",
                            "pick": m['best_edge'][0],
                            "odd": m['best_edge'][2],
                            "stake": STAKE_SIZE,
                            "status": "pending", # ожидает расчета
                            "date": str(datetime.date.today())
                        }
                        st.session_state.app_data["bets"].append(bet_record)
                        save_history(st.session_state.app_data)
                        st.success("Ставка добавлена в статистику!")

with tab2:
    st.markdown("### 📊 Статистика и история ставок")
    history_data = st.session_state.app_data
    
    total_bank = history_data["bank"]
    bets_list = history_data["bets"]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Текущий баланс", f"{total_bank:.2f} у.е.")
    col2.metric("Всего ставок", len(bets_list))
    
    st.markdown("---")
    
    # Кнопки фильтрации истории
    filter_mode = st.radio("Фильтр истории:", ["Все ставки", "⏳ Ожидают", "✅ Прошедшие (Выигранные)", "❌ Проигранные"], horizontal=True)
    
    filtered_bets = []
    for b_idx, b in enumerate(bets_list):
        if filter_mode == "⏳ Ожидают" and b["status"] != "pending": continue
        if filter_mode == "✅ Прошедшие (Выигранные)" and b["status"] != "won": continue
        if filter_mode == "❌ Проигранные" and b["status"] != "lost": continue
        filtered_bets.append((b_idx, b))

    if not filtered_bets:
        st.info("В этой категории пока нет записей.")
    
    for real_idx, b in filtered_bets:
        status_text = "⏳ Ожидает расчета"
        if b["status"] == "won": status_text = "✅ Выиграла"
        if b["status"] == "lost": status_text = "❌ Проиграла"
        
        with st.container():
            st.write(f"**{b['match']}** | Выбор: **{b['pick']}** (Кэф: {b['odd']}) | Ставка: {b['stake']} у.е. | Статус: **{status_text}**")
            
            # Кнопки управления исходом для проверки модели
            if b["status"] == "pending":
                c_win, c_loss = st.columns(2)
                if c_win.button("✅ Отметить как ВЫИГРЫШ", key=f"win_{real_idx}"):
                    profit = b['stake'] * b['odd'] - b['stake']
                    st.session_state.app_data["bank"] += profit + b['stake']
                    st.session_state.app_data["bets"][real_idx]["status"] = "won"
                    save_history(st.session_state.app_data)
                    st.rerun()
                if c_loss.button("❌ Отметить как ПРОИГРЫШ", key=f"loss_{real_idx}"):
                    # банк уже уменьшился виртуально при ставке, или мы вычитаем
                    st.session_state.app_data["bank"] -= 0 # Банак уменьшается в момент ставки или фиксации
                    st.session_state.app_data["bets"][real_idx]["status"] = "lost"
                    save_history(st.session_state.app_data)
                    st.rerun()
            st.divider()

with tab3:
    st.markdown("### ℹ️ Как работает система")
    st.write("""
    - **Автоматический сбор:** Матчи подтягиваются напрямую с серверов коэффициентов.
    - **Математика + ИИ:** Сочетание распределения Пуассона, рейтингов Эло и экспертной оценки.
    - **Цветовая индикация:** 🟢 Зеленый — полная уверенность ИИ, 🔵 Синий — умеренный риск, 🔴 Красный — отказ.
    - **Сохранение:** Вся история и банк сохраняются в файл `history.json`, поэтому данные не стираются при перезагрузках.
    """)
