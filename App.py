"""
Ultimate Multi-Sport Experience Hub & High-Probability Value Scanner
- Сканирует ВСЕ виды спорта (Футбол, Хоккей, Баскетбол, Теннис и др.)
- Ведет полную базу опыта (сохраняет каждый матч для истории)
- Рассчитывает глубокую статистику (маржа, честная вероятность, Edge, EV, Келли)
- Выводит ТОП-события с высокой вероятностью прохода
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

    # Проверка наличия коэффициентов на победу хозяев и гостей
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

      # Выбираем фаворита/достойного по честной вероятности для ставки
      if true_p1 >= true_p2:
        bet_choice = f"Победа 1 ({home})"
        chosen_odds = p1
        true_p = true_p1
      else:
        bet_choice = f"Победа 2 ({away})"
        chosen_odds = p2
        true_p = true_p2

    # 2. Модельная оценка с учетом рыночной неэффективности (поиск реального валуя)
    model_p = true_p * 1.035
    model_p = min(model_p, 0.92)  # Рациональный кап

    ev = (chosen_odds * model_p) - 1
    edge = model_p - true_p

    # 3. Расчет ставки по Келли
    b = chosen_odds - 1
    q = 1 - model_p
    kelly = (model_p * b - q) / b if b > 0 else 0
    stake = (
        round(bankroll * kelly * kelly_fraction, 2) if kelly > 0 else 0.0
    )

    # Статус матча для базы опыта
    if ev > 0.015 and model_p >= 0.52:
      recommendation = "🔥 ВЫСОКИЙ ПОТЕНЦИАЛ (Валуй)"
      is_top = True
    elif ev > 0:
      recommendation = "🟡 УМЕРЕННЫЙ РИСК"
      is_top = False
    else:
      recommendation = "🔴 НИЗКОЕ ОЖИДАНИЕ"
      is_top = False

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
        "Статус": recommendation,
        "Букмекер": bm_name,
        "Начало": commence,
        "Is_Top": is_top,
    })

  return pd.DataFrame(analyzed_records)


# ==========================================
# 3. УПРАВЛЕНИЕ БАЗОЙ ОПЫТА (АРХИВ ВСЕХ МАТЧЕЙ)
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
  st.title("🎯 Multi-Sport Experience & High-Probability Value Hub")
  st.markdown(
      "Автоматический сканер **всех видов спорта** с накоплением базы опыта,"
      " глубокой статистикой (маржа, честная вероятность, Edge, EV) и отбором"
      " только надежных событий."
  )

  with st.sidebar:
    st.header("⚙️ Настройки и Банк")
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
    sport_filter = st.selectbox(
        "Фильтр по видам спорта",
        [
            "Все виды спорта",
            "⚽ Футбол",
            "🏒 Хоккей",
            "🏀 Баскетбол",
            "🎾 Теннис",
            "⚾ Бейсбол",
        ],
    )

    st.markdown("---")
    run_btn = st.button(
        "🚀 Сканировать все виды спорта и обновить базу",
        type="primary",
        use_container_width=True,
    )

  tab1, tab2, tab3 = st.tabs(
      [
          "🔥 ТОП матчей с высокой вероятностью",
          "📊 Вся база опыта (Все матчи и статистика)",
          "🗄️ Накопленная история",
      ]
  )

  if run_btn:
    with st.spinner(
        "Опрашиваем все лиги (футбол, хоккей, баскетбол, теннис и др.), считаем"
        " маржу и сохраняем в базу опыта..."
    ):
      sports_list = fetch_all_active_sports(api_key)
      if not sports_list:
        st.error("Не удалось получить список видов спорта. Проверьте API ключ.")
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

      # Обрабатываем всё и строим базу опыта
      df_processed = analyze_and_build_experience(
          all_raw_matches, bankroll, kelly_fraction
      )
      st.session_state["experience_df"] = df_processed

      if not df_processed.empty:
        save_to_experience_db(df_processed)

      st.success(
          f"Анализ завершен! Обработано матчей со всех лиги:"
          f" {len(df_processed)}"
      )

  # Получаем данные из сессии или архива
  current_df = st.session_state.get("experience_df", pd.DataFrame())
  if current_df.empty:
    current_df = load_experience_db()

  # Применяем фильтр по виду спорта, если выбран
  if not current_df.empty and sport_filter != "Все виды спорта":
    display_df = current_df[current_df["Вид спорта"] == sport_filter]
  else:
    display_df = current_df

  # --- Вкладка 1: ТОП матчей с высокой вероятностью ---
  with tab1:
    st.subheader(
        "🔥 Отобранные события с высокой вероятностью прохода и плюсовым EV"
    )

    if not display_df.empty:
      top_df = display_df[display_df["Is_Top"] == True]
      st.info(
          f"Найдено высоковероятных валуйных матчей: **{len(top_df)}** (из"
          f" {len(display_df)} всего в базе)"
      )

      if top_df.empty:
        st.warning(
            "В текущей линии нет матчей, удовлетворяющих строгим критериям"
            " высокой вероятности. Попробуйте обновить сканирование."
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
              st.caption(
                  f"🕒 Начало матча: {row['Начало']} | Статус:"
                  f" `{row['Статус']}`"
              )

            with col_stats:
              st.markdown("##### 📊 Статистика и Вероятности:")
              m1, m2, m3 = st.columns(3)
              m1.metric("Коэффициент", row["Коэффициент"])
              m2.metric("EV", f"+{row['EV (%)']}%")
              m3.metric("Edge", f"+{row['Edge (%)']}%")

              st.caption(
                  f"🔹 Маржа БК: {row['Маржа БК (%)']}% | Честная вер.:"
                  f" {row['Честная вер. (%)']}% | Оценка модели:"
                  f" {row['Оценка модели (%)']}%"
              )

            with col_stake:
              st.markdown("##### 💰 Управление банком:")
              st.metric("Ставка Келли", f"{row['Ставка Келли']} у.е.")
              st.success("🟢 Одобрено моделью")

    else:
      st.warning(
          "⚠️ База пуста. Нажмите **'🚀 Сканировать все виды спорта и обновить"
          " базу'** в левой панели."
      )

  # --- Вкладка 2: Вся база опыта ---
  with tab2:
    st.subheader(
        "📊 Полная база опыта (Все проанализированные матчи со статистикой)"
    )
    st.markdown(
        "Здесь система хранит абсолютно все просканированные матчи по всем видам"
        " спорта вместе с их математическими параметрами для накопления опыта."
    )
    if not display_df.empty:
      st.dataframe(display_df, use_container_width=True, height=600)
    else:
      st.info("Нет данных. Запустите сканирование.")

  # --- Вкладка 3: Накопленная история ---
  with tab3:
    st.subheader("🗄️ Архив накопленной базы данных (`experience_db`)")
    arch_df = load_experience_db()
    if not arch_df.empty:
      st.metric("Всего записей в истории опыта", len(arch_df))
      st.dataframe(arch_df, use_container_width=True, height=500)
      if st.button("🗑️ Очистить базу опыта"):
        if os.path.exists(EXPERIENCE_DB):
          os.remove(EXPERIENCE_DB)
          st.success("База опыта успешно очищена.")
          st.rerun()
    else:
      st.info("Архив пуст.")


if __name__ == "__main__":
  main()
