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

# Стильный дизайн, темная тема стадиона и яркие цветовые карточки
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
    .bet-card-pending {
        background: rgba(30, 41, 59, 0.7);
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #f59e0b;
        border-top: 1px solid rgba(245, 158, 11, 0.2);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 12px;
    }
    .bet-card-won {
        background: rgba(16, 185, 129, 0.12);
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #10b981;
        border-top: 1px solid rgba(16, 185, 129, 0.3);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 12px;
    }
    .bet-card-lost {
        background: rgba(239, 68, 68, 0.12);
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #ef4444;
        border-top: 1px solid rgba(239, 68, 68, 0.3);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 12px;
    }
    </style>
""", unsafe_allow_html=True)

HISTORY_FILE = "bet_history.json"
STAKE_SIZE = 100.0

def reset_history_file():
    clean_data = {
        "bank": 10000.0, 
        "weights": {"xg_w": 1.0, "odds_limit": 2.2},
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
                    data["weights"] = {"xg_w": 1.0, "form_w": 0.5, "odds_limit": 2.2}
                if "archive_matches" not in data:
                    data["archive_matches"] = []
                if "bets" in data:
                    for b in data["bets"]:
                        if "stake" not in b or not b["stake"] or b["stake"] <= 0:
                            b["stake"] = STAKE_SIZE
                        if "reason" not in b or not b["reason"]:
                            b["reason"] = "Автоматический валуйный сигнал модели"
                return data
        except:
            pass
    return reset_history_file()

def save_history(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if "app_data" not in st.session_state:
    st.session_state.app_data = load_history()

st.title("⚽ AI Football Bot Pro — Автоматический Анализатор")

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
    'soccer_turkey_super_lig'
]

# --- ЗАГРУЗКА АРХИВА С ПУТЕМ MMZ4281 ---
def load_public_football_archive():
    seasons = ["2425", "2324", "2223", "2122"]
    archive_items = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for season in seasons:
        url = f"https://www.football-data.co.uk/mmz4281/{season}/E0.csv"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))
                for _, row in df.iterrows():
                    home = row.get('HomeTeam')
                    away = row.get('AwayTeam')
                    fthg = row.get('FTHG')
                    ftag = row.get('FTAG')
                    
                    if pd.notna(home) and pd.notna(away) and pd.notna(fthg) and pd.notna(ftag):
                        winner = "П1" if fthg > ftag else ("Ничья (X)" if fthg == ftag else "П2")
                        archive_items.append({
                            "match": f"{home} vs {away}",
                            "winner": winner,
                            "source": f"Football-Data ({season})"
                        })
                if archive_items:
                    break
        except Exception:
            continue
            
    if archive_items:
        st.session_state.app_data["archive_matches"] = archive_items
        save_history(st.session_state.app_data)
        return len(archive_items), f"Успешно загружено {len(archive_items)} реальных матчей из архива!"
    else:
        return 0, "Не удалось загрузить архив. Проверьте соединение или используйте ручную загрузку ниже."

# --- ГЕНЕРАТОР ОБОСНОВАНИЙ ---
def get_smart_reason(pick, odd, edge):
    reasons = []
    if edge > 0.08:
        reasons.append(f"Высокий статистический перевес (+{edge*100:.1f}%)")
    elif edge > 0.04:
        reasons.append(f"Уверенный валуйный сигнал (+{edge*100:.1f}%)")
    else:
        reasons.append(f"Умеренный сигнал (+{edge*100:.1f}%)")
        
    if odd < 1.75:
        reasons.append("коэффициент надежного фаворита")
    elif odd <= 2.1:
        reasons.append("сбалансированный коэффициент под риск-менеджмент")
    else:
        reasons.append("высокий коэффициент на грани лимита")
        
    return " • ".join(reasons)

# --- АНАЛИЗАТОР МАТЧЕЙ И РАЗМЕЩЕНИЕ СТАВОК ---
def analyze_upcoming_matches(api_key):
    weights = st.session_state.app_data["weights"]
    xg_w = weights.get("xg_w", 1.0)
    odds_limit = weights.get("odds_limit", 2.2)
    
    new_bets_placed = 0
    checked_count = 0
    
    for league in LEAGUES:
        url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={api_key}&regions=eu&markets=h2h&oddsFormat=decimal"
        try:
            response = requests.get(url, timeout=10)
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
                
                if best_pick and best_pick[3] > 0.02:
                    pick_name, prob, odd, edge = best_pick
                    match_str = f"{home_team} vs {away_team}"
                    
                    existing_matches = [b["match"] for b in st.session_state.app_data["bets"]]
                    if match_str not in existing_matches:
                        if st.session_state.app_data["bank"] >= STAKE_SIZE:
                            st.session_state.app_data["bank"] -= STAKE_SIZE
                            new_bet = {
                                "id": len(st.session_state.app_data["bets"]) + 1,
                                "match": match_str,
                                "pick": pick_name,
                                "odd": odd,
                                "stake": STAKE_SIZE,
                                "status": "pending",
                                "reason": get_smart_reason(pick_name, odd, edge)
                            }
                            st.session_state.app_data["bets"].append(new_bet)
                            new_bets_placed += 1
        except Exception:
            continue
            
    save_history(st.session_state.app_data)
    return checked_count, new_bets_placed

# --- МНОГОКРУГОВОЕ ОБУЧЕНИЕ ИИ ---
def train_on_epochs_multisource(epochs=3):
    weights = st.session_state.app_data["weights"]
    logs = []
    training_items = []
    
    settled_bets = [b for b in st.session_state.app_data["bets"] if b["status"] in ["won", "lost"]]
    for b in settled_bets:
        training_items.append({
            "match": b["match"],
            "is_win": (b["status"] == "won")
        })

    arch = st.session_state.app_data.get("archive_matches", [])
    for item in arch:
        training_items.append({
            "match": item["match"],
            "winner": item["winner"]
        })

    if not training_items:
        return 0, ["⚠️ База для обучения пуста! Нажмите кнопку '📥 Загрузить архив' или загрузите CSV-файл ниже."]

    total_events_processed = 0
    
    for epoch in range(1, epochs + 1):
        epoch_correct = 0
        logs.append(f"--- 🔄 КРУГ ОБУЧЕНИЯ (ЭПОХА) №{epoch} ---")
        
        for item in training_items:
            xg_w = weights.get("xg_w", 1.0)
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
            
            if "is_win" in item:
                success = item["is_win"]
            else:
                ai_pick = "П1" if p_home > p_away and p_home > p_draw else ("Ничья (X)" if p_draw > p_home and p_draw > p_away else "П2")
                success = (ai_pick == item["winner"])
            
            if success:
                weights["xg_w"] = min(2.5, weights["xg_w"] * 1.008)
                epoch_correct += 1
            else:
                weights["odds_limit"] = max(1.6, weights["odds_limit"] * 0.992)
                weights["xg_w"] = max(0.5, weights["xg_w"] * 0.995)
            
            total_events_processed += 1

        acc = (epoch_correct / len(training_items)) * 100
        logs.append(f"📊 Эпоха {epoch} завершена. Точность на базе: {acc:.1f}% | Вес xG: {weights['xg_w']:.3f}")

    save_history(st.session_state.app_data)
    return len(training_items), logs

# --- ИНТЕРФЕЙС ВКЛАДОК ---
tab1, tab2, tab3, tab4 = st.tabs(["🎯 Анализ и Авто-ставки", "📊 Статистика и История", "🧠 Обучение ИИ по ставкам", "⚙️ О системе"])

with tab1:
    st.markdown("### 🚀 Автоматический поиск матчей и валуйных ставок")
    st.write("Нажмите кнопку ниже, чтобы бот опросил The Odds API, проанализировал расписание матчей через модель и автоматически разместил виртуальные ставки.")
    
    if st.button("🔎 Запустить сканирование и сделать ставки"):
        if not odds_api_key:
            st.warning("⚠️ Введите API ключ для The Odds API в боковой панели слева!")
        else:
            with st.spinner("ИИ сканирует линии букмекеров и рассчитывает перевес..."):
                checked, placed = analyze_upcoming_matches(odds_api_key)
                st.success(f"Анализ завершен! Проверено матчей: {checked}. Успешно размещено новых ставок: {placed}.")
                st.rerun()

    st.markdown("### 📋 Активные и текущие ставки в работе:")
    bets = st.session_state.app_data.get("bets", [])
    if not bets:
        st.info("Пока нет ни одной ставки. Запустите сканирование выше.")
    else:
        for idx, b in enumerate(bets):
            match_name = b.get("match", "Матч")
            reason_text = b.get("reason", "Автоматический сигнал модели")
            pick_name = b.get("pick", "-")
            odd_val = b.get("odd", 1.9)
            stake_val = b.get("stake", STAKE_SIZE)
            status = b["status"]
            
            # Выбор цвета карточки в зависимости от статуса
            card_class = "bet-card-pending"
            if status == "won":
                card_class = "bet-card-won"
            elif status == "lost":
                card_class = "bet-card-lost"
            
            st.markdown(f"""
                <div class="{card_class}">
                    <div style="font-size: 1.15rem; font-weight: 700; color: #f8fafc; margin-bottom: 4px;">⚽ {match_name}</div>
                    <div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 10px; font-style: italic;">💡 {reason_text}</div>
                    <div style="display: flex; gap: 15px; font-size: 0.95rem; font-weight: 500;">
                        <span style="color: #38bdf8;">Выбор: <b>{pick_name}</b></span>
                        <span style="color: #cbd5e1;">Кф: <b style="color: #facc15;">{odd_val:.2f}</b></span>
                        <span style="color: #cbd5e1;">Сумма: <b style="color: #4ade80;">{stake_val} у.е.</b></span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            cols = st.columns([2, 2])
            with cols[0]:
                if status == "pending":
                    st.markdown("⏳ <span style='color: #f59e0b; font-weight: bold;'>Статус: В ожидании</span>", unsafe_allow_html=True)
                elif status == "won":
                    st.markdown("🎉 <span style='color: #10b981; font-weight: bold;'>Статус: Выиграна</span>", unsafe_allow_html=True)
                else:
                    st.markdown("😢 <span style='color: #ef4444; font-weight: bold;'>Статус: Проиграна</span>", unsafe_allow_html=True)
                    
            with cols[1]:
                if status == "pending":
                    c_win, c_loss = st.columns(2)
                    if c_win.button("✅ Зашло", key=f"w_{idx}"):
                        b["status"] = "won"
                        st.session_state.app_data["bank"] += stake_val * odd_val
                        save_history(st.session_state.app_data)
                        st.rerun()
                    if c_loss.button("❌ Мимо", key=f"l_{idx}"):
                        b["status"] = "lost"
                        save_history(st.session_state.app_data)
                        st.rerun()
                else:
                    if st.button("↩️ Сбросить статус", key=f"reset_{idx}"):
                        if status == "won":
                            st.session_state.app_data["bank"] -= (stake_val * odd_val - stake_val)
                        else:
                            st.session_state.app_data["bank"] += stake_val
                        b["status"] = "pending"
                        save_history(st.session_state.app_data)
                        st.rerun()
            st.markdown("---")

with tab2:
    st.markdown("### 📊 Статистика и Процент проходов (Win Rate)")
    bets = st.session_state.app_data.get("bets", [])
    real_bets = [b for b in bets if b["status"] in ["won", "lost", "pending"]]
    total_bets = len(real_bets)
    won_bets = len([b for b in real_bets if b["status"] == "won"])
    lost_bets = len([b for b in real_bets if b["status"] == "lost"])
    pending_bets = len([b for b in real_bets if b["status"] == "pending"])
    settled_count = won_bets + lost_bets
    win_rate = (won_bets / settled_count * 100) if settled_count > 0 else 0.0

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.markdown(f'<div class="metric-card"><h4>Всего ставок</h4><h2>{total_bets}</h2></div>', unsafe_allow_html=True)
    with col_m2:
        st.markdown(f'<div class="metric-card"><h4>Выиграно / Проиграно</h4><h2>{won_bets} / {lost_bets}</h2></div>', unsafe_allow_html=True)
    with col_m3:
        st.markdown(f'<div class="metric-card"><h4>Win Rate</h4><h2 style="color: #4ade80;">{win_rate:.1f}%</h2></div>', unsafe_allow_html=True)
    with col_m4:
        st.markdown(f'<div class="metric-card"><h4>В ожидании</h4><h2 style="color: #f59e0b;">{pending_bets}</h2></div>', unsafe_allow_html=True)

with tab3:
    st.markdown("### 🧠 Многокруговое обучение ИИ (Архив + Эпохи)")
    st.write("Загрузите официальную открытую базу реальных матчей из европейских лиг или добавьте CSV-файл вручную, затем запустите многокруговое обучение (эпохи) для точной калибровки весов.")
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("📥 Загрузить архив с сайта (Европа)"):
            with st.spinner("Скачиваем базу матчей..."):
                count, msg = load_public_football_archive()
                if count > 0:
                    st.success(msg)
                else:
                    st.error(msg)
                    
    with col_b2:
        uploaded_file = st.file_uploader("📂 Или загрузить свой CSV-файл матчей", type=["csv"])
        if uploaded_file is not None:
            try:
                df_up = pd.read_csv(uploaded_file)
                archive_items = []
                for _, row in df_up.iterrows():
                    home = row.get('HomeTeam')
                    away = row.get('AwayTeam')
                    fthg = row.get('FTHG')
                    ftag = row.get('FTAG')
                    if pd.notna(home) and pd.notna(away) and pd.notna(fthg) and pd.notna(ftag):
                        winner = "П1" if fthg > ftag else ("Ничья (X)" if fthg == ftag else "П2")
                        archive_items.append({
                            "match": f"{home} vs {away}",
                            "winner": winner,
                            "source": "Custom CSV"
                        })
                if archive_items:
                    st.session_state.app_data["archive_matches"] = archive_items
                    save_history(st.session_state.app_data)
                    st.success(f"Успешно загружено {len(archive_items)} матчей из вашего файла!")
            except Exception as e:
                st.error(f"Ошибка чтения файла: {e}")

    st.markdown(f"📦 Загружено матчей в базе архива: **{len(st.session_state.app_data.get('archive_matches', []))}**")
    
    epochs_count = st.slider("Количество кругов обучения (эпох за один клик)", min_value=1, max_value=20, value=5, step=1)
    
    if st.button("⚡ Запустить обучение в несколько кругов"):
        with st.spinner(f"ИИ проводит {epochs_count} кругов обучения..."):
            trained_n, arch_logs = train_on_epochs_multisource(epochs=epochs_count)
            st.success(f"Успешно проведено кругов: {epochs_count} (обработано записей в базе: {trained_n})")
            with st.expander("📋 Подробный лог всех кругов обучения"):
                for line in arch_logs:
                    st.write(line)

    history_data = st.session_state.app_data
    st.metric("Текущий баланс банка", f"{history_data['bank']:.2f} у.е.")
    
    st.markdown("#### Текущие веса модели после обучения:")
    st.json(history_data["weights"])

with tab4:
    st.markdown("### ℹ️ О системе")
    st.write("""
    Профессиональный бот для анализа футбольных матчей, интеграции с The Odds API, автоматического поиска валуйных сигналов и самообучения нейро-модели методом эпох на исторических датасетах.
    """)
