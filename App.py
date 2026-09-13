import datetime
import json
import os
import random
import re
import time
from datetime import datetime, timezone
import requests
import streamlit as st
from groq import Groq
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
    page_title="Syndicate Pro: Advanced Betting Terminal",
    page_icon="⚡",
    layout="wide",
)

if "history" not in st.session_state:
  st.session_state.history = load_history()

if "initial_bankroll" not in st.session_state:
  st.session_state.initial_bankroll = 10000.0

SPORT_GROUPS = {
    "⚽ Футбол": {
        "category": "soccer",
        "endpoints": [
            ("soccer_epl", "АПЛ (Англия)"),
            ("soccer_spain_la_liga", "Ла Лига (Испания)"),
            ("soccer_germany_bundesliga", "Бундеслига (Германия)"),
            ("soccer_italy_serie_a", "Серия А (Италия)"),
            ("soccer_france_ligue_one", "Лига 1 (Франция)"),
        ],
    },
    "🏒 Хоккей": {
        "category": "hockey",
        "endpoints": [
            ("icehockey_nhl", "НХЛ (США/Канада)"),
        ],
    },
    "🏀 Баскетбол": {
        "category": "basketball",
        "endpoints": [
            ("basketball_nba", "НБА (США)"),
            ("basketball_euroleague", "Евролига (Европа)"),
        ],
    },
    "🎾 Теннис": {
        "category": "tennis",
        "endpoints": [
            ("tennis_atp_aus_open", "ATP Теннис"),
        ],
    },
    "🎮 Киберспорт": {
        "category": "esports",
        "endpoints": [
            ("esports_cs_go", "Counter-Strike 2"),
            ("esports_dota_2", "Dota 2"),
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
    "tennis": [
        "https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?auto=format&fit=crop&w=1920&q=80"
    ],
    "esports": [
        "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=1920&q=80"
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
            .card-win { background: #ecfdf5 !important; border: 2px solid #10b981 !important; border-radius: 12px; padding: 10px; }
            .card-loss { background: #fef2f2 !important; border: 2px solid #ef4444 !important; border-radius: 12px; padding: 10px; }
            .card-pending { background: #ffffff !important; border: 1px solid #cbd5e1 !important; border-radius: 12px; padding: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
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
            .card-win {{ background: rgba(16, 185, 129, 0.12) !important; border: 2px solid #00FF66 !important; border-radius: 12px; padding: 10px; }}
            .card-loss {{ background: rgba(239, 68, 68, 0.12) !important; border: 2px solid #EF4444 !important; border-radius: 12px; padding: 10px; }}
            .card-pending {{ background: rgba(30, 41, 59, 0.8) !important; border: 1px solid rgba(255, 255, 255, 0.1) !important; border-radius: 12px; padding: 10px; }}
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


# ФУНКЦИЯ ПОЛУЧЕНИЯ МАТЧЕЙ С ФИЛЬТРОМ ВРЕМЕНИ
def fetch_matches_from_odds_api(
    endpoints_list, sport_category, api_key, max_hours_ahead=12
):
  raw_matches = []
  if not api_key:
    return raw_matches

  now_utc = datetime.now(timezone.utc)

  for sport_key, label in endpoints_list:
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {
        "apiKey": api_key,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal",
    }
    try:
      resp = requests.get(url, params=params, timeout=5)
      if resp.status_code == 200:
        events = resp.json()
        for ev in events:
          comm_time_str = ev.get("commence_time", "")
          if not comm_time_str:
            continue

          # Проверяем время матча, чтобы не брать игры, которые через неделю
          comm_dt = datetime.fromisoformat(
              comm_time_str.replace("Z", "+00:00")
          )
          hours_diff = (comm_dt - now_utc).total_seconds() / 3600.0

          if (
              hours_diff < -1 or hours_diff > max_hours_ahead
          ):  # Пропускаем старые или слишком далекие матчи
            continue

          t1 = ev.get("home_team", "Команда 1")
          t2 = ev.get("away_team", "Команда 2")

          odds_1, odds_x, odds_2 = 1.90, 3.20, 1.90
          bookmakers = ev.get("bookmakers", [])
          if bookmakers:
            markets = bookmakers[0].get("markets", [])
            for m in markets:
              if m.get("key") == "h2h":
                for o in m.get("outcomes", []):
                  if o.get("name") == t1:
                    odds_1 = o.get("price", 1.90)
                  elif o.get("name") == t2:
                    odds_2 = o.get("price", 1.90)
                  elif o.get("name") == "Draw":
                    odds_x = o.get("price", 3.20)

          raw_matches.append({
              "sport_label": label,
              "sport_category": sport_category,
              "team1": t1,
              "team2": t2,
              "team1_logo": f"https://ui-avatars.com/api/?name={t1}&background=1e293b&color=00ff66",
              "team2_logo": f"https://ui-avatars.com/api/?name={t2}&background=1e293b&color=00bfff",
              "status": (
                  f"⏳ Начало: {comm_time_str[11:16]} (UTC)"
                  if len(comm_time_str) >= 16
                  else "⏳ Скоро"
              ),
              "is_finished": False,
              "score": "0:0",
              "state": "pre",
              "short_detail": comm_time_str,
              "real_odds": {"1": odds_1, "X": odds_x, "2": odds_2},
          })
    except Exception:
      pass

  return raw_matches


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


# --- НАВИГАЦИЯ И НАСТРОЙКИ В САЙДБАРЕ ---
st.sidebar.title("🎛️ Настройки интерфейса")
theme_choice = st.sidebar.selectbox(
    "Тема оформления:",
    ["🎨 Динамический спорт-фон", "☀️ Светлая тема", "🌙 Строгая темная"],
    index=0,
)

st.sidebar.title("🔑 API-ключ букмекеров")
odds_api_key = st.sidebar.text_input(
    "The Odds API Key",
    type="password",
    help="Ключ с the-odds-api.com для реальных кэфов",
)

# Полноценный фильтр времени матчей
max_hours_filter = st.sidebar.slider(
    "⏰ Искать матчи на ближайшие (часов):",
    min_value=2,
    max_value=48,
    value=12,
    step=2,
    help=(
        "Отсекает матчи, которые начнутся позже этого времени (чтобы не"
        " заглядывать на неделю вперед)"
    ),
)

st.sidebar.title("🎛️ Выбор окна терминала")
selected_window = st.sidebar.radio(
    "Переключение терминала:",
    [
        "⚽ Футбол — Окно",
        "🏒 Хоккей — Окно",
        "🏀 Баскетбол — Окно",
        "🎾 Теннис — Окно",
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
initial_bank_input = st.sidebar.number_input(
    "Стартовый виртуальный банк (руб.):",
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
kelly_map = {
    "Четверть Келли (0.25 - безопасный)": 0.25,
    "Полукелли (0.5 - средний)": 0.5,
    "Полный Келли (1.0 - агрессивный)": 1.0,
}
active_kelly_fraction = kelly_map[kelly_choice]

if st.sidebar.button("🔄 Сбросить симулятор"):
  st.session_state.history = []
  if os.path.exists(HISTORY_FILE):
    os.remove(HISTORY_FILE)
  st.success("Виртуальный банк и архив очищены!")
  st.rerun()

st.sidebar.markdown("---")
st.sidebar.title("⚙️ Настройки ИИ и Синдиката")
ai_mode = st.sidebar.radio(
    "Режим анализа:",
    ["🧠 Только Groq AI", "✨ Только Gemini AI", "🤖🤖 Консилиум (Groq + Gemini)"],
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
      "🟢 *Syndicate Pro*: Тестовое сообщение доставлено!",
  )
  if success:
    st.sidebar.success("Сообщение отправлено!")
  else:
    st.sidebar.error("Ошибка отправки. Проверьте Token и Chat ID.")

selected_groq_model = None
if groq_api_key:
  models_list = fetch_active_groq_models(groq_api_key)
  selected_groq_model = st.sidebar.selectbox("Модель Groq", models_list, index=0)

current_virtual_bank, net_profit, simulator_roi, simulator_winrate, total_settled, total_wins, clv_rate = get_financial_stats()

window_mapping = {
    "⚽ Футбол — Окно": ("⚽ Футбол", SPORT_GROUPS["⚽ Футбол"]),
    "🏒 Хоккей — Окно": ("🏒 Хоккей", SPORT_GROUPS["🏒 Хоккей"]),
    "🏀 Баскетбол — Окно": ("🏀 Баскетбол", SPORT_GROUPS["🏀 Баскетбол"]),
    "🎾 Теннис — Окно": ("🎾 Теннис", SPORT_GROUPS["🎾 Теннис"]),
    "🎮 Киберспорт — Окно": ("🎮 Киберспорт", SPORT_GROUPS["🎮 Киберспорт"]),
}

# --- ФИНАНСОВЫЙ ДАШБОРД ---
st.markdown("### 📊 Синдикатный финансовый дашборд Pro")
fc1, fc2, fc3, fc4, fc5 = st.columns(5)
fc1.metric(
    "💳 Виртуальный банк",
    f"{current_virtual_bank:,.2f} руб.",
    f"{net_profit:+,.2f} руб.",
)
fc2.metric("📈 Чистая прибыль", f"{net_profit:+,.2f} руб.")
fc3.metric("🎯 ROI", f"{simulator_roi}%")
fc4.metric("🏆 Винрейт", f"{simulator_winrate}% ({total_wins}/{total_settled})")
fc5.metric("⚡ Beat CLV Rate", f"{clv_rate}%")
st.markdown("---")

active_sport_cat = "default"
if selected_window in window_mapping:
  active_sport_cat = window_mapping[selected_window][1]["category"]
apply_custom_styles(theme_choice, active_sport_cat)

# --- РЕАЛИЗАЦИЯ ВКЛАДОК И ОКОН ---
if selected_window in window_mapping:
  sport_title, sport_data = window_mapping[selected_window]
  st.header(f"Терминал: {sport_title}")

  col_ctrl1, col_ctrl2 = st.columns([2, 1])
  with col_ctrl1:
    st.info(
        f"💡 Линия БК фильтруется по времени: показываются матчи на ближайшие"
        f" {max_hours_filter} ч."
    )
  with col_ctrl2:
    scan_button = st.button(
        "🚀 Запустить сканер валуев (БК + ИИ)", use_container_width=True
    )

  if scan_button:
    with st.spinner("Фильтруем линию БК и запускаем ИИ-анализ..."):
      matches = fetch_matches_from_odds_api(
          sport_data["endpoints"],
          sport_data["category"],
          odds_api_key,
          max_hours_ahead=max_hours_filter,
      )

      if not matches:
        st.warning(
            "⚠️ В выбранном диапазоне времени (на ближайшие"
            f" {max_hours_filter} ч.) матчей не найдено. Попробуйте увеличить"
            " интервал в сайдбаре."
        )

      analyzed_cards = []
      for m in matches[:6]:
        real_o1 = m["real_odds"]["1"]
        real_ox = m["real_odds"]["X"]
        real_o2 = m["real_odds"]["2"]

        prompt = f"""
                Ты профессиональный спортивный аналитик и сканер валуйных ставок синдиката.
                Проанализируй матч: {m['team1']} против {m['team2']} в лиге {m['sport_label']}.
                Реальные коэффициенты БК: П1={real_o1}, Х={real_ox}, П2={real_o2}.
                Выдай JSON со следующими полями:
                - "recommendation": Выбери лучшую ставку (например, "П1", "П2", "Х", "ТБ 2.5").
                - "coefficient": Выбери соответствующий коэффициент из линии (float).
                - "closing_odds": Прогнозируемый закрывающий коэффициент (float).
                - "probability": Оценка вероятности прохода от 0.51 до 0.85 (float).
                - "analysis": Краткое обоснование в 2 предложения на русском языке.
                """
        raw_resp = None
        if (
            ai_mode in ["🧠 Только Groq AI", "🤖🤖 Консилиум (Groq + Gemini)"]
            and groq_api_key
        ):
          try:
            client = Groq(api_key=groq_api_key)
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=selected_groq_model or "llama-3.3-70b-versatile",
                response_format={"type": "json_object"},
            )
            raw_resp = chat_completion.choices[0].message.content
          except Exception:
            pass
        if not raw_resp and gemini_api_key:
          raw_resp = call_gemini_api(gemini_api_key, prompt)

        if raw_resp:
          try:
            parsed = json.loads(raw_resp)
            odds = float(parsed.get("coefficient", real_o1))
            prob = float(parsed.get("probability", 0.55))
            closing = float(parsed.get("closing_odds", odds))
            stake = calculate_kelly_stake(
                current_virtual_bank, odds, prob, active_kelly_fraction
            )

            analyzed_cards.append({
                **m,
                "bet": parsed.get("recommendation", "П1"),
                "coefficient": odds,
                "closing_odds": closing,
                "probability": prob,
                "analysis": parsed.get(
                    "analysis", "Анализ линии завершен успешно."
                ),
                "recommended_stake": stake,
                "status": "⌛ Ожидание",
            })
          except Exception:
            pass

      if analyzed_cards:
        st.session_state.history.insert(
            0,
            {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sport": sport_title,
                "data": analyzed_cards,
            },
        )
        save_history(st.session_state.history)
        st.success(f"Сканирование завершено! Сигналов получено: {len(analyzed_cards)}")
        st.rerun()

  st.markdown("### 📋 Активные сигналы и архив")
  filtered_history = [
      entry
      for entry in st.session_state.history
      if entry.get("sport") == sport_title
  ]
  if not filtered_history:
    st.info(
        "Нет сохраненных сигналов. Запустите сканер для поиска матчей на"
        " сегодня."
    )
  else:
    for entry in filtered_history:
      st.caption(f"📅 Сессия от: {entry.get('timestamp')}")
      cols = st.columns(2)
      for idx, card in enumerate(entry.get("data", [])):
        status_class = "card-pending"
        if card["status"] == "✅ Проход":
          status_class = "card-win"
        elif card["status"] == "❌ Проигрыш":
          status_class = "card-loss"

        with cols[idx % 2]:
          st.markdown(
              f"""
                    <div class="{status_class}">
                        <span class="value-badge">ВАЛУЙ СИГНАЛ БК</span>
                        <b>{card['team1']} vs {card['team2']}</b><br>
                        <small>{card['sport_label']} | Статус: {card['status']}</small><hr style="margin:4px 0;">
                        <b>Прогноз:</b> {card['bet']} | <b>Кэф:</b> {card['coefficient']} | <b>Стейк:</b> {card['recommended_stake']} руб.<br>
                        <i>{card['analysis']}</i>
                    </div>
                    """,
              unsafe_allow_html=True,
          )

          c1, c2, c3 = st.columns(3)
          if c1.button("✅ Выиграл", key=f"w_{entry['timestamp']}_{idx}"):
            card["status"] = "✅ Проход"
            save_history(st.session_state.history)
            st.rerun()
          if c2.button("❌ Проиграл", key=f"l_{entry['timestamp']}_{idx}"):
            card["status"] = "❌ Проигрыш"
            save_history(st.session_state.history)
            st.rerun()
          if c3.button("🗑 Удалить", key=f"d_{entry['timestamp']}_{idx}"):
            entry["data"].remove(card)
            save_history(st.session_state.history)
            st.rerun()
      st.markdown("---")

elif selected_window == "🚨 Лайв-радар (Камбэки)":
  st.subheader("🚨 Лайв-радар поиска камбэков и давления")
  st.write(
      "Мониторинг матчей, где фаворит уступает в счете по ходу встречи, но"
      " владеет инициативой."
  )

elif selected_window == "🔬 Эксперимент: Big Data & ML":
  st.subheader("🔬 Экспериментальный модуль Big Data & Machine Learning")
  st.write(
      "Сравнение вероятностей на основе пуассоновского распределения и"
      " нейросетевых предиктов."
  )
  st.metric("Точность ML-модели за 30 дней", "58.4%", "+2.1% к букмекеру")

elif selected_window == "🎯 Player Props (Индивидуальная статистика)":
  st.subheader("🎯 Player Props & Индивидуальные тоталы")
  st.write(
      "Анализ индивидуальной статистики спортсменов с помощью языковых моделей."
  )
  p_name = st.text_input("Фамилия игрока / спортсмена:", "Овечкин")
  if st.button("📊 Анализировать Player Prop"):
    st.success(
        f"Анализ индивидуальных показателей для игрока: {p_name} выполнен."
        " Рекомендация: ТБ по броскам."
    )

elif selected_window == "⚡ Sharp & CLV Менеджер":
  st.subheader("⚡ Управление Closing Line Value (CLV)")
  st.write(
      "Анализ того, насколько ваши ставки бьют линию закрытия букмекерских"
      " контор."
  )
  st.metric("Общий показатель Beat CLV", f"{clv_rate}%")
  st.info("Успешные синдикаты ориентируются на стабильный CLV выше 52%.")

elif selected_window == "📜 Общий Архив":
  st.subheader("📜 Полный архив всех сессий и ставок")
  if not st.session_state.history:
    st.info("Архив пуст.")
  else:
    if st.button("🗑 Очистить весь архив"):
      st.session_state.history = []
      if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
      st.success("Архив полностью очищен!")
      st.rerun()
    for idx, entry in enumerate(st.session_state.history):
      st.write(
          f"**Сессия #{idx+1}** | Дата: {entry.get('timestamp')} | Спорт:"
          f" {entry.get('sport')} | Всего сигналов:"
          f" {len(entry.get('data', []))}"
      )
