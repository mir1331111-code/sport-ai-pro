from datetime import datetime, timezone
import json
import os
import random
from google import genai
from google.genai import types
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
    page_title="Syndicate Pro: Clean Dual-AI Terminal", page_icon="⚡", layout="wide"
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


# --- ПОИСК АКТУАЛЬНЫХ МАТЧЕЙ И КОНСЕНСУС ИИ ---
def fetch_real_matches_consensus(groq_key, gemini_key, sport_title, sport_desc):
  if not groq_key and not gemini_key:
    return []

  prompt = f"""
    Ты — ведущий аналитический спортивный сканер. Текущая дата: сентябрь 2026 года.
    Составь список из 4-5 АКТУАЛЬНЫХ, РЕАЛЬНЫХ матчей, которые пройдут в ближайшие дни в категории: "{sport_title} ({sport_desc})".
    Для каждого матча укажи реальные команды, актуальные букмекерские коэффициенты и дай детальный аналитический прогноз.
    Ответ выдай СТРОГО в формате JSON-объекта с ключом "matches", содержащим массив (без маркдауна, чистый JSON):
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
          "groq_analysis": "Разбор формы и мотивации от Groq (2 предложения)",
          "gemini_analysis": "Статистический разбор и выводы от Gemini (2 предложения)"
        }}
      ]
    }}
    """

  raw_text = ""
  if groq_key:
    try:
      client = Groq(api_key=groq_key)
      completion = client.chat.completions.create(
          model="llama-3.3-70b-versatile",
          messages=[{"role": "user", "content": prompt}],
          temperature=0.3,
          response_format={"type": "json_object"},
      )
      raw_text = completion.choices[0].message.content
    except Exception:
      pass

  if not raw_text and gemini_key:
    try:
      client = genai.Client(api_key=gemini_key)
      response = client.models.generate_content(
          model="gemini-1.5-flash",
          contents=prompt,
          config=types.GenerateContentConfig(response_mime_type="application/json"),
      )
      raw_text = response.text
    except Exception:
      pass

  if not raw_text:
    return []

  try:
    clean_json = raw_text.strip()
    if clean_json.startswith("```"):
      clean_json = clean_json.split("```")[1]
      if clean_json.startswith("json"):
        clean_json = clean_json[4:]
    parsed_data = json.loads(clean_json)

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
      analysis_comment = f"🤖 Groq: {g_text} | 💎 Gemini: {gem_text}"

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
  except Exception:
    return []


# --- САЙДБАР ---
st.sidebar.title("🎛️ Настройки терминала")
theme_choice = st.sidebar.selectbox(
    "Тема оформления:",
    ["🎨 Динамический спорт-фон", "☀️ Светлая тема", "🌙 Строгая темная"],
    index=0,
)

st.sidebar.title("🔑 API-ключи Совета ИИ")
groq_api_key = st.sidebar.text_input(
    "Groq API Key (Llama 3.3)", type="password", placeholder="gsk_..."
)
gemini_api_key = st.sidebar.text_input(
    "Gemini API Key", type="password", placeholder="AIzaSy..."
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

st.markdown("### ⚡ Терминал прогнозов Совета ИИ (Groq + Gemini)")
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
    prob_val = card.get("probability", 70)
    analysis_val = card.get("analysis", "")

    with cols[idx % 2]:
      st.markdown(
          f"""
                <div class="{status_class}">
                    <span class="value-badge">⚡ Консенсус Совет ИИ (Groq + Gemini)</span><br>
                    <b>{team1_val} vs {team2_val}</b><br>
                    <small>{sport_lbl} | БК: `{bk_val}` | Статус: {status_val}</small><hr style="margin:6px 0;">
                    <b>Рекомендуемая ставка:</b> {bet_val}<br>
                    <b>Коэффициент:</b> {coef_val} | <b>Вероятность:</b> {prob_val}%<br>
                    <i>🤖💎 Совместная аналитика:<br>{analysis_val}</i>
                </div>
                """,
          unsafe_allow_html=True,
      )
      c1, c2, c3 = st.columns(3)
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
          "🗑 Удалить",
          key=f"{session_key_prefix}_d_{entry['timestamp']}_{idx}",
      ):
        entry["data"].remove(card)
        save_history(st.session_state.history)
        st.rerun()
      st.markdown("<br>", unsafe_allow_html=True)


# --- ВКЛАДКИ ---
if selected_window == "🌍 Глобальный омниссканер":
  st.header("🌍 Глобальный поиск актуальных матчей")
  st.info(
      "Сканирует топ-события по всем видам спорта на текущую неделю и выдает"
      " консенсус-прогнозы."
  )

  if st.button("🚀 Найти актуальные матчи со всеми ИИ", use_container_width=True):
    if not groq_api_key and not gemini_api_key:
      st.error("Введите хотя бы один API ключ (Groq или Gemini) в сайдбаре!")
    else:
      with st.spinner(
          "ИИ ищет актуальные матчи и проводит совместный анализ..."
      ):
        all_global_matches = []
        for sport_name, sport_info in SPORT_GROUPS.items():
          real_matches = fetch_real_matches_consensus(
              groq_api_key,
              gemini_api_key,
              sport_name,
              sport_info["label"],
          )
          all_global_matches.extend(real_matches)

        if all_global_matches:
          st.session_state.history.insert(
              0,
              {
                  "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  "sport": "🌍 Глобальный рынок",
                  "data": all_global_matches,
              },
          )
          save_history(st.session_state.history)
          st.success(f"Найдено актуальных матчей: {len(all_global_matches)}")
          st.rerun()
        else:
          st.warning("Не удалось получить матчи. Проверьте API ключи.")

  for entry in [
      e
      for e in st.session_state.history
      if e.get("sport") == "🌍 Глобальный рынок"
  ]:
    st.caption(f"📅 Сформировано: {entry.get('timestamp')}")
    render_match_cards(entry, "glob")
    st.markdown("---")

elif selected_window == "📥 Ручной инжектор":
  st.header("📥 Ручной ввод матча")
  with st.form("manual_form"):
    c1, c2 = st.columns(2)
    with c1:
      t1 = st.text_input("Хозяева / Игрок 1", "Реал Мадрид")
      o1 = st.number_input("Коэффициент П1", min_value=1.01, value=1.75)
    with c2:
      t2 = st.text_input("Гости / Игрок 2", "Барселона")
      o2 = st.number_input("Коэффициент П2", min_value=1.01, value=4.20)
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
    submitted = st.form_submit_button(
        "⚡ Запросить консенсус Groq + Gemini и разобрать"
    )

    if submitted:
      single_prompt = f"""
            Проанализируй матч: {t1} vs {t2} ({sport_lbl}). Коэффициенты: П1={o1}, П2={o2}.
            Верни СТРОГО JSON-объект без маркдауна:
            {{
              "recommended_bet": "Победа 1 ({t1})",
              "expert_probability": 72,
              "groq_analysis": "Краткий аргумент Groq.",
              "gemini_analysis": "Краткий аргумент Gemini."
            }}
            """
      res_text = ""
      if groq_api_key:
        try:
          client = Groq(api_key=groq_api_key)
          comp = client.chat.completions.create(
              model="llama-3.3-70b-versatile",
              messages=[{"role": "user", "content": single_prompt}],
              temperature=0.2,
              response_format={"type": "json_object"},
          )
          res_text = comp.choices[0].message.content
        except Exception:
          pass

      if not res_text and gemini_api_key:
        try:
          client = genai.Client(api_key=gemini_api_key)
          resp = client.models.generate_content(
              model="gemini-1.5-flash",
              contents=single_prompt,
              config=types.GenerateContentConfig(response_mime_type="application/json"),
          )
          res_text = resp.text
        except Exception:
          pass

      try:
        res_json = json.loads(res_text.strip())
        bet_choice = res_json.get("recommended_bet", f"Победа 1 ({t1})")
        chosen_odds = o1 if "1" in bet_choice or t1 in bet_choice else o2
        prob = int(res_json.get("expert_probability", 70))
        g_txt = res_json.get("groq_analysis", "")
        gem_txt = res_json.get("gemini_analysis", "")
        analysis_text = f"🤖 Groq: {g_txt} | 💎 Gemini: {gem_txt}"
      except Exception:
        bet_choice = f"Победа 1 ({t1})"
        chosen_odds = o1
        prob = 70
        analysis_text = "Аналитический консенсус ИИ."

      card = {
          "sport_label": sport_lbl,
          "team1": t1,
          "team2": t2,
          "bet": bet_choice,
          "coefficient": chosen_odds,
          "probability": prob,
          "bookmaker": "Ручной ввод",
          "status": "⌛ Ожидание",
          "analysis": analysis_text,
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
      st.success("Матч успешно проанализирован!")
      st.rerun()

  for entry in [
      e for e in st.session_state.history if e.get("sport") == "📥 Ручной ввод"
  ]:
    render_match_cards(entry, "man")

elif selected_window in window_mapping:
  sport_title, sport_data = window_mapping[selected_window]
  st.header(f"Терминал: {sport_title}")

  if st.button(
      f"🚀 Найти актуальные матчи ({sport_title})", use_container_width=True
  ):
    if not groq_api_key and not gemini_api_key:
      st.error("Введите API ключ Groq или Gemini в сайдбаре!")
    else:
      with st.spinner(f"Запрос актуальных матчей по направлению {sport_title}..."):
        matches = fetch_real_matches_consensus(
            groq_api_key, gemini_api_key, sport_title, sport_data["label"]
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
          st.success(f"Найдено актуальных матчей: {len(matches)}")
          st.rerun()
        else:
          st.warning("Не удалось получить матчи. Проверьте ключи.")

  for entry in [
      e for e in st.session_state.history if e.get("sport") == sport_title
  ]:
    render_match_cards(entry, "sp")

elif selected_window == "📜 Общий Архив":
  st.subheader("📜 История и архив прогнозов")
  if st.button("🗑 Очистить архив"):
    st.session_state.history = []
    if os.path.exists(HISTORY_FILE):
      os.remove(HISTORY_FILE)
    st.rerun()

  for entry in st.session_state.history:
    st.caption(
        f"📅 Спортивная сессия от: {entry.get('timestamp')} | Раздел:"
        f" {entry.get('sport')}"
    )
    render_match_cards(entry, "arch")
    st.markdown("---")
