import datetime
import json
import os
import time
from duckduckgo_search import DDGS
from groq import Groq
import streamlit as st

# Файл для хранения истории
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

# --- БОКОВАЯ ПАНЕЛЬ ---
st.sidebar.header("⚙️ Настройки и Архив")
groq_api_key = st.sidebar.text_input("Ключ Groq API", type="password")


def fetch_active_groq_models(api_key):
  if not api_key:
    return ["llama-3.3-70b-versatile"]
  try:
    client = Groq(api_key=api_key)
    models = client.models.list()
    active_ids = [
        m.id
        for m in models.data
        if getattr(m, "active", True) and "whisper" not in m.id.lower()
    ]
    return active_ids if active_ids else ["llama-3.3-70b-versatile"]
  except Exception:
    return ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


selected_model = None
if groq_api_key:
  available_models = fetch_active_groq_models(groq_api_key)
  selected_model = st.sidebar.selectbox(
      "🤖 Активная модель Groq", available_models, index=0
  )

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

# --- ГЛАВНЫЙ ЭКРАН ---
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
        # Усиленный сбор сведений через DDGS
        search_results = []
        queries = [
            f"футбол сегодня {today_date} матчи расписание",
            f"чемпионат футбол матчи {today_date}",
            f"football matches schedule today {today_date}",
        ]

        with DDGS() as ddgs:
          for q in queries:
            try:
              res_text = ddgs.text(
                  q, region="ru-ru", timelimit="d", max_results=5
              )
              for r in res_text:
                body = r.get("body") or r.get("snippet") or ""
                title = r.get("title", "")
                if body:
                  search_results.append(f"{title}: {body}")
            except Exception:
              pass

            try:
              res_news = ddgs.news(
                  q, region="ru-ru", timelimit="d", max_results=3
              )
              for r in res_news:
                body = r.get("body") or r.get("snippet") or ""
                title = r.get("title", "")
                if body:
                  search_results.append(f"{title}: {body}")
            except Exception:
              pass

        search_context = (
            "\n".join(search_results)
            if search_results
            else "Результаты онлайн-поиска временно ограничены."
        )

        client = Groq(api_key=groq_api_key)

        # Гибкий и универсальный промпт
        prompt = f"""
Сегодня {today_date}, текущее время {current_time} МСК.

Вот данные из поисковой выдачи:
{search_context}

Инструкция:
Ты профессиональный спортивный аналитик и каппер. 
Выбери {num_signals} наиболее актуальных и важных футбольных матчей на сегодня ({today_date}). 
Если поисковых данных мало, опирайся на свои знания реальных матчей главных европейских турниров (АПЛ, Ла Лига, Серия А, Бундеслига, РПЛ и др.), завершающих тур в этот день.

Для каждого из {num_signals} сигналов выведи строгую структуру:
- ⏱ **Время начала (МСК)**:
- 🌐 **Турнир / Лига**:
- ⚠️ **Уровень риска**: (🟢 Ультра-надежный или 🟡 Стандартный)
- 🏆 **Матч**: (Команда 1 - Команда 2)
- 🎯 **Прогноз и коэффициент**:
- 📈 **Вероятность прохода**: (в %)
- 💡 **Аналитика и обоснование**:
"""

        models_to_try = []
        if selected_model:
          models_to_try.append(selected_model)

        fallback_list = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "llama-3.2-3b-preview",
            "deepseek-r1-distill-llama-70b",
        ]
        for m in fallback_list:
          if m not in models_to_try:
            models_to_try.append(m)

        response_text = None
        last_error = None

        for model_name in models_to_try:
          try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            response_text = completion.choices[0].message.content
            break
          except Exception as err:
            last_error = err
            continue

        if not response_text:
          raise last_error

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

if st.session_state.history:
  st.markdown("---")
  st.subheader("🔥 Последний свежий прогноз")
  latest = st.session_state.history[0]
  st.info(f"Дата запроса: {latest['date']} | Статус: **{latest['status']}**")
  st.write(latest["content"])
