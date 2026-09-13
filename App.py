import datetime
from google import genai
import streamlit as st

st.set_page_config(
    page_title="Match-Analyst: Анализ матча", page_icon="⚽", layout="centered"
)

st.markdown(
    """
<h1 style='text-align: center;'>⚽ Match-Analyst: Профессиональный разбор</h1>
<p style='text-align: center; color: gray;'>Введите интересующий матч вручную — ИИ выдаст глубокую аналитику и прогноз.</p>
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

st.subheader("📝 Введите матч для детального анализа")
user_match = st.text_input(
    "Команды / Событие:",
    placeholder="например: Арсенал - Челси или Спартак - Зенит",
)

if st.button("📊 Сделать глубокий анализ матча", type="primary"):
  if not api_key:
    st.error("⚠️ Введите ключ Gemini API в боковой панели слева!")
  elif not user_match.strip():
    st.error("⚠️ Пожалуйста, введите название матча!")
  else:
    with st.spinner("Анализируем статистику и форму команд..."):
      try:
        client = genai.Client(api_key=api_key)

        prompt = (
            f"Сегодня {today_date}. Пользователь запросил детальный спортивный"
            f" анализ и прогноз на матч: {user_match}.\n\n"
            "Ты профессиональный спортивный аналитик, скаут и каппер. "
            "Сделай глубокий профессиональный разбор этого конкретного матча. "
            "Для анализа укажи строго по пунктам: "
            "- 🌐 Турнир / Лига. "
            "- ⚠️ Уровень риска (🟢 Ультра-надежный, 🟡 Стандартный или 🟠 Рискованный). "
            f"- 🏆 Событие: {user_match}. "
            "- 🎯 Сигнал для ставки (Конкретный исход, тотал/фора и примерный коэффициент). "
            "- 📈 Вероятность прохода (в %). "
            "- 💡 Развернутое обоснование прогноза (текущая форма, мотивация, статистика личных встреч, кадровые потери)."
        )

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        new_signal = {
            "match": user_match,
            "date": f"{today_date} в {current_time}",
            "content": response.text,
            "status": "⌛ Ожидание",
        }
        st.session_state.history.insert(0, new_signal)
        st.success("Анализ матча успешно готов!")

      except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "ResourceExhausted" in error_msg:
          st.error(
              "⚠️ Исчерпан суточный лимит бесплатных запросов для ключа"
              " Gemini. Подождите немного."
          )
        else:
          st.error(f"Ошибка при обработке запроса: {error_msg}")

st.markdown("---")
st.subheader("📊 Трекер исходов и история прогнозов")

if not st.session_state.history:
  st.info("История пуста. Введите матч выше и запустите анализ.")
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
    match_title = item.get("match", f"Матч #{signal_num}")

    st.markdown(
        f"""
        <div style="background-color: {bg_color}; border-left: 6px solid {border_color}; padding: 12px; border-radius: 6px; margin-top: 15px; margin-bottom: 5px; color: {text_color};">
            <b>#{signal_num} | {match_title}</b> (Запрошен: {item['date']}) &nbsp;|&nbsp; Статус: <b>{status}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"📄 Показать детальный разбор #{signal_num}"):
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
