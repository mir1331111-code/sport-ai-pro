import datetime
import json
import os
import time
from duckduckgo_search import DDGS
from groq import Groq
import streamlit as st

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
    page_title="Auto-Sniper: Ставки и Прогнозы", page_icon="⚽", layout="wide"
)

# Компактный стиль оформления
st.markdown(
    """
<style>
    .element-container { margin-bottom: 0.3rem; }
    div[data-testid="stMetricValue"] { font-size: 1.3rem; color: #00FF66; }
</style>
""",
    unsafe_allow_html=True,
)

if "history" not in st.session_state:
  st.session_state.history = load_history()

# --- БОКОВАЯ ПАНЕЛЬ (Настройки) ---
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

# --- ВЫНОС СТАТИСТИКИ НА ГЛАВНЫЙ ЭКРАН (УДОБНО НА СМАРТФОНЕ) ---
total_wins = sum(
    1 for i in st.session_state.history if i.get("status") == "✅ Проход"
)
total_losses = sum(
    1 for i in st.session_state.history if i.get("status") == "❌ Проигрыш"
)
total_finished = total_wins + total_losses
win_rate = (total_wins / total_finished * 100) if total_finished > 0 else 0.0

st.title("⚽ Auto-Sniper")

# Блок статистики в самом верху экрана
stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
stat_col1.metric("📊 Win Rate", f"{win_rate:.1f}%")
stat_col2.metric("🟢 Победы", f"{total_wins}")
stat_col3.metric("🔴 Поражения", f"{total_losses}")
if stat_col4.button("🗑 Сброс", use_container_width=True):
  st.session_state.history = []
  save_history([])
  st.rerun()

st.markdown("---")

# --- ГЛАВНЫЙ ЭКРАН ---
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
    st.error("⚠️ Введите ключ Groq API в настройках слева (меню `>>`)!")
  else:
    with st.spinner("Сканируем спортивную сеть и формируем прогнозы..."):
      try:
        search_results = []
        queries = [
            f"футбол расписание матчей на сегодня {today_date}",
            f"футбол сегодня {today_date} коэффициенты трансляция",
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
            else "Данные о матчах на сегодня."
        )

        client = Groq(api_key=groq_api_key)

        prompt = f"""
Сегодня {today_date}, время {current_time} МСК.
Данные из сети:
{search_context}

Сформируй {num_signals} точных прогнозов на реальные футбольные матчи на СЕГОДНЯ ({today_date}).
Верни СТРОГО JSON без лишнего текста.

Структура JSON:
{{
  "matches": [
    {{
      "team1": "Название команды 1",
      "team2": "Название команды 2",
      "league": "Лига / Турнир",
      "time": "Время МСК (например, 19:00)",
      "bet": "Ставка (например: П1, ТБ 2.5, ОЗ - Да)",
      "coefficient": "1.85",
      "probability": "80%",
      "risk": "🟢 Низкий",
      "reason": "Краткое обоснование в 1 предложение"
    }}
  ]
}}
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
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            raw_response = comp.choices[0].message.content
            if raw_response:
              break
          except Exception:
            try:
              comp = client.chat.completions.create(
                  model=m,
                  messages=[{"role": "user", "content": prompt}],
                  temperature=0.3,
              )
              raw_response = comp.choices[0].message.content
              if raw_response:
                break
            except Exception:
              continue

        if not raw_response:
          st.error("Не удалось получить ответ от Groq API.")
        else:
          json_start = raw_response.find("{")
          json_end = raw_response.rfind("}") + 1
          parsed_data = json.loads(raw_response[json_start:json_end])

          new_signal = {
              "id": str(time.time()),
              "date": f"{today_date} {current_time}",
              "data": parsed_data.get("matches", []),
              "status": "⌛ Ожидание",
          }
          st.session_state.history.insert(0, new_signal)
          save_history(st.session_state.history)
          st.success("Матчи успешно рассчитаны!")

      except Exception as e:
        st.error(f"Ошибка при обработке: {e}")

# --- ОТОБРАЖЕНИЕ КАРТОЧЕК С ЛОГОТИПАМИ ---
if st.session_state.history:
  latest = st.session_state.history[0]
  matches = latest.get("data", [])

  st.subheader(f"🔥 Сигналы на {latest['date']}")

  if matches and isinstance(matches, list):
    cols = st.columns(len(matches))

    for idx, m in enumerate(matches):
      with cols[idx]:
        with st.container(border=True):
          team1 = m.get("team1", "Команда 1")
          team2 = m.get("team2", "Команда 2")

          # Динамическая генерация эмблем команд
          logo1_url = f"https://ui-avatars.com/api/?name={team1}&background=1e293b&color=00ff66&bold=true&size=64"
          logo2_url = f"https://ui-avatars.com/api/?name={team2}&background=1e293b&color=00bfff&bold=true&size=64"

          # Шапка карточки с графическими логотипами
          l_col1, l_col2, l_col3 = st.columns([1, 2, 1])
          with l_col1:
            st.image(logo1_url, width=44)
          with l_col2:
            st.markdown(
                f"<div style='text-align: center; font-size: 0.85rem;'"
                f"><b>{team1}</b><br><span"
                f" style='color:gray;'>VS</span><br><b>{team2}</b></div>",
                unsafe_allow_html=True,
            )
          with l_col3:
            st.image(logo2_url, width=44)

          st.caption(
              f"🏆 {m.get('league', 'Турнир')} | ⏰ {m.get('time', '19:00')}"
          )
          st.markdown("---")

          c1, c2 = st.columns(2)
          with c1:
            st.metric(
                "🎯 Ставка",
                m.get("bet", "—"),
                f"Кф {m.get('coefficient', '—')}",
            )
          with c2:
            st.metric(
                "📈 Проход",
                m.get("probability", "—"),
                m.get("risk", "🟢 Низкий"),
            )

          st.info(f"💡 {m.get('reason', 'Анализ формы команд.')}")
          
