import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# --- НАСТРОЙКИ И СТИЛИ ---
st.set_page_config(page_title="Pro Betting AI v5.0", page_icon="🎯", layout="wide")
st.markdown("""
<style>
    .stApp { background-color: #0f172a; color: #e2e8f0; }
    .main-header { font-size: 2rem; font-weight: 800; color: #38bdf8; margin-bottom: 20px; }
    .card { background: rgba(30, 41, 59, 0.6); padding: 20px; border-radius: 12px; border: 1px solid rgba(56, 189, 248, 0.15); margin-bottom: 15px; }
    .ev-pos { color: #10b981; font-weight: bold; }
    .ev-neg { color: #ef4444; font-weight: bold; }
    .debug-box { background: #1e293b; padding: 10px; border-radius: 8px; font-family: monospace; font-size: 0.85rem; margin-top: 10px; border-left: 3px solid #f59e0b; white-space: pre-wrap; }
</style>
""", unsafe_allow_html=True)

# --- КОНСТАНТЫ ---
HISTORY_FILE = "data.json"
SEASON = "2526" 
BASE_URL = f"https://www.football-data.co.uk/mmz4281/{SEASON}/"

LEAGUES = {
    "🏴󠁧󠁢󠁮󠁧 Англия (АПЛ)": "E0.csv",
    "🇪🇸 Испания (Ла Лига)": "SP1.csv",
    "🇮🇹 Италия (Серия А)": "I1.csv",
    "🇪 Германия (Бундеслига)": "D1.csv",
    "🇫 Франция (Лига 1)": "F1.csv"
}

# --- УПРАВЛЕНИЕ ДАННЫМИ ---
def load_data():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f: return json.load(f)
        except: pass
    return {"bank": 10000.0, "bets": [], "forecasts": [], "stats": {"won": 0, "lost": 0, "profit": 0}}

def save_data(d):
    with open(HISTORY_FILE, "w") as f: json.dump(d, f, indent=2)

if "app" not in st.session_state: 
    st.session_state.app = load_data()

# --- МОДЕЛЬ ELO + PUISSON (ЧИСТЫЙ PYTHON, БЕЗ SKLEARN) ---
class SimpleModel:
    def __init__(self): self.elo = {}
    
    def update(self, h, a, hg, ag):
        r1, r2 = self.elo.get(h, 1500), self.elo.get(a, 1500)
        e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        s1 = 1 if hg > ag else (0.5 if hg == ag else 0)
        self.elo[h] = r1 + 32 * (s1 - e1)
        self.elo[a] = r2 + 32 * ((1-s1) - (1-e1))

    def predict(self, h, a, df_past):
        # Вероятности на основе Elo
        r1, r2 = self.elo.get(h, 1500), self.elo.get(a, 1500)
        p1_e = 1 / (1 + 10 ** ((r2 - r1) / 400))
        p2_e = 1 / (1 + 10 ** ((r1 - r2) / 400))
        pd_e = 0.25 * (1 - abs(p1_e - p2_e))
        tot_e = p1_e + p2_e + pd_e
        
        # Ожидаемые голы на основе формы (последние 5 матчей)
        h_goals = df_past[(df_past['HomeTeam']==h)|(df_past['AwayTeam']==h)].tail(5)['FTHG'].mean() if len(df_past) > 0 else 1.3
        a_goals = df_past[(df_past['HomeTeam']==a)|(df_past['AwayTeam']==a)].tail(5)['FTAG'].mean() if len(df_past) > 0 else 1.1
        
        lam_h, lam_a = max(0.4, h_goals), max(0.4, a_goals)
        
        # Матрица Пуассона
        mat = np.zeros((7,7))
        for i in range(7):
            for j in range(7): mat[i,j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
            
        p1_p = np.sum(np.tril(mat, -1))
        pd_p = np.sum(np.diag(mat))
        p2_p = np.sum(np.triu(mat, 1))
        tot_p = p1_p + pd_p + p2_p
        
        # Ансамбль 50/50
        p1 = (0.5 * p1_e/tot_e) + (0.5 * p1_p/tot_p)
        pd_val = (0.5 * pd_e/tot_e) + (0.5 * pd_p/tot_p)
        p2 = (0.5 * p2_e/tot_e) + (0.5 * p2_p/tot_p)
        
        return p1, pd_val, p2

# --- ГЛАВНЫЙ ИНТЕРФЕЙС ---
st.markdown('<div class="main-header">🎯 Pro Betting AI v5.0</div>', unsafe_allow_html=True)

sb = st.sidebar
sb.metric("💰 Банк", f"{st.session_state.app['bank']:.2f}")
kelly_frac = sb.slider("Келли (дробь)", 0.1, 0.5, 0.25, 0.05)
min_ev = sb.slider("Мин. EV (%)", 0, 10, 0) / 100
check_mode = sb.checkbox("🔍 Режим проверки (показать сыгранные матчи)", value=False, help="Включи, если будущих матчей нет в файле")

if sb.button("🔄 Полный сброс"):
    st.session_state.app = {"bank": 10000.0, "bets": [], "forecasts": [], "stats": {"won": 0, "lost": 0, "profit": 0}}
    save_data(st.session_state.app)
    st.rerun()

tab1, tab2 = st.tabs(["🔍 Анализ матчей", "📋 Мои ставки"])

with tab1:
    selected = st.multiselect("Выберите лиги:", list(LEAGUES.keys()), default=["🏴󠁧󠁥󠁮󠁿 Англия (АПЛ)"])
    days = st.slider("Горизонт поиска (дни)", 1, 30, 7)
    
    if st.button("🚀 ЗАПУСТИТЬ АНАЛИЗ", type="primary"):
        if not selected: st.warning("️ Выбери хотя бы одну лигу!"); st.stop()
        
        # 1. ЗАГРУЗКА ДАННЫХ
        dfs = []
        errors = []
        for l in selected:
            try:
                d = pd.read_csv(BASE_URL + LEAGUES[l])
                d['League'] = l
                dfs.append(d)
            except Exception as e: errors.append(f"{l}: {str(e)[:80]}")
        
        if not dfs:
            st.error("❌ Не удалось загрузить данные! Проверь интернет или названия лиг.")
            for e in errors: st.code(e)
            st.stop()
            
        df = pd.concat(dfs, ignore_index=True)
        st.success(f"✅ Загружено {len(df)} строк из файлов.")
        
        # 2. ПАРСИНГ И ДИАГНОСТИКА ДАТ
        if 'Date' not in df.columns:
            st.error("❌ Ошибка структуры файла: нет колонки 'Date'."); st.stop()
            
        df['MatchDate'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        today = pd.Timestamp.now().normalize()
        limit = today + pd.Timedelta(days=days)
        
        debug_info = f"📅 Сегодня: {today.strftime('%d.%m')} | Ищем до: {limit.strftime('%d.%m')}\n"
        debug_info += f"📂 Диапазон дат в файле: {df['MatchDate'].min()} — {df['MatchDate'].max()}\n"
        debug_info += f"❓ Сыгранных матчей (есть результат): {df['FTHG'].notna().sum()}\n"
        
        # 3. ФИЛЬТРАЦИЯ МАТЧЕЙ
        mask_date = (df['MatchDate'] >= today) & (df['MatchDate'] <= limit)
        mask_unplayed = df['FTHG'].isna() 
        
        if check_mode:
            # Режим проверки: берем матчи за последние N дней, даже если они сыграны
            target_df = df[mask_date].copy()
            debug_info += f"🔍 [РЕЖИМ ПРОВЕРКИ] Найдено матчей в диапазоне: {len(target_df)}\n"
        else:
            # Обычный режим: только будущие без результата
            target_df = df[mask_date & mask_unplayed].copy()
            debug_info += f"🔍 [ОБЫЧНЫЙ РЕЖИМ] Будущих матчей без результата: {len(target_df)}"

        st.markdown(f'<div class="debug-box">{debug_info}</div>', unsafe_allow_html=True)
        
        if len(target_df) == 0:
            st.warning("⚠️ Матчей для анализа не найдено. Попробуй увеличить горизонт дней или включи 'Режим проверки' в сайдбаре.")
            st.stop()
            
        # 4. ОБУЧЕНИЕ МОДЕЛИ
        model = SimpleModel()
        past_df = df[df['FTHG'].notna()]
        for _, r in past_df.iterrows():
            model.update(r['HomeTeam'], r['AwayTeam'], float(r['FTHG']), float(r['FTAG']))
            
        # 5. ГЕНЕРАЦИЯ ПРОГНОЗОВ
        forecasts = []
        bank = st.session_state.app['bank']
        
        for _, row in target_df.iterrows():
            h, a = row['HomeTeam'], row['AwayTeam']
            if pd.isna(h) or pd.isna(a): continue
            
            p1, pd_v, p2 = model.predict(h, a, past_df)
            
            oh = float(row.get('B365H', row.get('PSH', 2.0)))
            od = float(row.get('B365D', row.get('PSD', 3.5)))
            oa = float(row.get('B365A', row.get('PSA', 3.5)))
            
            opts = [("П1", p1, oh), ("X", pd_v, od), ("П2", p2, oa)]
            pick, prob, odd = max(opts, key=lambda x: x[1]*x[2])
            
            ev = (prob * odd) - 1.0
            b = odd - 1
            kelly_stake = max(0, ((b*prob - (1-prob))/b) * kelly_frac) * bank
            kelly_stake = min(kelly_stake, bank * 0.05)
            
            # Если режим проверки, добавляем реальный счет
            actual_score = ""
            is_played = False
            if check_mode and pd.notna(row.get('FTHG')):
                actual_score = f" (Счет: {int(row['FTHG'])}:{int(row['FTAG'])})"
                is_played = True
            
            forecasts.append({
                "match": f"{h} vs {a}{actual_score}", "league": row['League'], 
                "date": row['MatchDate'].strftime('%d.%m'),
                "pick": pick, "prob": prob, "odd": odd, "ev": ev, 
                "stake": round(kelly_stake, 2), 
                "pass_filter": (ev > min_ev and kelly_stake > 1) and not is_played
            })
        
        st.session_state.app['forecasts'] = forecasts
        save_data(st.session_state.app)
        st.success(f"✅ Анализ завершен! Обработано {len(forecasts)} матчей.")
        st.rerun()

    # ОТОБРАЖЕНИЕ КАРТОЧЕК
    fc = st.session_state.app.get('forecasts', [])
    if fc:
        passed = [x for x in fc if x['pass_filter']]
        display_list = passed if passed else fc[:15] 
        
        title_text = f"### 🎯 Найдено {len(passed)} ставок с перевесом (показано топ-{len(display_list)})"
        if check_mode: title_text = "### 🔍 Результаты проверки модели на сыгранных матчах"
        st.markdown(title_text)
        
        for f in display_list:
            border_color = "#10b981" if f['pass_filter'] else "#334155"
            opacity = "1" if f['pass_filter'] else "0.5"
            
            st.markdown(f"""
            <div class="card" style="border-color: {border_color}; opacity: {opacity};">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:#38bdf8; font-weight:bold; font-size:0.9rem;">{f['league']}</span>
                    <span style="color:#94a3b8; font-size:0.85rem;">{f['date']}</span>
                </div>
                <div style="font-size:1.3rem; font-weight:800; margin:10px 0; color:#f8fafc;">{f['match']}</div>
                <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:10px; text-align:center; background:rgba(15,23,42,0.5); padding:10px; border-radius:8px;">
                    <div><div style="font-size:0.75rem; color:#94a3b8; margin-bottom:4px;">ПРОГНОЗ</div><div style="color:#facc15; font-weight:bold; font-size:1.2rem">{f['pick']}</div></div>
                    <div><div style="font-size:0.75rem; color:#94a3b8; margin-bottom:4px;">ВЕРОЯТНОСТЬ</div><div style="color:#4ade80; font-weight:bold; font-size:1.2rem">{f['prob']*100:.1f}%</div></div>
                    <div><div style="font-size:0.75rem; color:#94a3b8; margin-bottom:4px;">КОЭФФИЦИЕНТ</div><div style="color:#facc15; font-weight:bold; font-size:1.2rem">{f['odd']:.2f}</div></div>
                    <div><div style="font-size:0.75rem; color:#94a3b8; margin-bottom:4px;">EV (ПЕРЕВЕС)</div><div class="{'ev-pos' if f['ev']>0 else 'ev-neg'}" style="font-size:1.2rem">{f['ev']*100:.1f}%</div></div>
                </div>
                <div style="margin-top:15px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.1); display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:#cbd5e1; font-size:0.9rem;">Рекомендуемая ставка (Келли):</span>
                    <span style="color:#facc15; font-weight:800; font-size:1.3rem">{f['stake']:.2f} у.е.</span>
                </div>
            </div>""", unsafe_allow_html=True)
            
        if not passed and not check_mode: 
            st.info("💡 Ни одна ставка не прошла фильтр EV. Уменьши 'Мин. EV' в сайдбаре до 0% или увеличь горизонт дней.")

with tab2:
    bets = st.session_state.app.get('bets', [])
    if not bets: 
        st.info("📭 История ставок пуста. Ставки появятся здесь, когда ты начнешь отслеживать результаты."); st.stop()
    
    pending = [b for b in bets if b['status'] == 'pending']
    completed = [b for b in bets if b['status'] != 'pending']
    
    if pending:
        st.markdown("#### ⏳ Активные ставки")
        for i, b in enumerate(pending):
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.markdown(f"**{b['match']}** \n\n `{b['pick']} @ {b['odd']}` | Ставка: `{b['stake']:.2f}`")
            if c2.button("✅ Win", key=f"w{i}"):
                b['status'] = 'won'; st.session_state.app['bank'] += b['stake']*b['odd']
                st.session_state.app['stats']['profit'] += b['stake']*(b['odd']-1)
                save_data(st.session_state.app); st.rerun()
            if c3.button("❌ Loss", key=f"l{i}"):
                b['status'] = 'lost'; st.session_state.app['stats']['profit'] -= b['stake']
                save_data(st.session_state.app); st.rerun()
                
    if completed:
        st.markdown("#### 📜 История")
        for b in completed[-10:]:
            status_emoji = "" if b['status']=='won' else "😢"
            st.markdown(f"{status_emoji} **{b['match']}** ({b['pick']} @ {b['odd']}) — {b['status'].upper()}")
