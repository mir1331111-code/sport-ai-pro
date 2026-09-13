import datetime
import json
import os
import re
import time
from duckduckgo_search import DDGS
from groq import Groq
import requests
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


st.set_page_config(
    page_title="Auto-Sniper: Live & Сегодня", page_icon="⚽", layout="wide"
)

# Стили для мобильного экрана
st.markdown(
    """
<style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    .element-container { margin-bottom: 0.3rem; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem; color: #00FF66; }
    div[data-testid="stMetricLabel"] { font-size: 0.8rem; }
</style>
""",
    unsafe_allow_html=True,
)

if "history" not in st.session_state:
  st.session_state.history = load_history()

# --- ФУНКЦИЯ ПОЛУЧЕНИЯ 100% РЕАЛЬНЫХ МАТЧЕЙ С ESPN API ---


def fetch_espn_matches():
  today_str = datetime.date.today().strftime("%Y%m%d")
  leagues = [
      "eng.1",
      "esp.1",
      "ger.1",
      "ita.1",
      "fra.1",
      "rus.1",
      "uefa.champions",
      "uefa.europa",
      "usa.1",
      "fifa.world",
  ]
  real_matches = []

  for lg in leagues:
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/scoreboard?dates={today_str}"
    try:
      resp = requests.get(url, timeout=4)
      if resp.status_code == 200:
        data = resp.json()
        events = data.get("events", [])
        lg_name = (
            data.get("leagues", [{}])[0].get("name")
            or lg.upper().replace(".1", "")
        )

        for ev in events:
          comp = ev.get("competitions", [{}])[0]
          status_type = ev.get("status", {}).get("type", {})
          state = status_type.get("state", "pre")
          short_detail = status_type.get("shortDetail", "Сегодня")

          competitors = comp.get("competitors", [])
          if len(competitors) < 2:
            continue

          home = next(
              (c for c in competitors if c.get("homeAway") == "home"),
              competitors[0],
          )
          away = next(
              (c for c in competitors if c.get("homeAway") == "away"),
              competitors[1],
          )

          t1_name = home.get("team", {}).get("displayName", "Команда 1")
          t2_name = away.get("team", {}).get("displayName", "Команда 2")

          t1_logo = home.get("team", {}).get(
              "logo",
              f"https://ui-avatars.com/api/?name={t1_name}&background=1e293b&color=00ff66",
          )
          t2_logo = away.get("team", {}).get(
              "logo",
              f"https://ui-avatars.com/api/?name={t2_name}&background=1e293b&color=00bfff",
          )

          score_home = home.get("score", "0")
          score_away = away.get("score", "0")

          is_live = state == "in"
          status_str = (
              f"🔴 LIVE {short_detail} ({score_home}:{score_away})"
              if is_live
              else f"⏰ {short_detail}"
          )

          real_matches.append({
              "league": lg_name,
              "team1": t1_name,
              "team2": t2_name,
              "team1_logo": t1_logo,
              "team2_logo": t2_logo,
              "status": status_str,
              "is_live": is_live,
              "state": state,
          })
    except Exception:
      pass

  real_matches.sort(key=lambda x: (not x["is_live"], x["state"] == "post"))
  return real_matches


# --- БОКОВАЯ ПАНЕЛЬ (Настройки) ---
st.sidebar.title("⚙️ Настройки API")
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
  selected_model = st.sidebar.selectbox("Модель Groq", models_list, index=0)

# --- ВЕРХНЯЯ ПАНЕЛЬ: СТАТИСТИКА В САМОМ ВЕРХУ ---
total_wins = 0
total_losses = 0
total_pending = 0

for item in st.session_state.history:
  for match_card in item.get("data", []):
    st_val = match_card.get("status", "⌛ Ожидание")
    if st_val == "✅ Проход":
      total_wins += 1
    elif st_val == "❌ Проигрыш":
      total_losses += 1
    else:
      total_pending += 1

total_finished = total_wins + total_losses
win_rate = (total_wins / total_finished * 100) if total_finished > 0 else 0.0

st.title("⚽ Auto-Sniper: Live и Сегодня")

stat_col1, stat_col2, stat_col3, stat_col4, stat_col5 = st.columns(5)
stat_col1.metric("📊 Win Rate", f"{win_rate:.1f}%")
stat_col2.metric("🟢 Победы", f"{total_wins}")
stat_col3.metric("🔴 Поражения", f"{total_losses}")
stat_col4.metric("⏳ В игре", f"{total_pending}")
if stat_col5.button("🗑 Очистить", use_container_width=True):
  st.session_state.history = []
  save_history([])
  st.rerun()

st.markdown("---")

# --- УПРАВЛЕНИЕ ПОИСКОМ ---
today_date = datetime.date.today().strftime("%d.%m.%Y")
current_time = datetime.datetime.now().strftime("%H:%M")

c_input1, c_input2 = st.columns([3, 1])
with c_input1:
  num_signals = st.slider("Сколько матчей проанализировать:", 1, 4, 2)
with c_input2:
  btn_search = st.button(
      "🚀 Запросить LIVE и Сегодня", type="primary", use_container_width=True
  )

if btn_search:
  if not groq_api_key:
    st.error("⚠️ Введите ключ Groq API слева в настройках (кнопка `>>`)!")
  else:
    with st.spinner("Получаем прямые трансляции и расписание матчей..."):
      try:
        real_matches = fetch_espn_matches()

        if real_matches:
          match_lines = []
          for idx, rm in enumerate(real_matches[:12]):
            match_lines.append(
                f"{idx+1}. [{rm['league']}] {rm['team1']} VS {rm['team2']} |"
                f" Статус: {rm['status']}"
            )
          context_text = "СПИСОК РЕАЛЬНЫХ МАТЧЕЙ НА СЕГОДНЯ / LIVE:\n" + "\n".join(
              match_lines
          )
        else:
          search_results = []
          with DDGS() as ddgs:
            try:
              results = ddgs.text(
                  f"футбол онлайн трансляция сегодня {today_date}",
                  region="ru-ru",
                  max_results=5,
              )
              for r in results:
                search_results.append(r.get("body", ""))
            except Exception:
              pass
          context_text = "\n".join(search_results)

        client = Groq(api_key=groq_api_key)

        prompt = f"""
Сегодня {today_date}, текущее время {current_time} МСК.

{context_text}

ЗАДАЧА:
Выбери ровно {num_signals} наиболее надежных матча ИЗ СПИСКА ВЫШЕ.
Для каждого матча дай ПРОФЕССИОНАЛЬНУЮ СТАВКУ. 
Используй РАЗНООБРАЗНЫЕ ТИПЫ СТАВОК (не только победы, а также: Тотал Больше/Меньше (ТБ/ТМ), Фора (Ф1/Ф2), Обе Забьют (ОЗ - Да/Нет), Двойной Шанс (1X/X2)).

ТРЕБОВАНИЯ:
1. Строго на РУССКОМ языке.
2. Никаких текстов мыслей, кода или английских слов.
3. Верни СТРОГО JSON без лишних символов.

Формат JSON:
{{
  "matches": [
    {{
      "team1": "Точное название Команды 1",
      "team2": "Точное название Команды 2",
      "league": "Название турнира",
      "time_status": "Время или Статус LIVE",
      "bet_type": "Тип ставки (Тотал / Фора / Исход / ОЗ)",
      "bet": "Конкретная ставка (например: ТБ 2.5, Ф1 (0), ОЗ - Да, П1)",
      "coefficient": "1.85",
      "probability": "82%",
      "risk": "🟢 Низкий",
      "reason": "Короткая аналитика в 1 предложение"
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
          st.error("Ошибка получения ответа от Groq.")
        else:
          cleaned = re.sub(
              r"<think>.*?</think>", "", raw_response, flags=re.DOTALL
          ).strip()
          json_start = cleaned.find("{")
          json_end = cleaned.rfind("}") + 1
          parsed_json = json.loads(cleaned[json_start:json_end])

          parsed_matches = parsed_json.get("matches", [])

          for pm in parsed_matches:
            t1 = pm.get("team1", "")
            t2 = pm.get("team2", "")

            match_found = next(
                (
                    rm
                    for rm in real_matches
                    if t1.lower() in rm["team1"].lower()
                    or rm["team1"].lower() in t1.lower()
                ),
                None,
            )

            if match_found:
              pm["team1_logo"] = match_found["team1_logo"]
              pm["team2_logo"] = match_found["team2_logo"]
              pm["league"] = match_found["league"]
              pm["time_status"] = match_found["status"]
            else:
              pm["team1_logo"] = (
                  f"https://ui-avatars.com/api/?name={t1}&background=1e293b&color=00ff66&bold=true"
              )
              pm["team2_logo"] = (
                  f"https://ui-avatars.com/api/?name={t2}&background=1e293b&color=00bfff&bold=true"
              )

            pm["status"] = "⌛ Ожидание"

          new_entry = {
              "id": str(time.time()),
              "date": f"{today_date} {current_time}",
              "data": parsed_matches,
          }
          st.session_state.history.insert(0, new_entry)
          save_history(st.session_state.history)
          st.success("Матчи найдены и ставки рассчитаны!")

      except Exception as e:
        st.error(f"Ошибка при обработке: {e}")

# --- ОТОБРАЖЕНИЕ КАРТОЧЕК ---
if st.session_state.history:
  latest = st.session_state.history[0]
  matches_data = latest.get("data", [])

  st.subheader(f"🔥 Прогнозы на {latest['date']}")

  if matches_data:
    cols = st.columns(min(len(matches_data), 3))

    for idx, card in enumerate(matches_data):
      col_idx = idx % len(cols)
      with cols[col_idx]:
        with st.container(border=True):
          t1 = card.get("team1", "Команда 1")
          t2 = card.get("team2", "Команда 2")
          logo1 = card.get("team1_logo")
          logo2 = card.get("team2_logo")

          c_l1, c_l2, c_l3 = st.columns([1, 2, 1])
          with c_l1:
            st.image(logo1, width=48)
          with c_l2:
            st.markdown(
                f"<div style='text-align: center; font-size: 0.85rem;'"
                f"><b>{t1}</b><br><span"
                f" style='color:gray;'>VS</span><br><b>{t2}</b></div>",
                unsafe_allow_html=True,
            )
          with c_l3:
            st.image(logo2, width=48)

          st.caption(
              f"🏆 {card.get('league', 'Футбол')} |"
              f" {card.get('time_status', 'Сегодня')}"
          )
          st.markdown("---")

          m_c1, m_c2 = st.columns(2)
          with m_c1:
            st.metric(
                f"🎯 {card.get('bet_type', 'Ставка')}",
                card.get("bet", "—"),
                f"Кф {card.get('coefficient', '—')}",
            )
          with m_c2:
            st.metric(
                "📈 Проход",
                card.get("probability", "—"),
                card.get("risk", "🟢 Низкий"),
            )

          st.info(f"💡 {card.get('reason', 'Анализ формы команд.')}")

          cur_status = card.get("status", "⌛ Ожидание")
          st.write(f"Результат: **{cur_status}**")

          b_c1, b_c2, b_c3 = st.columns(3)
          if b_c1.button("🟢 Зашел", key=f"win_{latest['id']}_{idx}"):
            card["status"] = "✅ Проход"
            save_history(st.session_state.history)
            st.rerun()
          if b_c2.button("🔴 Минус", key=f"loss_{latest['id']}_{idx}"):
            card["status"] = "❌ Проигрыш"
            save_history(st.session_state.history)
            st.rerun()
          if b_c3.button("⏳ Ждем", key=f"pend_{latest['id']}_{idx}"):
            card["status"] = "⌛ Ожидание"
            save_history(st.session_state.history)
            st.rerun()
            
