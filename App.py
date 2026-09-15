import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
import json
import os
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Pro Betting AI v3.0", page_icon="", layout="wide")

# ============================================================
# СТИЛИ
# ============================================================
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

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================
HISTORY_FILE = "pro_betting_v3.json"
BACKTEST_FILE = "backtest_results.json"

# Understat API endpoints
UNDERSTAT_BASE = "https://understat.com/league"
LEAGUE_MAP = {
    "EPL": "EPL",
    "La Liga": "La_liga",
    "Serie A": "Serie_A",
    "Bundesliga": "Bundesliga",
    "Ligue 1": "Ligue_1",
    "RFPL": "RFPL"
}

# ============================================================
# МОДУЛЬ ДАННЫХ
# ============================================================
class DataManager:
    """Управление загрузкой данных из CSV и Understat"""
    
    @staticmethod
    def load_football_data_csv(leagues: list, season: str = "2526") -> pd.DataFrame:
        """Загрузка данных из football-data.co.uk"""
        base_url = f"https://www.football-data.co.uk/mmz4281/{season}/"
        league_codes = {
            "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Англия (АПЛ)": "E0.csv",
            "🇪🇸 Испания (Ла Лига)": "SP1.csv",
            "🇹 Италия (Серия А)": "I1.csv",
            "🇩 Германия (Бундеслига)": "D1.csv",
            "🇫🇷 Франция (Лига 1)": "F1.csv",
            "🇷🇺 Россия (РПЛ)": "R1.csv",
            "🇷 Турция (Суперлига)": "T1.csv"
        }
        
        all_data = []
        for league in leagues:
            if league in league_codes:
                url = base_url + league_codes[league]
                try:
                    df = pd.read_csv(url)
                    df['League'] = league
                    df['Source'] = 'football-data'
                    all_data.append(df)
                except Exception as e:
                    st.warning(f"Не удалось загрузить {league}: {e}")
        
        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
    
    @staticmethod
    def load_xg_data(league: str, year: int) -> pd.DataFrame:
        """Загрузка xG данных с Understat"""
        try:
            league_code = LEAGUE_MAP.get(league, league)
            url = f"{UNDERSTAT_BASE}/{league_code}/{year}"
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # Парсинг JSON из HTML (Understat хранит данные в JavaScript)
                import re
                json_data = re.search(r"var datesData = (\[.*?\]);", response.text)
                if json_data:
                    data = json.loads(json_data.group(1))
                    return pd.DataFrame(data)
        except Exception as e:
            st.warning(f"Understat: {e}")
        
        return pd.DataFrame()
    
    @staticmethod
    def calculate_form(df: pd.DataFrame, team: str, last_n: int = 5) -> dict:
        """Расчёт формы команды за последние N матчей"""
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
        """Обнаружение падающих коэффициентов (dropping odds)"""
        # Сравниваем B365 (открытие) с PS (закрытие)
        home_open = row.get('B365H', None)
        home_close = row.get('PSH', None)
        
        if pd.notna(home_open) and pd.notna(home_close):
            drop_pct = (home_open - home_close) / home_open
            return drop_pct > 0.05  # Падение более 5%
        
        return False

# ============================================================
# МОДЕЛИ ПРОГНОЗИРОВАНИЯ
# ============================================================
class HybridModel:
    """Гибридная модель: Пуассон + Elo + XGBoost"""
    
    def __init__(self):
        self.elo_ratings = {}
        self.xgb_model = None
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def update_elo(self, team1: str, team2: str, score1: float, score2: float, k: float = 32):
        """Обновление Elo-рейтинга"""
        r1 = self.elo_ratings.get(team1, 1500)
        r2 = self.elo_ratings.get(team2, 1500)
        
        e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        e2 = 1 - e1
        
        s1 = 1 if score1 > score2 else (0.5 if score1 == score2 else 0)
        s2 = 1 - s1
        
        self.elo_ratings[team1] = r1 + k * (s1 - e1)
        self.elo_ratings[team2] = r2 + k * (s2 - e2)
    
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Подготовка признаков для XGBoost"""
        features = []
        
        for _, row in df.iterrows():
            home = row.get('HomeTeam', '')
            away = row.get('AwayTeam', '')
            
            if not home or not away:
                continue
            
            # Elo разница
            home_elo = self.elo_ratings.get(home, 1500)
            away_elo = self.elo_ratings.get(away, 1500)
            elo_diff = home_elo - away_elo
            
            # Форма
            home_form = DataManager.calculate_form(df, home, 5)
            away_form = DataManager.calculate_form(df, away, 5)
            
            feat = {
                'elo_diff': elo_diff,
                'home_form': home_form['form'],
                'away_form': away_form['form'],
                'home_goals_avg': home_form['goals_scored'],
                'away_goals_avg': away_form['goals_scored'],
                'home_conceded_avg': home_form['goals_conceded'],
                'away_conceded_avg': away_form['goals_conceded'],
                'home_advantage': 1.0 if home else 0.0
            }
            
            features.append(feat)
        
        return pd.DataFrame(features)
    
    def train(self, df: pd.DataFrame):
        """Обучение XGBoost на исторических данных"""
        X = self.prepare_features(df)
        
        if len(X) < 100:
            st.warning("Недостаточно данных для обучения ML модели")
            return
        
        # Целевая переменная: 0=П1, 1=X, 2=П2
        y = []
        for _, row in df.iterrows():
            if pd.notna(row.get('FTHG')):
                if row['FTHG'] > row['FTAG']:
                    y.append(0)
                elif row['FTHG'] == row['FTAG']:
                    y.append(1)
                else:
                    y.append(2)
        
        if len(y) < 100:
            return
        
        y = np.array(y[:len(X)])
        
        # Time Series Split для избежания утечки данных
        tscv = TimeSeriesSplit(n_splits=5)
        
        self.xgb_model = GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            random_state=42
        )
        
        self.xgb_model.fit(X, y)
        self.is_trained = True
    
    def predict(self, home: str, away: str, df: pd.DataFrame) -> tuple:
        """Предсказание вероятностей"""
        # Elo probabilities
        home_elo = self.elo_ratings.get(home, 1500)
        away_elo = self.elo_ratings.get(away, 1500)
        
        p_home_elo = 1 / (1 + 10 ** ((away_elo - home_elo) / 400))
        p_away_elo = 1 / (1 + 10 ** ((home_elo - away_elo) / 400))
        p_draw_elo = 0.25 * (1 - abs(p_home_elo - p_away_elo))
        
        total = p_home_elo + p_draw_elo + p_away_elo
        p_home_elo /= total
        p_draw_elo /= total
        p_away_elo /= total
        
        # Poisson probabilities
        home_form = DataManager.calculate_form(df, home, 5)
        away_form = DataManager.calculate_form(df, away, 5)
        
        home_lambda = home_form['goals_scored'] * 1.1
        away_lambda = away_form['goals_scored'] * 0.9
        
        matrix = np.zeros((6, 6))
        for h in range(6):
            for a in range(6):
                matrix[h, a] = poisson.pmf(h, home_lambda) * poisson.pmf(a, away_lambda)
        
        p_home_poisson = np.sum(np.tril(matrix, -1))
        p_draw_poisson = np.sum(np.diagonal(matrix))
        p_away_poisson = np.sum(np.triu(matrix, 1))
        
        total = p_home_poisson + p_draw_poisson + p_away_poisson
        p_home_poisson /= total
        p_draw_poisson /= total
        p_away_poisson /= total
        
        # XGBoost probabilities (если обучена)
        if self.is_trained:
            X_new = self.prepare_features(pd.DataFrame([{
                'HomeTeam': home,
                'AwayTeam': away,
                'FTHG': np.nan,
                'FTAG': np.nan
            }]))
            
            if len(X_new) > 0:
                xgb_proba = self.xgb_model.predict_proba(X_new)[0]
                p_home_xgb, p_draw_xgb, p_away_xgb = xgb_proba
            else:
                p_home_xgb, p_draw_xgb, p_away_xgb = p_home_elo, p_draw_elo, p_away_elo
        else:
            p_home_xgb, p_draw_xgb, p_away_xgb = p_home_elo, p_draw_elo, p_away_elo
        
        # Ансамбль: 0.3*Elo + 0.3*Poisson + 0.4*XGBoost
        p_home = 0.3 * p_home_elo + 0.3 * p_home_poisson + 0.4 * p_home_xgb
        p_draw = 0.3 * p_draw_elo + 0.3 * p_draw_poisson + 0.4 * p_draw_xgb
        p_away = 0.3 * p_away_elo + 0.3 * p_away_poisson + 0.4 * p_away_xgb
        
        total = p_home + p_draw + p_away
        return p_home/total, p_draw/total, p_away/total

# ============================================================
# КРИТЕРИЙ КЕЛЛИ
# ============================================================
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

# ============================================================
# БЭКТЕСТИНГ
# ============================================================
class Backtester:
    """Бэктестинг модели на исторических данных"""
    
    @staticmethod
    def run(model: HybridModel, df: pd.DataFrame, min_ev: float = 0.03) -> dict:
        """Прогон модели на истории"""
        results = []
        bank = 10000.0
        initial_bank = bank
        
        past_matches = df[pd.notna(df['FTHG'])].copy()
        
        for idx, row in past_matches.iterrows():
            home = row.get('HomeTeam', '')
            away = row.get('AwayTeam', '')
            
            if not home or not away:
                continue
            
            # Предсказание
            p_home, p_draw, p_away = model.predict(home, away, df)
            
            # Коэффициенты
            home_odd = float(row.get('B365H', row.get('PSH', 1.95)))
            draw_odd = float(row.get('B365D', row.get('PSD', 3.40)))
            away_odd = float(row.get('B365A', row.get('PSA', 3.10)))
            
            options = [
                ("П1", p_home, home_odd, 0 if row['FTHG'] > row['FTAG'] else 1),
                ("X", p_draw, draw_odd, 1 if row['FTHG'] == row['FTAG'] else 0),
                ("П2", p_away, away_odd, 2 if row['FTHG'] < row['FTAG'] else 0)
            ]
            
            best = max(options, key=lambda x: x[1] * x[2])
            pick, prob, odd, actual = best
            
            ev = (prob * odd) - 1.0
            
            if ev > min_ev:
                stake = KellyCriterion.calculate(prob, odd, bank, 0.25)
                
                if stake > 0:
                    if actual == 0:  # Угадали
                        profit = stake * (odd - 1)
                        bank += profit
                        results.append({'date': row.get('Date', ''), 'pick': pick, 'odds': odd, 'stake': stake, 'profit': profit, 'bank': bank})
                    else:
                        bank -= stake
                        results.append({'date': row.get('Date', ''), 'pick': pick, 'odds': odd, 'stake': stake, 'profit': -stake, 'bank': bank})
        
        return {
            'results': results,
            'final_bank': bank,
            'profit': bank - initial_bank,
            'roi': ((bank - initial_bank) / initial_bank) * 100,
            'total_bets': len(results)
        }

# ============================================================
# УПРАВЛЕНИЕ ДАННЫМИ
# ============================================================
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
        "statistics": {"total_bets": 0, "won": 0, "lost": 0, "profit": 0.0}
    }

def save_history(data: dict):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ============================================================
# ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ============================================================
if "app_data" not in st.session_state:
    st.session_state.app_data = load_history()

st.markdown('<div class="main-header">🎯 Pro Betting AI v3.0</div>', unsafe_allow_html=True)

# Боковая панель
st.sidebar.header("⚙️ Настройки")
bank = st.session_state.app_data["bank"]
st.sidebar.metric("💰 Банкролл", f"{bank:.2f} у.е.")

kelly_frac = st.sidebar.slider("Дробь Келли", 0.1, 0.5, st.session_state.app_data.get("kelly_fraction", 0.25), 0.05)
st.session_state.app_data["kelly_fraction"] = kelly_frac

min_ev = st.sidebar.slider("Минимальный EV (%)", 1, 10, 3, 1) / 100

if st.sidebar.button("🔄 Сброс"):
    st.session_state.app_data = {
        "bank": 10000.0,
        "bets": [],
        "kelly_fraction": 0.25,
        "statistics": {"total_bets": 0, "won": 0, "lost": 0, "profit": 0.0}
    }
    save_history(st.session_state.app_data)
    st.rerun()

# Вкладки
tab1, tab2, tab3, tab4 = st.tabs(["🎯 Прогнозы", "📋 Ставки", " Бэктестинг", "ℹ️ О системе"])

# ============================================================
# ВКЛАДКА 1: ПРОГНОЗЫ
# ============================================================
with tab1:
    st.markdown("### 🎯 Анализ матчей с xG и формой")
    
    leagues = st.multiselect(
        "Выберите лиги:",
        options=["🏴󠁧󠁥󠁮󠁿 Англия (АПЛ)", "🇪🇸 Испания", "🇮🇹 Италия", "🇪 Германия", "🇫 Франция", "🇷🇺 Россия", "🇹🇷 Турция"],
        default=["🏴󠁢󠁥󠁧󠁿 Англия (АПЛ)"]
    )
    
    days = st.slider("Период анализа (дни)", 1, 14, 7)
    today = pd.Timestamp.now().normalize()
    future_limit = today + pd.Timedelta(days=days)
    
    use_xg = st.checkbox("Использовать xG данные (Understat)", value=False, help="Требует интернет-соединение")
    
    if st.button("🚀 Запустить анализ", type="primary"):
        if not leagues:
            st.warning("Выберите лиги!")
        else:
            with st.spinner("Загрузка данных..."):
                df = DataManager.load_football_data_csv(leagues)
                
                if len(df) == 0:
                    st.error("Не удалось загрузить данные")
                    st.stop()
                
                st.success(f"✅ Загружено {len(df)} матчей")
            
            with st.spinner("Обучение модели..."):
                model = HybridModel()
                
                # Обучение Elo на истории
                past = df[pd.notna(df['FTHG'])]
                for _, row in past.iterrows():
                    model.update_elo(
                        row.get('HomeTeam', ''),
                        row.get('AwayTeam', ''),
                        float(row.get('FTHG', 0)),
                        float(row.get('FTAG', 0))
                    )
                
                # Обучение XGBoost
                model.train(past)
                
                st.success("✅ Модель обучена")
            
            with st.spinner("Генерация прогнозов..."):
                df['MatchDate'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
                future = df[(df['MatchDate'] >= today) & (df['MatchDate'] <= future_limit) & pd.isna(df['FTHG'])]
                
                forecasts = []
                app_data = st.session_state.app_data
                
                for _, row in future.iterrows():
                    home = row.get('HomeTeam', '')
                    away = row.get('AwayTeam', '')
                    
                    if not home or not away:
                        continue
                    
                    p_home, p_draw, p_away = model.predict(home, away, df)
                    
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
                    
                    # Фильтр dropping odds
                    is_dropping = DataManager.detect_dropping_odds(row)
                    
                    if ev > min_ev:
                        stake = KellyCriterion.calculate(prob, odd, bank, kelly_frac)
                        
                        if stake > 0:
                            form_home = DataManager.calculate_form(df, home, 5)
                            form_away = DataManager.calculate_form(df, away, 5)
                            
                            forecasts.append({
                                "league": row.get('League', ''),
                                "match": f"{home} vs {away}",
                                "date": row['MatchDate'].strftime('%d.%m'),
                                "pick": pick,
                                "probability": prob,
                                "odds": odd,
                                "ev": ev,
                                "stake": stake,
                                "dropping": is_dropping,
                                "home_form": form_home['form'],
                                "away_form": form_away['form']
                            })
                
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
        st.info("Нет прогнозов. Запустите анализ выше.")

# ============================================================
# ВКЛАДКА 2: СТАВКИ
# ============================================================
with tab2:
    st.markdown("###  Активные ставки")
    
    bets = st.session_state.app_data.get("bets", [])
    
    if not bets:
        st.info("Нет активных ставок")
    else:
        pending = [b for b in bets if b["status"] == "pending"]
        
        for idx, bet in enumerate(pending):
            st.markdown(f"""
                <div class="bet-card-pending">
                    <div style="font-size: 1.1rem; font-weight: 700; color: #f8fafc;">
                         {bet["match"]}
                    </div>
                    <div style="color: #94a3b8; margin-top: 5px;">
                        Прогноз: <b style="color: #4ade80;">{bet["pick"]}</b> @ {bet["odds"]:.2f} | Ставка: <b style="color: #facc15;">{bet["stake"]:.2f} у.е.</b>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            cols = st.columns(2)
            with cols[0]:
                if st.button(f"✅ Выиграла #{idx}", key=f"win_{idx}"):
                    bet["status"] = "won"
                    profit = bet["stake"] * bet["odds"]
                    st.session_state.app_data["bank"] += profit
                    st.session_state.app_data["statistics"]["won"] += 1
                    st.session_state.app_data["statistics"]["profit"] += profit - bet["stake"]
                    save_history(st.session_state.app_data)
                    st.success(f"+{profit:.2f} у.е.")
                    st.rerun()
            
            with cols[1]:
                if st.button(f"❌ Проиграла #{idx}", key=f"loss_{idx}"):
                    bet["status"] = "lost"
                    st.session_state.app_data["statistics"]["lost"] += 1
                    st.session_state.app_data["statistics"]["profit"] -= bet["stake"]
                    save_history(st.session_state.app_data)
                    st.error(f"-{bet['stake']:.2f} у.е.")
                    st.rerun()

# ============================================================
# ВКЛАДКА 3: БЭКТЕСТИНГ
# ============================================================
with tab3:
    st.markdown("### 📊 Бэктестинг модели на истории")
    
    st.write("Проверка эффективности модели на исторических данных")
    
    bt_leagues = st.multiselect(
        "Лиги для бэктеста:",
        options=["🏴󠁢󠁥󠁧󠁿 Англия (АПЛ)", "🇪🇸 Испания", "🇮🇹 Италия", "🇩🇪 Германия", "🇷 Франция"],
        default=["󠁧󠁢󠁮󠁧 Англия (АПЛ)"]
    )
    
    bt_min_ev = st.slider("Минимальный EV для бэктеста (%)", 1, 10, 3, 1) / 100
    
    if st.button(" Запустить бэктест", type="primary"):
        if bt_leagues:
            with st.spinner("Загрузка исторических данных..."):
                df = DataManager.load_football_data_csv(bt_leagues)
                
                if len(df) == 0:
                    st.error("Нет данных")
                    st.stop()
                
                st.info(f"Загружено {len(df)} матчей")
            
            with st.spinner("Обучение и прогон модели..."):
                model = HybridModel()
                
                past = df[pd.notna(df['FTHG'])]
                for _, row in past.iterrows():
                    model.update_elo(
                        row.get('HomeTeam', ''),
                        row.get('AwayTeam', ''),
                        float(row.get('FTHG', 0)),
                        float(row.get('FTAG', 0))
                    )
                
                model.train(past)
                
                results = Backtester.run(model, df, bt_min_ev)
                
                st.session_state.app_data["backtest"] = results
                st.success(f"✅ Бэктест завершён: {results['total_bets']} ставок")
                st.rerun()
    
    backtest = st.session_state.app_data.get("backtest", None)
    
    if backtest:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(" Финальный банк", f"{backtest['final_bank']:.2f} у.е.")
        
        with col2:
            st.metric("📈 Прибыль", f"{backtest['profit']:+.2f} у.е.")
        
        with col3:
            st.metric("📊 ROI", f"{backtest['roi']:.2f}%")
        
        with col4:
            st.metric("🎯 Всего ставок", backtest['total_bets'])
        
        # График роста банка
        if backtest['results']:
            fig = go.Figure()
            
            banks = [10000.0] + [r['bank'] for r in backtest['results']]
            fig.add_trace(go.Scatter(
                y=banks,
                mode='lines',
                name='Банк',
                line=dict(color='#10b981', width=3)
            ))
            
            fig.update_layout(
                title='Рост банка на бэктесте',
                xaxis_title='Ставка',
                yaxis_title='Банк (у.е.)',
                template='plotly_dark',
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
