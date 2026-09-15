import streamlit as st
import requests
import pandas as pd
import numpy as np
from scipy.stats import poisson
import json
import os
import datetime

st.set_page_config(page_title="AI Football Bot Pro", page_icon="⚽", layout="wide")

HISTORY_FILE = "bet_history.json"

def reset_history_file():
    clean_data = {
        "bank": 10000.0, 
        "weights": {"xg_w": 1.0, "form_w": 0.5, "odds_limit": 2.2},
        "bets": []
    }
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(clean_data, f, ensure_ascii=False, indent=4)
    return clean_data

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "weights" not in data:
                    data["weights"] = {"xg_w": 1.0, "form_w": 0.5, "odds_limit": 2.2}
                return data
        except:
            pass
    return reset_history_file()

def save_history(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if "app_data" not in st.session_state:
    st.session_state.app_data = load_history()

st.title("⚽ Автоматический AI-Аналитик Ставок (Самообучающаяся система)")

# --- БОКОВАЯ ПАНЕЛЬ ---
st.sidebar.header("🔑 Настройки и API-ключи")
odds_api_key = st.sidebar.text_input("The Odds API Key", type="password")
hours_ahead = st.sidebar.slider("Искать матчи на сколько часов вперед?", min_value=6, max_value=72, value=24, step=6)

st.sidebar.markdown("---")
st.sidebar.header("🧠 Состояние ИИ (Веса обучения)")
current_weights = st.session_state.app_data.get("weights", {"xg_w": 1.0, "odds_limit": 2.2})
st.sidebar.write(f"Важность xG-фактора: `1.0 → {current_weights.get('xg_w', 1.0):.3f}`")
st.sidebar.write(f"Лимит коэффициента: `{current_weights.get('odds_limit', 2.2):.2f}`")

st.sidebar.markdown("---")
st.sidebar.header("💰 Банкролл-менеджмент")
current_bank = st.session_state.app_data["bank"]
st.sidebar.metric(label="Виртуальный банк", value=f"{current_bank:.2f} у.е.")
STAKE_SIZE = 100.0

if st.sidebar.button("🔄 Сбросить всё (банк и веса)"):
    st.session_state.app_data = reset_history_file()
    st.sidebar.success("История и статистика полностью очищены!")
    st.rerun()

# --- СПИСОК ЛИГ ---
LEAGUES = [
    'soccer_epl', 
    'soccer_spain_la_liga', 
    'soccer_italy_serie_a',
    'soccer_germany_bundesliga', 
    'soccer_france_ligue_one', 
    'soccer_russia_premier_league',
    'soccer_uefa_champions_league',
    'soccer_uefa_europa_conference_league',
    'soccer_turkey_super_lig'
]

# --- АЛГОРИТМИЧЕСКИЙ ГЕНЕРАТОР ОБОСНОВАНИЙ ---
def get_smart_reason(m, best_edge):
    pick, prob, odd, edge = best_edge
    reasons = []
    
    if edge > 0.08:
        reasons.append(f"🔥 Высокий статистический перевес (+{edge*100:.1f}%)")
    elif edge > 0.04:
        reasons.append(f"✅ Уверенный валуйный сигнал (+{edge*100:.1f}%)")
    else:
        reasons.append(f"⚖️ Умеренный сигнал (+{edge*100:.1f}%)")
        
    reasons.append(f"Модель Пуассона оценивает вероятность исхода '{pick}' в {prob*100:.1f}%")
    
    if odd < 1.75:
        reasons.append("коэффициент надежного фаворита")
    elif odd <= 2.1:
        reasons.append("сбалансированный коэффициент в рамках риск-менеджмента")
    else:
        reasons.append("высокий коэффициент на грани допустимого лимита")
        
    return " • ".join(reasons)

# --- ОБУЧЕНИЕ ИИ НА РЕАЛЬНЫХ СЫГРАННЫХ МАТЧАХ ИЗ API ---
def train_on_real_recent_matches(odds_key):
    data = st.session_state.app_data
    weights = data["weights"]
    
    analyzed_count = 0
    errors_fixed = 0

    for league in LEAGUES:
        url = f"https://api.the-odds-api.com/v4/sports/{league}/scores/"
        params = {'apiKey': odds_key, 'daysFrom': 3}
        try:
            res = requests.get(url, params=params, timeout=8)
            if res.status_code == 200:
                events = res.json()
                for ev in events:
                    if ev.get('completed'):
                        scores = ev.get('scores', [])
                        ev_home, ev_away = ev.get('home_team'), ev.get('away_team')
                        if len(scores) == 2:
                            analyzed_count += 1
                            home_score = int(scores[0]['score']) if scores[0]['name'] == ev_home else int(scores[1]['score'])
                            away_score = int(scores[1]['score']) if scores[1]['name'] == ev_away else int(scores[0]['score'])
                            
                            if abs(home_score - away_score) >= 3:
                                weights["odds_limit"] = max(1.75, weights["odds_limit"] * 0.99)
                                weights["xg_w"] = min(2.5, weights["xg_w"] * 1.01)
                                errors_fixed += 1
        except:
            pass

    save_history(data)
    return f"Проанализировано реальных завершенных матчей: {analyzed_count}. Проведена адаптация весов (скорректировано по факторам сенсаций: {errors_fixed})."

# --- ПРОВЕРКА РЕЗУЛЬТАТОВ СВОИХ СТАВОК ---
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
                        ev_home, ev_away = ev.get('home_team'), ev.get('away_team')
                        scores = ev.get('scores', [])
                        if len(scores) == 2:
                            home_score = int(scores[0]['score']) if scores[0]['name'] == ev_home else int(scores[1]['score'])
                            away_score = int(scores[1]['score']) if scores[1]['name'] == ev_away else int(scores[0]['score'])
                            
                            winner = "П1" if home_score > away_score else ("Ничья (X)" if home_score == away_score else "П2")
                            
                            for idx, b in enumerate(st.session_state.app_data["bets"]):
                                if b["status"] == "pending" and b.get("home") == ev_home and b.get("away") == ev_away:
                                    if b["pick"] == winner:
                                        st.session_state.app_data["bets"][idx]["status"] = "won"
                                        # Возвращаем полную выплату, так как ставка уже была списана при оформлении
                                        payout = b['stake'] * b['odd']
                                        st.session_state.app_data["bank"] += payout
                                    else:
                                        st.session_state.app_data["bets"][idx]["status"] = "lost"
                                        # При проигрыше деньги не возвращаются (уже списаны)
                                    updated_count += 1
        except:
            pass

    save_history(st.session_state.app_data)
    return f"Готово! Обновлено статусов матчей: {updated_count}"

# --- КЛАСС АНАЛИЗА ---
class UltimateBot:
    def __init__(self, odds_key, hours_limit, weights):
        self.odds_key = odds_key
        self.hours_limit = hours_limit
        self.weights = weights

    def fetch_fixtures(self):
        board = []
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        max_time = now_utc + datetime.timedelta(hours=self.hours_limit)

        for league in LEAGUES:
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
                                    'league': league, 'home': home, 'away': away, 'time': commence_time_str,
                                    'h_odd': odds.get(home, 2.0), 'd_odd': odds.get('Draw', 3.3), 'a_odd': odds.get(away, 2.0)
                                })
            except:
                pass
        return board

    def predict_poisson(self, h_odd, a_odd):
        impl_h = 1 / h_odd
        impl_a = 1 / a_odd
        xg_w = self.weights.get("xg_w", 1.0)
        h_lam = max(0.6, min(3.5, 2.2 * (impl_h / (impl_h + impl_a + 0.1)) * 2 * xg_w))
        a_lam = max(0.5, min(3.2, 2.2 * (impl_a / (impl_h + impl_a + 0.1)) * 2))

        matrix = np.zeros((6, 6))
        for h in range(6):
            for a in range(6):
                matrix[h, a] = poisson.pmf(h, h_lam) * poisson.pmf(a, a_lam)
                
        p_home = np.sum(np.tril(matrix, -1))
        p_draw = np.sum(np.diagonal(matrix))
        p_away = np.sum(np.triu(matrix, 1))
        
        total = p_home + p_draw + p_away
        if total > 0:
            return p_home/total, p_draw/total, p_away/total
        return 0.45, 0.25, 0.30

# --- ИНТЕРФЕЙС ПРИЛОЖЕНИЯ ---
tab1, tab2, tab3 = st.tabs(["🎯 Анализ матчей", "📊 История и Самообучение ИИ", "⚙️ О системе"])

with tab1:
    if st.button("🚀 Загрузить матчи и проанализировать с учетом ИИ-памяти"):
        if not odds_api_key:
            st.warning("⚠️ Введите API ключ для The Odds API в боковой панели!")
        else:
            with st.spinner(f"ИИ применяет обученные веса (xG_w: {current_weights.get('xg_w', 1.0):.2f}) для поиска матчей..."):
                bot = UltimateBot(odds_api_key, hours_ahead, current_weights)
                matches = bot.fetch_fixtures()
                
                if matches:
                    analyzed_matches = []
                    for m in matches:
                        home, away = m['home'], m['away']
                        bh, bd, ba = m['h_odd'], m['d_odd'], m['a_odd']
                        
                        p_h, p_d, p_a = bot.predict_poisson(bh, ba)
                        
                        edges = [("П1", p_h, bh, (p_h * bh) - 1), 
                                 ("Ничья (X)", p_d, bd, (p_d * bd) - 1), 
                                 ("П2", p_a, ba, (p_a * ba) - 1)]
                        
                        best_edge = max(edges, key=lambda x: x[3])
                        max_allowed_odd = current_weights.get("odds_limit", 2.2)
                        
                        reason_text = get_smart_reason(m, best_edge)
                        
                        if best_edge[3] > 0.05 and best_edge[2] <= max_allowed_odd:
                            status = "green"
                            ai_text = f"🤖 Анализ ИИ: Строгий отбор пройден. Валуй на **{best_edge[0]}** (+{best_edge[3]*100:.1f}% перевес).<br>💡 *Почему интересен:* {reason_text}"
                        elif best_edge[3] > 0:
                            status = "blue"
                            ai_text = f"🤖 Анализ ИИ: Умеренный сигнал на **{best_edge[0]}**, коэффициент близко к лимиту.<br>💡 *Почему интересен:* {reason_text}"
                        else:
                            status = "red"
                            ai_text = f"🤖 Анализ ИИ: Матч отклонен. Перевеса нет или параметры нарушают правила.<br>💡 *Причина отклонения:* {reason_text}"

                        analyzed_matches.append({
                            'home': home, 'away': away, 'league': m.get('league', ''), 'time': m.get('time', ''),
                            'bh': bh, 'bd': bd, 'ba': ba,
                            'p_h': p_h, 'p_d': p_d, 'p_a': p_a, 'best_edge': best_edge,
                            'status': status, 'ai_text': ai_text
                        })
                    
                    st.success(f"Проанализировано матчей: {len(analyzed_matches)}")
                    st.session_state.current_board = analyzed_matches
                else:
                    st.info("В выбранном диапазоне матчей не найдено.")

    if "current_board" in st.session_state:
        st.markdown(f"### 🏆 Рекомендации матчей (Обученный ИИ)")
        for idx, m in enumerate(st.session_state.current_board):
            status = m['status']
            border_color = "#28a745" if status == "green" else ("#17a2b8" if status == "blue" else "#dc3545")
            box_color = "rgba(40, 167, 69, 0.15)" if status == "green" else ("rgba(23, 162, 184, 0.15)" if status == "blue" else "rgba(220, 53, 69, 0.15)")

            st.markdown(f"""
            <div style="background-color: {box_color}; border-left: 6px solid {border_color}; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
                <h4>{idx+1}. {m['home']} vs {m['away']} <span style="font-size: 12px; color: gray;">({m['league']})</span></h4>
                <p><b>Время (UTC):</b> {m['time']} | <b>Котировки:</b> П1: {m['bh']} | Х: {m['bd']} | П2: {m['ba']}</p>
                <p><b>Вероятности (ИИ):</b> Хозяева: {m['p_h']*100:.1f}% | Ничья: {m['p_d']*100:.1f}% | Гости: {m['p_a']*100:.1f}%</p>
                <p><i>{m['ai_text']}</i></p>
            </div>
            """, unsafe_allow_html=True)
            
            if m['status'] != "red":
                if st.button(f"Поставить 100 у.е. на мат. №{idx+1}", key=f"bet_{idx}"):
                    if st.session_state.app_data["bank"] >= STAKE_SIZE:
                        # Списываем сумму ставки с банка сразу
                        st.session_state.app_data["bank"] -= STAKE_SIZE
                        
                        bet_record = {
                            "match": f"{m['home']} vs {m['away']}",
                            "home": m['home'], "away": m['away'], "league": m['league'],
                            "pick": m['best_edge'][0], "odd": m['best_edge'][2],
                            "stake": STAKE_SIZE, "status": "pending", "date": str(datetime.date.today())
                        }
                        st.session_state.app_data["bets"].append(bet_record)
                        save_history(st.session_state.app_data)
                        st.success("Ставка записана, 100 у.е. списано с банка!")
                        st.rerun()
                    else:
                        st.error("Недостаточно средств в виртуальном банке!")

with tab2:
    st.markdown("### 🧠 Панель самообучения ИИ и История")
    
    col_l1, col_l2 = st.columns(2)
    
    with col_l1:
        if st.button("⚡ Обучить ИИ на реальных матчах из API (за 3 дня)"):
            if not odds_api_key:
                st.warning("Введите API ключ!")
            else:
                msg = train_on_real_recent_matches(odds_api_key)
                st.success(msg)
                st.rerun()
            
    with col_l2:
        if st.button("🔄 Проверить результаты моих ставок"):
            if not odds_api_key:
                st.warning("Введите API ключ!")
            else:
                msg = update_pending_results(odds_api_key)
                st.success(msg)
                st.rerun()

    history_data = st.session_state.app_data
    st.metric("Баланс банка", f"{history_data['bank']:.2f} у.е.")
    
    st.markdown("#### Активные веса нейросети:")
    st.json(history_data["weights"])
    
    st.markdown("---")
    st.markdown("#### 📊 Интерактивная статистика и фильтр прогнозов:")
    
    if "history_filter" not in st.session_state:
        st.session_state.history_filter = "all"
        
    bets_list = history_data["bets"]
    total_count = len(bets_list)
    wins_count = len([b for b in bets_list if b["status"] == "won"])
    losses_count = len([b for b in bets_list if b["status"] == "lost"])
    pending_count = len([b for b in bets_list if b["status"] == "pending"])
    
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        if st.button(f"📋 Всего: {total_count}", use_container_width=True):
            st.session_state.history_filter = "all"
    with col_s2:
        if st.button(f"🟢 Победы: {wins_count}", use_container_width=True):
            st.session_state.history_filter = "won"
    with col_s3:
        if st.button(f"🔴 Поражения: {losses_count}", use_container_width=True):
            st.session_state.history_filter = "lost"
    with col_s4:
        if st.button(f"⏳ В процессе: {pending_count}", use_container_width=True):
            st.session_state.history_filter = "pending"
            
    current_filter = st.session_state.history_filter
    st.info(f"📁 Показаны записи в категории: **{current_filter.upper()}**")
    
    filtered_bets = [b for b in bets_list if current_filter == "all" or b["status"] == current_filter]
    
    if not filtered_bets:
        st.write("В этой категории пока нет записей.")
    else:
        for real_idx, b in enumerate(filtered_bets):
            status_color = "🟢" if b['status'] == 'won' else ("🔴" if b['status'] == 'lost' else "⏳")
            st.write(f"{status_color} **{b['match']}** | Выбор: **{b['pick']}** (Кэф: {b.get('odd', 0)}) | Статус: **{b['status']}**")

with tab3:
    st.markdown("### ℹ️ О системе")
    st.write("""
    Эта программа сочетает в себе статистическое моделирование матчей (через распределение Пуассона и оценку потенциала), 
    алгоритмический генератор логических обоснований и механизм непрерывного самообучения на основе реальных данных из API.
    """)
