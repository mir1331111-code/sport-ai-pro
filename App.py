import streamlit as st
import csv
import io
import requests
import json
import os
from datetime import datetime, timedelta
from scipy.stats import poisson
import numpy as np

st.set_page_config(page_title="Betting AI", page_icon="🎯", layout="wide")

HISTORY_FILE = "data.json"

def load_data():
    if os.path.exists(HISTORY_FILE):
        try:
            return json.load(open(HISTORY_FILE, "r"))
        except:
            pass
    return {"bank": 10000.0, "bets": [], "forecasts": []}

def save_data(data):
    json.dump(data, open(HISTORY_FILE, "w"), indent=4)

def load_csv_from_url(url):
    """Загрузка CSV без pandas"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        text = response.text
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)
    except Exception as e:
        return []

def parse_date(date_str):
    """Парсинг даты в формате DD/MM/YY"""
    try:
        return datetime.strptime(date_str, "%d/%m/%y")
    except:
        return None

def calculate_form(data, team, n=5):
    """Расчет формы команды"""
    matches = []
    for row in data:
        if row.get('HomeTeam') == team or row.get('AwayTeam') == team:
            if row.get('FTHG') and row.get('FTAG'):
                matches.append(row)
                if len(matches) >= n:
                    break
    
    if not matches:
        return 0.5, 1.0, 1.0
    
    points = 0
    goals_for = 0
    goals_against = 0
    
    for m in matches:
        is_home = m['HomeTeam'] == team
        gf = float(m['FTHG']) if is_home else float(m['FTAG'])
        ga = float(m['FTAG']) if is_home else float(m['FTHG'])
        goals_for += gf
        goals_against += ga
        
        if gf > ga:
            points += 3
        elif gf == ga:
            points += 1
    
    form = points / (len(matches) * 3)
    return form, goals_for/len(matches), goals_against/len(matches)

if "data" not in st.session_state:
    st.session_state.data = load_data()

st.title(" Pro Betting AI")

bank = st.session_state.data["bank"]
st.sidebar.metric("💰 Банк", f"{bank:.2f} у.е.")

kelly_frac = st.sidebar.slider("Келли", 0.1, 0.5, 0.25, 0.05)
min_ev = st.sidebar.slider("Мин EV %", 1, 10, 3) / 100

if st.sidebar.button("🔄 Сброс"):
    st.session_state.data = {"bank": 10000.0, "bets": [], "forecasts": []}
    save_data(st.session_state.data)
    st.rerun()

tab1, tab2 = st.tabs(["🎯 Прогнозы", "📋 Ставки"])

with tab1:
    st.header("Анализ матчей")
    
    leagues = {
        "🏴󠁧󠁢󠁥󠁧󠁿 Англия": "E0",
        "🇪🇸 Испания": "SP1",
        "🇮🇹 Италия": "I1",
        "🇩🇪 Германия": "D1",
        "🇫🇷 Франция": "F1",
        "🇷🇺 Россия": "R1",
        "🇹🇷 Турция": "T1"
    }
    
    selected_league = st.selectbox("Лига", list(leagues.keys()))
    days = st.slider("Дней вперед", 1, 14, 7)
    
    if st.button("🚀 Анализ", type="primary"):
        code = leagues[selected_league]
        url = f"https://www.football-data.co.uk/mmz4281/2526/{code}.csv"
        
        with st.spinner("Загрузка данных..."):
            data = load_csv_from_url(url)
            
            if not data:
                st.error("Не удалось загрузить данные")
                st.stop()
            
            st.success(f"✅ Загружено {len(data)} матчей")
        
        with st.spinner("Анализ..."):
            today = datetime.now().normalize() if hasattr(datetime, 'normalize') else datetime.now()
            limit = today + timedelta(days=days)
            
            # Elo рейтинги
            elo = {}
            for row in data:
                if row.get('FTHG') and row.get('FTAG'):
                    h, a = row.get('HomeTeam',''), row.get('AwayTeam','')
                    hg, ag = float(row['FTHG']), float(row['FTAG'])
                    
                    if h not in elo: elo[h] = 1500
                    if a not in elo: elo[a] = 1500
                    
                    r1, r2 = elo[h], elo[a]
                    e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
                    s1 = 1 if hg > ag else (0.5 if hg == ag else 0)
                    
                    elo[h] = r1 + 32 * (s1 - e1)
                    elo[a] = r2 + 32 * ((1-s1) - (1-e1))
            
            # Прогнозы
            forecasts = []
            for row in data:
                home = row.get('HomeTeam', '')
                away = row.get('AwayTeam', '')
                
                if not home or not away:
                    continue
                
                # Проверка даты
                if 'Date' in row:
                    match_date = parse_date(row['Date'])
                    if match_date and (match_date < today or match_date > limit):
                        continue
                
                # Пропускаем сыгранные
                if row.get('FTHG'):
                    continue
                
                # Вероятности Elo
                r1 = elo.get(home, 1500)
                r2 = elo.get(away, 1500)
                p_home = 1 / (1 + 10 ** ((r2 - r1) / 400))
                p_away = 1 / (1 + 10 ** ((r1 - r2) / 400))
                p_draw = 0.25 * (1 - abs(p_home - p_away))
                
                total = p_home + p_draw + p_away
                p_home /= total
                p_draw /= total
                p_away /= total
                
                # Пуассон
                form_h, gf_h, _ = calculate_form(data, home, 5)
                form_a, gf_a, _ = calculate_form(data, away, 5)
                
                lam_h = max(0.5, gf_h * 1.1)
                lam_a = max(0.5, gf_a * 0.9)
                
                matrix = np.zeros((6,6))
                for i in range(6):
                    for j in range(6):
                        matrix[i,j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
                
                pp_home = np.sum(np.tril(matrix, -1))
                pp_draw = np.sum(np.diag(matrix))
                pp_away = np.sum(np.triu(matrix, 1))
                
                total = pp_home + pp_draw + pp_away
                if total > 0:
                    pp_home /= total
                    pp_draw /= total
                    pp_away /= total
                
                # Ансамбль
                ph = 0.4*p_home + 0.6*pp_home
                px = 0.4*p_draw + 0.6*pp_draw
                pa = 0.4*p_away + 0.6*pp_away
                
                # Коэффициенты
                try:
                    odds_h = float(row.get('B365H', row.get('PSH', '1.95')))
                    odds_x = float(row.get('B365D', row.get('PSD', '3.40')))
                    odds_a = float(row.get('B365A', row.get('PSA', '3.10')))
                except:
                    odds_h, odds_x, odds_a = 1.95, 3.40, 3.10
                
                options = [("П1", ph, odds_h), ("X", px, odds_x), ("П2", pa, odds_a)]
                pick, prob, odd = max(options, key=lambda x: x[1]*x[2])
                
                ev = (prob * odd) - 1.0
                
                if ev > min_ev:
                    b = odd - 1
                    kelly = max(0, (b * prob - (1-prob)) / b) * kelly_frac
                    stake = round(min(kelly * bank, bank * 0.05), 2)
                    
                    if stake > 0:
                        forecasts.append({
                            "match": f"{home} vs {away}",
                            "pick": pick,
                            "odds": odd,
                            "prob": prob,
                            "ev": ev,
                            "stake": stake
                        })
            
            st.session_state.data["forecasts"] = forecasts
            save_data(st.session_state.data)
            st.success(f"✅ Найдено {len(forecasts)} ставок с +EV")
            st.rerun()
    
    forecasts = st.session_state.data.get("forecasts", [])
    if forecasts:
        st.subheader(f" {len(forecasts)} выгодных ставок")
        for f in forecasts:
            st.markdown(f"""
            <div style="background:rgba(30,41,59,0.75);padding:15px;border-radius:10px;margin-bottom:10px;border-left:4px solid #38bdf8">
                <div style="font-size:1.1rem;font-weight:700;color:#f8fafc;margin-bottom:8px">⚽ {f['match']}</div>
                <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
                    <div><span style="color:#94a3b8">Прогноз:</span> <b style="color:#facc15">{f['pick']}</b></div>
                    <div><span style="color:#94a3b8">Вероятность:</span> <b style="color:#4ade80">{f['prob']*100:.1f}%</b></div>
                    <div><span style="color:#94a3b8">Коэф:</span> <b style="color:#facc15">{f['odds']:.2f}</b></div>
                    <div><span style="color:#94a3b8">EV:</span> <b style="color:{'#10b981' if f['ev']>0 else '#ef4444'}">{f['ev']*100:.1f}%</b></div>
                </div>
                <div style="margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.1)">
                    <span style="color:#94a3b8">Ставка (Келли):</span> <b style="color:#facc15;font-size:1.1rem">{f['stake']:.2f} у.е.</b>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Выберите лигу и нажмите «Анализ»")

with tab2:
    st.header("📋 Активные ставки")
    bets = st.session_state.data.get("bets", [])
    
    if not bets:
        st.info("Нет активных ставок")
    else:
        pending = [b for b in bets if b.get("status") == "pending"]
        for i, bet in enumerate(pending):
            st.markdown(f"""
            <div style="background:rgba(30,41,59,0.75);padding:15px;border-radius:10px;margin-bottom:10px;border-left:4px solid #f59e0b">
                <div style="font-size:1.1rem;font-weight:700;color:#f8fafc">⚽ {bet.get('match','')}</div>
                <div style="color:#94a3b8;margin:5px 0">{bet.get('pick','')} @ {bet.get('odds',0):.2f} | Ставка: {bet.get('stake',0):.2f} у.е.</div>
                <div style="margin-top:10px;display:flex;gap:10px">
                    <button onclick="alert('win')" style="background:#10b981;color:white;border:none;padding:8px 16px;border-radius:6px;cursor:pointer">✅ Выиграла</button>
                    <button onclick="alert('loss')" style="background:#ef4444;color:white;border:none;padding:8px 16px;border-radius:6px;cursor:pointer">❌ Проиграла</button>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            cols = st.columns(2)
            with cols[0]:
                if st.button(f"✅ #{i}", key=f"w{i}"):
                    bet["status"] = "won"
                    profit = bet.get("stake", 0) * bet.get("odds", 0)
                    st.session_state.data["bank"] += profit
                    st.session_state.data["bets"] = bets
                    save_data(st.session_state.data)
                    st.success(f"+{profit:.2f} у.е.")
                    st.rerun()
            with cols[1]:
                if st.button(f"❌ #{i}", key=f"l{i}"):
                    bet["status"] = "lost"
                    st.session_state.data["bets"] = bets
                    save_data(st.session_state.data)
                    st.error(f"-{bet.get('stake',0):.2f} у.е.")
                    st.rerun()
