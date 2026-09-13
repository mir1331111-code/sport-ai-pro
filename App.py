
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
    page_title="Auto-Sniper: Elite Sports AI", page_icon="🎯", layout="wide"
)

# Пользовательский CSS для стиля спортивного терминала
st.markdown(
    """
<style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    .element-container { margin-bottom: 0.3rem; }
    div[data-testid="stMetricValue"] { font-size: 1.25rem; color: #00FF66; font-weight: bold; }
    div[data-testid="stMetricLabel"] { font-size: 0.8rem; opacity: 0.8; }
    
    .value-badge {
        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
        color: white;
        padding: 4px 10px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.8rem;
        display: inline-block;
        margin-bottom: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    
    .score-badge {
        background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85rem;
        display: inline-block;
        margin-bottom: 8px;
        animation: pulse 2s infinite;
    }
    
    .stat-box {
        background-color: #1e293b;
        border-left: 4px solid #00FF66;
        padding: 8px 12px;
        border-radius: 4px;
        margin: 6px 0;
        font-size: 0.85rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

if "history" not in st.session_state:
  st.session_state.history = load_history()

SPORTS_ENDPOINTS = [
    ("soccer", "eng.1", "⚽ АПЛ (Англия)"),
    ("soccer", "esp.1", "⚽ Ла Лига (Испания)"),
    ("soccer", "ger.1", "⚽ Бундеслига (Германия)"),
    ("soccer", "ita.1", "⚽ Серия А (Италия)"),
    ("soccer", "rus.1", "⚽ РПЛ (Россия)"),
    ("soccer", "uefa.champions", "⚽ Лига Чемпионов"),
    ("basketball", "nba", "🏀 НБА"),
    ("hockey", "nhl", "🏒 НХЛ"),
    ("tennis", "atp", "🎾 ATP Теннис"),
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
          is_finished = state == "post"
          score_str = f"{score_home}:{score_away}"

          if is_live:
            status_str = f"🔴 LIVE {short_detail} ({score_str})"
          elif is_finished:
            status_str = f"🏁 Завершен ({score_str})"
          else:
            status_str = f"⏰ {short_detail}"

          real_matches.append({
              "sport_label": label,
              "team1": t1_name,
              "team2": t2_name,
              "team1_logo": t1_logo,
              "team2_logo": t2_logo,
              "status": status_str,
              "is_live": is_live,
              "is_finished": is_finished,
              "score": score_str,
              "state": state,
          })
    except Exception:
      pass

  real_matches.sort(key=lambda x: (not x["is_live"], x["state"] == "post"))
  return real_matches


def auto_evaluate_bet(card, score_str, is_finished):
  if not is_finished or card.get("status") != "⌛ Ожидание":
    return card.get("status", "⌛ Ожидание")

  try:
    parts = score_str.split(":")
    sh, sa = int(parts[0]), int(parts[1])
    total = sh + sa
    bet = str(card.get("bet", "")).upper()

    if "ТБ" in bet:
      val = float(re.findall(r"\d+\.?\d*", bet)[0])
      return "✅ Проход" if total > val else "❌ Проигрыш"
    elif "ТМ" in bet:
      val = float(re.findall(r"\d+\.?\d*", bet)[0])
      return "✅ Проход" if total < val else "❌ Проигрыш"
    elif bet in ["П1", "Ф1(0)", "ПОБЕДА 1"]:
      return "✅ Проход" if sh > sa else "❌ Проигрыш"
    elif bet in ["П2", "Ф2(0)", "ПОБЕДА 2"]:
      return "✅ Проход" if sa > sh else "❌ Проигрыш"
    elif bet in ["Х", "НИЧЬЯ"]:
      return "✅ Проход" if sh == sa else "❌ Проигрыш"
    elif "ОЗ" in bet or "ОБЕ ЗАБЬЮТ" in bet:
      return "✅ Проход" if (sh > 0 and sa > 0) else "❌ Проигрыш"
  except Exception:
    pass

  return "⌛ Ожидание"


def call_gemini_api(api_key, prompt_text):
  url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
  headers = {"Content-Type": "application/json"}
  payload = {
      "contents": [{"parts": [{"text": prompt_text}]}],
      "generationConfig": {
          "temperature": 0.3,
          "responseMimeType": "application/json",
      },
  }
  try:
    res = requests.post(url, json=payload, headers=headers, timeout=14)
    if res.status_code == 200:
      data = res.json()
      return data["candidates"][0]["content"]["parts"][0]["text"]
  except Exception:
    pass
  return None


# Боковая панель
st.sidebar.title("⚙️ Аналитический Движок")

ai_mode = st.sidebar.radio(
    "Выбор нейросети:",
    [
        "🧠 Только Groq AI",
        "✨ Только Gemini AI",
        "🤖🤖 Консилиум (Groq + Gemini)",
    ],
    index=0,
)

groq_api_key = st.sidebar.text_input("Ключ Groq API", type="password")
gemini_api_key = st.sidebar.text_input("Ключ Gemini API", type="password")


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
  selected_groq_model = st.sidebar.selectbox(
      "Модель Groq", models_list, index=0
  )

# Статистика
total_wins = sum(
    1
    for item in st.session_state.history
    for card in item.get("data", [])
    if card.get("status") == "✅ Проход"
)
total_losses = sum(
    1
    for item in st.session_state.history
    for card in item.get("data", [])
    if card.get("status") == "❌ Проигрыш"
)
failed_predictions = [
    f"Лига: {card.get('league')}, {card.get('team1')}-{card.get('team2')}, Ставка: {card.get('bet')}"
    for item in st.session_state.history
    for card in item.get("data", [])
    if card.get("status") == "❌ Проигрыш"
]

total_finished = total_wins + total_losses
win_rate = (total_wins / total_finished * 100) if total_finished > 0 else 0.0

st.title("🎯 Auto-Sniper: Живая Аналитика & Валуи")

s_c1, s_c2, s_c3, s_c4, s_c5 = st.columns(5)
s_c1.metric("📊 Проходимость", f"{win_rate:.1f}%")
s_c2.metric("🟢 Проход", f"{total_wins}")
s_c3.metric("🔴 Не зашло", f"{total_losses}")
s_c4.metric("🧠 Ошибок в базе", f"{len(failed_predictions)}")

if s_c5.button("🔄 Синхронизировать счета", use_container_width=True):
  with st.spinner("Сверка результатов и перерасчет ставок..."):
    live_matches = fetch_all_sports_matches()
    updated_count, settled_count = 0, 0

    for entry in st.session_state.history:
      for card in entry.get("data", []):
        t1 = card.get("team1", "").lower()
        found = next(
            (m for m in live_matches if t1 in m["team1"].lower()), None
        )
        if found:
          old_score = card.get("score", "0:0")
          if old_score != found["score"] and found["score"] != "0:0":
            card["score_changed"] = True
            card["prev_score"] = old_score
            card["score"] = found["score"]
            card["time_status"] = found["status"]
            updated_count += 1
          else:
            card["score"] = found["score"]
            card["time_status"] = found["status"]

          old_status = card.get("status", "⌛ Ожидание")
          new_status = auto_evaluate_bet(
              card, found["score"], found["is_finished"]
          )
          if old_status != new_status:
            card["status"] = new_status
            settled_count += 1

    save_history(st.session_state.history)
    st.success(
        f"Обновлено: {updated_count} счетов, автоматически рассчитано:"
        f" {settled_count} ставок!"
    )
    st.rerun()

st.markdown("---")

tab_current, tab_history = st.tabs(
    ["🔥 Глубокий Анализ Матчей", "📜 Журнал & История Исходов"]
)

with tab_current:
  today_date = datetime.date.today().strftime("%d.%m.%Y")
  current_time = datetime.datetime.now().strftime("%H:%M")

  c_input1, c_input2 = st.columns([3, 1])
  with c_input1:
    num_signals = st.slider("Количество событий для разбора:", 1, 4, 2)
  with c_input2:
    btn_search = st.button(
        f"🚀 Экспертный Сканирование", type="primary", use_container_width=True
    )

  if btn_search:
    if ai_mode == "🧠 Только Groq AI" and not groq_api_key:
      st.error("⚠️ Введите API ключ Groq!")
    elif ai_mode == "✨ Только Gemini AI" and not gemini_api_key:
      st.error("⚠️ Введите API ключ Gemini!")
    elif (
        ai_mode == "🤖🤖 Консилиум (Groq + Gemini)"
        and (not groq_api_key or not gemini_api_key)
    ):
      st.error("⚠️ Нужны оба API ключа!")
    else:
      with st.spinner(
          "Изучаем тактику, составы, статистику и сканируем коэффициенты..."
      ):
        try:
          real_matches = fetch_all_sports_matches()

          if real_matches:
            match_lines = [
                f"{idx+1}. [{rm['sport_label']}] {rm['team1']} vs {rm['team2']} | Счет: {rm['score']} | Статус: {rm['status']}"
                for idx, rm in enumerate(real_matches[:15])
            ]
            context_text = "АКТУАЛЬНЫЕ СОБЫТИЯ:\n" + "\n".join(match_lines)
          else:
            search_results = []
            with DDGS() as ddgs:
              try:
                results = ddgs.text(
                    f"главные спортивные матчи расписание {today_date}",
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
                "\n\nУЧТИ ПРОШЛЫЕ ОШИБКИ И НЕ ПОВТОРЯЙ ИХ:\n"
                + "\n".join(failed_predictions[-5:])
            )

          base_prompt = f"""
Ты — топовый спортивный аналитик и каппер с 15-летним стажем. Твоя задача — дать не сухую статистику, а ВЕЛЕКОЛЕПНЫЙ ИНФОРМАТИВНЫЙ РАЗБОР.

Дата: {today_date}, Время: {current_time} МСК.
{context_text}
{loss_context}

ТРЕБОВАНИЯ К АНАЛИЗУ:
1. Выбери {num_signals} наиболее перспективных матчей.
2. Никаких штампованных фраз вроде "команды равны". Пиши по существу!
3. Заполни структуру JSON строго по формату:

{{
  "matches": [
    {{
      "team1": "Название Команды 1",
      "team2": "Название Команды 2",
      "league": "Лига / Турнир",
      "time_status": "Время или LIVE статус",
      "score": "Текущий счет",
      "bet_type": "Тип маркета",
      "bet": "Конкретная ставка (например: ТБ 2.5, Ф1 (-1), ОЗ)",
      "coefficient": "1.85",
      "confidence_percent": 82,
      "value_tag": "🛡️ Бетон дня | 💎 Снайперский валуй | ⚡ Опасный кф",
      "x_factor": "🔥 Ключевой фактор (например: Главный бомбардир соперника травмирован, или гости играют 3-й матч за 6 дней)",
      "tactical_summary": "🧠 Тактический расклад (Как будут играть команды: автобус, высокий прессинг, доминирование на стандартах)",
      "key_stat": "📊 Главная цифра (Трендовая статистика, например: 8 из 10 последних очных встреч завершились через ТБ 2.5)",
      "reason": "Короткий итоговый вердикт (2 предложения)"
    }}
  ]
}}
"""

          raw_response = ""

          if ai_mode == "🧠 Только Groq AI":
            client = Groq(api_key=groq_api_key)
            comp = client.chat.completions.create(
                model=selected_groq_model or "llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": base_prompt}],
                temperature=0.3,
            )
            raw_response = comp.choices[0].message.content

          elif ai_mode == "✨ Только Gemini AI":
            raw_response = call_gemini_api(gemini_api_key, base_prompt)

          else:
            gemini_raw = call_gemini_api(gemini_api_key, base_prompt)
            consensus_prompt = (
                base_prompt
                + f"\n\nМнение модели Gemini:\n{gemini_raw}\nСинтезируй умный единый ответ и верни СТРОГО JSON!"
            )
            client = Groq(api_key=groq_api_key)
            comp = client.chat.completions.create(
                model=selected_groq_model or "llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": consensus_prompt}],
                temperature=0.3,
            )
            raw_response = comp.choices[0].message.content

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
              "ai_source": ai_mode,
              "data": parsed_matches,
          }
          st.session_state.history.insert(0, new_entry)
          save_history(st.session_state.history)
          st.success("Разбор готов! Изучайте аналитику ниже.")

        except Exception as e:
          st.error(f"Ошибка при составлении прогноза: {e}")

  if st.session_state.history:
    latest = st.session_state.history[0]
    matches_data = latest.get("data", [])

    st.subheader(
        f"🔥 Свежая аналитика ({latest['date']}) — {latest.get('ai_source', 'ИИ')}"
    )

    if matches_data:
      cols = st.columns(min(len(matches_data), 2))
      for idx, card in enumerate(matches_data):
        col_idx = idx % len(cols)
        with cols[col_idx]:
          with st.container(border=True):
            tag = card.get("value_tag", "💎 Снайперский выбор")
            st.markdown(
                f"<div class='value-badge'>{tag}</div>", unsafe_allow_html=True
            )

            if card.get("score_changed"):
              st.markdown(
                  f"<div class='score-badge'>🔥 СЧЕТ ИЗМЕНИЛСЯ:"
                  f" {card.get('prev_score')} ➔ {card.get('score')}</div>",
                  unsafe_allow_html=True,
              )

            t1, t2 = card.get("team1", "Команда 1"), card.get(
                "team2", "Команда 2"
            )
            c_l1, c_l2, c_l3 = st.columns([1, 2, 1])
            with c_l1:
              st.image(card.get("team1_logo"), width=48)
            with c_l2:
              st.markdown(
                  f"<div style='text-align: center; font-size:"
                  f" 0.9rem;'><b>{t1}</b><br><span style='color:#00FF66;"
                  f" font-size:1.3rem;'><b>{card.get('score','0:0')}</b></span><br><b>{t2}</b></div>",
                  unsafe_allow_html=True,
              )
            with c_l3:
              st.image(card.get("team2_logo"), width=48)

            st.caption(
                f"🏆 {card.get('league')} | {card.get('time_status','Сегодня')}"
            )
            st.markdown("---")

            m_c1, m_c2 = st.columns(2)
            with m_c1:
              st.metric(
                  f"🎯 Ставка ({card.get('bet_type','Маркет')})",
                  card.get("bet", "—"),
                  f"Кф {card.get('coefficient', '1.80')}",
              )
            with m_c2:
              conf = card.get("confidence_percent", 80)
              st.write(f"Уверенность ИИ: **{conf}%**")
              st.progress(conf / 100)

            # Вывод ключевых аналитических фишек
            if card.get("x_factor"):
              st.markdown(
                  f"<div class='stat-box'>{card.get('x_factor')}</div>",
                  unsafe_allow_html=True,
              )

            if card.get("key_stat"):
              st.caption(f"📈 **Цифра дня:** {card.get('key_stat')}")

            with st.expander("🧠 Тактический расклад и аргументы"):
              st.write(
                  f"**Тактика:** {card.get('tactical_summary', 'Анализ стиля игры.')}"
              )
              st.write(f"**Вердикт:** {card.get('reason', 'Обоснование.')}")

            st.write(f"Статус: **{card.get('status', '⌛ Ожидание')}**")

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
              save_history(st.session_state.histo
