import datetime
import json
import os
import random
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
    page_title="Auto-Sniper: Smart AI Hub", page_icon="🎯", layout="wide"
)

if "history" not in st.session_state:
  st.session_state.history = load_history()

SPORTS_ENDPOINTS = [
    ("soccer", "eng.1", "⚽ АПЛ (Англия)", "soccer"),
    ("soccer", "esp.1", "⚽ Ла Лига (Испания)", "soccer"),
    ("soccer", "ger.1", "⚽ Бундеслига (Германия)", "soccer"),
    ("soccer", "ita.1", "⚽ Серия А (Италия)", "soccer"),
    ("soccer", "rus.1", "⚽ РПЛ (Россия)", "soccer"),
    ("soccer", "uefa.champions", "⚽ Лига Чемпионов", "soccer"),
    ("basketball", "nba", "🏀 НБА", "basketball"),
    ("hockey", "nhl", "🏒 НХЛ", "hockey"),
    ("tennis", "atp", "🎾 ATP Теннис", "tennis"),
]

DEFAULT_STADIUM_BGS = {
    "soccer": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80",
    "basketball": "https://images.unsplash.com/photo-1546519638-68e109498ffc?auto=format&fit=crop&w=1920&q=80",
    "hockey": "https://images.unsplash.com/photo-1580748141549-71748dbe0bdc?auto=format&fit=crop&w=1920&q=80",
    "tennis": "https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?auto=format&fit=crop&w=1920&q=80",
    "default": "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?auto=format&fit=crop&w=1920&q=80",
}


def apply_dynamic_background(sport_type="default"):
  bg_url = DEFAULT_STADIUM_BGS.get(
      sport_type, DEFAULT_STADIUM_BGS["default"]
  )
  css_style = """
    <style>
        .stApp {
            background: linear-gradient(rgba(15, 23, 42, 0.88), rgba(15, 23, 42, 0.92)), url("__BG_URL__");
            background-size: cover;
            background-attachment: fixed;
            background-position: center;
        }
        .block-container { padding-top: 1rem; padding-bottom: 2rem; }
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
        }
        .stat-box {
            background-color: rgba(30, 41, 59, 0.7);
            border-left: 4px solid #00FF66;
            padding: 8px 12px;
            border-radius: 4px;
            margin: 6px 0;
            font-size: 0.85rem;
        }
    </style>
    """.replace("__BG_URL__", bg_url)
  st.markdown(css_style, unsafe_allow_html=True)


def determine_match_phase(status_str, state_str):
  s = status_str.lower()
  if state_str == "pre":
    return "до перерыва"
  if any(
      x in s
      for x in [
          "2nd",
          "3rd",
          "4th",
          "2-й",
          "3-й",
          "4-й",
          "post",
          "завершен",
          "ot",
          "овертайм",
      ]
  ):
    return "после перерыва"
  return "до перерыва"


def fetch_all_sports_matches():
  today_str = datetime.date.today().strftime("%Y%m%d")
  raw_matches = []

  for sport, league, label, sport_cat in SPORTS_ENDPOINTS:
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

          phase = determine_match_phase(status_str, state)

          raw_matches.append({
              "sport_label": label,
              "sport_category": sport_cat,
              "team1": t1_name,
              "team2": t2_name,
              "team1_logo": t1_logo,
              "team2_logo": t2_logo,
              "status": status_str,
              "is_live": is_live,
              "is_finished": is_finished,
              "score": score_str,
              "state": state,
              "game_phase": phase,
          })
    except Exception:
      pass

  categorized = {}
  for m in raw_matches:
    cat = m["sport_category"]
    categorized.setdefault(cat, []).append(m)

  balanced_list = []
  for cat, m_list in categorized.items():
    m_list.sort(key=lambda x: (not x["is_live"], x["state"] == "post"))
    balanced_list.extend(m_list[:4])

  random.shuffle(balanced_list)
  return balanced_list


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
          "temperature": 0.25,
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


initial_bg_cat = "default"
if st.session_state.history and st.session_state.history[0].get("data"):
  initial_bg_cat = st.session_state.history[0]["data"][0].get(
      "sport_category", "default"
  )
apply_dynamic_background(initial_bg_cat)

st.sidebar.title("⚙️ Настройки ИИ")
ai_mode = st.sidebar.radio(
    "Режим анализа:",
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

total_wins, total_losses = 0, 0
failed_predictions = []

for item in st.session_state.history:
  for card in item.get("data", []):
    st_val = card.get("status", "⌛ Ожидание")
    if st_val == "✅ Проход":
      total_wins += 1
    elif st_val == "❌ Проигрыш":
      total_losses += 1
      failed_predictions.append(
          f"Лига: {card.get('league')}, Игра: {card.get('team1')} vs"
          f" {card.get('team2')}, Ставка: {card.get('bet')}, Обоснование:"
          f" {card.get('reason')}"
      )

total_finished = total_wins + total_losses
win_rate = (total_wins / total_finished * 100) if total_finished > 0 else 0.0

st.title("🎯 Auto-Sniper: Мультиспортивный Сканер")

s_c1, s_c2, s_c3, s_c4, s_c5 = st.columns(5)
s_c1.metric("📊 Win Rate", f"{win_rate:.1f}%")
s_c2.metric("🟢 Победы", f"{total_wins}")
s_c3.metric("🔴 Поражения", f"{total_losses}")
s_c4.metric("🧠 Ошибок в базе", f"{len(failed_predictions)}")

if s_c5.button("🔄 Синхронизировать счета", use_container_width=True):
  with st.spinner("Проверяем счета..."):
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
            card["game_phase"] = found["game_phase"]
            updated_count += 1
          else:
            card["score"] = found["score"]
            card["time_status"] = found["status"]
            card["game_phase"] = found["game_phase"]

          old_status = card.get("status", "⌛ Ожидание")
          new_status = auto_evaluate_bet(
              card, found["score"], found["is_finished"]
          )
          if old_status != new_status:
            card["status"] = new_status
            settled_count += 1

    save_history(st.session_state.history)
    st.success(
        f"Счета обновлены: {updated_count} | Рассчитано ставок: {settled_count}"
    )
    st.rerun()

st.markdown("---")

tab_current, tab_history = st.tabs(
    ["🔥 Глубокий Анализ Матчей", "📜 История & Обучение"]
)

with tab_current:
  today_date = datetime.date.today().strftime("%d.%m.%Y")
  current_time = datetime.datetime.now().strftime("%H:%M")

  c_input1, c_input2 = st.columns([3, 1])
  with c_input1:
    num_signals = st.slider("Количество событий для разбора:", 1, 4, 2)
  with c_input2:
    btn_search = st.button(
        "🚀 Сканировать Линию", type="primary", use_container_width=True
    )

  if btn_search:
    if ai_mode == "🧠 Только Groq AI" and not groq_api_key:
      st.error("⚠️ Укажите API ключ Groq!")
    elif ai_mode == "✨ Только Gemini AI" and not gemini_api_key:
      st.error("⚠️ Укажите API ключ Gemini!")
    elif (
        ai_mode == "🤖🤖 Консилиум (Groq + Gemini)"
        and (not groq_api_key or not gemini_api_key)
    ):
      st.error("⚠️ Укажите оба ключа!")
    else:
      with st.spinner(
          "Фильтруем повторы, проверяем фазы матчей и формируем разбор..."
      ):
        try:
          real_matches = fetch_all_sports_matches()

          analyzed_phases = set()
          for item in st.session_state.history:
            for card in item.get("data", []):
              t1 = card.get("team1", "").lower().strip()
              t2 = card.get("team2", "").lower().strip()
              phase = card.get("game_phase", "до перерыва")
              analyzed_phases.add((f"{t1}_vs_{t2}", phase))

          filtered_matches = []
          seen_in_batch = set()

          for rm in real_matches:
            t1_k = rm["team1"].lower().strip()
            t2_k = rm["team2"].lower().strip()
            pair_key = f"{t1_k}_vs_{t2_k}"
            phase = rm["game_phase"]

            if (
                pair_key not in seen_in_batch
                and (pair_key, phase) not in analyzed_phases
            ):
              seen_in_batch.add(pair_key)
              filtered_matches.append(rm)

          if filtered_matches:
            match_lines = [
                f"{idx+1}. [{rm['sport_label']}] {rm['team1']} VS {rm['team2']} | Счет: {rm['score']} | Фаза: {rm['game_phase']} | Статус: {rm['status']}"
                for idx, rm in enumerate(filtered_matches[:12])
            ]
            context_text = "НОВЫЕ СОБЫТИЯ ДЛЯ АНАЛИЗА:\n" + "\n".join(
                match_lines
            )
          else:
            search_results = []
            with DDGS() as ddgs:
              try:
                results = ddgs.text(
                    f"главные спортивные матчи баскетбол хоккей футбол"
                    f" {today_date}",
                    region="ru-ru",
                    max_results=6,
                )
                for r in results:
                  search_results.append(r.get("body", ""))
              except Exception:
                pass
            context_text = "\n".join(search_results)

          loss_context = ""
          if failed_predictions:
            loss_context = (
                "\n\n🚨 БЛОК САМООБУЧЕНИЯ (ПРОШЛЫЕ ОШИБКИ ИИ):\n"
                "Учти причины прошлых неудач и не повторяй аналогичных"
                " ошибок:\n" + "\n".join(failed_predictions[-5:])
            )

          base_prompt = f"""
Сегодня {today_date}, время {current_time} МСК.

{context_text}
{loss_context}

ИНСТРУКЦИЯ ПО ВЫБОРУ:
1. Выбери {num_signals} самых надежных матча из предложенного списка. 
2. ОБЯЗАТЕЛЬНО бери разборчивые события из разных видов спорта, если они доступны.
3. Соблюдай баланс рисков.

Верни СТРОГО JSON следующего формата:
{{
  "matches": [
    {{
      "team1": "Название Команды 1",
      "team2": "Название Команды 2",
      "league": "Вид спорта / Лига",
      "time_status": "Время или Статус LIVE",
      "game_phase": "до перерыва OR после перерыва",
      "score": "Текущий счет",
      "bet_type": "Тип маркета",
      "bet": "Ставка (например: ТБ 2.5, П1, ОЗ, Ф2 (+4.5))",
      "coefficient": "1.85",
      "confidence_percent": 85,
      "value_tag": "🛡️ Бетон дня | 💎 Снайперский валуй | ⚡ Опасный кф",
      "x_factor": "🔥 Ключевой фактор или инсайд",
      "tactical_summary": "🧠 Разбор формы и стиля команд",
      "key_stat": "📊 Главная статистическая цифра",
      "reason": "Единое экспертное обоснование ИИ"
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
                temperature=0.25,
            )
            raw_response = comp.choices[0].message.content

          elif ai_mode == "✨ Только Gemini AI":
            raw_response = call_gemini_api(gemini_api_key, base_prompt)

          else:
            gemini_raw = call_gemini_api(gemini_api_key, base_prompt)
            consensus_prompt = (
                base_prompt
                + f"\n\nМнение Gemini:\n{gemini_raw}\nСинтезируй общее финальное решение в формате JSON!"
            )
            client = Groq(api_key=groq_api_key)
            comp = client.chat.completions.create(
                model=selected_groq_model or "llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": consensus_prompt}],
                temperature=0.25,
            )
            raw_response = comp.choices[0].message.content

          cleaned = re.sub(
              r"<think>.*?</think>", "", raw_response, flags=re.DOTALL
          ).strip()
          json_start = cleaned.find("{")
          json_end = cleaned.rfind("}") + 1
          parsed_json = json.loads(cleaned[json_start:json_end])

          parsed_matches = parsed_json.get("matches", [])
          first_sport_cat = "default"

          for idx_pm, pm in enumerate(parsed_matches):
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
              pm["sport_category"] = match_found["sport_category"]
              pm["time_status"] = match_found["status"]
              pm["score"] = match_found["score"]
              pm["game_phase"] = match_found["game_phase"]
            else:
              pm["team1_logo"] = (
                  f"https://ui-avatars.com/api/?name={t1}&background=1e293b&color=00ff66"
              )
              pm["team2_logo"] = (
                  f"https://ui-avatars.com/api/?name={pm.get('team2','')}&background=1e293b&color=00bfff"
              )
              pm["score"] = pm.get("score", "0:0")
              pm["sport_category"] = "default"
              pm["game_phase"] = pm.get("game_phase", "до перерыва")

            if idx_pm == 0:
              first_sport_cat = pm.get("sport_category", "default")

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

          apply_dynamic_background(first_sport_cat)
          st.success("Новый уникальный разбор сформирован без дубликатов!")

        except Exception as e:
          st.error(f"Ошибка генерации: {e}")

  if st.session_state.history:
    latest = st.session_state.history[0]
    matches_data = latest.get("data", [])

    
