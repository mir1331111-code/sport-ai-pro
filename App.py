import streamlit as st
import requests
import pandas as pd
import numpy as np
from scipy.stats import poisson
import json
import os
import datetime
import io

st.set_page_config(page_title="AI Football Bot Pro", page_icon="⚽", layout="wide")

# Стильный дизайн, темная тема стадиона и цветовые стили
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(10, 15, 25, 0.90), rgba(10, 15, 25, 0.98)), 
                    url('https://images.unsplash.com/photo-1518091043644-c1d4457512c6?q=80&w=1920&auto=format&fit=crop');
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }
    .metric-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9));
        padding: 20px;
        border-radius: 14px;
        border: 1px solid rgba(56, 189, 248, 0.2);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        text-align: center;
    }
    .league-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
        color: #fff;
        margin-bottom: 6px;
    }
    .forecast-card {
        background: rgba(30, 41, 59, 0.7);
        padding: 16px;
        border-radius: 12px;
        border: 1px solid rgba(56, 189, 248, 0.2);
        margin-bottom: 12px;
    }
    .bet-card-pending {
        background: rgba(30, 41, 59, 0.7);
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.2);
        margin-bottom: 12px;
    }
    .bet-card-won {
        background: rgba(16, 185, 129, 0.12);
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
        margin-bottom: 12px;
    }
    .bet-card-lost {
        background: rgba(239, 68, 68, 0.12);
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
        margin-bottom: 12px;
    }
    </style>
""", unsafe_allow_html=True)

HISTORY_FILE = "bet_history.json"
STAKE_SIZE = 100.0

# --- КОНФИГУРАЦИЯ ЛИГ С ЦВЕТАМИ ---
LEAGUES_CONFIG = {
    'soccer_epl': {'name': 'Англия (ПЛ)', 'color': '#38bdf8'},
    'soccer_spain_la_liga': {'name': 'Испания (Ла Лига)', 'color': '#f43f5e'},
    'soccer_italy_serie_a': {'name': 'Италия (Серия А)', 'color': '#3b82f6'},
    'soccer_germany_bundesliga': {'name': 'Германия (Бундеслига)', 'color': '#ef4444'},
    'soccer_france_ligue_one': {'name': 'Франция (Лига 1)', 'color': '#8b5cf6'},
    'soccer_netherlands_eredivisie': {'name': 'Нидерланды (Эредивизи)', 'color': '#f97316'},
    'soccer_portugal_primeira_liga': {'name': 'Португалия (Примейра)', 'color': '#10b981'},
    'soccer_turkey_super_lig': {'name': 'Турция (Суперлига)', 'color': '#eab308'},
    'soccer_russia_premier_league': {'name': 'Россия (РПЛ)', 'color': '#06b6d4'},
    'soccer_usa_mls': {'name': 'США (MLS)', 'color': '#ec4899'},
    'soccer_uefa_champions_league': {'name': 'Лига Чемпионов УЕФА', 'color': '#6366f1'},
    'soccer_uefa_europa_league': {'name': 'Лига Европы УЕФА', 'color': '#f59e0b'},
    'soccer_uefa_conference_league': {'name': 'Лига Конференций УЕФА', 'color': '#14b8a6'},
    'soccer_efl_champ': {'name': 'Англия (Ченпионшип)', 'color': '#64748b'}
}

def reset_full_system():
    clean_data = {
        "bank": 10000.0, 
        "weights": {"xg_w": 1.0, "odds_limit": 2.5},
        "scanned_forecasts": [],
        "bets": [],
        "archive_matches": []
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
                    data["weights"] = {"xg_w": 1.0, "odds_limit": 2.5}
                if "scanned_forecasts" not in data:
                    data["scanned_forecasts"] = []
                if "archive_matches" not in data:
                    data["archive_matches"] = []
                if "bets" in data:
                    for b in data["bets"]:
                        if "stake" not in b or not b["stake"] or b["stake"] <= 0:
                            b["stake"] = STAKE_SIZE
                        if "reason" not in b or not b["reason"]:
                            b["reason"] = "Сигнал модели"
                        if "prob" not in b:
                            b["prob"] = 0.5
                return data
        except:
            pass
    return reset_full_system()

def save_history(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if "app_data" not in st.session_state:
    st.session_state.app_data = load_history()

st.title("⚽ AI Football Bot Pro — Умный рабочий терминал")

# --- БОКОВАЯ ПАНЕЛЬ ---
st.sidebar.header("🔑 Настройки API и Банк")
odds_api_key = st.sidebar.text_input("The Odds API Key", type="password")
hours_ahead = st.sidebar.slider("Искать матчи на сколько часов вперед?", min_value=6, max_value=168, value=72, step=6)
min_edge = st.sidebar.slider("Мин. перевес (Edge)", min_value=0.0, max_value=0.05, value=0.0, step=0.001, format="%.3f")

st.sidebar.markdown("---")
st.sidebar.header("🧠 Состояние ИИ")
current_weights = st.session_state.app_data.get("weights", {"xg_w": 1.0, "odds_limit": 2.5})
st.sidebar.write(f"Текущий вес xG: `{current_weights.get('xg_w', 1.0):.3f}`")

st.sidebar.markdown("---")
current_bank = st.session_state.app_data["bank"]
st.sidebar.metric(label="Баланс банкролла", value=f"{current_bank:.2f} у.е.")

if st.sidebar.button("🔄 Полный сброс системы"):
    st.session_state.app_data = reset_full_system()
    st.sidebar.success("Система сброшена!")
    st.rerun()

# --- СКАНИРОВАНИЕ И НОВЫЕ ПРОГНОЗЫ ---
def scan_new_forecasts(api_key):
    weights = st.session_state.app_data["weights"]
    xg_w = weights.get("xg_w", 1.0)
    odds_limit = weights.get("odds_limit", 2.5)
    
    found_forecasts = []
    checked_count = 0
    debug_logs = []
    
    for league_key, cfg in LEAGUES_CONFIG.items():
        url = f"https://api.the-odds-api.com/v4/sports/{league_key}/odds/?apiKey={api_key}&regions=eu,uk&markets=h2h&oddsFormat=decimal"
        try:
            response = requests.get(url, timeout=8)
            debug_logs.append(f"{cfg['name']}: статус `{response.status_code}`")
            
            if response.status_code != 200:
                continue
                
            events = response.json()
            for event in events:
                commence_time = event.get("commence_time")
                if commence_time:
                    match_dt = datetime.datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
                    now_dt = datetime.datetime.now(datetime.timezone.utc)
                    diff_hours = (match_dt - now_dt).total_seconds() / 3600
                    if diff_hours < 0 or diff_hours > hours_ahead:
                        continue
                
                home_team = event.get("home_team")
                away_team = event.get("away_team")
                bookmakers = event.get("bookmakers", [])
                
                if not bookmakers:
                    continue
                
                markets = bookmakers[0].get("markets", [])
                outcomes = []
                for m in markets:
                    if m.get("key") == "h2h":
                        outcomes = m.get("outcomes", [])
                        break
                
                if len(outcomes) < 2:
                    continue
                
                odds_dict = {o["name"]: o["price"] for o in outcomes}
                home_odd = odds_dict.get(home_team, 1.9)
                away_odd = odds_dict.get(away_team, 1.9)
                draw_odd = odds_dict.get("Draw", 3.2)
                
                checked_count += 1
                
                h_lam = max(0.6, min(3.5, 1.4 * xg_w))
                a_lam = max(0.5, min(3.2, 1.1))
                
                matrix = np.zeros((6, 6))
                for h in range(6):
                    for a in range(6):
                        matrix[h, a] = poisson.pmf(h, h_lam) * poisson.pmf(a, a_lam)
                
                p_home = np.sum(np.tril(matrix, -1))
                p_draw = np.sum(np.diagonal(matrix))
                p_away = np.sum(np.triu(matrix, 1))
                total = p_home + p_draw + p_away
                if total > 0:
                    p_home /= total
                    p_draw /= total
                    p_away /= total
                
                options = [
                    ("П1", p_home, home_odd),
                    ("Ничья (X)", p_draw, draw_odd),
                    ("П2", p_away, away_odd)
                ]
                
                best_pick = None
                max_edge = -999
                for name, prob, odd in options:
                    if odd <= odds_limit:
                        edge = (prob * odd) - 1.0
                        if edge > max_edge:
                            max_edge = edge
                            best_pick = (name, prob, odd, edge)
                
                if best_pick and best_pick[3] >= min_edge:
                    pick_name, prob, odd, edge = best_pick
                    win_pct = prob * 100
                    lose_pct = 100 - win_pct
                    reason = f"🟢 Шанс: {win_pct:.1f}% | 🔴 Риск: {lose_pct:.1f}% (Edge: +{edge*100:.1f}%)"
                    
                    found_forecasts.append({
                        "league_key": league_key,
                        "league_name": cfg['name'],
                        "league_color": cfg['color'],
                        "match": f"{home_team} vs {away_team}",
                        "pick": pick_name,
                        "odd": odd,
                        "prob": prob,
                        "reason": reason
                    })
        except Exception:
            continue
            
    st.session_state.app_data["scanned_forecasts"] = found_forecasts
    save_history(st.session_state.app_data)
    return checked_count, len(found_forecasts), debug_logs

# --- ДООБУЧЕНИЕ ИИ (НЕ С НУЛЯ) ---
def fine_tune_ai():
    weights = st.session_state.app_data["weights"]
    bets = st.session_state.app_data.get("bets", [])
    settled = [b for b in bets if b["status"] in ["won", "lost"]]
    
    if not settled:
        return "⚠️ Недостаточно завершенных ставок для дообучения. Сделайте несколько ставок и отметьте их результаты."
    
    correct = len([b for b in settled if b["status"] == "won"])
    accuracy = correct / len(settled)
    
    old_weight = weights["xg_w"]
    if accuracy >= 0.5:
        weights["xg_w"] = min(2.5, weights["xg_w"] * 1.02)
    else:
        weights["xg_w"] = max(0.5, weights["xg_w"] * 0.98)
        
    st.session_state.app_data["weights"] = weights
    save_history(st.session_state.app_data)
    return f"✅ ИИ успешно дообучен на основе {len(settled)} ставок! Точность серии: {accuracy*100:.1f}%. Вес xG изменен: {old_weight:.3f} ➡️ {weights['xg_w']:.3f}"

# --- ИНТЕРФЕЙС ВКЛАДОК ---
tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 Новые прогнозы", 
    "📜 История и Активные ставки", 
    "🧠 Дообучение ИИ", 
    "⚙️ О системе"
])

with tab1:
    st.markdown("### 🚀 Сканирование лиг и новые прогнозы модели")
    st.write("Здесь отображаются только свежие матчи, найденные сканером. Каждая лига выделена своим фирменным цветом.")
    
    if st.button("🔎 Запустить сканирование матчей", type="primary"):
        if not odds_api_key:
            st.warning("⚠️ Введите API ключ для The Odds API в боковой панели!")
        else:
            with st.spinner("Сканирование лиг и расчет пуассоновских моделей..."):
                checked, found, logs = scan_new_forecasts(odds_api_key)
                st.success(f"Проверено матчей: {checked}. Найдено выгодных прогнозов: {found}.")
                with st.expander("🔍 Логи сканирования"):
                    for l in logs:
                        st.write(l)

    st.markdown("### 📋 Свежие прогнозы:", unsafe_allow_html=True)
    forecasts = st.session_state.app_data.get("scanned_forecasts", [])
    
    if not forecasts:
        st.info("Нет активных прогнозов. Запустите сканирование выше.")
    else:
        for idx, f in enumerate(forecasts):
            l_name = f.get("league_name", "Лига")
            l_color = f.get("league_color", "#38bdf8")
            match_str = f.get("match", "Матч")
            pick = f.get("pick", "-")
            odd = f.get("odd", 1.9)
            reason = f.get("reason", "")
            
            st.markdown(f"""
                <div class="forecast-card">
                    <span class="league-badge" style="background-color: {l_color};">{l_name}</span>
                    <div style="font-size: 1.15rem; font-weight: 700; color: #f8fafc; margin-bottom: 4px;">⚽ {match_str}</div>
                    <div style="font-size: 0.85rem; color: #38bdf8; margin-bottom: 8px; font-weight: 600;">{reason}</div>
                    <div style="font-size: 0.95rem; color: #cbd5e1;">Рекомендация: <b style="color: #facc15;">{pick}</b> | Кф: <b style="color: #facc15;">{odd:.2f}</b></div>
                </div>
            """, unsafe_allow_html=True)
            
            if st.button("➕ Сделать ставку (взять в работу)", key=f"take_fc_{idx}"):
                existing_matches = [b["match"] for b in st.session_state.app_data["bets"]]
                if match_str in existing_matches:
                    st.warning("Этот матч уже есть в ваших ставках!")
                elif st.session_state.app_data["bank"] < STAKE_SIZE:
                    st.error("Недостаточно средств на балансе банкролла!")
                else:
                    st.session_state.app_data["bank"] -= STAKE_SIZE
                    new_bet = {
                        "id": len(st.session_state.app_data["bets"]) + 1,
                        "match": match_str,
                        "league_name": l_name,
                        "league_color": l_color,
                        "pick": pick,
                        "odd": odd,
                        "stake": STAKE_SIZE,
                        "status": "pending",
                        "reason": reason
                    }
                    st.session_state.app_data["bets"].append(new_bet)
                    save_history(st.session_state.app_data)
                    st.success(f"Ставка на {match_str} добавлена!")
                    st.rerun()
            st.markdown("---")

with tab2:
    st.markdown("### 📜 История ставок и Активные матчи")
    st.write("Здесь собраны все ваши ставки (и те, что еще ждут матча, и те, которые уже завершились). Также здесь доступна статистика.")
    
    # Кнопка обновления результатов
    if st.button("🔄 Обновить результаты и статистику"):
        st.success("Данные актуализированы!")
        st.rerun()

    bets = st.session_state.app_data.get("bets", [])
    
    # Блок статистики
    real_bets = [b for b in bets if b["status"] in ["won", "lost", "pending"]]
    total_bets = len(real_bets)
    won_bets = len([b for b in real_bets if b["status"] == "won"])
    lost_bets = len([b for b in real_bets if b["status"] == "lost"])
    pending_count = len([b for b in real_bets if b["status"] == "pending"])
    settled = won_bets + lost_bets
    win_rate = (won_bets / settled * 100) if settled > 0 else 0.0

    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.markdown(f'<div class="metric-card"><h4>В ожидании</h4><h2>{pending_count}</h2></div>', unsafe_allow_html=True)
    sc2.markdown(f'<div class="metric-card"><h4>Побед / Поражений</h4><h2>{won_bets} / {lost_bets}</h2></div>', unsafe_allow_html=True)
    sc3.markdown(f'<div class="metric-card"><h4>Win Rate</h4><h2 style="color: #4ade80;">{win_rate:.1f}%</h2></div>', unsafe_allow_html=True)
    sc4.markdown(f'<div class="metric-card"><h4>Всего ставок</h4><h2>{total_bets}</h2></div>', unsafe_allow_html=True)
    
    st.markdown("---")

    if not bets:
        st.info("История пуста. Перейдите во вкладку 'Новые прогнозы' и добавьте матчи в работу.")
    else:
        for idx, b in enumerate(bets):
            match_name = b.get("match", "Матч")
            l_name = b.get("league_name", "Футбол")
            l_color = b.get("league_color", "#38bdf8")
            reason = b.get("reason", "")
            pick = b.get("pick", "-")
            odd = b.get("odd", 1.9)
            stake = b.get("stake", STAKE_SIZE)
            status = b["status"]
            
            card_cls = "bet-card-pending"
            if status == "won":
                card_cls = "bet-card-won"
            elif status == "lost":
                card_cls = "bet-card-lost"
                
            status_label = "⏳ В ожидании" if status == "pending" else ("🎉 Выиграна" if status == "won" else "😢 Проиграна")
            
            st.markdown(f"""
                <div class="{card_cls}">
                    <span class="league-badge" style="background-color: {l_color};">{l_name}</span>
                    <div style="font-size: 1.15rem; font-weight: 700; color: #f8fafc; margin-bottom: 4px;">⚽ {match_name}</div>
                    <div style="font-size: 0.85rem; color: #38bdf8; margin-bottom: 8px; font-weight: 600;">{reason}</div>
                    <div style="display: flex; gap: 15px; font-size: 0.95rem; font-weight: 500; margin-bottom: 6px;">
                        <span style="color: #cbd5e1;">Выбор: <b style="color: #facc15;">{pick}</b></span>
                        <span style="color: #cbd5e1;">Кф: <b style="color: #facc15;">{odd:.2f}</b></span>
                        <span style="color: #cbd5e1;">Сумма: <b style="color: #4ade80;">{stake} у.е.</b></span>
                    </div>
                    <div style="font-size: 0.9rem; font-weight: 700; color: {'#f59e0b' if status=='pending' else ('#10b981' if status=='won' else '#ef4444')};">Статус: {status_label}</div>
                </div>
            """, unsafe_allow_html=True)
            
            cols = st.columns(2)
            with cols[0]:
                if status == "pending":
                    if st.button("✅ Зашло", key=f"win_{idx}"):
                        b["status"] = "won"
                        st.session_state.app_data["bank"] += stake * odd
                        save_history(st.session_state.app_data)
                        st.rerun()
                    if st.button("❌ Мимо", key=f"loss_{idx}"):
                        b["status"] = "lost"
                        save_history(st.session_state.app_data)
                        st.rerun()
                else:
                    if st.button("↩️ Вернуть в ожидание", key=f"res_{idx}"):
                        if status == "won":
                            st.session_state.app_data["bank"] -= (stake * odd - stake)
                        else:
                            st.session_state.app_data["bank"] += stake
                        b["status"] = "pending"
                        save_history(st.session_state.app_data)
                        st.rerun()
            st.markdown("---")

with tab3:
    st.markdown("### 🧠 Интеллектуальное дообучение ИИ")
    st.write("Система адаптируется на основе ваших реальных результатов. Нажмите кнопку ниже, чтобы ИИ подстроил веса под текущую проходимость.")
    
    if st.button("⚡ Запустить дообучение ИИ"):
        msg = fine_tune_ai()
        if "✅" in msg:
            st.success(msg)
        else:
            st.warning(msg)
            
    st.markdown("---")
    st.markdown("#### Отдельное управление весами:")
    if st.button("🔄 Сбросить только веса ИИ к стандарту"):
        st.session_state.app_data["weights"] = {"xg_w": 1.0, "odds_limit": 2.5}
        save_history(st.session_state.app_data)
        st.success("Веса сброшены к базовым значениям!")
        st.rerun()

    st.markdown("Текущие параметры весов:")
    st.json(st.session_state.app_data["weights"])

with tab4:
    st.markdown("### ℹ️ О системе и лигах")
    st.write("Рабочая лошадка для анализа матчей по распределению Пуассона. Поддерживает все топ-лигии и кубки Европы, РПЛ, MLS, Турцию, Голландию, Португалию и еврокубки с цветовой маркировкой.")
