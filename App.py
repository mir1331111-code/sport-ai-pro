import datetime
from duckduckgo_search import DDGS
from google import genai
import streamlit as st

st.set_page_config(
    title="Auto-Sniper: Точный авто-поиск", page_icon="🤖", layout="centered"
)

st.markdown(
    """
<h1 style='text-align: center;'>🤖 Auto-Sniper: Точный авто-поиск матчей</h1>
<p style='text-align: center; color: gray;'>Многоуровневый сканер интернета для поиска реальных матчей на сегодня.</p>
""",
    unsafe_allow_html=True,
)

if "history" not in st.session_state:
  st.session_state.history = []

st.sidebar.header("⚙️ Настройки и Статистика")
api_key = st.sidebar.text_input("Ключ Gemini API", type="password")

total_finished = 0
total_wins = 0
total_losses = 0

for item in st.session_state.history:
  if item["status"] == "✅ Проход":
    total_wins += 1
    total_finished += 1
  elif item["status"] == "❌ Проигрыш":
    total_losses += 1
    total_finished += 1

win_rate = (total_wins / total_finished * 100) if total_finished > 0 else 0

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Ваша статистика")
st.sidebar.write(f"🟢 Побед: **{total_wins}**")
st.sidebar.write(f"🔴 Поражений: **{total_losses}**")
st.sidebar.metric(
    label="Проходимость (Win Rate)",
    value=f"{win_rate:.1f}%" if total_finished > 0 else "0.0%",
)

today_date = datetime.date.today().strftime("%d.%m.%Y")
current_time = datetime.datetime.now().strftime("%H:%M")

st.subheader(f"⏱ Текущее время: {current_time} МСК ({today_date})")
st.info(
    "Нажми кнопку ниже — сканер соберет точное расписание матчей на сегодня"
    " без путаницы."
)

num_signals = st.slider("Количество сигналов", 1, 3, 2)

if st.button("🔍 Найти реальные матчи и сделать прогноз", type="primary"):
  if not api_key:
    st.error("⚠️ Введите ключ Gemini API в боковой панели слева!")
  else:
    with st.spinner("Многоуровневый сканирование спортивных баз данных..."):
      try:
        # Делаем несколько точных поисковых запросов параллельно
        queries = [
            f"футбол матчи расписание сегодня 13 сентября 2026",
            f"апл ла лига сериал а бундеслига матчи 13.09.2026",
            f"flashscore футбол матчи на сегодня",
        ]

        search_results = []
        with DDGS() as ddgs:
          for q in queries:
            try:
              results = ddgs.text(q, max_results=3)
              for r in results:
                body = r.get("body", "")
                if body:
                  search_results.append(body)
            except Exception:
              continue

        search_context = "\n".join(search_results)
        if len(search_context) < 50:
          search_context = (
              "Топ матчи европейских чемпионатов (АПЛ, Ла Лига, Серия А)"
              " воскресенье 13 сентября 2026"
          )

        # Отправляем очищенные данные в Gemini с жестким требованием
        client = genai.Client(api_key=api_key)

        prompt = (
            f"Сегодня воскресенье, {today_date}, текущее время {current_time} МСК."
            " Вот данные, найденные в сети по сегодняшним матчам:\n"
            f"{search_context}\n\n"
            "Ты профессиональный спортивный аналитик и скаут. "
            f"Выбери ровно {num_signals} реальных, существующих матча топ-уровня,"
            " которые играются сегодня. Запрещено выдумывать команды или"
            " матчи-пустышки. Используй только реальные пары соперников."
            " Для каждого сигнала укажи строго по пунктам: "
            "- ⏱ Время начала матча (по МСК). "
            "- 🌐 Турнир / Лига (например: АПЛ, Ла Лига и т.д.). "
            "- ⚠️ Уровень риска (🟢 Ультра-надежный или 🟡 Стандартный). "
            "- 🏆 Событие (Реальные команды: Команда 1 - Команда 2). "
            "- 🎯 Сигнал для ставки (Конкретный исход и примерный коэффициент)."
            " "
            "- 📈 Вероятность прохода (в %). "
            "- 💡 Обоснование прогноза на основе текущей формы команд."
        )

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        new_signal = {
            "date": f"{today_date} в {current_time}",
            "content": response.text,
            "status": "⌛ Ожидание",
        }
        st.session_state.history.insert(0, new_signal)
        st.success("Актуальные матчи успешно сформированы!")

      except Exception as e:
        st.error(f"Ошибка при обработке: {e}")

st.markdown("---")
st.subheader("📊 Трекер исходов и история сигналов")

if not st.session_state.history:
  st.info("История пуста. Запусти поиск выше.")
else:
  if st.button("🗑 Очистить всю историю"):
    st.session_state.history = []
    st.rerun()

  for idx, item in enumerate(st.session_state.history):
    status = item["status"]

    if status == "✅ Проход":
      bg_color, border_color, text_color = "#d4edda", "#28a745", "#155724"
    elif status == "❌ Проигрыш":
      bg_color, border_color, text_color = "#f8d7da", "#dc3545", "#721c24"
    else:
      bg_color, border_color, text_color = "#fff3cd", "#ffc107", "#856404"

    signal_num = len(st.session_state.history) - idx

    st.markdown(
        f"""
        <div style="background-color: {bg_color}; border-left: 6px solid"
        f" {border_color}; padding: 12px; border-radius: 6px; margin-top: 15px;"
        f" margin-bottom: 5px; color: {text_color};">
            <b>Сигнал #{signal_num}</b> (Запрошен: {item['date']})"
        f" &nbsp;|&nbsp; Статус: <b>{status}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"📄 Показать аналитику и прогноз #{signal_num}"):
      st.write(item["content"])

    col1, col2, col3 = st.columns(3)
    if col1.button("🟢 Проход", key=f"win_{idx}"):
      st.session_state.history[idx]["status"] = "✅ Проход"
      st.rerun()
    if col2.button("🔴 Проигрыш", key=f"loss_{idx}"):
      st.session_state.history[idx]["status"] = "❌ Проигрыш"
      st.rerun()
    if col3.button("⏳ Ожидание", key=f"pend_{idx}"):
      st.session_state.history[idx]["status"] = "⌛ Ожидание"
      st.rerun()

    st.markdown("---")
