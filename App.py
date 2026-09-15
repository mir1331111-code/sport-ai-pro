import streamlit as st
import json
import os
from datetime import datetime, timedelta
import numpy as np

st.set_page_config(page_title="Football Betting AI", page_icon="🎯", layout="wide")

HISTORY_FILE = "betting_ai_data.json"

def load_data():
    if os.path.exists(HISTORY_FILE):
        try:
            return json.load(open(HISTORY_FILE, "r", encoding="utf-8"))
        except:
            pass
    return {"bank": 10000.0, "bets": [], "forecasts": [], "stats": {"won": 0, "lost": 0, "profit": 0}}

def save_data(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# Встроенная база данных актуальных матчей и коэффициентов сезона 2026/2027
def get_mock_database():
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Англия (АПЛ)": [
            {"home": "Arsenal", "away": "Manchester United", "date": today + timedelta(days=1), "h_odds": 1.75, "d_odds": 3.80, "a_odds": 4.50, "h_elo_past": [1, 1, 3], "a_elo_past": [1, 0, 1]},
            {"home": "Manchester City", "away": "Liverpool", "date": today + timedelta(days=1), "h_odds": 2.05, "d_odds": 3.60, "a_odds": 3.40, "h_elo_past": [3, 3, 1], "a_elo_past": [3, 1, 3]},
            {"home": "Chelsea", "away": "Tottenham", "date": today + timedelta(days=2), "h_odds": 2.20, "d_odds": 3.40, "a_odds": 3.20, "h_elo_past": [1, 3, 0], "a_elo_past": [3, 1, 1]},
            {"home": "Newcastle", "away": "Aston Villa", "date": today + timedelta(days=3), "h_odds": 1.90, "d_odds": 3.50, "a_odds": 3.90, "h_elo_past": [3, 1, 3], "a_elo_past": [1, 1, 0]},
        ],
        "🇪🇸 Испания (Ла Лига)": [
            {"home": "Real Madrid", "away": "Barcelona", "date": today + timedelta(days=1), "h_odds": 2.10, "d_odds": 3.50, "a_odds": 3.30, "h_elo_past": [3, 3, 3], "a_elo_past": [3, 3, 1]},
            {"home": "Atletico Madrid", "away": "Villarreal", "date": today + timedelta(days=2), "h_odds": 1.80, "d_odds": 3.60, "a_odds": 4.40, "h_elo_past": [3, 1, 3], "a_elo_past": [1, 0, 3]},
            {"home": "Real Sociedad", "away": "Sevilla", "date": today + timedelta(days=3), "h_odds": 1.95, "d_odds": 3.30, "a_odds": 4.10, "h_elo_past": [1, 1, 3], "a_elo_past": [0, 1, 1]},
        ],
        "🇮🇹 Италия (Серия А)": [
            {"home": "Inter", "away": "Juventus", "date": today + timedelta(days=1), "h_odds": 1.95, "d_odds": 3.40, "a_odds": 4.00, "h_elo_past": [3, 3, 1], "a_elo_past": [3, 1, 3]},
            {"home": "AC Milan", "away": "Napoli", "date": today + timedelta(days=2), "h_odds": 2.25, "d_odds": 3.30, "a_odds": 3.20, "h_elo_past": [1, 3, 3], "a_elo_past": [3, 3, 0]},
        ],
        "🇩🇪 Германия (Бундеслига)": [
            {"home": "Bayern Munich", "away": "Borussia Dortmund", "date": today + timedelta(days=1), "h_odds": 1.55, "d_odds": 4.50, "a_odds": 5.20, "h_elo_past": [3, 3, 3], "a_elo_past": [3, 1, 3]},
            {"home": "RB Leipzig", "away": "Bayer Leverkusen", "date": today + timedelta(days=2), "h_odds": 2.40, "d_odds": 3.50, "a_odds": 2.80, "h_elo_past": [1, 3, 1], "a_elo_past": [3, 3, 1]},
        ]
    }

def calculate_dynamic_elo(league_data):
    elo = {}
    for match in league_data:
        h, a = match["home"], match["away"]
        if h not in elo: elo[h] = 1500
        if a not in elo: elo[a] = 1500
        
        # Симуляция изменения рейтинга по прошлым матчам
        for res in match["h_elo_past"]:
            r1, r2 = elo[h], elo[a]
            e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
            elo[h] = r1 + 16 * (res/3 - e1)
    return elo

def predict_match(elo, home, away):
    r1 = elo.get(home, 1500)
    r2 = elo.get(away, 1500)
    
    p_home = 1 / (1 + 10 ** ((r2 - r1) / 400))
    p_away = 1 / (1 + 10 ** ((r1 - r2) / 400))
    p_draw = 0.26 * (1 - abs(p_home - p_away)) # Статистическая поправка на ничью
    
    total = p_home + p_draw + p_away
    return [
        ("П1", p_home/total),
        ("X", p_draw/total),
        ("П2", p_away/total)
    ]

def kelly_stake(prob, odds, bank, fraction=0.25):
    if prob <= 0 or odds <= 1:
        return 0
    b = odds - 1
    kelly = (b * prob - (1 - prob)) / b
    stake = max(0, kelly * fraction) * bank
    return round(min(stake, bank * 0.05), 2)

if "data" not in st.session_state:
    st.session_state.data = load_data()

st.title("🎯 Football Betting AI Assistant")

with st.sidebar:
    st.header("⚙️ Управление банком")
    bank = st.session_state.data["bank"]
    st.metric("💰 Текущий банк", f"{bank:.2f} у.е.")
    
    kelly_frac = st.slider("Дробь Келли", 0.1, 0.5, 0.25, 0.05)
    min_ev = st.slider("Мин. перевес (EV %)", 0, 15, 3) / 100
    
    if st.button("🔄 Сброс системы"):
        st.session_state.data = {"bank": 10000.0, "bets": [], "forecasts": [], "stats": {"won": 0, "lost": 0, "profit": 0}}
        save_data(st.session_state.data)
        st.rerun()

tab1, tab2, tab3 = st.tabs(["🎯 Прогнозы и вердикт ИИ", "📋 Мои ставки", "📊 Статистика"])

with tab1:
    st.header("Анализ предстоящих матчей")
    
    db = get_mock_database()
    selected_league = st.selectbox("Выберите лигу", list(db.keys()))
    
    if st.button("🚀 Запустить анализ матчей", type="primary"):
        matches = db[selected_league]
        elo = calculate_dynamic_elo(matches)
        
        forecasts = []
        for match in matches:
            home = match["home"]
            away = match["away"]
            
            predictions = predict_match(elo, home, away)
            odds_map = {"П1": match["h_odds"], "X": match["d_odds"], "П2": match["a_odds"]}
            
            best_pick = None
            best_ev = -1
            best_prob = 0
            best_odd = 0
            
            for pick, prob in predictions:
                odd = odds_map[pick]
                ev = (prob * odd) - 1.0
                if ev > best_ev:
                    best_ev = ev
                    best_pick = pick
                    best_prob = prob
                    best_odd = odd
            
            # Вердикт ИИ: стоит ставить или пропустить
            recommendation = "🟢 СТОИТ СТАВИТЬ" if best_ev >= min_ev else "🔴 ПРОПУСТИТЬ"
            stake = kelly_stake(best_prob, best_odd, bank, kelly_frac) if best_ev >= min_ev else 0
            
            forecasts.append({
                "league": selected_league,
                "match": f"{home} vs {away}",
                "date": match["date"].strftime('%d.%m.%Y %H:%M'),
                "pick": best_pick,
                "prob": best_prob,
                "odds": best_odd,
                "ev": best_ev,
                "recommendation": recommendation,
                "stake": stake
            })
        
        st.session_state.data["forecasts"] = forecasts
        save_data(st.session_state.data)
        st.success(f"✅ Анализ завершен! Обработано матчей: {len(forecasts)}")
        st.rerun()

    forecasts = st.session_state.data.get("forecasts", [])
    if forecasts:
        st.subheader("📊 Результаты прогнозирования")
        for idx, f in enumerate(forecasts):
            with st.container():
                st.markdown(f"### ⚽ {f['match']} ({f['date']})")
                
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.markdown(f"**Вердикт ИИ:** {f['recommendation']}")
                    st.caption(f"Лига: {f['league']} | Выбор модели: **{f['pick']}**")
                with c2:
                    st.metric("Вероятность", f"{f['prob']*100:.1f}%")
                with c3:
                    st.metric("Коэффициент", f"{f['odds']:.2f}")
                
                m1, m2 = st.columns(2)
                m1.metric("Перевес (EV)", f"{f['ev']*100:+.1f}%")
                m2.metric("Рекомендация Келли", f"{f['stake']:.2f} у.е.")
                
                if f['recommendation'] == "🟢 СТОИТ СТАВИТЬ" and f['stake'] > 0:
                    if st.button(f"📥 Добавить в мои ставки #{idx+1}", key=f"add_rec_{idx}"):
                        new_bet = {
                            "match": f['match'],
                            "league": f['league'],
                            "pick": f['pick'],
                            "odds": f['odds'],
                            "stake": f['stake'],
                            "status": "pending"
                        }
                        st.session_state.data["bets"].append(new_bet)
                        save_data(st.session_state.data)
                        st.success("Ставка успешно добавлена!")
                st.markdown("---")
    else:
        st.info("👆 Нажмите кнопку «Запустить анализ матчей», чтобы увидеть прогнозы и вердикты модели.")

with tab2:
    st.header("📋 Управление активными ставками")
    bets = st.session_state.data.get("bets", [])
    if not bets:
        st.info("Нет активных ставок. Добавьте их из вкладки прогнозов.")
    else:
        pending = [b for b in bets if b.get("status") == "pending"]
        completed = [b for b in bets if b.get("status") in ["won", "lost"]]
        
        if pending:
            st.subheader(f"⏳ Ожидающие расчета ({len(pending)})")
            for i, bet in enumerate(pending):
                with st.container():
                    st.markdown(f"**{bet.get('league')}** | `{bet.get('match')}`")
                    st.write(f"Выбор: **{bet.get('pick')}** | Кэф: **{bet.get('odds'):.2f}** | Сумма: **{bet.get('stake'):.2f} у.е.**")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Выиграла", key=f"win_{i}"):
                            bet["status"] = "won"
                            profit = bet.get("stake", 0) * (bet.get("odds", 0) - 1)
                            st.session_state.data["bank"] += profit
                            st.session_state.data["stats"]["won"] += 1
                            st.session_state.data["stats"]["profit"] += profit
                            save_data(st.session_state.data)
                            st.rerun()
                    with c2:
                        if st.button("❌ Проиграла", key=f"loss_{i}"):
                            bet["status"] = "lost"
                            loss = bet.get("stake", 0)
                            st.session_state.data["bank"] -= loss
                            st.session_state.data["stats"]["lost"] += 1
                            st.session_state.data["stats"]["profit"] -= loss
                            save_data(st.session_state.data)
                            st.rerun()
                    st.markdown("---")
        
        if completed:
            st.subheader(f"📁 Архив завершенных ставок ({len(completed)})")
            for bet in completed[-10:]:
                status_icon = "🟢" if bet.get("status") == "won" else "🔴"
                st.text(f"{status_icon} {bet.get('match')} | {bet.get('pick')} @ {bet.get('odds')} — Ставка: {bet.get('stake')} у.е.")

with tab3:
    st.header("📊 Статистика эффективности")
    stats = st.session_state.data.get("stats", {})
    bank = st.session_state.data["bank"]
    initial_bank = 10000.0
    
    won = stats.get("won", 0)
    lost = stats.get("lost", 0)
    profit = stats.get("profit", 0)
    total = won + lost
    
    win_rate = (won / total * 100) if total > 0 else 0
    roi = (profit / initial_bank * 100)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Текущий банк", f"{bank:.2f} у.е.", f"{bank - initial_bank:+.2f}")
    c2.metric("📊 Всего ставок", total)
    c3.metric("🎯 Win Rate", f"{win_rate:.1f}%")
    c4.metric("📈 Прибыль (ROI)", f"{roi:.2f}%")
