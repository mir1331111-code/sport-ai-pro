import json
import os
import random
import re
from datetime import datetime, timezone

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

from google import genai
from google.genai import types
from groq import Groq
import requests
import streamlit as st

# --- АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ ---
if HAS_AUTOREFRESH:
    count = st_autorefresh(interval=900000, key="auto_sniper_refresh")

HISTORY_FILE = "match_history_clean.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "bets" in data:
                    return data.get("bets", [])
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
    page_title="Терминал прогнозов Совета ИИ", page_icon="⚡", layout="wide"
)

if "history" not in st.session_state:
    st.session_state.history = load_history()

SPORT_GROUPS = {
    "⚽ Футбол (Клубы и Сборные)": {
        "category": "soccer",
        "label": "АПЛ, Ла Лига, Серия А и Еврокубки",
    },
    "🏒 Хоккей": {"category": "hockey", "label": "НХЛ, КХЛ и матчи сборных"},
    "🏀 Баскетбол": {"category": "basketball", "label": "НБА и Евролига"},
    "🎾 Теннис": {"category": "tennis", "label": "ATP и WTA турниры"},
    "🏐 Волейбол": {"category": "volleyball", "label": "Лига Чемпионов ЕКВ"},
    "🤾 Гандбол": {"category": "handball", "label": "Европейские чемпионаты"},
    "🎮 Киберспорт": {"category": "esports", "label": "Counter-Strike 2 и Dota 2"},
}

SPORT_BACKGROUNDS = {
    "soccer": ["https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"],
    "basketball": ["https://images.unsplash.com/photo-1546519638-68e109498ffc?auto=format&fit=crop&w=1920&q=80"],
    "hockey": ["https://images.unsplash.com/photo-1580748141549-71748dbe0bdc?auto=format&fit=crop&w=1920&q=80"],
    "tennis": ["https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?auto=format&fit=crop&w=1920&q=80"],
    "volleyball": ["https://images.unsplash.com/photo-1612872087720-bb876e2e67d1?auto=format&fit=crop&w=1920&q=80"],
    "handball": ["https://images.unsplash.com/photo-1574629810360-7efbbe195018?auto=format&fit=crop&w=1920&q=80"],
    "esports": ["https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=1920&q=80"],
    "default": ["https://images.unsplash.com/photo-1517649763962-0c623266ddc0?auto=format&fit=crop&w=1920&q=80"],
}

def apply_custom_styles(theme_mode, sport_type="default"):
    bgs = SPORT_BACKGROUNDS.get(sport_type, SPORT_BACKGROUNDS["default"])
    bg1 = bgs[0]
    if theme_mode == "☀️ Светлая тема":
        css_code = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
            .stApp { background-color: #f8fafc !important; color: #0f172a; font-family: 'Plus Jakarta Sans', sans-serif; }
            .block-container { padding-top: 1.2rem; padding-bottom: 3rem; max-width: 98%; }
            .value-badge { color: #ffffff; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.8rem; display: inline-block; margin-bottom: 6px; background: #10b981; }
            .card-win { background: #ecfdf5 !important; border: 2px solid #10b981 !important; border-radius: 12px; padding: 14px; }
            .card-loss { background: #fef2f2 !important; border: 2px solid #ef4444 !important; border-radius: 12px; padding: 14px; }
            .card-default { background: #ffffff !important; border: 2px solid #cbd5e1 !important; border-radius: 12px; padding: 14px; }
            .stat-box { background: #ffffff; border: 1px solid #cbd5e1; padding: 12px; border-radius: 10px; text-align: center; }
        </style>
        """
    else:
        css_code = f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
            .stApp {{
                background-image: linear-gradient(rgba(8, 12, 22, 0.92), rgba(8, 12, 22, 0.96)), url("{bg1}");
                background-size: cover; background-attachment: fixed; background-position: center;
                color: #f1f5f9; font-family: 'Plus Jakarta Sans', sans-serif;
            }}
            .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 98%; }}
            .value-badge {{ color: #ffffff; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.80rem; display: inline-block; margin-bottom: 6px; background: #10b981; }}
            .card-win {{ background: rgba(16, 185, 129, 0.15) !important; border: 2px solid #10b981 !important; border-radius: 12px; padding: 14px; }}
            .card-loss {{ background: rgba(239, 68, 68, 0.15) !important; border: 2px solid #ef4444 !important; border-radius: 12px; padding: 14px; }}
            .card-default {{ background: rgba(30, 41, 59, 0.7) !important; border: 2px solid #475569 !important; border-radius: 12px; padding: 14px; }}
            .stat-box {{ background: rgba(30, 41, 59, 0.8); border: 1px solid #475569; padding: 12px; border-radius: 10px; text-align: center; }}
        </style>
        """
    st.markdown(css_code, unsafe_allow_html=True)

def send_telegram_message(token, chat_id, message):
    if not token or not chat_id:
        return False, "Не заполнен Telegram Token или Chat ID"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code == 200:
            return True, "Успешно отправлено в Telegram!"
        else:
            return False, f"Ошибка Telegram API: {r.text}"
    except Exception as e:
        return False, f"Ошибка сети: {e}"

def extract_json_safely(text):
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    cleaned = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned.strip())
    except Exception:
        pass

    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    return None

# --- МОДУЛЬ САМООБУЧЕНИЯ ---
def get_self_learning_context():
    resolved_bets = []
    wins = 0
    losses = 0
    for entry in st.session_state.history:
        for card in entry.get("data", []):
            status = card.get("status")
            if status == "✅ Проход":
                wins += 1
                resolved_bets.append(
                    f"[УСПЕХ] Матч: {card.get('team1')} vs {card.get('team2')} | Ставка: {card.get('bet')}"
                )
            elif status == "❌ Проигрыш":
                losses += 1
                resolved_bets.append(
                    f"[ОШИБКА] Матч: {card.get('team1')} vs {card.get('team2')} | Ставка: {card.get('bet')}"
                )

    total = wins + losses
    winrate = (wins / total * 100) if total > 0 else 0

    context_str = f"\n\n📊 СТАТИСТИКА САМООБУЧЕНИЯ (Всего сыграно: {total}, Винрейт: {winrate:.1f}%):\n"
    if resolved_bets:
        context_str += "Учитывай опыт прошлых прогнозов:\n"
        for b in resolved_bets[-12:]:
            context_str += f"- {b}\n"
    else:
        context_str += "История пуста.\n"

    return context_str

# --- ПОИСК МАТЧЕЙ ---
def fetch_and_analyze_matches(groq_key, gemini_key, sport_title, sport_desc, is_strategy=False):
    if not gemini_key and not groq_key:
        st.error("⚠️ Укажите хотя бы один API Key (Groq или Gemini) в боковой панели слева!", icon="🔑")
        return []

    learning_prompt_addition = get_self_learning_context()

    prompt = f"""
    Сегодня 14 сентября 2026 года. 
    Найди актуальные матчи в категории "{sport_title} ({sport_desc})".
    ВАЖНО: Ищи ценность (value betting), глубоко анализируй форму, а не гонись за слепыми низкими коэффициентами.
    {learning_prompt_addition}
    
    Верни СТРОГО JSON объект:
    {{
      "matches": [
        {{
          "team1": "Название первой команды",
          "team2": "Название второй команды",
          "coefficient_1": 1.85,
          "coefficient_2": 2.10,
          "bookmaker": "Fonbet",
          "recommended_bet": "Обоснованная ставка",
          "expert_probability": 78,
          "groq_analysis": "Глубокий разбор: анализ формы, факторов риска и обоснование."
        }}
      ]
    }}
    """

    raw_text = ""
    error_log = []

    if groq_key:
        try:
            client = Groq(api_key=groq_key)
            for g_model in ["llama-3.1-70b-versatile", "llama-3.1-8b-instant"]:
                try:
                    completion = client.chat.completions.create(
                        model=g_model,
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                        temperature=0.3,
                    )
                    raw_text = completion.choices[0].message.content
                    break
                except Exception as e:
                    error_log.append(f"Groq ({g_model}): {e}")
                    continue
        except Exception as e:
            error_log.append(f"Groq Init Error: {e}")

    if not raw_text and gemini_key:
        try:
            g_client = genai.Client(api_key=gemini_key)
            # ОБНОВЛЕННАЯ АКТУАЛЬНАЯ МОДЕЛЬ GOOGLE
            for g_model in ["gemini-3.6-flash"]:
                try:
                    response = g_client.models.generate_content(
                        model=g_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            tools=[{"google_search": {}}],
                            response_mime_type="application/json"
                        ),
                    )
                    if response and response.text:
                        raw_text = response.text.strip()
                        break
                except Exception as e:
                    error_log.append(f"Gemini ({g_model}): {e}")
                    continue
        except Exception as e:
            error_log.append(f"Gemini Init Error: {e}")

    parsed_data = extract_json_safely(raw_text)
    data_list = []
    if parsed_data and isinstance(parsed_data, dict):
        data_list = parsed_data.get("matches", [])

    if not data_list:
        details = " | ".join(error_log) if error_log else f"Сырой текст: {raw_text[:120]}"
        st.error(f"🚨 Ошибка получения матчей: {details}", icon="⚠️")
        return [{
            "sport_label": sport_title,
            "team1": "⚠️ Ошибка анализа",
            "team2": "проверьте ключи",
            "bet": "Нет данных",
            "coefficient": 1.0,
            "probability": 0,
            "bookmaker": "Система",
            "status": "⌛ Ожидание",
            "analysis": f"Детали: {details}",
        }]

    parsed_matches = []
    for item in data_list:
        t1 = item.get("team1", "Хозяева")
        t2 = item.get("team2", "Гости")
        p1 = float(item.get("coefficient_1", 1.85))
        p2 = float(item.get("coefficient_2", 2.10))
        bet = item.get("recommended_bet", f"Победа 1 ({t1})")
        chosen_odds = p1 if "1" in bet or t1 in bet else p2
        prob = int(item.get("expert_probability", 80))
        g_text = item.get("groq_analysis", "Анализ формы и обоснование выбора.")

        parsed_matches.append({
            "sport_label": f"🎯 Стратегия / Матч: {sport_title}" if is_strategy else sport_title,
            "team1": t1,
            "team2": t2,
            "bet": bet,
            "coefficient": chosen_odds,
            "probability": prob,
            "bookmaker": item.get("bookmaker", "БК"),
            "status": "⌛ Ожидание",
            "analysis": f"📊 Аналитика ИИ: {g_text}",
        })
    return parsed_matches

# --- МУЛЬТИМОДАЛЬНЫЙ АНАЛИЗ СКРИНШОТА С ЗАЩИТОЙ ОТ ОШИБОК КЛЮЧЕЙ ---
def analyze_screenshot_with_two_brains(gemini_key, groq_key, image):
    if gemini_key and gemini_key.startswith("gsk_") and not groq_key:
        groq_key = gemini_key
        gemini_key = ""

    if not gemini_key:
        if groq_key:
            return None, "⚠️ В поле Gemini API Key обнаружен ключ Groq (начинается с gsk_). Для анализа скриншотов нужен именно Gemini API Key из Google AI Studio (начинается с AIza...)."
        return None, "⚠️ Не указан Gemini API Key в боковой панели слева! Получите его бесплатно в Google AI Studio."

    learning_prompt_addition = get_self_learning_context()

    try:
        g_client = genai.Client(api_key=gemini_key)
        prompt = f"""
        Ты профессиональный спортивный аналитик и каппер.
        Внимательно изучи этот скриншот букмекерской конторы (найди названия игроков/команд, коэффициенты матча, сет-победы, тоталы).
        НЕ ГОНИСЬ за самыми низкими коэффициентами. Проанализируй ситуацию, форму и найди самую валуйную и обоснованную ставку.
        
        Верни результат СТРОГО в формате JSON без каких-либо вводных слов и пояснений снаружи:
        {{
          "team1": "Название первой команды или игрока",
          "team2": "Название второй команды или игрока",
          "sport": "Вид спорта (например, Теннис)",
          "recommended_bet": "Конкретная ставка с учетом анализа и коэффициентов со скриншота",
          "coefficient": 1.75,
          "probability": 78,
          "bookmaker": "Название БК со скриншота",
          "analysis": "Глубокий аналитический разбор: почему именно эта ставка выгодна и что видно на скриншоте."
        }}
        {learning_prompt_addition}
        """

        raw_text = ""
        last_error = ""
        # ОБНОВЛЕННАЯ АКТУАЛЬНАЯ МОДЕЛЬ GOOGLE
        for g_model in ["gemini-3.6-flash"]:
            try:
                response = g_client.models.generate_content(
                    model=g_model,
                    contents=[image, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    ),
                )
                if response and response.text:
                    raw_text = response.text.strip()
                    break
            except Exception as e:
                last_error = str(e)
                continue

        if not raw_text:
            if "API_KEY_INVALID" in last_error or "not valid" in last_error:
                return None, "❌ Ошибка: Указанный Gemini API Key недействителен. Проверьте правильность ключа в Google AI Studio."
            return None, f"Ошибка Gemini API: {last_error or 'Модель не вернула ответ'}"

        parsed = extract_json_safely(raw_text)
        if not parsed:
            return None, f"Не удалось распарсить JSON. Сырой текст ответа: {raw_text[:200]}"

        return parsed, None
    except Exception as e:
        err_str = str(e)
        if "API_KEY_INVALID" in err_str or "not valid" in err_str:
            return None, "❌ Ошибка: Неверный Gemini API Key. Убедитесь, что скопировали правильный ключ."
        return None, f"Критическая ошибка мультимодального анализа: {err_str}"

# --- САЙДБАР ---
st.sidebar.title("🎛️ Настройки терминала")
theme_choice = st.sidebar.selectbox(
    "Тема оформления:",
    ["🎨 Динамический спорт-фон", "☀️ Светлая тема", "🌙 Строгая темная"],
    index=0,
)

st.sidebar.title("🔑 API-ключи ИИ")
groq_api_key = st.sidebar.text_input("Groq API Key (Рекомендуется для текстов)", type="password", placeholder="gsk_...")
gemini_api_key = st.sidebar.text_input("Gemini API Key (Для скриншотов/поиска)", type="password", placeholder="AIzaSy...")

st.sidebar.title("🤖 Настройки Telegram")
tg_token = st.sidebar.text_input("Telegram Bot Token", type="password", placeholder="123456:ABC...")
tg_chat_id = st.sidebar.text_input("Telegram Chat ID", placeholder="-100...")

selected_window = st.sidebar.radio(
    "Переключение терминала:",
    [
        "🌍 Глобальный омниссканер",
        "📸 Скрин-аналитик (2 мозга)",
        "🎯 Стратегия: Камбэк фаворита (0:1)",
        "📥 Ручной инжектор",
        "⚽ Футбол (Клубы и Сборные)",
        "🏒 Хоккей",
        "🏀 Баскетбол",
        "🎾 Теннис",
        "🏐 Волейбол",
        "🤾 Гандбол",
        "🎮 Киберспорт",
        "📜 Общий Архив",
    ],
    index=0,
)

if st.sidebar.button("🔄 Очистить всю историю"):
    st.session_state.history = []
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    st.success("История очищена!")
    st.rerun()

window_mapping = {
    "⚽ Футбол (Клубы и Сборные)": ("⚽ Футбол (Клубы и Сборные)", SPORT_GROUPS["⚽ Футбол (Клубы и Сборные)"]),
    "🏒 Хоккей": ("🏒 Хоккей", SPORT_GROUPS["🏒 Хоккей"]),
    "🏀 Баскетбол": ("🏀 Баскетбол", SPORT_GROUPS["🏀 Баскетбол"]),
    "🎾 Теннис": ("🎾 Теннис", SPORT_GROUPS["🎾 Теннис"]),
    "🏐 Волейбол": ("🏐 Волейбол", SPORT_GROUPS["🏐 Волейбол"]),
    "🤾 Гандбол": ("🤾 Гандбол", SPORT_GROUPS["🤾 Гандбол"]),
    "🎮 Киберспорт": ("🎮 Киберспорт", SPORT_GROUPS["🎮 Киберспорт"]),
}

active_sport_cat = "default"
if selected_window in window_mapping:
    active_sport_cat = window_mapping[selected_window][1]["category"]
apply_custom_styles(theme_choice, active_sport_cat)

st.markdown("### ⚡ Терминал прогнозов Совета ИИ + Самообучение")
st.markdown("---")

def render_match_cards(entry, session_key_prefix):
    if not entry.get("data"):
        st.info("ℹ️ Список пуст. Запустите поиск выше.")
        return

    cols = st.columns(2)
    for idx, card in enumerate(entry.get("data", [])):
        status_val = card.get("status", "⌛ Ожидание")
        if status_val == "✅ Проход":
            status_class = "card-win"
        elif status_val == "❌ Проигрыш":
            status_class = "card-loss"
        else:
            status_class = "card-default"

        team1_val = card.get("team1", "")
        team2_val = card.get("team2", "")
        sport_lbl = card.get("sport_label", "")
        bk_val = card.get("bookmaker", "")
        bet_val = card.get("bet", "")
        coef_val = card.get("coefficient", 1.0)
        prob_val = card.get("probability", 80)
        analysis_val = card.get("analysis", "")

        with cols[idx % 2]:
            st.markdown(
                f"""
                <div class="{status_class}">
                    <span class="value-badge">💎 Валуй / Анализ ({prob_val}%)</span><br>
                    <b>{team1_val} vs {team2_val}</b><br>
                    <small>{sport_lbl} | БК: `{bk_val}` | Статус: {status_val}</small><hr style="margin:6px 0;">
                    <b>Рекомендуемая ставка:</b> {bet_val}<br>
                    <b>Вероятность прохода:</b> <b>{prob_val}%</b> (Кф: {coef_val})<br><br>
                    <div style="background: rgba(0,0,0,0.2); padding: 8px; border-radius: 6px; font-size: 0.9rem;">
                        {analysis_val}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            c1, c2, c3, c4 = st.columns(4)
            if c1.button("✅ Зашло", key=f"{session_key_prefix}_w_{entry['timestamp']}_{idx}"):
                card["status"] = "✅ Проход"
                save_history(st.session_state.history)
                st.rerun()
            if c2.button("❌ Мимо", key=f"{session_key_prefix}_l_{entry['timestamp']}_{idx}"):
                card["status"] = "❌ Проигрыш"
                save_history(st.session_state.history)
                st.rerun()
            if c3.button("📤 Телеграм", key=f"{session_key_prefix}_tg_{entry['timestamp']}_{idx}"):
                msg = (
                    f"🎯 *Прогноз ИИ* ({sport_lbl})\n"
                    f"⚔️ {team1_val} vs {team2_val}\n"
                    f"📌 Ставка: *{bet_val}*\n"
                    f"📈 Вероятность: {prob_val}% (Кф: `{coef_val}`)\n"
                    f"🏦 БК: {bk_val}\n\n"
                    f"💡 {analysis_val}"
                )
                success, msg_res = send_telegram_message(tg_token, tg_chat_id, msg)
                if success:
                    st.success("Отправлено в Telegram!")
                else:
                    st.error(msg_res)
            if c4.button("🗑 Удалить", key=f"{session_key_prefix}_d_{entry['timestamp']}_{idx}"):
                entry["data"].remove(card)
                save_history(st.session_state.history)
                st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)

# --- РАЗДЕЛЫ ---
if selected_window == "🌍 Глобальный омниссканер":
    st.header("🌍 Глобальный поиск надежных исходов")
    if st.button("🚀 Запустить глобальный сканер (с учетом самообучения)", use_container_width=True):
        with st.spinner("Сканирование топ-рынков..."):
            all_global = []
            for sport_name, sport_info in SPORT_GROUPS.items():
                matches = fetch_and_analyze_matches(
                    groq_api_key,
                    gemini_api_key,
                    sport_name,
                    sport_info["label"],
                    is_strategy=False,
                )
                all_global.extend(matches)

            if all_global:
                st.session_state.history.insert(
                    0,
                    {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "sport": "🌍 Глобальный рынок",
                        "data": all_global,
                    },
                )
                save_history(st.session_state.history)
                st.success(f"Анализ завершен! Найдено матчей: {len(all_global)}")
                st.rerun()

    for entry in [e for e in st.session_state.history if e.get("sport") == "🌍 Глобальный рынок"]:
        render_match_cards(entry, "glob")

elif selected_window == "📸 Скрин-аналитик (2 мозга)":
    st.header("📸 Загрузка скриншота матча (Глубокий анализ)")

    screen_entries = [e for e in st.session_state.history if e.get("sport") == "📸 Скрин-анализ"]
    total_screens = sum(len(e.get("data", [])) for e in screen_entries)
    screen_wins = sum(1 for e in screen_entries for c in e.get("data", []) if c.get("status") == "✅ Проход")
    screen_losses = sum(1 for e in screen_entries for c in e.get("data", []) if c.get("status") == "❌ Проигрыш")
    screen_winrate = ((screen_wins / (screen_wins + screen_losses) * 100) if (screen_wins + screen_losses) > 0 else 0)

    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.markdown(f'<div class="stat-box"><b>Всего скриншотов</b><br><h2>{total_screens}</h2></div>', unsafe_allow_html=True)
    sc2.markdown(f'<div class="stat-box"><b>Зашло (Win)</b><br><h2 style="color:#10b981;">{screen_wins}</h2></div>', unsafe_allow_html=True)
    sc3.markdown(f'<div class="stat-box"><b>Мимо (Loss)</b><br><h2 style="color:#ef4444;">{screen_losses}</h2></div>', unsafe_allow_html=True)
    sc4.markdown(f'<div class="stat-box"><b>Винрейт скриншотов</b><br><h2>{screen_winrate:.1f}%</h2></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    uploaded_file = st.file_uploader("Выберите скриншот (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"])

    if uploaded_file is not None and HAS_PIL:
        image = Image.open(uploaded_file)
        st.image(image, caption="Загруженный скриншот", use_container_width=True)

        if st.button("🧠 Запустить глубокий анализ скриншота", use_container_width=True):
            with st.spinner("ИИ проводит детальный разбор матча и коэффициентов..."):
                result_dict, err_msg = analyze_screenshot_with_two_brains(gemini_api_key, groq_api_key, image)
                if err_msg:
                    st.error(err_msg)
                elif result_dict:
                    card = {
                        "sport_label": f"📸 Скриншот: {result_dict.get('sport', 'Спорт')}",
                        "team1": result_dict.get("team1", "Хозяева"),
                        "team2": result_dict.get("team2", "Гости"),
                        "bet": result_dict.get("recommended_bet", "Победа 1"),
                        "coefficient": float(result_dict.get("coefficient", 1.65)),
                        "probability": int(result_dict.get("probability", 78)),
                        "bookmaker": result_dict.get("bookmaker", "Скриншот"),
                        "status": "⌛ Ожидание",
                        "analysis": result_dict.get("analysis", ""),
                    }

                    st.session_state.history.insert(
                        0,
                        {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "sport": "📸 Скрин-анализ",
                            "data": [card],
                        },
                    )
                    save_history(st.session_state.history)
                    st.success("Глубокий анализ скриншота завершен!")
                    st.rerun()

    for entry in screen_entries:
        render_match_cards(entry, "screen")

elif selected_window == "🎯 Стратегия: Камбэк фаворита (0:1)":
    st.header("🎯 Стратегия Live-камбэков с самообучением")
    if st.button("🚀 Найти ситуации для камбэка", use_container_width=True):
        with st.spinner("Сканирование Live-ситуаций..."):
            strategy_matches = []
            for s_name in ["🎾 Теннис", "🏐 Волейбол", "🏒 Хоккей"]:
                matches = fetch_and_analyze_matches(
                    groq_api_key,
                    gemini_api_key,
                    s_name,
                    SPORT_GROUPS[s_name]["label"],
                    is_strategy=True,
                )
                strategy_matches.extend(matches)

            if strategy_matches:
                st.session_state.history.insert(
                    0,
                    {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "sport": "🎯 Стратегия Камбэк",
                        "data": strategy_matches,
                    },
                )
                save_history(st.session_state.history)
                st.success(f"Найдено ситуаций: {len(strategy_matches)}")
                st.rerun()

    for entry in [e for e in st.session_state.history if e.get("sport") == "🎯 Стратегия Камбэк"]:
        render_match_cards(entry, "strat")

elif selected_window == "📥 Ручной инжектор":
    st.header("📥 Ручной ввод матча и аналитики")
    with st.form("manual_form"):
        c1, c2 = st.columns(2)
        with c1:
            t1 = st.text_input("Хозяева / Первая команда", "")
            o1 = st.number_input("Коэффициент", min_value=1.01, value=1.75)
        with c2:
            t2 = st.text_input("Гости / Вторая команда", "")
            o2 = st.number_input("Коэффициент (резерв)", min_value=1.01, value=2.10)
        sport_lbl = st.selectbox(
            "Вид спорта",
            ["⚽ Футбол", "🏒 Хоккей", "🏀 Баскетбол", "🎾 Теннис", "🏐 Волейбол", "🤾 Гандбол", "🎮 Киберспорт"],
        )
        manual_analysis = st.text_area("Аналитическое обоснование / Риски", "Валуйный анализ матча...")
        submitted = st.form_submit_button("⚡ Сохранить прогноз в базу обучения")

        if submitted:
            card = {
                "sport_label": sport_lbl,
                "team1": t1,
                "team2": t2,
                "bet": f"Выбор по анализу ({t1})",
                "coefficient": o1,
                "probability": 80,
                "bookmaker": "Ручной ввод",
                "status": "⌛ Ожидание",
                "analysis": f"📊 Ручной разбор: {manual_analysis}",
            }
            st.session_state.history.insert(
                0,
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "sport": "📥 Ручной ввод",
                    "data": [card],
                },
            )
            save_history(st.session_state.history)
            st.success("Прогноз добавлен и учтен в самообучении!")
            st.rerun()

    for entry in [e for e in st.session_state.history if e.get("sport") == "📥 Ручной ввод"]:
        render_match_cards(entry, "man")

elif selected_window in window_mapping:
    sport_title, sport_data = window_mapping[selected_window]
    st.header(f"Терминал: {sport_title}")

    if st.button(f"🚀 Найти валуйные исходы ({sport_title})", use_container_width=True):
        with st.spinner(f"Анализ матчей ({sport_title})..."):
            matches = fetch_and_analyze_matches(
                groq_api_key,
                gemini_api_key,
                sport_title,
                sport_data["label"],
                is_strategy=False,
            )
            if matches:
                st.session_state.history.insert(
                    0,
                    {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "sport": sport_title,
                        "data": matches,
                    },
                )
                save_history(st.session_state.history)
                st.success(f"Анализ завершен. Найдено прогнозов: {len(matches)}")
                st.rerun()

    for entry in [e for e in st.session_state.history if e.get("sport") == sport_title]:
        render_match_cards(entry, "sp")

elif selected_window == "📜 Общий Архив":
    st.subheader("📜 История и результаты матчей")
    if st.button("🗑 Очистить архив"):
        st.session_state.history = []
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
        st.rerun()

    for entry in st.session_state.history:
        st.caption(f"📅 Сессия от: {entry.get('timestamp')} | Раздел: {entry.get('sport')}")
        render_match_cards(entry, "arch")
        st.markdown("---")
