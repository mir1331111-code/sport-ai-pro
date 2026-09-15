import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Настройка страницы
st.set_page_config(page_title="Pro Betting AI v4.0", page_icon="🎯", layout="wide")

# Стили интерфейса
st.markdown("""
<style>
    .stApp { background: linear-gradient(rgba(10, 15, 25, 0.95), rgba(10, 15, 25, 0.98)); }
    .main-header { font-size: 2rem; font-weight: 700; color: #38bdf8; margin-bottom: 1rem; }
    .card { background: rgba(30, 41, 59, 0.8); padding: 15px; border-radius: 10px; border: 1px solid rgba(56, 189, 248, 0.2); margin-bottom: 10px; }
    .ev-pos { color: #10b981; font-weight: bold; }
    .ev-neg { color: #ef4444; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# === КОНФИГУРАЦИЯ ЛИГ И КУБКОВ ===
# Используем коды football-data.co.uk для сезона 2526 (2025/2026)
LEAGUES = {
    "󠁧󠁢󠁮󠁧 Англия (АПЛ)": "E0.csv",
    "🇪🇸 Испания (Ла Лига)": "SP1.csv",
    "🇮🇹 Италия (Серия А)": "I1.csv",
    "🇪 Германия (Бундеслига)": "D1.csv",
    "🇫 Франция (Лига 1)": "F1.csv",
    "🇳🇱 Нидерланды (Эредивизи)": "N1.csv",
    "🇵 Португалия (Примейра)": "P1.csv",
    "🇹🇷 Турция (Суперлига)": "T1.csv",
    "🇷 Россия (РПЛ)": "R1.csv",
    "🇳🇴 Норвегия (Элитсерия)": "N0.csv", 
    "🏆 Лига Чемпионов": "C1.csv",
    "🏆 Лига Европы": "EU1.csv",
    "🏆 Лига Конференций": "EC1.csv",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Кубок Англии": "ECL.csv",
    "🇪🇸 Кубок Испании": "SPC.csv",
    "🇮🇹 Кубок Италии": "IC.csv",
    "🇩 Кубок Германии": "DFB.csv",
    "🇫🇷 Кубок Франции": "FR1.csv" 
}

HISTORY_FILE = "betting_data_v4.json"

# === УТИЛИТЫ ===
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            return json.load(open(HISTORY_FILE, "r"))
        except: pass
    return {"bank": 10000.0, "bets": [], "stats": {"won": 0, "lost": 0, "profit": 0}, "forecasts": []}

def save_history(data):
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

if "app_data" not in st.session_state:
    st.session_state.app_data = load_history()

# === МОДЕЛЬ ЭЛО И ПУАССОНА ===
class SimpleModel:
    def __init__(self):
        self.elo = {}
    
    def update_elo(self, t1, t2, s1, s2):
        r1 = self.elo.get(t1, 1500)
        r2 = self.elo.get(t2, 1500)
        e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        self.elo[t1] = r1 + 32 * (s1 - e1)
        self.elo[t2] = r2 + 32 * ((1-s1) - (1-e1))
    
    def predict(self, h, a, df):
        # Elo вероятности
        r1 = self.elo.get(h, 1500)
        r2 = self.elo.get(a, 1500)
        p1_e = 1 / (1 + 10 ** ((r2 - r1) / 400))
        p2_e = 1 / (1 + 10 ** ((r1 - r2) / 400))
        px_e = 0.25 * (1 - abs(p1_e - p2_e))
        
        # Пуассон (на основе средних голов лиги, если нет истории команды)
        lam_h = 1.5 
        lam_a = 1.2
        
        matrix = np.zeros((6,6))
        for i in range(6):
            for j in range(6):
                matrix[i,j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
                
        p1_p = np.sum(np.tril(matrix, -1))
        px_p = np.sum(np.diag(matrix))
        p2_p = np.sum(np.triu(matrix, 1))
        
        # Гибрид
        p1 = 0.5*p1_e + 0.5*p1_p
        px = 0.5*px_e + 0.5*px_p
        p2 = 0.5*p2_e + 0.5*p2_p
        
        total = p1 + px + p2
        return p1/total, px/total, p2/total

# === ИНТЕРФЕЙС ===
st.markdown('<div class="main-header">🎯 Pro Betting AI v4.0</div>', unsafe_allow_html=True)

st.sidebar.header("⚙️ Банк и настройки")
st.sidebar.metric(" Банкролл", f"{st.session_state.app_data['bank']:.2f} у.е.")

kelly_frac = st.sidebar.slider("Дробь Келли", 0.1, 0.5, 0.25, 0.05)
min_ev = st.sidebar.slider("Мин. перевес (EV %)", 1, 10, 3) / 100

if st.sidebar.button("🔄 Полный сброс"):
    st.session_state.app_data = load_history()
    save_history(st.session_state.app_data)
    st.rerun()

tab1, tab2, tab3 = st.tabs([" Прогнозы", "📋 Ставки", "📊 Статистика"])

with tab1:
    st.header("Выбор турниров")
    
    # Безопасный multiselect без default
    selected_leagues = st.multiselect(
        "Отметьте лиги и кубки:",
        options=list(LEAGUES.keys())
    )
    
    days = st.slider("Период анализа (дни)", 1, 14, 7)
    
    if st.button("🚀 Запустить анализ", type="primary"):
        if not selected_leagues:
            st.warning("Выберите хотя бы один турнир!")
        else:
            with st.spinner("Загрузка данных со всех серверов..."):
                all_dfs = []
                base_url = "https://www.football-data.co.uk/mmz4281/2526/"
                
                for league_name in selected_leagues:
                    code = LEAGUES[league_name]
                    try:
                        df = pd.read_csv(base_url + code)
                        df['League'] = league_name
                        all_dfs.append(df)
                    except Exception as e:
                        st.warning(f"Не удалось загрузить {league_name} (возможно, сезон еще не начался или файл недоступен).")
                
                if not all_dfs:
                    st.error("Ни одна лига не загрузилась. Проверьте интернет или попробуйте другие лиги.")
                    st.stop()
                    
                combined_df = pd.concat(all_dfs, ignore_index=True)
                st.success(f"✅ Загружено {len(combined_df)} матчей из {len(selected_leagues)} турниров.")
            
            with st.spinner("Обучение модели и расчет вероятностей..."):
                model = SimpleModel()
                
                # Обучение на сыгранных матчах
                if 'FTHG' in combined_df.columns:
                    past = combined_df[pd.notna(combined_df['FTHG'])]
                    for _, row in past.iterrows():
                        h, a = str(row.get('HomeTeam','')), str(row.get('AwayTeam',''))
                        hg, ag = float(row.get('FTHG',0)), float(row.get('FTAG',0))
                        if h and a:
                            s1 = 1 if hg > ag else (0.5 if hg == ag else 0)
                            model.update_elo(h, a, s1, 1-s1)
                
                # Фильтрация будущих матчей
                today = pd.Timestamp.now().normalize()
                limit = today + pd.Timedelta(days=days)
                
                if 'Date' in combined_df.columns:
                    combined_df['MatchDate'] = pd.to_datetime(combined_df['Date'], dayfirst=True, errors='coerce')
                    future = combined_df[
                        (combined_df['MatchDate'] >= today) & 
                        (combined_df['MatchDate'] <= limit)
                    ]
                    # Если есть результаты, исключаем их (значит матч уже прошел)
                    if 'FTHG' in future.columns:
                        future = future[pd.isna(future['FTHG']) | (future['FTHG']=='')]
                else:
                    future = combined_df
                
                forecasts = []
                bank = st.session_state.app_data["bank"]
                
                for _, row in future.iterrows():
                    h, a = str(row.get('HomeTeam','')), str(row.get('AwayTeam',''))
                    if not h or not a: continue
                    
                    try:
                        p1, px, p2 = model.predict(h, a, combined_df)
                        
                        # Коэффициенты
                        oh = float(row.get('B365H', row.get('PSH', 1.95)))
                        ox = float(row.get('B365D', row.get('PSD', 3.40)))
                        oa = float(row.get('B365A', row.get('PSA', 3.10)))
                        
                        opts = [("П1", p1, oh), ("X", px, ox), ("П2", p2, oa)]
                        pick, prob, odd = max(opts, key=lambda x: x[1]*x[2])
                        
                        ev = (prob * odd) - 1.0
                        
                        # Расчет ставки по Келли
                        b = odd - 1
                        kelly_raw = (b * prob - (1-prob)) / b
                        stake = max(0, min(kelly_raw * kelly_frac * bank, bank * 0.05))
                        
                        if ev > min_ev and stake > 0:
                            forecasts.append({
                                "league": row.get('League', ''),
                                "match": f"{h} vs {a}",
                                "date": row.get('MatchDate', today).strftime('%d.%m'),
                                "pick": pick,
                                "prob": prob,
                                "odds": odd,
                                "ev": ev,
                                "stake": round(stake, 2)
                            })
                    except: continue
                
                st.session_state.app_data["forecasts"] = forecasts
                save_history(st.session_state.app_data)
                st.success(f" Найдено {len(forecasts)} выгодных ставок!")
                st.rerun()
    
    # Вывод прогнозов
    forecasts = st.session_state.app_data.get("forecasts", [])
    if forecasts:
        st.subheader(f"📊 Результаты ({len(forecasts)} ставок)")
        for f in forecasts:
            st.markdown(f"""
            <div class="card">
                <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                    <span style="background:#38bdf8; padding:2px 8px; border-radius:4px; font-size:0.8rem; color:white;">{f['league']}</span>
                    <span style="color:#94a3b8">{f['date']}</span>
                </div>
                <div style="font-size:1.1rem; font-weight:bold; color:white; margin-bottom:8px;">⚽ {f['match']}</div>
                <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:10px; font-size:0.9rem;">
                    <div><span style="color:#94a3b8">Прогноз:</span> <b style="color:#facc15">{f['pick']}</b></div>
                    <div><span style="color:#94a3b8">Вероятность:</span> <b style="color:#4ade80">{f['prob']*100:.1f}%</b></div>
                    <div><span style="color:#94a3b8">Коэф:</span> <b style="color:#facc15">{f['odds']:.2f}</b></div>
                    <div><span style="color:#94a3b8">EV:</span> <b class="{'ev-pos' if f['ev']>0 else 'ev-neg'}">{f['ev']*100:.1f}%</b></div>
                </div>
                <div style="margin-top:8px; border-top:1px solid rgba(255,255,255,0.1); padding-top:8px;">
                    💰 Рекомендованная ставка (Келли): <b style="color:#facc15">{f['stake']:.2f} у.е.</b>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Выберите лиги выше и нажмите «Запустить анализ», чтобы получить прогнозы.")

with tab2:
    st.header("Активные ставки")
    bets = st.session_state.app_data.get("bets", [])
    
    pending = [b for b in bets if b.get("status") == "pending"]
    if not pending:
        st.info("Нет активных ставок. Добавьте их из вкладки «Прогнозы» или вручную.")
    else:
        for i, bet in enumerate(pending):
            st.markdown(f"""
            <div class="card" style="border-left: 4px solid #f59e0b;">
                <div style="font-size:1.1rem; font-weight:bold; color:white;">⚽ {bet.get('match','')}</div>
                <div style="color:#cbd5e1; margin:5px 0;">
                    Прогноз: <b>{bet.get('pick','')}</b> | Коэф: <b>{bet.get('odds',0):.2f}</b> | Ставка: <b>{bet.get('stake',0):.2f} у.е.</b>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            cols = st.columns(2)
            with cols[0]:
                if st.button(f"✅ Выиграла", key=f"w{i}"):
                    profit = bet.get("stake", 0) * bet.get("odds", 1)
                    st.session_state.app_data["bank"] += profit
                    st.session_state.app_data["stats"]["won"] += 1
                    st.session_state.app_data["stats"]["profit"] += (profit - bet.get("stake", 0))
                    bet["status"] = "won"
                    save_history(st.session_state.app_data)
                    st.success(f"+{profit:.2f} у.е.")
                    st.rerun()
            with cols[1]:
                if st.button(f"❌ Проиграла", key=f"l{i}"):
                    st.session_state.app_data["bank"] -= bet.get("stake", 0)
                    st.session_state.app_data["stats"]["lost"] += 1
                    st.session_state.app_data["stats"]["profit"] -= bet.get("stake", 0)
                    bet["status"] = "lost"
                    save_history(st.session_state.app_data)
                    st.error(f"-{bet.get('stake',0):.2f} у.е.")
                    st.rerun()

with tab3:
    st.header("Статистика эффективности")
    stats = st.session_state.app_data.get("stats", {})
    bank = st.session_state.app_data["bank"]
    
    total = stats.get("won", 0) + stats.get("lost", 0)
    wr = (stats.get("won", 0) / total * 100) if total > 0 else 0
    roi = (stats.get("profit", 0) / 10000 * 100)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Текущий банк", f"{bank:.2f}", f"{bank-10000:+.2f}")
    c2.metric(" Всего ставок", total)
    c3.metric("🎯 Win Rate", f"{wr:.1f}%")
    c4.metric("📈 ROI", f"{roi:.2f}%")
