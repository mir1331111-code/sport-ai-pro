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
            return json.load(open(HISTORY_FILE, "r", encoding="utf-8"))
        except:
            pass
    return {"bank": 10000.0, "bets": [], "forecasts": [], "stats": {"won": 0, "lost": 0, "profit": 0}}

def save_data(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_csv(url):
    """Загрузка CSV без pandas"""
    try:
        r = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        return list(csv.DictReader(io.StringIO(r.text)))
    except Exception as e:
        return []

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

def predict_match(elo, home, away):
    """Предсказание вероятностей (футбол с учетом ничьей)"""
    r1 = elo.get(home, 1500)
    r2 = elo.get(away, 1500)
    
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

st.title("🎯 Football Betting AI")

# Боковая панель
with st.sidebar:
    st.header("⚙️ Настройки")
    bank = st.session_state.data["bank"]
    st.metric("💰 Банк", f"{bank:.2f} у.е.")
    
    kelly_frac = st.slider("Дробь Келли", 0.1, 0.5, 0.25, 0.05)
    min_ev = st.slider("Мин EV %", 0, 15, 3) / 100
    
    if st.button("🔄 Сброс системы"):
        st.session_state.data = {"bank": 10000.0, "bets": [], "forecasts": [], "stats": {"won": 0, "lost": 0, "profit": 0}}
        save_data(st.session_state.data)
        st.rerun()

# Вкладки
tab1, tab2, tab3 = st.tabs(["🎯 Прогнозы", "📋 Ставки", "📊 Статистика"])

with tab1:
    st.header("Анализ матчей (Football-Data)")
    
    leagues = {
        "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Англия (АПЛ)": "E0",
        "🇪🇸 Испания (Ла Лига)": "SP1",
        "🇮🇹 Италия (Серия А)": "I1",
        "🇩🇪 Германия (Бундеслига)": "D1",
        "🇫🇷 Франция (Лига 1)": "F1",
        "🇷🇺 Россия (РПЛ)": "R1",
        "🇹🇷 Турция (Суперлига)": "T1"
    }
    
    selected_league = st.selectbox("Лига/Турнир", list(leagues.keys()))
    days = st.slider("Период анализа (дней вперед)", 1, 30, 14)
    
    col1, col2 = st.columns(2)
    with col1:
        show_all = st.checkbox("Показать все матчи (включая сыгранные)", False)
    with col2:
        debug_mode = st.checkbox("Режим отладки", False)
    
    if st.button("🚀 Запустить анализ", type="primary"):
        league_code = leagues[selected_league]
        season = "2526" # Сезон 2025/2026
        url = f"https://www.football-data.co.uk/mmz4281/{season}/{league_code}.csv"
        
        if debug_mode:
            st.info(f"URL: {url}")
        
        with st.spinner("Загрузка данных с сервера..."):
            data = load_csv(url)
            
            if not data:
                st.error("❌ Не удалось загрузить данные. Проверьте подключение к интернету.")
                st.stop()
            
            st.success(f"✅ Загружено {len(data)} записей")
        
        with st.spinner("Обработка и анализ матчей..."):
            today = datetime.now()
            limit = today + timedelta(days=days)
            
            elo = calculate_elo(data)
            
            if debug_mode:
                st.write(f"Команд в базе Elo: {len(elo)}")
            
            forecasts = []
            
            for row in data:
                home = row.get('HomeTeam', '')
                away = row.get('AwayTeam', '')
                
                if not home or not away:
                    continue
                
                date_str = row.get('Date', '')
                match_date = parse_date(date_str) if date_str else None
                
                if not match_date and not show_all:
                    continue
                
                if match_date and not show_all:
                    if match_date < today.replace(hour=0, minute=0, second=0, microsecond=0) or match_date > limit:
                        continue
                
                score1 = row.get('FTHG', '')
                if score1 and score1.strip() != '' and not show_all:
                    continue
                
                try:
                    odds_h = float(row.get('B365H', row.get('PSH', 0)))
                    odds_x = float(row.get('B365D', row.get('PSD', 0)))
                    odds_a = float(row.get('B365A', row.get('PSA', 0)))
                    odds_dict = {"П1": odds_h, "X": odds_x, "П2": odds_a}
                    
                    if all(v <= 1 for v in odds_dict.values()):
                        continue
                except:
                    continue
                
                predictions = predict_match(elo, home, away)
                
                best_pick = None
                best_ev = -1
                best_prob = 0
                best_odd = 0
                
                for pick, prob in predictions:
                    odd = odds_dict.get(pick, 0)
                    if odd > 1:
                        ev = (prob * odd) - 1.0
                        if ev > best_ev:
                            best_ev = ev
                            best_pick = pick
                            best_prob = prob
                            best_odd = odd
                
                if best_ev >= min_ev:
                    stake = kelly_stake(best_prob, best_odd, bank, kelly_frac)
                    
                    if stake > 0:
                        forecasts.append({
                            "league": selected_league,
                            "match": f"{home} vs {away}",
                            "date": match_date.strftime('%d.%m.%Y') if match_date else "N/A",
                            "pick": best_pick,
                            "prob": best_prob,
                            "odds": best_odd,
                            "ev": best_ev,
                            "stake": stake
                        })
            
            st.session_state.data["forecasts"] = forecasts
            save_data(st.session_state.data)
            
            if forecasts:
                st.success(f"✅ Найдено {len(forecasts)} выгодных ставок!")
            else:
                st.warning("⚠️ Не найдено ставок с заданным EV. Попробуйте увеличить период анализа или снизить мин. EV в настройках.")
            
            st.rerun()

    # Отображение прогнозов через нативные компоненты Streamlit (без багов с сырым HTML)
    forecasts = st.session_state.data.get("forecasts", [])
    
    if forecasts:
        st.subheader(f"📊 Найдено выгодных ставок: {len(forecasts)}")
        
        for idx, f in enumerate(forecasts):
            with st.container():
                st.markdown(f"### ⚽ {f['match']}")
                col_l, col_d = st.columns([2, 1])
                with col_l:
                    st.caption(f"Лига: **{f['league']}** | Дата: 📅 {f['date']}")
                with col_d:
                    st.markdown(f"Прогноз: **{f['pick']}**")
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Вероятность", f"{f['prob']*100:.1f}%")
                m2.metric("Коэффициент", f"{f['odds']:.2f}")
                m3.metric("EV (Перевес)", f"{f['ev']*100:+.1f}%")
                m4.metric("Ставка (Келли)", f"{f['stake']:.2f} у.е.")
                
                if st.button(f"📥 Добавить в мои ставки #{idx+1}", key=f"add_forecast_{idx}"):
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
                    st.success("Ставка успешно добавлена во вкладку «Ставки»!")
                st.markdown("---")
    else:
        st.info("👆 Выберите лигу и нажмите кнопку «Запустить анализ»")

with tab2:
    st.header("📋 Управление активными ставками")
    
    bets = st.session_state.data.get("bets", [])
    
    if not bets:
        st.info("У вас нет добавленных ставок. Добавьте их из вкладки «Прогнозы».")
    else:
        pending = [b for b in bets if b.get("status") == "pending"]
        completed = [b for b in bets if b.get("status") in ["won", "lost"]]
        
        if pending:
            st.subheader(f"⏳ Активные ставки ({len(pending)})")
            for i, bet in enumerate(pending):
                with st.container():
                    st.markdown(f"**{bet.get('league')}** | `{bet.get('match')}`")
                    st.write(릎f"Выбор: **{bet.get('pick')}** | Кэф: **{bet.get('odds'):.2f}** | Сумма: **{bet.get('stake'):.2f} у.е.**")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Выиграла", key=f"win_{i}"):
                            bet["status"] = "won"
                            profit = bet.get("stake", 0) * (bet.get("odds", 0) - 1)
                            st.session_state.data["bank"] += profit
                            st.session_state.data["stats"]["won"] += 1
                            st.session_state.data["stats"]["profit"] += profit
                            save_data(st.session_state.data)
                            st.success(f"Засчитан выигрыш: +{profit:.2f} у.е.")
                            st.rerun()
                    with c2:
                        if st.button("❌ Проиграла", key=f"loss_{i}"):
                            bet["status"] = "lost"
                            loss = bet.get("stake", 0)
                            st.session_state.data["bank"] -= loss
                            st.session_state.data["stats"]["lost"] += 1
                            st.session_state.data["stats"]["profit"] -= loss
                            save_data(st.session_state.data)
                            st.error(f"Засчитан проигрыш: -{loss:.2f} у.е.")
                            st.rerun()
                    st.markdown("---")
        
        if completed:
            st.subheader(f"📁 Завершённые ставки ({len(completed)})")
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
    
    st.markdown("---")
    st.markdown("""
    ### ℹ️ Справка
    - **Elo + Probability Model**: Рассчитывает реальные шансы команд на основе истории матчей текущего сезона.
    - **Критерий Келли**: Автоматически рассчитывает безопасный размер ставки для защиты вашего банкролла.
    """)
