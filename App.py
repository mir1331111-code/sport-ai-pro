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

SPORTS_ENDPOINTS = [
    ("soccer", "eng.1", "⚽ АПЛ (Англия)", "soccer"),
    ("soccer", "esp.1", "⚽ Ла Лига (Испания)", "soccer"),
    ("soccer", "ger.1", "⚽ Бундеслига (Германия)", "soccer"),
    ("soccer", "ita.1", "⚽ Серия А (Италия)", "soccer"),
    ("soccer", "rus.1", "⚽ РПЛ (Россия)", "soccer"),
    ("basketball", "nba", "🏀 НБА (Баскетбол)", "basketball"),
    ("hockey", "nhl", "🏒 НХЛ (Хоккей)", "hockey"),
    ("tennis", "atp", "🎾 ATP Теннис", "tennis"),
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
            background: linear-gradient(rgba(8, 12, 22, 0.92), rgba(8, 12, 22, 0.96)), url("{bg_url}");
            background-size: cover;
            background-attachment: fixed;
            background-position: center;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }}
        .block-container {{ padding-top: 1.5rem; padding-bottom: 3rem; }}
        
        /* Метрики */
        div[data-testid="stMetric"] {{
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.08);
            padding: 14px 18px;
            border-radius: 14px;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }}
        div[data-testid="stMetricValue"] {{ font-size: 1.5rem; color: #00FF66; font-weight: 800; text-shadow: 0 0 10px rgba(0,255,102,0.3); }}
        div[data-testid="stMetricLabel"] {{ font-size: 0.8rem; opacity: 0.8; text-transform: uppercase; letter-spacing: 0.5px; }}

        /* Кнопки */
        .stButton>button {{
            border-radius: 10px;
            font-weight: 700;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }}
        .stButton>button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,255,102,0.25);
        }}

        /* Значки ценности */
        .value-badge {{
            background: linear-gradient(135deg, #059669 0%, #10b981 100%);
            color: #ffffff;
            padding: 4px 10px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 0.75rem;
            display: inline-block;
            margin-bottom: 8px;
            box-shadow: 0 2px 8px rgba(16, 185, 129, 0.4);
            letter-spacing: 0.3px;
        }}
        
        .score-badge-live {{
            background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);
            color: white;
            padding: 4px 10px;
            border-radius: 8px;
            font-weight: 800;
            font-size: 0.78rem;
            animation: pulse 2s infinite;
            display: inline-block;
            box-shadow: 0 0 12px rgba(239, 68, 68, 0.5);
        }}
        
        .stat-box {{
            background: rgba(30, 41, 59, 0.6);
            border-left: 3px solid #00FF66;
            padding: 10px 12px;
            border-radius: 6px;
            margin: 8px 0;
            font-size: 0.84rem;
            color: #f1f5f9;
            backdrop-filter: blur(6px);
        }}
        
        .loss-reason-box {{
            background: rgba(220, 38, 38, 0.15);
            border-left: 3px solid #ef4444;
            padding: 8px 12px;
            border-radius: 6px;
            margin: 6px 0;
            font-size: 0.82rem;
            color: #fca5a5;
        }}

        /* Вкладки */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 8px;
            background-color: rgba(15, 23, 42, 0.6);
            padding: 6px;
            border-radius: 14px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 10px;
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

    categorized = {}
    for m in raw_matches:
        cat = m["sport_category"]
        categorized.setdefault(cat, []).append(m)

    balanced_list = []
    sport_keys = list(categorized.keys())
    if sport_keys:
        max_per_cat = max(1, 10 // len(sport_keys))
        for cat in sport_keys:
            cat_items = categorized[cat]
            cat_items.sort(key=lambda x: not x["is_live"])
            balanced_list.extend(cat_items[:max_per_cat])

    random.shuffle(balanced_list)
    return balanced_list


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
failed_predictions = []

for item in st.session_state.history:
    for card in item.get("data", []):
        st_val = card.get("status", "⌛ Ожидание")
        if st_val == "✅ Проход":
            total_wins += 1
        elif st_val == "❌ Проигрыш":
            total_losses += 1
            user_note = card.get("user_loss_reason", "Неустановленный фактор")
            failed_predictions.append(
                f"Игра: {card.get('team1')} vs {card.get('team2')} | Ставка:"
                f" {card.get('bet')} | Причина провала: {user_note} | Анализ:"
                f" {card.get('reason')}"
            )

total_finished = total_wins + total_losses
win_rate = (total_wins / total_finished * 100) if total_finished > 0 else 0.0

st.title("🎯 Auto-Sniper Pro Terminal")
st.caption(
    "Интеллектуальная система аналитики и отбора валуйных событий (КФ $\\ge$"
    " 1.40)"
)

s_c1, s_c2, s_c3, s_c4, s_c5 = st.columns(5)
s_c1.metric("📊 Win Rate", f"{win_rate:.1f}%")
s_c2.metric("🟢 Победы", f"{total_wins}")
s_c3.metric("🔴 Поражения", f"{total_losses}")
s_c4.metric("🧠 База ошибок", f"{len(failed_predictions)}")

if s_c5.button("🔄 Синхролайн", use_container_width=True):
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
        st.success(
            f"Обновлено: {updated_count} | Рассчитано ставок: {settled_count}"
        )
        st.rerun()

st.markdown("---")

tab_current, tab_manual, tab_history = st.tabs([
    "🔥 Авто-Сканер Линии",
    "✏️ Ручной Ввод События",
    "📜 Архив & Центр Обучения",
])

with tab_current:
    today_date = datetime.date.today().strftime("%d.%m.%Y")
    current_time = datetime.datetime.now().strftime("%H:%M")

    c_input1, c_input2 = st.columns([3, 1])
    with c_input1:
        num_signals = st.slider("Количество событий в выборке:", 1, 4, 2)
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
                "Сканируем линии, фильтруем завершенные матчи и отбираем кф"
                " от 1.40..."
            ):
                try:
                    real_matches = fetch_all_sports_matches()

                    if not real_matches:
                        st.warning(
                            "⚠️ Нет активных матчей. Воспользуйтесь вкладкой"
                            " «✏️ Ручной Ввод События»!"
                        )
                    else:
                        match_lines = [
                            f"{idx+1}. [{rm['sport_label']}] {rm['team1']} VS {rm['team2']} | Текущий счет: {rm['score']} | Фаза: {rm['game_phase']} | Статус: {rm['status']}"
                            for idx, rm in enumerate(real_matches[:12])
                        ]
                        context_text = (
                            "ДОСТУПНЫЕ ПРЕДСТОЯЩИЕ И LIVE СОБЫТИЯ:\n"
                            + "\n".join(match_lines)
                        )

                        loss_context = ""
                        if failed_predictions:
                            loss_context = (
                                "\n\n🚨 БЛОК ОБУЧЕНИЯ НА ПРОШЛЫХ ОШИБКАХ (НЕ"
                                " ПОВТОРЯТЬ!):\n"
                                + "\n".join(failed_predictions[-6:])
                            )

                        base_prompt = f"""
Сегодня {today_date}, время {current_time} МСК.

{context_text}
{loss_context}

КРИТИЧЕСКИЕ ПРАВИЛА АНАЛИЗА:
1. ИСКЛЮЧИТЕЛЬНО предстоящие матчи или текущие LIVE. Никаких завершенных игр!
2. ЖЕСТКОЕ ТРЕБОВАНИЕ К КОЭФФИЦИЕНТУ: Коэффициент каждого прогноза должен быть СТРОГО ОТ 1.40 и выше! Никаких низких кф (1.10 - 1.35) предлагать нельзя. Если надежный исход идет ниже 1.40, ищи другой маркет с кф >= 1.40 (форы, индивидуальные тоталы, рискованные исходы с валуем).
3. Разнообразь виды спорта, если в списке есть выбор.

Верни СТРОГО JSON формата:
{{
  "matches": [
    {{
      "team1": "Команда 1",
      "team2": "Команда 2",
      "league": "Лига / Вид спорта",
      "time_status": "Время или LIVE статус",
      "game_phase": "до перерыва OR после перерыва",
      "score": "Счет",
      "bet_type": "Тип маркета",
      "bet": "Ставка (например: ТБ 2.5, П1, Ф1(-1))",
      "coefficient": "1.85",
      "confidence_percent": 82,
      "value_tag": "🛡️ Топ-Валуй | 💎 Снайперский выбор | ⚡ Профит-Пик",
      "x_factor": "🔥 Ключевой инсайд или фактор",
      "tactical_summary": "🧠 Тактический разбор формы",
      "key_stat": "📊 Главная цифра матча",
      "reason": "Единое экспертное обоснование"
    }}
  ]
}}
"""

                        raw_response = ""
                        if ai_mode == "🧠 Только Groq AI":
                            client = Groq(api_key=groq_api_key)
                            comp = client.chat.completions.create(
                                model=selected_groq_model
                           
