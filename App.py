import datetime
import json
import os
import re
import time
from duckduckgo_search import DDGS
from groq import Groq
import streamlit as st

# Файл истории
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


# Настройки страницы Streamlit
st.set_page_config(
    page_title="Auto-Sniper: Ставки и Прогнозы", page_icon="⚽", layout="wide"
)

# Стили для компактного отображения
st.markdown(
    """
<style>
    .element-container { margin-bottom: 0.5rem; }
    .stAlert { padding: 0.5rem 1rem; }
    div[data-testid="stMetricValue"] { font-size: 1.4rem; color: #00FF66; }
</style>
""",
    unsafe_allow_html=True,
)

if "history" not in st.session_state:
  st.session_state.history = load_history()

# --- БОКОВАЯ ПАНЕЛЬ ---
st.sidebar.title("⚙️ Настройки")
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
        if getattr(m, "active", True)
        and "whisper" not in m.id.lower()
        and "vision" not in m.id.lower()
    ]
    return active_ids if active_ids else ["llama-3.3-70b-versatile"]
  except Exception:
    return ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


selected_model = None
if groq_api_key:
  models_list = fetch_active_groq_models(groq_api_key)
  selected_model = st.sidebar.selectbox("Активная модель", models_list, index=0)

# Статистика
total_wins = sum(
    1 for i in st.session_state.history if i.get("status") == "✅ Проход"
)
total_losses = sum(
    1 for i in st.session_state.history if i.get("status") == "❌ Проигрыш"
)
total_finished = total_wins + total_losses
win_rate = (total_wins / total_finished * 100) if total_finished > 0 else 0

st.sidebar.markdown("---")
st.sidebar.write(
    f"📊 **WinRate:** `{win_rate:.1f}%` (🟢 {total_wins} / 🔴 {total_losses})"
)

if st.sidebar.button("🗑 Очистить историю"):
  st.session_state.history = []
  save_history([])
  st.rerun()

# --- ГЛАВНЫЙ ЭКРАН ---
st.title("⚽ Auto-Sniper: Точные Экспрессы и Одинары")

today_date = datetime.date.today().strftime("%d.%m.%Y")
current_time = datetime.datetime.now().strftime("%H:%M")

col_top1, col_top2 = st.columns([3, 1])
with col_top1:
  num_signals = st.slider("Количество матчей для анализа", 1, 3, 2)
with col_top2:
  btn_search = st.button(
      "🚀 Найти и рассчитать", type="primary", use_container_width=True
  )

if btn_search:
  if not groq_api_key:
    st.error("⚠️ Введите ключ Groq API слева в настройках!")
  else:
    with st.spinner("Поиск актуальных матчей и расчет ставок..."):
      try:
        # Поиск свежих спортивных данных
        search_results = []
        queries = [
            f"футбол расписание матчей на сегодня {today_date}",
            f"футбол сегодня {today_date} трансляция коэффициенты",
        ]

        with DDGS() as ddgs:
          for q in queries:
            try:
              results = ddgs.text(
                  q, region="ru-ru", timelimit="d", max_results=4
              )
              for r in results:
                body = r.get("body") or r.get("snippet") or ""
                if body:
                  search_results.append(body)
            except Exception:
              pass

        search_context = (
            "\n".join(search_results)
            if search_results
            else "Данные онлайн-поиска обновлены."
        )

        client = Groq(api_key=groq_api_key)

        # Строгий системный промпт без лишних мыслей и рассуждений
        prompt = f"""
Сегодня {today_date}, время {current_time} МСК.
Данные из сети:
{search_context}

ЗАДАЧА:
Сформируй ровно {num_signals} наиболее надежных прогнозов на реальные футбольные матчи СЕГОДНЯ ({today_date}).
ОТВЕЧАЙ СТРОГО НА РУССКОМ ЯЗЫКЕ. Запрещено выводить технические мысли, код или текст на английском.

Формат для КАЖДОГО матча должен быть СТРОГО таким (разделяй матчи строкой ---):

МАТЧ: Команда 1 — Команда 2
ЛИГА: Название турнира
ВРЕМЯ: HH:MM МСК
СТАВКА: Конкретный исход (например: П1, ТБ 2.5, ОЗ - Да, 1X)
КОЭФФИЦИЕНТ: 1.75
ВЕРОЯТНОСТЬ: 85%
РИСК: 🟢 Низкий (или 🟡 Средний)
ПРИЧИНА: Коротко в 1 предложение (почему эта ставка).
"""

        models_to_try = []
        if selected_model:
          models_to_try.append(selected_model)
        models_to_try.extend(
            ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
        )

        raw_response = None
        for m in models_to_try:
          try:
            comp = client.chat.completions.create(
                model=m,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )
            raw_response = comp.choices[0].message.content
            if raw_response:
              break
          except Exception:
            continue

        if not raw_response:
          st.error("Не удалось получить ответ от API. Попробуйте еще раз.")
        else:
          # ОЧИСТКА: Удаляем теги мыслей <think>...</think> и возможный английский текст
          cleaned_text = re.sub(
              r"<think>.*?</think>", "", raw_response, flags=re.DOTALL
          ).strip()

          new_signal = {
              "id": str(time.time()),
              "date": f"{today_date} {current_time}",
              "content": cleaned_text,
              "status": "⌛ Ожидание",
          }
          st.session_state.history.insert(0, new_signal)
          save_history(st.session_state.history)
          st.success("Прогнозы успешно обновлены!")

      except Exception as e:
        st.error(f"Ошибка при поиске: {e}")

# --- ОТОБРАЖЕНИЕ КАРТОЧЕК (КОМПАКТНО НА ОДНОМ ЭКРАНЕ) ---
if st.session_state.history:
  latest = st.session_state.history[0]
  st.subheader(f"🔥 Актуальные сигналы ({latest['date']})")

  # Разбиваем текст на отдельные матчи
  raw_matches = [
      m.strip() for m in latest["content"].split("---") if m.strip()
  ]

  if raw_matches:
    cols = st.columns(len(raw_matches))

    for idx, match_text in enumerate(raw_matches):
      with cols[idx]:
        with st.container(border=True):
          # Извлекаем данные через регулярные выражения для красивого вывода
          match_title = re.search(r"МАТЧ:\s*(.*)", match_text)
          league = re.search(r"ЛИГА:\s*(.*)", match_text)
          match_time = re.search(r"ВРЕМЯ:\s*(.*)", match_text)
          bet = re.search(r"СТАВКА:\s*(.*)", match_text)
          coeff = re.search(r"КОЭФФИЦИЕНТ:\s*(.*)", match_text)
          prob = re.search(r"ВЕРОЯТНОСТЬ:\s*(.*)", match_text)
          risk = re.search(r"РИСК:\s*(.*)", match_text)
          reason = re.search(r"ПРИЧИНА:\s*(.*)", match_text)

          st.markdown(
              f"### ⚽ {match_title.group(1) if match_title else 'Матч'}"
          )
          st.caption(
              f"🏆 {league.group(1) if league else 'Футбол'} | ⏰"
              f" {match_time.group(1) if match_time else 'Сегодня'}"
          )

          st.markdown("---")
          c1, c2 = st.columns(2)
          with c1:
            st.metric(
                "🎯 Ставка",
                bet.group(1) if bet else "—",
                f"Кф {coeff.group(1) if coeff else '—'}",
            )
          with c2:
            st.metric(
                "📈 Проход",
                prob.group(1) if prob else "—",
                risk.group(1) if risk else "",
            )

          if reason:
            st.info(f"💡 {reason.group(1)}")
  else:
    st.write(latest["content"])
    
