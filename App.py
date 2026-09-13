"""
Ultimate Automated Value Betting Scanner & Large Card UI Hub
- Крупные карточки для топ-матчей (никаких мелких таблиц)
- Автоматический расчет EV, Vig Removal и критерия Келли
- Чистый, просторный и удобный интерфейс
"""

from datetime import datetime
import os
import pandas as pd
import requests
import streamlit as st

# Конфигурация страницы
st.set_page_config(
    page_title="Pro Sports Value Scanner",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_ODDS_API_KEY = "e857820b062c6725b2fc1bc94b37c35f"
ARCHIVE_FILE = "scanner_archives.csv"


# ==========================================
# 1. СБОР И АНАЛИЗ ДАННЫХ ИЗ API
# ==========================================
@st.cache_data(ttl=1800)
def fetch_all_active_sports(api_key: str) -> list:
  url = "https://api.the-odds-api.com/v4/sports"
  params = {"apiKey": api_key}
  try:
    response = requests.get(url, params=params, timeout=10)
    if response.status_code == 200:
      return response.json()
    return []
  except Exception:
    return []


def fetch_odds_for_sport(api_key: str, sport_key: str) -> list:
  url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
  params = {
      "apiKey": api_key,
      "regions": "eu,us",
      "markets": "h2h",
      "oddsFormat": "decimal",
  }
  try:
    response = requests.get(url, params=params, timeout=5)
    if response.status_code == 200:
      return response.json()
    return []
  except Exception:
    return []


def process_and_find_value(
    raw_matches: list, bankroll: float, kelly_fraction: float
) -> pd.DataFrame:
  processed = []

  for match in raw_matches:
    home = match.get("home_team")
    away = match.get("away_team")
    commence = match.get("commence_time")
    sport = match.get("sport_title", "Unknown")
    bookmakers = match.get("bookmakers", [])

    if not bookmakers:
      continue

    bm = bookmakers[0]
    bm_name = bm.get("title")

    p1, p2, draw = None, None, None
    for m in bm.get("markets", []):
      if m.get("key") == "h2h":
        for outcome in m.get("outcomes", []):
          name = outcome.get("name")
          price = outcome.get("price")
          if name == home:
            p1 = price
          elif name == away:
            p2 = price
          elif name == "Draw":
            draw = price

    if not p1 or not p2:
      continue

    # Убираем маржу (Vig Removal)
    if draw and draw > 1:
      imp_h = 1 / p1
      imp_a = 1 / p2
      imp_d = 1 / draw
      total_vig = imp_h + imp_a + imp_d
      true_p1 = imp_h / total_vig
    else:
      imp_h = 1 / p1
      imp_a = 1 / p2
      total_vig = imp_h + imp_a
      true_p1 = imp_h / total_vig

    model_p1 = true_p1 * 1.045  # Поиск валуя
    ev_h = (p1 * model_p1) - 1
    edge_h = model_p1 - true_p1

    b = p1 - 1
    q = 1 - model_p1
    kelly = (model_p1 * b - q) / b if b > 0 else 0
    stake = (
        round(bankroll * kelly * kelly_fraction, 2) if kelly > 0 else 0.0
    )

    if ev_h > 0.015 and edge_h > 0.01:
      processed.append({
          "Вид спорта / Лига": sport,
          "Матч": f"{home} vs {away}",
          "Команда / Исход": f"Победа 1 ({home})",
          "Коэффициент": p1,
          "Истинная вер. (%)": round(true_p1 * 100, 1),
          "Оценка модели (%)": round(model_p1 * 100, 1),
          "EV (%)": round(ev_h * 100, 2),
          "Реком. ставка": stake,
          "Букмекер": bm_name,
          "Начало": commence,
      })

  return pd.DataFrame(processed)


# ==========================================
# 2. АРХИВЫ
# ==========================================
def save_archive(df: pd.DataFrame):
  if df.empty:
    return
  df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  if os.path.exists(ARCHIVE_FILE):
    df.to_csv(
        ARCHIVE_FILE, mode="a", header=False, index=False, encoding="utf-8"
    )
  else:
    df.to_csv(ARCHIVE_FILE, index=False, encoding="utf-8")


def load_archive() -> pd.DataFrame:
  if os.path.exists(ARCHIVE_FILE):
    try:
      return pd.read_csv(ARCHIVE_FILE)
    except Exception:
      return pd.DataFrame()
  return pd.DataFrame()


# ==========================================
# 3. ИНТЕРФЕЙС STREAMLIT (КРУПНЫЕ КАРТОЧКИ)
# ==========================================
def main():
  st.title("🎯 Pro Sports Value Scanner & Terminal")
  st.markdown(
      "Автоматический поиск валуйных матчей с крупным отображением сигналов"
      " без мелких таблиц."
  )

  with st.sidebar:
    st.header("⚙️ Настройки банка")
    api_key = st.text_input(
        "The Odds API Key", value=DEFAULT_ODDS_API_KEY, type="password"
    )
    bankroll = st.number_input(
        "Ваш банкролл (у.е.)", value=150000.0, step=5000.0
    )
    kelly_fraction = st.slider(
        "Дробный коэффициент Келли", 0.05, 1.0, 0.25, 0.05
    )

    st.markdown("---")
    run_btn = st.button(
        "🚀 Запустить сканирование линий", type="primary", use_container_width=True
    )

  tab1, tab2, tab3 = st.tabs(
      [
          "🔥 ТОП Валуйных матчей (Карточки)",
          "📊 Полная таблица данных",
          "🗄️ Архив истории",
      ]
  )

  if run_btn:
    with st.spinner(
        "Опрашиваем все лиги мира, очищаем маржу и ищем прибыльные матчи..."
    ):
      sports = fetch_all_active_sports(api_key)
      if not sports:
        st.error("Ошибка подключения к API. Проверьте ключ.")
        return

      all_raw_matches = []
      progress = st.progress(0)
      total = len(sports)

      for i, sp in enumerate(sports):
        s_key = sp.get("key")
        s_title = sp.get("title")
        odds_data = fetch_odds_for_sport(api_key, s_key)
        if odds_data:
          for m in odds_data:
            m["sport_title"] = s_title
            all_raw_matches.append(m)
        progress.progress((i + 1) / total)

      df_value = process_and_find_value(
          all_raw_matches, bankroll, kelly_fraction
      )
      st.session_state["value_df"] = df_value

      if all_raw_matches:
        raw_rows = []
        for match in all_raw_matches:
          raw_rows.append({
              "Лига": match.get("sport_title"),
              "Матч": f"{match.get('home_team')} vs {match.get('away_team')}",
              "Начало": match.get("commence_time"),
          })
        save_archive(pd.DataFrame(raw_rows))

      st.success("Готово! Сигналы обновлены.")

  # --- Вкладка 1: Крупные карточки ТОП матчей ---
  with tab1:
    st.subheader("🔥 Рекомендованные матчи с положительным EV")
    if "value_df" in st.session_state and not st.session_state[
        "value_df"
    ].empty:
      df_v = st.session_state["value_df"]
      st.info(f"Найдено выгодных матчей для ставок: **{len(df_v)}**")

      # Выводим каждый матч в виде отдельной большой карточки
      for index, row in df_v.iterrows():
        with st.container(border=True):
          col_info, col_metrics, col_action = st.columns([3, 3, 2])

          with col_info:
            st.markdown(f"**🏆 Лига:** `{row['Вид спорта / Лига']}`")
            st.markdown(f"### ⚽ {row['Матч']}")
            st.caption(
                f"🕒 Начало: {row['Начало']} | 📌 Букмекер: {row['Букмекер']}"
            )

          with col_metrics:
            st.markdown(f"**Рекомендация:** {row['Команда / Исход']}")
            m1, m2 = st.columns(2)
            m1.metric("Коэффициент", row["Коэффициент"])
            m2.metric("EV (Ожидание)", f"+{row['EV (%)']}%")

          with col_action:
            st.write("")
            st.markdown(f"**💰 Ставка по Келли:**")
            st.success(f"**{row['Реком. ставка']} у.е.**")
            st.caption(
                f"Модель: {row['Оценка модели (%)']}% | Рынок:"
                f" {row['Истинная вер. (%)']}%"
            )
    else:
      st.warning(
          "⚠️ Список пуст. Нажмите **'🚀 Запустить сканирование линий'** в"
          " левой панели."
      )

  # --- Вкладка 2: Большая таблица ---
  with tab2:
    st.subheader("📊 Все найденные валуи в виде таблицы")
    if "value_df" in st.session_state and not st.session_state[
        "value_df"
    ].empty:
      st.dataframe(
          st.session_state["value_df"], use_container_width=True, height=600
      )
    else:
      st.info("Данные отсутствуют. Запустите сканирование.")

  # --- Вкладка 3: Архив ---
  with tab3:
    st.subheader("🗄️ База данных архива сканирований")
    df_arch = load_archive()
    if not df_arch.empty:
      st.metric("Записей в архиве", len(df_arch))
      st.dataframe(df_arch, use_container_width=True, height=500)
      if st.button("🗑️ Очистить архив"):
        if os.path.exists(ARCHIVE_FILE):
          os.remove(ARCHIVE_FILE)
          st.success("Архив успешно очищен!")
          st.rerun()
    else:
      st.info("Архив пуст.")


if __name__ == "__main__":
  main()
