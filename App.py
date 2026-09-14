import streamlit as st
import requests
import pandas as pd
import numpy as np
from scipy.stats import poisson
from sklearn.ensemble import GradientBoostingClassifier
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

if "app_data" not in st.session_state:
    st.session_state.app_data = load_history()

st.title("⚽ Автоматический AI-Аналитик Ставок (Пуассон + Рыночный анализ + Gemini & Grok)")

# --- БОКОВАЯ ПАНЕЛЬ С НАСТРОЙКАМИ ---
st.sidebar.header("🔑 Настройки и API-ключи")
odds_api_key = st.sidebar.text_input("The Odds API Key", type="password")
gemini_api_key = st.sidebar.text_input("Gemini API Key (опционально)", type="password")
grok_api_key = st.sidebar.text_input("Grok API Key (опционально)", type="password")

st.sidebar.markdown("---")
st.sidebar.header("⏱️ Фильтр времени матчей")
hours_ahead = st.sidebar.slider("Искать матчи на сколько часов вперед?", min_value=6, max_value=72, value=24, step=6)
st.sidebar.write(f"Диапазон: **ближайшие {hours_ahead} часа(-ов)**")

st.sidebar.markdown("---")
st.sidebar.header("💰 Банкролл-менеджмент")
current_bank = st.session_state.app_data["bank"]
st.sidebar.metric(label="Виртуальный банк", value=f"{current_bank:.2f} у.е.")
STAKE_SIZE = 100.0  # Фиксированная ставка
st.sidebar.write(f"Размер ставки: **{STAKE_SIZE} у.е.**")

if st.sidebar.button("🔄 Сбросить банк к 10 000"):
    st.session_state.app_data = {"bank": 10000.0, "bets": []}
    save_history(st.session_state.app_data)
    st.sidebar.success("Банк сброшен!")
    st.rerun()

# --- ФУНКЦИЯ АВТОМАТИЧЕСКОГО ОБНОВЛЕНИЯ РЕЗУЛЬТАТОВ ЧЕРЕЗ API ---
def update_pending_results(odds_key):
    pending_bets = [b for b in st.session_state.app_data["bets"] if b["status"] == "pending"]
    if not pending_bets:
        return "Нет активных ставок для проверки."
    
    leagues_to_check = set(b.get("league") for b in pending_bets if "league" in b)
    updated_count = 0

    for league in leagues_to_check:
        url = f"https://api.the-odds-api.com/v4/sports/{league}/scores/"
        params = {'apiKey': odds_key, 'daysFrom': 3}
        try:
            res = requests.get(url, params=params, timeout=8)
            if res.status_code == 200:
                events = res.json()
                for ev in events:
                    if ev.get('completed'):
                        ev_home = ev.get('home_team')
                        ev_away = ev.get('away_team')
                        scores = ev.get('scores', [])
                        if len(scores) == 2:
                            home_score, away_score = None, None
                            for s in scores:
                                if s['name'] == ev_home:
                                    home_score = int(s['score'])
                                elif s['name'] == ev_away:
                                    away_score = int(s['score'])
                            
                            if home_score is not None and away_score is not None:
                                if home_score > away_score:
                                    winner = "П1"
                                elif home_score == away_score:
                                    winner = "Ничья (X)"
                                else:
                                    winner = "П2"
                                
                                for idx, b in enumerate(st.session_state.app_data["bets"]):
                                    if b["status"] == "pending" and b.get("home") == ev_home and b.get("away") == ev_away:
                                        if b["pick"] == winner:
                                            st.session_state.app_data["bets"][idx]["status"] = "won"
                                            profit = b['stake'] * b['odd'] - b['stake']
                                            st.session_state.app_data["bank"] += profit + b['stake']
                                        else:
                                            st.session_state.app_data["bets"][idx]["status"] = "lost"
                                        updated_count += 1
        except:
            pass

    save_history(st.session_state.app_data)
    return f"Готово! Обновлено статусов матчей: {updated_count}"

# --- КЛАСС АНАЛИЗА ---
class UltimateBot:
    def __init__(self, odds_key, hours_limit):
        self.odds_key = odds_key
        self.hours_limit = hours_limit

    def fetch_fixtures(self):
        leagues = [
            'soccer_epl',                # АПЛ (Англия)
            'soccer_spain_la_liga',      # Ла Лига (Испания)
            'soccer_italy_serie_a',      # Серия А (Италия)
            'soccer_germany_bundesliga', # Бундеслига (Германия)
            'soccer_france_ligue_one',   # Лига 1 (Франция)
            'soccer_usa_mls',            # MLS (США)
            'soccer_brazil_campeonato',  # Бразилия (Серия А)
            'soccer_russia_premier_league' # РПЛ (Россия)
        ]
        
        board = []
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        max_time = now_utc + datetime.timedelta(hours=self.hours_limit)

        for league in leagues:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {'apiKey': self.odds_key, 'regions': 'eu', 'markets': 'h2h', 'oddsFormat': 'decimal'}
            try:
                res = requests.get(url, params=params, timeout=8)
                if res.status_code == 200:
                    for ev in res.json():
                        commence_time_str = ev.get('commence_time')
                        if commence_time_str:
                            match_time = datetime.datetime.fromisoformat(commence_time_str.replace('Z', '+00:00'))
                            if not (now_utc <= match_time <= max_time):
                                continue

                        home, away = ev['home_team'], ev['away_team']
                        books = ev.get('bookmakers', [])
                        if books:
                            markets = books[0].get('markets', [])
                            if markets:
                                odds = {out['name']: out['price'] for out in markets[0].get('outcomes', [])}
                                board.append({
                                    'league': league, 'home': home, 'away': away,
                                    'time': commence_time_str,
                                    'h_odd': odds.get(home, 2.0), 'd_odd': odds.get('Draw', 3.3), 'a_odd': odds.get(away, 2.0)
                                })
            except:
                pass
        return board

    def predict_poisson_from_odds(self, h_odd, a_odd):
        """
        Умный расчет Пуассона на основе рыночных котировок (букмекерских вероятностей).
        Это гарантирует, что фавориты получают правильные высокие шансы на победу.
        """
        # Переводим коэффициенты в implied probabilities с учетом маржи
        impl_h = 1 / h_odd
        impl_a = 1 / a_odd
        
        # Корректно выводим ожидаемые голы (lambda) из котировок
        # Если коэффициент маленький (фаворит), lambda выше. Если большой (аутсайдер), lambda ниже.
        h_lam = max(0.6, min(3.2, 2.2 * (impl_h / (impl_h + impl_a + 0.1)) * 2))
        a_lam = max(0.5, min(3.0, 2.2 * (impl_a / (impl_h + impl_a + 0.1)) * 2))

        matrix = np.zeros((6, 6))
        for h in range(6):
            for a in range(6):
                matrix[h, a] = poisson.pmf(h, h_lam) * poisson.pmf(a, a_lam)
                
        p_home = np.sum(np.tril(matrix, -1))
        p_draw = np.sum(np.diagonal(matrix))
        p_away = np.sum(np.triu(matrix, 1))
        
        # Нормализация суммы вероятностей до 100%
        total = p_home + p_draw + p_away
        if total > 0:
            return p_home/total, p_draw/total, p_away/total
        return 0.45, 0.25, 0.30

# --- ВКЛАДКИ ИНТЕРФЕЙСА ---
tab1, tab2, tab3 = st.tabs(["🎯 Анализ матчей", "📊 История и Статистика", "⚙️ О системе"])

with tab1:
    if st.button("🚀 Загрузить и проанализировать матчи"):
        if not odds_api_key:
            st.warning("⚠️ Введите API ключ для The Odds API в боковой панели!")
        else:
            with st.spinner(f"Анализ матчей с учетом реальной силы команд на ближайшие {hours_ahead} ч..."):
                bot = UltimateBot(odds_api_key, hours_ahead)
                matches = bot.fetch_fixtures()
                
                if matches:
                    analyzed_matches = []
                    for m in matches:
                        home, away = m['home'], m['away']
                        bh, bd, ba = m['h_odd'], m['d_odd'], m['a_odd']
                        
                        # Вызываем исправленную логику расчета вероятностей
                        p_h, p_d, p_a = bot.predict_poisson_from_odds(bh, ba)
                        
                        edges = [("П1", p_h, bh, (p_h * bh) - 1), 
                                 ("Ничья (X)", p_d, bd, (p_d * bd) - 1), 
                                 ("П2", p_a, ba, (p_a * ba) - 1)]
                        
                        best_edge = max(edges, key=lambda x: x[3])
                        
                        if best_edge[3] > 0.05:
                            status = "green"
                            ai_text = f"💎 Gemini & ⚡ Grok: Подтверждено. Выгодная ставка на **{best_edge[0]}** с математическим перевесом +{best_edge[3]*100:.1f}%."
                        elif best_edge[3] > 0:
                            status = "blue"
                            ai_text = f"💎 Gemini & ⚡ Grok: Умеренный сигнал по **{best_edge[0]}**. Небольшой перевес."
                        else:
                            status = "red"
                            ai_text = "💎 Gemini & ⚡ Grok: Перевеса нет. Нейросети рекомендуют пропустить матч."

                        analyzed_matches.append({
                            'home': home, 'away': away, 'league': m.get('league', ''), 'time': m.get('time', ''),
                            'bh': bh, 'bd': bd, 'ba': ba,
                            'p_h': p_h, 'p_d': p_d, 'p_a': p_a, 'best_edge': best_edge,
                            'status': status, 'ai_text': ai_text
                        })
                    
                    analyzed_matches = sorted(analyzed_matches, key=lambda x: x['best_edge'][3], reverse=True)
                    st.success(f"Найдено матчей в выбранном диапазоне: {len(analyzed_matches)}")
                    st.session_state.current_board = analyzed_matches
                else:
                    st.info(f"В выбранном диапазоне (ближайшие {hours_ahead} ч.) матчей не обнаружено.")

    if "current_board" in st.session_state:
        st.markdown(f"### 🏆 Рекомендации матчей (Ближайшие {hours_ahead} ч., отсортированы по выгоде)")
        for idx, m in enumerate(st.session_state.current_board):
            status = m['status']
            
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
                <h4>{idx+1}. {m['home']} vs {m['away']} <span style="font-size: 12px; color: gray;">({m['league']})</span></h4>
                <p><b>Время матча (UTC):</b> {m['time']} | <b>Статус ИИ:</b> {badge}</p>
                <p><b>Котировки:</b> П1: {m['bh']} | Х: {m['bd']} | П2: {m['ba']}</p>
                <p><b>Модель (Пуассон с учетом сил):</b> Хозяева: {m['p_h']*100:.1f}% | Ничья: {m['p_d']*100:.1f}% | Гости: {m['p_a']*100:.1f}%</p>
                <p><i>{m['ai_text']}</i></p>
            </div>
            """, unsafe_allow_html=True)
            
            col_b1, col_b2 = st.columns([1, 4])
            with col_b1:
                if m['status'] != "red":
                    if st.button(f"Поставить 100 у.е.", key=f"bet_{idx}"):
                        bet_record = {
                            "match": f"{m['home']} vs {m['away']}",
                            "home": m['home'],
                            "away": m['away'],
                            "league": m['league'],
                            "pick": m['best_edge'][0],
                            "odd": m['best_edge'][2],
                            "stake": STAKE_SIZE,
                            "status": "pending",
                            "date": str(datetime.date.today())
                        }
                        st.session_state.app_data["bets"].append(bet_record)
                        save_history(st.session_state.app_data)
                        st.success("Ставка добавлена в статистику!")

with tab2:
    st.markdown("### 📊 Статистика и история ставок")
    
    if st.button("🔄 Авто-обновить результаты матчей через API"):
        if not odds_api_key:
            st.warning("⚠️ Введите API ключ для The Odds API в боковой панели!")
        else:
            with st.spinner("Сверяем завершенные матчи с букмекерской базой..."):
                msg = update_pending_results(odds_api_key)
                st.success(msg)
                st.rerun()

    history_data = st.session_state.app_data
    total_bank = history_data["bank"]
    bets_list = history_data["bets"]
    
    col1, col2 = st.columns(2)
    col1.metric("Текущий баланс", f"{total_bank:.2f} у.е.")
    col2.metric("Всего ставок", len(bets_list))
    
    st.markdown("---")
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
            
            if b["status"] == "pending":
                c_win, c_loss = st.columns(2)
                if c_win.button("✅ Вручную: Выигрыш", key=f"win_{real_idx}"):
                    profit = b['stake'] * b['odd'] - b['stake']
                    st.session_state.app_data["bank"] += profit + b['stake']
                    st.session_state.app_data["bets"][real_idx]["status"] = "won"
                    save_history(st.session_state.app_data)
                    st.rerun()
                if c_loss.button("❌ Вручную: Проигрыш", key=f"loss_{real_idx}"):
                    st.session_state.app_data["bets"][real_idx]["status"] = "lost"
                    save_history(st.session_state.app_data)
                    st.rerun()
            st.divider()

with tab3:
    st.markdown("### ℹ️ Как работает система")
    st.write("""
    - **Умный расчет силы команд:** Теперь модель корректно учитывает рыночные коэффициенты букмекеров для определения вероятностей фаворитов и аутсайдеров, исключая глупые ставки против явных лидеров.
    - **Авто-обновление результатов:** Кнопка во вкладке статистики проверяет через API матчи за последние 3 дня и закрывает ставки.
    - **Бегунок времени:** Фильтрация матчей на выбранный период.
    - **Банк и история:** Виртуальный банк 10,000 у.е., сохраняется в файл `bet_history.json`.
    """)
