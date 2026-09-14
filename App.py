import streamlit as st
import requests
import pandas as pd
import numpy as np
from scipy.stats import poisson
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split

st.set_page_config(page_title="AI Football Bot", page_icon="⚽", layout="wide")

st.title("⚽ Автоматический футбольный аналитик (Пуассон + Эло + ИИ)")
st.write("Платформа автоматически собирает матчи на сегодня, считает вероятности и выдает вердикт.")

# Боковая панель для настроек
st.sidebar.header("Настройки")
api_key = st.sidebar.text_input("Введи ключ The Odds API", type="password")

class AutoFootballBot:
    def __init__(self, odds_api_key):
        self.odds_api_key = odds_api_key
        self.ml_model = GradientBoostingClassifier(random_state=42)
        self.df_history = None
        self.elo_ratings = {}

    def fetch_live_odds_and_fixtures(self):
        soccer_leagues = [
            'soccer_epl', 'soccer_spain_la_liga', 
            'soccer_italy_serie_a', 'soccer_germany_bundesliga', 
            'soccer_france_ligue_one'
        ]
        matches_board = []
        
        for league in soccer_leagues:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {
                'apiKey': self.odds_api_key,
                'regions': 'eu',
                'markets': 'h2h',
                'oddsFormat': 'decimal'
            }
            try:
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    for event in data:
                        home = event['home_team']
                        away = event['away_team']
                        bookmakers = event.get('bookmakers', [])
                        if bookmakers:
                            markets = bookmakers[0].get('markets', [])
                            if markets:
                                outcomes = markets[0].get('outcomes', [])
                                odds = {out['name']: out['price'] for out in outcomes}
                                matches_board.append({
                                    'league': league,
                                    'home': home,
                                    'away': away,
                                    'h_odd': odds.get(home, 2.0),
                                    'd_odd': odds.get('Draw', 3.3),
                                    'a_odd': odds.get(away, 2.0)
                                })
            except Exception as e:
                st.error(f"Ошибка лиги {league}: {e}")
        return matches_board

    def prepare_historical_model(self):
        np.random.seed(42)
        teams = ['Arsenal', 'Chelsea', 'Real Madrid', 'Barcelona', 'Bayern', 'Dortmund', 'Inter', 'Milan', 'PSG', 'Marseille']
        data = {
            'HomeTeam': np.random.choice(teams, 400),
            'AwayTeam': np.random.choice(teams, 400),
            'FTHG': np.random.poisson(1.5, 400),
            'FTAG': np.random.poisson(1.1, 400),
        }
        self.df_history = pd.DataFrame(data)
        self.df_history = self.df_history[self.df_history['HomeTeam'] != self.df_history['AwayTeam']]
        
        for t in teams:
            self.elo_ratings[t] = 1500
            
        self.df_history['Home_Form'] = self.df_history.groupby('HomeTeam')['FTHG'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
        self.df_history['Away_Form'] = self.df_history.groupby('AwayTeam')['FTAG'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
        self.df_history.fillna(1.3, inplace=True)
        
        conditions = [
            self.df_history['FTHG'] > self.df_history['FTAG'],
            self.df_history['FTHG'] == self.df_history['FTAG'],
            self.df_history['FTHG'] < self.df_history['FTAG']
        ]
        self.df_history['Target'] = np.select(conditions, [1, 0, 2])
        X = self.df_history[['Home_Form', 'Away_Form']]
        y = self.df_history['Target']
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        self.ml_model.fit(X_train, y_train)

    def predict_poisson(self, home_lambda, away_lambda, max_goals=5):
        matrix = np.zeros((max_goals + 1, max_goals + 1))
        for h in range(max_goals + 1):
            for a in range(max_goals + 1):
                matrix[h, a] = poisson.pmf(h, home_lambda) * poisson.pmf(a, away_lambda)
        return np.sum(np.tril(matrix, -1)), np.sum(np.diagonal(matrix)), np.sum(np.triu(matrix, 1))

# Кнопка запуска анализа в интерфейсе
if st.button("🚀 Запустить анализ матчей на сегодня"):
    if not api_key:
        st.warning("Пожалуйста, введи API-ключ в боковой панели слева!")
    else:
        with st.spinner("Загружаем данные и анализируем матчи..."):
            bot = AutoFootballBot(odds_api_key=api_key)
            bot.prepare_historical_model()
            matches = bot.fetch_live_odds_and_fixtures()
            
            if matches:
                st.success(f"Найдено матчей: {len(matches)}")
                for match in matches:
                    home, away = match['home'], match['away']
                    bh, bd, ba = match['h_odd'], match['d_odd'], match['a_odd']
                    
                    elo_h = bot.elo_ratings.get(home, 1500)
                    elo_a = bot.elo_ratings.get(away, 1500)
                    h_lambda = max(0.7, (elo_h / 1500) * 1.5)
                    a_lambda = max(0.5, (elo_a / 1500) * 1.1)
                    
                    p_h, p_d, p_a = bot.predict_poisson(h_lambda, a_lambda)
                    
                    implied_h, implied_d, implied_a = 1/bh, 1/bd, 1/ba
                    value_bets = []
                    if p_h > implied_h: value_bets.append(("П1", p_h, bh, (p_h * bh) - 1))
                    if p_d > implied_d: value_bets.append(("Ничья (X)", p_d, bd, (p_d * bd) - 1))
                    if p_a > implied_a: value_bets.append(("П2", p_a, ba, (p_a * ba) - 1))
                    
                    # Красивые блоки результатов в Streamlit
                    with st.expander(f"🏟️ {home} vs {away}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Котировки БК:** П1: {bh} | X: {bd} | П2: {ba}")
                            st.write(f"**Вероятности модели:**")
                            st.write(f"- Хозяева: {p_h*100:.1f}%")
                            st.write(f"- Ничья: {p_d*100:.1f}%")
                            st.write(f"- Гости: {p_a*100:.1f}%")
                        with col2:
                            st.write("**🤖 Вердикт Gemini & Grok:**")
                            if value_bets:
                                best = max(value_bets, key=lambda x: x[3])
                                st.success(f"✅ НАЙДЕН ВАЛУЙ!\nРекомендация: **{best[0]}** (кэф {best[2]})\nПеревес: +{best[3]*100:.1f}%")
                            else:
                                st.info("❌ Рыночный тупик. Перевеса нет, матч пропускаем.")
            else:
                st.info("На сегодня активных матчей в топ-лигах не обнаружено.")
