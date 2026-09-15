import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import json
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="AI Sport Bot Pro (Будущие матчи)", page_icon="⚽", layout="wide")

# Дизайн и стили
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(10, 15, 25, 0.92), rgba(10, 15, 25, 0.98)), 
                    url('https://images.unsplash.com/photo-1518091043644-c1d4457512c6?q=80&w=1920&auto=format&fit=crop');
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }
    .forecast-card {
        background: rgba(30, 41, 59, 0.75);
        padding: 16px;
        border-radius: 12px;
        border: 1px solid rgba(56, 189, 248, 0.2);
        margin-bottom: 12px;
        backdrop-filter: blur(4px);
    }
    .bet-card-pending {
        background: rgba(30, 41, 59, 0.75);
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.2);
        margin-bottom: 12px;
    }
    .bet-card-won {
        background: rgba(16, 185, 129, 0.15);
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
        margin-bottom: 12px;
    }
    .bet-card-lost {
        background: rgba(239, 68, 68, 0.15);
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

def get_league_urls():
    """Алгоритм автоопределения актуального сезона и правильных URL (только поддерживаемые лиги)"""
    base = "https://www.football-data.co.uk/mmz4281/"
    seasons = ["2627", "2526", "2425"] 
    
    leagues = {
        "Англия (АПЛ)": "E0.csv",
        "Испания (Ла Лига)": "SP1.csv",
        "Италия (Серия А)": "I1.csv",
        "Германия (Бундеслига)": "D1.csv",
        "Франция (Лига 1)": "F1.csv",
        "Турция (Суперлига)": "T1.csv",
        "Бельгия (Про-лига)": "B1.csv",
        "Нидерланды (Эредивизи)": "N1.csv",
        "Португалия (Примейра)": "P1.csv"
    }
    
    active_season = "2526"
    for season in seasons:
        try:
            test_url = f"{base}{season}/E0.csv"
            pd.read_csv(test_url, nrows=1)
            active_season = season
            break
        except Exception:
            continue
            
    return {name: f"{base}{active_season}/{file}" for name, file in leagues.items()}, active_season

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
                for key in ["weights", "scanned_forecasts", "archive_matches"]:
                    if key not in data:
                        data[key] = {"xg_w": 1.0} if key == "weights" else []
                if "bets" in data:
                    for b in data["bets"]:
                        b["stake"] = b.get("stake", STAKE_SIZE) or STAKE_SIZE
                        b["reason"] = b.get("reason", "Сигнал модели")
                        b["prob"] = b.get("prob", 0.5)
                return data
        except Exception:
            pass
    return reset_full_system()

def save_history(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if "app_data" not in st.session_state:
    st.session_state.app_data = load_history()

st.title("⚽ AI Sport Bot Pro (Прогноз будущих матчей)")

# --- БОКОВАЯ ПАНЕЛЬ ---
st.sidebar.header("⚙️ Настройки и Банк")
current_weights = st.session_state.app_data.get("weights", {"xg_w": 1.0})
st.sidebar.write(f"Вес модели xG: `{current_weights.get('xg_w', 1.0):.3f}`")
current_bank = st.session_state.app_data["bank"]
st.sidebar.metric(label="Баланс банкролла", value=f"{current_bank:.2f} у.е.")

leagues_dict, active_season = get_league_urls()
st.sidebar.success(f"✅ Активный сезон данных: **{active_season[:2]}/{active_season[2:]}**")

if st.sidebar.button("🔄 Полный сброс системы"):
    st.session_state.app_data = reset_full_system()
    st.sidebar.success("Система сброшена!")
    st.rerun()

# --- ИНТЕРФЕЙС ВКЛАДОК ---
tab1, tab2, tab3 = st.tabs([
    "🌐 Прогноз будущих матчей", 
    "📜 История и Активные ставки", 
    "⚙️ О системе"
])

with tab1:
    st.markdown("### 📅 Алгоритмический прогноз на будущие матчи")
    st.write("Модель обучается на *сыгранных* матчах текущего сезона, чтобы рассчитать силу команд, а затем применяет эти данные для поиска валуйных ставок в *будущих* матчах.")

    selected_leagues = st.multiselect(
        "Отметьте лиги и турниры для анализа:",
        options=list(leagues_dict.keys()),
        default=[
            "Англия (АПЛ)", 
            "Испания (Ла Лига)", 
            "Италия (Серия А)",
            "Германия (Бундеслига)"
        ]
    )

    # ПОЛЗУНОК ПО ДНЯМ
    days_ahead = st.slider(
        "Показывать матчи на ближайшие дни:", 
        min_value=1, 
        max_value=14, 
        value=7,
        help="Бот проанализирует и покажет прогнозы только на те матчи, которые состоятся в выбранный период."
    )
    
    today = pd.Timestamp.now().normalize()
    future_limit = today + pd.Timedelta(days=days_ahead)
    st.info(f"📆 Диапазон анализа: с **{today.strftime('%d.%m.%Y')}** по **{future_limit.strftime('%d.%m.%Y')}**")

    if st.button("🚀 Запустить анализ будущих матчей", type="primary"):
        if not selected_leagues:
            st.warning("Выберите хотя бы один турнир!")
        else:
            all_dfs = []
            success_count = 0
            
            with st.spinner("Загрузка актуальных расписаний и результатов..."):
                for league_name in selected_leagues:
                    url = leagues_dict[league_name]
                    try:
                        df_temp = pd.read_csv(url)
                        df_temp['League_Source'] = league_name
                        all_dfs.append(df_temp)
                        success_count += 1
                    except Exception as e:
                        st.warning(f"Не удалось загрузить {league_name}.")

            if not all_dfs:
                st.error("Не удалось загрузить данные.")
            else:
                combined_df = pd.concat(all_dfs, ignore_index=True)
                
                # Корректное приведение дат с учетом возможных форматов
                combined_df['MatchDate'] = pd.to_datetime(combined_df['Date'], errors='coerce', dayfirst=True)
                
                st.success(f"Загружено лиг: {success_count}. Всего строк в базе: {len(combined_df)}")

                with st.spinner("1. Обучение модели на сыгранных матчах..."):
                    past_matches = combined_df[pd.notna(combined_df['FTHG']) & pd.notna(combined_df['FTAG']) & (combined_df['FTHG'] != '')]
                    
                    team_stats = {}
                    valid_matches_count = 0
                    
                    for _, row in past_matches.iterrows():
                        try:
                            home = row.get('HomeTeam')
                            away = row.get('AwayTeam')
                            
                            if pd.isna(home) or pd.isna(away) or home == '' or away == '':
                                continue
                                
                            fthg = float(row.get('FTHG'))
                            ftag = float(row.get('FTAG'))
                            
                            if home not in team_stats:
                                team_stats[home] = {'home_goals': [], 'away_conceded': [], 'away_goals': [], 'home_conceded': []}
                            if away not in team_stats:
                                team_stats[away] = {'home_goals': [], 'away_conceded': [], 'away_goals': [], 'home_conceded': []}
                                
                            team_stats[home]['home_goals'].append(fthg)
                            team_stats[home]['away_conceded'].append(ftag)
                            team_stats[away]['away_goals'].append(ftag)
                            team_stats[away]['home_conceded'].append(fthg)
                            
                            valid_matches_count += 1
                        except Exception:
                            continue
                    
                    if valid_matches_count == 0:
                        st.error("Не найдено сыгранных матчей для обучения модели.")
                        st.stop()
                    
                    st.success(f"✅ Проанализировано сыгранных матчей: {valid_matches_count}")
                    
                    all_home_goals = [g for t in team_stats.values() for g in t.get('home_goals', [])]
                    all_away_goals = [g for t in team_stats.values() for g in t.get('away_goals', [])]
                    
                    league_avg_home = np.mean(all_home_goals) if all_home_goals else 1.4
                    league_avg_away = np.mean(all_away_goals) if all_away_goals else 1.1

                with st.spinner(f"2. Поиск будущих матчей до {future_limit.strftime('%d.%m.%Y')}..."):
                    # Фильтрация будущих матчей (где дата в диапазоне и результат пустой)
                    future_mask = (
                        (combined_df['MatchDate'] >= today) & 
                        (combined_df['MatchDate'] <= future_limit) & 
                        (combined_df['FTHG'].isna() | (combined_df['FTHG'] == ''))
                    )
                    future_matches = combined_df[future_mask]

                    xg_w = current_weights.get("xg_w", 1.0)
                    app_data = st.session_state.app_data
                    bets = app_data["bets"]
                    existing_match_names = {b["match"] for b in bets}
                    bank = app_data["bank"]

                    found_forecasts = []
                    processed_count = 0
                    
                    for _, row in future_matches.iterrows():
                        try:
                            home_team = row.get('HomeTeam')
                            away_team = row.get('AwayTeam')
                            league_src = row.get('League_Source', 'Турнир')
                            match_date = row.get('MatchDate')

                            if pd.isna(home_team) or pd.isna(away_team) or pd.isna(match_date):
                                continue
                            if home_team == '' or away_team == '':
                                continue

                            home_odd = float(row.get('B365H', 1.95)) if pd.notna(row.get('B365H')) else (float(row.get('PSH', 1.95)) if pd.notna(row.get('PSH')) else 1.95)
                            draw_odd = float(row.get('B365D', 3.40)) if pd.notna(row.get('B365D')) else (float(row.get('PSD', 3.40)) if pd.notna(row.get('PSD')) else 3.40)
                            away_odd = float(row.get('B365A', 3.10)) if pd.notna(row.get('B365A')) else (float(row.get('PSA', 3.10)) if pd.notna(row.get('PSA')) else 3.10)

                            processed_count += 1

                            h_goals = team_stats.get(home_team, {}).get('home_goals', [league_avg_home])
                            a_conceded = team_stats.get(away_team, {}).get('home_conceded', [league_avg_home])
                            a_goals = team_stats.get(away_team, {}).get('away_goals', [league_avg_away])
                            h_conceded = team_stats.get(home_team, {}).get('away_conceded', [league_avg_away])

                            h_attack = np.mean(h_goals) / max(0.1, league_avg_home)
                            a_defense = np.mean(a_conceded) / max(0.1, league_avg_home)
                            a_attack = np.mean(a_goals) / max(0.1, league_avg_away)
                            h_defense = np.mean(h_conceded) / max(0.1, league_avg_away)

                            h_lam = max(0.3, h_attack * a_defense * league_avg_home * xg_w)
                            a_lam = max(0.3, a_attack * h_defense * league_avg_away * xg_w)

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

                            best_pick = max(options, key=lambda x: x[1] * x[2])
                            pick_name, prob, odd = best_pick

                            edge = (prob * odd) - 1.0
                            decision = "🟢 СТАВИМ" if edge > 0.03 and odd < 3.5 else "🔴 НЕ СТАВИМ"
                            
                            date_str = match_date.strftime('%d.%m')
                            reason = f"Дата: {date_str}. λ={h_lam:.2f}/{a_lam:.2f}. Шанс: {prob*100:.1f}%, Edge: {edge*100:.1f}%."

                            forecast_item = {
                                "league_name": league_src,
                                "league_color": "#38bdf8",
                                "match": f"{home_team} vs {away_team}",
                                "pick": pick_name,
                                "odd": odd,
                                "prob": prob,
                                "reason": reason,
                                "decision": decision
                            }
                            found_forecasts.append(forecast_item)

                            if "СТАВИМ" in decision and forecast_item["match"] not in existing_match_names and bank >= STAKE_SIZE:
                                bank -= STAKE_SIZE
                                new_bet = {
                                    "id": len(bets) + 1,
                                    "match": forecast_item["match"],
                                    "league_name": forecast_item["league_name"],
                                    "league_color": forecast_item["league_color"],
                                    "pick": pick_name,
                                    "odd": odd,
                                    "stake": STAKE_SIZE,
                                    "status": "pending",
                                    "reason": f"{reason} | Рекомендация: {pick_name}",
                                    "prob": prob
                                }
                                bets.append(new_bet)
                                existing_match_names.add(forecast_item["match"])
                        except Exception:
                            continue

                    app_data["bank"] = bank
                    app_data["scanned_forecasts"] = found_forecasts
                    save_history(app_data)
                    st.success(f"✅ Найдено будущих матчей в расписании: {processed_count}. Отображено в прогнозах ниже.")
                    st.rerun()

    st.markdown("### 📋 Прогнозы на выбранный период:", unsafe_allow_html=True)
    forecasts = st.session_state.app_data.get("scanned_forecasts", [])
    
    if not forecasts:
        st.info("Прогнозов на выбранный период пока нет. Нажмите кнопку «Запустить анализ будущих матчей» или увеличьте диапазон дней.")
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
            
            decision_color = "#10b981" if "СТАВИМ" in decision else "#ef4444"
            
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
                        st.session_state.app_data["bank"] += float(stake) * float(odd)
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
    st.write("""
    **Как работает алгоритм:**
    1. **Данные:** Скрипт загружает актуальные таблицы лиг Европы.
    2. **Обучение:** На основе сыгранных матчей рассчитывается средняя результативность лиги и индивидуальные коэффициенты атаки/обороны команд.
    3. **Прогноз:** Для будущих матчей модель подставляет эти коэффициенты в распределение Пуассона, вычисляет честные вероятности и сравнивает их с коэффициентами букмекеров.
    4. **Валуй (Edge):** Ставка рекомендуется только если математическое ожидание превышает 3% (`prob * odd > 1.03`).
    """)
