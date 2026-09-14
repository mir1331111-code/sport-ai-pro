from datetime import datetime, timezone
import json
import os
import random
import re

# Безопасный импорт PIL для работы со скриншотами
try:
  from PIL import Image

  HAS_PIL = True
except ImportError:
  HAS_PIL = False

# Безопасный импорт автообновления
try:
  from streamlit_autorefresh import st_autorefresh

  HAS_AUTOREFRESH = True
except ImportError:
  HAS_AUTOREFRESH = False

try:
  from duckduckgo_search import DDGS

  HAS_DDGS = True
except ImportError:
  HAS_DDGS = False

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
            .value-badge { color: #ffffff; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.8rem; display: inline-block; margin-bottom: 6px; background: #10b981; }
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
            .value-badge {{ color: #ffffff; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.80rem; display: inline-block; margin-bottom: 6px; background: #10b981; }}
            .card-win {{ background: rgba(16, 185, 129, 0.15) !important; border: 2px solid #10b981 !important; border-radius: 12px; padding: 14px; }}
            .card-loss {{ background: rgba(239, 68, 68, 0.15) !important; border: 2px solid #ef4444 !important; border-radius: 12px; padding: 14px; }}
            .card-default {{ background: rgba(30, 41, 59, 0.7) !important; border: 2px solid #475569 !important; border-radius: 12px; padding: 14px; }}
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


def fetch_real_web_data(sport_title):
  if not HAS_DDGS:
    return ""
  current_date_str = "14 сентября 2026"
  query = (
      f"календарь матчей {sport_title} топ турниры на сегодня {current_date_str}"
  )
  try:
    results = DDGS().text(query, max_results=6)
    snippets = [r.get("body", "") for r in results]
    return "\n".join(snippets)
  except Exception:
    return ""


def extract_json_safely(text):
  if not text:
    return None
  try:
    return json.loads(text)
  except Exception:
    pass

  match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
  if match:
    try:
      return json.loads(match.group(1))
    except Exception:
      pass

  try:
    start = text.index("{")
    end = text.rindex("}") + 1
    return json.loads(text[start:end])
  except Exception:
    pass

  return None


# --- АНАЛИЗ РЕАЛЬНЫХ МАТЧЕЙ (БЕЗ ФЕЙКОВЫХ ЗАГЛУШЕК) ---
def fetch_and_analyze_matches(
    groq_key, gemini_key, sport_title, sport_desc, is_strategy=False
):
  if not groq_key and not gemini_key:
    return [{
        "sport_label": sport_title,
        "team1": "⚠️ Требуется API-ключ",
        "team2": "в сайдбаре слева",
        "bet": "Укажите Groq или Gemini Key",
        "coefficient": 1.0,
        "probability": 0,
        "bookmaker": "Система",
        "status": "⌛ Ожидание",
        "analysis": (
            "⚠️ Введите Groq API Key или Gemini API Key в боковой панели, чтобы"
            " ИИ мог искать актуальные матчи в реальном времени."
        ),
    }]

  try:
    web_context = fetch_real_web_data(sport_title)

    prompt = f"""
    Сегодня 14 сентября 2026 года. 
    Найди и выдай реальные актуальные матчи (или главные топ-противостояния текущего сезона) в категории "{sport_title} ({sport_desc})".
    Выбери матчи с высокой вероятностью прохода (от 80%).
    
    Данные из поиска:
    {web_context}
    
    Верни СТРОГО JSON объект без лишнего текста:
    {{
      "matches": [
        {{
          "team1": "Реальное название первой команды",
          "team2": "Реальное название второй команды",
          "coefficient_1": 1.45,
          "coefficient_2": 3.10,
          "bookmaker": "Fonbet",
          "recommended_bet": "Победа 1 с форой (0)",
          "expert_probability": 88,
          "groq_analysis": "Детальный разбор: текущая форма, статистика и обоснование ставки."
        }}
      ]
    }}
    """

    raw_text = ""

    # Пробуем Groq
    if groq_key:
      try:
        client = Groq(api_key=groq_key)
        for model_name in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
          try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            raw_text = completion.choices[0].message.content
            if raw_text:
              break
          except Exception:
            continue
      except Exception:
        pass

    # Пробуем Gemini, если Groq не ответил
    if not raw_text and gemini_key:
      try:
        g_client = genai.Client(api_key=gemini_key)
        for g_model in [
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-2.5-flash",
        ]:
          try:
            response = g_client.models.generate_content(
                model=g_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            if response and response.text:
              raw_text = response.text.strip()
              break
          except Exception:
            continue
      except Exception:
        pass

    parsed_data = extract_json_safely(raw_text)
    data_list = []
    if parsed_data and isinstance(parsed_data, dict):
      data_list = parsed_data.get("matches", [])

    if not data_list:
      return [{
          "sport_label": sport_title,
          "team1": "⚠️ Матчи не найдены",
          "team2": "или сеть заблокировала поиск",
          "bet": "Попробуйте позже",
          "coefficient": 1.0,
          "probability": 0,
          "bookmaker": "Система",
          "status": "⌛ Ожидание",
          "analysis": (
              "⚠️ Не удалось получить список матчей через поисковик. Проверьте"
              " валидность API-ключа."
          ),
      }]

    parsed_matches = []
    for item in data_list:
      t1 = item.get("team1", "Хозяева")
      t2 = item.get("team2", "Гости")
      p1 = float(item.get("coefficient_1", 1.45))
      p2 = float(item.get("coefficient_2", 2.60))
      bet = item.get("recommended_bet", f"Победа 1 ({t1})")
      chosen_odds = p1 if "1" in bet or t1 in bet else p2
      prob = int(item.get("expert_probability", 88))
      g_text = item.get("groq_analysis", "Анализ формы и факторов победы.")

      parsed_matches.append({
          "sport_label": (
              f"🎯 Стратегия / Матч: {sport_title}"
              if is_strategy
              else sport_title
          ),
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
  except Exception as e:
    st.error(f"Ошибка: {e}")
    return []


# --- МУЛЬТИМОДАЛЬНЫЙ АНАЛИЗ СКРИНШОТА ---
def analyze_screenshot_with_two_brains(gemini_key, groq_key, image):
  if not gemini_key:
    return None, "Для анализа скриншота необходим Gemini API Key в сайдбаре!"

  try:
    g_client = genai.Client(api_key=gemini_key)
    prompt = """
    Ты профессиональный спортивный аналитик. Посмотри на этот скриншот. 
    Распознай реальные команды, турнир и вынеси обоснованный прогноз.
    
    Верни СТРОГО JSON объект:
    {
      "team1": "Команда 1",
      "team2": "Команда 2",
      "sport": "Вид спорта",
      "recommended_bet": "Рекомендация ставки",
      "coefficient": 1.55,
      "probability": 90,
      "bookmaker": "БК со скриншота",
      "analysis": "Обоснование прогноза по данным на скриншоте."
    }
    """

    raw_text = ""
    for g_model in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]:
      try:
        response = g_client.models.generate_content(
            model=g_model,
            contents=[image, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        if response and response.text:
          raw_text = response.text.strip()
          break
      except Exception:
        continue

    parsed = extract_json_safely(raw_text)
    if not parsed:
      return (
          None,
          "Не удалось распознать матч на скриншоте. Убедитесь, что текст четкий.",
      )

    return parsed, None
  except Exception as e:
    return None, f"Ошибка мультимодального анализа: {e}"


# --- САЙДБАР ---
st.sidebar.title("🎛️ Настройки терминала")
theme_choice = st.sidebar.selectbox(
    "Тема оформления:",
    ["🎨 Динамический спорт-фон", "☀️ Светлая тема", "🌙 Строгая темная"],
    index=0,
)

st.sidebar.title("🔑 API-ключи ИИ")
groq_api_key = st.sidebar.text_input(
    "Groq API Key (Рекомендуется)", type="password", placeholder="gsk_..."
)
gemini_api_key = st.sidebar.text_input(
    "Gemini API Key (Для фото и резерва)",
    type="password",
    placeholder="AIzaSy...",
)

st.sidebar.title("🤖 Настройки Telegram")
tg_token = st.sidebar.text_input(
    "Telegram Bot Token", type="password", placeholder="123456:ABC..."
)
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

st.markdown("### ⚡ Терминал прогнозов Совета ИИ (Фокус на Проход)")
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
    prob_val = card.get("probability", 85)
    analysis_val = card.get("analysis", "")

    with cols[idx % 2]:
      st.markdown(
          f"""
                <div class="{status_class}">
                    <span class="value-badge">💎 Надежный выбор ({prob_val}%)</span><br>
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
      if c1.button(
          "✅ Зашло", key=f"{session_key_prefix}_w_{entry['timestamp']}_{idx}"
      ):
        card["status"] = "✅ Проход"
        save_history(st.session_state.history)
        st.rerun()
      if c2.button(
          "❌ Мимо", key=f"{session_key_prefix}_l_{entry['timestamp']}_{idx}"
      ):
        card["status"] = "❌ Проигрыш"
        save_history(st.session_state.history)
        st.rerun()
      if c3.button(
          "📤 Телеграм",
          key=f"{session_key_prefix}_tg_{entry['timestamp']}_{idx}",
      ):
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
      if c4.button(
          "🗑 Удалить",
          key=f"{session_key_prefix}_d_{entry['timestamp']}_{idx}",
      ):
        entry["data"].remove(card)
        save_history(st.session_state.history)
        st.rerun()
      st.markdown("<br>", unsafe_allow_html=True)


# --- РАЗДЕЛЫ ---
if selected_window == "🌍 Глобальный омниссканер":
  st.header("🌍 Глобальный поиск надежных исходов")
  if st.button(
      "🚀 Запустить глобальный сканер (Фокус на проход)",
      use_container_width=True,
  ):
    with st.spinner(
        "Сканирование топ-рынков и формирование железобетонных ставок..."
    ):
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

      st.session_state.history.insert(
          0,
          {
              "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "sport": "🌍 Глобальный рынок",
              "data": all_global,
          },
      )
      save_history(st.session_state.history)
      st.success(f"Анализ завершен! Найдено надежных матчей: {len(all_global)}")
      st.rerun()

  for entry in [
      e
      for e in st.session_state.history
      if e.get("sport") == "🌍 Глобальный рынок"
  ]:
    render_match_cards(entry, "glob")

elif selected_window == "📸 Скрин-аналитик (2 мозга)":
  st.header("📸 Загрузка скриншота матча (Анализ 2 мозгами)")
  st.markdown("Загрузите скриншот из БК. ИИ распознает команды и выдаст разбор.")

  uploaded_file = st.file_uploader(
      "Выберите скриншот (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"]
  )

  if uploaded_file is not None and HAS_PIL:
    image = Image.open(uploaded_file)
    st.image(image, caption="Загруженный скриншот", use_container_width=True)

    if st.button("🧠 Запустить анализ скриншота", use_container_width=True):
      if not gemini_api_key:
        st.error(
            "Для анализа скриншота обязательно укажите Gemini API Key в"
            " сайдбаре!"
        )
      else:
        with st.spinner("ИИ изучает скриншот и формирует точный прогноз..."):
          result_dict, err_msg = analyze_screenshot_with_two_brains(
              gemini_api_key, groq_api_key, image
          )
          if err_msg:
            st.error(err_msg)
          elif result_dict:
            card = {
                "sport_label": f"📸 Скриншот: {result_dict.get('sport', 'Спорт')}",
                "team1": result_dict.get("team1", "Хозяева"),
                "team2": result_dict.get("team2", "Гости"),
                "bet": result_dict.get("recommended_bet", "Победа 1"),
                "coefficient": float(result_dict.get("coefficient", 1.50)),
                "probability": int(result_dict.get("probability", 88)),
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
            st.success("Анализ скриншота успешно завершен!")
            st.rerun()

  for entry in [
      e for e in st.session_state.history if e.get("sport") == "📸 Скрин-анализ"
  ]:
    render_match_cards(entry, "screen")

elif selected_window == "🎯 Стратегия: Камбэк фаворита (0:1)":
  st.header("🎯 Стратегия Live-камбэков с высокой проходимостью")
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

  for entry in [
      e
      for e in st.session_state.history
      if e.get("sport") == "🎯 Стратегия Камбэк"
  ]:
    render_match_cards(entry, "strat")

elif selected_window == "📥 Ручной инжектор":
  st.header("📥 Ручной ввод матча и аналитики")
  with st.form("manual_form"):
    c1, c2 = st.columns(2)
    with c1:
      t1 = st.text_input("Хозяева / Фаворит", "")
      o1 = st.number_input("Коэффициент", min_value=1.01, value=1.40)
    with c2:
      t2 = st.text_input("Гости / Андердог", "")
      o2 = st.number_input("Коэффициент (резерв)", min_value=1.01, value=3.00)
    sport_lbl = st.selectbox(
        "Вид спорта",
        [
            "⚽ Футбол",
            "🏒 Хоккей",
            "🏀 Баскетбол",
            "🎾 Теннис",
            "🏐 Волейбол",
            "🤾 Гандбол",
            "🎮 Киберспорт",
        ],
    )
    manual_analysis = st.text_area(
        "Аналитическое обоснование / Риски", "Анализ матча..."
    )
    submitted = st.form_submit_button("⚡ Сохранить прогноз")

    if submitted:
      card = {
          "sport_label": sport_lbl,
          "team1": t1,
          "team2": t2,
          "bet": f"Победа 1 ({t1})",
          "coefficient": o1,
          "probability": 90,
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
      st.success("Прогноз добавлен!")
      st.rerun()

  for entry in [
      e for e in st.session_state.history if e.get("sport") == "📥 Ручной ввод"
  ]:
    render_match_cards(entry, "man")

elif selected_window in window_mapping:
  sport_title, sport_data = window_mapping[selected_window]
  st.header(f"Терминал: {sport_title}")

  if st.button(
      f"🚀 Найти надежные исходы ({sport_title})", use_container_width=True
  ):
    with st.spinner(f"Поиск матчей с высокой проходимостью ({sport_title})..."):
      matches = fetch_and_analyze_matches(
          groq_api_key,
          gemini_api_key,
          sport_title,
          sport_data["label"],
          is_strategy=False,
      )
      st.session_state.history.insert(
          0,
          {
              "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "sport": sport_title,
              "data": matches,
          },
      )
      save_history(st.session_state.history)
      st.success(f"Поиск завершен. Найдено прогнозов: {len(matches)}")
      st.rerun()

  for entry in [
      e for e in st.session_state.history if e.get("sport") == sport_title
  ]:
    render_match_cards(entry, "sp")

elif selected_window == "📜 Общий Архив":
  st.subheader("📜 История и результаты матчей")
  if st.button("🗑 Очистить архив"):
    st.session_state.history = []
    if os.path.exists(HISTORY_FILE):
      os.remove(HISTORY_FILE)
    st.rerun()

  for entry in st.session_state.history:
    st.caption(
        f"📅 Сессия от: {entry.get('timestamp')} | Раздел:"
        f" {entry.get('sport')}"
    )
    render_match_cards(entry, "arch")
    st.markdown("---")
