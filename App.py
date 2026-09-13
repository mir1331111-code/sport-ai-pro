import datetime
import json
import os
import re
import time
import requests
import streamlit as st
from duckduckgo_search import DDGS
from groq import Groq

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
    page_title="Auto-Sniper: Dual AI (Groq + Gemini)", page_icon="⚡", layout="wide"
)

st.markdown(
    """
<style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    .element-container { margin-bottom: 0.3rem; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem; color: #00FF66; }
    div[data-testid="stMetricLabel"] { font-size: 0.8rem; }
    .score-badge {
        background-color: #059669;
        color: white;
        padding: 4px 8px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85rem;
        display: inline-block;
        margin-bottom: 5px;
    }
</style>
""",
    unsafe_allow_html=True,
)

if "history" not in st.session_state:
  st.session_state.history = load_history()

# --- СКАНИРОВАНИЕ ВСЕХ ВИДОВ СПОРТА (ESPN MULTI-SPORT) ---
SPORTS_ENDPOINTS = [
    ("soccer", "eng.1", "⚽ Футбол (Англия)"),
    ("soccer", "esp.1", "⚽ Футбол (Испания)"),
    ("soccer", "ger.1", "⚽ Футбол (Германия)"),
    ("soccer", "ita.1", "⚽ Футбол (Италия)"),
    ("soccer", "rus.1", "⚽ Футбол (Россия)"),
    ("soccer", "uefa.champions", "⚽ ЛЧ"),
    ("basketball", "nba", "🏀 Баскетбол (NBA)"),
    ("hockey", "nhl", "🏒 Хоккей (NHL)"),
    ("tennis", "atp", "🎾 Теннис (ATP)"),
]


def fetch_all_sports_matches():
  today_str = datetime.date.today().strftime("%Y%m%d")
  real_matches = []

  for sport, league, label in SPORTS_ENDPOINTS:
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={today_str}"
    try:
      resp = requests.get(url, timeout=3)
      if resp.status_code == 200:
        data = resp.json()
        events = data.get("events", [])

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
          score_str = f"{score_home}:{score_away}"
          status_str = (
              f"🔴 LIVE {short_detail} ({score_str})"
              if is_live
              else f"⏰ {short_detail}"
          )

          real_matches.append({
              "sport_label": label,
              "team1": t1_name,
              "team2": t2_name,
              "team1_logo": t1_logo,
              "team2_logo": t2_logo,
              "status": status_str,
              "is_live": is_live,
              "score": score_str,
              "state": state,
          })
    except Exception:
      pass

  real_matches.sort(key=lambda x: (not x["is_live"], x["state"] == "post"))
  return real_matches


def call_gemini_api(api_key, prompt_text):
  url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
  headers = {"Content-Type": "application/json"}
  payload = {
      "contents": [{"parts": [{"text": prompt_text}]}],
      "generationConfig": {
          "temperature": 0.2,
          "responseMimeType": "application/json",
      },
  }
  try:
    res = requests.post(url, json=payload, headers=headers, timeout=12)
    if res.status_code == 200:
      data = res.json()
      return data["candidates"][0]["content"]["parts"][0]["text"]
  except Exception:
    pass
  return None


# --- БОКОВАЯ ПАНЕЛЬ ---
st.sidebar.title("⚙️ Интеллект ИИ (Двухъядерный)")
groq_api_key = st.sidebar.text_input("1. Ключ Groq API", type="password")
gemini_api_key = st.sidebar.text_input("2. Ключ Gemini API", type="password")


def fetch_active_groq_models(api_key):
  if not api_key:
    return ["llama-3.3-70b-versatile"]
  try:
    client = Groq(api_key=api_key)
    models = client.models.list()
    return [
        m.id
        for m in models.data
        if getattr(m, "active", True)
        and "whisper" not in m.id.lower()
        and "vision" not in m.id.lower()
    ]
  except Exception:
    return ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


selected_groq_model = None
if groq_api_key:
  models_list = fetch_active_groq_models(groq_api_key)
  selected_groq_model = st.sidebar.selectbox("Модель Groq", models_list, index=0)

# --- РАСЧЕТ СТАТИСТИКИ ---
total_wins = 0
total_losses = 0
total_pending = 0
failed_predictions = []

for item in st.session_state.history:
  for card in item.get("data", []):
    st_val = card.get("status", "⌛ Ожидание")
    if st_val == "✅ Проход":
      total_wins += 1
    elif st_val == "❌ Проигрыш":
      total_losses += 1
      failed_predictions.append(
          f"Лига: {card.get('league')}, Игра: {card.get('team1')} -"
          f" {card.get('team2')}, Ставка: {card.get('bet')}, Аналитика:"
          f" {card.get('reason')}"
      )
    else:
      total_pending += 1

total_finished = total_wins + total_losses
win_rate = (total_wins / total_finished * 100) if total_finished > 0 else 0.0

st.title("⚡ Auto-Sniper: Консилиум Groq + Gemini")

# Шапка статистики
s_c1, s_c2, s_c3, s_c4, s_c5 = st.columns(5)
s_c1.metric("📊 Win Rate", f"{win_rate:.1f}%")
s_c2.metric("🟢 Победы", f"{total_wins}")
s_c3.metric("🔴 Поражения", f"{total_losses}")
s_c4.metric("🧠 Ошибок в памяти", f"{len(failed_predictions)}")

if s_c5.button("🔄 Обновить счета LIVE", use_container_width=True):
  with st.spinner("Проверяем текущие счета в прямом эфире..."):
    live_matches = fetch_all_sports_matches()
    updated_count = 0
    for entry in st.session_state.history:
      for card in entry.get("data", []):
        t1 = card.get("team1", "").lower()
        found = next(
            (m for m in live_matches if t1 in m["team1"].lower()), None
        )
        if found:
          old_score = card.get("score", "0:0")
          new_score = found["score"]
          if old_score != new_score and new_score != "0:0":
            card["score_changed"] = True
            card["prev_score"] = old_score
            card["score"] = new_score
            card["time_status"] = found["status"]
            updated_count += 1
          else:
            card["score"] = new_score
            card["time_status"] = found["status"]

    save_history(st.session_state.history)
    st.success(f"Счета обновлены! Изменений: {updated_count}")
    st.rerun()

st.markdown("---")

tab_current, tab_history = st.tabs(
    ["🔥 Генерировать Прогнозы (Два ИИ)", "📜 Умный Архив & История Счетов"]
)

with tab_current:
  today_date = datetime.date.today().strftime("%d.%m.%Y")
  current_time = datetime.datetime.now().strftime("%H:%M")

  c_input1, c_input2 = st.columns([3, 1])
  with c_input1:
    num_signals = st.slider("Сколько матчей проанализировать:", 1, 4, 2)
  with c_input2:
    btn_search = st.button(
        "🧠 Консилиум и Расчет", type="primary", use_container_width=True
    )

  if btn_search:
    if not groq_api_key and not gemini_api_key:
      st.error("⚠️ Введите хотя бы один API ключ (Groq или Gemini) слева!")
    else:
      with st.spinner(
          "Запуск совместного разума Groq + Gemini и сбор матчей..."
      ):
        try:
          real_matches = fetch_all_sports_matches()

          if real_matches:
            match_lines = [
                f"{idx+1}. [{rm['sport_label']}] {rm['team1']} VS"
                f" {rm['team2']} | Счет: {rm['score']} | Статус: {rm['status']}"
                for idx, rm in enumerate(real_matches[:15])
            ]
            context_text = "СПИСОК МАТЧЕЙ LIVE И СЕГОДНЯ:\n" + "\n".join(
                match_lines
            )
          else:
            search_results = []
            with DDGS() as ddgs:
              try:
                results = ddgs.text(
                    f"спорт онлайн трансляции сегодня {today_date}",
                    region="ru-ru",
                    max_results=5,
                )
                for r in results:
                  search_results.append(r.get("body", ""))
              except Exception:
                pass
            context_text = "\n".join(search_results)

          loss_context = ""
          if failed_predictions:
            loss_context = (
                "\n\nИЗБЕГАЙ ПРОШЛЫХ ОШИБОК! Ранее проиграли ставки:\n"
                + "\n".join(failed_predictions[-5:])
            )

          base_prompt = f"""
Сегодня {today_date}, время {current_time} МСК.

{context_text}
{loss_context}

ЗАДАЧА:
Выбери {num_signals} самых надежных матча. Проанализируй формы команд, личные встречи и текущий счет.
Дай точную ставку (Тотал, Фора, Победитель, Обе Забьют).

Верни СТРОГО JSON формата:
{{
  "matches": [
    {{
      "team1": "Название Команды 1",
      "team2": "Название Команды 2",
      "league": "Вид спорта / Лига",
      "time_status": "Время или Статус LIVE",
      "score": "Текущий счет (например 1:0)",
      "bet_type": "Тип ставки",
      "bet": "Ставка (например: ТБ 2.5, Ф1 (-1), П1)",
      "coefficient": "1.85",
      "probability": "85%",
      "risk": "🟢 Низкий",
      "reason": "Единое экспертное обоснование ИИ"
    }}
  ]
}}
"""

          parsed_json = None
          used_ai = "Single AI"

          if groq_api_key and gemini_api_key:
            used_ai = "🤖🤖 Консенсус Groq + Gemini"
            gemini_raw = call_gemini_api(gemini_api_key, base_prompt)

            consensus_prompt = (
                base_prompt
                + f"\n\nМнение модели Gemini:\n{gemini_raw}\nСинтезируй общее"
                " окончательное решение в формате JSON!"
            )

            client = Groq(api_key=groq_api_key)
            comp = client.chat.completions.create(
                model=selected_groq_model or "llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": consensus_prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            raw_response = comp.choices[0].message.content

          elif groq_api_key:
            used_ai = "🧠 Groq AI"
            client = Groq(api_key=groq_api_key)
            comp = client.chat.completions.create(
                model=selected_groq_model or "llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": base_prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            raw_response = comp.choices[0].message.content

          else:
            used_ai = "✨ Gemini AI"
            raw_response = call_gemini_api(gemini_api_key, base_prompt)

          cleaned = re.sub(
              r"<think>.*?</think>", "", raw_response, flags=re.DOTALL
          ).strip()
          json_start = cleaned.find("{")
          json_end = cleaned.rfind("}") + 1
          parsed_json = json.loads(cleaned[json_start:json_end])

          parsed_matches = parsed_json.get("matches", [])

          for pm in parsed_matches:
            t1 = pm.get("team1", "")
            match_found = next(
                (
                    rm
                    for rm in real_matches
                    if t1.lower() in rm["team1"].lower()
                ),
                None,
            )

            if match_found:
              pm["team1_logo"] = match_found["team1_logo"]
              pm["team2_logo"] = match_found["team2_logo"]
              pm["league"] = match_found["sport_label"]
              pm["time_status"] = match_found["status"]
              pm["score"] = match_found["score"]
            else:
              pm["team1_logo"] = (
                  f"https://ui-avatars.com/api/?name={t1}&background=1e293b&color=00ff66"
              )
              pm["team2_logo"] = (
                  f"https://ui-avatars.com/api/?name={pm.get('team2','')}&background=1e293b&color=00bfff"
              )
              pm["score"] = pm.get("score", "0:0")

            pm["status"] = "⌛ Ожидание"
            pm["score_changed"] = False

          new_entry = {
              "id": str(time.time()),
              "date": f"{today_date} {current_time}",
              "ai_source": used_ai,
              "data": parsed_matches,
          }
          st.session_state.history.insert(0, new_entry)
          save_history(st.session_state.history)
          st.success(f"Прогноз сформирован! Источник: {used_ai}")

        except Exception as e:
          st.error(f"Ошибка анализа: {e}")

  # Отображение ПОСЛЕДНИХ прогнозов
  if st.session_state.history:
    latest = st.session_state.history[0]
    matches_data = latest.get("data", [])

    st.subheader(
        f"🔥 Свежий прогноз ({latest['date']}) — {latest.get('ai_source', 'ИИ')}"
    )

    if matches_data:
      cols = st.columns(min(len(matches_data), 3))
      for idx, card in enumerate(matches_data):
        col_idx = idx % len(cols)
        with cols[col_idx]:
          with st.container(border=True):
            t1, t2 = card.get("team1", "Команда 1"), card.get(
                "team2", "Команда 2"
            )

            if card.get("score_changed"):
              prev_sc = card.get("prev_score", "0:0")
              curr_sc = card.get("score", "0:0")
              st.markdown(
                  f"<div class='score-badge'>🔥 ГОЛ / СЧЕТ ИЗМЕНИЛСЯ: {prev_sc}"
                  f" ➔ {curr_sc}</div>",
                  unsafe_allow_html=True,
              )

            c_l1, c_l2, c_l3 = st.columns([1, 2, 1])
            with c_l1:
              st.image(card.get("team1_logo"), width=44)
            with c_l2:
              score_val = card.get("score", "0:0")
              st.markdown(
                  f"<div style='text-align: center; font-size:"
                  f" 0.85rem;'><b>{t1}</b><br><span style='color:#00FF66;"
                  f" font-size:1.1rem;'><b>{score_val}</b></span><br><b>{t2}</b></div>",
                  unsafe_allow_html=True,
              )
            with c_l3:
              st.image(card.get("team2_logo"), width=44)

            st.caption(
                f"🏆 {card.get('league', 'Спорт')} |"
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

            st.info(f"💡 {card.get('reason', 'Анализ.')}")

            cur_status = card.get("status", "⌛ Ожидание")
            st.write(f"Результат: **{cur_status}**")

            b_c1, b_c2, b_c3 = st.columns(3)
            if b_c1.button("🟢 Зашел", key=f"latest_win_{idx}"):
              card["status"] = "✅ Проход"
              save_history(st.session_state.history)
              st.rerun()
            if b_c2.button("🔴 Минус", key=f"latest_loss_{idx}"):
              card["status"] = "❌ Проигрыш"
              save_history(st.session_state.history)
              st.rerun()
            if b_c3.button("⏳ Ждем", key=f"latest_pend_{idx}"):
              card["status"] = "⌛ Ожидание"
              save_history(st.session_state.history)
              st.rerun()

# --- ВКЛАДКА 2: ИСТОРИЯ ---
with tab_history:
  st.subheader("📜 Красивая история всех прогнозов и динамика счетов")

  if not st.session_state.history:
    st.info("История прогнозов пуста.")
  else:
    filter_status = st.radio(
        "Фильтр по статусу:",
        ["Все", "🟢 Выигрыши", "🔴 Проигрыши", "⏳ В процессе"],
        horizontal=True,
    )

    for entry in st.session_state.history:
      h_matches = entry.get("data", [])

      filtered_matches = []
      for card in h_matches:
        st_val = card.get("status", "⌛ Ожидание")
        if filter_status == "🟢 Выигрыши" and st_val != "✅ Проход":
          continue
        if filter_status == "🔴 Проигрыши" and st_val != "❌ Проигрыш":
          continue
        if filter_status == "⏳ В процессе" and st_val != "⌛ Ожидание":
          continue
        filtered_matches.append(card)

      if not filtered_matches:
        continue

      st.markdown(
          f"### 📅 Прогноз от {entry.get('date')} ({entry.get('ai_source', 'ИИ')})"
      )

      cols = st.columns(min(len(filtered_matches), 3))
      for idx, card in enumerate(filtered_matches):
        col_idx = idx % len(cols)
        with cols[col_idx]:
          with st.container(border=True):
            if card.get("score_changed"):
              prev_sc = card.get("prev_score", "0:0")
              curr_sc = card.get("score", "0:0")
              st.markdown(
                  f"<div class='score-badge'>🔥 СЧЕТ ИЗМЕНИЛСЯ: {prev_sc} ➔"
                  f" {curr_sc}</div>",
                  unsafe_allow_html=True,
              )

            c_l1, c_l2, c_l3 = st.columns([1, 2, 1])
            with c_l1:
              st.image(card.get("team1_logo"), width=40)
            with c_l2:
              team1_name = card.get("team1", "")
              team2_name = card.get("team2", "")
              score_val = card.get("score", "0:0")
              st.markdown(
                  f"<div style='text-align: center; font-size: 0.8rem;'>"
                  f"<b>{team1_name}</b><br><span style='color:#00FF66;"
                  f" font-size:1rem;'><b>{score_val}</b></span><br><b>{team2_name}</b></div>",
                  unsafe_allow_html=True,
              )
            with c_l3:
              st.image(card.get("team2_logo"), width=40)

            st.caption(
                f"🏆 {card.get('league')} | {card.get('time_status','Сегодня')}"
            )
            st.markdown(
                f"🎯 **Ставка:** `{card.get('bet')}` (Кф"
                f" {card.get('coefficient')})"
            )
            st.markdown(f"💡 {card.get('reason')}")

            cur_st = card.get("status", "⌛ Ожидание")
            st.write(f"Статус: **{cur_st}**")

            hc1, hc2, hc3 = st.columns(3)
            if hc1.button("🟢", key=f"hist_win_{entry['id']}_{idx}"):
              card["status"] = "✅ Проход"
              save_history(st.session_state.history)
              st.rerun()
            if hc2.button("🔴", key=f"hist_loss_{entry['id']}_{idx}"):
              card["status"] = "❌ Проигрыш"
              save_history(st.session_state.history)
              st.rerun()
            if hc3.button("⏳", key=f"hist_pend_{entry['id']}_{idx}"):
              card["status"] = "⌛ Ожидание"
              save_history(s
