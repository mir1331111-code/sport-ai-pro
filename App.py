import datetime
import json
import os
import time
from google import genai
import streamlit as st

# Файл для постоянного хранения истории навека
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
<p style='text-align: center; color: gray;'>Введите матч по центру, а история и результаты аккуратно собраны в боковой панели слева.</p>
""",
    unsafe_allow_html=True,
)

if "history" not in st.session_state:
  st.session_state.history = load_history()

# --- БОКОВАЯ ПАНЕЛЬ (История, статистика и трекер) ---
st.sidebar.header("⚙️ Настройки и История")
api_key = st.sidebar.text_input("Ключ Gemini API", type="password")

# Подсчет статистики
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
st.sidebar.subheader("📊 Статистика")
st.sidebar.write(f"🟢 Побед: **{total_wins}**")
st.sidebar.write(f"🔴 Поражений: **{total_losses}**")
st.sidebar.metric(
    label="Проходимость (Win Rate)",
    value=f"{win_rate:.1f}%" if total_finished > 0 else "0.0%",
)

st.sidebar.markdown("---")
st.sidebar.subheader("📂 Архив прогнозов")

if not st.session_state.history:
  st.sidebar.info("История пуста.")
else:
  if st.sidebar.button("🗑 Очистить всю историю"):
    st.session_state.history = []
    save_history(st.session_state.history)
    st.rerun()

  for idx, item in enumerate(st.session_state.history):
    item_id = item.get("id", str(idx))
    status = item["status"]

    if status == "✅ Проход":
      badge = "🟢"
    elif status == "❌ Проигрыш":
      badge = "🔴"
    else:
      badge = "⏳"

    signal_num = len(st.session_state.history) - idx
    match_title = item.get("match", f"Матч #{signal_num}")

    with st.sidebar.expander(f"{badge} #{signal_num} | {match_title}"):
      st.write(f"**Дата:** {item['date']}")
      st.write(f"**Статус:** {status}")
      st.markdown("---")
      st.write(item["content"])

      col1, col2, col3 = st.columns(3)
      if col1.button("🟢", key=f"win_{item_id}", help="Проход"):
        item["status"] = "✅ Проход"
        save_history(st.session_state.history)
        st.rerun()
      if col2.button("🔴", key=f"loss_{item_id}", help="Проигрыш"):
        item["status"] = "❌ Проигрыш"
        save_history(st.session_state.history)
        st.rerun()
      if col3.button("⏳", key=f"pend_{item_id}", help="Ожидание"):
        item["status"] = "⌛ Ожидание"
        save_history(st.session_state.history)
        st.rerun()


# --- ГЛАВНЫЙ ЭКРАН (Ввод матча и генерация анализа) ---
st.subheader("📝 Введите матч для детального анализа")
user_match = st.text_input(
    "Команды / Событие:",
    placeholder="например: Арсенал - Челси или Спартак - Зенит",
)

today_date = datetime.date.today().strftime("%d.%m.%Y")
current_time = datetime.datetime.now().strftime("%H:%M")

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
            "id": str(time.time()),
            "match": user_match,
            "date": f"{today_date} в {current_time}",
            "content": response.text,
            "status": "⌛ Ожидание",
        }
        st.session_state.history.insert(0, new_signal)
        save_history(st.session_state.history)  # Сохраняем на диск навека
        st.success("Анализ готов и успешно добавлен в историю слева!")

      except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "ResourceExhausted" in error_msg:
          st.error(
              "⚠️ Исчерпан суточный лимит бесплатных запросов для ключа"
              " Gemini. Подождите немного."
          )
        else:
          st.error(f"Ошибка при обработке запроса: {error_msg}")

# Отображение последнего свежего разбора по центру
if st.session_state.history:
  st.markdown("---")
  st.subheader("🔥 Последний результат анализа")
  latest = st.session_state.history[0]
  st.info(f"Матч: **{latest['match']}** | Статус: **{latest['status']}**")
  st.write(latest["content"])
  
