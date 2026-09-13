import datetime
import json
import os
import time
from duckduckgo_search import DDGS
from groq import Groq
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
    page_title="Auto-Sniper Groq: Авто-поиск матчей",
    page_icon="🤖",
    layout="centered",
)

st.markdown(
    """
<h1 style='text-align: center;'>🤖 Auto-Sniper (Groq AI)</h1>
<p style='text-align: center; color: gray;'>Автоматический поиск реальных матчей в интернете и глубокая аналитика.</p>
""",
    unsafe_allow_html=True,
)

if "history" not in st.session_state:
  st.session_state.history = load_history()

# --- БОКОВАЯ ПАНЕЛЬ (Ключ, Статистика и Архив) ---
st.sidebar.header("⚙️ Настройки и Архив")
groq_api_key = st.sidebar.text_input("Ключ Groq API", type="password")

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
st.sidebar.subheader("📂 История прогнозов")

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
    badge = (
        "🟢"
        if status == "✅ Проход"
        else ("🔴" if status == "❌ Проигрыш" else "⏳")
    )
    signal_num = len(st.session_state.history) - idx
    match_title = item.get("match", f"Сигнал #{signal_num}")

    with st.sidebar.expander(f"{badge} #{signal_num} | {match_title}"):
      st.write(f"**Дата:** {item['date']}")
      st.write(f"**Статус:** {status}")
      st.markdown("---")
      st.write(item["content"])

      col1, col2, col3 = st.columns(3)
      if col1.button("🟢", key=f"win_{item_id}"):
        item["status"] = "✅ Проход"
        save_history(st.session_state.history)
        st.rerun()
      if col2.button("🔴", key=f"loss_{item_id}"):
        item["status"] = "❌ Проигрыш"
        save_history(st.session_state.history)
        st.rerun()
      if col3.button("⏳", key=f"pend_{item_id}"):
        item["status"] = "⌛ Ожидание"
        save_history(st.session_state.history)
        st.rerun()


# --- ГЛАВНЫЙ ЭКРАН (Авто-поиск матчей онлайн) ---
today_date = datetime.date.today().strftime("%d.%m.%Y")
current_time = datetime.datetime.now().strftime("%H:%M")

st.subheader("🔍 Автоматический поиск матчей на сегодня")
st.info(
    "Нажмите кнопку ниже — система сама найдет актуальные матчи в сети и"
    " выдаст готовые прогнозы."
)

num_signals = st.slider("Количество сигналов для поиска", 1, 3, 2)

if st.button("🚀 Найти матчи и сделать прогноз через Groq", type="primary"):
  if not groq_api_key:
    st.error("⚠️ Введите ключ Groq API в боковой панели слева!")
  else:
    with st.spinner("Сканируем спортивные сайты и анализируем матчи..."):
      try:
        # Автоматический сбор свежих матчей из интернета
        queries = [
            f"футбол матчи расписание сегодня {today_date}",
            f"апл ла лига сериал а бундеслига матчи {today_date}",
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
              f"Топ матчи европейских чемпионатов на сегодня ({today_date})"
          )

        client = Groq(api_key=groq_api_key)

        prompt = (
            f"Сегодня {today_date}, текущее время {current_time} МСК."
            " Вот данные, найденные в интернете по сегодняшним матчам:\n"
            f"{search_context}\n\n"
            "Ты профессиональный спортивный аналитик и каппер. "
            f"Выбери ровно {num_signals} реальных матча из найденных данных, "
            "которые играются сегодня. Запрещено выдумывать команды. "
            "Для каждого сигнала укажи строго по пунктам: "
            "- ⏱ Время начала (МСК). "
            "- 🌐 Турнир / Лига. "
            "- ⚠️ Уровень риска (🟢 Ультра-надежный или 🟡 Стандартный). "
            "- 🏆 Событие (Команда 1 - Команда 2). "
            "- 🎯 Ставка и коэффициент. "
            "- 📈 Вероятность прохода (в %). "
            "- 💡 Обоснование прогноза."
        )

        # СТАБИЛЬНАЯ АКТУАЛЬНАЯ МОДЕЛЬ
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )

        response_text = completion.choices[0].message.content

        new_signal = {
            "id": str(time.time()),
            "match": f"Авто-подбор от {today_date}",
            "date": f"{today_date} в {current_time}",
            "content": response_text,
            "status": "⌛ Ожидание",
        }
        st.session_state.history.insert(0, new_signal)
        save_history(st.session_state.history)
        st.success("Матчи успешно найдены и проанализированы!")

      except Exception as e:
        st.error(f"Ошибка при обработке: {e}")

# Отображение последнего результата на главном экране
if st.session_state.history:
  st.markdown("---")
  st.subheader("🔥 Последний свежий прогноз")
  latest = st.session_state.history[0]
  st.info(f"Дата запроса: {latest['date']} | Статус: **{latest['status']}**")
  st.write(latest["content"])
  
