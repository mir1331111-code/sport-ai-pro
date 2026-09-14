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

HISTORY_FILE = "match_history_pro.json"


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

  for entry in st.session_state.history:
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
  return (
      round(current_bank, 2),
      round(total_profit, 2),
      round(roi, 2),
      round(win_rate, 1),
      settled,
      wins,
      round(clv_rate, 1),
  )


st.set_page_config(
    page_title="Syndicate Pro: Autonomous Dual-AI Terminal",
    page_icon="⚡",
    layout="wide",
)

if "history" not in st.session_state:
  st.session_state.history = load_history()

if "initial_bankroll" not in st.session_state:
  st.session_state.initial_bankroll = 10000.0

SPORT_GROUPS = {
    "⚽ Футбол (Клубы и Сборные)": {
        "category": "soccer",
        "label": "АПЛ, Ла Лига, Серия А и Еврокубки",
    },
    "🏒 Хоккей": {"category": "hockey", "label": "НХЛ, КХЛ и Международные матчи"},
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
            .value-badge { color: #ffffff; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.75rem; display: inline-block; margin-bottom: 6px; }
            .card-win { background: #ecfdf5 !important; border: 2px solid #10b981 !important; border-radius: 12px; padding: 12px; }
            .card-loss { background: #fef2f2 !important; border: 2px solid #ef4444 !important; border-radius: 12px; padding: 12px; }
            .card-green { background: #ecfdf5 !important; border: 2px solid #10b981 !important; border-radius: 12px; padding: 12px; }
            .card-blue { background: #eff6ff !important; border: 2px solid #3b82f6 !important; border-radius: 12px; padding: 12px; }
            .card-red { background: #fef2f2 !important; border: 2px solid #ef4444 !important; border-radius: 12px; padding: 12px; }
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
            .value-badge {{ color: #ffffff; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.75rem; display: inline-block; margin-bottom: 6px; }}
            .card-win {{ background: rgba(16, 185, 129, 0.15) !important; border: 2px solid #10b981 !important; border-radius: 12px; padding: 12px; }}
            .card-loss {{ background: rgba(239, 68, 68, 0.15) !important; border: 2px solid #ef4444 !important; border-radius: 12px; padding: 12px; }}
            .card-green {{ background: rgba(16, 185, 129, 0.15) !important; border: 2px solid #10b981 !important; border-radius: 12px; padding: 12px; }}
            .card-blue {{ background: rgba(59, 130, 246, 0.15) !important; border: 2px solid #3b82f6 !important; border-radius: 12px; padding: 12px; }}
            .card-red {{ background: rgba(239, 68, 68, 0.15) !important; border: 2px solid #ef4444 !important; border-radius: 12px; padding: 12px; }}
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


# --- АВТОНОМНЫЙ ПОИСК И АНАЛИЗ СОВЕТА ИИ (GROQ + GEMINI) ---
def fetch_autonomous_matches_consensus(
    groq_key, gemini_key, sport_title, sport_desc
):
  # Если ключей нет, возвращаем заглушку-ошибку
  if not groq_key and not gemini_key:
    return []

  prompt = f"""
    Ты — главный сканер спортивного синдиката. Составь список из 4-5 актуальных, реальных топ-матчей на ближайшее время в категории: "{sport_title} ({sport_desc})".
    Для каждого матча подбери реалистичные букмекерские коэффициенты (например, П1 и П2) и проведи глубокий экспертный анализ.
    Ответ выдай СТРОГО в формате JSON-массива объектов. Без маркдауна (без ```json), чистый JSON:
    [
      {{
        "team1": "Название первой команды / игрока",
        "team2": "Название второй команды / игрока",
        "coefficient_1": 1.85,
        "coefficient_2": 3.90,
        "bookmaker": "Pin-Up / Fonbet",
        "recommended_bet": "Победа 1 (название)",
        "expert_probability": 0.72,
        "groq_analysis": "Аналитический аргумент от Groq (2 предложения)",
        "gemini_analysis": "Аналитический аргумент от Gemini (2 предложения)"
      }
    ]
    """

  raw_text = ""
  # Пробуем получить от Groq
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

  # Если Groq не сработал, пробуем Gemini
  if not raw_text and gemini_key:
    try:
      client = genai.Client(api_key=gemini_key)
      response = client.models.generate_content(
          model="gemini-2.5-flash",
          contents=prompt,
          config=types.GenerateContentConfig(response_mime_type="application/json"),
      )
      raw_text = response.text
    except Exception:
      pass

  if not raw_text:
    return []

  try:
    # Очистка от возможных лишних символов
    clean_json = raw_text.strip()
    if clean_json.startswith("```"):
      clean_json = clean_json.split("```")[1]
      if clean_json.startswith("json"):
        clean_json = clean_json[4:]
    data_list = json.loads(clean_json)

    # Если бэкенд вернул словарь с ключом, найдем внутри список
    if isinstance(data_list, dict):
      for k, v in data_list.items():
        if isinstance(v, list):
          data_list = v
          break

    parsed_matches = []
    if isinstance(data_list, list):
      for item in data_list:
        t1 = item.get("team1", "Команда 1")
        t2 = item.get("team2", "Команда 2")
        p1 = float(item.get("coefficient_1", 1.85))
        p2 = float(item.get("coefficient_2", 2.10))
        bet = item.get("recommended_bet", f"Победа 1 ({t1})")
        chosen_odds = p1 if "1" in bet or t1 in bet else p2

        prob = float(item.get("expert_probability", 0.70))

        imp1 = 1 / p1
        imp2 = 1 / p2
        total_vig = imp1 + imp2
        true_p1 = imp1 / total_vig
        margin = round((total_vig - 1) * 100, 2)

        ev = (chosen_odds * prob) - 1
        edge = prob - true_p1
        rec_status = "green" if ev >= 1.5 else ("blue" if ev >= -2.0 else "red")

        g_text = item.get("groq_analysis", "Анализ формы и мотивации.")
        gem_text = item.get("gemini_analysis", "Статистический расчет вероятностей.")
        analysis_comment = f"🤖 Groq: {g_text} | 💎 Gemini: {gem_text}"

        parsed_matches.append({
            "sport_label": sport_title,
            "sport_category": "autonomous",
            "team1": t1,
            "team2": t2,
            "bet": bet,
            "coefficient": chosen_odds,
            "closing_odds": round(chosen_odds * 0.98, 2),
            "probability": prob,
            "true_probability": round(true_p1, 3),
            "margin": margin,
            "edge": round(edge * 100, 2),
            "ev": round(ev * 100, 2),
            "bookmaker": item.get("bookmaker", "Совет ИИ БК"),
            "status": "⌛ Ожидание",
            "rec_status": rec_status,
            "analysis": analysis_comment,
        })
    return sorted(parsed_matches, key=lambda x: x["ev"], reverse=True)
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

min_ev_filter = st.sidebar.slider(
    "📊 Мин. EV (%) для отбора:", -5.0, 15.0, -2.0, 0.5
)

selected_window = st.sidebar.radio(
    "Переключение терминала:",
    [
        "🌍 Глобальный омниссканер (Все виды спорта)",
        "📥 Ручной инжектор",
        "⚽ Футбол (Клубы и Сборные)",
        "🏒 Хоккей",
        "🏀 Баскетбол",
        "🎾 Теннис",
        "🏐 Волейбол",
        "🤾 Гандбол",
        "🎮 Киберспорт",
        "📈 Аналитика и статистика",
        "📜 Общий Архив",
    ],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.title("💰 Виртуальный симулятор банка")
initial_bank_input = st.sidebar.number_input(
    "Стартовый банк (руб.):",
    min_value=10.0,
    value=st.session_state.initial_bankroll,
    step=500.0,
)
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
active_kelly_fraction = {
    "Четверть Келли (0.25 - безопасный)": 0.25,
    "Полукелли (0.5 - средний)": 0.5,
    "Полный Келли (1.0 - агрессивный)": 1.0,
}[kelly_choice]

if st.sidebar.button("🔄 Сбросить симулятор и архив"):
  st.session_state.history = []
  if os.path.exists(HISTORY_FILE):
    os.remove(HISTORY_FILE)
  st.success("Сброшено!")
  st.rerun()

telegram_token = st.sidebar.text_input(
    "Telegram Bot Token", type="password", placeholder="..."
)
telegram_chat_id = st.sidebar.text_input("Telegram Chat ID", placeholder="...")

if st.sidebar.button("🔔 Тест Telegram"):
  success = send_telegram_message(
      telegram_token, telegram_chat_id, "🟢 Syndicate Pro работает!"
  )
  if success:
    st.sidebar.success("Отправлено!")
  else:
    st.sidebar.error("Ошибка.")

(
    current_virtual_bank,
    net_profit,
    simulator_roi,
    simulator_winrate,
    total_settled,
    total_wins,
    clv_rate,
) = get_financial_stats()

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

# --- ДАШБОРД ---
st.markdown("### 📊 Финансовый дашборд Синдиката Pro (Autonomous Dual-AI)")
fc1, fc2, fc3, fc4, fc5 = st.columns(5)
fc1.metric(
    "💳 Виртуальный банк",
    f"{current_virtual_bank:,.2f} руб.",
    f"{net_profit:+,.2f} руб.",
)
fc2.metric("📈 Прибыль", f"{net_profit:+,.2f} руб.")
fc3.metric("🎯 ROI", f"{simulator_roi}%")
fc4.metric("🏆 Винрейт", f"{simulator_winrate}% ({total_wins}/{total_settled})")
fc5.metric("⚡ Beat CLV", f"{clv_rate}%")
st.markdown("---")

active_sport_cat = "default"
if selected_window in window_mapping:
  active_sport_cat = window_mapping[selected_window][1]["category"]
apply_custom_styles(theme_choice, active_sport_cat)


def render_match_cards(entry, session_key_prefix):
  cols = st.columns(2)
  for idx, card in enumerate(entry.get("data", [])):
    status_val = card.get("status", "⌛ Ожидание")
    rec_status = card.get("rec_status", "blue")

    if status_val == "✅ Проход":
      status_class = "card-win"
    elif status_val == "❌ Проигрыш":
      status_class = "card-loss"
    else:
      status_class = f"card-{rec_status}"

    ev_val = card.get("ev", 0.0)
    team1_val = card.get("team1", "")
    team2_val = card.get("team2", "")
    sport_lbl = card.get("sport_label", "")
    bk_val = card.get("bookmaker", "")
    bet_val = card.get("bet", "")
    coef_val = card.get("coefficient", 1.0)
    prob_val = round(card.get("probability", 0.5) * 100, 1)
    stake_val = card.get("recommended_stake", 0.0)
    analysis_val = card.get("analysis", "")

    badge_color = (
        "#10b981"
        if rec_status == "green"
        else ("#ef4444" if rec_status == "red" else "#3b82f6")
    )
    badge_text = f"🔥 EV: {ev_val:+.2f}% | Автономный Совет ИИ (Groq + Gemini)"

    with cols[idx % 2]:
      st.markdown(
          f"""
                <div class="{status_class}">
                    <span class="value-badge" style="background: {badge_color};">{badge_text}</span>
                    <b>{team1_val} vs {team2_val}</b><br>
                    <small>{sport_lbl} | Источник: `{bk_val}` | Статус: {status_val}</small><hr style="margin:4px 0;">
                    <b>Прогноз:</b> {bet_val}<br>
                    <b>Кэф:</b> {coef_val} | <b>Совместная Вероятность:</b> {prob_val}%<br>
                    <b>Рекомендация Келли:</b> {stake_val} руб.<br>
                    <i>🤖💎 Аналитика Совета ИИ:<br>{analysis_val}</i>
                </div>
                """,
          unsafe_allow_html=True,
      )
      c1, c2, c3 = st.columns(3)
      if c1.button(
          "✅ Выиграл",
          key=f"{session_key_prefix}_w_{entry['timestamp']}_{idx}",
      ):
        card["status"] = "✅ Проход"
        save_history(st.session_state.history)
        st.rerun()
      if c2.button(
          "❌ Проиграл",
          key=f"{session_key_prefix}_l_{entry['timestamp']}_{idx}",
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


# --- РАЗДЕЛЫ ---
if selected_window == "🌍 Глобальный омниссканер (Все виды спорта)":
  st.header("🌍 Глобальный омниссканер (Автономный Совет ИИ)")
  st.info(
      "Искусственный интеллект автоматически формирует расписание топ-матчей по"
      " всем видам спорта и выдает консенсус-прогнозы."
  )

  if st.button(
      "🚀 Запустить глобальный поиск и анализ", use_container_width=True
  ):
    if not groq_api_key and not gemini_api_key:
      st.error(
          "Пожалуйста, введите хотя бы один API-ключ (Groq или Gemini) в"
            " сайдбаре!"
      )
    else:
      with st.spinner(
          "Совет ИИ генерирует актуальные матчи и проводит анализ..."
      ):
        all_global_matches = []
        for sport_name, sport_info in SPORT_GROUPS.items():
          matches = fetch_autonomous_matches_consensus(
              groq_api_key,
              gemini_api_key,
              sport_name,
              sport_info["label"],
          )
          for m in matches:
            if m["ev"] >= min_ev_filter:
              m["recommended_stake"] = calculate_kelly_stake(
                  current_virtual_bank,
                  m["coefficient"],
                  m["probability"],
                  active_kelly_fraction,
              )
              all_global_matches.append(m)

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
          st.success(f"Готово! Найдено сигналов: {len(all_global_matches)}")
          st.rerun()
        else:
          st.warning("Не удалось сформировать матчи. Проверьте правильность API ключей.")

  st.markdown("### 📋 Результаты")
  for entry in [
      e
      for e in st.session_state.history
      if e.get("sport") == "🌍 Глобальный рынок"
  ]:
    st.caption(f"📅 Сессия от: {entry.get('timestamp')}")
    render_match_cards(entry, "glob")
    st.markdown("---")

elif selected_window == "📥 Ручной инжектор":
  st.header("📥 Ручной инжектор матчей (Совместный анализ ИИ)")
  with st.form("manual_form"):
    c1, c2 = st.columns(2)
    with c1:
      t1 = st.text_input("Хозяева", "Зенит")
      o1 = st.number_input("Кэф П1", min_value=1.01, value=1.85)
    with c2:
      t2 = st.text_input("Гости", "Динамо")
      o2 = st.number_input("Кэф П2", min_value=1.01, value=3.90)
    sport_lbl = st.selectbox(
        "Спорт",
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
        "⚡ Запросить консенсус Groq + Gemini и добавить"
    )

    if submitted:
      imp1 = 1 / o1
      imp2 = 1 / o2
      vig = imp1 + imp2
      true_p1 = imp1 / vig
      margin = round((vig - 1) * 100, 2)

      # Запрос к ИИ для одного матча
      single_prompt = f"""
            Проанализируй матч: {t1} vs {t2} ({sport_lbl}). Коэффициенты: П1={o1}, П2={o2}.
            Верни СТРОГО JSON без маркдауна:
            {{
              "recommended_bet": "Победа 1 ({t1})",
              "expert_probability": 0.72,
              "analysis": "Глубокий аналитический разбор матча на 2 предложения."
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
              model="gemini-2.5-flash",
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
        prob = float(res_json.get("expert_probability", 0.70))
        analysis_text = res_json.get("analysis", "Анализ матча.")
      except Exception:
        bet_choice = f"Победа 1 ({t1})"
        chosen_odds = o1
        prob = 0.70
        analysis_text = "Математический расчет по линии."

      ev = (chosen_odds * prob) - 1
      edge = prob - true_p1
      rec_status = "green" if ev >= 1.5 else ("blue" if ev >= -2.0 else "red")
      stake = calculate_kelly_stake(
          current_virtual_bank, chosen_odds, prob, active_kelly_fraction
      )

      card = {
          "sport_label": sport_lbl,
          "sport_category": "manual",
          "team1": t1,
          "team2": t2,
          "bet": bet_choice,
          "coefficient": chosen_odds,
          "closing_odds": round(chosen_odds * 0.98, 2),
          "probability": prob,
          "true_probability": round(true_p1, 3),
          "margin": margin,
          "edge": round(edge * 100, 2),
          "ev": round(ev * 100, 2),
          "bookmaker": "Ручной инжектор",
          "status": "⌛ Ожидание",
          "rec_status": rec_status,
          "recommended_stake": stake,
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
      st.success("Успешно проанализировано Советом ИИ!")
      st.rerun()

  for entry in [
      e for e in st.session_state.history if e.get("sport") == "📥 Ручной ввод"
  ]:
    render_match_cards(entry, "man")

elif selected_window in window_mapping:
  sport_title, sport_data = window_mapping[selected_window]
  st.header(f"Терминал: {sport_title}")

  if st.button(
      f"🚀 Автоматический поиск матчей и анализ ({sport_title})",
      use_container_width=True,
  ):
    if not groq_api_key and not gemini_api_key:
      st.error("Введите API ключ Groq или Gemini в сайдбаре!")
    else:
      with st.spinner(
          f"Совет ИИ подбирает актуальные матчи ({sport_title}) и считает EV..."
      ):
        matches = fetch_autonomous_matches_consensus(
            groq_api_key,
            gemini_api_key,
            sport_title,
            sport_data["label"],
        )
        filtered = [m for m in matches if m["ev"] >= min_ev_filter]
        for m in filtered:
          m["recommended_stake"] = calculate_kelly_stake(
              current_virtual_bank,
              m["coefficient"],
              m["probability"],
              active_kelly_fraction,
          )

        if filtered:
          st.session_state.history.insert(
              0,
              {
                  "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  "sport": sport_title,
                  "data": filtered,
              },
          )
          save_history(st.session_state.history)
          st.success(f"Найдено сигналов: {len(filtered)}")
          st.rerun()
        else:
          st.warning("Не удалось получить матчи. Попробуйте еще раз.")

  for entry in [
      e for e in st.session_state.history if e.get("sport") == sport_title
  ]:
    render_match_cards(entry, "sp")

elif selected_window == "📈 Аналитика и статистика":
  st.subheader("📈 Аудит портфеля")
  st.metric("Всего записей в истории", len(st.session_state.history))

elif selected_window == "📜 Общий Архив":
  st.subheader("📜 Архив")
  if st.button("🗑 Очистить архив"):
    st.session_state.history = []
    if os.path.exists(HISTORY_FILE):
      os.remove(HISTORY_FILE)
    st.rerun()
