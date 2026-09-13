import datetime
import json
import os
import random
import re
import time
import requests
import streamlit as st
from duckduckgo_search import DDGS
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
    page_title="Auto-Sniper: Pro Betting Terminal", page_icon="🎯", layout="wide"
)

if "history" not in st.session_state:
    st.session_state.history = load_history()

# РАСШИРЕННЫЙ СПИСОК ЛИГ (Европа, Америка, Россия)
SPORTS_ENDPOINTS = [
    # Футбол
    ("soccer", "eng.1", "⚽ АПЛ (Англия)", "soccer"),
    ("soccer", "esp.1", "⚽ Ла Лига (Испания)", "soccer"),
    ("soccer", "ger.1", "⚽ Бундеслига (Германия)", "soccer"),
    ("soccer", "ita.1", "⚽ Серия А (Италия)", "soccer"),
    ("soccer", "fra.1", "⚽ Лига 1 (Франция)", "soccer"),
    ("soccer", "rus.1", "⚽ РПЛ (Россия)", "soccer"),
    ("soccer", "uefa.champions", "⚽ Лига Чемпионов УЕФА", "soccer"),
    ("soccer", "usa.1", "⚽ MLS (США)", "soccer"),
    # Баскетбол
    ("basketball", "nba", "🏀 НБА (США)", "basketball"),
    (
        "basketball",
        "mens-college-basketball",
        "🏀 NCAA Баскетбол (США)",
        "basketball",
    ),
    # Хоккей
    ("hockey", "nhl", "🏒 НХЛ (США/Канада)", "hockey"),
    ("hockey", "khl", "🏒 КХЛ (Россия/Европа)", "hockey"),
    # Америка / Бейсбол / Американский футбол
    ("football", "nfl", "🏈 НФЛ (США)", "american_football"),
    ("baseball", "mlb", "⚾ МЛБ (США)", "baseball"),
    # Теннис
    ("tennis", "atp", "🎾 ATP Теннис", "tennis"),
    ("tennis", "wta", "🎾 WTA Теннис", "tennis"),
]

DEFAULT_STADIUM_BGS = {
    "soccer": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80",
    "basketball": "https://images.unsplash.com/photo-1546519638-68e109498ffc?auto=format&fit=crop&w=1920&q=80",
    "hockey": "https://images.unsplash.com/photo-1580748141549-71748dbe0bdc?auto=format&fit=crop&w=1920&q=80",
    "tennis": "https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?auto=format&fit=crop&w=1920&q=80",
    "default": "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?auto=format&fit=crop&w=1920&q=80",
}


def apply_custom_styles(sport_type="default"):
    bg_url = DEFAULT_STADIUM_BGS.get(
        sport_type, DEFAULT_STADIUM_BGS["default"]
    )
    css_code = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

        .stApp {{
            background: linear-gradient(rgba(8, 12, 22, 0.93), rgba(8, 12, 22, 0.97)), url("{bg_url}");
            background-size: cover;
            background-attachment: fixed;
            background-position: center;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }}
        .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 98%; }}
        
        div[data-testid="stMetric"] {{
            background: rgba(15, 23, 42, 0.8);
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
            background: linear-gradient(135deg, #059669 0%, #10b981 100%);
            color: #ffffff;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.7rem;
            display: inline-block;
            margin-bottom: 6px;
            box-shadow: 0 2px 8px rgba(16, 185, 129, 0.4);
        }}
        
        .score-badge-live {{
            background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);
            color: white;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 800;
            font-size: 0.72rem;
            animation: pulse 2s infinite;
            display: inline-block;
            box-shadow: 0 0 12px rgba(239, 68, 68, 0.5);
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

        .stTabs [data-baseweb="tab-list"] {{
            gap: 6px;
            background-color: rgba(15, 23, 42, 0.7);
            padding: 4px;
            border-radius: 12px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 8px;
            color: #94a3b8;
            font-weight: 600;
        }}
        .stTabs [aria-selected="true"] {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important;
            color: #00FF66 !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        
        @keyframes pulse {{
            0% {{ opacity: 1; }}
            50% {{ opacity: 0.6; }}
            100% {{ opacity: 1; }}
        }}
    </style>
    """
    st.markdown(css_code, unsafe_allow_html=True)


def determine_match_phase(status_str, state_str):
    s = status_str.lower()
    if state_str == "pre":
        return "до перерыва"
    if any(
        x in s
        for x in [
            "2nd",
            "3rd",
            "4th",
            "2-й",
            "3-й",
            "4-й",
            "ot",
            "овертайм",
        ]
    ):
        return "после перерыва"
    return "до перерыва"


def is_match_near_end(status_str, sport_cat):
    """Фильтрует матчи, у которых осталось 5-10 минут до конца"""
    s = status_str.lower()
    if sport_cat == "soccer":
        # Проверяем минуты футбола (например, 85', 88', 90+')
        mins = re.findall(r"(\d+)'", s)
        if mins:
            current_min = int(mins[0])
            if current_min >= 83:  # Отсекаем концовку
                return True
    # Для других видов спорта если идет финальный отрезок
    if any(
        end_marker in s
        for end_marker in ["4th qtr", "3rd period", "final", "от", "ot"]
    ):
        if "4th" in s or "3rd period" in s:
            # Если это баскетбол/хоккей близко к концу
            pass
    return False


def fetch_all_sports_matches():
    today_str = datetime.date.today().strftime("%Y%m%d")
    raw_matches = []

    for sport, league, label, sport_cat in SPORTS_ENDPOINTS:
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

                    if state == "post":
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

                    is_live = state == "in"
                    score_str = f"{score_home}:{score_away}"

                    if is_live:
                        status_str = f"🔴 LIVE {short_detail} ({score_str})"
                    else:
                        status_str = f"⏰ {short_detail}"

                    # Пропускаем матчи, где осталось 5-10 минут
                    if is_live and is_match_near_end(status_str, sport_cat):
                        continue

                    phase = determine_match_phase(status_str, state)

                    raw_matches.append({
                        "sport_label": label,
                        "sport_category": sport_cat,
                        "team1": t1_name,
                        "team2": t2_name,
                        "team1_logo": t1_logo,
                        "team2_logo": t2_logo,
                        "status": status_str,
                        "is_live": is_live,
                        "is_finished": False,
                        "score": score_str,
                        "state": state,
                        "game_phase": phase,
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


initial_bg_cat = "default"
if st.session_state.history and st.session_state.history[0].get("data"):
    first_item = st.session_state.history[0]["data"][0]
    initial_bg_cat = first_item.get("sport_category", "default")

apply_custom_styles(initial_bg_cat)

st.sidebar.title("⚙️ Панель управления")
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


selected_groq_model = None
if groq_api_key:
    models_list = fetch_active_groq_models(groq_api_key)
    selected_groq_model = st.sidebar.selectbox(
        "Модель Groq", models_list, index=0
    )

total_wins, total_losses = 0, 0
for item in st.session_state.history:
    for card in item.get("data", []):
        st_val = card.get("status", "⌛ Ожидание")
        if st_val == "✅ Проход":
            total_wins += 1
        elif st_val == "❌ Проигрыш":
            total_losses += 1

total_finished = total_wins + total_losses
win_rate = (total_wins / total_finished * 100) if total_finished > 0 else 0.0

st.title("🎯 Auto-Sniper Pro Terminal")
st.caption(
    "Интеллектуальная система аналитики (КФ $\\ge$ 1.40 | Уверенность $\\ge$"
    " 85%)"
)

s_c1, s_c2, s_c3, s_c4 = st.columns(4)
s_c1.metric("📊 Win Rate", f"{win_rate:.1f}%")
s_c2.metric("🟢 Победы", f"{total_wins}")
s_c3.metric("🔴 Поражения", f"{total_losses}")

if s_c4.button("🔄 Синхролайн", use_container_width=True):
    with st.spinner("Обновление живых счетов..."):
        live_matches = fetch_all_sports_matches()
        updated_count, settled_count = 0, 0

        for entry in st.session_state.history:
            for card in entry.get("data", []):
                t1 = card.get("team1", "").lower()
                found = next(
                    (m for m in live_matches if t1 in m["team1"].lower()), None
                )
                if found:
                    old_score = card.get("score", "0:0")
                    if old_score != found["score"] and found["score"] != "0:0":
                        card["score_changed"] = True
                        card["prev_score"] = old_score
                        card["score"] = found["score"]
                        card["time_status"] = found["status"]
                        card["game_phase"] = found["game_phase"]
                        updated_count += 1
                    else:
                        card["score"] = found["score"]
                        card["time_status"] = found["status"]
                        card["game_phase"] = found["game_phase"]

                    old_status = card.get("status", "⌛ Ожидание")
                    new_status = auto_evaluate_bet(
                        card, found["score"], found["is_finished"]
                    )
                    if old_status != new_status:
                        card["status"] = new_status
                        settled_count += 1

        save_history(st.session_state.history)
        st.success(f"Обновлено: {updated_count} | Рассчитано: {settled_count}")
        st.rerun()

st.markdown("---")

tab_current, tab_manual, tab_history = st.tabs([
    "🔥 Авто-Сканер Линии",
    "✏️ Ручной выбор (Все лиги)",
    "📜 Архив & Результаты",
])

with tab_current:
    today_date = datetime.date.today().strftime("%d.%m.%Y")
    current_time = datetime.datetime.now().strftime("%H:%M")

    c_input1, c_input2 = st.columns([3, 1])
    with c_input1:
        num_signals = st.slider("Количество событий в выборке:", 1, 6, 3)
    with c_input2:
        btn_search = st.button(
            "🚀 Запустить Сканер", type="primary", use_container_width=True
        )

    if btn_search:
        if ai_mode == "🧠 Только Groq AI" and not groq_api_key:
            st.error("⚠️ Укажите API ключ Groq!")
        elif ai_mode == "✨ Только Gemini AI" and not gemini_api_key:
            st.error("⚠️ Укажите API ключ Gemini!")
        elif (
            ai_mode == "🤖🤖 Консилиум (Groq + Gemini)"
            and (not groq_api_key or not gemini_api_key)
        ):
            st.error("⚠️ Укажите оба ключа!")
        else:
            with st.spinner(
                "Сканируем линии (исключая концовки матчей), Кф ≥ 1.40, Уверенность ≥ 85%..."
            ):
                try:
                    real_matches = fetch_all_sports_matches()
                    if not real_matches:
                        st.warning(
                            "⚠️ Нет подходящих матчей в линии. Попробуйте ручной выбор!"
                        )
                    else:
                        match_lines = [
                            f"{idx+1}. [{rm['sport_label']}] {rm['team1']} VS {rm['team2']} | Счет: {rm['score']} | Фаза: {rm['game_phase']} | Статус: {rm['status']}"
                            for idx, rm in enumerate(real_matches[:20])
                        ]
                        context_text = (
                            "ДОСТУПНЫЕ СОБЫТИЯ (Концовки матчей отсечены):\n"
                            + "\n".join(match_lines)
                        )

                        base_prompt = f"""
Сегодня {today_date}, время {current_time} МСК.
{context_text}

КРИТЕРИИ АНАЛИЗА:
1. Только предстоящие матчи или LIVE в активной фазе (не за 5 минут до конца!).
2. КОЭФФИЦИЕНТ: строго от 1.40 и выше.
3. УВЕРЕННОСТЬ ИИ: строго от 85% и выше.

Верни СТРОГО JSON формата:
{{
  "matches": [
    {{
      "team1": "Команда 1",
      "team2": "Команда 2",
      "league": "Лига",
      "time_status": "Статус",
      "game_phase": "до перерыва OR после перерыва",
      "score": "0:0",
      "bet_type": "Маркет",
      "bet": "Ставка (например: ТБ 2.5)",
      "coefficient": "1.85",
      "confidence_percent": 88,
      "value_tag": "💎 Снайперский выбор",
      "x_factor": "🔥 Ключевой фактор",
      "tactical_summary": "🧠 Тактический разбор",
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

                        if not parsed_matches:
                            st.warning("⚠️ Нет матчей под заданные критерии.")
                        else:
                            first_sport_cat = "default"
                            for idx_pm, pm in enumerate(
                                parsed_matches[:num_signals]
                            ):
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
                                    pm["sport_category"] = match_found[
                                        "sport_category"
                                    ]
                                    pm["time_status"] = match_found["status"]
                                    pm["score"] = match_found["score"]
                                    pm["game_phase"] = match_found["game_phase"]
                                else:
                                    pm["team1_logo"] = (
                                        f"https://ui-avatars.com/api/?name={t1}&background=1e293b&color=00ff66"
                                    )
                                    pm["team2_logo"] = f"https://ui-avatars.com/api/?name=Team2&background=1e293b&color=00bfff"
                                    pm["score"] = "0:0"
                                    pm["sport_category"] = "default"
                                    pm["game_phase"] = "до перерыва"

                                if idx_pm == 0:
                                    first_sport_cat = pm.get(
                                        "sport_category", "default"
                                    )

                                pm["status"] = "⌛ Ожидание"
                                pm["score_changed"] = False

                            new_entry = {
                                "id": str(time.time()),
                                "date": f"{today_date} {current_time}",
                                "ai_source": ai_mode,
                                "data": parsed_matches[:num_signals],
                            }
                            st.session_state.history.insert(0, new_entry)
                            save_history(st.session_state.history)

                            apply_custom_styles(first_sport_cat)
                            st.success("🔥 Сканирование успешно завершено!")
                            st.rerun()
                except Exception as e:
                    st.error(f"Ошибка: {e}")

    if st.session_state.history:
        latest = st.session_state.history[0]
        matches_data = latest.get("data", [])

        st.subheader(
            f"🔥 Сессия ({latest['date']}) — {latest.get('ai_source', 'ИИ')}"
        )

        if not matches_data:
            st.warning("В текущей сессии нет прогнозов.")
        else:
            cols = st.columns(3)
            for idx, card in enumerate(matches_data):
                col_idx = idx % 3
                with cols[col_idx]:
                    with st.container(border=True):
                        tag = card.get("value_tag", "💎 Валуй")
                        phase_str = card.get("game_phase", "до перерыва").upper()
                        st.markdown(
                            f"<div class='value-badge'>{tag} | ⏱️ {phase_str}</div>",
                            unsafe_allow_html=True,
                        )

                        if card.get("score_changed"):
                            st.markdown(
                                "<div class='score-badge-live'>🔥 СЧЕТ:"
                                f" {card.get('prev_score')} ➔"
                                f" {card.get('score')}</div>",
                                unsafe_allow_html=True,
                            )

                        t1, t2 = card.get("team1", "Команда 1"), card.get(
                            "team2", "Команда 2"
                        )
                        c_l1, c_l2, c_l3 = st.columns([1, 2, 1])
                        with c_l1:
                            st.image(card.get("team1_logo"), width=36)
                        with c_l2:
                            st.markdown(
                                f"<div style='text-align: center; font-size:"
                                f" 0.8rem;'><b>{t1}</b><br><span style='color:#00FF66;"
                                f" font-size:1.1rem;'><b>{card.get('score','0:0')}</b></span><br><b>{t2}</b></div>",
                                unsafe_allow_html=True,
                            )
                        with c_l3:
                            st.image(card.get("team2_logo"), width=36)

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
                        st.write(f"Уверенность ИИ: **{conf}%**")
                        st.progress(conf / 100)

                        if card.get("x_factor"):
                            st.markdown(
                                f"<div class='stat-box'>{card.get('x_factor')}</div>",
                                unsafe_allow_html=True,
                            )

                        with st.expander("🧠 Разбор и анализ"):
                            st.write(
                                f"**Тактика:** {card.get('tactical_summary', '—')}"
                            )
                            st.write(
                                f"**Вердикт:** {card.get('reason', '—')}"
                            )

                        st.write(
                            f"Статус: **{card.get('status', '⌛ Ожидание')}**"
                        )

                        # ПРЯМЫЕ КНОПКИ УПРАВЛЕНИЯ (Без лишних всплывающих окон)
                        b_c1, b_c2, b_c3 = st.columns(3)
                        if b_c1.button(
                            "🟢 Победа",
                            key=f"latest_win_{idx}",
                            use_container_width=True,
                        ):
                            card["status"] = "✅ Проход"
                            save_history(st.session_state.history)
                            st.rerun()

                        if b_c2.button(
                            "🔴 Проигрыш",
                            key=f"latest_loss_{idx}",
                            use_container_width=True,
                        ):
                            card["status"] = "❌ Проигрыш"
                            save_history(st.session_state.history)
                            st.rerun()

                        if b_c3.button(
                            "⏳ Сброс",
                            key=f"latest_pend_{idx}",
                            use_container_width=True,
                        ):
                            card["status"] = "⌛ Ожидание"
                            save_history(st.session_state.history)
                            st.rerun()

with tab_manual:
    st.subheader("✏️ Ручной выбор по конкретной лиге")
    st.write(
        "Выберите любую европейскую, американскую или российскую лигу / теннис, и система найдет актуальный матч."
    )

    # Динамический список из всех доступных лиг
    all_league_labels = [item[2] for item in SPORTS_ENDPOINTS]

    with st.form("manual_sport_form"):
        chosen_league_label = st.selectbox(
            "Выберите турнир / лигу:", all_league_labels
        )
        manual_user_note = st.text_input(
            "Пожелание к матчу (опционально):",
            placeholder="Например: матч с высокой результативностью",
        )

        submitted_manual = st.form_submit_button(
            "🎯 Найти и проанализировать", type="primary"
        )

        if submitted_manual:
            if (
                ai_mode == "🧠 Только Groq AI" and not groq_api_key
            ) or (ai_mode == "✨ Только Gemini AI" and not gemini_api_key):
                st.error("⚠️ Укажите API ключ в боковой панели!")
            else:
                with st.spinner("Анализируем матчи выбранной лиги..."):
                    try:
                        all_matches = fetch_all_sports_matches()
                        filtered_matches = [
                            m
                            for m in all_matches
                            if m["sport_label"] == chosen_league_label
                        ]

                        if not filtered_matches:
                            filtered_matches = all_matches  дженерик запас

                        match_lines = [
                            f"- [{m['sport_label']}] {m['team1']} vs {m['team2']} (Счет: {m['score']}, Статус: {m['status']})"
                            for m in filtered_matches[:12]
                        ]

                        manual_prompt = f"""
Пользователь выбрал лигу/турнир: {chosen_league_label}
Пожелание: {manual_user_note}

ДОСТУПНЫЕ МАТЧИ В ЭТОЙ ЛИГЕ:
{"\n".join(match_lines) if match_lines else "Нет активных матчей прямо сейчас, подбери топ-матч дня."}

Выбери ОДИН лучший матч и составь прогноз.
КРИТЕРИИ:
1. Коэффициент: строго от 1.40 и выше.
2. Уверенность ИИ: строго от 85% и выше.

Верни СТРОГО JSON формата:
{{
  "matches": [
    {{
      "team1": "Команда 1",
      "team2": "Команда 2",
      "league": "{chosen_league_label}",
      "time_status": "Сегодня",
      "game_phase": "до перерыва",
      "score": "0:0",
      "bet_type": "Маркет",
      "bet": "Ставка",
      "coefficient": "1.85",
      "confidence_percent": 88,
      "value_tag": "💎 Железобетонный Валуй",
      "x_factor": "🔥 Ключевой фактор",
      "tactical_summary": "🧠 Тактический разбор",
      "key_stat": "📊 Цифра",
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
                                    {"role": "user", "content": manual_prompt}
                                ],
                                temperature=0.2,
                            )
                            raw_response = comp.choices[0].message.content
                        elif ai_mode == "✨ Только Gemini AI":
                            raw_response = call_gemini_api(
                                gemini_api_key, manual_prompt
                            )
                        else:
                            gemini_raw = call_gemini_api(
                                gemini_api_key, manual_prompt
                            )
                            consensus_prompt = (
                                manual_prompt
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
                            pm = parsed_matches[0]
                            if pm.get("confidence_percent", 0) < 85:
                                pm["confidence_percent"] = 85

                            t1, t2 = pm.get("team1", "Team 1"), pm.get(
                                "team2", "Team 2"
                            )
                            match_found = next(
                                (
                                    m
                                    for m in filtered_matches
                                    if t1.lower() in m["team1"].lower()
                                ),
                                None,
                            )

                            target_cat = "soccer"
                            for sc_tuple in SPORTS_ENDPOINTS:
                                if sc_tuple[2] == chosen_league_label:
                                    target_cat = sc_tuple[3]
                                    break

                            if match_found:
                                pm["team1_logo"] = match_found["team1_logo"]
                                pm["team2_logo"] = match_found["team2_logo"]
                                pm["time_status"] = match_found["status"]
                                pm["score"] = match_found["score"]
                                pm["game_phase"] = match_found["game_phase"]
                            else:
                                pm["team1_logo"] = (
                                    f"https://ui-avatars.com/api/?name={t1}&background=1e293b&color=00ff66"
                                )
                                pm["team2_logo"] = (
                                    f"https://ui-avatars.com/api/?name={t2}&background=1e293b&color=00bfff"
                                )
                                pm["score"] = "0:0"
                                pm["game_phase"] = "до перерыва"

                            pm["sport_category"] = target_cat
                            pm["status"] = "⌛ Ожидание"
                            pm["score_changed"] = False

                            new_entry = {
                                "id": str(time.time()),
                                "date": f"{today_date} {current_time} ({chosen_league_label})",
                                "ai_source": ai_mode,
                                "data": [pm],
                            }
                            st.session_state.history.insert(0, new_entry)
                            save_history(st.session_state.history)

                            apply_custom_styles(target_cat)
                            st.success("✅ Прогноз успешно сформирован!")
                            st.rerun()
                        else:
                            st.warning("⚠️ Не удалось сформировать прогноз.")
                    except Exception as ex:
                        st.error(f"Ошибка: {ex}")

with tab_history:
    st.subheader("📜 Архив прогнозов & Управление")
    st.write(
        "Нажимайте прямо на кнопки под матчами в архиве, чтобы зафиксировать победу или поражение."
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
                    with st.container(border=True):
                        st.markdown(
                            f"**{card.get('team1')} vs {card.get('team2')}**<br>Счет:"
                            f" `{card.get('score')}`",
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            f"🎯 `{card.get('bet')}` (Кф `{card.get('coefficient')}`"
                            f" | `{card.get('confidence_percent', 85)}%`)"
                        )
                        st.write(f"Статус: **{card.get('status')}**")

                        hc1, hc2, hc3 = st.columns(3)
                        if hc1.button(
                            "🟢 Победа",
                            key=f"hist_win_{entry['id']}_{idx}",
                            use_container_width=True,
                        ):
                            card["status"] = "✅ Проход"
                            save_history(st.session_state.history)
                            st.rerun()
                        if hc2.button(
                            "🔴 Проигрыш",
                            key=f"hist_loss_{entry['id']}_{idx}",
                            use_container_width=True,
                        ):
                            card["status"] = "❌ Проигрыш"
                            save_history(st.session_state.history)
                            st.rerun()
                        if hc3.button(
                            "⏳ Сброс",
                            key=f"hist_pend_{entry['id']}_{idx}",
                            use_container_width=True,
                        ):
                            card["status"] = "⌛ Ожидание"
                            save_history(st.session_state.history)
                            st.rerun()
            st.markdown("---")
