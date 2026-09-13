
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
import random
import re
import time
from google import genai
from google.genai import types
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
    page_title="Syndicate Pro: Dual-AI Consensus Terminal",
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
        ],
    },
    "🏒 Хоккей": {
        "category": "hockey",
        "endpoints": [
            ("icehockey_nhl", "НХЛ (США/Канада)"),
            ("icehockey_khl", "КХЛ (Россия/Евразия)"),
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
            ("tennis_atp_match", "ATP Международные"),
            ("tennis_wta_aus_open", "WTA Турниры"),
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


# --- АНАЛИТИК 1: GROQ (LLAMA 3.3) ---
def call_groq_deep_analyst(groq_api_key, team1, team2, sport_label, odds1, odds2):
  if not groq_api_key:
    return None
  try:
    client = Groq(api_key=groq_api_key)
    prompt = f"""
        Ты — элитный спортивный капер и синдикатный аналитик с 20-летним стажем. 
        Проанализируй матч: {team1} vs {team2} ({sport_label}). 
        Коэффициенты БК: П1 = {odds1}, П2 = {odds2}.
        Оцени текущую форму команд, мотивацию и статистику. Выдай экспертный вердикт на русском языке в формате строгого JSON с полями:
        - "recommended_bet": точная ставка (например, "Победа 1 ({team1})")
        - "expert_probability": число от 0.50 до 0.90 (реальная вероятность исхода)
        - "analysis_text": глубокий аналитический разбор на 2-3 предложения с обоснованием валуя (EV).
        Отвечай ТОЛЬКО валидным JSON без лишнего текста.
        """
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return json.loads(completion.choices[0].message.content)
  except Exception:
    return None


# --- АНАЛИТИК 2: GEMINI ---
def call_gemini_deep_analyst(
    gemini_api_key, team1, team2, sport_label, odds1, odds2
):
  if not gemini_api_key:
    return None
  try:
    client = genai.Client(api_key=gemini_api_key)
    prompt = f"""
        Ты — элитный спортивный капер и математический статист синдиката. 
        Проанализируй матч: {team1} vs {team2} ({sport_label}). 
        Коэффициенты БК: П1 = {odds1}, П2 = {odds2}.
        Оцени потенциал команд и вероятности. Выдай вердикт на русском языке в формате строгого JSON с полями:
        - "recommended_bet": точная ставка (например, "Победа 1 ({team1})")
        - "expert_probability": число от 0.50 до 0.90 (реальная вероятность исхода)
        - "analysis_text": глубокий аналитический разбор на 2-3 предложения.
        Отвечай ТОЛЬКО валидным JSON без маркдауна и лишнего текста.
        """
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)
  except Exception:
    return None


# --- ОБЪЕДИНЕННЫЙ КОНСЕНСУС ИИ (GROQ + GEMINI) ---
def get_dual_ai_consensus(
    groq_key, gemini_key, t1, t2, label, p1, p2, market_margin, implied_p1
):
  groq_res = (
      call_groq_deep_analyst(groq_key, t1, t2, label, p1, p2)
      if groq_key
      else None
  )
  gemini_res = (
      call_gemini_deep_analyst(gemini_key, t1, t2, label, p1, p2)
      if gemini_key
      else None
  )

  # Если оба ИИ дали ответ — делаем консенсус
  if isinstance(groq_res, dict) and isinstance(gemini_res, dict):
    bet_choice = groq_res.get(
        "recommended_bet", f"Победа 1 ({t1})"
    )  # Приоритет Groq или совпадение
    chosen_odds = p1 if "1" in bet_choice or t1 in bet_choice else p2

    prob_groq = float(groq_res.get("expert_probability", 0.7))
    prob_gemini = float(gemini_res.get("expert_probability", 0.7))
    consensus_prob = round((prob_groq + prob_gemini) / 2, 3)

    analysis_comment = (
        f"🤖 Groq: {groq_res.get('analysis_text', '')} | 💎 Gemini:"
        f" {gemini_res.get('analysis_text', '')}"
    )

  elif isinstance(groq_res, dict):
    bet_choice = groq_res.get("recommended_bet", f"Победа 1 ({t1})")
    chosen_odds = p1 if "1" in bet_choice or t1 in bet_choice else p2
    consensus_prob = float(groq_res.get("expert_probability", 0.75))
    analysis_comment = f"🤖 Groq (Solo): {groq_res.get('analysis_text', '')}"

  elif isinstance(gemini_res, dict):
    bet_choice = gemini_res.get("recommended_bet", f"Победа 1 ({t1})")
    chosen_odds = p1 if "1" in bet_choice or t1 in bet_choice else p2
    consensus_prob = float(gemini_res.get("expert_probability", 0.75))
    analysis_comment = (
        f"💎 Gemini (Solo): {gemini_res.get('analysis_text', '')}"
    )

  else:
    # Базовый расчет по линии если ключи ИИ не указаны
    if implied_p1 >= 0.5:
      bet_choice, chosen_odds, consensus_prob = f"Победа 1 ({t1})", p1, 0.72
    else:
      bet_choice, chosen_odds, consensus_prob = f"Победа 2 ({t2})", p2, 0.72
    analysis_comment = f"Математический расчет по линии (маржа {market_margin}%)."

  ev = (chosen_odds * consensus_prob) - 1
  edge = consensus_prob - implied_p1
  rec_status = "green" if ev >= 1.5 else ("blue" if ev >= -2.0 else "red")

  return {
      "bet": bet_choice,
      "coefficient": chosen_odds,
      "probability": consensus_prob,
      "ev": round(ev * 100, 2),
      "edge": round(edge * 100, 2),
      "rec_status": rec_status,
      "analysis": analysis_comment,
  }


# --- ЗАГРУЗЧИК МАТЧЕЙ ---
def fetch_matches_from_odds_api(
    endpoints_list,
    sport_category,
    api_key,
    groq_key="",
    gemini_key="",
):
  raw_matches = []
  if not api_key:
    return raw_matches

  for sport_key, label in endpoints_list:
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {
        "apiKey": api_key,
        "regions": "eu,us",
        "markets": "h2h",
        "oddsFormat": "decimal",
    }
    try:
      resp = requests.get(url, params=params, timeout=4)
      if resp.status_code == 200:
        events = resp.json()
        if events:
          for ev in events:
            t1 = ev.get("home_team", "Команда 1")
            t2 = ev.get("away_team", "Команда 2")
            bookmakers = ev.get("bookmakers", [])
            if not bookmakers:
                continue
            bm = bookmakers[0]
            prices = {}
            for m in bm.get("markets", []):
              if m.get("key") == "h2h":
                for o in m.get("outcomes", []):
                  prices[o.get("name")] = o.get("price")
            if t1 not in prices or t2 not in prices:
              continue
            p1, p2 = prices[t1], prices[t2]

            imp1 = 1 / p1
            imp2 = 1 / p2
            total_vig = imp1 + imp2
            true_p1 = imp1 / total_vig
            margin = round((total_vig - 1) * 100, 2)

            # Получаем консенсус от Groq + Gemini
            consensus = get_dual_ai_consensus(
                groq_key, gemini_key, t1, t2, label, p1, p2, margin, true_p1
            )

            raw_matches.append({
                "sport_label": label,
                "sport_category": sport_category,
                "team1": t1,
                "team2": t2,
                "bet": consensus["bet"],
                "coefficient": consensus["coefficient"],
                "closing_odds": round(consensus["coefficient"] * 0.98, 2),
                "probability": consensus["probability"],
                "true_probability": round(true_p1, 3),
                "margin": margin,
                "edge": consensus["edge"],
                "ev": consensus["ev"],
                "bookmaker": bm.get("title", "БК"),
                "status": "⌛ Ожидание",
                "rec_status": consensus["rec_status"],
                "analysis": consensus["analysis"],
            })
    except Exception:
      pass

  return sorted(raw_matches, key=lambda x: x["ev"], reverse=True)


# --- САЙДБАР ---
st.sidebar.title("🎛️ Настройки терминала")
theme_choice = st.sidebar.selectbox(
    "Тема оформления:",
    ["🎨 Динамический спорт-фон", "☀️ Светлая тема", "🌙 Строгая темная"],
    index=0,
)

st.sidebar.title("🔑 API-ключи Совет ИИ")
odds_api_key = st.sidebar.text_input(
    "The Odds API Key", value="", type="password"
)
groq_api_key = st.sidebar.text_input(
    "Groq API Key (Llama 3.3)", type="password", placeholder="gsk_..."
)
gemini_api_key = st.sidebar.text_input(
    "Gemini API Key", type="password", placeholder="AIzaSy..."
)

max_hours_filter = st.sidebar.slider(
    "⏰ Фильтр: матчи на ближайшие (часов):", 2, 72, 48, 2
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
  if os.path.exists(EXPERIENCE_CSV):
    os.remove(EXPERIENCE_CSV)
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
st.markdown("### 📊 Финансовый дашборд Синдиката Pro (Dual-AI)")
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
    badge_text = f"🔥 EV: {ev_val:+.2f}% | Консенсус Совет ИИ (Groq + Gemini)"

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
  st.header("🌍 Глобальный омниссканер рынков (Консенсус ИИ)")
  st.info(
      "Многопоточный сканер собирает матчи, после чего Groq и Gemini совместно"
      " проводят аналитический разбор."
  )

  if st.button("🚀 Запустить сканирование с Советом ИИ", use_container_width=True):
    with st.spinner(
        "Сканирование линии и одновременный консенсус-анализ Groq + Gemini..."
    ):
      all_global_matches = []
      for group_name, group_data in SPORT_GROUPS.items():
        matches = fetch_matches_from_odds_api(
            group_data["endpoints"],
            group_data["category"],
            odds_api_key,
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
        st.warning(
            "Матчи не найдены. Проверьте правильность введенного The Odds API"
            " ключа."
        )

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

      consensus = get_dual_ai_consensus(
          groq_api_key,
          gemini_api_key,
          t1,
          t2,
          sport_lbl,
          o1,
          o2,
          margin,
          true_p1,
      )
      stake = calculate_kelly_stake(
          current_virtual_bank,
          consensus["coefficient"],
          consensus["probability"],
          active_kelly_fraction,
      )

      card = {
          "sport_label": sport_lbl,
          "sport_category": "manual",
          "team1": t1,
          "team2": t2,
          "bet": consensus["bet"],
          "coefficient": consensus["coefficient"],
          "closing_odds": round(consensus["coefficient"] * 0.98, 2),
          "probability": consensus["probability"],
          "true_probability": round(true_p1, 3),
          "margin": margin,
          "edge": consensus["edge"],
          "ev": consensus["ev"],
          "bookmaker": "Ручной инжектор",
          "status": "⌛ Ожидание",
          "rec_status": consensus["rec_status"],
          "recommended_stake": stake,
          "analysis": consensus["analysis"],
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
      f"🚀 Запустить анализ Совета ИИ ({sport_title})", use_container_width=True
  ):
    with st.spinner("Запрос к Groq и Gemini..."):
      matches = fetch_matches_from_odds_api(
          sport_data["endpoints"],
          sport_data["category"],
          odds_api_key,
          groq_key=groq_api_key,
          gemini_key=gemini_api_key,
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
        st.warning(
            "Матчи не получены. Проверьте правильность The Odds API ключа в"
            " сайдбаре."
        )

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
