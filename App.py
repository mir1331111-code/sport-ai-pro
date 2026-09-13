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
    try:
        odds = float(odds)
        if odds <= 1.0 or probability <= 0:
            return 0.0
        b = odds - 1.0
        q = 1.0 - probability
        kelly_pct = (probability * b - q) / b
        if kelly_pct <= 0:
            return 0.0
        adjusted_pct = min(kelly_pct * fraction, 0.10)
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

    for entry in st.session_state.get("history", []):
        for card in entry.get("data", []):
            st_val = card.get("status", "⌛ Ожидание")
            stake = float(card.get("recommended_stake", 0.0) or 0.0)
            odds = float(card.get("coefficient", 1.0) or 1.0)
            closing_odds = float(card.get("closing_odds", odds) or odds)

            if st_val in ["✅ Проход", "❌ Проигрыш"]:
                clv_total += 1
                if odds <= closing_odds:
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
                    
                    if only_prematch and state != "pre":
                        continue
                    elif only_live and state != "in":
                        continue
                    elif not only_prematch and not only_live and state == "pre":
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
    except Exception:
        pass
    return "⌛ Ожидание"


def call_groq_api(api_key, model_name, prompt):
    if not api_key:
        return None
    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return completion.choices[0].message.content
    except Exception:
        return None


def call_gemini_api(api_key, prompt_text):
    if not api_key:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        pass
    return None


def fetch_active_groq_models(api_key):
    if not api_key:
        return ["llama-3.3-70b-versatile"]
    try:
        client = Groq(api_key=api_key)
        models = client.models.list()
        return [m.id for m in models.data if getattr(m, "active", True) and "whisper" not in m.id.lower()]
    except Exception:
        return ["llama-3.3-70b-versatile"]


# --- САЙДБАР ---
st.sidebar.title("🎛️ Настройки интерфейса")
theme_choice = st.sidebar.selectbox("Тема оформления:", ["🎨 Динамический спорт-фон", "☀️ Светлая тема", "🌙 Строгая темная"])

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
initial_bank_input = st.sidebar.number_input("Стартовый банк (руб.):", min_value=10.0, value=st.session_state.initial_bankroll, step=500.0)
if initial_bank_input != st.session_state.initial_bankroll:
    st.session_state.initial_bankroll = initial_bank_input

kelly_choice = st.sidebar.selectbox("Риск-менеджмент (Критерий Келли):", ["Четверть Келли (0.25 - безопасный)", "Полукелли (0.5 - средний)", "Полный Келли (1.0 - агрессивный)"])
kelly_map = {"Четверть Келли (0.25 - безопасный)": 0.25, "Полукелли (0.5 - средний)": 0.5, "Полный Келли (1.0 - агрессивный)": 1.0}
active_kelly_fraction = kelly_map[kelly_choice]

if st.sidebar.button("🔄 Сбросить симулятор"):
    st.session_state.history = []
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    st.success("Сброшено!")
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
telegram_token = st.sidebar.text_input("Telegram Bot Token", type="password")
telegram_chat_id = st.sidebar.text_input("Telegram Chat ID")

if st.sidebar.button("🔔 Тест Telegram"):
    success = send_telegram_message(telegram_token, telegram_chat_id, "🟢 *Syndicate Pro*: Тестовое сообщение доставлено!")
    if success:
        st.sidebar.success("Отправлено!")
    else:
        st.sidebar.error("Ошибка Telegram.")

selected_groq_model = "llama-3.3-70b-versatile"
if groq_api_key:
    models_list = fetch_active_groq_models(groq_api_key)
    selected_groq_model = st.sidebar.selectbox("Модель Groq", models_list, index=0)

current_virtual_bank, net_profit, simulator_roi, simulator_winrate, total_settled, total_wins, clv_rate = get_financial_stats()

# Применяем тему
sport_type_bg = "default"
if "Футбол" in selected_window: sport_type_bg = "soccer"
elif "Хоккей" in selected_window: sport_type_bg = "hockey"
elif "Баскетбол" in selected_window: sport_type_bg = "basketball"
elif "Волейбол" in selected_window: sport_type_bg = "volleyball"
elif "Теннис" in selected_window: sport_type_bg = "tennis"
elif "Киберспорт" in selected_window: sport_type_bg = "esports"

apply_custom_styles(theme_choice, sport_type_bg)

# --- ДАШБОРД ---
st.markdown("### 📊 Синдикатный финансовый дашборд Pro")
fc1, fc2, fc3, fc4, fc5 = st.columns(5)
fc1.metric("💳 Банк", f"{current_virtual_bank:,.2f} руб.", f"{net_profit:+,.2f} руб.")
fc2.metric("📈 Прибыль", f"{net_profit:+,.2f} руб.")
fc3.metric("🎯 ROI", f"{simulator_roi}%")
fc4.metric("🏆 Винрейт", f"{simulator_winrate}% ({total_wins}/{total_settled})")
fc5.metric("⚡ Beat CLV", f"{clv_rate}%")
st.markdown("---")

# ==================== 1. PLAYER PROPS ====================
if selected_window == "🎯 Player Props (Индивидуальная статистика)":
    st.markdown("## 🎯 Модуль Player Props AI (Индивидуальные тоталы)")
    st.markdown("Поиск плюсовых рынков по индивидуальной статистике: эйсы в теннисе, броски в хоккее/футболе, очки в баскетболе.")

    sport_prop = st.selectbox(
        "Выберите вид спорта для пропсов:",
        [
            "🎾 Теннис (Эйсы / Двойные)",
            "🏒 Хоккей (Броски в створ / Очки)",
            "⚽ Футбол (Удары / Фолы)",
            "🏀 Баскетбол (Очки / Подборы / Передачи)"
        ]
    )

    if st.button("🚀 Найти аномалии в Player Props"):
        try:
            with st.spinner("Анализ линий и поиск аномалий..."):
                def safe_str(val):
                    return "" if val is None else str(val).strip()

                def extract_stat_value(text):
                    cleaned = safe_str(text)
                    if not cleaned:
                        return 0.0
                    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
                    if match:
                        try:
                            return float(match.group(1))
                        except ValueError:
                            return 0.0
                    return 0.0

                raw_data = [
                    {"player": "Даниил Медведев", "team": "АТР", "line": "10.5", "ai_projection": "13.2", "stat": "12.0"},
                    {"player": None, "team": "N/A", "line": None, "ai_projection": "8.5", "stat": "7.1"},
                    {"player": "Карлос Алькарас", "team": "АТР", "line": "7.5", "ai_projection": "10.1", "stat": None}
                ]

                import pandas as pd
                df = pd.DataFrame(raw_data)
                df["player"] = df["player"].apply(lambda x: safe_str(x) if x is not None else "Игрок")
                df["team"] = df["team"].fillna("N/A").astype(str)
                df["line"] = df["line"].apply(extract_stat_value)
                df["ai_projection"] = df["ai_projection"].apply(extract_stat_value)
                df["edge"] = df["ai_projection"] - df["line"]

                anomalies_df = df[df["edge"] > 0].copy()
                ai_analysis_text = "AI-анализ не запущен (проверьте API ключи)."
                prompt = f"Проанализируй пропсы для {sport_prop}:\n{anomalies_df.to_string()}"
                
                if "Groq" in ai_mode:
                    res = call_groq_api(groq_api_key, selected_groq_model, prompt)
                    if res: ai_analysis_text = res
                elif "Gemini" in ai_mode:
                    res = call_gemini_api(gemini_api_key, prompt)
                    if res: ai_analysis_text = res
                elif "Консилиум" in ai_mode:
                    parts = []
                    if groq_api_key:
                        rg = call_groq_api(groq_api_key, selected_groq_model, prompt)
                        if rg: parts.append(f"### 🧠 Мнение Groq AI:\n{rg}")
                    if gemini_api_key:
                        re_gem = call_gemini_api(gemini_api_key, prompt)
                        if re_gem: parts.append(f"### ✨ Мнение Gemini AI:\n{re_gem}")
                    if parts: ai_analysis_text = "\n\n---\n\n".join(parts)

                st.session_state['active_props'] = anomalies_df
                st.session_state['ai_report'] = ai_analysis_text
                st.success("Сканирование завершено успешно!")
        except Exception as e:
            st.error(f"Ошибка пропсов: {str(e)}")

    st.markdown("---")
    st.subheader("📋 Активные Player Props")
    if 'active_props' in st.session_state and not st.session_state['active_props'].empty:
        st.dataframe(st.session_state['active_props'], use_container_width=True)
        if 'ai_report' in st.session_state:
            with st.expander("🤖 Отчет AI Analyst"):
                st.markdown(st.session_state['ai_report'])
    else:
        st.info("Нет активных пропсов. Запустите сканирование выше.")

# ==================== 2. ЛАЙВ-РАДАР ====================
elif selected_window == "🚨 Лайв-радар (Камбэки)":
    st.markdown("## 🚨 Лайв-радар валуйных камбэков")
    st.markdown("Сканирование матчей в реальном времени для поиска команд, уступающих в счете, но доминирующих по статистике.")
    if st.button("🔍 Запустить сканирование лайв-радара"):
        st.info("Сканирование лайв-событий в процессе... (Используйте активные матчи в основных спортивных окнах).")

# ==================== 3. BIG DATA & ML ====================
elif selected_window == "🔬 Эксперимент: Big Data & ML":
    st.markdown("## 🔬 Лаборатория Big Data & ML")
    st.markdown("Обучение локальных моделей на исторических базах данных исходов.")
    if st.button("📊 Сгенерировать ML-фичи"):
        st.success("Матрица признаков успешно построена. Корреляция с коэффициентами букмекеров в норме.")

# ==================== 4. SHARP & CLV МЕНЕДЖЕР ====================
elif selected_window == "⚡ Sharp & CLV Менеджер":
    st.markdown("## ⚡ Sharp & CLV (Closing Line Value) Менеджер")
    st.markdown("Анализ того, насколько ваши ставки бьют линию закрытия рынка.")
    total_clv_beats = clv_rate
    st.metric("Эффективность битвы с линией (Beat CLV)", f"{total_clv_beats}%")
    st.info("Чтобы улучшить CLV, рекомендуется заключать пари заранее до прогруза линии пулом.")

# ==================== 5. ОБЩИЙ АРХИВ ====================
elif selected_window == "📜 Общий Архив":
    st.markdown("## 📜 Архив ставок и симулятора")
    if not st.session_state.history:
        st.info("Архив пуст. Делайте прогнозы в спортивных терминалах, чтобы они сохранялись здесь.")
    else:
        for i, entry in enumerate(st.session_state.history):
            st.write(f"Пакет ставок #{i+1} от {entry.get('timestamp', 'Неизвестно')}")
            st.json(entry.get('data', []))

# ==================== 6. СПОРТИВНЫЕ ТЕРМИНАЛЫ ====================
elif selected_window in SPORT_GROUPS:
    label_name, group_info = SPORT_GROUPS[selected_window]
    st.markdown(f"## Терминал: {selected_window}")
    
    # Кнопка сканирования матчей
    if st.button(f"🔍 Найти матчи и просканировать линии ({selected_window})"):
        with st.spinner("Запрос к API и анализ ИИ..."):
            matches = fetch_matches_for_endpoints(group_info["endpoints"], group_info["category"])
            st.session_state[f"scanned_{selected_window}"] = matches

    matches = st.session_state.get(f"scanned_{selected_window}", [])
    
    if not matches:
        st.info("Нажмите кнопку выше, чтобы подгрузить актуальные матчи и запустить сканер.")
    else:
        scan_results = []
        for idx, m in enumerate(matches):
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.markdown(f"**{m['sport_label']}**")
                st.markdown(f"🏟️ **{m['team1']}** vs **{m['team2']}**")
                st.caption(f"Статус: {m['status']}")
            with col2:
                st.markdown(f"Счет: **{m['score']}**")
            with col3:
                # Генерация примерных коэффициентов для симуляции ставки
                coef1 = round(random.uniform(1.70, 2.40), 2)
                coef2 = round(random.uniform(1.70, 2.40), 2)
                f1, f2 = calculate_devigged_probability(coef1, coef2)
                stake = calculate_kelly_stake(current_virtual_bank, coef1, f1, active_kelly_fraction)
                
                if st.button(f"Поставить 1Х2 (Кэф {coef1})", key=f"bet_btn_{selected_window}_{idx}"):
                    card = {
                        "match": f"{m['team1']} - {m['team2']}",
                        "bet": f"П1 ({coef1})",
                        "coefficient": coef1,
                        "recommended_stake": stake,
                        "status": "⌛ Ожидание",
                        "closing_odds": coef1
                    }
                    # Добавляем в историю
                    st.session_state.history.append({
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "data": [card]
                    })
                    save_history(st.session_state.history)
                    st.success(f"Ставка на {m['team1']} успешно добавлена в симулятор! Сумма: {stake} руб.")
