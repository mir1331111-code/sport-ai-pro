import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import json
import os

st.set_page_config(page_title="AI Sport Bot Pro", page_icon="⚽", layout="wide")

# Дизайн и стили
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(10, 15, 25, 0.90), rgba(10, 15, 25, 0.98)), 
                    url('https://images.unsplash.com/photo-1518091043644-c1d4457512c6?q=80&w=1920&auto=format&fit=crop');
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
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

def reset_full_system():
    clean_data = {
        "bank": 10000.0, 
        "weights": {"xg_w": 1.0},
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
                    data["weights"] = {"xg_w": 1.0}
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

st.title("⚽ AI Sport Bot Pro (Универсальный анализ)")

st.sidebar.header("⚙️ Настройки и Банк")
current_weights = st.session_state.app_data.get("weights", {"xg_w": 1.0})
st.sidebar.write(f"Вес модели xG: `{current_weights.get('xg_w', 1.0):.3f}`")
current_bank = st.session_state.app_data["bank"]
st.sidebar.metric(label="Баланс банкролла", value=f"{current_bank:.2f} у.е.")

if st.sidebar.button("🔄 Полный сброс системы"):
    st.session_state.app_data = reset_full_system()
    st.sidebar.success("Система сброшена!")
    st.rerun()

tab1, tab2, tab3 = st.tabs([
    "🎯 Добавить матч / Турнир", 
    "📜 История и Активные ставки", 
    "⚙️ О системе"
])

with tab1:
    st.markdown("### ✍️ Ручной ввод матча из любого турнира (ЛЧ, РПЛ, Турция, МЛС и др.)")
    st.write("Введите название команд, выберите турнир и укажите коэффициенты букмекера. ИИ мгновенно произведет расчет.")
    
    with st.form("match_input_form"):
        col1, col2 = st.columns(2)
        with col1:
            tournament = st.selectbox("Турнир / Лига", [
                "⭐ Лига Чемпионов УЕФА", 
                "🇪🇺 Лига Европы УЕФА", 
                "🇪🇺 Лига Конференций", 
                "🇷🇺 Россия (РПЛ)", 
                "🇹🇷 Турция (Суперлига)", 
                "🇺🇸 США (MLS)", 
                "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Англия (АПЛ)", 
                "🇪🇸 Испания (Ла Лига)", 
                "🇮🇹 Италия (Серия А)", 
                "🇩🇪 Германия (Бундеслига)",
                "🌐 Другой турнир"
            ])
            home_team = st.text_input("Хозяева", placeholder="например, Зенит / Реал")
        with col2:
            custom_tourn = st.text_input("Уточнение (если Другой турнир)", placeholder="например, Кубок России")
            away_team = st.text_input("Гости", placeholder="например, Спартак / Манчестер")
            
        st.markdown("---")
        st.write("📈 **Коэффициенты букмекера:**")
        col3, col4, col5 = st.columns(3)
        with col3:
            odd_home = st.number_input("Кф на П1", min_value=1.01, max_value=20.0, value=2.10, step=0.01)
        with col4:
            odd_draw = st.number_input("Кф на Ничья (X)", min_value=0.0, max_value=20.0, value=3.40, step=0.01)
        with col5:
            odd_away = st.number_input("Кф на П2", min_value=1.01, max_value=20.0, value=3.20, step=0.01)
            
        submitted = st.form_submit_button("🚀 Рассчитать и добавить в ставки", type="primary")
        
        if submitted:
            if not home_team or not away_team:
                st.error("Пожалуйста, укажите названия команд!")
            else:
                xg_w = current_weights.get("xg_w", 1.0)
                
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
                    ("П1", p_home, odd_home),
                    ("Ничья (X)", p_draw, odd_draw if odd_draw > 0 else 0.01),
                    ("П2", p_away, odd_away)
                ]
                
                best_pick = max(options, key=lambda x: x[1] * x[2] if x[2] > 0 else -1)
                pick_name, prob, odd = best_pick
                
                edge = (prob * odd) - 1.0
                decision = "🟢 СТАВИМ" if edge > -0.08 and odd < 3.2 else "🔴 НЕ СТАВИМ"
                reason = f"Анализ матча. Шанс модели: {prob*100:.1f}%."
                
                tourn_label = tournament if "Другой" not in tournament else (custom_tourn or "Матч")
                
                new_forecast = {
                    "league_name": tourn_label,
                    "league_color": "#38bdf8",
                    "match": f"{home_team} vs {away_team}",
                    "pick": pick_name,
                    "odd": odd,
                    "prob": prob,
                    "reason": reason,
                    "decision": decision
                }
                
                app_data = st.session_state.app_data
                app_data["scanned_forecasts"].insert(0, new_forecast)
                
                if "СТАВИМ" in decision:
                    bank = app_data["bank"]
                    if bank >= STAKE_SIZE:
                        bank -= STAKE_SIZE
                        app_data["bank"] = bank
                        new_bet = {
                            "id": len(app_data["bets"]) + 1,
                            "match": new_forecast["match"],
                            "league_name": new_forecast["league_name"],
                            "league_color": new_forecast["league_color"],
                            "pick": pick_name,
                            "odd": odd,
                            "stake": STAKE_SIZE,
                            "status": "pending",
                            "reason": f"{reason} | Рекомендация: {pick_name}",
                            "prob": prob
                        }
                        app_data["bets"].append(new_bet)
                        st.success(f"Матч успешно проанализирован! Авто-ставка {STAKE_SIZE} у.е. добавлена в историю.")
                    else:
                        st.warning("Прогноз создан, но недостаточно средств в банкролле.")
                else:
                    st.info("Матч проанализирован. Вердикт: Не ставить.")
                
                save_history(app_data)
                st.rerun()

    st.markdown("### 📋 Проанализированные матчи:", unsafe_allow_html=True)
    forecasts = st.session_state.app_data.get("scanned_forecasts", [])
    
    if not forecasts:
        st.info("Список пуст. Добавьте матч через форму выше.")
    else:
        for idx, f in enumerate(forecasts):
            l_name = f.get("league_name", "Спорт")
            l_color = f.get("league_color", "#38bdf8")
            match_str = f.get("match", "Матч")
            pick = f.get("pick", "-")
            odd = f.get("odd", 1.95)
            prob = f.get("prob", 0.5)
            reason = f.get("reason", "")
            decision = f.get("decision", "🔴 НЕ СТАВИМ")
            
            decision_color = "#10b981" if "СТАВИМ" in decision and "НЕ" not in decision else "#ef4444"
            
            st.markdown(f"""
                <div class="forecast-card">
                    <span style="background-color: {l_color}; padding: 3px 8px; border-radius: 6px; font-size: 0.75rem; color: #fff; font-weight: 700;">{l_name}</span>
                    <div style="font-size: 1.1rem; font-weight: 700; color: #f8fafc; margin-top: 6px;">⚽ {match_str}</div>
                    <div style="font-size: 0.85rem; color: #cbd5e1; margin: 4px 0;"><b>Анализ:</b> {reason}</div>
                    <div style="font-size: 0.9rem; color: #38bdf8;">Выбор ИИ: <b style="color: #facc15;">{pick}</b> | Вероятность: <b style="color: #4ade80;">{prob*100:.1f}%</b> | Кф: <b style="color: #facc15;">{odd:.2f}</b></div>
                    <div style="font-size: 1rem; font-weight: 700; color: {decision_color}; margin-top: 4px;">Вердикт: {decision}</div>
                </div>
            """, unsafe_allow_html=True)

with tab2:
    st.markdown("### 📜 История и Активные ставки")
    bets = st.session_state.app_data.get("bets", [])
    if not bets:
        st.info("История ставок пуста.")
    else:
        for idx, b in enumerate(bets):
            match_name = b.get("match", "Матч")
            l_name = b.get("league_name", "Спорт")
            l_color = b.get("league_color", "#38bdf8")
            reason = b.get("reason", "")
            pick = b.get("pick", "-")
            odd = b.get("odd", 1.95)
            stake = b.get("stake", STAKE_SIZE)
            status = b["status"]
            
            card_cls = "bet-card-pending" if status == "pending" else ("bet-card-won" if status == "won" else "bet-card-lost")
            status_label = "⏳ В ожидании" if status == "pending" else ("🎉 Выиграна" if status == "won" else "😢 Проиграна")
            
            st.markdown(f"""
                <div class="{card_cls}">
                    <span style="background-color: {l_color}; padding: 3px 8px; border-radius: 6px; font-size: 0.75rem; color: #fff; font-weight: 700;">{l_name}</span>
                    <div style="font-size: 1.1rem; font-weight: 700; color: #f8fafc; margin-top: 6px;">⚽ {match_name}</div>
                    <div style="font-size: 0.8rem; color: #cbd5e1; margin: 4px 0;">{reason}</div>
                    <div style="font-size: 0.9rem; color: #cbd5e1;">Выбор: <b style="color: #facc15;">{pick}</b> | Кф: <b style="color: #facc15;">{odd:.2f}</b> | Сумма: <b style="color: #4ade80;">{stake} у.е.</b></div>
                    <div style="font-size: 0.85rem; font-weight: 700; margin-top: 4px;">Статус: {status_label}</div>
                </div>
            """, unsafe_allow_html=True)
            
            if status == "pending":
                cols = st.columns(2)
                with cols[0]:
                    if st.button("✅ Зашло", key=f"win_{idx}"):
                        b["status"] = "won"
                        st.session_state.app_data["bank"] += stake * odd
                        save_history(st.session_state.app_data)
                        st.rerun()
                with cols[1]:
                    if st.button("❌ Мимо", key=f"loss_{idx}"):
                        b["status"] = "lost"
                        save_history(st.session_state.app_data)
                        st.rerun()
            st.markdown("---")

with tab3:
    st.markdown("### ℹ️ О системе")
    st.write("Приложение готово к работе с любыми матчами мира.")
