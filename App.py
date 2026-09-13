import datetime
import json
import os
import time
from google import genai
import streamlit as st

# Файл для постоянного хранения истории
HISTORY_FILE = "match_history.json"


def load_history():
  if os.path.exists(HISTORY_FILE):
    try:
      with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      return []
  return []


def save_history(history_data):
  try:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
      json.dump(history_data, f, ensure_ascii=False, indent=4)
  except Exception:
    pass


st.set_page_config(
    page_title="Match-Analyst: Анализ матча", page_icon="⚽", layout="centered"
)

st.markdown(
    """
<h1 style='text-align: center;'>⚽ Match-Analyst: Профессиональный разбор</h1>
<p style='text-align: center; color: gray;'>Введите матч в боковой панели слева — ИИ выдаст глубокую аналитику. Данные сохраняются навсегда!</p>
""",
    unsafe_allow_html=True,
)

if "history" not in st.session_state:
  st.session_state.history = load_history()

# --- БОКОВАЯ ПАНЕЛЬ (Настройки, ввод матча и статистика) ---
st.sidebar.header("⚙️ Настройки и Ввод")
api_key = st.sidebar.text_input("Ключ Gemini API", type="password")

st.sidebar.markdown("---")
st.sidebar.subheader("📝 Новый матч")
user_match = st.sidebar.text_input(
    "Команды / Событие:",
    placeholder="например: Арсенал - Челси",
    key="sidebar_match_input",
)

today_date = datetime.date.today().strftime("%d.%m.%Y")
current_time = datetime.datetime.now().strftime("%H:%M")

if st.sidebar.button("📊 Сделать анализ матча", type="primary"):
  if not api_key:
    st.sidebar.error("⚠️ Введите ключ Gemini API!")
  elif not user_match.strip():
    st.sidebar.error("⚠️ Введите название матча!")
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
            "id": str(time.time()),
            "match": user_match,
            "date": f"{today_date} в {current_time}",
            "content": response.text,
            "status": "⌛ Ожидание",
        }
        st.session_state.history.insert(0, new_signal)
        save_history(st.session_state.history)  # Сохраняем на диск навека
        st.sidebar.success("Анализ готов и сохранен!")

      except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "ResourceExhausted" in error_msg:
          st.sidebar.error(
              "⚠️ Исчерпан суточный лимит бесплатных запросов Gemini."
          )
        else:
          st.sidebar.error(f"Ошибка: {error_msg}")

# Подсчет статистики для боковой панели
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


# --- ГЛАВНЫЙ ЭКРАН (Только история, трекер и результаты) ---
st.subheader("📊 Трекер исходов и история прогнозов")

if not st.session_state.history:
  st.info(
      "История пуста. Введите название матча в боковой панели слева и нажмите"
      " кнопку анализа."
  )
else:
  if st.button("🗑 Очистить всю историю"):
    st.session_state.history = []
    save_history(st.session_state.history)  # Очищаем файл на диске
    st.rerun()

  for idx, item in enumerate(st.session_state.history):
    item_id = item.get("id", str(idx))
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
    if col1.button("🟢 Проход", key=f"win_{item_id}"):
      item["status"] = "✅ Проход"
      save_history(st.session_state.history)  # Обновляем статус в файле
      st.rerun()
    if col2.button("🔴 Проигрыш", key=f"loss_{item_id}"):
      item["status"] = "❌ Проигрыш"
      save_history(st.session_state.history)  # Обновляем статус в файле
      st.rerun()
    if col3.button("⏳ Ожидание", key=f"pend_{item_id}"):
      item["status"] = "⌛ Ожидание"
      save_history(st.session_state.history)  # Обновляем статус в файле
      st.rerun()

    st.markdown("---")
