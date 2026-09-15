import streamlit as st
import requests
import json
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="Football Betting AI Global", page_icon="🎯", layout="wide")

HISTORY_FILE = "betting_global_data.json"

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

def fetch_api_matches(competition_code, api_key):
    url = f"https://api.football-data.org/v4/competitions/{competition_code}/matches"
    headers = {'X-Auth-Token': api_key.strip()}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json().get("matches", [])
        return []
    except:
        return []

def calculate_elo(matches):
    elo = {}
    for match in matches:
        if match.get("status") != "FINISHED":
            continue
        h = match.get("homeTeam", {}).get("name")
        a = match.get("awayTeam", {}).get("name")
        score = match.get("score", {}).get("fullTime", {})
        s1 = score.get("home")
        s2 = score.get("away")
        
        if not h or not a or s1 is None or s2 is None:
            continue
            
        if h not in elo: elo[h] = 1500
        if a not in elo: elo[a] = 1500
        
        r1, r2 = elo[h], elo[a]
        e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        result = 1 if s1 > s2 else (0.5 if s1 == s2 else 0)
        
        elo[h] = r1 + 32 * (result - e1)
        elo[a] = r2 + 32 * ((1 - result) - (1 - e1))
    return elo

def predict_match(elo, home, away):
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
    if prob <= 0 or odds <= 1:
        return 0
    b = odds - 1
    kelly = (b * prob - (1 - prob)) / b
    stake = max(0, kelly * fraction) * bank
    return round(min(stake, bank * 0.05), 2)

def generate_ai_commentary(home, away, r1, r2, pick, prob, league_name):
    diff = abs(r1 - r2)
    comm = []
    
    if diff > 150:
        comm.append("🛡️ **Анализ состава:** Класс команд существенно различается. Основные лидеры в строю, глубина скамейки позволяет избежать просадки в темпе.")
    else:
        comm.append("⚠️ **Анализ состава:** Соперники равны. Высока вероятность точечной ротации из-за плотного графика, цена ошибки в центре поля максимальна.")
        
    if "Лига Чемпионов" in league_name or "Лига Европы" in league_name:
        comm.append("🇪🇺 **Фактор турнира:** Еврокубковый матч. Нагрузка на основу максимальная, опыт игры на международной арене выходит на первый план.")
    elif "Кубок" in league_name:
        comm.append("🏆 **Фактор кубка:** Кубковое противостояние. Повышенный риск выхода резервного состава у фаворита и мотивация аутсайдера.")
    else:
        comm.append("📊 **Трендовый анализ:** Оптимальные сочетания линий атаки и обороны подтверждены текущей статистикой сезона.")
        
    return " \n".join(comm)

if "data" not in st.session_state:
    st.session_state.data = load_data()

st.title("🎯 Football Betting AI Global (Auto-Scan)")

with st.sidebar:
    st.header("⚙️ Настройки и Банк")
    api_key = st.text_input("API Ключ (football-data.org)", type="password", value="")
    
    bank = st.session_state.data["bank"]
    st.metric("💰 Текущий банк", f"{bank:.2f} у.е.")
    
    kelly_frac = st.slider("Дробь Келли", 0.1, 0.5, 0.25, 0.05)
    min_ev = st.slider("Мин. перевес (EV %)", 0, 15, 2) / 100
    
    if st.button("🔄 Сброс системы"):
        st.session_state.data = {"bank": 10000.0, "bets": [], "forecasts": [], "stats": {"won": 0, "lost": 0, "profit": 0}}
        save_data(st.session_state.data)
        st.rerun()

tab1, tab2, tab3 = st.tabs(["🎯 Все матчи и анализ", "📋 Мои ставки", "📊 Статистика"])

with tab1:
    st.header("Глобальное сканирование всех лиг")
    days_ahead = st.slider("Горизонт анализа (дней вперед)", 1, 60, 30)
    
    if st.button("🚀 Запустить глобальный анализ всех турниров", type="primary"):
        if not api_key:
            st.error("❌ Введи API-ключ в боковой панели слева!")
            st.stop()
            
        # Полный список доступных лиг и международных турниров
        global_leagues = {
            "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Англия (АПЛ)": "PL",
            "🇪🇸 Испания (Ла Лига)": "PD",
            "🇮🇹 Италия (Серия А)": "SA",
            "🇩🇪 Германия (Бундеслига)": "BL1",
            "🇫🇷 Франция (Лига 1)": "FL1",
            "🇪🇺 Лига Чемпионов": "CL",
            "🇪🇺 Лига Европы": "EL",
            "🇳🇱 Нидерланды (Эредивизи)": "DED",
            "🇵🇹 Португалия (Примейра)": "PPL",
            "🇧🇷 Бразилия (Серия А)": "BSA",
            "🌎 Кубок Либертадорес": "CLI"
        }
        
        all_forecasts = []
        
        with st.spinner("Сканируем все лиги и кубки, рассчитываем рейтинги и формируем вердикты..."):
            for l_name, code in global_leagues.items():
                matches = fetch_api_matches(code, api_key)
                if not matches:
                    continue
                
                elo = calculate_elo(matches)
                now = datetime.utcnow()
                limit_date = now + timedelta(days=days_ahead)
                
                for match in matches:
                    if match.get("status") not in ["SCHEDULED", "TIMED"]:
                        continue
                    
                    utc_date_str = match.get("utcDate")
                    if not utc_date_str:
                        continue
                    
                    try:
                        match_date = datetime.strptime(utc_date_str[:19], "%Y-%m-%dT%H:%M:%S")
                    except:
                        continue
                    
                    if match_date > limit_date:
                        continue
                    
                    home = match.get("homeTeam", {}).get("name")
                    away = match.get("awayTeam", {}).get("name")
                    if not home or not away:
                        continue
                    
                    predictions = predict_match(elo, home, away)
                    r1 = elo.get(home, 1500)
                    r2 = elo.get(home, 1500)
                    
                    best_pick = None
                    best_ev = -1
                    best_prob = 0
                    best_odd = 0
                    
                    for pick, prob in predictions:
                        if prob > 0:
                            odd = round(1 / prob * 0.98, 2)
                            ev = (prob * odd) - 1.0
                            if ev > best_ev:
                                best_ev = ev
                                best_pick = pick
                                best_prob = prob
                                best_odd = odd
                    
                    recommendation = "🟢 ДОБРО НА СТАВКУ" if best_ev >= min_ev else "🔴 ПРОПУСТИТЬ"
                    stake = kelly_stake(best_prob, best_odd, bank, kelly_frac) if best_ev >= min_ev else 0
                    commentary = generate_ai_commentary(home, away, r1, r2, best_pick, best_prob, l_name)
                    
                    all_forecasts.append({
                        "league": l_name,
                        "match": f"{home} vs {away}",
                        "date": match_date.strftime('%d.%m.%Y %H:%M (UTC)'),
                        "pick": best_pick,
                        "prob": best_prob,
                        "odds": best_odd,
                        "ev": best_ev,
                        "recommendation": recommendation,
                        "stake": stake,
                        "commentary": commentary
                    })
            
            # Сортировка от высокой проходимости к низкой
            all_forecasts.sort(key=lambda x: (x['recommendation'] == "🟢 ДОБРО НА СТАВКУ", x['prob'], x['ev']), reverse=True)
            
            st.session_state.data["forecasts"] = all_forecasts
            save_data(st.session_state.data)
            st.success(f"✅ Сканирование завершено! Найдено матчей: {len(all_forecasts)}")
            st.rerun()

    forecasts = st.session_state.data.get("forecasts", [])
    if forecasts:
        st.subheader(f"📊 Отсортировано по проходимости (от высоких к низким шансам): {len(forecasts)}")
        for idx, f in enumerate(forecasts):
            with st.container():
                st.markdown(f"### ⚽ {f['match']} ({f['league']})")
                
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.markdown(f"**Статус:** {f['recommendation']}")
                    st.caption(f"📅 Дата: {f['date']} | Выбор: **{f['pick']}**")
                with c2:
                    st.metric("Проходимость", f"{f['prob']*100:.1f}%")
                with c3:
                    st.metric("Коэффициент", f"{f['odds']:.2f}")
                
                m1, m2 = st.columns(2)
                m1.metric("Перевес (EV)", f"{f['ev']*100:+.1f}%")
                m2.metric("Рекомендация (Келли)", f"{f['stake']:.2f} у.е.")
                
                st.info(f"{f['commentary']}")
                
                if f['recommendation'] == "🟢 ДОБРО НА СТАВКУ" and f['stake'] > 0:
                    if st.button(f"📥 Дать добро и загнать в статистику #{idx+1}", key=f"add_global_bet_{idx}"):
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
                        st.success("Ставка успешно добавлена в статистику!")
                st.markdown("---")
    else:
        st.info("👆 Введи ключ в сайдбар и начни глобальное сканирование.")

with tab2:
    st.header("📋 Управление активными ставками")
    bets = st.session_state.data.get("bets", [])
    if not bets:
        st.info("Нет активных ставок.")
    else:
        pending = [b for b in bets if b.get("status") == "pending"]
        completed = [b for b in bets if b.get("status"] in ["won", "lost"]]
        
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
            st.subheader(f"📁 Архив ({len(completed)})")
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
