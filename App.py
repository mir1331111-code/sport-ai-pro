import streamlit as st
import requests
import pandas as pd
import numpy as np
from scipy.stats import poisson
import json
import os
import datetime

st.set_page_config(page_title="AI Football Bot Pro", page_icon="⚽", layout="wide")

# Роскошные обои стадиона на фоне интерфейса + стилизация карточек
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(10, 15, 25, 0.82), rgba(10, 15, 25, 0.92)), 
                    url('https://images.unsplash.com/photo-1518091043644-c1d4457512c6?q=80&w=1920&auto=format&fit=crop');
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }
    .match-card {
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 18px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.6);
        backdrop-filter: blur(8px);
    }
    </style>
""", unsafe_allow_html=True)

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

st.title("⚽ AI Football Bot Pro — Статистический Анализатор")

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

CUP_LEAGUES = [
    'soccer_uefa_champions_league',
    'soccer_uefa_europa_conference_league'
]

# --- ГЕНЕРАТОР ОБОСНОВАНИЙ ---
def get_smart_reason(m, best_edge):
    pick, prob, odd, edge = best_edge
    reasons = []
    
    if edge > 0.08:
        reasons.append(f"Высокий статистический перевес (+{edge*100:.1f}%)")
    elif edge > 0.04:
        reasons.append(f"Уверенный валуйный сигнал (+{edge*100:.1f}%)")
    else:
        reasons.append(f"Умеренный сигнал (+{edge*100:.1f}%)")
        
    reasons.append(f"Вероятность исхода '{pick}' по модели: {prob*100:.1f}%")
    
    if odd < 1.75:
        reasons.append("коэффициент надежного фаворита")
    elif odd <= 2.1:
        reasons.append("сбалансированный коэффициент под риск-менеджмент")
    else:
        reasons.append("высокий коэффициент на грани лимита")
        
    return " • ".join(reasons)

# --- ОБУЧЕНИЕ ИИ ---
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
    return f"Проанализировано матчей: {analyzed_count}. Скорректировано весов: {errors_fixed}."

# --- ПРОВЕРКА СТАВОК ---
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
                                        st.session_state.app_data["bank"] += b['stake'] * b['odd']
                                    else:
                                        st.session_state.app_data["bets"][idx]["status"] = "lost"
                                    updated_count += 1
        except:
            pass

    save_history(st.session_state.app_data)
    return f"Обновлено статусов матчей: {updated_count}"

# --- АНАЛИЗАТОР ---
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
    if st.button("🚀 Загрузить матчи и проанализировать"):
        if not odds_api_key:
            st.warning("⚠️ Введите API ключ для The Odds API в боковой панели!")
        else:
            with st.spinner("Анализ расписания и расчет вероятностей..."):
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
                            ai_text = f"✅ Валуйный сигнал на **{best_edge[0]}** (+{best_edge[3]*100:.1f}% перевес).<br>💡 *Обоснование:* {reason_text}"
                        elif best_edge[3] > 0:
                            status = "blue"
                            ai_text = f"⚖️ Умеренный сигнал на **{best_edge[0]}**.<br>💡 *Обоснование:* {reason_text}"
                        else:
                            status = "red"
                            ai_text = f"❌ Матч отклонен (нет перевеса или лимиты нарушены).<br>💡 *Причина:* {reason_text}"

                        analyzed_matches.append({
                            'home': home, 'away': away, 'league': m.get('league', ''), 'time': m.get('time', ''),
                            'bh': bh, 'bd': bd, 'ba': ba,
                            'p_h': p_h, 'p_d': p_d, 'p_a': p_a, 'best_edge': best_edge,
                            'status': status, 'ai_text': ai_text
                        })
                    
                    st.success(f"Успешно проанализировано матчей: {len(analyzed_matches)}")
                    st.session_state.current_board = analyzed_matches
                else:
                    st.info("В выбранном диапазоне матчей не найдено.")

    if "current_board" in st.session_state:
        st.markdown("### 🏆 Рекомендации матчей")
        for idx, m in enumerate(st.session_state.current_board):
            league_name = m['league']
            is_cup = league_name in CUP_LEAGUES
            status = m['status']
            
            # Настройка цветов рамок и фона для каждого типа матча
            if is_cup:
                border_color = "#ffc107"  # Желтый (Кубок / Еврокубок)
                bg_color = "rgba(255, 193, 7, 0.12)"
                badge_text = "🏆 **[КУБКОВЫЙ / ЕВРОКУБКОВЫЙ ТУРНИР]** — ⚠️ *Повышенный риск ротации состава!*"
            elif status == "green":
                border_color = "#28a745"  # Зеленый (Отличный валуй)
                bg_color = "rgba(40, 167, 69, 0.12)"
                badge_text = "🟢 **[ВЫСОКИЙ ВАЛУЙ]** — Рекомендовано к ставке"
            elif status == "blue":
                border_color = "#17a2b8"  # Синий (Умеренный)
                bg_color = "rgba(23, 162, 184, 0.12)"
                badge_text = "🔵 **[УМЕРЕННЫЙ СИГНАЛ]** — Ставка под контролем"
            else:
                border_color = "#dc3545"  # Красный (Пропуск)
                bg_color = "rgba(220, 53, 69, 0.12)"
                badge_text = "🔴 **[ПРОПУСК МАТЧА]** — Высокие риски / нет перевеса"

            # Рендер карточки с полноценной цветной подсветкой и логотипами-иконками
            st.markdown(f"""
            <div style="background-color: {bg_color}; border-left: 6px solid {border_color}; border-radius: 10px; padding: 16px; margin-bottom: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.4);">
                <p style="color: {border_color}; font-weight: bold; margin-bottom: 6px; font-size: 13px;">{badge_text}</p>
                <h4 style="margin-top: 0; color: #ffffff;">🛡️ {idx+1}. {m['home']} <span style="color: #ff4b4b;">VS</span> ⚔️ {m['away']}</h4>
                <p style="color: #cbd5e1; font-size: 14px; margin-bottom: 8px;">🌍 <b>Лига:</b> {league_name} &nbsp;|&nbsp; ⏰ <b>Время (UTC):</b> {m['time']}</p>
                <p style="color: #e2e8f0; font-size: 14px;">📊 <b>Котировки:</b> П1: <code>{m['bh']}</code> | Х: <code>{m['bd']}</code> | П2: <code>{m['ba']}</code></p>
                <p style="color: #e2e8f0; font-size: 14px;">🤖 <b>Вероятности ИИ:</b> Хозяева: <code>{m['p_h']*100:.1f}%</code> | Ничья: <code>{m['p_d']*100:.1f}%</code> | Гости: <code>{m['p_a']*100:.1f}%</code></p>
                <hr style="border-color: rgba(255,255,255,0.1); margin: 10px 0;">
                <p style="font-style: italic; color: #f8fafc; margin-bottom: 0;">{m['ai_text']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if m['status'] != "red":
                if st.button(f"💵 Поставить 100 у.е. на матч №{idx+1}", key=f"bet_{idx}"):
                    if st.session_state.app_data["bank"] >= STAKE_SIZE:
                        st.session_state.app_data["bank"] -= STAKE_SIZE
                        bet_record = {
                            "match": f"{m['home']} vs {m['away']}",
                            "home": m['home'], "away": m['away'], "league": m['league'],
                            "pick": m['best_edge'][0], "odd": m['best_edge'][2],
                            "stake": STAKE_SIZE, "status": "pending", "date": str(datetime.date.today())
                        }
                        st.session_state.app_data["bets"].append(bet_record)
                        save_history(st.session_state.app_data)
                        st.success("Ставка успешно принята!")
                        st.rerun()
                    else:
                        st.error("Не хватает средств в виртуальном банке!")

with tab2:
    st.markdown("### 🧠 Панель самообучения ИИ и История")
    
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        if st.button("⚡ Обучить ИИ на реальных матчах из API"):
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
    
    st.markdown("#### Активные веса модели:")
    st.json(history_data["weights"])
    
    st.markdown("---")
    st.markdown("#### 📊 История ставок:")
    bets_list = history_data["bets"]
    if not bets_list:
        st.write("История пока пуста.")
    else:
        for b in bets_list:
            status_emoji = "🟢" if b['status'] == 'won' else ("🔴" if b['status'] == 'lost' else "⏳")
            st.write(f"{status_emoji} **{b['match']}** | Выбор: **{b['pick']}** (Кэф: {b.get('odd', 0)}) | Статус: **{b['status']}**")

with tab3:
    st.markdown("### ℹ️ О системе")
    st.write("""
    Программа использует математическое распределение Пуассона, анализирует котировки через The Odds API 
    и выводит данные в интерфейсе с цветовой индикацией валуев, кубковых матчей и стадионными обоями.
    """)
