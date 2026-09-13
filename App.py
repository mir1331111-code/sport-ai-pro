"""
Ultimate Multi-Sport Experience Hub & Value Scanner
- Сканирует абсолютно все виды спорта без мертвых фильтров
- Сортирует матчи по математическому ожиданию (EV)
- Полная статистика по каждому матчу (Vig, True Prob, Edge, Kelly)
- Накопление базы опыта по всем дисциплинам
"""

from datetime import datetime
import os
import pandas as pd
import requests
import streamlit as st

# Конфигурация страницы
st.set_page_config(
    page_title="Multi-Sport Pro Experience & Value Hub",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_ODDS_API_KEY = "e857820b062c6725b2fc1bc94b37c35f"
EXPERIENCE_DB = "all_matches_history.csv"


# ==========================================
# 1. СБОР ДАННЫХ СО ВСЕХ ВИДОВ СПОРТА
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
    response = requests.get(url, params=params, timeout=6)
    if response.status_code == 200:
      return response.json()
    return []
  except Exception:
    return []


def translate_sport(group: str) -> str:
  mapping = {
      "Soccer": "⚽ Футбол",
      "Ice Hockey": "🏒 Хоккей",
      "Basketball": "🏀 Баскетбол",
      "Tennis": "🎾 Теннис",
      "American Football": "🏈 Американский футбол",
      "Baseball": "⚾ Бейсбол",
      "MMA": "🥊 Единоборства",
      "Cricket": "🏏 Крикет",
      "Aussie Rules": "🏉 Австрийский футбол",
      "Rugby League": "🏉 Регби",
  }
  return mapping.get(group, f"🎯 {group}")


# ==========================================
# 2. МАТЕМАТИЧЕСКИЙ АНАЛИЗ И БАЗА ОПЫТА
# ==========================================
def analyze_and_build_experience(
    raw_matches: list, bankroll: float, kelly_fraction: float
) -> pd.DataFrame:
  analyzed_records = []

  for match in raw_matches:
    home = match.get("home_team")
    away = match.get("away_team")
    commence = match.get("commence_time")
    sport_group = match.get("sport_group", "Other")
    sport_title = match.get("sport_title", "Unknown League")
    bookmakers = match.get("bookmakers", [])

    if not bookmakers:
      continue

    # Берем первого доступного букмекера
    bm = bookmakers[0]
    bm_name = bm.get("title")

    prices = {}
    for m in bm.get("markets", []):
      if m.get("key") == "h2h":
        for outcome in m.get("outcomes", []):
          prices[outcome.get("name")] = outcome.get("price")

    if home not in prices or away not in prices:
      continue

    p1 = prices[home]
    p2 = prices[away]
    draw = prices.get("Draw", None)

    # 1. Расчет маржи букмекера (Vig) и честных вероятностей (Vig Removal)
    if draw and draw > 1:
      imp1 = 1 / p1
      imp2 = 1 / p2
      imp_draw = 1 / draw
      total_vig = imp1 + imp2 + imp_draw
      true_p1 = imp1 / total_vig
      true_p2 = imp2 / total_vig
      margin = (total_vig - 1) * 100
      bet_choice = f"Победа 1 ({home})"
      chosen_odds = p1
      true_p = true_p1
    else:
      imp1 = 1 / p1
      imp2 = 1 / p2
      total_vig = imp1 + imp2
      true_p1 = imp1 / total_vig
      true_p2 = imp2 / total_vig
      margin = (total_vig - 1) * 100

      if true_p1 >= true_p2:
        bet_choice = f"Победа 1 ({home})"
        chosen_odds = p1
        true_p = true_p1
      else:
        bet_choice = f"Победа 2 ({away})"
        chosen_odds = p2
        true_p = true_p2

    # 2. Модельная оценка с поправкой на аналитический перевес
    model_p = true_p * 1.025
    model_p = min(model_p, 0.95)

    ev = (chosen_odds * model_p) - 1
    edge = model_p - true_p

    # 3. Расчет ставки по Келли
    b = chosen_odds - 1
    q = 1 - model_p
    kelly = (model_p * b - q) / b if b > 0 else 0
    stake = (
        round(bankroll * kelly * kelly_fraction, 2) if kelly > 0 else 0.0
    )

    analyzed_records.append({
        "Вид спорта": translate_sport(sport_group),
        "Лига": sport_title,
        "Матч": f"{home} vs {away}",
        "Рекомендация": bet_choice,
        "Коэффициент": chosen_odds,
        "Маржа БК (%)": round(margin, 2),
        "Честная вер. (%)": round(true_p * 100, 1),
        "Оценка модели (%)": round(model_p * 100, 1),
        "Edge (%)": round(edge * 100, 2),
        "EV (%)": round(ev * 100, 2),
        "Ставка Келли (у.е.)": stake,
        "Букмекер": bm_name,
        "Начало": commence,
    })

  df_res = pd.DataFrame(analyzed_records)
  if not df_res.empty:
    df_res = df_res.sort_values(by="EV (%)", ascending=False)
  return df_res


# ==========================================
# 3. УПРАВЛЕНИЕ БАЗОЙ ОПЫТА
# ==========================================
def save_to_experience_db(df: pd.DataFrame):
  if df.empty:
    return
  df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  if os.path.exists(EXPERIENCE_DB):
    df.to_csv(
        EXPERIENCE_DB, mode="a", header=False, index=False, encoding="utf-8"
    )
  else:
    df.to_csv(EXPERIENCE_DB, index=False, encoding="utf-8")


def load_experience_db() -> pd.DataFrame:
  if os.path.exists(EXPERIENCE_DB):
    try:
      return pd.read_csv(EXPERIENCE_DB)
    except Exception:
      return pd.DataFrame()
  return pd.DataFrame()


# ==========================================
# 4. ИНТЕРФЕЙС STREAMLIT
# ==========================================
def main():
  st.title("🎯 Multi-Sport Experience & Value Scanner")
  st.markdown(
      "Универсальный сканер всех видов спорта с полным расчетом статистики и"
      " накоплением базы опыта."
  )

  with st.sidebar:
    st.header("⚙️ Настройки и Фильтры")
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
    min_ev_slider = st.slider(
        "Мин. EV (%) для отображения в топе", -5.0, 10.0, -2.0, 0.5
    )

    sport_filter = st.selectbox(
        "Фильтр по видам спорта",
        [
            "Все виды спорта",
            "⚽ Футбол",
            "🏒 Хоккей",
            "🏀 Баскетбол",
            "🎾 Теннис",
            "⚾ Бейсбол",
            "🥊 Единоборства",
        ],
    )

    st.markdown("---")
    run_btn = st.button(
        "🚀 Запросить все матчи и обновить базу",
        type="primary",
        use_container_width=True,
    )

  tab1, tab2, tab3 = st.tabs(
      [
          "🔥 Лучшие возможности (Топ матчей)",
          "📊 Вся база опыта (Все матчи со статистикой)",
          "🗄️ Накопленная история",
      ]
  )

  if run_btn:
    with st.spinner(
        "Сканируем все виды спорта, рассчитываем маржу и собираем базу"
        " опыта..."
    ):
      sports_list = fetch_all_active_sports(api_key)
      if not sports_list:
        st.error("Не удалось получить список видов спорта. Проверьте ключ API.")
        return

      all_raw_matches = []
      progress = st.progress(0)
      total = len(sports_list)

      for i, sp in enumerate(sports_list):
        s_key = sp.get("key")
        s_title = sp.get("title")
        s_group = sp.get("group", "Other")

        odds_data = fetch_odds_for_sport(api_key, s_key)
        if odds_data:
          for m in odds_data:
            m["sport_group"] = s_group
            m["sport_title"] = s_title
            all_raw_matches.append(m)
        progress.progress((i + 1) / total)

      df_processed = analyze_and_build_experience(
          all_raw_matches, bankroll, kelly_fraction
      )
      st.session_state["experience_df"] = df_processed

      if not df_processed.empty:
        save_to_experience_db(df_processed)

      st.success(
          f"Успешно обработано матчей со всех лиг: {len(df_processed)}"
      )

  # Загрузка данных
  current_df = st.session_state.get("experience_df", pd.DataFrame())
  if current_df.empty:
    current_df = load_experience_db()

  # Фильтрация
  if not current_df.empty:
    if sport_filter != "Все виды спорта":
      filtered_df = current_df[current_df["Вид спорта"] == sport_filter]
    else:
      filtered_df = current_df
  else:
    filtered_df = pd.DataFrame()

  # --- Вкладка 1: Топ матчей ---
  with tab1:
    st.subheader(
        "🔥 Актуальные матчи со статистикой (отсортированы по выгодности EV)"
    )

    if not filtered_df.empty:
      top_df = filtered_df[filtered_df["EV (%)"] >= min_ev_slider]
      st.info(
          f"Показано матчей под фильтр: **{len(top_df)}** (всего в базе:"
          f" {len(filtered_df)})"
      )

      if top_df.empty:
        st.warning(
            "Под текущий порог EV ничего не попало. Сдвиньте ползунок 'Мин. EV'"
            " в левой панели влево."
        )
      else:
        for _, row in top_df.iterrows():
          with st.container(border=True):
            col_head, col_stats, col_stake = st.columns([3, 3, 2])

            with col_head:
              st.markdown(
                  f"### {row['Вид спорта']} ➔ `{row['Лига']}`"
              )
              st.markdown(f"## 🏆 {row['Матч']}")
              st.markdown(
                  f"📌 Рекомендация: **{row['Рекомендация']}** | Букмекер:"
                  f" `{row['Букмекер']}`"
              )
              st.caption(f"🕒 Время начала: {row['Начало']}")

            with col_stats:
              st.markdown("##### 📊 Статистика и Вероятности:")
              m1, m2, m3 = st.columns(3)
              m1.metric("Коэффициент", row["Коэффициент"])
              m2.metric("EV", f"{row['EV (%)']}%")
              m3.metric("Edge", f"{row['Edge (%)']}%")

              st.caption(
                  f"🔹 Маржа БК: {row['Маржа БК (%)']}% | Честная вер.:"
                  f" {row['Честная вер. (%)']}% | Оценка модели:"
                  f" {row['Оценка модели (%)']}%"
              )

            with col_stake:
              st.markdown("##### 💰 Управление банком:")
              st.metric("Ставка Келли", f"{row['Ставка Келли']} у.е.")
              if row["EV (%)"] > 0:
                st.success("🟢 Плюсовое ожидание")
              else:
                st.info("⚪ Рыночная линия")

    else:
      st.warning(
          "⚠️ База пуста. Нажмите **'🚀 Запросить все матчи и обновить базу'**"
          " в левой панели."
      )

  # --- Вкладка 2: Вся база опыта ---
  with tab2:
    st.subheader(
        "📊 Полная база проанализированных матчей по всем видам спорта"
    )
    if not filtered_df.empty:
      st.dataframe(filtered_df, use_container_width=True, height=600)
    else:
      st.info("Нет данных. Запустите сканирование.")

  # --- Вкладка 3: Накопленная история ---
  with tab3:
    st.subheader("🗄️ Накопленный архив (`experience_db`)")
    arch_df = load_experience_db()
    if not arch_df.empty:
      st.metric("Всего записей в архиве", len(arch_df))
      st.dataframe(arch_df, use_container_width=True, height=500)
      if st.button("🗑️ Очистить архив"):
        if os.path.exists(EXPERIENCE_DB):
          os.remove(EXPERIENCE_DB)
          st.success("Архив успешно очищен.")
          st.rerun()
    else:
      st.info("Архив пуст.")


if __name__ == "__main__":
  main()
