import datetime
import json
import os
import random
import re
import time
import requests
import streamlit as st
from groq import Groq

HISTORY_FILE = "match_history.json"


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


st.set_page_config(
    page_title="Auto-Sniper: Sport Terminals", page_icon="🎯", layout="wide"
)

if "history" not in st.session_state:
    st.session_state.history = load_history()

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
            ("soccer", "usa.1", "MLS (США)"),
        ],
    },
    "🏒 Хоккей": {
        "category": "hockey",
        "endpoints": [
            ("hockey", "nhl", "НХЛ (США/Канада)"),
            ("hockey", "khl", "КХЛ (Россия/Европа)"),
            ("hockey", "vhl", "ВХЛ (Россия)"),
            ("hockey", "mhl", "МХЛ (Россия)"),
            ("hockey", "shl", "Шведская лига (SHL)"),
        ],
    },
    "🏀 Баскетбол": {
        "category": "basketball",
        "endpoints": [
            ("basketball", "nba", "НБА (США)"),
            ("basketball", "mens-college-basketball", "NCAA Баскетбол (США)"),
            ("basketball", "euroleague", "Евролига (Европа)"),
            ("basketball", "russia.1", "Единая лига ВТБ (Россия)"),
        ],
    },
    "🏐 Волейбол": {
        "category": "volleyball",
        "endpoints": [
            ("volleyball", "volleyball", "Волейбол (Международный)"),
            (
                "volleyball",
                "womens-college-volleyball",
                "NCAA Волейбол (Женщины)",
            ),
            (
                "volleyball",
                "mens-college-volleyball",
                "NCAA Волейбол (Мужчины)",
            ),
        ],
    },
    "🎾 Теннис": {
        "category": "tennis",
        "endpoints": [
            ("tennis", "atp", "ATP Теннис"),
            ("tennis", "wta", "WTA Теннис"),
        ],
    },
}

# ДИНАМИЧЕСКИЕ НАБОРЫ ФОНОВ (Стадион -> Игрок -> Мяч/Момент)
SPORT_BACKGROUNDS = {
    "soccer": [
        "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80",  # Стадион
        "https://images.unsplash.com/photo-1574629810360-7efbbe195018?auto=format&fit=crop&w=1920&q=80",  # Игрок
        "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?auto=format&fit=crop&w=1920&q=80",  # Мяч
    ],
    "basketball": [
        "https://images.unsplash.com/photo-1546519638-68e109498ffc?auto=format&fit=crop&w=1920&q=80",  # Арена
        "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80",  # Игрок
        "https://images.unsplash.com/photo-1574623452334-1e0ac2bbfccb?auto=format&fit=crop&w=1920&q=80",  # Мяч
    ],
    "hockey": [
        "https://images.unsplash.com/photo-1580748141549-71748dbe0bdc?auto=format&fit=crop&w=1920&q=80",  # Арена
        "https://images.unsplash.com/photo-1515703407324-5f753ff420b8?auto=format&fit=crop&w=1920&q=80",  # Игрок
        "https://images.unsplash.com/photo-1529900748604-07564a03e7a6?auto=format&fit=crop&w=1920&q=80",  # Шайба/Клюшка
    ],
    "volleyball": [
        "https://images.unsplash.com/photo-1612872087720-bb876e2e67d1?auto=format&fit=crop&w=1920&q=80",
        "https://images.unsplash.com/photo-1593341646782-e0b495cffc6d?auto=format&fit=crop&w=1920&q=80",
    ],
    "tennis": [
        "https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?auto=format&fit=crop&w=1920&q=80",
        "https://images.unsplash.com/photo-1595435934249-5df7ed86e1c0?auto=format&fit=crop&w=1920&q=80",
    ],
    "default": [
        "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?auto=format&fit=crop&w=1920&q=80"
    ],
}


def apply_custom_styles(sport_type="default"):
    bgs = SPORT_BACKGROUNDS.get(sport_type, SPORT_BACKGROUNDS["default"])
    bg1 = bgs[0]
    bg2 = bgs[1 % len(bgs)]
    bg3 = bgs[2 % len(bgs)]

    css_code = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

        @keyframes slideShow {{
            0% {{ background-image: linear-gradient(rgba(8, 12, 22, 0.92), rgba(8, 12, 22, 0.96)), url("{bg1}"); }}
            38% {{ background-image: linear-gradient(rgba(8, 12, 22, 0.92), rgba(8, 12, 22, 0.96)), url("{bg2}"); }}
            72% {{ background-image: linear-gradient(rgba(8, 12, 22, 0.92), rgba(8, 12, 22, 0.96)), url("{bg3}"); }}
            100% {{ background-image: linear-gradient(rgba(8, 12, 22, 0.92), rgba(8, 12, 22, 0.96)), url("{bg1}"); }}
        }}

        .stApp {{
            animation: slideShow 25s infinite ease-in-out;
            background-size: cover;
            background-attachment: fixed;
            background-position: center;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }}
        .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 98%; }}
        
        div[data-testid="stMetric"] {{
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.08);
            padding: 12px 16px;
            border-radius: 12px;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }}
        div[data-testid="stMetricValue"] {{ font-size: 1.4rem; color: #00FF66; font-weight: 800; text-shadow: 0 0 10px rgba(0,255,102,0.3); }}
        div[data-testid="stMetricLabel"] {{ font-size: 0.75rem; opacity: 0.8; text-transform: uppercase; letter-spacing: 0.5px; }}

        .stButton>button {{
            border-radius: 8px;
            font-weight: 700;
            font-size: 0.81rem;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }}
        .stButton>button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,255,102,0.25);
        }}

        .value-badge {{
            background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
            color: #ffffff;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.7rem;
            display: inline-block;
            margin-bottom: 6px;
            box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
        }}
        
        .stat-box {{
            background: rgba(30, 41, 59, 0.6);
            border-left: 3px solid #00FF66;
            padding: 8px 10px;
            border-radius: 6px;
            margin: 6px 0;
            font-size: 0.8rem;
            color: #f1f5f9;
        }}

        /* КАРТОЧКИ ПО СТАТУСАМ */
        .card-win {{
            background: rgba(16, 185, 129, 0.12) !important;
            border: 2px solid #00FF66 !important;
            box-shadow: 0 0 20px rgba(0, 255, 102, 0.3);
            border-radius: 12px;
            padding: 4px;
        }}
        .card-loss {{
            background: rgba(239, 68, 68, 0.12) !important;
            border: 2px solid #EF4444 !important;
            box-shadow: 0 0 20px rgba(239, 68, 68, 0.3);
            border-radius: 12px;
            padding: 4px;
        }}
        .card-pending {{
            background: rgba(30, 41, 59, 0.75) !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 12px;
            padding: 4px;
        }}

        @keyframes goalPulse {{
            0% {{ transform: scale(1); box-shadow: 0 0 0 0 rgba(0, 255, 102, 0.8); }}
            70% {{ transform: scale(1.01); box-shadow: 0 0 0 12px rgba(0, 255, 102, 0); }}
            100% {{ transform: scale(1); box-shadow: 0 0 0 0 rgba(0, 255, 102, 0); }}
        }}
        .goal-highlight {{
            animation: goalPulse 1.5s infinite;
        }}
    </style>
    """
    st.markdown(css_code, unsafe_allow_html=True)


def fetch_matches_for_endpoints(endpoints_list, sport_category, only_prematch=False):
    today_str = datetime.date.today().strftime("%Y%m%d")
    raw_matches = []

    for sport, league, label in endpoints_list:
        url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={today_str}"
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                events = data.get("events", [])

                for ev in events:
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
                                now_utc = datetime.datetime.now(
                                    datetime.timezone.utc
                                )
                                diff_hours = (
                                    match_time - now_utc
                                ).total_seconds() / 3600.0
                                if diff_hours < -0.1 or diff_hours > 1.0:
                                    continue
                            except Exception:
                                pass
                    else:
                        if state == "pre":
                            continue

                    short_detail = status_type.get("shortDetail", "Сегодня")
                    competitors = comp.get("competitors", [])
                    if len(competitors) < 2:
                        continue

                    home = next(
                        (c for c in competitors if c.get("homeAway") == "home"),
                        competitors[0],
                    )
                    away = next(
                        (c for c in competitors if c.get("homeAway") == "away"),
                        competitors[1],
                    )

                    t1_name = home.get("team", {}).get(
                        "displayName", "Команда 1"
                    )
                    t2_name = away.get("team", {}).get(
                        "displayName", "Команда 2"
                    )

                    t1_logo = home.get("team", {}).get(
                        "logo",
                        f"https://ui-avatars.com/api/?name={t1_name}&background=1e293b&color=00ff66",
                    )
                    t2_logo = away.get("team", {}).get(
                        "logo",
                        f"https://ui-avatars.com/api/?name={t2_name}&background=1e293b&color=00bfff",
                    )

                    score_home = home.get("score", "0")
                    score_away = away.get("score", "0")
                    score_str = f"{score_home}:{score_away}"

                    is_finished = state == "post"
                    status_str = (
                        f"🏁 Завершен ({score_str})"
                        if is_finished
                        else f"⏳ Начало в {short_detail}"
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
                        "game_phase": "прематч (до 1 часа)",
                    })
        except Exception:
            pass

    return raw_matches


def auto_evaluate_bet(card, score_str, is_finished):
    if not is_finished or card.get("status") != "⌛ Ожидание":
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
            "temperature": 0.2,
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


# БОКОВАЯ ПАНЕЛЬ НАВИГАЦИИ ПО ОКНАМ
st.sidebar.title("🎛️ Выбор окна спорта")
selected_window = st.sidebar.radio(
    "Переключение терминала:",
    [
        "⚽ Футбол — Окно",
        "🏒 Хоккей — Окно",
        "🏀 Баскетбол — Окно",
        "🏐 Волейбол — Окно",
        "🎾 Теннис — Окно",
        "📜 Общий Архив",
    ],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.title("⚙️ Настройки ИИ")
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

selected_groq_model = None
if groq_api_key:
    models_list = fetch_active_groq_models(groq_api_key)
    selected_groq_model = st.sidebar.selectbox(
        "Модель Groq", models_list, index=0
    )

# ОПРЕДЕЛЕНИЕ ТЕКУЩЕГО КАТЕГОРИЙНОГО ОКНА
window_mapping = {
    "⚽ Футбол — Окно": ("⚽ Футбол", SPORT_GROUPS["⚽ Футбол"]),
    "🏒 Хоккей — Окно": ("🏒 Хоккей", SPORT_GROUPS["🏒 Хоккей"]),
    "🏀 Баскетбол — Окно": ("🏀 Баскетбол", SPORT_GROUPS["🏀 Баскетбол"]),
    "🏐 Волейбол — Окно": ("🏐 Волейбол", SPORT_GROUPS["🏐 Волейбол"]),
    "🎾 Теннис — Окно": ("🎾 Теннис", SPORT_GROUPS["🎾 Теннис"]),
}

if selected_window != "📜 Общий Архив":
    sport_title, sport_data = window_mapping[selected_window]
    current_cat = sport_data["category"]
    current_endpoints = sport_data["endpoints"]
    apply_custom_styles(current_cat)

    # СВОЯ СТАТИСТИКА ДЛЯ ДАННОГО ОКНА СПОРТА
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
    sport_win_rate = (
        (sport_wins / sport_finished * 100) if sport_finished > 0 else 0.0
    )

    st.title(f"🎯 Терминал прематча: {sport_title}")
    st.caption(
        f"Собственная аналитика для {sport_title} (Кф $\\ge$ 1.40 | Уверенность"
        " $\\ge$ 85% | До 1 часа до матча)"
    )

    # МЕТРИКИ ЭТОГО ОКНА
    m_c1, m_c2, m_c3, m_c4 = st.columns(4)
    m_c1.metric("📊 Win Rate в окне", f"{sport_win_rate:.1f}%")
    m_c2.metric("🟢 Победы", f"{sport_wins}")
    m_c3.metric("🔴 Поражения", f"{sport_losses}")

    if m_c4.button(
        "🔄 Проверить итоги окна",
        key=f"check_btn_{current_cat}",
        use_container_width=True,
    ):
        with st.spinner(f"Проверяем результаты матчей в категории {sport_title}..."):
            finished_matches = fetch_matches_for_endpoints(
                current_endpoints, current_cat, only_prematch=False
            )
            settled_count = 0

            for entry in st.session_state.history:
                for card in entry.get("data", []):
                    if card.get("sport_category") == current_cat:
                        t1 = card.get("team1", "").lower()
                        found = next(
                            (
                                m
                                for m in finished_matches
                                if t1 in m["team1"].lower() and m["is_finished"]
                            ),
                            None,
                        )
                        if found:
                            card["score"] = found["score"]
                            card["time_status"] = found["status"]
                            old_status = card.get("status", "⌛ Ожидание")
                            new_status = auto_evaluate_bet(
                                card, found["score"], found["is_finished"]
                            )
                            if old_status != new_status:
                                card["status"] = new_status
                                settled_count += 1

            save_history(st.session_state.history)
            st.success(f"Обновлено статусов в окне: {settled_count}")
            st.rerun()

    st.markdown("---")

    # СКАНИРОВАНИЕ И РУЧНОЙ ВЫБОР ДЛЯ ЭТОГО СПОРТА
    today_date = datetime.date.today().strftime("%d.%m.%Y")
    current_time = datetime.datetime.now().strftime("%H:%M")

    col_scan1, col_scan2 = st.columns([2, 1])
    with col_scan1:
        num_signals = st.slider(
            "Количество прематч-сигналов:", 1, 5, 2, key=f"slider_{current_cat}"
        )
    with col_scan2:
        btn_search = st.button(
            f"🚀 Сканировать {sport_title}",
            type="primary",
            use_container_width=True,
            key=f"btn_scan_{current_cat}",
        )

    if btn_search:
        if ai_mode == "🧠 Только Groq AI" and not groq_api_key:
            st.error("⚠️ Укажите API ключ Groq!")
        elif ai_mode == "✨ Только Gemini AI" and not gemini_api_key:
            st.error("⚠️ Укажите API ключ Gemini!")
        else:
            with st.spinner(
                f"Сканируем линию прематча ({sport_title}) на 1 час вперед..."
            ):
                try:
                    real_matches = fetch_matches_for_endpoints(
                        current_endpoints, current_cat, only_prematch=True
                    )
                    if not real_matches:
                        st.warning(
                            f"⚠️ В данный момент нет матчей в {sport_title} в диапазоне до 1 часа до начала."
                        )
                    else:
                        match_lines = [
                            f"{idx+1}. [{rm['sport_label']}] {rm['team1']} VS {rm['team2']} | {rm['status']}"
                            for idx, rm in enumerate(real_matches[:20])
                        ]
                        context_text = (
                            f"ДОСТУПНЫЕ МАТЧИ ({sport_title}, до 1 часа до начала):\n"
                            + "\n".join(match_lines)
                        )

                        base_prompt = f"""
Сегодня {today_date}, время {current_time} МСК.
Вид спорта: {sport_title}
{context_text}

КРИТЕРИИ ПРЕМАТЧ-АНАЛИЗА:
1. Выбирай только из предложенного списка матчей для {sport_title}.
2. Проанализируй мотивацию, форму и статистику.
3. КОЭФФИЦИЕНТ: строго от 1.40 и выше.
4. УВЕРЕННОСТЬ ИИ: строго от 85% и выше.

Верни СТРОГО JSON формата:
{{
  "matches": [
    {{
      "team1": "Команда 1 / Игрок 1",
      "team2": "Команда 2 / Игрок 2",
      "league": "Лига",
      "time_status": "Время начала",
      "game_phase": "прематч (до 1 часа)",
      "score": "0:0",
      "bet_type": "Маркет",
      "bet": "Ставка",
      "coefficient": "1.85",
      "confidence_percent": 88,
      "value_tag": "💎 Валуй",
      "x_factor": "🔥 Ключевой фактор",
      "tactical_summary": "🧠 Анализ",
      "reason": "Обоснование"
    }}
  ]
}}
"""
                        raw_response = ""
                        if ai_mode == "🧠 Только Groq AI":
                            client = Groq(api_key=groq_api_key)
                            comp = client.chat.completions.create(
                                model=selected_groq_model
                                or "llama-3.3-70b-versatile",
                                messages=[
                                    {"role": "user", "content": base_prompt}
                                ],
                                temperature=0.2,
                            )
                            raw_response = comp.choices[0].message.content
                        elif ai_mode == "✨ Только Gemini AI":
                            raw_response = call_gemini_api(
                                gemini_api_key, base_prompt
                            )
                        else:
                            gemini_raw = call_gemini_api(
                                gemini_api_key, base_prompt
                            )
                            consensus_prompt = (
                                base_prompt
                                + f"\n\nМнение Gemini:\n{gemini_raw}\nСинтезируй финальный JSON!"
                            )
                            client = Groq(api_key=groq_api_key)
                            comp = client.chat.completions.create(
                                model=selected_groq_model
                                or "llama-3.3-70b-versatile",
                                messages=[
                                    {
                                        "role": "user",
                                        "content": consensus_prompt,
                                    }
                                ],
                                temperature=0.2,
                            )
                            raw_response = comp.choices[0].message.content

                        cleaned = re.sub(
                            r"<think>.*?</think>",
                            "",
                            raw_response,
                            flags=re.DOTALL,
                        ).strip()
                        json_start = cleaned.find("{")
                        json_end = cleaned.rfind("}") + 1
                        parsed_json = json.loads(cleaned[json_start:json_end])
                        parsed_matches = parsed_json.get("matches", [])

                        if parsed_matches:
                            for pm in parsed_matches[:num_signals]:
                                if pm.get("confidence_percent", 0) < 85:
                                    pm["confidence_percent"] = 85

                                t1 = pm.get("team1", "")
                                match_found = next(
                                    (
                                        rm
                                        for rm in real_matches
                                        if t1.lower() in rm["team1"].lower()
                                    ),
                                    None,
                                )

                                if match_found:
                                    pm["team1_logo"] = match_found[
                                        "team1_logo"
                                    ]
                                    pm["team2_logo"] = match_found[
                                        "team2_logo"
                                    ]
                                    pm["league"] = match_found["sport_label"]
                                else:
                                    pm["team1_logo"] = (
                                        f"https://ui-avatars.com/api/?name={t1}&background=1e293b&color=00ff66"
                                    )
                                    pm["team2_logo"] = f"https://ui-avatars.com/api/?name=Team2&background=1e293b&color=00bfff"

                                pm["sport_category"] = current_cat
                                pm["score"] = "0:0"
                                pm["game_phase"] = "прематч (до 1 часа)"
                                pm["status"] = "⌛ Ожидание"

                            new_entry = {
                                "id": str(time.time()),
                                "date": f"{today_date} {current_time} ({sport_title})",
                                "ai_source": ai_mode,
                                "data": parsed_matches[:num_signals],
                            }
                            st.session_state.history.insert(0, new_entry)
                            save_history(st.session_state.history)
                            st.success(
                                f"✅ Сканирование для {sport_title} завершено!"
                            )
                            st.rerun()
                        else:
                            st.warning(
                                "⚠️ ИИ не смог сформировать сигнал под заданные фильтры."
                            )
                except Exception as e:
                    st.error(f"Ошибка: {e}")

    st.markdown("### 📋 Активные прематч-прогнозы в окне")

    # ФИЛЬТРУЕМ И ПОКАЗЫВАЕМ ПРОГНОЗЫ ТОЛЬКО ДЛЯ ЭТОГО ВИДА СПОРТА
    window_history = [
        entry
        for entry in st.session_state.history
        if any(
            c.get("sport_category") == current_cat
            for c in entry.get("data", [])
        )
    ]

    if not window_history:
        st.info(
            f"В окне '{sport_title}' пока нет прогнозов. Нажмите кнопку «Сканировать» выше."
        )
    else:
        for entry in window_history:
            filtered_cards = [
                c
                for c in entry.get("data", [])
                if c.get("sport_category") == current_cat
            ]
            if not filtered_cards:
                continue

            st.caption(
                f"Сессия от {entry.get('date')} [{entry.get('ai_source')}]"
            )
            cols = st.columns(3)
            for idx, card in enumerate(filtered_cards):
                col_idx = idx % 3
                with cols[col_idx]:
                    st_val = card.get("status", "⌛ Ожидание")
                    
                    # Выбираем визуальный стиль карточки в зависимости от результата
                    if st_val == "✅ Проход":
                        card_class = "card-win goal-highlight"
                    elif st_val == "❌ Проигрыш":
                        card_class = "card-loss"
                    else:
                        card_class = "card-pending"

                    with st.container():
                        st.markdown(f"<div class='{card_class}'>", unsafe_allow_html=True)
                        
                        st.markdown(
                            f"<div class='value-badge'>{card.get('value_tag', '💎 Валуй')}</div>",
                            unsafe_allow_html=True,
                        )

                        t1, t2 = card.get("team1"), card.get("team2")
                        cl1, cl2, cl3 = st.columns([1, 2, 1])
                        with cl1:
                            st.image(card.get("team1_logo"), width=34)
                        with cl2:
                            st.markdown(
                                f"<div style='text-align: center; font-size:0.75rem;'><b>{t1}</b><br><span style='color:#00FF66;'><b>VS</b></span><br><b>{t2}</b></div>",
                                unsafe_allow_html=True,
                            )
                        with cl3:
                            st.image(card.get("team2_logo"), width=34)

                        st.caption(
                            f"🏆 {card.get('league')} |"
                            f" {card.get('time_status','Сегодня')}"
                        )
                        st.markdown("---")

                        st.metric(
                            f"🎯 {card.get('bet_type','Маркет')}",
                            card.get("bet", "—"),
                            f"Кф {card.get('coefficient', '1.80')}",
                        )

                        conf = max(card.get("confidence_percent", 85), 85)
                        st.write(f"Уверенность: **{conf}%**")
                        st.progress(conf / 100)

                        if card.get("x_factor"):
                            st.markdown(
                                f"<div class='stat-box'>{card.get('x_factor')}</div>",
                                unsafe_allow_html=True,
                            )

                        with st.expander("🧠 Анализ"):
                            st.write(
                                f"**Разбор:** {card.get('tactical_summary', '—')}"
                            )
                            st.write(
                                f"**Вердикт:** {card.get('reason', '—')}"
                            )

                        st.write(
                            f"Статус: **{st_val}** (Счет: `{card.get('score', '0:0')}`)"
                        )

                        bc1, bc2, bc3 = st.columns(3)
                        if bc1.button(
                            "🟢", key=f"win_{entry['id']}_{idx}", use_container_width=True
                        ):
                            card["status"] = "✅ Проход"
                            save_history(st.session_state.history)
                            st.rerun()
                        if bc2.button(
                            "🔴", key=f"loss_{entry['id']}_{idx}", use_container_width=True
                        ):
                            card["status"] = "❌ Проигрыш"
                            save_history(st.session_state.history)
                            st.rerun()
                        if bc3.button(
                            "⏳", key=f"pend_{entry['id']}_{idx}", use_container_width=True
                        ):
                            card["status"] = "⌛ Ожидание"
                            save_history(st.session_state.history)
                            st.rerun()
                            
                        st.markdown("</div>", unsafe_allow_html=True)

else:
    # ОКНО ОБЩЕГО АРХИВА
    apply_custom_styles("default")
    st.title("📜 Общий архив всех прогнозов")
    st.write(
        "Здесь собраны все сессии и прогнозы по всем видам спорта. Вы можете управлять их статусами."
    )

    if not st.session_state.history:
        st.info("Архив пуст.")
    else:
        for entry in st.session_state.history:
            h_matches = entry.get("data", [])
            if not h_matches:
                continue

            st.markdown(
                f"### 📅 Сессия от {entry.get('date')}"
                f" [{entry.get('ai_source', 'ИИ')}]"
            )

            cols = st.columns(3)
            for idx, card in enumerate(h_matches):
                col_idx = idx % 3
                with cols[col_idx]:
                    st_val = card.get("status", "⌛ Ожидание")
                    card_class = "card-win" if st_val == "✅ Проход" else ("card-loss" if st_val == "❌ Проигрыш" else "card-pending")
                    
                    st.markdown(f"<div class='{card_class}'>", unsafe_allow_html=True)
                    st.markdown(
                        f"**{card.get('team1')} vs {card.get('team2')}**",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"🎯 `{card.get('bet')}` (Кф `{card.get('coefficient')}`"
                        f" | `{card.get('confidence_percent', 85)}%`)"
                    )
                    st.write(f"Статус: **{st_val}** (Счет: `{card.get('score', '0:0')}`)")

                    hc1, hc2, hc3 = st.columns(3)
                    if hc1.button(
                        "🟢", key=f"arch_win_{entry['id']}_{idx}", use_container_width=True
                    ):
                        card["status"] = "✅ Проход"
                        save_history(st.session_state.history)
                        st.rerun()
                    if hc2.button(
                        "🔴", key=f"arch_loss_{entry['id']}_{idx}", use_container_width=True
                    ):
                        card["status"] = "❌ Проигрыш"
                        save_history(st.session_state.history)
                        st.rerun()
                    if hc3.button(
                        "⏳", key=f"arch_pend_{entry['id']}_{idx}", use_container_width=True
                    ):
                        card["status"] = "⌛ Ожидание"
                        save_history(st.session_state.history)
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("---")
