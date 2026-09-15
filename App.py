import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
import json
import os
import requests
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

LEAGUE_MAP = {
    "EPL": "EPL",
    "La Liga": "La_liga",
    "Serie A": "Serie_A",
    "Bundesliga": "Bundesliga",
    "Ligue 1": "Ligue_1",
    "RFPL": "RFPL"
}

# МОДУЛЬ ДАННЫХ
class DataManager:
    @staticmethod
    def load_football_data_csv(leagues: list, season: str = "2526") -> pd.DataFrame:
        base_url = f"https://www.football-data.co.uk/mmz4281/{season}/"
        league_codes = {
            "🏴󠁢󠁥󠁧󠁿 Англия (АПЛ)": "E0.csv",
            "🇪🇸 Испания (Ла Лига)": "SP1.csv",
            "🇹 Италия (Серия А)": "I1.csv",
            "🇩🇪 Германия (Бундеслига)": "D1.csv",
            "🇫🇷 Франция (Лига 1)": "F1.csv",
            "🇷🇺 Россия (РПЛ)": "R1.csv",
            "🇹🇷 Турция (Суперлига)": "T1.csv"
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
    def calculate_form(df: pd.DataFrame, team: str, last_n: int = 5) -> dict:
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
            drop_pct = (home_open - home_close) / home_open
            return drop_pct > 0.05
        
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
        
        e1 = 1 / (1
