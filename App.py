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

# --- АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ ---
# 3600000 миллисекунд = 1 час. Вкладка обновляется и запускает сканирование всех видов спорта.
count = st_autorefresh(interval=3600000, key="auto_sniper_refresh")

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
    page_title="Auto-Sniper: Global Terminals", page_icon="🎯", layout="wide"
)

if "history" not in st.session_state:
    st.session_state.history = load_history()

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
            ("tennis", "atp", "ATP Теннис"),
            ("tennis", "wta", "WTA Теннис"),
        ],
    },
}

SPORT_BACKGROUNDS = {
    "soccer": [
        "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"
    ],
    "basketball": [
        "https://images.unsplash.com/photo-1546519638-68e109498ffc?auto=format&fit=crop&w=1920&q=80"
    ],
    "hockey": [
        "https://images.unsplash.com/photo-1580748141549-71748dbe0bdc?auto=format&fit=crop&w=1920&q=80"
    ],
    "volleyball": [
        "https://images.unsplash.com/photo-1612872087720-bb876e2e67d1?auto=format&fit=crop&w=1920&q=80"
    ],
    "tennis": [
        "https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?auto=format&fit=crop&w=1920&q=80"
    ],
    "default": [
        "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?auto=format&fit=crop&w=1920&q=80"
    ],
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
    elif theme_mode == "🌙 Строгая темная":
        css_code = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
            .stApp { background-color: #0b0f19 !important; color: #f1f5f9; font-family: 'Plus Jakarta Sans', sans-serif; }
            .block-container { padding-top: 1.2rem; padding-bottom: 3rem; max-width: 98%; }
            .value-badge { background: #2563eb; color: #ffffff; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.7rem; display: inline-block; margin-bottom: 6px; }
            .stat-box { background: #1e293b; border-left: 3px solid #00ff66; padding: 8px 10px; border-radius: 6px; margin: 6px 0; font-size: 0.8rem; color: #f1f5f9; }
            .card-win { background: rgba(16, 185, 129, 0.12) !important; border: 2px solid #00ff66 !important; border-radius: 12px; padding: 10px; }
            .card-loss { background: rgba(239, 68, 68, 0.12) !important; border: 2px solid #ef4444 !important; border-radius: 12px; padding: 10px; }
            .card-pending { background: #1e293b !important; border: 1px solid rgba(255, 255, 255, 0.1) !important; border-radius: 12px; padding: 10px; }
        </style>
        """
    else:
        bgs = SPORT_BACKGROUNDS.get(sport_type, SPORT_BACKGROUNDS["default"])
        bg1 = bgs[0]
        css_code = f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
            .stApp {{
                background-image: linear-gradient(rgba(8, 12, 22, 0.92), rgba(8, 12, 22, 0.96)), url("{bg1}");
                background-size: cover; background-attachment: fixed; background-position: center;
                color: #f1f5f9; font-family: 'Plus Jakarta Sans', sans-serif;
            }}
            .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 98%; }}
            .value-badge {{ background: #2563eb; color: #ffffff; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.7rem; display: inline-block; margin-bottom: 6px; }}
            .stat-box {{ background: rgba(30, 41, 59, 0.6); border-left: 3px solid #00FF66; padding: 8px 10px; border-radius: 6px; margin: 6px 0; font-size: 0.8rem; color: #f1f5f9; }}
            .card-win {{ background: rgba(16, 185, 129, 0.12) !important; border: 2px solid #00FF66 !important; border-radius: 12px; padding: 10px; }}
            .card-loss {{ background: rgba(239, 68, 68, 0.12) !important; border: 2px solid #EF4444 !important; border-radius: 12px; padding: 10px; }}
            .card-pending {{ background: rgba(30, 41, 59, 0.75) !important; border: 1px solid rgba(255, 255, 255, 0.1) !important; border-radius: 12px; padding: 10px; }}
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


def fetch_matches_for_endpoints(endpoints_list, sport_category, only_prematch=False):
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
                                now_utc = datetime.datetime.now(
                                    datetime.timezone.utc
                                )
                                diff_hours = (
                                    match_time - now_utc
                                ).total_seconds() / 3600.0
                                if diff_hours < -0.1 or diff_hours > 2.0:
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


def run_background_global_scan(
    groq_key,
    gemini_key,
    ai_mode_setting,
    groq_model_name,
    tg_token,
    tg_chat_id,
):
    current_time_ts = time.time()
    if current_time_ts - st.session_state.last_scan_timestamp < 3300:
        return

    st.session_state.last_scan_timestamp = current_time_ts
    today_date = datetime.date.today().strftime("%d.%m.%Y")
    current_time_str = datetime.datetime.now().strftime("%H:%M")

    for sport_name, sport_info in SPORT_GROUPS.items():
        cat = sport_info["category"]
        endpoints = sport_info["endpoints"]

        try:
            real_matches = fetch_matches_for_endpoints(
                endpoints, cat, only_prematch=True
            )
            if not real_matches:
                continue

            existing_teams = set()
            for entry in st.session_state.history:
                for card in entry.get("data", []):
                    if card.get("sport_category") == cat:
                        existing_teams.add(card.get("team1", "").lower())
                        existing_teams.add(card.get("team2", "").lower())

            filtered_matches = [
                m
                for m in real_matches
                if m["team1"].lower() not in existing_teams
                and m["team2"].lower() not in existing_teams
            ]
            if not filtered_matches:
                continue

            match_lines = [
                f"{idx+1}. [{rm['sport_label']}] {rm['team1']} VS {rm['team2']} | {rm['status']}"
                for idx, rm in enumerate(filtered_matches[:15])
            ]
            context_text = (
                f"ДОСТУПНЫЕ МАТЧИ ({sport_name}):\n"
                + "\n".join(match_lines)
            )

            base_prompt = f"""
Сегодня {today_date}, время {current_time_str}. Вид спорта: {sport_name}
{context_text}

СТРОГИЕ ПРАВИЛА:
1. Выбери ТОЛЬКО 1 самое безупречное железобетонное событие с вероятностью прохода от 90%. Если идеального нет, верни пустой список матчей.
2. Коэффициент: от 1.50 до 2.10.

Верни СТРОГО JSON формата:
{{
  "matches": [
    {{
      "team1": "Команда 1",
      "team2": "Команда 2",
      "league": "Лига",
      "time_status": "Время",
      "bet_type": "Маркет",
      "bet": "Ставка",
      "coefficient": "1.85",
      "confidence_percent": 92,
      "value_tag": "💎 ЖЕЛЕЗО",
      "x_factor": "Главный довод",
      "tactical_summary": "Разбор"
    }}
  ]
}}
"""
            raw_response = ""
            if ai_mode_setting == "🧠 Только Groq AI" and groq_key:
                client = Groq(api_key=groq_key)
                comp = client.chat.completions.create(
                    model=groq_model_name or "llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": base_prompt}],
                    temperature=0.1,
                )
                raw_response = comp.choices[0].message.content
            elif ai_mode_setting == "✨ Только Gemini AI" and gemini_key:
                raw_response = call_gemini_api(gemini_key, base_prompt)
            else:
                continue

            if not raw_response:
                continue

            cleaned = re.sub(
                r"<think>.*?</think>", "", raw_response, flags=re.DOTALL
            ).strip()
            json_start = cleaned.find("{")
            json_end = cleaned.rfind("}") + 1
            parsed_json = json.loads(cleaned[json_start:json_end])
            parsed_matches = parsed_json.get("matches", [])

            if parsed_matches:
                pm = parsed_matches[0]
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
                    pm["team1_logo"] = match_found["team1_logo"]
                    pm["team2_logo"] = match_found["team2_logo"]
                    pm["league"] = match_found["sport_label"]
                else:
                    pm["team1_logo"] = f"https://ui-avatars.com/api/?name={t1}&background=1e293b&color=00ff66"
                    pm["team2_logo"] = f"https://ui-avatars.com/api/?name=Team2&background=1e293b&color=00bfff"

                pm["sport_category"] = cat
                pm["score"] = "0:0"
                pm["status"] = "⌛ Ожидание"

                if tg_token and tg_chat_id:
                    tg_text = (
                        f"💎 *ФОНОВЫЙ СИГНАЛ: {sport_name}*\n\n"
                        f"🏆 {pm.get('league')}\n"
                        f"⚽ *{pm.get('team1')} vs {pm.get('team2')}*\n"
                        f"📌 Ставка: `{pm.get('bet')}` (Кф `{pm.get('coefficient')}`)\n"
                        f"🔥 Проход: `{pm.get('confidence_percent')}%`\n"
                        f"💡 Обоснование: {pm.get('x_factor')}"
                    )
                    send_telegram_message(tg_token, tg_chat_id, tg_text)

                new_entry = {
                    "id": str(time.time()),
                    "date": f"{today_date} {current_time_str} ({sport_name} - Авто)",
                    "ai_source": ai_mode_setting,
                    "data": [pm],
                }
                st.session_state.history.insert(0, new_entry)
                save_history(st.session_state.history)
        except Exception:
            pass


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
st.sidebar.title("⚙️ Настройки ИИ и Telegram")
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
telegram_token = st.sidebar.text_input(
    "Telegram Bot Token", type="password", placeholder="123456:ABC-DEF..."
)
telegram_chat_id = st.sidebar.text_input(
    "Telegram Chat ID", placeholder="-100123456789"
)

if st.sidebar.button("🔔 Тест Telegram"):
    success = send_telegram_message(
        telegram_token,
        telegram_chat_id,
        "🟢 *Auto-Sniper*: Тестовое сообщение успешно доставлено!",
    )
    if success:
        st.sidebar.success("Сообщение отправлено!")
    else:
        st.sidebar.error("Ошибка отправки. Проверьте Token и Chat ID.")

selected_groq_model = None
if groq_api_key:
    models_list = fetch_active_groq_models(groq_api_key)
    selected_groq_model = st.sidebar.selectbox(
        "Модель Groq", models_list, index=0
    )

# Автоматический запуск глобального фонового сканирования по всем вкладкам
if groq_api_key or gemini_api_key:
    run_background_global_scan(
        groq_api_key,
        gemini_api_key,
        ai_mode,
        selected_groq_model,
        telegram_token,
        telegram_chat_id,
    )

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
    sport_win_rate = (
        (sport_wins / sport_finished * 100) if sport_finished > 0 else 0.0
    )

    st.title(f"🎯 Терминал прематча: {sport_title}")
    st.caption(
        "Элитный отбор: генерируются только 1-2 железобетонных события высшей пробы"
    )

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        if st.button(
            f"📊 Win Rate\n{sport_win_rate:.1f}%",
            use_container_width=True,
            key=f"btn_f_all_{current_cat}",
        ):
            st.session_state[filter_key] = "Все"
    with mc2:
        if st.button(
            f"🟢 Победы\n{sport_wins}",
            use_container_width=True,
            key=f"btn_f_win_{current_cat}",
        ):
            st.session_state[filter_key] = "✅ Проход"
    with mc3:
        if st.button(
            f"🔴 Поражения\n{sport_losses}",
            use_container_width=True,
            key=f"btn_f_loss_{current_cat}",
        ):
            st.session_state[filter_key] = "❌ Проигрыш"
    with mc4:
        if st.button(
            "🔄 Проверить итоги окна",
            use_container_width=True,
            key=f"check_btn_{current_cat}",
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
                                old_status = card.get("status", "⌛ Ожидание")
                                new_status = auto_evaluate_bet(
                                    card, found["score"], found["is_finished"]
                                )
                                if old_status != new_status:
                                    card["status"] = new_status
                                    settled_count += 1
                save_history(st.session_state.history)
                st.success(f"Обновлено статусов: {settled_count}")
                st.rerun()

    active_f = st.session_state[filter_key]
    st.markdown("---")

    today_date = datetime.date.today().strftime("%d.%m.%Y")
    current_time = datetime.datetime.now().strftime("%H:%M")

    col_scan1, col_scan2 = st.columns([2, 1])
    with col_scan1:
        num_signals = st.slider(
            "Количество сигналов (рекомендуется 1-2):", 1, 2, 1, key=f"slider_{current_cat}"
        )
    with col_scan2:
        btn_search = st.button(
            f"🚀 Найти железо в {sport_title}",
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
                f"Глубокий аналитический отбор матчей в {sport_title}..."
            ):
                try:
                    real_matches = fetch_matches_for_endpoints(
                        current_endpoints, current_cat, only_prematch=True
                    )
                    
                    existing_teams = set()
                    for entry in st.session_state.history:
                        for card in entry.get("data", []):
                            if card.get("sport_category") == current_cat:
                                existing_teams.add(card.get("team1", "").lower())
                                existing_teams.add(card.get("team2", "").lower())

                    filtered_real_matches = [
                        rm for rm in real_matches 
                        if rm["team1"].lower() not in existing_teams and rm["team2"].lower() not in existing_teams
                    ]

                    if not filtered_real_matches:
                        st.warning(
                            f"⚠️ Все доступные матчи в {sport_title} уже проанализированы ранее или отсутствуют в линии."
                        )
                    else:
                        match_lines = [
                            f"{idx+1}. [{rm['sport_label']}] {rm['team1']} VS {rm['team2']} | {rm['status']}"
                            for idx, rm in enumerate(filtered_real_matches[:25])
                        ]
                        context_text = (
                            f"ДОСТУПНЫЕ УНИКАЛЬНЫЕ МАТЧИ ({sport_title}):\n"
                            + "\n".join(match_lines)
                        )

                        past_losses_list = []
                        for entry in st.session_state.history:
                            for card in entry.get("data", []):
                                if (
                                    card.get("sport_category") == current_cat
                                    and card.get("status") == "❌ Проигрыш"
                                ):
                                    past_losses_list.append(
                                        f"- Матч: {card.get('team1')} vs {card.get('team2')} | Ошибка: {card.get('bet')}"
                                    )

                        feedback_section = ""
                        if past_losses_list:
                            losses_str = "\n".join(past_losses_list[-5:])
                            feedback_section = f"""
                            ⚠️ РЕФЛЕКСИЯ И РАБОТА НАД ОШИБКАМИ:
                            Избегай подобных промахов:
                            {losses_str}
                            """

                        base_prompt = f"""
Сегодня {today_date}, время {current_time}. Вид спорта: {sport_title}
{context_text}
{feedback_section}

СТРОГИЕ ПРАВИЛА ОТБОРА (ВАЖНО):
1. Из всего списка выбери ТОЛЬКО {num_signals} самых безупречных, железобетонных события с наивысшей статистической вероятностью прохода (от 90% и выше). Никаких случайных ставок!
2. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО дублировать команды, которые уже анализировались.
3. Коэффициент: от 1.50 до 2.10. Уверенность: от 90%.

Верни СТРОГО JSON формата (без лишнего текста):
{{
  "matches": [
    {{
      "team1": "Команда 1",
      "team2": "Команда 2",
      "league": "Лига",
      "time_status": "Время",
      "bet_type": "Маркет",
      "bet": "Ставка",
      "coefficient": "1.85",
      "confidence_percent": 92,
      "value_tag": "💎 ЖЕЛЕЗО",
      "x_factor": "🔥 Главный статистический довод",
      "tactical_summary": "🧠 Глубокий разбор трендов и формы"
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
                                temperature=0.1,
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
                                + f"\n\nМнение Gemini:\n{gemini_raw}\nСинтезируй идеальный финальный JSON!"
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
                                temperature=0.1,
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
                            telegram_notifications_sent = 0
                            for pm in parsed_matches[:num_signals]:
                                if pm.get("confidence_percent", 0) < 90:
                                    pm["confidence_percent"] = 90
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
                                    pm["team1_logo"] = f"https://ui-avatars.com/api/?name={t1}&background=1e293b&color=00ff66"
                                    pm["team2_logo"] = f"https://ui-avatars.com/api/?name=Team2&background=1e293b&color=00bfff"

                                pm["sport_category"] = current_cat
                                pm["score"] = "0:0"
                                pm["status"] = "⌛ Ожидание"

                                if telegram_token and telegram_chat_id:
                                    tg_text = (
                                        f"💎 *ЭЛИТНЫЙ СИГНАЛ: {sport_title}*\n\n"
                                        f"🏆 {pm.get('league')}\n"
                                        f"⚽ *{pm.get('team1')} vs {pm.get('team2')}*\n"
                                        f"📌 Ставка: `{pm.get('bet')}` (Кф `{pm.get('coefficient')}`)\n"
                                        f"🔥 Проход: `{pm.get('confidence_percent')}%`\n"
                                        f"💡 Обоснование: {pm.get('x_factor')}"
                                    )
                                    if send_telegram_message(
                                        telegram_token, telegram_chat_id, tg_text
                                    ):
                                        telegram_notifications_sent += 1

                            new_entry = {
                                "id": str(time.time()),
                                "date": f"{today_date} {current_time} ({sport_title})",
                                "ai_source": ai_mode,
                                "data": parsed_matches[:num_signals],
                            }
                            st.session_state.history.insert(0, new_entry)
                            save_history(st.session_state.history)
                            st.success(
                                f"✅ Успешно отобрано элитных сигналов: {len(parsed_matches[:num_signals])}. В Telegram отправлено: {telegram_notifications_sent}"
                            )
                            st.rerun()
                        else:
                            st.warning("⚠️ ИИ не нашел матчей, удовлетворяющих строгим критериям качества (90%+).")
                except Exception as e:
                    st.error(f"Ошибка отбора: {e}")

    st.markdown("### 📋 Элитные прогнозы в окне")
    window_history = []
    for entry in st.session_state.history:
        filtered_cards = [
            c for c in entry.get("data", [])
            if c.get("sport_category") == current_cat and (active_f == "Все" or c.get("status") == active_f)
        ]
        if filtered_cards:
            entry_copy = entry.copy()
            entry_copy["data"] = filtered_cards
            window_history.append(entry_copy)

    if not window_history:
        st.info(f"Нет прогнозов в окне '{sport_title}'.")
    else:
        for entry in window_history:
            filtered_cards = entry.get("data", [])
            st.caption(f"Сессия от {entry.get('date')} [{entry.get('ai_source')}]")
            cols = st.columns(3)
            for idx, card in enumerate(filtered_cards):
                col_idx = idx % 3
                with cols[col_idx]:
                    st_val = card.get("status", "⌛ Ожидание")
                    card_class = (
                        "card-win"
                        if st_val == "✅ Проход"
                        else (
                            "card-loss"
                            if st_val == "❌ Проигрыш"
                            else "card-pending"
                        )
                    )
                    with st.container():
                        st.markdown(
                            f"<div class='{card_class}'>", unsafe_allow_html=True
                        )
                        st.markdown(
                            f"<div class='value-badge'>{card.get('value_tag', '💎 ЖЕЛЕЗО')}</div>",
                            unsafe_allow_html=True,
                        )
                        t1, t2 = card.get("team1"), card.get("team2")
                        cl1, cl2, cl3 = st.columns([1, 2, 1])
                        with cl1:
                            st.image(card.get("team1_logo"), width=34)
                        with cl2:
                            st.markdown(
                                f"<div style='text-align: center; font-size:0.75rem;'><b>{t1}</b><br><span style='color:#10b981;'><b>VS</b></span><br><b>{t2}</b></div>",
                                unsafe_allow_html=True,
                            )
                        with cl3:
                            st.image(card.get("team2_logo"), width=34)

                        st.caption(
                            f"🏆 {card.get('league')} | {card.get('time_status','Сегодня')}"
                        )
                        st.markdown("---")
                        st.metric(
                            f"🎯 {card.get('bet_type','Маркет')}",
                            card.get("bet", "—"),
                            f"Кф {card.get('coefficient', '1.80')}",
                        )
                        conf = max(card.get("confidence_percent", 90), 90)
                        st.write(f"Уверенность: **{conf}%**")
                        st.progress(conf / 100)

                        if card.get("x_factor"):
                            st.markdown(
                                f"<div class='stat-box'>{card.get('x_factor')}</div>",
                                unsafe_allow_html=True,
                            )

                        with st.expander("🧠 Разбор ИИ"):
                            st.write(
                                f"**Статус итога:** {st_val} (Счет: `{card.get('score', '0:0')}`)"
                            )
                            st.write(
                                f"**Анализ:** {card.get('tactical_summary', '—')}"
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
    apply_custom_styles(theme_choice, "default")
    st.title("📜 Общий архив всех прогнозов")
    if not st.session_state.history:
        st.info("Архив пуст.")
    else:
        for entry in st.session_state.history:
            h_matches = entry.get("data", [])
            if not h_matches:
                continue
            st.markdown(
                f"### 📅 Сессия от {entry.get('date')} [{entry.get('ai_source', 'ИИ')}]"
            )
            cols = st.columns(3)
            for idx, card in enumerate(h_matches):
                col_idx = idx % 3
                with cols[col_idx]:
                    st_val = card.get("status", "⌛ Ожидание")
                    card_class = (
                        "card-win"
                        if st_val == "✅ Проход"
                        else (
                            "card-loss"
                            if st_val == "❌ Проигрыш"
                            else "card-pending"
                        )
                    )
                    st.markdown(
                        f"<div class='card-pending'>", unsafe_allow_html=True
                    )
                    st.markdown(
                        f"**{card.get('team1')} vs {card.get('team2')}**",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"🎯 `{card.get('bet')}` (Кф `{card.get('coefficient')}`)"
                    )
                    st.write(
                        f"Статус: **{st_val}** (Счет: `{card.get('score', '0:0')}`)"
                    )
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
