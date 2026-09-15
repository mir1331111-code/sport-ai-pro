import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Pro Betting AI", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.stApp { background: linear-gradient(rgba(10,15,25,0.95), rgba(10,15,25,0.98)); }
.main-header { font-size: 2.5rem; font-weight: 700; background: linear-gradient(90deg, #38bdf8, #10b981); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 1rem; }
.forecast-card { background: rgba(30,41,59,0.75); padding: 18px; border-radius: 12px; border: 1px solid rgba(56,189,248,0.2); margin-bottom: 12px; }
.ev-positive { color: #10b981; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

HISTORY_FILE = "betting_v3.json"
LEAGUE_CODES = {
    "🏴󠁢󠁧 Англия (АПЛ)": "E0.csv",
    "🇸 Испания": "SP1.csv",
    "🇮🇹 Италия": "I1.csv",
    "🇪 Германия": "D1.csv",
    "🇫🇷 Франция": "F1.csv",
    "🇷🇺 Россия": "R1.csv",
    "🇷 Турция": "T1.csv"
}

class EloModel:
    def __init__(self):
        self.ratings = {}
    
    def update(self, t1, t2, s1, s2, k=32):
        r1 = self.ratings.get(t1, 1500)
        r2 = self.ratings.get(t2, 1500)
        e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        self.ratings[t1] = r1 + k * (s1 - e1)
        self.ratings[t2] = r2 + k * (s2 - (1-e1))
    
    def predict(self, t1, t2):
        r1 = self.ratings.get(t1, 1500)
        r2 = self.ratings.get(t2, 1500)
        p1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        p2 = 1 / (1 + 10 ** ((r1 - r2) / 400))
        pd_raw = 0.25 * (1 - abs(p1 - p2))
        total = p1 + p2 + pd_raw
        return p1/total, pd_raw/total, p2/total

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"bank": 10000.0, "bets": [], "kelly_frac": 0.25, "stats": {"total": 0, "won": 0, "lost": 0, "profit": 0.0}, "forecasts": []}

def save_history(data):
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

if "app_data" not in st.session_state:
    st.session_state.app_data = load_history()

st.markdown('<div class="main-header">🎯 Pro Betting AI</div>', unsafe_allow_html=True)

st.sidebar.header("️ Настройки")
st.sidebar.metric(" Банк", f"{st.session_state.app_data['bank']:.2f} у.е.")
kelly_frac = st.sidebar.slider("Дробь Келли", 0.1, 0.5, st.session_state.app_data.get("kelly_frac", 0.25), 0.05)
st.session_state.app_data["kelly_frac"] = kelly_frac
min_ev = st.sidebar.slider("Мин EV %", 1, 10, 3) / 100

if st.sidebar.button("🔄 Сброс"):
    st.session_state.app_data = {"bank": 10000.0, "bets": [], "kelly_frac": 0.25, "stats": {"total": 0, "won": 0, "lost": 0, "profit": 0.0}, "forecasts": []}
    save_history(st.session_state.app_data)
    st.rerun()

tab1, tab2 = st.tabs(["🎯 Прогнозы", " Ставки"])

with tab1:
    st.markdown("### 🔍 Анализ матчей")
    
    leagues = st.multiselect("Лиги:", list(LEAGUE_CODES.keys()), default=["🏴󠁢󠁧 Англия (АПЛ)"])
    days = st.slider("Дней вперед", 1, 30, 7)
    show_all = st.checkbox("📊 Показать все матчи (включая прошедшие)", value=False, help="Включите для отладки")
    
    if st.button("🚀 Анализ", type="primary"):
        if not leagues:
            st.warning("Выберите лиги")
        else:
            with st.spinner("Загрузка данных..."):
                base = "https://www.football-data.co.uk/mmz4281/2526/"
                all_df = []
                for league in leagues:
                    if league in LEAGUE_CODES:
                        try:
                            df = pd.read_csv(base + LEAGUE_CODES[league])
                            df['League'] = league
                            all_df.append(df)
                            st.success(f"✅ {league}: {len(df)} матчей")
                        except Exception as e:
                            st.error(f"❌ {league}: {str(e)[:100]}")
                
                if not all_df:
                    st.stop()
                
                df = pd.concat(all_df, ignore_index=True)
                st.info(f"📊 Всего загружено: {len(df)} матчей")
                
                # Показываем доступные даты
                if 'Date' in df.columns:
                    st.write(f"**Даты в данных:** {df['Date'].min()} - {df['Date'].max()}")
                    st.write(f"**Матчей без результата:** {df['FTHG'].isna().sum() if 'FTHG' in df.columns else 'N/A'}")
                
                # Парсинг дат
                if 'Date' in df.columns:
                    df['MatchDate'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
                    valid_dates = df['MatchDate'].dropna()
                    if len(valid_dates) > 0:
                        st.write(f"**Диапазон дат:** {valid_dates.min().strftime('%d.%m.%Y')} - {valid_dates.max().strftime('%d.%m.%Y')}")
                
                today = pd.Timestamp.now().normalize()
                future_limit = today + pd.Timedelta(days=days)
                
                # Фильтрация матчей
                if 'MatchDate' in df.columns:
                    if show_all:
                        # Показываем все матчи для отладки
                        matches_to_analyze = df[df['MatchDate'].notna()].copy()
                        st.warning(f"🔍 Режим отладки: анализируем {len(matches_to_analyze)} матчей (все)")
                    else:
                        # Только будущие матчи без результата
                        matches_to_analyze = df[
                            (df['MatchDate'] >= today) & 
                            (df['MatchDate'] <= future_limit) &
                            (df['FTHG'].isna() if 'FTHG' in df.columns else True)
                        ].copy()
                        st.info(f"📅 Найдено {len(matches_to_analyze)} будущих матчей на {days} дней")
                else:
                    matches_to_analyze = df.copy()
                    st.warning("️ Колонка Date не найдена, анализируем все матчи")
                
                if len(matches_to_analyze) == 0:
                    st.error("❌ Нет матчей для анализа! Попробуйте:")
                    st.write("1. Увеличить период (ползунок выше)")
                    st.write("2. Включить чекбокс 'Показать все матчи'")
                    st.write("3. Выбрать другие лиги")
                    st.stop()
                
                # Обучение модели
                with st.spinner("Обучение модели..."):
                    elo = EloModel()
                    past_matches = df[df['FTHG'].notna()] if 'FTHG' in df.columns else pd.DataFrame()
                    
                    for _, row in past_matches.iterrows():
                        h = row.get('HomeTeam', '')
                        a = row.get('AwayTeam', '')
                        if h and a:
                            hg = float(row.get('FTHG', 0))
                            ag = float(row.get('FTAG', 0))
                            s1 = 1 if hg > ag else (0.5 if hg == ag else 0)
                            s2 = 1 - s1
                            elo.update(h, a, s1, s2)
                    
                    st.success(f"✅ Обучено на {len(past_matches)} матчах")
                
                # Генерация прогнозов
                with st.spinner("Генерация прогнозов..."):
                    forecasts = []
                    bank = st.session_state.app_data["bank"]
                    analyzed_count = 0
                    
                    for idx, row in matches_to_analyze.iterrows():
                        h = row.get('HomeTeam', '')
                        a = row.get('AwayTeam', '')
                        
                        if not h or not a or pd.isna(h) or pd.isna(a):
                            continue
                        
                        try:
                            analyzed_count += 1
                            
                            # Вероятности Elo
                            p1, px, p2 = elo.predict(h, a)
                            
                            # Пуассон на основе формы
                            h_matches = past_matches[(past_matches['HomeTeam']==h) | (past_matches['AwayTeam']==h)].tail(5)
                            a_matches = past_matches[(past_matches['HomeTeam']==a) | (past_matches['AwayTeam']==a)].tail(5)
                            
                            h_goals = h_matches['FTHG' if h_matches['HomeTeam']==h else 'FTAG'].mean() if len(h_matches) > 0 else 1.2
                            a_goals = a_matches['FTAG' if a_matches['HomeTeam']==a else 'FTHG'].mean() if len(a_matches) > 0 else 1.0
                            
                            lam_h = max(0.5, h_goals)
                            lam_a = max(0.5, a_goals)
                            
                            # Матрица Пуассона
                            matrix = np.zeros((6,6))
                            for i in range(6):
                                for j in range(6):
                                    matrix[i,j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
                            
                            pp1 = np.sum(np.tril(matrix, -1))
                            ppx = np.sum(np.diag(matrix))
                            pp2 = np.sum(np.triu(matrix, 1))
                            total = pp1 + ppx + pp2
                            if total > 0:
                                pp1 /= total
                                ppx /= total
                                pp2 /= total
                            
                            # Ансамбль
                            ph = 0.4*p1 + 0.6*pp1
                            px_final = 0.4*px + 0.6*ppx
                            pa = 0.4*p2 + 0.6*pp2
                            
                            # Коэффициенты
                            odds_h = float(row.get('B365H', row.get('PSH', 1.95)))
                            odds_x = float(row.get('B365D', row.get('PSD', 3.40)))
                            odds_a = float(row.get('B365A', row.get('PSA', 3.10)))
                            
                            opts = [("П1", ph, odds_h), ("X", px_final, odds_x), ("П2", pa, odds_a)]
                            pick, prob, odd = max(opts, key=lambda x: x[1]*x[2])
                            
                            ev = (prob * odd) - 1.0
                            
                            # Расчет ставки
                            if ev > min_ev:
                                b = odd - 1
                                kelly = (b * prob - (1 - prob)) / b
                                stake = max(0, kelly * kelly_frac) * bank
                                stake = min(stake, bank * 0.05)
                                
                                if stake > 1:
                                    match_date = row.get('MatchDate', today)
                                    date_str = match_date.strftime('%d.%m') if pd.notna(match_date) else 'N/A'
                                    
                                    forecasts.append({
                                        "league": row.get('League',''),
                                        "match": f"{h} vs {a}",
                                        "date": date_str,
                                        "pick": pick,
                                        "prob": prob,
                                        "odds": odd,
                                        "ev": ev,
                                        "stake": round(stake, 2),
                                        "p1": ph,
                                        "px": px_final,
                                        "p2": pa
                                    })
                        except Exception as e:
                            continue
                    
                    st.session_state.app_data["forecasts"] = forecasts
                    save_history(st.session_state.app_data)
                    
                    st.success(f"✅ Проанализировано: {analyzed_count} матчей")
                    st.success(f"🎯 Найдено {len(forecasts)} ставок с EV > {min_ev*100:.0f}%")
                    
                    if len(forecasts) == 0:
                        st.info("💡 Совет: уменьшите 'Мин EV %' в боковой панели до 1-2%")
                    
                    st.rerun()
    
    # Показ прогнозов
    forecasts = st.session_state.app_data.get("forecasts", [])
    
    if forecasts:
        st.markdown(f"### 📊 Найдено {len(forecasts)} выгодных ставок")
        
        for f in forecasts:
            st.markdown(f"""
                <div class="forecast-card">
                    <div style="display:flex;justify-content:space-between;margin-bottom:10px">
                        <span style="background:#38bdf8;padding:4px 10px;border-radius:6px;font-size:0.8rem;color:white;font-weight:700">{f['league']}</span>
                        <span style="color:#94a3b8">{f['date']}</span>
                    </div>
                    <div style="font-size:1.2rem;font-weight:700;color:#f8fafc;margin-bottom:8px">⚽ {f['match']}</div>
                    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:10px">
                        <div><div style="color:#94a3b8;font-size:0.75rem">Прогноз</div><div style="color:#facc15;font-weight:700;font-size:1.1rem">{f['pick']}</div></div>
                        <div><div style="color:#94a3b8;font-size:0.75rem">Вероятность</div><div style="color:#4ade80;font-weight:700;font-size:1.1rem">{f['prob']*100:.1f}%</div></div>
                        <div><div style="color:#94a3b8;font-size:0.75rem">Коэффициент</div><div style="color:#facc15;font-weight:700;font-size:1.1rem">{f['odds']:.2f}</div></div>
                        <div><div style="color:#94a3b8;font-size:0.75rem">EV (перевес)</div><div class="ev-positive" style="font-size:1.1rem">{f['ev']*100:.1f}%</div></div>
                    </div>
                    <div style="border-top:1px solid rgba(255,255,255,0.1);padding-top:10px;display:flex;justify-content:space-between;align-items:center">
                        <div>
                            <span style="color:#94a3b8;font-size:0.85rem">Рекомендуемая ставка:</span>
                            <span style="color:#facc15;font-weight:700;font-size:1.1rem;margin-left:8px">{f['stake']:.2f} у.е.</span>
                        </div>
                        <div style="color:#64748b;font-size:0.75rem">
                            Вероятности: П1={f['p1']*100:.0f}% X={f['px']*100:.0f}% П2={f['p2']*100:.0f}%
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("👆 Выберите лиги и нажмите «Анализ»")

with tab2:
    st.markdown("### 📋 Активные ставки")
    bets = st.session_state.app_data.get("bets", [])
    
    if not bets:
        st.info("Нет активных ставок")
    else:
        pending = [b for b in bets if b.get("status") == "pending"]
        for i, bet in enumerate(pending):
            cols = st.columns(2)
            with cols[0]:
                if st.button(f"✅ {bet.get('match','')[:30]}", key=f"w{i}"):
                    bet["status"] = "won"
                    profit = bet.get("stake",0) * bet.get("odds",0)
                    st.session_state.app_data["bank"] += profit
                    st.session_state.app_data["stats"]["won"] += 1
                    st.session_state.app_data["stats"]["profit"] += profit - bet.get("stake",0)
                    save_history(st.session_state.app_data)
                    st.success(f"+{profit:.2f} у.е.")
                    st.rerun()
            with cols[1]:
                if st.button(f"❌ {bet.get('match','')[:30]}", key=f"l{i}"):
                    bet["status"] = "lost"
                    st.session_state.app_data["stats"]["lost"] += 1
                    st.session_state.app_data["stats"]["profit"] -= bet.get("stake",0)
                    save_history(st.session_state.app_data)
                    st.error(f"-{bet.get('stake',0):.2f} у.е.")
                    st.rerun()
