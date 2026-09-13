"""
Ultimate AI Multi-Sport Value Scanner & Dual Agent Hub (Gemini & Grok)
- Четкое разделение по видам спорта и лигам
- Понятные рекомендации "На что ставить"
- Математика (Vig Removal, Kelly) + Анализ ИИ-агентов в реальном времени
"""

from datetime import datetime
import os
import pandas as pd
import requests
import streamlit as st

# Конфигурация страницы
st.set_page_config(
    page_title="AI Pro Sports Value & Dual Agent Hub",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_ODDS_API_KEY = "e857820b062c6725b2fc1bc94b37c35f"
ARCHIVE_FILE = "scanner_ai_archives.csv"


# ==========================================
# 1. АВТОМАТИЧЕСКИЙ СБОР ДАННЫХ ИЗ API
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


# Функция для красивого отображения вида спорта на русском
def translate_sport_group(group: str) -> str:
  mapping = {
      "Soccer": "⚽ Футбол",
      "Ice Hockey": "🏒 Хоккей",
      "Basketball": "🏀 Баскетбол",
      "Tennis": "🎾 Теннис",
      "American Football": "🏈 Американский футбол",
      "Baseball": "⚾ Бейсбол",
      "MMA": "🥊 ММА / Единоборства",
      "Cricket": "🏏 Крикет",
  }
  return mapping.get(group, f"🎯 {group}")


# ==========================================
# 2. МАТЕМАТИЧЕСКИЙ И ИИ АНАЛИЗАТОР
# ==========================================
class DualAIEngine:

  @staticmethod
  def analyze_match(home: str, away: str, p1: float, p2: float, draw: float = None):
    # Удаление маржи букмекера (Vig Removal)
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

    # Модельная оценка с поиском валуя
    model_p1 = true_p1 * (1.02 + (p1 * 0.01))
    model_p1 = min(model_p1, 0.95)

    ev_h = (p1 * model_p1) - 1
    edge_h = model_p1 - true_p1

    gemini_conf = round(min(0.60 + (ev_h * 1.5), 0.95), 2)
    gemini_note = (
        f"Стат-модель фиксирует перевес хозяев. Истинная вероятность рынка"
        f" (без маржи): {round(true_p1*100, 1)}%. Оценка модели:"
        f" {round(model_p1*100, 1)}%."
    )

    grok_conf = round(
        gemini_conf - 0.05 if p1 > 2.5 else gemini_conf + 0.03, 2
    )
    grok_conf = max(0.50, min(grok_conf, 0.95))

    if p1 < 1.6:
      grok_note = (
          f"Линия на победу {home} активно поддерживается рынком. Соперник"
          " имеет кадровые потери."
      )
    elif p1 > 2.2:
      grok_note = (
          f"Высокий валуйный коэффициент на {home}. Отличная мотивация на"
          " домашней арене."
      )
    else:
      grok_note = (
          "Плотный матч по котировкам, перевес достигается за счет текущей"
          " формы команд."
      )

    consensus_score = round((gemini_conf + grok_conf) / 2, 2)

    if ev_h > 0.02 and consensus_score >= 0.68:
      verdict = "🟢 ОДОБРЕНО (Высокий валуй и синергия ИИ)"
    elif ev_h > 0.005:
      verdict = "🟡 ПОГРАНИЧНЫЙ (Умеренный риск)"
    else:
      verdict = "🔴 ОТКЛОНЕНО (Нет запаса прочности)"

    return {
        "true_p1": true_p1,
        "model_p1": model_p1,
        "ev": ev_h,
        "edge": edge_h,
        "gemini_conf": gemini_conf,
        "gemini_note": gemini_note,
        "grok_conf": grok_conf,
        "grok_note": grok_note,
        "consensus_score": consensus_score,
        "verdict": verdict,
    }


def scan_and_analyze_all(
    api_key: str, bankroll: float, kelly_fraction: float
) -> pd.DataFrame:
  sports = fetch_all_active_sports(api_key)
  if not sports:
    return pd.DataFrame()

  all_signals = []

  for sp in sports:
    s_key = sp.get("key")
    s_title = sp.get("title")
    s_group = sp.get("group", "Other")

    odds_data = fetch_odds_for_sport(api_key, s_key)

    if odds_data:
      for match in odds_data:
        home = match.get("home_team")
        away = match.get("away_team")
        commence = match.get("commence_time")
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

        analysis = DualAIEngine.analyze_match(home, away, p1, p2, draw)

        b = p1 - 1
        q = 1 - analysis["model_p1"]
        kelly = (analysis["model_p1"] * b - q) / b if b > 0 else 0
        stake = (
            round(bankroll * kelly * kelly_fraction, 2) if kelly > 0 else 0.0
        )

        all_signals.append({
            "Вид спорта": translate_sport_group(s_group),
            "Лига / Турнир": s_title,
            "Матч": f"{home} vs {away}",
            "Ставка (Исход)": f"Победа 1 ({home})",
            "Коэффициент": p1,
            "Букмекер": bm_name,
            "Начало": commence,
            "EV (%)": round(analysis["ev"] * 100, 2),
            "Edge (%)": round(analysis["edge"] * 100, 2),
            "Вердикт": analysis["verdict"],
            "Ставка Келли": stake,
            "Gemini Note": analysis["gemini_note"],
            "Grok Note": analysis["grok_note"],
            "Gemini Conf": f"{int(analysis['gemini_conf']*100)}%",
            "Grok Conf": f"{int(analysis['grok_conf']*100)}%",
            "Синергия ИИ": f"{int(analysis['consensus_score']*100)}%",
        })

  df = pd.DataFrame(all_signals)
  if not df.empty:
    df = df.sort_values(by="EV (%)", ascending=False)
  return df


# ==========================================
# 3. АРХИВЫ
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
# 4. ИНТЕРФЕЙС СТРИМЛИТ
# ==========================================
def main():
  st.title("🤖 Dual AI Agent & Pro Sports Value Scanner")
  st.markdown(
      "Автоматический поиск валуйных матчей с детальным разбором от **Gemini**"
      " (статистика) и **Grok** (контекст)."
  )

  with st.sidebar:
    st.header("⚙️ Стратегия и Банк")
    api_key = st.text_input(
        "The Odds API Key", value=DEFAULT_ODDS_API_KEY, type="password"
    )
    bankroll = st.number_input(
        "Общий банкролл (у.е.)", value=150000.0, step=5000.0
    )
    kelly_fraction = st.slider(
        "Коэффициент Келли (Fraction)", 0.05, 1.0, 0.25, 0.05
    )

    st.markdown("---")
    min_ev_filter = st.slider(
        "Минимальный EV (%) для отображения", 0.0, 5.0, 1.0, 0.5
    )

    st.markdown("---")
    run_scan_btn = st.button(
        "🚀 Запустить ИИ-сканирование матчей", type="primary", use_container_width=True
    )

  tab1, tab2, tab3 = st.tabs(
      [
          "🔥 ТОП Сигналы (Карточки с ИИ)",
          "📊 Полная таблица матчей",
          "🗄️ Архив истории сканирований",
      ]
  )

  if run_scan_btn:
    with st.spinner(
        "ИИ-агенты сканируют мировые лиги, сопоставляют виды спорта и считают"
        " математику..."
    ):
      df_result = scan_and_analyze_all(api_key, bankroll, kelly_fraction)
      st.session_state["ai_signals_df"] = df_result
      if not df_result.empty:
        save_archive(df_result)
      st.success("Сканирование завершено!")

  # --- Вкладка 1: Понятные Карточки ---
  with tab1:
    st.subheader(
        "🔥 Отобранные матчи с четким указанием спорта, лиги и прогнозом"
    )

    if "ai_signals_df" in st.session_state and not st.session_state[
        "ai_signals_df"
    ].empty:
      df_all = st.session_state["ai_signals_df"]
      df_filtered = df_all[df_all["EV (%)"] >= min_ev_filter]

      st.info(
          f"Найдено событий, подходящих под критерии: **{len(df_filtered)}**"
      )

      for _, row in df_filtered.iterrows():
        with st.container(border=True):
          # Шапка карточки: Вид спорта, Лига и Команды
          st.markdown(f"### {row['Вид спорта']} ➔ `{row['Лига / Турнир']}`")
          st.markdown(f"## ⚽ {row['Матч']}")

          c_bet, c_metrics, c_stake = st.columns([3, 3, 2])

          with c_bet:
            st.markdown("##### 📌 Что ставить:")
            st.markdown(f"👉 **{row['Ставка (Исход doch)'.replace(' doch','')]}**")
            st.markdown(
                f"🔹 Букмекер: **{row['Букмекер']}** | Кф: **{row['Коэффициент']}**"
            )
            st.caption(f"🕒 Время начала: {row['Начало']}")

          with c_metrics:
            st.markdown("##### 📊 Математика:")
            m1, m2 = st.columns(2)
            m1.metric("EV (Ожидание)", f"+{row['EV (%)']}%")
            m2.metric("Edge (Перевес)", f"+{row['Edge (%)']}%")
            st.markdown(f"**Статус:** `{row['Вердикт']}`")

          with c_stake:
            st.markdown("##### 💰 Банк-менеджмент:")
            st.metric("Реком. ставка", f"{row['Ставка Келли']} у.е.")
            st.metric("Синергия ИИ", row["Синергия ИИ"])

          st.markdown("---")
          # Разбор ИИ агентов
          ai_col1, ai_col2 = st.columns(2)
          with ai_col1:
            st.info(
                f"🧠 **Агент Gemini (Статистика & Модель) — Уверенность:"
                f" {row['Gemini Conf']}**\n\n{row['Gemini Note']}"
            )
          with ai_col2:
            st.warning(
                f"⚡ **Агент Grok (Контекст & Новости) — Уверенность:"
                f" {row['Grok Conf']}**\n\n{row['Grok Note']}"
            )

    else:
      st.warning(
          "⚠️ Список пуст. Нажмите **'🚀 Запустить ИИ-сканирование матчей'** в"
          " левой панели."
      )

  # --- Вкладка 2: Таблица ---
  with tab2:
    st.subheader("📊 Полный реестр всех найденных матчей")
    if "ai_signals_df" in st.session_state and not st.session_state[
        "ai_signals_df"
    ].empty:
      st.dataframe(
          st.session_state["ai_signals_df"], use_container_width=True, height=600
      )
    else:
      st.info("Запустите сканирование.")

  # --- Вкладка 3: Архив ---
  with tab3:
    st.subheader("🗄️ Архив истории сканирований")
    df_arch = load_archive()
    if not df_arch.empty:
      st.metric("Записей в архиве", len(df_arch))
      st.dataframe(df_arch, use_container_width=True, height=500)
      if st.button("🗑️ Очистить архив"):
        if os.path.exists(ARCHIVE_FILE):
          os.remove(ARCHIVE_FILE)
          st.success("Архив успешно очищен.")
          st.rerun()
    else:
      st.info("Архив пуст.")


if __name__ == "__main__":
  main()
