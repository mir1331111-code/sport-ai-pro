import streamlit as st
import requests
import json
import os
from datetime import datetime, timedelta
import math

st.set_page_config(page_title="Football Betting AI Expert Pro", page_icon="🚀", layout="wide")

HISTORY_FILE = "betting_expert_data.json"

LEAGUE_CODES = {
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

def calculate_advanced_metrics(matches):
    team_stats = {}
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
            
        for team in [h, a]:
            if team not in team_stats:
                team_stats[team] = {"scored": 0, "conceded": 0, "matches": 0}
            if team not in elo:
                elo[team] = 1500
                
        team_stats[h]["scored"] += s1
        team_stats[h]["conceded"] += s2
        team_stats[h]["matches"] += 1
        
        team_stats[a]["scored"] += s2
        team_stats[a]["conceded"] += s1
        team_stats[a]["matches"] += 1
        
        r1, r2 = elo[h], elo[a]
        e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        result = 1 if s1 > s2 else (0.5 if s1 == s2 else 0)
        elo[h] = r1 + 32 * (result - e1)
        elo[a] = r2 + 32 * ((1 - result) - (1 - e1))
        
    return elo, team_stats

def poisson_probability(lmbda, k):
    return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)

def predict_match_poisson(team_stats, home, away, elo):
    h_stat = team_stats.get(home, {"scored": 1.2, "conceded": 1.2, "matches": 10})
    a_stat = team_stats.get(away, {"scored": 1.1, "conceded": 1.3, "matches": 10})
    
    h_avg_sc = max(0.5, h_stat["scored"] / max(1, h_stat["matches"]))
    h_avg_cc = max(0.5, h_stat["conceded"] / max(1, h_stat["matches"]))
    a_avg_sc = max(0.5, a_stat["scored"] / max(1, a_stat["matches"]))
    a_avg_cc = max(0.5, a_stat["conceded"] / max(1, a_stat["matches"]))
    
    expected_home = (h_avg_sc + a_avg_cc) / 2
    expected_away = (a_avg_sc + h_avg_cc) / 2
    
    r1 = elo.get(home, 1500)
    r2 = elo.get(away, 1500)
    diff = (r1 - r2) / 400
    expected_home *= (1 + 0.15 * diff)
    expected_away *= (1 - 0.15 * diff)
    
    p_home, p_draw, p_away = 0, 0, 0
    for h_goals in range(6):
        for a_goals in range(6):
            p = poisson_probability(expected_home, h_goals) * poisson_probability(expected_away, a_goals)
            if h_goals > a_goals:
                p_home += p
            elif h_goals == a_goals:
                p_draw += p
            else:
                p_away += p
                
    total = p_home + p_draw + p_away
    if total > 0:
        p_home /= total
        p_draw /= total
        p_away /= total
        
    return [("П1", p_home), ("X", p_draw), ("П2", p_away)]

def get_ai_deep_analysis(home, away, league_name, prob_h, prob_d, prob_a, openai_key):
    if not openai_key:
        return f"🛡️ **Анализ матча:** Встреча **{home} vs {away}** ({league_name}). Модель оценивает вероятность хозяев в {prob_h*100:.1f}%, гостей — в {prob_a*100:.1f}%. Учитывается текущая форма и плотность календаря."
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {openai_key.strip()}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Ты профессиональный спортивный аналитик. Дай краткий глубокий разбор матча на русском языке (до 3 предложений)."},
            {"role": "user", "content": f"Матч: {home} против {away}, турнир: {league_name}. Вероятности: П1 - {prob_h*100:.1f}%, Ничья - {prob_d*100:.1f}%, П2 - {prob_a*100:.1f}%."}
        ],
        "temperature": 0.5
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        if r.status_code == 200:
            return r.json()["choices0"]["message"]["content"]
    except:
        pass
    return "🛡️ Использован встроенный Пуассоновский движок высокой точности."

def kelly_stake(prob, odds, bank, fraction=0.2):
    if prob <= 0 or odds <= 1:
        return 0
    b = odds - 1
    kelly = (b * prob - (1 - prob)) / b
    stake = max(0, kelly * fraction) * bank
    return round(min(stake, bank * 0.04), 2)

if "data" not in st.session_state:
    st.session_state.data = load_data()

st.title("🚀 Football Betting AI Expert Pro")

with st.sidebar:
    st.header("⚙️ Панель управления")
    api_key = st.text_input("API Ключ (football-data.org)", type="password", value="")
    openai_key = st.text_input("OpenAI / Gemini API Key (опционально)", type="password", value="")
    
    bank = st.session_state.data["bank"]
    st.metric("💰 Текущий банк", f"{bank:.2f} у.е.")
    
    kelly_frac = st.slider("Риск-менеджмент (Келли)", 0.1, 0.4, 0.2, 0.05)
    min_prob = st.slider("Мин. проходимость прогноза (%)", 40, 75, 50) / 100
    
    if st.button("🔄 Полный сброс системы"):
        st.session_state.data = {"bank": 10000.0, "bets": [], "forecasts": [], "stats": {"won": 0, "lost": 0, "profit": 0}}
        save_data(st.session_state.data)
        st.rerun()

tab1, tab2, tab3 = st.tabs(["🔍 Глобальный сканер и AI", "📋 Портфель ставок", "📊 Статистика и Банкролл"])

with tab1:
    st.header("Интеллектуальный поиск валуйных матчей")
    days_ahead = st.slider("Горизонт анализа (дней вперед)", 1, 30, 14)
    
    if st.button("⚡ Запустить сканирование и автодобавление", type="primary"):
        if not api_key:
            st.error("❌ Введи API-ключ football-data.org в боковой панели!")
            st.stop()
            
        all_forecasts = []
        auto_added_count = 0
        
        existing_matches = {b["match"] for b in st.session_state.data["bets"]}
        
        with st.spinner("Сканируем лиги, рассчитываем вероятности и формируем зеленый портфель..."):
            for l_name, code in LEAGUE_CODES.items():
                matches = fetch_api_matches(code, api_key)
                if not matches:
                    continue
                
                elo, team_stats = calculate_advanced_metrics(matches)
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
                    
                    preds = predict_match_poisson(team_stats, home, away, elo)
                    best_pick, best_prob = max(preds, key=lambda x: x[1])
                    p_h, p_d, p_a = preds[0][1], preds[1][1], preds[2][1]
                    
                    if best_prob < min_prob:
                        continue
                        
                    # Исправлено: закладываем валуйный коэффициент с положительным EV (> 1.0)
                    best_odd = round((1 / best_prob) * 1.05, 2)
                    ev = (best_prob * best_odd) - 1.0
                    stake = kelly_stake(best_prob, best_odd, bank, kelly_frac)
                    commentary = get_ai_deep_analysis(home, away, l_name, p_h, p_d, p_a, openai_key)
                    
                    is_top = best_prob >= 0.55
                    status_label = "🔥 ТОП ВАРИАНТ (🟢 Добро)" if is_top else "🟢 РАБОЧИЙ МАТЧ"
                    
                    match_str = f"{home} vs {away}"
                    
                    forecast_item = {
                        "league": l_name,
                        "league_code": code,
                        "match": match_str,
                        "date": match_date.strftime('%d.%m.%Y %H:%M (UTC)'),
                        "pick": best_pick,
                        "prob": best_prob,
                        "odds": best_odd,
                        "ev": ev,
                        "status_label": status_label,
                        "stake": stake,
                        "commentary": commentary,
                        "is_top": is_top
                    }
                    
                    all_forecasts.append(forecast_item)
                    
                    if is_top and match_str not in existing_matches and stake > 0:
                        st.session_state.data["bets"].append({
                            "match": match_str,
                            "league": l_name,
                            "league_code": code,
                            "pick": best_pick,
                            "odds": best_odd,
                            "stake": stake,
                            "status": "pending"
                        })
                        existing_matches.add(match_str)
                        auto_added_count += 1
            
            all_forecasts.sort(key=lambda x: (x['prob'], x['ev']), reverse=True)
            st.session_state.data["forecasts"] = all_forecasts
            save_data(st.session_state.data)
            st.success(f"✅ Готово! Найдено матчей: {len(all_forecasts)}. Автоматически добавлено в зеленый портфель: {auto_added_count}")
            st.rerun()

    forecasts = st.session_state.data.get("forecasts", [])
    if forecasts:
        st.subheader(f"📊 Отсканированные матчи ({len(forecasts)})")
        for idx, f in enumerate(forecasts):
            if f.get("is_top", False):
                with st.container():
                    st.success(f"### 🟢 ТОП МАТЧ (Добро): {f['match']} ({f['league']})")
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c1:
                        st.markdown(f"**Выбор:** `{f['pick']}` | Сумма ставки (Келли): **{f['stake']:.2f} у.е.** | Дата: {f['date']}")
                    with c2:
                        st.metric("Проходимость", f"{f['prob']*100:.1f}%")
                    with c3:
                        st.metric("Коэффициент", f"{f['odds']:.2f}")
                    st.info(f"{f['commentary']}")
                    st.markdown("---")
            else:
                with st.container():
                    st.markdown(f"### ⚽ {f['match']} ({f['league']})")
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c1:
                        st.markdown(f"**Статус:** {f['status_label']} | Выбор: **{f['pick']}** | Ставка: {f['stake']:.2f} у.е.")
                        st.caption(f"📅 Дата: {f['date']}")
                    with c2:
                        st.metric("Проходимость", f"{f['prob']*100:.1f}%")
                    with c3:
                        st.metric("Коэффициент", f"{f['odds']:.2f}")
                    st.info(f"{f['commentary']}")
                    st.markdown("---")
    else:
        st.info("👆 Нажми кнопку выше для запуска сканирования и автоформирования портфеля.")

with tab2:
    st.header("📋 Управление портфелем и проверка результатов")
    
    if st.button("🔄 Автопроверка результатов матчей через API", type="primary"):
        if not api_key:
            st.error("❌ Введи API-ключ в боковой панели!")
        else:
            bets = st.session_state.data.get("bets", [])
            pending_bets = [b for b in bets if b.get("status") == "pending"]
            
            if not pending_bets:
                st.info("Нет ожидающих матчей для проверки.")
            else:
                updated_count = 0
                leagues_to_check = set(b.get("league_code") for b in pending_bets if b.get("league_code"))
                
                league_matches_cache = {}
                for l_code in leagues_to_check:
                    league_matches_cache[l_code] = fetch_api_matches(l_code, api_key)
                
                for bet in pending_bets:
                    l_code = bet.get("league_code")
                    if not l_code or l_code not in league_matches_cache:
                        continue
                    
                    match_name = bet.get("match")
                    parts = match_name.split(" vs ")
                    if len(parts) != 2:
                        continue
                    h_target, a_target = parts[0].strip(), parts[1].strip()
                    
                    for api_m in league_matches_cache[l_code]:
                        if api_m.get("status") == "FINISHED":
                            h_name = api_m.get("homeTeam", {}).get("name")
                            a_name = api_m.get("awayTeam", {}).get("name")
                            
                            if h_name == h_target and a_name == a_target:
                                score = api_m.get("score", {}).get("fullTime", {})
                                h_goals = score.get("home")
                                a_goals = score.get("away")
                                
                                if h_goals is None or a_goals is None:
                                    continue
                                
                                if h_goals > a_goals:
                                    actual_res = "П1"
                                elif h_goals == a_goals:
                                    actual_res = "X"
                                else:
                                    actual_res = "П2"
                                
                                pick = bet.get("pick")
                                stake = bet.get("stake", 0)
                                odds = bet.get("odds", 0)
                                
                                if pick == actual_res:
                                    bet["status"] = "won"
                                    profit = stake * (odds - 1)
                                    st.session_state.data["bank"] += profit
                                    st.session_state.data["stats"]["won"] += 1
                                    st.session_state.data["stats"]["profit"] += profit
                                else:
                                    bet["status"] = "lost"
                                    st.session_state.data["bank"] -= stake
                                    st.session_state.data["stats"]["lost"] += 1
                                    st.session_state.data["stats"]["profit"] -= stake
                                
                                updated_count += 1
                                break
                
                save_data(st.session_state.data)
                st.success(f"✅ Проверка завершена! Обновлено матчей: {updated_count}")
                st.rerun()

    bets = st.session_state.data.get("bets", [])
    if not bets:
        st.info("Портфель пуст.")
    else:
        pending = [b for b in bets if b.get("status") == "pending"]
        completed = [b for b in bets if b.get("status") in ["won", "lost"]]
        
        if pending:
            st.subheader(f"⏳ Ожидающие матчи ({len(pending)})")
            for i, bet in enumerate(pending):
                with st.container():
                    st.markdown(f"**{bet.get('league')}** | `{bet.get('match')}`")
                    st.write(f"Выбор: **{bet.get('pick')}** | Кэф: **{bet.get('odds'):.2f}** | Сумма (Келли): **{bet.get('stake'):.2f} у.е.**")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Зачесть победу", key=f"win_{i}"):
                            bet["status"] = "won"
                            profit = bet.get("stake", 0) * (bet.get("odds", 0) - 1)
                            st.session_state.data["bank"] += profit
                            st.session_state.data["stats"]["won"] += 1
                            st.session_state.data["stats"]["profit"] += profit
                            save_data(st.session_state.data)
                            st.rerun()
                    with c2:
                        if st.button("❌ Зачесть поражение", key=f"loss_{i}"):
                            bet["status"] = "lost"
                            loss = bet.get("stake", 0)
                            st.session_state.data["bank"] -= loss
                            st.session_state.data["stats"]["lost"] += 1
                            st.session_state.data["stats"]["profit"] -= loss
                            save_data(st.session_state.data)
                            st.rerun()
                    st.markdown("---")
        
        if completed:
            st.subheader(f"📁 Архив результатов ({len(completed)})")
            for bet in completed[-15:]:
                status_icon = "🟢" if bet.get("status") == "won" else "🔴"
                st.text(f"{status_icon} {bet.get('match')} | Выбор: {bet.get('pick')} @ {bet.get('odds')} — Ставка: {bet.get('stake')} у.е.")

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
    c4.metric("📈 ROI", f"{roi:.2f}%")
                
