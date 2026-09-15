import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Pro Betting AI v3.0", page_icon="🎯", layout="wide")

# СТИЛИ
st.markdown("""
<style>
.stApp {
    background: linear-gradient(rgba(10, 15, 25, 0.95), rgba(10, 15, 25, 0.98));
}
.main-header {
    font-size: 2.5rem;
    font-weight: 700;
    background: linear-gradient(90deg, #38bdf8, #10b981);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 1rem;
}
.metric-card {
    background: rgba(30, 41, 59, 0.8);
    padding: 20px;
    border-radius: 12px;
    border: 1px solid rgba(56, 189, 248, 0.3);
    margin-bottom: 15px;
}
.forecast-card {
    background: rgba(30, 41, 59, 0.75);
    padding: 18px;
    border-radius: 12px;
    border: 1px solid rgba(56, 189, 248, 0.2);
    margin-bottom: 12px;
}
.bet-card-pending {
    background: rgba(30, 41, 59, 0.75);
    padding: 18px;
    border-radius: 12px;
    border-left: 6px solid #f59e0b;
}
.bet-card-won {
    background: rgba(16, 185, 129, 0.15);
    padding: 18px;
    border-radius: 12px;
    border-left: 6px solid #10b981;
}
.bet-card-lost {
    background: rgba(239, 68, 68, 0.15);
    padding: 18px;
    border-radius: 12px;
    border-left: 6px solid #ef4444;
}
.ev-positive { color: #10b981; font-weight: 700; }
.ev-negative { color: #ef4444; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# КОНФИГУРАЦИЯ
HISTORY_FILE = "pro_betting_v3.json"

LEAGUES_DICT = {
    "England": "🏴󠁧󠁢󠁥󠁮 Англия (АПЛ)",
    "Spain": "🇪🇸 Испания (Ла Лига)",
    "Italy": "🇮🇹 Италия (Серия А)",
    "Germany": "🇩 Германия (Бундеслига)",
    "France": "🇫🇷 Франция (Лига 1)",
    "Russia": "🇷🇺 Россия (РПЛ)",
    "Turkey": "🇹🇷 Турция (Суперлига)"
}

LEAGUE_CODES = {
    "🏴󠁧󠁥󠁮 Англия (АПЛ)": "E0.csv",
    "🇪🇸 Испания (Ла Лига)": "SP1.csv",
    "🇮🇹 Италия (Серия А)": "I1.csv",
    "🇩🇪 Германия (Бундеслига)": "D1.csv",
    "🇫🇷 Франция (Лига 1)": "F1.csv",
    "🇺 Россия (РПЛ)": "R1.csv",
    "🇹🇷 Турция (Суперлига)": "T1.csv"
}

# МОДУЛЬ ДАННЫХ
class DataManager:
    @staticmethod
    def load_football_data_csv(leagues: list, season: str = "2526") -> pd.DataFrame:
        base_url = f"https://www.football-data.co.uk/mmz4281/{season}/"
        
        all_data = []
        for league in leagues:
            if league in LEAGUE_CODES:
                url = base_url + LEAGUE_CODES[league]
                try:
                    df = pd.read_csv(url)
                    df['League'] = league
                    df['Source'] = 'football-data'
                    all_data.append(df)
                except Exception as e:
                    st.warning(f"Не удалось загрузить {league}: {str(e)[:100]}")
        
        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
    
    @staticmethod
    def calculate_form(df: pd.DataFrame, team: str, last_n: int = 5) -> dict:
        if 'HomeTeam' not in df.columns:
            return {'form': 0.5, 'goals_scored': 1.0, 'goals_conceded': 1.0}
            
        team_matches = df[
            ((df['HomeTeam'] == team) | (df['AwayTeam'] == team)) & 
            pd.notna(df['FTHG'])
        ].tail(last_n)
        
        if len(team_matches) == 0:
            return {'form': 0.5, 'goals_scored': 1.0, 'goals_conceded': 1.0}
        
        points = 0
        goals_scored = 0
        goals_conceded = 0
        
        for _, row in team_matches.iterrows():
            is_home = row['HomeTeam'] == team
            goals_for = row['FTHG'] if is_home else row['FTAG']
            goals_against = row['FTAG'] if is_home else row['FTHG']
            
            goals_scored += goals_for
            goals_conceded += goals_against
            
            if goals_for > goals_against:
                points += 3
            elif goals_for == goals_against:
                points += 1
        
        max_points = last_n * 3
        form = points / max_points if max_points > 0 else 0.5
        
        return {
            'form': form,
            'goals_scored': goals_scored / len(team_matches),
            'goals_conceded': goals_conceded / len(team_matches)
        }
    
    @staticmethod
    def detect_dropping_odds(row: pd.Series) -> bool:
        home_open = row.get('B365H', None)
        home_close = row.get('PSH', None)
        
        if pd.notna(home_open) and pd.notna(home_close):
            try:
                drop_pct = (float(home_open) - float(home_close)) / float(home_open)
                return drop_pct > 0.05
            except:
                return False
        
        return False

# МОДЕЛИ
class HybridModel:
    def __init__(self):
        self.elo_ratings = {}
        self.xgb_model = None
        self.is_trained = False
    
    def update_elo(self, team1: str, team2: str, score1: float, score2: float, k: float = 32):
        r1 = self.elo_ratings.get(team1, 1500)
        r2 = self.elo_ratings.get(team2, 1500)
        
        e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        e2 = 1 - e1
        
        s1 = 1 if score1 > score2 else (0.5 if score1 == score2 else 0)
        s2 = 1 - s1
        
        self.elo_ratings[team1] = r1 + k * (s1 - e1)
        self.elo_ratings[team2] = r2 + k * (s2 - e2)
    
    def train(self, df: pd.DataFrame):
        if 'HomeTeam' not in df.columns or len(df) < 100:
            return
        
        self.is_trained = True
    
    def predict(self, home: str, away: str, df: pd.DataFrame) -> tuple:
        home_elo = self.elo_ratings.get(home, 1500)
        away_elo = self.elo_ratings.get(away, 1500)
        
        p_home_elo = 1 / (1 + 10 ** ((away_elo - home_elo) / 400))
        p_away_elo = 1 / (1 + 10 ** ((home_elo - away_elo) / 400))
        p_draw_elo = 0.25 * (1 - abs(p_home_elo - p_away_elo))
        
        total = p_home_elo + p_draw_elo + p_away_elo
        p_home_elo /= total
        p_draw_elo /= total
        p_away_elo /= total
        
        home_form = DataManager.calculate_form(df, home, 5)
        away_form = DataManager.calculate_form(df, away, 5)
        
        home_lambda = max(0.5, home_form['goals_scored'] * 1.1)
        away_lambda = max(0.5, away_form['goals_scored'] * 0.9)
        
        matrix = np.zeros((6, 6))
        for h in range(6):
            for a in range(6):
                matrix[h, a] = poisson.pmf(h, home_lambda) * poisson.pmf(a, away_lambda)
        
        p_home_poisson = np.sum(np.tril(matrix, -1))
        p_draw_poisson = np.sum(np.diagonal(matrix))
        p_away_poisson = np.sum(np.triu(matrix, 1))
        
        total = p_home_poisson + p_draw_poisson + p_away_poisson
        if total > 0:
            p_home_poisson /= total
            p_draw_poisson /= total
            p_away_poisson /= total
        
        p_home = 0.4 * p_home_elo + 0.6 * p_home_poisson
        p_draw = 0.4 * p_draw_elo + 0.6 * p_draw_poisson
        p_away = 0.4 * p_away_elo + 0.6 * p_away_poisson
        
        total = p_home + p_draw + p_away
        return p_home/total, p_draw/total, p_away/total

# КЕЛЛИ
class KellyCriterion:
    @staticmethod
    def calculate(probability: float, odds: float, bankroll: float, fraction: float = 0.25) -> float:
        if probability <= 0 or odds <= 1:
            return 0.0
        
        b = odds - 1
        q = 1 - probability
        kelly_fraction = (b * probability - q) / b
        
        adjusted_fraction = max(0, kelly_fraction * fraction)
        adjusted_fraction = min(adjusted_fraction, 0.05)
        
        return round(bankroll * adjusted_fraction, 2)

# УПРАВЛЕНИЕ ДАННЫМИ
def load_history() -> dict:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "bank": 10000.0,
        "bets": [],
        "kelly_fraction": 0.25,
        "statistics": {"total_bets": 0, "won": 0, "lost": 0, "profit": 0.0},
        "forecasts": [],
        "backtest": None
    }

def save_history(data: dict):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ГЛАВНОЕ ПРИЛОЖЕНИЕ
if "app_data" not in st.session_state:
    st.session_state.app_data = load_history()

st.markdown('<div class="main-header">🎯 Pro Betting AI v3.0</div>', unsafe_allow_html=True)

# Боковая панель
st.sidebar.header("⚙️ Настройки")
bank = st.session_state.app_data["bank"]
st.sidebar.metric("💰 Банкролл", f"{bank:.2f} у.е.")

kelly_frac = st.sidebar.slider("Дробь Келли", 0.1, 0.5, float(st.session_state.app_data.get("kelly_fraction", 0.25)), 0.05)
st.session_state.app_data["kelly_fraction"] = kelly_frac

min_ev = st.sidebar.slider("Минимальный EV (%)", 1, 10, 3, 1) / 100

if st.sidebar.button("🔄 Сброс"):
    st.session_state.app_data = {
        "bank": 10000.0,
        "bets": [],
        "kelly_fraction": 0.25,
        "statistics": {"total_bets": 0, "won": 0, "lost": 0, "profit": 0.0},
        "forecasts": [],
        "backtest": None
    }
    save_history(st.session_state.app_data)
    st.rerun()

# Вкладки
tab1, tab2, tab3 = st.tabs(["🎯 Прогнозы", "📋 Ставки", " Статистика"])

# ВКЛАДКА 1: ПРОГНОЗЫ
with tab1:
    st.markdown("### 🎯 Анализ матчей с формой команд")
    
    available_leagues = list(LEAGUES_DICT.values())
    default_league = "🏴󠁢󠁥󠁿 Англия (АПЛ)"
    
    selected_leagues = st.multiselect(
        "Выберите лиги:",
        options=available_leagues,
        default=[default_league] if default_league in available_leagues else available_leagues[:1]
    )
    
    days = st.slider("Период анализа (дни)", 1, 14, 7)
    today = pd.Timestamp.now().normalize()
    future_limit = today + pd.Timedelta(days=days)
    
    st.info(f"📅 Диапазон: {today.strftime('%d.%m.%Y')} - {future_limit.strftime('%d.%m.%Y')}")
    
    if st.button("🚀 Запустить анализ", type="primary"):
        if not selected_leagues:
            st.warning("Выберите хотя бы одну лигу!")
        else:
            with st.spinner("Загрузка данных..."):
                df = DataManager.load_football_data_csv(selected_leagues)
                
                if len(df) == 0:
                    st.error("Не удалось загрузить данные. Проверьте выбранные лиги.")
                    st.stop()
                
                st.success(f"✅ Загружено {len(df)} матчей")
            
            with st.spinner("Обучение модели..."):
                model = HybridModel()
                
                if 'FTHG' in df.columns:
                    past = df[pd.notna(df['FTHG'])]
                    for _, row in past.iterrows():
                        model.update_elo(
                            row.get('HomeTeam', ''),
                            row.get('AwayTeam', ''),
                            float(row.get('FTHG', 0)),
                            float(row.get('FTAG', 0))
                        )
                
                model.train(past if 'FTHG' in df.columns else df)
                
                st.success("✅ Модель обучена")
            
            with st.spinner("Генерация прогнозов..."):
                if 'Date' in df.columns:
                    df['MatchDate'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
                    future = df[
                        (df['MatchDate'] >= today) & 
                        (df['MatchDate'] <= future_limit) & 
                        (pd.isna(df['FTHG']) if 'FTHG' in df.columns else True)
                    ]
                else:
                    future = df
                
                forecasts = []
                bank = st.session_state.app_data["bank"]
                
                for _, row in future.iterrows():
                    home = row.get('HomeTeam', '')
                    away = row.get('AwayTeam', '')
                    
                    if not home or not away or pd.isna(home) or pd.isna(away):
                        continue
                    
                    try:
                        p_home, p_draw, p_away = model.predict(str(home), str(away), df)
                        
                        home_odd = float(row.get('B365H', row.get('PSH', 1.95)))
                        draw_odd = float(row.get('B365D', row.get('PSD', 3.40)))
                        away_odd = float(row.get('B365A', row.get('PSA', 3.10)))
                        
                        options = [
                            ("П1", p_home, home_odd),
                            ("X", p_draw, draw_odd),
                            ("П2", p_away, away_odd)
                        ]
                        
                        best = max(options, key=lambda x: x[1] * x[2])
                        pick, prob, odd = best
                        
                        ev = (prob * odd) - 1.0
                        
                        is_dropping = DataManager.detect_dropping_odds(row)
                        
                        if ev > min_ev:
                            stake = KellyCriterion.calculate(prob, odd, bank, kelly_frac)
                            
                            if stake > 0:
                                form_home = DataManager.calculate_form(df, str(home), 5)
                                form_away = DataManager.calculate_form(df, str(away), 5)
                                
                                forecasts.append({
                                    "league": row.get('League', ''),
                                    "match": f"{home} vs {away}",
                                    "date": row.get('MatchDate', today).strftime('%d.%m') if 'MatchDate' in df.columns else today.strftime('%d.%m'),
                                    "pick": pick,
                                    "probability": prob,
                                    "odds": odd,
                                    "ev": ev,
                                    "stake": stake,
                                    "dropping": is_dropping,
                                    "home_form": form_home['form'],
                                    "away_form": form_away['form']
                                })
                    except Exception as e:
                        continue
                
                st.session_state.app_data["forecasts"] = forecasts
                save_history(st.session_state.app_data)
                st.success(f"✅ Найдено {len(forecasts)} ставок с +EV > {min_ev*100:.0f}%")
                st.rerun()
    
    forecasts = st.session_state.app_data.get("forecasts", [])
    
    if forecasts:
        st.markdown(f"### 📊 Найдено {len(forecasts)} выгодных ставок")
        
        for f in forecasts:
            ev_class = "ev-positive" if f["ev"] > 0 else "ev-negative"
            dropping_badge = " 📉 DROPPING" if f["dropping"] else ""
            
            st.markdown(f"""
                <div class="forecast-card">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                        <span style="background: #38bdf8; padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; color: white; font-weight: 700;">
                            {f["league"]}
                        </span>
                        <span style="color: #94a3b8;">{f["date"]}{dropping_badge}</span>
                    </div>
                    
                    <div style="font-size: 1.2rem; font-weight: 700; color: #f8fafc; margin-bottom: 8px;">
                        ⚽ {f["match"]}
                    </div>
                    
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 10px;">
                        <div>
                            <div style="color: #94a3b8; font-size: 0.75rem;">Прогноз</div>
                            <div style="color: #facc15; font-weight: 700; font-size: 1.1rem;">{f["pick"]}</div>
                        </div>
                        <div>
                            <div style="color: #94a3b8; font-size: 0.75rem;">Вероятность</div>
                            <div style="color: #4ade80; font-weight: 700;">{f["probability"]*100:.1f}%</div>
                        </div>
                        <div>
                            <div style="color: #94a3b8; font-size: 0.75rem;">Коэффициент</div>
                            <div style="color: #facc15; font-weight: 700;">{f["odds"]:.2f}</div>
                        </div>
                        <div>
                            <div style="color: #94a3b8; font-size: 0.75rem;">EV</div>
                            <div class="{ev_class}">{f["ev"]*100:.1f}%</div>
                        </div>
                    </div>
                    
                    <div style="border-top: 1px solid rgba(255,255,255,0.1); padding-top: 10px; display: flex; justify-content: space-between;">
                        <div>
                            <span style="color: #94a3b8; font-size: 0.85rem;">Ставка (Келли):</span>
                            <span style="color: #facc15; font-weight: 700; margin-left: 8px;">{f["stake"]:.2f} у.е.</span>
                        </div>
                        <div style="color: #64748b; font-size: 0.75rem;">
                            Форма: {f["home_form"]*100:.0f}% vs {f["away_form"]*100:.0f}%
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Нет прогнозов. Выберите лиги и нажмите «Запустить анализ».")

# ВКЛАДКА 2: СТАВКИ
with tab2:
    st.markdown("###  Активные ставки")
    
    bets = st.session_state.app_data.get("bets", [])
    
    if not bets:
        st.info("Нет активных ставок")
    else:
        pending = [b for b in bets if b.get("status") == "pending"]
        
        if pending:
            st.markdown(f"#### ⏳ В ожидании ({len(pending)})")
            
            for idx, bet in enumerate(pending):
                st.markdown(f"""
                    <div class="bet-card-pending">
                        <div style="font-size: 1.1rem; font-weight: 700; color: #f8fafc;">
                            ⚽ {bet.get("match", "")}
                        </div>
                        <div style="color: #94a3b8; margin-top: 5px;">
                            Прогноз: <b style="color: #4ade80;">{bet.get("pick", "")}</b> @ {bet.get("odds", 0):.2f} | 
                            Ставка: <b style="color: #facc15;">{bet.get("stake", 0):.2f} у.е.</b>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                cols = st.columns(2)
                with cols[0]:
                    if st.button(f"✅ Выиграла", key=f"win_{idx}"):
                        bet["status"] = "won"
                        profit = bet.get("stake", 0) * bet.get("odds", 0)
                        st.session_state.app_data["bank"] += profit
                        st.session_state.app_data["statistics"]["won"] += 1
                        st.session_state.app_data["statistics"]["profit"] += profit - bet.get("stake", 0)
                        save_history(st.session_state.app_data)
                        st.success(f"+{profit:.2f} у.е.")
                        st.rerun()
                
                with cols[1]:
                    if st.button(f"❌ Проиграла", key=f"loss_{idx}"):
                        bet["status"] = "lost"
                        st.session_state.app_data["statistics"]["lost"] += 1
                        st.session_state.app_data["statistics"]["profit"] -= bet.get("stake", 0)
                        save_history(st.session_state.app_data)
                        st.error(f"-{bet.get('stake', 0):.2f} у.е.")
                        st.rerun()
        
        completed = [b for b in bets if b.get("status") in ["won", "lost"]]
        if completed:
            st.markdown(f"#### ✅ Завершенные ({len(completed)})")
            for bet in completed[-10:]:
                status_emoji = "🎉" if bet.get("status") == "won" else "😢"
                card_cls = "bet-card-won" if bet.get("status") == "won" else "bet-card-lost"
                
                st.markdown(f"""
                    <div class="{card_cls}">
                        <div style="font-size: 1rem; font-weight: 700; color: #f8fafc;">
                            {status_emoji} {bet.get("match", "")} - {bet.get("pick", "")} @ {bet.get("odds", 0):.2f}
                        </div>
                        <div style="color: #94a3b8; font-size: 0.85rem; margin-top: 5px;">
                            Ставка: {bet.get("stake", 0):.2f} у.е. | Результат: {bet.get("status", "").upper()}
                        </div>
                    </div>
                """, unsafe_allow_html=True)

# ВКЛАДКА 3: СТАТИСТИКА
with tab3:
    st.markdown("### 📊 Статистика и эффективность")
    
    stats = st.session_state.app_data.get("statistics", {})
    bank = st.session_state.app_data["bank"]
    initial_bank = 10000.0
    
    total_bets = stats.get("total_bets", 0)
    won = stats.get("won", 0)
    lost = stats.get("lost", 0)
    profit = stats.get("profit", 0.0)
    
    win_rate = (won / total_bets * 100) if total_bets > 0 else 0
    roi = (profit / initial_bank * 100) if initial_bank > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Банкролл", f"{bank:.2f} у.е.", f"{bank - initial_bank:+.2f}")
    
    with col2:
        st.metric("📊 Всего ставок", total_bets)
    
    with col3:
        st.metric("🎯 Win Rate", f"{win_rate:.1f}%")
    
    with col4:
        st.metric("📈 ROI", f"{roi:.2f}%")
    
    st.markdown("---")
    
    if total_bets > 0:
        st.markdown(f"""
            <div class="metric-card">
                <h4 style="color: #f8fafc; margin-bottom: 15px;">📊 Детальная статистика</h4>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                    <div>
                        <div style="color: #94a3b8; font-size: 0.85rem;">Выиграно</div>
                        <div style="color: #10b981; font-size: 1.5rem; font-weight: 700;">{won}</div>
                    </div>
                    <div>
                        <div style="color: #94a3b8; font-size: 0.85rem;">Проиграно</div>
                        <div style="color: #ef4444; font-size: 1.5rem; font-weight: 700;">{lost}</div>
                    </div>
                    <div>
                        <div style="color: #94a3b8; font-size: 0.85rem;">Общая прибыль</div>
                        <div style="color: {'#10b981' if profit > 0 else '#ef4444'}; font-size: 1.5rem; font-weight: 700;">{profit:+.2f} у.е.</div>
                    </div>
                    <div>
                        <div style="color: #94a3b8; font-size: 0.85rem;">Текущий банк</div>
                        <div style="color: #38bdf8; font-size: 1.5rem; font-weight: 700;">{bank:.2f} у.е.</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Сделайте первые ставки для отображения статистики")
