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

# БАЗА ДАННЫХ ЛИГ ПО КАТЕГОРИЯМ (ВКЛЮЧАЯ СПЕЦИФИКУ ТЕННИСА)
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
                                # Для тенниса и общих видов расширяем окно до 12 часов, чтобы не пропускать матчи
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

# ==================== ОПЦИЯ 1: TARGET PLAYER PROPS ====================
if selected_window == "🎯 Player Props (Индивидуальная статистика)":
    apply_custom_styles(theme_choice, "default")
    st.title("🎯 Модуль Player Props AI (Индивидуальные тоталы)")
    st.caption("Поиск плюсовых рынков по индивидуальной статистике: эйсы в теннисе, броски игроков в хоккее/футболе, очки в баскетболе")

    prop_sport = st.selectbox("Выберите вид спорта для пропсов:", ["🎾 Теннис (Эйсы / Двойные)", "🏒 Хоккей (Броски в створ / Очки)", "🏀 Баскетбол (Очки / Передачи игроков)"])

    if st.button("🚀 Найти аномалии в Player Props", type="primary", use_container_width=True):
        if ai_mode == "🧠 Только Groq AI" and not groq_api_key:
            st.error("⚠️ Укажите API ключ Groq!")
        else:
            with st.spinner("Сканируем линии индивидуальных тоталов и сопоставляем с личной статистикой игроков..."):
                today_date = datetime.date.today().strftime("%d.%m.%Y")
                prop_prompt = f"""
Сегодня {today_date}. Вид спорта для пропсов: {prop_sport}.
Найди 2 железобетонных события по индивидуальным тоталам игроков (Player Props) с вероятностью от 90% и коэффициентами от 1.70 до 2.10.

Верни СТРОГО JSON формата:
{{
  "matches": [
    {{
      "team1": "Игрок 1 / Команда",
      "team2": "Игрок 2 / Команда",
      "league": "Турнир / Матч",
      "time_status": "Сегодня",
      "bet_type": "Player Prop (Например: Эйсы ТБ 12.5)",
      "bet": "Тотал больше 12.5 эйсов",
      "coefficient": "1.85",
      "closing_odds": "1.75",
      "confidence_percent": 91,
      "value_tag": "🎯 PROPS EV+",
      "x_factor": "Статистическое превосходство игрока на данном покрытии",
      "tactical_summary": "Детальный разбор пропса"
    }}
  ]
}}
"""
                try:
                    if ai_mode == "🧠 Только Groq AI":
                        client = Groq(api_key=groq_api_key)
                        comp = client.chat.completions.create(
                            model=selected_groq_model or "llama-3.3-70b-versatile",
                            messages=[{"role": "user", "content": prop_prompt}],
                            temperature=0.1,
                        )
                        raw_resp = comp.choices[0].message.content
                    else:
                        raw_resp = call_gemini_api(gemini_api_key, prop_prompt)

                    cleaned = re.sub(r"<think>.*?</think>", "", raw_resp, flags=re.DOTALL).strip()
                    json_start = cleaned.find("{")
                    json_end = cleaned.rfind("}") + 1
                    parsed = json.loads(cleaned[json_start:json_end])
                    pm_list = parsed.get("matches", [])

                    if pm_list:
                        for pm in pm_list:
                            pm["team1_logo"] = f"https://ui-avatars.com/api/?name={pm.get('team1')}&background=1e293b&color=00ff66"
                            pm["team2_logo"] = f"https://ui-avatars.com/api/?name={pm.get('team2')}&background=1e293b&color=00bfff"
                            pm["sport_category"] = "props"
                            pm["score"] = "0:0"
                            pm["status"] = "⌛ Ожидание"
                            
                            odds_val = float(pm.get("coefficient", 1.85))
                            prob_val = float(pm.get("confidence_percent", 90)) / 100.0
                            rec_stake = calculate_kelly_stake(current_virtual_bank, odds_val, prob_val, active_kelly_fraction)
                            stake_pct = round((rec_stake / current_virtual_bank) * 100, 1) if current_virtual_bank > 0 else 0
                            pm["recommended_stake"] = rec_stake
                            pm["stake_percentage"] = stake_pct

                        new_entry = {
                            "id": str(time.time()),
                            "date": f"{today_date} (Player Props)",
                            "ai_source": ai_mode,
                            "data": pm_list,
                        }
                        st.session_state.history.insert(0, new_entry)
                        save_history(st.session_state.history)
                        st.success(f"✅ Найдено Player Props сигналов: {len(pm_list)}")
                        st.rerun()
                    else:
                        st.warning("⚠️ Не удалось сформировать пропсы.")
                except Exception as e:
                    st.error(f"Ошибка пропсов: {e}")

    st.markdown("### 📋 Активные Player Props")
    props_history = [e for e in st.session_state.history if "Player Props" in e.get("date", "")]
    if not props_history:
        st.info("Нет активных пропсов. Запустите сканирование выше.")
    else:
        for entry in props_history:
            for idx, card in enumerate(entry.get("data", [])):
                st.markdown(f"<div class='card-pending'>", unsafe_allow_html=True)
                st.markdown(f"<div class='value-badge'>{card.get('value_tag', '🎯 PROPS')}</div>", unsafe_allow_html=True)
                st.write(f"**{card.get('team1')} vs {card.get('team2')}** | {card.get('league')}")
                st.metric(card.get("bet_type"), card.get("bet"), f"Кф {card.get('coefficient')}")
                st.markdown(f"<div class='stat-box'>💡 {card.get('x_factor')}</div>", unsafe_allow_html=True)
                st.write(f"Статус: **{card.get('status')}**")
                
                bc1, bc2, bc3 = st.columns(3)
                if bc1.button("🟢 Проход", key=f"prop_win_{entry['id']}_{idx}", use_container_width=True):
                    card["status"] = "✅ Проход"
                    save_history(st.session_state.history)
                    st.rerun()
                if bc2.button("🔴 Проигрыш", key=f"prop_loss_{entry['id']}_{idx}", use_container_width=True):
                    card["status"] = "❌ Проигрыш"
                    save_history(st.session_state.history)
                    st.rerun()
                if bc3.button("⏳ Сброс", key=f"prop_pend_{entry['id']}_{idx}", use_container_width=True):
                    card["status"] = "⌛ Ожидание"
                    save_history(st.session_state.history)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

# ==================== ОПЦИЯ 2: SHARP & CLV MANAGER ====================
elif selected_window == "⚡ Sharp & CLV Менеджер":
    apply_custom_styles(theme_choice, "default")
    st.title("⚡ Синдикатный менеджер Sharp & CLV")
    st.caption("Анализ маржи (De-vigging), сравнение с Sharp-букмекерами (Pinnacle) и контроль закрывающей линии (Closing Line Value)")

    st.markdown("#### 🧮 Интерактивный калькулятор De-vigging (Истинная вероятность)")
    c_od1 = st.number_input("Коэффициент на П1:", min_value=1.01, value=1.90, step=0.01)
    c_od2 = st.number_input("Коэффициент на П2:", min_value=1.01, value=1.90, step=0.01)
    
    fair_p1, fair_p2 = calculate_devigged_probability(c_od1, c_od2)
    ev1 = round(fair_p1 * c_od1 * 100, 2)
    ev2 = round(fair_p2 * c_od2 * 100, 2)

    sc1, sc2 = st.columns(2)
    with sc1:
        st.markdown(f"<div class='stat-box'><b>Исход 1:</b> Истинная вероятность: <b>{fair_p1*100:.1f}%</b> | Ожидаемый EV: <b>{ev1}%</b></div>", unsafe_allow_html=True)
    with sc2:
        st.markdown(f"<div class='stat-box'><b>Исход 2:</b> Истинная вероятность: <b>{fair_p2*100:.1f}%</b> | Ожидаемый EV: <b>{ev2}%</b></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 📋 Лог качества CLV по всем совершенным ставкам")
    clv_table_data = []
    for entry in st.session_state.history:
        for card in entry.get("data", []):
            if card.get("status") in ["✅ Проход", "❌ Проигрыш"]:
                clv_table_data.append({
                    "Матч": f"{card.get('team1')} vs {card.get('team2')}",
                    "Ставка": card.get("bet"),
                    "Кф входа": card.get("coefficient"),
                    "Кф закрытия (CLV)": card.get("closing_odds", card.get("coefficient")),
                    "Статус": card.get("status")
                })
    if clv_table_data:
        st.table(clv_table_data)
    else:
        st.info("Нет завершенных ставок для анализа CLV.")

# ==================== ОПЦИЯ 3: ЛАЙВ-РАДАР ====================
elif selected_window == "🚨 Лайв-радар (Камбэки)":
    apply_custom_styles(theme_choice, "default")
    st.title("🚨 Лайв-радар: Поиск камбэков фаворитов")
    st.caption("Сканирование матчей в реальном времени: отслеживание фаворитов, проигрывающих по ходу встречи")

    if st.button("🚀 Запустить сканирование Live-радара", type="primary", use_container_width=True):
        if ai_mode == "🧠 Только Groq AI" and not groq_api_key:
            st.error("⚠️ Укажите API ключ Groq!")
        else:
            with st.spinner("Сканируем лайв-линии всех видов спорта..."):
                try:
                    all_live_matches = []
                    for s_name, s_info in SPORT_GROUPS.items():
                        live_items = fetch_matches_for_endpoints(s_info["endpoints"], s_info["category"], only_live=True)
                        for li in live_items:
                            li["sport_group_name"] = s_name
                            all_live_matches.append(li)

                    if not all_live_matches:
                        st.warning("⚠️ В данный момент в лайве нет подходящих матчей.")
                    else:
                        match_lines = [
                            f"{idx+1}. [{lm['sport_group_name']}] {lm['team1']} VS {lm['team2']} | Счет: {lm['score']} | {lm['status']}"
                            for idx, lm in enumerate(all_live_matches[:25])
                        ]
                        context_text = "АКТУАЛЬНЫЕ МАТЧИ В РЕАЛЬНОМ ВРЕМЕНИ (LIVE):\n" + "\n".join(match_lines)
                        today_date = datetime.date.today().strftime("%d.%m.%Y")
                        current_time = datetime.datetime.now().strftime("%H:%M")

                        live_prompt = f"""
Сегодня {today_date}, время {current_time}.
{context_text}
Проанализируй текущий лайв-счет. Найди 1-2 матча, где фаворит проигрывает, но имеет шанс на камбэк. Коэффициент от 1.60 до 2.50.
Верни СТРОГО JSON формата:
{{
  "matches": [
    {{
      "team1": "Команда 1",
      "team2": "Команда 2",
      "league": "Лига",
      "time_status": "Лайв",
      "bet_type": "Маркет Камбэк",
      "bet": "П1 с учетом камбэка",
      "coefficient": "1.95",
      "closing_odds": "1.85",
      "confidence_percent": 88,
      "value_tag": "🚨 КАМБЭК",
      "x_factor": "Фаворит уступает в счете, но доминирует",
      "tactical_summary": "Разбор"
    }}
  ]
}}
"""
                        if ai_mode == "🧠 Только Groq AI":
                            client = Groq(api_key=groq_api_key)
                            comp = client.chat.completions.create(
                                model=selected_groq_model or "llama-3.3-70b-versatile",
                                messages=[{"role": "user", "content": live_prompt}],
                                temperature=0.1,
                            )
                            raw_response = comp.choices[0].message.content
                        else:
                            raw_response = call_gemini_api(gemini_api_key, live_prompt)

                        if raw_response:
                            cleaned = re.sub(r"<think>.*?</think>", "", raw_response, flags=re.DOTALL).strip()
                            json_start = cleaned.find("{")
                            json_end = cleaned.rfind("}") + 1
                            parsed_json = json.loads(cleaned[json_start:json_end])
                            parsed_matches = parsed_json.get("matches", [])

                            if parsed_matches:
                                for pm in parsed_matches:
                                    t1 = pm.get("team1", "")
                                    match_found = next((m for m in all_live_matches if t1.lower() in m["team1"].lower()), None)
                                    if match_found:
                                        pm["team1_logo"] = match_found["team1_logo"]
                                        pm["team2_logo"] = match_found["team2_logo"]
                                        pm["score"] = match_found["score"]
                                        pm["league"] = match_found["sport_label"]
                                    else:
                                        pm["team1_logo"] = f"https://ui-avatars.com/api/?name={t1}&background=1e293b&color=00ff66"
                                        pm["team2_logo"] = f"https://ui-avatars.com/api/?name=Team2&background=1e293b&color=00bfff"
                                        pm["score"] = "0:0"

                                    pm["status"] = "🔴 ЛАЙВ-СИГНАЛ"
                                    odds_val = float(pm.get("coefficient", 1.85))
                                    prob_val = float(pm.get("confidence_percent", 85)) / 100.0
                                    rec_stake = calculate_kelly_stake(current_virtual_bank, odds_val, prob_val, active_kelly_fraction)
                                    pm["recommended_stake"] = rec_stake
                                    pm["stake_percentage"] = round((rec_stake / current_virtual_bank) * 100, 1) if current_virtual_bank > 0 else 0

                                new_entry = {
                                    "id": str(time.time()),
                                    "date": f"{today_date} {current_time} (Лайв-радар)",
                                    "ai_source": ai_mode,
                                    "data": parsed_matches,
                                }
                                st.session_state.history.insert(0, new_entry)
                                save_history(st.session_state.history)
                                st.success(f"✅ Найдено лайв-сигналов: {len(parsed_matches)}")
                                st.rerun()
                except Exception as e:
                    st.error(f"Ошибка лайв-радара: {e}")

    st.markdown("### 📋 Активные сигналы Лайв-радара")
    live_history = [e for e in st.session_state.history if "Лайв-радар" in e.get("date", "")]
    if not live_history:
        st.info("Нет активных сигналов лайв-радара.")
    else:
        for entry in live_history:
            for idx, card in enumerate(entry.get("data", [])):
                st.markdown(f"<div class='card-pending'>", unsafe_allow_html=True)
                st.markdown(f"<div class='value-badge'>{card.get('value_tag', '🚨 КАМБЭК')}</div>", unsafe_allow_html=True)
                st.write(f"**{card.get('team1')} vs {card.get('team2')}** (Счет: {card.get('score')})")
                st.metric(card.get("bet_type"), card.get("bet"), f"Кф {card.get('coefficient')}")
                st.write(f"Статус: **{card.get('status')}**")
                lc1, lc2, lc3 = st.columns(3)
                if lc1.button("🟢 Проход", key=f"live_win_{entry['id']}_{idx}", use_container_width=True):
                    card["status"] = "✅ Проход"
                    save_history(st.session_state.history)
                    st.rerun()
                if lc2.button("🔴 Проигрыш", key=f"live_loss_{entry['id']}_{idx}", use_container_width=True):
                    card["status"] = "❌ Проигрыш"
                    save_history(st.session_state.history)
                    st.rerun()
                if lc3.button("⏳ Сброс", key=f"live_pend_{entry['id']}_{idx}", use_container_width=True):
                    card["status"] = "🔴 ЛАЙВ-СИГНАЛ"
                    save_history(st.session_state.history)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

# ==================== ОПЦИЯ 4: BIG DATA & ML ====================
elif selected_window == "🔬 Эксперимент: Big Data & ML":
    apply_custom_styles(theme_choice, "default")
    st.title("🔬 Лаборатория Big Data & Машинного обучения")
    st.caption("Глобальный кросс-дисциплинарный анализ с обучением на всей истории побед и поражений")

    historical_wins_list = []
    historical_losses_list = []
    for entry in st.session_state.history:
        for card in entry.get("data", []):
            st_val = card.get("status")
            if st_val == "✅ Проход":
                historical_wins_list.append(f"- Успех: {card.get('team1')} vs {card.get('team2')} | {card.get('bet')}")
            elif st_val == "❌ Проигрыш":
                historical_losses_list.append(f"- Провал: {card.get('team1')} vs {card.get('team2')} | {card.get('bet')}")

    st.markdown(f"🧠 **Датасет в памяти:** Успехов: `{len(historical_wins_list)}` | Ошибок для фильтрации: `{len(historical_losses_list)}`")

    if st.button("🚀 Запустить Big Data Сводный Анализ", type="primary", use_container_width=True):
        if ai_mode == "🧠 Только Groq AI" and not groq_api_key:
            st.error("⚠️ Укажите API ключ Groq!")
        else:
            with st.spinner("Агрегируем матчи со всех видов спорта через нейро-фильтр..."):
                try:
                    all_matches_pool = []
                    for s_name, s_info in SPORT_GROUPS.items():
                        matches_sub = fetch_matches_for_endpoints(s_info["endpoints"], s_info["category"], only_prematch=True)
                        for ms in matches_sub:
                            ms["sport_group_name"] = s_name
                            all_matches_pool.append(ms)

                    if not all_matches_pool:
                        st.warning("⚠️ Нет доступных прематч-матчей в линии.")
                    else:
                        match_lines = [
                            f"{idx+1}. [{m['sport_group_name']}] {m['team1']} VS {m['team2']}"
                            for idx, m in enumerate(all_matches_pool[:50])
                        ]
                        context_text = "ГЛОБАЛЬНЫЙ ПУЛ МАТЧЕЙ:\n" + "\n".join(match_lines)
                        wins_str = "\n".join(historical_wins_list[-10:]) if historical_wins_list else "Нет данных."
                        losses_str = "\n".join(historical_losses_list[-10:]) if historical_losses_list else "Нет данных."
                        today_date = datetime.date.today().strftime("%d.%m.%Y")

                        bigdata_prompt = f"""
Сегодня {today_date}.
{context_text}
Успешные паттерны: {wins_str}
Ошибки (избегать): {losses_str}

Выбери топ-4 железобетонных события с уверенностью от 90% и Кф от 1.50 до 2.10.
Верни СТРОГО JSON формата:
{{
  "matches": [
    {{
      "team1": "Команда 1",
      "team2": "Команда 2",
      "league": "Лига",
      "time_status": "Сегодня",
      "bet_type": "Маркет",
      "bet": "Ставка",
      "coefficient": "1.85",
      "closing_odds": "1.75",
      "confidence_percent": 92,
      "value_tag": "💎 BIG DATA",
      "x_factor": "Обоснование",
      "tactical_summary": "Разбор"
    }}
  ]
}}
"""
                        if ai_mode == "🧠 Только Groq AI":
                            client = Groq(api_key=groq_api_key)
                            comp = client.chat.completions.create(
                                model=selected_groq_model or "llama-3.3-70b-versatile",
                                messages=[{"role": "user", "content": bigdata_prompt}],
                                temperature=0.1,
                            )
                            raw_response = comp.choices[0].message.content
                        else:
                            raw_response = call_gemini_api(gemini_api_key, bigdata_prompt)

                        if raw_response:
                            cleaned = re.sub(r"<think>.*?</think>", "", raw_response, flags=re.DOTALL).strip()
                            json_start = cleaned.find("{")
                            json_end = cleaned.rfind("}") + 1
                            parsed_json = json.loads(cleaned[json_start:json_end])
                            parsed_matches = parsed_json.get("matches", [])

                            if parsed_matches:
                                for pm in parsed_matches:
                                    t1 = pm.get("team1", "")
                                    match_found = next((m for m in all_matches_pool if t1.lower() in m["team1"].lower()), None)
                                    if match_found:
                                        pm["team1_logo"] = match_found["team1_logo"]
                                        pm["team2_logo"] = match_found["team2_logo"]
                                        pm["league"] = match_found["sport_label"]
                                    else:
                                        pm["team1_logo"] = f"https://ui-avatars.com/api/?name={t1}&background=1e293b&color=00ff66"
                                        pm["team2_logo"] = f"https://ui-avatars.com/api/?name=Team2&background=1e293b&color=00bfff"

                                    pm["score"] = "0:0"
                                    pm["status"] = "⌛ Ожидание"
                                    odds_val = float(pm.get("coefficient", 1.85))
                                    prob_val = float(pm.get("confidence_percent", 90)) / 100.0
                                    rec_stake = calculate_kelly_stake(current_virtual_bank, odds_val, prob_val, active_kelly_fraction)
                                    pm["recommended_stake"] = rec_stake
                                    pm["stake_percentage"] = round((rec_stake / current_virtual_bank) * 100, 1) if current_virtual_bank > 0 else 0

                                new_entry = {
                                    "id": str(time.time()),
                                    "date": f"{today_date} (Big Data Lab)",
                                    "ai_source": ai_mode,
                                    "data": parsed_matches,
                                }
                                st.session_state.history.insert(0, new_entry)
                                save_history(st.session_state.history)
                                st.success(f"✅ Найдено Big Data сигналов: {len(parsed_matches)}")
                                st.rerun()
                except Exception as e:
                    st.error(f"Ошибка Big Data: {e}")

    st.markdown("### 📋 Результаты Big Data лаборатории")
    bigdata_history = [e for e in st.session_state.history if "Big Data" in e.get("date", "")]
    if not bigdata_history:
        st.info("В лаборатории нет запущенных сессий.")
    else:
        for entry in bigdata_history:
            cols = st.columns(3)
            for idx, card in enumerate(entry.get("data", [])):
                with cols[idx % 3]:
                    st_val = card.get("status", "⌛ Ожидание")
                    card_class = "card-win" if st_val == "✅ Проход" else ("card-loss" if st_val == "❌ Проигрыш" else "card-pending")
                    st.markdown(f"<div class='{card_class}'>", unsafe_allow_html=True)
                    st.markdown(f"<div class='value-badge'>{card.get('value_tag', '🔬 BIG DATA')}</div>", unsafe_allow_html=True)
                    st.write(f"**{card.get('team1')} vs {card.get('team2')}**")
                    st.metric(card.get("bet_type"), card.get("bet"), f"Кф {card.get('coefficient')}")
                    st.write(f"Статус: **{st_val}**")
                    bc1, bc2, bc3 = st.columns(3)
                    if bc1.button("🟢", key=f"bd_win_{entry['id']}_{idx}", use_container_width=True):
                        card["status"] = "✅ Проход"
                        save_history(st.session_state.history)
                        st.rerun()
                    if bc2.button("🔴", key=f"bd_loss_{entry['id']}_{idx}", use_container_width=True):
                        card["status"] = "❌ Проигрыш"
                        save_history(st.session_state.history)
                        st.rerun()
                    if bc3.button("⏳", key=f"bd_pend_{entry['id']}_{idx}", use_container_width=True):
                        card["status"] = "⌛ Ожидание"
                        save_history(st.session_state.history)
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

# ==================== ОПЦИЯ 5: СПОРТИВНЫЕ ОКНА И АРХИВ ====================
elif selected_window != "📜 Общий Архив":
    sport_title, sport_data = window_mapping[selected_window]
    current_cat = sport_data["category"]
    current_endpoints = sport_data["endpoints"]
    apply_custom_styles(theme_choice, current_cat)

    filter_key = f"filter_{current_cat}"
    if filter_key not in st.session_state:
        st.session_state[filter_key] = "Все"

    sport_wins, sport_losses = 0, 0
    for entry in st.session_state.history:
        for card in entry.get("data", []):
            if card.get("sport_category") == current_cat:
                st_val = card.get("status", "⌛ Ожидание")
                if st_val == "✅ Проход":
                    sport_wins += 1
                elif st_val == "❌ Проигрыш":
                    sport_losses += 1

    sport_finished = sport_wins + sport_losses
    sport_win_rate = (sport_wins / sport_finished * 100) if sport_finished > 0 else 0.0

    st.title(f"🎯 Терминал: {sport_title}")
    st.caption("Синдикатный отбор с расширенным окном данных и защитой от фильтрации")

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        if st.button(f"📊 Win Rate\n{sport_win_rate:.1f}%", use_container_width=True, key=f"btn_f_all_{current_cat}"):
            st.session_state[filter_key] = "Все"
    with mc2:
        if st.button(f"🟢 Победы\n{sport_wins}", use_container_width=True, key=f"btn_f_win_{current_cat}"):
            st.session_state[filter_key] = "✅ Проход"
    with mc3:
        if st.button(f"🔴 Поражения\n{sport_losses}", use_container_width=True, key=f"btn_f_loss_{current_cat}"):
            st.session_state[filter_key] = "❌ Проигрыш"
    with mc4:
        if st.button("🔄 Проверить итоги", use_container_width=True, key=f"check_btn_{current_cat}"):
            with st.spinner(f"Проверяем результаты в {sport_title}..."):
                finished_matches = fetch_matches_for_endpoints(current_endpoints, current_cat, only_prematch=False)
                settled_count = 0
                for entry in st.session_state.history:
                    for card in entry.get("data", []):
                        if card.get("sport_category") == current_cat:
                            t1 = card.get("team1", "").lower()
                            found = next((m for m in finished_matches if t1 in m["team1"].lower() and m["is_finished"]), None)
                            if found:
                                card["score"] = found["score"]
                                old_status = card.get("status", "⌛ Ожидание")
                                new_status = auto_evaluate_bet(card, found["score"], found["is_finished"])
                                if old_status != new_status:
                                    card["status"] = new_status
                                    settled_count += 1
                save_history(st.session_state.history)
                st.success(f"Обновлено: {settled_count}")
                st.rerun()

    active_f = st.session_state[filter_key]
    st.markdown("---")

    col_scan1, col_scan2 = st.columns([2, 1])
    with col_scan1:
        num_signals = st.slider("Количество сигналов:", 1, 3, 2, key=f"slider_{current_cat}")
    with col_scan2:
        btn_search = st.button(f"🚀 Найти железо в {sport_title}", type="primary", use_container_width=True, key=f"btn_scan_{current_cat}")

    if btn_search:
        if ai_mode == "🧠 Только Groq AI" and not groq_api_key:
            st.error("⚠️ Укажите API ключ Groq!")
        else:
            with st.spinner(f"Анализ матчей в {sport_title} с расширенным фидом..."):
                try:
                    real_matches = fetch_matches_for_endpoints(current_endpoints, current_cat, only_prematch=True)
                    if not real_matches:
                        st.warning(f"⚠️ В данный момент в линии {sport_title} нет активных матчей в рамках временного окна. Попробуйте проверить позже или использовать Big Data.")
                    else:
                        match_lines = [
                            f"{idx+1}. [{rm['sport_label']}] {rm['team1']} VS {rm['team2']} | {rm['status']}"
                            for idx, rm in enumerate(real_matches[:25])
                        ]
                        context_text = f"ДОСТУПНЫЕ МАТЧИ ({sport_title}):\n" + "\n".join(match_lines)
                        today_date = datetime.date.today().strftime("%d.%m.%Y")

                        base_prompt = f"""
Сегодня {today_date}. Вид спорта: {sport_title}
{context_text}

Выбери ТОЛЬКО {num_signals} самых железобетонных события с вероятностью от 90% и коэффициентом от 1.50 до 2.10.
Верни СТРОГО JSON формата:
{{
  "matches": [
    {{
      "team1": "Команда 1",
      "team2": "Команда 2",
      "league": "Лига",
      "time_status": "Сегодня",
      "bet_type": "Маркет",
      "bet": "Ставка",
      "coefficient": "1.85",
      "closing_odds": "1.75",
      "confidence_percent": 92,
      "value_tag": "💎 ЖЕЛЕЗО",
      "x_factor": "Довод",
      "tactical_summary": "Разбор"
    }}
  ]
}}
"""
                        if ai_mode == "🧠 Только Groq AI":
                            client = Groq(api_key=groq_api_key)
                            comp = client.chat.completions.create(
                                model=selected_groq_model or "llama-3.3-70b-versatile",
                                messages=[{"role": "user", "content": base_prompt}],
                                temperature=0.1,
                            )
                            raw_response = comp.choices[0].message.content
                        else:
                            raw_response = call_gemini_api(gemini_api_key, base_prompt)

                        cleaned = re.sub(r"<think>.*?</think>", "", raw_response, flags=re.DOTALL).strip()
                        json_start = cleaned.find("{")
                        json_end = cleaned.rfind("}") + 1
                        parsed_json = json.loads(cleaned[json_start:json_end])
                        parsed_matches = parsed_json.get("matches", [])

                        if parsed_matches:
                            for pm in parsed_matches[:num_signals]:
                                t1 = pm.get("team1", "")
                                match_found = next((rm for rm in real_matches if t1.lower() in rm["team1"].lower()), None)
                                if match_found:
                                    pm["team1_logo"] = match_found["team1_logo"]
                                    pm["team2_logo"] = match_found["team2_logo"]
                                    pm["league"] = match_found["sport_label"]
                                else:
                                    pm["team1_logo"] = f"https://ui-avatars.com/api/?name={t1}&background=1e293b&color=00ff66"
                                    pm["team2_logo"] = f"https://ui-avatars.com/api/?name=Team2&background=1e293b&color=00bfff"

                                pm["sport_category"] = current_cat
                                pm["score"] = "0:0"
                                pm["status"] = "⌛ Ожидание"
                                odds_val = float(pm.get("coefficient", 1.85))
                                prob_val = float(pm.get("confidence_percent", 90)) / 100.0
                                rec_stake = calculate_kelly_stake(current_virtual_bank, odds_val, prob_val, active_kelly_fraction)
                                pm["recommended_stake"] = rec_stake
                                pm["stake_percentage"] = round((rec_stake / current_virtual_bank) * 100, 1) if current_virtual_bank > 0 else 0

                            new_entry = {
                                "id": str(time.time()),
                                "date": f"{today_date} ({sport_title})",
                                "ai_source": ai_mode,
                                "data": parsed_matches[:num_signals],
                            }
                            st.session_state.history.insert(0, new_entry)
                            save_history(st.session_state.history)
                            st.success(f"✅ Успешно отобрано сигналов: {len(parsed_matches[:num_signals])}")
                            st.rerun()
                        else:
                            st.warning("⚠️ ИИ не нашел матчей, удовлетворяющих строгим критериям.")
                except Exception as e:
                    st.error(f"Ошибка отбора: {e}")

    st.markdown("### 📋 Сигналы в окне")
    window_history = []
    for entry in st.session_state.history:
        filtered_cards = [
            c for c in entry.get("data", [])
            if c.get("sport_category") == current_cat and (active_f == "Все" or c.get("status") == active_f)
        ]
        if filtered_cards:
            e_copy = entry.copy()
            e_copy["data"] = filtered_cards
            window_history.append(e_copy)

    if not window_history:
        st.info(f"Нет прогнозов в окне '{sport_title}'.")
    else:
        for entry in window_history:
            cols = st.columns(3)
            for idx, card in enumerate(entry.get("data", [])):
                with cols[idx % 3]:
                    st_val = card.get("status", "⌛ Ожидание")
                    card_class = "card-win" if st_val == "✅ Проход" else ("card-loss" if st_val == "❌ Проигрыш" else "card-pending")
                    st.markdown(f"<div class='{card_class}'>", unsafe_allow_html=True)
                    st.markdown(f"<div class='value-badge'>{card.get('value_tag', '💎 ЖЕЛЕЗО')}</div>", unsafe_allow_html=True)
                    st.write(f"**{card.get('team1')} vs {card.get('team2')}**")
                    st.metric(card.get("bet_type"), card.get("bet"), f"Кф {card.get('coefficient')}")
                    st.write(f"Статус: **{st_val}**")
                    bc1, bc2, bc3 = st.columns(3)
                    if bc1.button("🟢", key=f"win_{entry['id']}_{idx}", use_container_width=True):
                        card["status"] = "✅ Проход"
                        save_history(st.session_state.history)
                        st.rerun()
                    if bc2.button("🔴", key=f"loss_{entry['id']}_{idx}", use_container_width=True):
                        card["status"] = "❌ Проигрыш"
                        save_history(st.session_state.history)
                        st.rerun()
                    if bc3.button("⏳", key=f"pend_{entry['id']}_{idx}", use_container_width=True):
                        card["status"] = "⌛ Ожидание"
                        save_history(st.session_state.history)
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

elif selected_window == "📜 Общий Архив":
    apply_custom_styles(theme_choice, "default")
    st.title("📜 Общий архив всех прогнозов")
    if not st.session_state.history:
        st.info("Архив пуст.")
    else:
        for entry in st.session_state.history:
            h_matches = entry.get("data", [])
            if not h_matches:
                continue
            st.markdown(f"### 📅 Сессия от {entry.get('date')} [{entry.get('ai_source', 'ИИ')}]")
            cols = st.columns(3)
            for idx, card in enumerate(h_matches):
                with cols[idx % 3]:
                    st_val = card.get("status", "⌛ Ожидание")
                    st.markdown(f"<div class='card-pending'>", unsafe_allow_html=True)
                    st.markdown(f"**{card.get('team1')} vs {card.get('team2')}**")
                    st.markdown(f"🎯 `{card.get('bet')}` (Кф `{card.get('coefficient')}`)")
                    st.write(f"Статус: **{st_val}**")
                    hc1, hc2, hc3 = st.columns(3)
                    if hc1.button("🟢", key=f"arch_win_{entry['id']}_{idx}", use_container_width=True):
                        card["status"] = "✅ Проход"
                        save_history(st.session_state.history)
                        st.rerun()
                    if hc2.button("🔴", key=f"arch_loss_{entry['id']}_{idx}", use_container_width=True):
                        card["status"] = "❌ Проигрыш"
                        save_history(st.session_state.history)
                        st.rerun()
                    if hc3.button("⏳", key=f"arch_pend_{entry['id']}_{idx}", use_container_width=True):
                        card["status"] = "⌛ Ожидание"
                        save_history(st.session_state.history)
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("---")
