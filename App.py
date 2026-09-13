import json
import os
import requests
import streamlit as st

# Настройка страницы
st.set_page_config(
    page_title="Pro Sports Betting Scanner", page_icon="⚽", layout="wide"
)

HISTORY_FILE = "match_history_pro.json"


# --- Функция загрузки истории с защитой от старого формата (исправляет TypeError) ---
def load_history():
  if os.path.exists(HISTORY_FILE):
    try:
      with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        # Если в файле старый формат (список), автоматически конвертируем в словарь
        if isinstance(data, list):
          return {"bankroll": 1000.0, "bets": []}
        return data
    except Exception:
      pass
  return {"bankroll": 1000.0, "bets": []}


def save_history(data):
  try:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
      json.dump(data, f, ensure_ascii=False, indent=4)
  except Exception:
    pass


# --- Боковая панель: Настройки ---
st.sidebar.title("⚙️ Управление сканером")

odds_api_key = st.sidebar.text_input(
    "🔑 The Odds API Key",
    type="password",
    help="Введите бесплатный ключ с сайта the-odds-api.com",
)

# Словарь доступных чемпионатов
sport_leagues = {
    "⚽ Англия: АПЛ (Premier League)": "soccer_epl",
    "⚽ Испания: Ла Лига (La Liga)": "soccer_spain_la_liga",
    "⚽ Италия: Серия А (Serie A)": "soccer_italy_serie_a",
    "⚽ Германия: Бундеслига (Bundesliga)": "soccer_germany_bundesliga",
    "🏀 Баскетбол: NBA": "basketball_nba",
    "🏒 Хоккей: NHL": "icehockey_nhl",
}

selected_label = st.sidebar.selectbox(
    "Выберите чемпионат:", list(sport_leagues.keys())
)
selected_sport_key = sport_leagues[selected_label]

st.sidebar.markdown("---")


# --- Функция получения реальных коэффициентов от БК ---
def fetch_real_bookmaker_matches(sport_key, api_key):
  if not api_key:
    st.sidebar.warning("⚠️ Введите API-ключ вверху сайдбара!")
    return []

  url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
  params = {
      "apiKey": api_key,
      "regions": "eu",  # Европейские букмекеры
      "markets": "h2h",  # Основные исходы (П1, Х, П2)
      "oddsFormat": "decimal",
  }

  real_matches = []
  try:
    resp = requests.get(url, params=params, timeout=5)
    if resp.status_code == 200:
      events = resp.json()
      for ev in events:
        t1 = ev.get("home_team")
        t2 = ev.get("away_team")
        comm_time = ev.get("commence_time", "")

        # Значения по умолчанию на случай отсутствия рынка
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

        real_matches.append({
            "sport_label": selected_label,
            "team1": t1,
            "team2": t2,
            "team1_logo": f"https://ui-avatars.com/api/?name={t1}&background=1e293b&color=00ff66",
            "team2_logo": f"https://ui-avatars.com/api/?name={t2}&background=1e293b&color=00bfff",
            "status": (
                f"⏳ Начало: {comm_time[11:16]} (МСК)"
                if len(comm_time) >= 16
                else "⏳ Скоро"
            ),
            "real_odds": {"1": odds_1, "X": odds_x, "2": odds_2},
        })
    elif resp.status_code == 401:
      st.error(
          "❌ Ошибка 401: Неверный API-ключ The Odds API. Проверьте правильность"
          " ввода."
      )
  except Exception as e:
    st.error(f"Ошибка соединения с API: {e}")

  return real_matches


# --- Главная страница приложения ---
st.title("📊 Pro Multi-Sport Betting Scanner")
st.markdown(
    "Инструмент для сканирования матчей и анализа букмекерских коэффициентов в"
    " реальном времени."
)

history = load_history()

# Верхняя панель метрик банка
col_m1, col_m2 = st.columns(2)
with col_m1:
  st.metric(label="💰 Виртуальный банк", value=f"{history['bankroll']:.2f} USD")
with col_m2:
  st.metric(
      label="📂 Сохраненных ставок", value=len(history.get("bets", []))
  )

st.markdown("---")

# Кнопка запуска сканирования в сайдбаре
if st.sidebar.button("🔍 Загрузить линию БК", type="primary"):
  with st.spinner("Запрос актуальных коэффициентов у букмекеров..."):
    matches = fetch_real_bookmaker_matches(selected_sport_key, odds_api_key)
    if matches:
      st.session_state["matches"] = matches
      st.success(f"Успешно загружено матчей: {len(matches)}")
    else:
      st.session_state["matches"] = []

# Вывод списка матчей, если они загружены в сессию
if "matches" in st.session_state and st.session_state["matches"]:
  st.subheader(f"📋 Линия матчей: {selected_label}")

  for idx, match in enumerate(st.session_state["matches"]):
    with st.container():
      st.markdown(
          f"#### 🏟️ {match['team1']} &nbsp;&nbsp;VS&nbsp;&nbsp;"
          f" {match['team2']}"
      )
      c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])

      with c1:
        st.write(match["status"])
      with c2:
        st.info(f"П1: **{match['real_odds']['1']}**")
      with c3:
        st.info(f"Х: **{match['real_odds']['X']}**")
      with c4:
        st.info(f"П2: **{match['real_odds']['2']}**")
      with c5:
        if st.button("🤖 Анализ", key=f"btn_{idx}"):
          st.success(
              f"Запущен расчет валуйности для: {match['team1']} —"
              f" {match['team2']}"
          )

      st.markdown("---")
else:
  st.info(
      "👈 Введите ваш API-ключ в боковой панели слева и нажмите кнопку"
      " **«Загрузить линию БК»**."
  )
