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
.debug-card { background: rgba(239,68,68,0.1); padding: 12px; border-radius: 8px; border-left: 4px solid #ef4444; margin-bottom: 8px; }
.ev-positive { color: #10b981; font-weight: 700; }
.ev-negative { color: #ef4444; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

HISTORY_FILE = "betting_v3.json"
LEAGUE_CODES = {
    "🏴󠁢󠁧 Англия (АПЛ)": "E0.csv",
    "🇪🇸 Испания": "SP1.csv",
    "🇮🇹 Италия": "I1.csv",
    "🇪 Германия": "D1.csv",
    "🇫🇷 Франция": "F1.csv"
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

st.sidebar.header("⚙️ Настройки")
st.sidebar.metric("💰 Банк", f"{st.session_state.app_data['bank']:.2f} у.е.")
kelly_frac = st.sidebar.slider("Дробь Келли", 0.1, 0.5, st.session_state.app_data.get("kelly_frac", 0.25), 0.05)
st.session_state.app_data["kelly_frac"] = kelly_frac
min_ev = st.sidebar.slider("Мин EV %", 0, 10, 0) / 100  # По умолчанию 0%!
debug_mode = st.sidebar.checkbox(" Режим отладки", value=True)

if st.sidebar.button("🔄 Сброс"):
    st.session_state.app_data = {"bank": 10000.0, "bets": [], "kelly_frac": 0.25, "stats": {"total": 0, "won": 0, "lost": 0, "profit": 0.0}, "forecasts": []}
    save_history(st.session_state.app_data)
    st.rerun()

tab1, tab2 = st.tabs(["🎯 Прогнозы", "📋 Ставки"])

with tab1:
    st.markdown("### 🔍 Анализ матчей")
    
    leagues = st.multiselect("Лиги:", list(LEAGUE_CODES.keys()), default=["🏴󠁢 Англия (АПЛ)"])
    days = st.slider("Дней вперед", 1, 30, 7)
    
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
                        except Exception as e:
                            st.error(f"❌ {league}: {str(e)[:100]}")
                
                if not all_df:
                    st.stop()
                
                df = pd.concat(all_df, ignore_index=True)
                st.success(f"✅ Загружено {len(df)} матчей")
                
                # Парсинг дат
                if 'Date' in df.columns:
                    df['MatchDate'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
                    today = pd.Timestamp.now().normalize()
                    future_limit = today + pd.Timedelta(days=days)
                    
                    # Показываем статистику
                    st.write(f"**Даты в файле:** {df['MatchDate'].min().strftime('%d.%m.%Y') if pd.notna(df['MatchDate'].min()) else 'N/A'} - {df['MatchDate'].max().strftime('%d.%m.%Y') if pd.notna(df['MatchDate'].max()) else 'N/A'}")
                    st.write(f"**Сегодня:** {today.strftime('%d.%m.%Y')}")
                    st.write(f"**Ищем до:** {future_limit.strftime('%d.%m.%Y')}")
                    
                    # Фильтр
                    if 'FTHG' in df.columns:
                        no_result = df['FTHG'].isna()
                        st.write(f"**Матчей без результата:** {no_result.sum()}")
                    else:
                        no_result = pd.Series([True]*len(df))
                    
                    date_filter = (df['MatchDate'] >= today) & (df['MatchDate'] <= future_limit)
                    st.write(f"**Матчей в диапазоне дат:** {date_filter.sum()}")
                    
                    matches_to_analyze = df[date_filter & no_result].copy()
                    st.write(f"**Итого для анализа:** {len(matches_to_analyze)}")
                    
                    if len(matches_to_analyze) == 0:
                        st.error("❌ Нет матчей! Покажу первые 5 матчей из файла:")
                        st.write(df[['Date', 'HomeTeam', 'AwayTeam', 'FTHG']].head())
                        st.stop()
                else:
                    st.error("❌ Нет колонки Date!")
                    st.stop()
                
                # Обучение
                with st.spinner("Обучение..."):
                    elo = EloModel()
                    past = df[df['FTHG'].notna()] if 'FTHG' in df.columns else pd.DataFrame()
                    
                    for _, row in past.iterrows():
                        h, a = row.get('HomeTeam',''), row.get('AwayTeam','')
                        if h and a:
                            hg = float(row.get('FTHG', 0))
                            ag = float(row.get('FTAG', 0))
                            s1 = 1 if hg > ag else (0.5 if hg == ag else 0)
                            elo.update(h, a, s1, 1-s1)
                    
                    st.success(f"✅ Обучено на {len(past)} матчах")
                
                # Генерация
                with st.spinner("Генерация..."):
                    forecasts = []
                    all_predictions = []  # ВСЕ прогнозы для отладки
                    bank = st.session_state.app_data["bank"]
                    
                    for idx, row in matches_to_analyze.iterrows():
                        h = row.get('HomeTeam', '')
                        a = row.get('AwayTeam', '')
                        
                        if not h or not a:
                            continue
                        
                        try:
                            # Elo
                            p1, px, p2 = elo.predict(h, a)
                            
                            # Форма
                            h_past = past[(past['HomeTeam']==h) | (past['AwayTeam']==h)].tail(5)
                            a_past = past[(past['HomeTeam']==a) | (past['AwayTeam']==a)].tail(5)
                            
                            h_goals = h_past['FTHG'].mean() if len(h_past) > 0 else 1.2
                            a_goals = a_past['FTAG'].mean() if len(a_past) > 0 else 1.0
                            
                            lam_h = max(0.5, h_goals)
                            lam_a = max(0.5, a_goals)
                            
                            # Пуассон
                            matrix = np.zeros((6,6))
                            for i in range(6):
                                for j in range(6):
                                    matrix[i,j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
                            
                            pp1 = np.sum(np.tril(matrix, -1))
                            ppx = np.sum(np.diag(matrix))
                            pp2 = np.sum(np.triu(matrix, 1))
                            
                            # Ансамбль
                            ph = 0.4*p1 + 0.6*pp1
                            pxf = 0.4*px + 0.6*ppx
                            pa = 0.4*p2 + 0.6*pp2
                            
                            # Коэффициенты
                            odds_h = float(row.get('B365H', row.get('PSH', 1.95)))
                            odds_x = float(row.get('B365D', row.get('PSD', 3.40)))
                            odds_a = float(row.get('B365A', row.get('PSA', 3.10)))
                            
                            opts = [("П1", ph, odds_h), ("X", pxf, odds_x), ("П2", pa, odds_a)]
                            pick, prob, odd = max(opts, key=lambda x: x[1]*x[2])
                            
                            ev = (prob * odd) - 1.0
                            
                            # Келли
                            b = odd - 1
                            kelly = (b * prob - (1 - prob)) / b if b > 0 else 0
                            stake = max(0, kelly * kelly_frac) * bank
                            stake = min(stake, bank * 0.05)
                            
                            match_date = row.get('MatchDate', today)
                            date_str = match_date.strftime('%d.%m')
                            
                            prediction = {
                                "league": row.get('League',''),
                                "match": f"{h} vs {a}",
                                "date": date_str,
                                "pick": pick,
                                "prob": prob,
                                "odds": odd,
                                "ev": ev,
                                "stake": round(stake, 2),
                                "meets_ev": ev > min_ev and stake > 0
                            }
                            
                            all_predictions.append(prediction)
                            
                            if ev > min_ev and stake > 0:
                                forecasts.append(prediction)
                        except Exception as e:
                            if debug_mode:
                                st.error(f"Ошибка: {e}")
                            continue
                    
                    # Сортируем: сначала те что проходят фильтр
                    all_predictions.sort(key=lambda x: (x['meets_ev'], x['ev']), reverse=True)
                    
                    st.session_state.app_data["forecasts"] = forecasts
                    st.session_state.app_data["all_predictions"] = all_predictions
                    save_history(st.session_state.app_data)
                    
                    st.success(f"✅ Проанализировано: {len(all_predictions)}")
                    st.success(f"🎯 Проходят фильтр: {len(forecasts)}")
                    st.rerun()
    
    # Показ
    forecasts = st.session_state.app_data.get("forecasts", [])
    all_preds = st.session_state.app_data.get("all_predictions", [])
    
    if debug_mode and all_preds:
        st.markdown(f"### 🔍 ВСЕ прогнозы ({len(all_preds)})")
        st.write("Показываем все матчи. Зелёные = проходят фильтр EV")
        
        for p in all_preds[:20]:  # Первые 20
            status = "✅" if p['meets_ev'] else "❌"
            ev_class = "ev-positive" if p['ev'] > 0 else "ev-negative"
            
            st.markdown(f"""
                <div class="{'forecast-card' if p['meets_ev'] else 'debug-card'}">
                    <div style="display:flex;justify-content:space-between">
                        <span>{status} {p['league']}</span>
                        <span>{p['date']}</span>
                    </div>
                    <div style="font-weight:700;color:#f8fafc;margin:8px 0">{p['match']}</div>
                    <div style="font-size:0.9rem">
                        <b>{p['pick']}</b> | Prob: {p['prob']*100:.1f}% | Odds: {p['odds']:.2f} | 
                        EV: <span class="{ev_class}">{p['ev']*100:.1f}%</span> | 
                        Stake: {p['stake']:.2f}
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        if len(all_preds) > 20:
            st.write(f"... и ещё {len(all_preds)-20}")
    
    elif forecasts:
        st.markdown(f"### 📊 Выгодные ставки ({len(forecasts)})")
        for f in forecasts:
            st.markdown(f"""
                <div class="forecast-card">
                    <div style="display:flex;justify-content:space-between">
                        <span style="background:#38bdf8;padding:4px 10px;border-radius:6px;color:white;font-weight:700">{f['league']}</span>
                        <span style="color:#94a3b8">{f['date']}</span>
                    </div>
                    <div style="font-size:1.2rem;font-weight:700;color:#f8fafc;margin:8px 0"> {f['match']}</div>
                    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
                        <div><div style="color:#94a3b8;font-size:0.75rem">Прогноз</div><div style="color:#facc15;font-weight:700">{f['pick']}</div></div>
                        <div><div style="color:#94a3b8;font-size:0.75rem">Вероятность</div><div style="color:#4ade80;font-weight:700">{f['prob']*100:.1f}%</div></div>
                        <div><div style="color:#94a3b8;font-size:0.75rem">Коэффициент</div><div style="color:#facc15;font-weight:700">{f['odds']:.2f}</div></div>
                        <div><div style="color:#94a3b8;font-size:0.75rem">EV</div><div class="ev-positive">{f['ev']*100:.1f}%</div></div>
                    </div>
                    <div style="margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.1)">
                        <span style="color:#94a3b8">Ставка:</span> <span style="color:#facc15;font-weight:700">{f['stake']:.2f} у.е.</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("👆 Выберите лиги и нажмите «Анализ»")

with tab2:
    st.markdown("### 📋 Ставки")
    bets = st.session_state.app_data.get("bets", [])
    if not bets:
        st.info("Нет ставок")
    else:
        pending = [b for b in bets if b.get("status")=="pending"]
        for i, bet in enumerate(pending):
            cols = st.columns(2)
            with cols[0]:
                if st.button("✅", key=f"w{i}"):
                    bet["status"] = "won"
                    profit = bet.get("stake",0) * bet.get("odds",0)
                    st.session_state.app_data["bank"] += profit
                    st.session_state.app_data["stats"]["won"] += 1
                    save_history(st.session_state.app_data)
                    st.success(f"+{profit:.2f}")
                    st.rerun()
            with cols[1]:
                if st.button("", key=f"l{i}"):
                    bet["status"] = "lost"
                    st.session_state.app_data["stats"]["lost"] += 1
                    save_history(st.session_state.app_data)
                    st.error(f"-{bet.get('stake',0):.2f}")
                    st.rerun()
