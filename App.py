from datetime import datetime, timezone
import json
import os
import random
from groq import Groq
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# --- АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ ---
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
    page_title="Syndicate Pro: Groq Match Scanner", page_icon="⚡", layout="wide"
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
    "soccer": [
        "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"
    ],
    "basketball": [
        "https://images.unsplash.com/photo-1546519638-68e109498ffc?auto=format&fit=crop&w=1920&q=80"
    ],
    "hockey": [
        "https://images.unsplash.com/photo-1580748141549-71748dbe0bdc?auto=format&fit=crop&w=1920&q=80"
    ],
    "tennis": [
        "https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?auto=format&fit=crop&w=1920&q=80"
    ],
    "volleyball": [
        "https://images.unsplash.com/photo-1612872087720-bb876e2e67d1?auto=format&fit=crop&w=1920&q=80"
    ],
    "handball": [
        "https://images.unsplash.com/photo-1574629810360-7efbbe195018?auto=format&fit=crop&w=1920&q=80"
    ],
    "esports": [
        "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=1920&q=80"
    ],
    "default": [
        "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?auto=format&fit=crop&w=1920&q=80"
    ],
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
            .value-badge { color: #ffffff; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.8rem; display: inline-block; margin-bottom: 6px; background: #3b82f6; }
            .card-win { background: #ecfdf5 !important; border: 2px solid #10b981 !important; border-radius: 12px; padding: 14px; }
            .card-loss { background: #fef2f2 !important; border: 2px solid #ef4444 !important; border-radius: 12px; padding: 14px; }
            .card-default { background: #ffffff !important; border: 2px solid #cbd5e1 !important; border-radius: 12px; padding: 14px; }
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
            .value-badge {{ color: #ffffff; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.8rem; display: inline-block; margin-bottom: 6px; background: #3b82f6; }}
            .card-win {{ background: rgba(16, 185, 129, 0.15) !important; border: 2px solid #10b981 !important; border-radius: 12px; padding: 14px; }}
            .card-loss {{ background: rgba(239, 68, 68, 0.15) !important; border: 2px solid #ef4444 !important; border-radius: 12px; padding: 14px; }}
            .card-default {{ background: rgba(30, 41, 59, 0.7) !important; border: 2px solid #475569 !important; border-radius: 12px; padding: 14px; }}
        </style>
        """
  st.markdown(css_code, unsafe_allow_html=True)


# --- ПОИСК МАТЧЕЙ И АНАЛИЗ ЧЕРЕЗ GROQ ---
def fetch_real_matches_consensus(groq_key, sport_title, sport_desc):
  if not groq_key:
    st.warning("Введите Groq API ключ в сайдбаре слева!")
    return []

  prompt = f"""
    Ты — главный спортивный сканер и аналитический ИИ. Текущая дата: сентябрь 2026 года.
    Найди и составь список из 4-5 АКТУАЛЬНЫХ матчей, которые пройдут в ближайшие дни в категории: "{sport_title} ({sport_desc})".
    Для каждого матча укажи реальные команды, актуальные букмекерские коэффициенты, рекомендуемую ставку, вероятность прохода (%) и подробный аналитический разбор.
    Верни СТРОГО чистый JSON (без маркдауна, без тегов ```json), в виде объекта с ключом "matches":
    {{
      "matches": [
        {{
          "team1": "Название команды 1",
          "team2": "Название команды 2",
          "coefficient_1": 1.85,
          "coefficient_2": 3.90,
          "bookmaker": "Fonbet / Pinnacle",
          "recommended_bet": "Победа 1 (название)",
          "expert_probability": 72,
          "groq_analysis": "Тактический анализ формы и мотивации команд (2 предложения)",
          "gemini_analysis": "Статистический разбор и оценка рисков (2 предложения)"
        }}
      ]
    }}
    """

  try:
    client = Groq(api_key=groq_key)
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    raw_text = completion.choices[0].message.content
  except Exception as e:
    st.error(f"Ошибка подключения к Groq API: {e}")
    return []

  if not raw_text:
    st.error("Groq вернул пустой ответ.")
    return []

  try:
    clean_json = raw_text.strip()
    if clean_json.startswith("```"):
      clean_json = clean_json.split("```")[1]
      if clean_json.startswith("json"):
        clean_json = clean_json[4:]

    parsed_data = json.loads(clean_json.strip())

    data_list = []
    if isinstance(parsed_data, dict):
      data_list = parsed_data.get("matches", [])
      if not data_list:
        for k, v in parsed_data.items():
          if isinstance(v, list):
            data_list = v
            break
    elif isinstance(parsed_data, list):
      data_list = parsed_data

    parsed_matches = []
    for item in data_list:
      t1 = item.get("team1", "Команда 1")
      t2 = item.get("team2", "Команда 2")
      p1 = float(item.get("coefficient_1", 1.85))
      p2 = float(item.get("coefficient_2", 2.10))
      bet = item.get("recommended_bet", f"Победа 1 ({t1})")
      chosen_odds = p1 if "1" in bet or t1 in bet else p2
      prob = int(item.get("expert_probability", 70))

      g_text = item.get("groq_analysis", "Анализ формы команд.")
      gem_text = item.get("gemini_analysis", "Статистический расчет.")
      analysis_comment = f"🤖 Groq: {g_text} | 💎 Аналитик: {gem_text}"

      parsed_matches.append({
          "sport_label": sport_title,
          "team1": t1,
          "team2": t2,
          "bet": bet,
          "coefficient": chosen_odds,
          "probability": prob,
          "bookmaker": item.get("bookmaker", "БК"),
          "status": "⌛ Ожидание",
          "analysis": analysis_comment,
      })
    return parsed_matches
  except Exception as e:
    st.error(f"Ошибка обработки ответа ИИ: {e}")
    return []


# --- САЙДБАР ---
st.sidebar.title("🎛️ Настройки терминала")
theme_choice = st.sidebar.selectbox(
    "Тема оформления:",
    ["🎨 Динамический спорт-фон", "☀️ Светлая тема", "🌙 Строгая темная"],
    index=0,
)

st.sidebar.title("🔑 API-ключ Groq")
groq_api_key = st.sidebar.text_input(
    "Groq API Key (Llama 3.3)", type="password", placeholder="gsk_..."
)

selected_window = st.sidebar.radio(
    "Переключение терминала:",
    [
        "🌍 Глобальный омниссканер",
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
    "⚽ Футбол (Клубы и Сборные)": (
        "⚽ Футбол (Клубы и Сборные)",
        SPORT_GROUPS["⚽ Футбол (Клубы и Сборные)"],
    ),
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

st.markdown("### ⚡ Терминал сканирования матчей (Groq Llama 3.3)")
st.markdown("---")


def render_match_cards(entry, session_key_prefix):
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
    
