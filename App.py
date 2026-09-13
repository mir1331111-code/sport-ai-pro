from datetime import datetime, timezone
import json
import os
import random
import re
import time
from groq import Groq
import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# --- АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ ---
count = st_autorefresh(interval=900000, key="auto_sniper_refresh")

HISTORY_FILE = "match_history_pro.json"
EXPERIENCE_CSV = "all_matches_history.csv"


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
    page_title="Syndicate Pro: Ultimate Betting & Value Terminal",
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
        "endpoints": [
            ("soccer_epl", "АПЛ (Англия)"),
            ("soccer_spain_la_liga", "Ла Лига (Испания)"),
            ("soccer_germany_bundesliga", "Бундеслига (Германия)"),
            ("soccer_italy_serie_a", "Серия А (Италия)"),
            ("soccer_france_ligue_one", "Лига 1 (Франция)"),
            ("soccer_uefa_nations_league", "Лига Наций УЕФА"),
            ("soccer_fifa_world_cup", "ЧМ / Отборы"),
            ("soccer_international_friendly", "Товарищеские матчи"),
            ("soccer_turkey_super_lig", "Суперлига (Турция)"),
            ("soccer_netherlands_eredivisie", "Эредивизи (Нидерланды)"),
            ("soccer_portugal_primeira_liga", "Примейра (Португалия)"),
        ],
    },
    "🏒 Хоккей": {
        "category": "hockey",
        "endpoints": [
            ("icehockey_nhl", "НХЛ (США/Канада)"),
            ("icehockey_khl", "КХЛ (Россия/Евразия)"),
            ("icehockey_sweden_hockey_league", "Шведская хоккейная лига"),
            ("icehockey_liiga", "Лиига (Финляндия)"),
        ],
    },
    "🏀 Баскетбол": {
        "category": "basketball",
        "endpoints": [
            ("basketball_nba", "НБА (США)"),
            ("basketball_euroleague", "Евролига (Европа)"),
            ("basketball_ncaab", "NCAA (США)"),
        ],
    },
    "🎾 Теннис": {
        "category": "tennis",
        "endpoints": [
            ("tennis_atp_aus_open", "ATP Австралиан Опен"),
            ("tennis_wta_aus_open", "WTA Австралиан Опен"),
            ("tennis_atp_us_open", "ATP US Open"),
            ("tennis_wta_us_open", "WTA US Open"),
            ("tennis_atp_match", "ATP Международные"),
        ],
    },
    "🏐 Волейбол": {
        "category": "volleyball",
        "endpoints": [
            ("volleyball_cev_champions_league", "Лига Чемпионов ЕКВ"),
        ],
    },
    "🤾 Гандбол": {
        "category": "handball",
        "endpoints": [
            ("handball_bundesliga", "Бундеслига (Гандбол)"),
        ],
    },
    "🎮 Киберспорт": {
        "category": "esports",
        "endpoints": [
            ("esports_cs_go", "Counter-Strike 2"),
            ("esports_dota_2", "Dota 2"),
            ("esports_lol", "League of Legends"),
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
            .value-badge { background: #10b981; color: #ffffff; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.75rem; display: inline-block; margin-bottom: 6px; }
            .card-win { background: #ecfdf5 !important; border: 2px solid #10b981 !important; border-radius: 12px; padding: 12px; }
            .card-loss { background: #fef2f2 !important; border: 2px solid #ef4444 !important; border-radius: 12px; padding: 12px; }
            .card-pending { background: #ffffff !important; border: 1px solid #cbd5e1 !important; border-radius: 12px; padding: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
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
            .value-badge {{ background: #059669; color: #ffffff; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.75rem; display: inline-block; margin-bottom: 6px; }}
            .card-win {{ background: rgba(16, 185, 129, 0.15) !important; border: 2px solid #00FF66 !important; border-radius: 12px; padding: 12px; }}
            .card-loss {{ background: rgba(239, 68, 68, 0.15) !important; border: 2px solid #EF4444 !important; border-radius: 12px; padding: 12px; }}
            .card-pending {{ background: rgba(15, 23, 42, 0.85) !important; border: 1px solid rgba(255, 255, 255, 0.12) !important; border-radius: 12px; padding: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.4); }}
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


# --- ИИ АНАЛИТИК (GROQ И GEMINI) ---
def call_groq_deep_analyst(groq_api_key, team1, team2, sport_label, odds1, odds2):
  if not groq_api_key:
    return (
        "Groq API ключ не задан. Используется стандартная математическая модель."
    )
  try:
    client = Groq(api_key=groq_api_key)
    prompt = f"""
        Ты — элитный спортивный капер и синдикатный аналитик с 20-летним стажем. 
        Проанализируй матч: {team1} vs {team2} ({sport_label}). 
        Коэффициенты БК: П1 = {odds1}, П2 = {odds2}.
        Синтезируй мнения ведущих платных и бесплатных аналитиков, оцени форму команд, мотивацию, травмы и движение линии (sharp money).
        Выдай экспертный вердикт на русском языке в формате строгого JSON с полями:
        - "recommended_bet": точная ставка (например, "Победа 1 (Команда)")
        - "expert_probability": число от 0.0 до 1.0 (реальная вероятность исхода)
        - "analysis_text": глубокий аналитический разбор на 3-4 предложения с обоснованием валуя (EV).
        Отвечай ТОЛЬКО валидным JSON без лишнего текста.
        """
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": prompt,
        }],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    res_json = json.loads(completion.choices[0].message.content)
    return res_json
  except Exception as e:
    return None


def call_gemini_api(api_key, prompt_text):
  if not api_key:
    return None
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


# ИСПРАВЛЕНО: единое имя функции во избежание NameError
def fetch_matches_from_odds_api(
    endpoints_list,
    sport_category,
    api_key,
    max_hours_ahead=48,
    groq_key="",
    gemini_key="",
):
  raw_matches = []
  if not api_key:
    return []

  now_utc = datetime.now(timezone.utc)

  for sport_key, label in endpoints_list:
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {
        "apiKey": api_key,
        "regions": "eu,us",
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
          comm_dt = datetime.fromisoformat(
              comm_time_str.replace("Z", "+00:00")
          )
          hours_diff = (comm_dt - now_utc).total_seconds() / 3600.0

          if hours_diff < -1 or hours_diff > max_hours_ahead:
            continue

          t1 = ev.get("home_team", "Команда 1")
          t2 = ev.get("away_team", "Команда 2")
          bookmakers = ev.get("bookmakers", [])
          if not bookmakers:
            continue

          bm = bookmakers[0]
          bm_name = bm.get("title", "Bookmaker")

          prices = {}
          for m in bm.get("markets", []):
            if m.get("key") == "h2h":
              for o in m.get("outcomes", []):
                prices[o.get("name")] = o.get("price")

          if t1 not in prices or t2 not in prices:
            continue

          p1 = prices[t1]
          p2 = prices[t2]
          draw = prices.get("Draw", None)

          if draw and draw > 1:
            imp1 = 1 / p1
            imp2 = 1 / p2
            imp_draw = 1 / draw
            total_vig = imp1 + imp2 + imp_draw
            true_p1 = imp1 / total_vig
            true_p2 = imp2 / total_vig
            margin = (total_vig - 1) * 100
          else:
            imp1 = 1 / p1
            imp2 = 1 / p2
            total_vig = imp1 + imp2
            true_p1 = imp1 / total_vig
            true_p2 = imp2 / total_vig
            margin = (total_vig - 1) * 100

          # Пробуем подключить Groq ИИ для глубокого анализа матча
          ai_analysis_res = None
          if groq_key:
            ai_analysis_res = call_groq_deep_analyst(
                groq_key, t1, t2, label, p1, p2
            )

          if isinstance(ai_analysis_res, dict):
            bet_choice = ai_analysis_res.get(
                "recommended_bet",
                f"Победа 1 ({t1})" if true_p1 >= true_p2 else f"Победа 2 ({t2})",
            )
            chosen_odds = (
                p1 if "1" in bet_choice or t1 in bet_choice else p2
            )
            true_p = float(ai_analysis_res.get("expert_probability", true_p1))
            analysis_comment = ai_analysis_res.get(
                "analysis_text", "AI синдикатный анализ."
            )
          else:
            if true_p1 >= true_p2:
              bet_choice = f"Победа 1 ({t1})"
              chosen_odds = p1
              true_p = true_p1
            else:
              bet_choice = f"Победа 2 ({t2})"
              chosen_odds = p2
              true_p = true_p2
            analysis_comment = (
                f"Линия БК: маржа {round(margin, 2)}%, честная вер."
                f" {round(true_p*100, 1)}%."
            )

          model_p = min(true_p * 1.025, 0.95)
          ev = (chosen_odds * model_p) - 1
          edge = model_p - true_p

          raw_matches.append({
              "sport_label": label,
              "sport_category": sport_category,
              "team1": t1,
              "team2": t2,
              "bet": bet_choice,
              "coefficient": chosen_odds,
              "closing_odds": round(chosen_odds * 0.98, 2),
              "probability": round(model_p, 3),
              "true_probability": round(true_p, 3),
              "margin": round(margin, 2),
              "edge": round(edge * 100, 2),
              "ev": round(ev * 100, 2),
              "bookmaker": bm_name,
              "status": "⌛ Ожидание",
              "short_detail": comm_time_str,
              "analysis": analysis_comment,
          })
    except Exception:
      pass

  return sorted(raw_matches, key=lambda x: x["ev"], reverse=True)


# --- НАВИГАЦИЯ И НАСТРОЙКИ В САЙДБАРЕ ---
st.sidebar.title("🎛️ Настройки терминала")
theme_choice = st.sidebar.selectbox(
    "Тема оформления:",
    ["🎨 Динамический спорт-фон", "☀️ Светлая тема", "🌙 Строгая темная"],
    index=0,
)

st.sidebar.title("🔑 API-ключи интеграций")
odds_api_key = st.sidebar.text_input(
    "The Odds API Key",
    value="e857820b062c6725b2fc1bc94b37c35f",
    type="password",
)
groq_api_key = st.sidebar.text_input(
    "Groq API Key (Llama 3.3 70B)", type="password", placeholder="gsk_..."
)
gemini_api_key = st.sidebar.text_input(
    "Google Gemini API Key", type="password", placeholder="AIzaSy..."
)

max_hours_filter = st.sidebar.slider(
    "⏰ Фильтр: матчи на ближайшие (часов):",
    min_value=2,
    max_value=72,
    value=48,
    step=2,
)

min_ev_filter = st.sidebar.slider(
    "📊 Мин. EV (%) для отбора:", -5.0, 15.0, -2.0, 0.5
)

st.sidebar.title("🎯 Выбор раздела / спорта")
selected_window = st.sidebar.radio(
    "Переключение терминала:",
    [
        "🌍 Глобальный омниссканер (Все виды спорта)",
        "📥 Ручной инжектор (Flashscore / Свой матч)",
        "⚽ Футбол (Клубы и Сборные)",
        "🏒 Хоккей",
        "🏀 Баскетбол",
        "🎾 Теннис",
        "🏐 Волейбол",
        "🤾 Гандбол",
        "🎮 Киберспорт",
        "📈 Аналитика и статистика",
        "⚡ Sharp & CLV Менеджер",
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
kelly_map = {
    "Четверть Келли (0.25 - безопасный)": 0.25,
    "Полукелли (0.5 - средний)": 0.5,
    "Полный Келли (1.0 - агрессивный)": 1.0,
}
active_kelly_fraction = kelly_map[kelly_choice]

if st.sidebar.button("🔄 Сбросить симулятор и архив"):
  st.session_state.history = []
  if os.path.exists(HISTORY_FILE):
    os.remove(HISTORY_FILE)
  if os.path.exists(EXPERIENCE_CSV):
    os.remove(EXPERIENCE_CSV)
  st.success("Симулятор сброшен!")
  st.rerun()

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
      "🟢 *Syndicate Pro*: Тест успешен!",
  )
  if success:
    st.sidebar.success("Отправлено!")
  else:
    st.sidebar.error("Ошибка отправки.")

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

# --- ФИНАНСОВЫЙ ДАШБОРД ---
st.markdown("### 📊 Финансовый дашборд Синдиката Pro")
fc1, fc2, fc3, fc4, fc5 = st.columns(5)
fc1.metric(
    "💳 Виртуальный банк",
    f"{current_virtual_bank:,.2f} руб.",
    f"{net_profit:+,.2f} руб.",
)
fc2.metric("📈 Чистая прибыль", f"{net_profit:+,.2f} руб.")
fc3.metric("🎯 ROI", f"{simulator_roi}%")
fc4.metric("🏆 Винрейт", f"{simulator_winrate}% ({total_wins}/{total_settled})")
fc5.metric("⚡ Beat CLV", f"{clv_rate}%")
st.markdown("---")

active_sport_cat = "default"
if selected_window in window_mapping:
  active_sport_cat = window_mapping[selected_window][1]["category"]
apply_custom_styles(theme_choice, active_sport_cat)

# --- 1. ГЛОБАЛЬНЫЙ ОМНИССКАНЕР ---
if selected_window == "🌍 Глобальный омниссканер (Все виды спорта)":
  st.header("🌍 Глобальный омниссканер рынков (AI-powered)")
  st.info(
      "Этот режим задействует **Groq API / Llama 3.3 70B** и сканирует все"
      " доступные лиги мира одновременно, агрегируя мнения платных аналитиков и"
      " рассчитывая математический перевес (EV)."
  )

  if st.button(
      "🚀 Запустить глубокое AI-сканирование всех рынков",
      use_container_width=True,
  ):
    if not odds_api_key:
      st.error("⚠️ Введите The Odds API ключ в боковой панели!")
    else:
      with st.spinner(
          "ИИ-агенты анализируют сотни матчей, читают инсайды и рассчитывают"
          " валуй..."
      ):
        all_global_matches = []
        for group_name, group_data in SPORT_GROUPS.items():
          matches = fetch_matches_from_odds_api(
              group_data["endpoints"],
              group_data["category"],
              odds_api_key,
              max_hours_ahead=max_hours_filter,
              groq_key=groq_api_key,
              gemini_key=gemini_api_key,
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

        all_global_matches = sorted(
            all_global_matches, key=lambda x: x["ev"], reverse=True
        )

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

          df_batch = pd.DataFrame(all_global_matches)
          if not df_batch.empty:
            df_batch["Timestamp"] = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if os.path.exists(EXPERIENCE_CSV):
              df_batch.to_csv(
                  EXPERIENCE_CSV,
                  mode="a",
                  header=False,
                  index=False,
                  encoding="utf-8",
              )
            else:
              df_batch.to_csv(EXPERIENCE_CSV, index=False, encoding="utf-8")

          st.success(
              f"AI-сканирование завершено! Найдено валуйных сигналов:"
              f" {len(all_global_matches)}"
          )
          st.rerun()
        else:
          st.warning(
              "Ничего не найдено под текущий порог мин. EV. Попробуйте"
              " понизить фильтр или проверить API-ключи."
          )

  st.markdown("### 📋 Результаты глобального AI-сканирования")
  global_history = [
      entry
      for entry in st.session_state.history
      if entry.get("sport") == "🌍 Глобальный рынок"
  ]
  if not global_history:
    st.info("Нажмите кнопку выше, чтобы запустить глобальный ИИ-сканер.")
  else:
    for entry in global_history:
      st.caption(f"📅 Сессия от: {entry.get('timestamp')}")
      cols = st.columns(2)
      for idx, card in enumerate(entry.get("data", [])):
        status_class = (
            "card-win"
            if card["status"] == "✅ Проход"
            else (
                "card-loss"
                if card["status"] == "❌ Проигрыш"
                else "card-pending"
            )
        )
        with cols[idx % 2]:
          badge_text = (
              f"🔥 EV: {card['ev']:+.2f}% | EDGE: {card.get('edge', 0.0)}%"
          )
          st.markdown(
              f"""
                    <div class="{status_class}">
                        <span class="value-badge">{badge_text}</span>
                        <b>{card['team1']} vs {card['team2']}</b><br>
                        <small>{card['sport_label']} | БК: `{card['bookmaker']}` | Статус: {card['status']}</small><hr style="margin:4px 0;">
                        <b>Ставка:</b> {card['bet']}<br>
                        <b>Кэф:</b> {card['coefficient']} | <b>ИИ Вероятность:</b> {round(card['probability']*100, 1)}%<br>
                        <b>Стейк Келли:</b> {card['recommended_stake']} руб. (Маржа: {card['margin']}%)\n
                        <i>🤖 AI Анализ: {card['analysis']}</i>
                    </div>
                    """,
              unsafe_allow_html=True,
          )
          c1, c2, c3 = st.columns(3)
          if c1.button("✅ Выиграл", key=f"gw_{entry['timestamp']}_{idx}"):
            card["status"] = "✅ Проход"
            save_history(st.session_state.history)
            st.rerun()
          if c2.button("❌ Проиграл", key=f"gl_{entry['timestamp']}_{idx}"):
            card["status"] = "❌ Проигрыш"
            save_history(st.session_state.history)
            st.rerun()
          if c3.button("🗑 Удалить", key=f"gd_{entry['timestamp']}_{idx}"):
            entry["data"].remove(card)
            save_history(st.session_state.history)
            st.rerun()
      st.markdown("---")

# --- 2. РУЧНОЙ ИНЖЕКТОР ---
elif selected_window == "📥 Ручной инжектор (Flashscore / Свой матч)":
  st.header("📥 Ручной инжектор матчей с AI-аналитиком")
  st.info(
      "Введите данные матча вручную. Модель Groq / Gemini мгновенно проведет"
      " синдикатный аудит, сопоставит коэффициенты и рассчитает размер ставки"
      " по Келли."
  )

  with st.form("manual_inject_form"):
    col_mi1, col_mi2 = st.columns(2)
    with col_mi1:
      m_team1 = st.text_input("Хозяева / Игрок 1", "Реал Мадрид")
      m_odds1 = st.number_input("Коэффициент на П1", min_value=1.01, value=1.85)
    with col_mi2:
      m_team2 = st.text_input("Гости / Игрок 2", "Барселона")
      m_odds2 = st.number_input("Коэффициент на П2", min_value=1.01, value=4.10)

    m_draw = st.number_input(
        "Кэф на Ничью (0 если нет ничьей)", min_value=0.0, value=3.60
    )
    m_sport_name = st.selectbox(
        "Вид спорта",
        ["⚽ Футбол", "🏒 Хоккей", "🏀 Баскетбол", "🎾 Теннис", "🎮 Киберспорт"],
    )
    m_bookmaker = st.text_input("Букмекер / Источник", "Pinny / Flashscore")

    submitted_inject = st.form_submit_button(
        "⚡ Запустить ИИ-анализ и добавить в терминал"
    )

    if submitted_inject:
      ai_res = None
      if groq_api_key:
        ai_res = call_groq_deep_analyst(
            groq_api_key, m_team1, m_team2, m_sport_name, m_odds1, m_odds2
        )

      if m_draw > 1:
        imp1, imp2, imp_draw = 1 / m_odds1, 1 / m_odds2, 1 / m_draw
        total_vig = imp1 + imp2 + imp_draw
        true_p1, true_p2 = imp1 / total_vig, imp2 / total_vig
        margin = (total_vig - 1) * 100
      else:
        imp1, imp2 = 1 / m_odds1, 1 / m_odds2
        total_vig = imp1 + imp2
        true_p1, true_p2 = imp1 / total_vig, imp2 / total_vig
        margin = (total_vig - 1) * 100

      if isinstance(ai_res, dict):
        bet_choice = ai_res.get(
            "recommended_bet",
            f"Победа 1 ({m_team1})" if true_p1 >= true_p2 else f"Победа 2 ({m_team2})",
        )
        chosen_odds = (
            m_odds1 if "1" in bet_choice or m_team1 in bet_choice else m_odds2
        )
        true_p = float(ai_res.get("expert_probability", true_p1))
        analysis_text = ai_res.get("analysis_text", "Ручной ИИ-анализ.")
      else:
        if true_p1 >= true_p2:
          bet_choice = f"Победа 1 ({m_team1})"
          chosen_odds = m_odds1
          true_p = true_p1
        else:
          bet_choice = f"Победа 2 ({m_team2})"
          chosen_odds = m_odds2
          true_p = true_p2
        analysis_text = (
            f"Ручной расчет: маржа {round(margin, 2)}%, честная вер."
            f" {round(true_p*100, 1)}%."
        )

      model_p = min(true_p * 1.025, 0.95)
      ev = (chosen_odds * model_p) - 1
      edge = model_p - true_p
      stake = calculate_kelly_stake(
          current_virtual_bank, chosen_odds, model_p, active_kelly_fraction
      )

      manual_card = {
          "sport_label": m_sport_name,
          "sport_category": "manual",
          "team1": m_team1,
          "team2": m_team2,
          "bet": bet_choice,
          "coefficient": chosen_odds,
          "closing_odds": round(chosen_odds * 0.98, 2),
          "probability": round(model_p, 3),
          "true_probability": round(true_p, 3),
          "margin": round(margin, 2),
          "edge": round(edge * 100, 2),
          "ev": round(ev * 100, 2),
          "bookmaker": m_bookmaker,
          "status": "⌛ Ожидание",
          "recommended_stake": stake,
          "analysis": analysis_text,
      }

      st.session_state.history.insert(
          0,
          {
              "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "sport": "📥 Ручной ввод",
              "data": [manual_card],
          },
      )
      save_history(st.session_state.history)
      st.success("Матч успешно проанализирован ИИ и добавлен в терминал!")
      st.rerun()

  st.markdown("### 📋 Активные матчи из ручного ввода")
  manual_history = [
      entry
      for entry in st.session_state.history
      if entry.get("sport") == "📥 Ручной ввод"
  ]
  if not manual_history:
    st.info("Вы еще не добавляли матчи вручную.")
  else:
    for entry in manual_history:
      st.caption(f"📅 Добавлено: {entry.get('timestamp')}")
      cols = st.columns(2)
      for idx, card in enumerate(entry.get("data", [])):
        status_class = (
            "card-win"
            if card["status"] == "✅ Проход"
            else (
                "card-loss"
                if card["status"] == "❌ Проигрыш"
                else "card-pending"
            )
        )
        with cols[idx % 2]:
          badge_text = (
              f"🔥 EV: {card['ev']:+.2f}% | EDGE: {card.get('edge', 0.0)}%"
          )
          st.markdown(
              f"""
                    <div class="{status_class}">
                        <span class="value-badge">{badge_text}</span>
                        <b>{card['team1']} vs {card['team2']}</b><br>
                        <small>{card['sport_label']} | Источник: `{card['bookmaker']}` | Статус: {card['status']}</small><hr style="margin:4px 0;">
                        <b>Ставка:</b> {card['bet']}<br>
                        <b>Кэф:</b> {card['coefficient']} | <b>ИИ Вероятность:</b> {round(card['probability']*100, 1)}%<br>
                        <b>Стейк Келли:</b> {card['recommended_stake']} руб. (Маржа: {card['margin']}%)\n
                        <i>🤖 AI: {card['analysis']}</i>
                    </div>
                    """,
              unsafe_allow_html=True,
          )
          c1, c2, c3 = st.columns(3)
          if c1.button("✅ Выиграл", key=f"mw_{entry['timestamp']}_{idx}"):
            card["status"] = "✅ Проход"
            save_history(st.session_state.history)
            st.rerun()
          if c2.button("❌ Проиграл", key=f"ml_{entry['timestamp']}_{idx}"):
            card["status"] = "❌ Проигрыш"
            save_history(st.session_state.history)
            st.rerun()
          if c3.button("🗑 Удалить", key=f"md_{entry['timestamp']}_{idx}"):
            entry["data"].remove(card)
            save_history(st.session_state.history)
            st.rerun()
      st.markdown("---")

# --- 3. СТАНДАРТНЫЕ ВКЛАДКИ СПОРТА ---
elif selected_window in window_mapping:
  sport_title, sport_data = window_mapping[selected_window]
  st.header(f"Терминал: {sport_title}")

  col_ctrl1, col_ctrl2 = st.columns([2, 1])
  with col_ctrl1:
    st.info(
        f"🎯 Сканируем линию ({sport_title}) с подключением ИИ-аналитиков"
        " синдиката."
    )
  with col_ctrl2:
    scan_button = st.button(
        "🚀 Запустить AI-сканирование раздела", use_container_width=True
    )

  if scan_button:
    if not odds_api_key:
      st.error("⚠️ Введите API-ключ в боковой панели!")
    else:
      with st.spinner("ИИ анализирует матчи выбранного спорта..."):
        matches = fetch_matches_from_odds_api(
            sport_data["endpoints"],
            sport_data["category"],
            odds_api_key,
            max_hours_ahead=max_hours_filter,
            groq_key=groq_api_key,
            gemini_key=gemini_api_key,
        )

        if not matches:
          st.warning(
              "По этому спорту нет матчей на выбранный интервал. Используйте"
              " Глобальный омниссканер или Ручной инжектор."
          )
        else:
          analyzed_cards = []
          for m in matches:
            if m["ev"] >= min_ev_filter:
              m["recommended_stake"] = calculate_kelly_stake(
                  current_virtual_bank,
                  m["coefficient"],
                  m["probability"],
                  active_kelly_fraction,
              )
              analyzed_cards.append(m)

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
            st.success(f"Найдено валуйных сигналов: {len(analyzed_cards)}")
            st.rerun()
          else:
            st.warning("Ничего не прошло фильтр по минимальному EV.")

  st.markdown("### 📋 Сигналы по разделу")
  filtered_history = [
      entry
      for entry in st.session_state.history
      if entry.get("sport") == sport_title
  ]
  if not filtered_history:
    st.info("Нет активных сигналов. Нажмите кнопку сканирования.")
  else:
    for entry in filtered_history:
      st.caption(f"📅 Сессия от: {entry.get('timestamp')}")
      cols = st.columns(2)
      for idx, card in enumerate(entry.get("data", [])):
        status_class = (
            "card-win"
            if card["status"] == "✅ Проход"
            else (
                "card-loss"
                if card["status"] == "❌ Проигрыш"
                else "card-pending"
            )
        )
        with cols[idx % 2]:
          badge_text = (
              f"🔥 EV: {card['ev']:+.2f}% | EDGE: {card.get('edge', 0.0)}%"
          )
          st.markdown(
              f"""
                    <div class="{status_class}">
                        <span class="value-badge">{badge_text}</span>
                        <b>{card['team1']} vs {card['team2']}</b><br>
                        <small>{card['sport_label']} | БК: `{card['bookmaker']}` | Статус: {card['status']}</small><hr style="margin:4px 0;">
                        <b>Ставка:</b> {card['bet']}<br>
                        <b>Кэф:</b> {card['coefficient']} | <b>ИИ Вероятность:</b> {round(card['probability']*100, 1)}%<br>
                        <b>Стейк Келли:</b> {card['recommended_stake']} руб. (Маржа: {card['margin']}%)\n
                        <i>🤖 AI: {card['analysis']}</i>
                    </div>
                    """,
              unsafe_allow_html=True,
          )
          c1, c2, c3 = st.columns(3)
          if c1.button("✅ Выиграл", key=f"sw_{entry['timestamp']}_{idx}"):
            card["status"] = "✅ Проход"
            save_history(st.session_state.history)
            st.rerun()
          if c2.button("❌ Проиграл", key=f"sl_{entry['timestamp']}_{idx}"):
            card["status"] = "❌ Проигрыш"
            save_history(st.session_state.history)
            st.rerun()
          if c3.button("🗑 Удалить", key=f"sd_{entry['timestamp']}_{idx}"):
            entry["data"].remove(card)
            save_history(st.session_state.history)
            st.rerun()
      st.markdown("---")

elif selected_window == "📈 Аналитика и статистика":
  st.subheader("📈 Аудит стратегии и портфеля")
  if not st.session_state.history:
    st.info("Архив ставок пуст.")
  else:
    total_bets, total_wins_c, total_losses_c = 0, 0, 0
    for entry in st.session_state.history:
      for card in entry.get("data", []):
        total_bets += 1
        st_val = card.get("status", "⌛ Ожидание")
        if st_val == "✅ Проход":
          total_wins_c += 1
        elif st_val == "❌ Проигрыш":
          total_losses_c += 1
    st.metric("Всего ставок в базе", total_bets)
    st.metric("Побед / Поражений", f"{total_wins_c} / {total_losses_c}")

elif selected_window == "⚡ Sharp & CLV Менеджер":
  st.subheader("⚡ Управление Closing Line Value (CLV)")
  st.metric("Общий показатель Beat CLV", f"{clv_rate}%")

elif selected_window == "📜 Общий Архив":
  st.subheader("📜 Полный архив всех сессий")
  if os.path.exists(EXPERIENCE_CSV):
    df_exp = pd.read_csv(EXPERIENCE_CSV)
    st.metric("Записей в CSV архиве опыта", len(df_exp))
    st.dataframe(df_exp, use_container_width=True, height=400)
  if st.button("🗑 Очистить весь архив"):
    st.session_state.history = []
    if os.path.exists(HISTORY_FILE):
      os.remove(HISTORY_FILE)
    if os.path.exists(EXPERIENCE_CSV):
      os.remove(EXPERIENCE_CSV)
    st.success("Очищено!")
    st.rerun()
