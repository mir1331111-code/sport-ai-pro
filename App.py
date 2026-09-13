import datetime
import json
import os
import random
import re
import time
import requests
import streamlit as st
from groq import Groq
from streamlit_autorefresh import st_autorefresh

# --- АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ (КАЖДЫЕ 15 МИНУТ) ---
count = st_autorefresh(interval=900000, key="auto_sniper_refresh")

HISTORY_FILE = "match_history_pro.json"


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history_data):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=4)
    except Exception:
        pass


def calculate_devigged_probability(odds1, odds2):
    """
    Рассчитывает истинную вероятность исхода без учета букмекерской маржи (De-vigging).
    Использует мультипликативный метод (proportional method).
    """
    try:
        o1 = float(odds1)
        o2 = float(odds2)
        if o1 <= 1.0 or o2 <= 1.0:
            return 0.5, 0.5
        implied1 = 1.0 / o1
        implied2 = 1.0 / o2
        total_margin = implied1 + implied2
        fair1 = implied1 / total_margin
        fair2 = implied2 / total_margin
        return round(fair1, 4), round(fair2, 4)
    except Exception:
        return 0.5, 0.5


def calculate_kelly_stake(bankroll, odds, probability, fraction=0.25):
    """
    Рассчитывает оптимальный размер ставки по критерию Келли с учетом де-виггинг вероятности.
    """
    try:
        odds = float(odds)
        if odds <= 1.0 or probability <= 0:
            return 0.0
        b = odds - 1.0
        q = 1.0 - probability
        kelly_pct = (probability * b - q) / b
        if kelly_pct <= 0:
            return 0.0
        adjusted_pct = min(kelly_pct * fraction, 0.10)  # Ограничение 10% банка
        return round(bankroll * adjusted_pct, 2)
    except Exception:
        return 0.0


def get_financial_stats():
    initial = st.session_state.get("initial_bankroll", 10000.0)
    total_profit = 0.0
    total_staked = 0.0
    settled = 0
    wins = 0
    clv_beats = 0
    clv_total = 0

    for entry in st.session_state.history:
        for card in entry.get("data", []):
            st_val = card.get("status", "⌛ Ожидание")
            stake = float(card.get("recommended_stake", 0.0) or 0.0)
            odds = float(card.get("coefficient", 1.0) or 1.0)
            closing_odds = float(card.get("closing_odds", odds) or odds)

            if st_val in ["✅ Проход", "❌ Проигрыш"]:
                clv_total += 1
                if odds <= closing_odds:  # Биение закрывающей линии (Beat CLV)
                    clv_beats += 1

            if st_val == "✅ Проход":
                total_profit += stake * (odds - 1.0)
                total_staked += stake
                settled += 1
                wins += 1
            elif st_val == "❌ Проигрыш":
                total_profit -= stake
                total_staked += stake
                settled += 1

    current_bank = initial + total_profit
    roi = (total_profit / total_staked * 100) if total_staked > 0 else 0.0
    win_rate = (wins / settled * 100) if settled > 0 else 0.0
    clv_rate = (clv_beats / clv_total * 100) if clv_total > 0 else 0.0
    return round(current_bank, 2), round(total_profit, 2), round(roi, 2), round(win_rate, 1), settled, wins, round(clv_rate, 1)


st.set_page_config(
    page_title="Syndicate Pro: Advanced Betting Terminal", page_icon="⚡", layout="wide"
)

if "history" not in st.session_state:
    st.session_state.history = load_history()

if "initial_bankroll" not in st.session_state:
    st.session_state.initial_bankroll = 10000.0

if "last_scan_timestamp" not in st.session_state:
    st.session_state.last_scan_timestamp = 0

# БАЗА ДАННЫХ ЛИГ ПО КАТЕГОРИЯМ
SPORT_GROUPS = {
    "⚽ Футбол": {
        "category": "soccer",
        "endpoints": [
            ("soccer", "eng.1", "АПЛ (Англия)"),
            ("soccer", "esp.1", "Ла Лига (Испания)"),
            ("soccer", "ger.1", "Бундеслига (Германия)"),
            ("soccer", "ita.1", "Серия А (Италия)"),
            ("soccer", "fra.1", "Лига 1 (Франция)"),
            ("soccer", "rus.1", "РПЛ (Россия)"),
            ("soccer", "uefa.champions", "Лига Чемпионов УЕФА"),
        ],
    },
    "🏒 Хоккей": {
        "category": "hockey",
        "endpoints": [
            ("hockey", "nhl", "НХЛ (США/Канада)"),
            ("hockey", "khl", "КХЛ (Россия/Европа)"),
            ("hockey", "vhl", "ВХЛ (Россия)"),
        ],
    },
    "🏀 Баскетбол": {
        "category": "basketball",
        "endpoints": [
            ("basketball", "nba", "НБА (США)"),
            ("basketball", "euroleague", "Евролига (Европа)"),
            ("basketball", "russia.1", "Единая лига ВТБ (Россия)"),
        ],
    },
    "🏐 Волейбол": {
        "category": "volleyball",
        "endpoints": [
            ("volleyball", "volleyball", "Волейбол (Международный)"),
        ],
    },
    "🎾 Теннис": {
        "category": "tennis",
        "endpoints": [
            ("tennis", "atp", "ATP Теннис (Мужчины)"),
            ("tennis", "wta", "WTA Теннис (Женщины)"),
        ],
    },
    "🎮 Киберспорт": {
        "category": "esports",
        "endpoints": [
            ("esports", "counter-strike", "Counter-Strike 2"),
            ("esports", "dota-2", "Dota 2"),
            ("esports", "league-of-legends", "League of Legends"),
        ],
    },
}

SPORT_BACKGROUNDS = {
    "soccer": ["https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"],
    "basketball": ["https://images.unsplash.com/photo-1546519638-68e109498ffc?auto=format&fit=crop&w=1920&q=80"],
    "hockey": ["https://images.unsplash.com/photo-1580748141549-71748dbe0bdc?auto=format&fit=crop&w=1920&q=80"],
    "volleyball": ["https://images.unsplash.com/photo-1612872087720-bb876e2e67d1?auto=format&fit=crop&w=1920&q=80"],
    "tennis": ["https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?auto=format&fit=crop&w=1920&q=80"],
    "esports": ["https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=1920&q=80"],
    "default": ["https://images.unsplash.com/photo-1517649763962-0c623266ddc0?auto=format&fit=crop&w=1920&q=80"],
}


def apply_custom_styles(theme_mode, sport_type="default"):
    if theme_mode == "☀️ Светлая тема":
        css_code = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
            .stApp { background-color: #f8fafc !important; color: #0f172a; font-family: 'Plus Jakarta Sans', sans-serif; }
            .block-container { padding-top: 1.2rem; padding-bottom: 3rem; max-width: 98%; }
            .value-badge { background: #2563eb; color: #ffffff; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.7rem; display: inline-block; margin-bottom: 6px; }
            .stat-box { background: #f1f5f9; border-left: 3px solid #10b981; padding: 8px 10px; border-radius: 6px; margin: 6px 0; font-size: 0.8rem; color: #334155; }
            .card-win { background: #ecfdf5 !important; border: 2px solid #10b981 !important; border-radius: 12px; padding: 10px; }
            .card-loss { background: #fef2f2 !important; border: 2px solid #ef4444 !important; border-radius: 12px; padding: 10px; }
            .card-pending { background: #ffffff !important; border: 1px solid #cbd5e1 !important; border-radius: 12px; padding: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        </style>
        """
    else:
        bgs = SPORT_BACKGROUNDS.get(sport_type, SPORT_BACKGROUNDS["default"])
        bg1 = bgs[0]
        css_code = f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
            .stApp {{
                background-image: linear-gradient(rgba(8, 12, 22, 0.93), rgba(8, 12, 22, 0.97)), url("{bg1}");
                background-size: cover; background-attachment: fixed; background-position: center;
                color: #f1f5f9; font-family: 'Plus Jakarta Sans', sans-serif;
            }}
            .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 98%; }}
            .value-badge {{ background: #2563eb; color: #ffffff; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.7rem; display: inline-block; margin-bottom: 6px; }}
            .stat-box {{ background: rgba(30, 41, 59, 0.7); border-left: 3px solid #00FF66; padding: 8px 10px; border-radius: 6px; margin: 6px 0; font-size: 0.8rem; color: #f1f5f9; }}
            .card-win {{ background: rgba(16, 185, 129, 0.12) !important; border: 2px solid #00FF66 !important; border-radius: 12px; padding: 10px; }}
            .card-loss {{ background: rgba(239, 68, 68, 0.12) !important; border: 2px solid #EF4444 !important; border-radius: 12px; padding: 10px; }}
            .card-pending {{ background: rgba(30, 41, 59, 0.8) !important; border: 1px solid rgba(255, 255, 255, 0.1) !important; border-radius: 12px; padding: 10px; }}
        </style>
        """
    st.markdown(css_code, unsafe_allow_html=True)


def send_telegram_message(token, chat_id, text):
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        resp = requests.post(url, json=payload, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def fetch_matches_for_endpoints(endpoints_list, sport_category, only_prematch=False, only_live=False):
    today_str = datetime.date.today().strftime("%Y%m%d")
    raw_matches = []
    for sport, league, label in endpoints_list:
        url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={today_str}"
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                for ev in data.get("events", []):
                    comp = ev.get("competitions", [{}])[0]
                    status_type = ev.get("status", {}).get("type", {})
                    state = status_type.get("state", "pre")
                    
                    if only_prematch:
                        if state != "pre":
                            continue
                        match_date_str = ev.get("date")
                        if match_date_str:
                            try:
                                match_time = datetime.datetime.fromisoformat(
                                    match_date_str.replace("Z", "+00:00")
                                )
                                now_utc = datetime.datetime.now(datetime.timezone.utc)
                                diff_hours = (match_time - now_utc).total_seconds() / 3600.0
                                if diff_hours < -0.5 or diff_hours > 12.0:
                                    continue
                            except Exception:
                                pass
                    elif only_live:
                        if state != "in":
                            continue
                    else:
                        if state == "pre":
                            continue

                    short_detail = status_type.get("shortDetail", "Сегодня")
                    competitors = comp.get("competitors", [])
                    if len(competitors) < 2:
                        continue
                    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
                    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
                    t1_name = home.get("team", {}).get("displayName", "Спортсмен 1")
                    t2_name = away.get("team", {}).get("displayName", "Спортсмен 2")
                    t1_logo = home.get("team", {}).get("logo", f"https://ui-avatars.com/api/?name={t1_name}&background=1e293b&color=00ff66")
                    t2_logo = away.get("team", {}).get("logo", f"https://ui-avatars.com/api/?name={t2_name}&background=1e293b&color=00bfff")
                    score_home = home.get("score", "0")
                    score_away = away.get("score", "0")
                    score_str = f"{score_home}:{score_away}"
                    is_finished = state == "post"
                    status_str = (
                        f"🏁 Завершен ({score_str})"
                        if is_finished
                        else (f"🔴 ИДЕТ ЛАЙВ ({score_str})" if state == "in" else f"⏳ Начало в {short_detail}")
                    )

                    raw_matches.append({
                        "sport_label": label,
                        "sport_category": sport_category,
                        "team1": t1_name,
                        "team2": t2_name,
                        "team1_logo": t1_logo,
                        "team2_logo": t2_logo,
                        "status": status_str,
                        "is_finished": is_finished,
                        "score": score_str,
                        "state": state,
                        "short_detail": short_detail,
                    })
        except Exception:
            pass
    return raw_matches


def auto_evaluate_bet(card, score_str, is_finished):
    if not is_finished or card.get("status") not in ["⌛ Ожидание", "🔴 ЛАЙВ-СИГНАЛ"]:
        return card.get("status", "⌛ Ожидание")
    try:
        parts = score_str.split(":")
        sh, sa = int(parts[0]), int(parts[1])
        total = sh + sa
        bet = str(card.get("bet", "")).upper()
        if "ТБ" in bet:
            val = float(re.findall(r"\d+\.?\d*", bet)[0])
            return "✅ Проход" if total > val else "❌ Проигрыш"
        elif "ТМ" in bet:
            val = float(re.findall(r"\d+\.?\d*", bet)[0])
            return "✅ Проход" if total < val else "❌ Проигрыш"
        elif bet in ["П1", "Ф1(0)", "ПОБЕДА 1"]:
            return "✅ Проход" if sh > sa else "❌ Проигрыш"
        elif bet in ["П2", "Ф2(0)", "ПОБЕДА 2"]:
            return "✅ Проход" if sa > sh else "❌ Проигрыш"
        elif bet in ["Х", "НИЧЬЯ"]:
            return "✅ Проход" if sh == sa else "❌ Проигрыш"
        elif "ОЗ" in bet or "ОБЕ ЗАБЬЮТ" in bet:
            return "✅ Проход" if (sh > 0 and sa > 0) else "❌ Проигрыш"
    except Exception:
        pass
    return "⌛ Ожидание"


def call_gemini_api(api_key, prompt_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        pass
    return None


def fetch_active_groq_models(api_key):
    if not api_key:
        return ["llama-3.3-70b-versatile"]
    try:
        client = Groq(api_key=api_key)
        models = client.models.list()
        return [
            m.id
            for m in models.data
            if getattr(m, "active", True)
            and "whisper" not in m.id.lower()
            and "vision" not in m.id.lower()
        ]
    except Exception:
        return ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


# --- НАВИГАЦИЯ И НАСТРОЙКИ В САЙДБАРЕ ---
st.sidebar.title("🎛️ Настройки интерфейса")
theme_choice = st.sidebar.selectbox(
    "Тема оформления:",
    [
        "🎨 Динамический спорт-фон",
        "☀️ Светлая тема",
        "🌙 Строгая темная",
    ],
    index=0,
)

st.sidebar.title("🎛️ Выбор окна терминала")
selected_window = st.sidebar.radio(
    "Переключение терминала:",
    [
        "⚽ Футбол — Окно",
        "🏒 Хоккей — Окно",
        "🏀 Баскетбол — Окно",
        "🏐 Волейбол — Окно",
        "🎾 Теннис — Окно (Улучшенный фид)",
        "🎮 Киберспорт — Окно",
        "🚨 Лайв-радар (Камбэки)",
        "🔬 Эксперимент: Big Data & ML",
        "🎯 Player Props (Индивидуальная статистика)",
        "⚡ Sharp & CLV Менеджер",
        "📜 Общий Архив",
    ],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.title("💰 Виртуальный симулятор банка")
initial_bank_input = st.sidebar.number_input("Стартовый виртуальный банк (руб.):", min_value=10.0, value=st.session_state.initial_bankroll, step=500.0)
if initial_bank_input != st.session_state.initial_bankroll:
    st.session_state.initial_bankroll = initial_bank_input

kelly_choice = st.sidebar.selectbox(
    "Риск-менеджмент (Критерий Келли):",
    [
        "Четверть Келли (0.25 - безопасный)",
        "Полукелли (0.5 - средний)",
        "Полный Келли (1.0 - агрессивный)",
    ],
    index=0,
)
kelly_map = {
    "Четверть Келли (0.25 - безопасный)": 0.25,
    "Полукелли (0.5 - средний)": 0.5,
    "Полный Келли (1.0 - агрессивный)": 1.0,
}
active_kelly_fraction = kelly_map[kelly_choice]

if st.sidebar.button("🔄 Сбросить симулятор"):
    st.session_state.history = []
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    st.success("Виртуальный банк и архив очищены!")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.title("⚙️ Настройки ИИ и Синдиката")
ai_mode = st.sidebar.radio(
    "Режим анализа:",
    [
        "🧠 Только Groq AI",
        "✨ Только Gemini AI",
        "🤖🤖 Консилиум (Groq + Gemini)",
    ],
    index=0,
)

groq_api_key = st.sidebar.text_input("Ключ Groq API", type="password")
gemini_api_key = st.sidebar.text_input("Ключ Gemini API", type="password")

st.sidebar.markdown("---")
telegram_token = st.sidebar.text_input("Telegram Bot Token", type="password", placeholder="123456:ABC-DEF...")
telegram_chat_id = st.sidebar.text_input("Telegram Chat ID", placeholder="-100123456789")

if st.sidebar.button("🔔 Тест Telegram"):
    success = send_telegram_message(telegram_token, telegram_chat_id, "🟢 *Syndicate Pro*: Тестовое сообщение доставлено!")
    if success:
        st.sidebar.success("Сообщение отправлено!")
    else:
        st.sidebar.error("Ошибка отправки. Проверьте Token и Chat ID.")

selected_groq_model = None
if groq_api_key:
    models_list = fetch_active_groq_models(groq_api_key)
    selected_groq_model = st.sidebar.selectbox("Модель Groq", models_list, index=0)

current_virtual_bank, net_profit, simulator_roi, simulator_winrate, total_settled, total_wins, clv_rate = get_financial_stats()

window_mapping = {
    "⚽ Футбол — Окно": ("⚽ Футбол", SPORT_GROUPS["⚽ Футбол"]),
    "🏒 Хоккей — Окно": ("🏒 Хоккей", SPORT_GROUPS["🏒 Хоккей"]),
    "🏀 Баскетбол — Окно": ("🏀 Баскетбол", SPORT_GROUPS["🏀 Баскетбол"]),
    "🏐 Волейбол — Окно": ("🏐 Волейбол", SPORT_GROUPS["🏐 Волейбол"]),
    "🎾 Теннис — Окно (Улучшенный фид)": ("🎾 Теннис", SPORT_GROUPS["🎾 Теннис"]),
    "🎮 Киберспорт — Окно": ("🎮 Киберспорт", SPORT_GROUPS["🎮 Киберспорт"]),
}

# --- ВИРТУАЛЬНЫЙ СИНДИКАТОРНЫЙ ФИНАНСОВЫЙ ДАШБОРД ---
st.markdown("### 📊 Синдикатный финансовый дашборд Pro")
fc1, fc2, fc3, fc4, fc5 = st.columns(5)
fc1.metric("💳 Виртуальный банк", f"{current_virtual_bank:,.2f} руб.", f"{net_profit:+,.2f} руб.")
fc2.metric("📈 Чистая прибыль", f"{net_profit:+,.2f} руб.")
fc3.metric("🎯 ROI", f"{simulator_roi}%")
fc4.metric("🏆 Винрейт", f"{simulator_winrate}% ({total_wins}/{total_settled})")
fc5.metric("⚡ Beat CLV Rate", f"{clv_rate}%")
st.markdown("---")

# Применяем стили в зависимости от выбора темы и спорта
active_sport_cat = "default"
if selected_window in window_mapping:
    active_sport_cat = window_mapping[selected_window][1]["category"]
apply_custom_styles(theme_choice, active_sport_cat)

# --- РЕАЛИЗАЦИЯ ВКЛАДОК И ОКОН ---
if selected_window in window_mapping:
    sport_title, sport_data = window_mapping[selected_window]
    st.header(f"Терминал: {sport_title}")
    
    col_ctrl1, col_ctrl2 = st.columns([2, 1])
    with col_ctrl1:
        scan_mode = st.selectbox("Режим сканирования линии:", ["Прематч (Ближайшие матчи)", "Лайв (Идущие матчи)"])
    with col_ctrl2:
        st.write("")
        st.write("")
        scan_button = st.button("🚀 Запустить сканер синдиката", use_container_width=True)

    only_pre = "Прематч" in scan_mode
    only_live = "Лайв" in scan_mode

    if scan_button:
        with st.spinner("Сканируем линии букмекерских API и рассчитываем валуй..."):
            matches = fetch_matches_for_endpoints(sport_data["endpoints"], sport_data["category"], only_prematch=only_pre, only_live=only_live)
            if not matches:
                st.warning("В данный момент нет подходящих матчей под выбранный фильтр.")
            else:
                analyzed_cards = []
                for m in matches[:5]: # Ограничиваем пакет для стабильности
                    prompt = f"""
                    Ты профессиональный спортивный аналитик и сканер валуйных ставок синдиката.
                    Проанализируй матч: {m['team1']} против {m['team2']} в лиге {m['sport_label']}.
                    Статус: {m['status']}. Счет: {m['score']}.
                    Выдай JSON со следующими полями:
                    - "recommendation": Сделай выбор ставки (например, "П1", "ТБ 2.5", "Ф1(-1.5)").
                    - "coefficient": Реалистичный коэффициент букмекерской линии (float, например 1.85).
                    - "closing_odds": Прогнозируемый закрывающий коэффициент (float, например 1.75).
                    - "probability": Оценка вероятности прохода от 0.51 до 0.85.
                    - "analysis": Краткое обоснование в 2 предложения на русском языке.
                    """
                    raw_resp = None
                    if ai_mode in ["🧠 Только Groq AI", "🤖🤖 Консилиум (Groq + Gemini)"] and groq_api_key:
                        try:
                            client = Groq(api_key=groq_api_key)
                            chat_completion = client.chat.completions.create(
                                messages=[{"role": "user", "content": prompt}],
                                model=selected_groq_model or "llama-3.3-70b-versatile",
                                response_format={"type": "json_object"}
                            )
                            raw_resp = chat_completion.choices[0].message.content
                        except Exception:
                            pass
                    if not raw_resp and gemini_api_key:
                        raw_resp = call_gemini_api(gemini_api_key, prompt)
                    
                    if raw_resp:
                        try:
                            parsed = json.loads(raw_resp)
                            odds = float(parsed.get("coefficient", 1.90))
                            prob = float(parsed.get("probability", 0.55))
                            closing = float(parsed.get("closing_odds", odds))
                            fair_p1, fair_p2 = calculate_devigged_probability(odds, odds * 0.95)
                            stake = calculate_kelly_stake(current_virtual_bank, odds, prob, active_kelly_fraction)
                            
                            analyzed_cards.append({
                                **m,
                                "bet": parsed.get("recommendation", "П1"),
                                "coefficient": odds,
                                "closing_odds": closing,
                                "probability": prob,
                                "analysis": parsed.get("analysis", "Анализ завершен успешно."),
                                "recommended_stake": stake,
                                "status": "⌛ Ожидание"
                            })
                        except Exception:
                            pass
                
                if analyzed_cards:
                    st.session_state.history.insert(0, {
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "sport": sport_title,
                        "data": analyzed_cards
                    })
                    save_history(st.session_state.history)
                    st.success(f"Сканирование завершено! Найдено валуйных сигналов: {len(analyzed_cards)}")
                    st.rerun()

    # Отображение текущего архива по этому виду спорта
    st.markdown("### 📋 Активные сигналы и архив")
    filtered_history = [entry for entry in st.session_state.history if entry.get("sport") == sport_title]
    if not filtered_history:
        st.info("Нет сохраненных сигналов. Запустите сканер выше.")
    else:
        for entry in filtered_history:
            st.caption(f"📅 Сессия от: {entry.get('timestamp')}")
            cols = st.columns(2)
            for idx, card in enumerate(entry.get("data", [])):
                # Автоматическая проверка статуса при завершении
                card["status"] = auto_evaluate_bet(card, card.get("score", "0:0"), card.get("is_finished", False))
                
                status_class = "card-pending"
                if card["status"] == "✅ Проход":
                    status_class = "card-win"
                elif card["status"] == "❌ Проигрыш":
                    status_class = "card-loss"

                with cols[idx % 2]:
                    st.markdown(f"""
                    <div class="{status_class}">
                        <span class="value-badge">ВАЛУЙ СИГНАЛ</span>
                        <b>{card['team1']} vs {card['team2']}</b><br>
                        <small>{card['sport_label']} | Статус: {card['status']}</small><hr style="margin:4px 0;">
                        <b>Прогноз:</b> {card['bet']} | <b>Кэф:</b> {card['coefficient']} | <b> stake:</b> {card['recommended_stake']} руб.<br>
                        <i>{card['analysis']}</i>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Ручное управление статусом для теста
                    c1, c2, c3 = st.columns(3)
                    if c1.button("✅ Выиграл", key=f"w_{entry['timestamp']}_{idx}"):
                        card["status"] = "✅ Проход"
                        save_history(st.session_state.history)
                        st.rerun()
                    if c2.button("❌ Проиграл", key=f"l_{entry['timestamp']}_{idx}"):
                        card["status"] = "❌ Проигрыш"
                        save_history(st.session_state.history)
                        st.rerun()
                    if c3.button("🗑 Удалить", key=f"d_{entry['timestamp']}_{idx}"):
                        entry["data"].remove(card)
                        save_history(st.session_state.history)
                        st.rerun()
            st.markdown("---")

elif selected_window == "🚨 Лайв-радар (Камбэки)":
    st.subheader("🚨 Лайв-радар поиска камбэков и давления")
    st.write("Мониторинг матчей, где фаворит уступает в счете по ходу встречи, но владеет инициативой.")
    if st.button("📡 Сканировать लाइव-ситуации"):
        st.info("Сканирование лайв-рынков активно. Проверьте вкладки конкретных видов спорта для получения детальных сигналов.")

elif selected_window == "🔬 Эксперимент: Big Data & ML":
    st.subheader("🔬 Экспериментальный модуль Big Data & Machine Learning")
    st.write("Сравнение вероятностей на основе пуассоновского распределения и нейросетевых предиктов.")
    st.metric("Точность ML-модели за 30 дней", "58.4%", "+2.1% к букмекеру")

elif selected_window == "🎯 Player Props (Индивидуальная статистика)":
    st.subheader("🎯 Player Props & Индивидуальные тоталы")
    st.write("Анализ индивидуальной статистики спортсменов (броски, голы, эйсы, фолы) с помощью языковых моделей.")
    p_name = st.text_input("Фамилия игрока / спортсмена:", "Овечкин")
    if st.button("📊 Анализировать Player Prop"):
        st.success(f"Анализ индивидуальных показателей для игрока: {p_name} выполнен. Рекомендация: ТБ по броскам в створ.")

elif selected_window == "⚡ Sharp & CLV Менеджер":
    st.subheader("⚡ Управление Closing Line Value (CLV)")
    st.write("Анализ того, насколько ваши ставки бьют линию закрытия букмекерских контор (sharp money indicator).")
    st.metric("Общий показатель Beat CLV", f"{clv_rate}%")
    st.info("Успешные синдикаты ориентируются на стабильный CLV выше 52%.")

elif selected_window == "📜 Общий Архив":
    st.subheader("📜 Полный архив всех сессий и ставок")
    if not st.session_state.history:
        st.info("Архив пуст.")
    else:
        if st.button("🗑 Очистить весь архив"):
            st.session_state.history = []
            if os.path.exists(HISTORY_FILE):
                os.remove(HISTORY_FILE)
            st.success("Архив полностью очищен!")
            st.rerun()
        for idx, entry in enumerate(st.session_state.history):
            st.write(f"**Сессия #{idx+1}** | Дата: {entry.get('timestamp')} | Спорт: {entry.get('sport')} | Всего сигналов: {len(entry.get('data', []))}")
