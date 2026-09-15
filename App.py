import streamlit as st
import requests
import json
import os
from datetime import datetime, timedelta
import math
import numpy as np
from collections import defaultdict

st.set_page_config(page_title="Football Betting AI Expert Pro", page_icon="🚀", layout="wide")

HISTORY_FILE = "betting_expert_data.json"

LEAGUE_CODES = {
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Англия (АПЛ)": "PL",
    "🇪🇸 Испания (Ла Лига)": "PD",
    "🇮🇹 Италия (Серия А)": "SA",
    "🇩🇪 Германия (Бундеслига)": "BL1",
    "🇫🇷 Франция (Лига 1)": "FL1",
    "🇪🇺 Лига Чемпионов": "CL",
    "🇪🇺 Лига Европы": "EL",
    "🇳🇱 Нидерланды (Эредивизи)": "DED",
    "🇵🇹 Португалия (Примейра)": "PPL",
    "🇧🇷 Бразилия (Серия А)": "BSA",
    "🌎 Кубок Либертадорес": "CLI"
}

# ============================================================
# МОЩНЫЙ ДВИЖОК АНАЛИЗА
# ============================================================

class AdvancedAnalyticsEngine:
    """Профессиональный движок для анализа матчей"""
    
    def __init__(self):
        self.elo_ratings = {}
        self.team_stats = defaultdict(lambda: {
            'home_goals_scored': [], 'home_goals_conceded': [],
            'away_goals_scored': [], 'away_goals_conceded': [],
            'recent_form': [], 'h2h': []
        })
        
    def update_from_match(self, home_team, away_team, home_goals, away_goals, is_recent=True):
        """Обновление статистики после матча"""
        # Elo обновление с home advantage
        r_home = self.elo_ratings.get(home_team, 1500)
        r_away = self.elo_ratings.get(away_team, 1500)
        
        # Home advantage bonus
        r_home_adj = r_home + 65
        
        e_home = 1 / (1 + 10 ** ((r_away - r_home_adj) / 400))
        
        if home_goals > away_goals:
            s_home = 1.0
        elif home_goals == away_goals:
            s_home = 0.5
        else:
            s_home = 0.0
        
        k = 32
        self.elo_ratings[home_team] = r_home + k * (s_home - e_home)
        self.elo_ratings[away_team] = r_away + k * ((1 - s_home) - (1 - e_home))
        
        # Статистика голов
        stats = self.team_stats
        stats[home_team]['home_goals_scored'].append(home_goals)
        stats[home_team]['home_goals_conceded'].append(away_goals)
        stats[away_team]['away_goals_scored'].append(away_goals)
        stats[away_team]['away_goals_conceded'].append(home_goals)
        
        # Форма (последние 10 матчей)
        if is_recent:
            result_home = 3 if home_goals > away_goals else (1 if home_goals == away_goals else 0)
            result_away = 3 if away_goals > home_goals else (1 if home_goals == away_goals else 0)
            
            stats[home_team]['recent_form'].append(result_home)
            stats[away_team]['recent_form'].append(result_away)
            
            # Ограничиваем до 10 последних
            stats[home_team]['recent_form'] = stats[home_team]['recent_form'][-10:]
            stats[away_team]['recent_form'] = stats[away_team]['recent_form'][-10:]
    
    def get_team_strength(self, team, is_home=True):
        """Получение силы команды с учётом home/away"""
        stats = self.team_stats[team]
        
        if is_home:
            scored = stats['home_goals_scored']
            conceded = stats['home_goals_conceded']
        else:
            scored = stats['away_goals_scored']
            conceded = stats['away_goals_conceded']
        
        if not scored:
            return 1.3, 1.2  # Дефолтные значения
        
        avg_scored = sum(scored) / len(scored)
        avg_conceded = sum(conceded) / len(conceded)
        
        return avg_scored, avg_conceded
    
    def get_form_factor(self, team):
        """Фактор формы (0-1, где 1 = идеальная форма)"""
        recent = self.team_stats[team]['recent_form']
        if not recent:
            return 0.5
        
        # Взвешенное среднее (последние матчи важнее)
        weights = [1.5, 1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
        weights = weights[:len(recent)]
        
        weighted_sum = sum(r * w for r, w in zip(recent, weights))
        max_possible = sum(w * 3 for w in weights)
        
        return weighted_sum / max_possible if max_possible > 0 else 0.5
    
    def dixon_coles_prediction(self, home_team, away_team):
        """
        Dixon-Coles модель - профессиональная футбольная модель
        Учитывает:
        - Силу атаки/обороны
        - Home advantage
        - Low-score adjustment (коррекция для малых счётов)
        """
        # Сила команд
        home_attack, home_defense = self.get_team_strength(home_team, is_home=True)
        away_attack, away_defense = self.get_team_strength(away_team, is_home=False)
        
        # Форма
        home_form = self.get_form_factor(home_team)
        away_form = self.get_form_factor(away_team)
        
        # Elo разница
        elo_home = self.elo_ratings.get(home_team, 1500)
        elo_away = self.elo_ratings.get(away_team, 1500)
        elo_diff = (elo_home - elo_away) / 400
        
        # Базовые lambda (ожидаемые голы)
        # lambda_home = attack_home * defense_away * home_advantage * form_factor
        lambda_home = home_attack * (1 / max(0.5, away_defense)) * 1.25 * (0.7 + 0.6 * home_form)
        lambda_away = away_attack * (1 / max(0.5, home_defense)) * 0.95 * (0.7 + 0.6 * away_form)
        
        # Коррекция на основе Elo
        lambda_home *= (1 + 0.1 * elo_diff)
        lambda_away *= (1 - 0.1 * elo_diff)
        
        # Ограничения
        lambda_home = max(0.4, min(4.0, lambda_home))
        lambda_away = max(0.3, min(3.5, lambda_away))
        
        # Матрица вероятностей
        p_home, p_draw, p_away = 0, 0, 0
        
        for h in range(7):
            for a in range(7):
                p = self._poisson(lambda_home, h) * self._poisson(lambda_away, a)
                
                # Dixon-Coles correction для низких счётов
                if h == 0 and a == 0:
                    p *= 1.1  # 0-0 чуть более вероятно
                elif h == 1 and a == 0:
                    p *= 0.95
                elif h == 0 and a == 1:
                    p *= 0.95
                
                if h > a:
                    p_home += p
                elif h == a:
                    p_draw += p
                else:
                    p_away += p
        
        # Нормализация
        total = p_home + p_draw + p_away
        if total > 0:
            p_home /= total
            p_draw /= total
            p_away /= total
        
        return p_home, p_draw, p_away, lambda_home, lambda_away
    
    def _poisson(self, lmbda, k):
        """Расчёт вероятности Пуассона"""
        return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)
    
    def ensemble_prediction(self, home_team, away_team):
        """
        Ансамбль моделей для максимальной точности
        """
        # Модель 1: Dixon-Coles (основная)
        p1_h, p1_d, p1_a, lam_h, lam_a = self.dixon_coles_prediction(home_team, away_team)
        
        # Модель 2: Чистый Elo
        elo_h = self.elo_ratings.get(home_team, 1500) + 65  # home advantage
        elo_a = self.elo_ratings.get(away_team, 1500)
        
        p2_h = 1 / (1 + 10 ** ((elo_a - elo_h) / 400))
        p2_a = 1 / (1 + 10 ** ((elo_h - elo_a) / 400))
        p2_d = 0.25 * (1 - abs(p2_h - p2_a))
        
        total = p2_h + p2_d + p2_a
        p2_h /= total
        p2_d /= total
        p2_a /= total
        
        # Модель 3: Форма + статистика
        form_h = self.get_form_factor(home_team)
        form_a = self.get_form_factor(away_team)
        
        p3_h = 0.45 * (0.5 + form_h - form_a)
        p3_a = 0.45 * (0.5 + form_a - form_h)
        p3_d = 1 - p3_h - p3_a
        
        # Ансамбль (взвешенное среднее)
        weights = (0.6, 0.25, 0.15)  # Dixon-Coles, Elo, Form
        
        final_h = weights[0] * p1_h + weights[1] * p2_h + weights[2] * p3_h
        final_d = weights[0] * p1_d + weights[1] * p2_d + weights[2] * p3_d
        final_a = weights[0] * p1_a + weights[1] * p2_a + weights[2] * p3_a
        
        # Нормализация
        total = final_h + final_d + final_a
        final_h /= total
        final_d /= total
        final_a /= total
        
        confidence = max(final_h, final_d, final_a)
        
        return [
            ("П1", final_h),
            ("X", final_d),
            ("П2", final_a)
        ], confidence, (lam_h, lam_a)

class RiskManager:
    """Управление рисками портфеля"""
    
    @staticmethod
    def kelly_criterion(prob, odds, bankroll, fraction=0.25):
        """Дробный критерий Келли"""
        if prob <= 0 or odds <= 1:
            return 0
        
        b = odds - 1
        q = 1 - prob
        kelly_fraction = (b * prob - q) / b
        
        # Применяем дробь
        adjusted = max(0, kelly_fraction * fraction)
        
        # Ограничения
        adjusted = min(adjusted, 0.05)  # Макс 5% от банка
        
        return round(bankroll * adjusted, 2)
    
    @staticmethod
    def check_portfolio_risk(bets, max_exposure_per_league=0.15):
        """Проверка рисков портфеля"""
        if not bets:
            return True, "Портфель пуст"
        
        pending_bets = [b for b in bets if b.get("status") == "pending"]
        total_stake = sum(b.get("stake", 0) for b in pending_bets)
        
        # Проверка по лигам
        league_exposure = defaultdict(float)
        for bet in pending_bets:
            league = bet.get("league", "Unknown")
            league_exposure[league] += bet.get("stake", 0)
        
        # Проверка максимальной экспозиции
        total_bank = 10000.0  # Начальный банк
        for league, exposure in league_exposure.items():
            if exposure / total_bank > max_exposure_per_league:
                return False, f"Слишком большая экспозиция на {league}: {exposure:.2f} у.е."
        
        return True, "Риски в норме"

class BacktestEngine:
    """Движок для бэктестинга стратегии"""
    
    @staticmethod
    def run_backtest(matches, engine, initial_bank=10000, min_prob=0.50):
        """Запуск бэктеста на исторических данных"""
        bank = initial_bank
        results = []
        
        for match in matches:
            if match.get("status") != "FINISHED":
                continue
            
            home = match.get("homeTeam", {}).get("name")
            away = match.get("awayTeam", {}).get("name")
            score = match.get("score", {}).get("fullTime", {})
            
            h_goals = score.get("home")
            a_goals = score.get("away")
            
            if not home or not away or h_goals is None or a_goals is None:
                continue
            
            # Предсказание ДО матча
            predictions, confidence, _ = engine.ensemble_prediction(home, away)
            best_pick, best_prob = max(predictions, key=lambda x: x[1])
            
            if best_prob < min_prob:
                continue
            
            # Фейковый коэффициент
            fair_odds = 1 / best_prob
            market_odds = fair_odds * 0.95  # Маржа букмекера
            
            # Ставка по Келли
            stake = RiskManager.kelly_criterion(best_prob, market_odds, bank, 0.25)
            
            if stake <= 0:
                continue
            
            # Результат
            if h_goals > a_goals:
                actual = "П1"
            elif h_goals == a_goals:
                actual = "X"
            else:
                actual = "П2"
            
            won = (best_pick == actual)
            
            if won:
                profit = stake * (market_odds - 1)
                bank += profit
            else:
                profit = -stake
                bank -= stake
            
            results.append({
                "match": f"{home} vs {away}",
                "pick": best_pick,
                "prob": best_prob,
                "odds": market_odds,
                "stake": stake,
                "won": won,
                "profit": profit,
                "bank": bank
            })
            
            # Обновление модели
            engine.update_from_match(home, away, h_goals, a_goals, is_recent=False)
        
        # Статистика
        total_bets = len(results)
        won_bets = sum(1 for r in results if r['won'])
        win_rate = (won_bets / total_bets * 100) if total_bets > 0 else 0
        
        final_profit = bank - initial_bank
        roi = (final_profit / initial_bank * 100)
        
        return {
            "results": results,
            "total_bets": total_bets,
            "won": won_bets,
            "lost": total_bets - won_bets,
            "win_rate": win_rate,
            "final_bank": bank,
            "profit": final_profit,
            "roi": roi
        }

# ============================================================
# УТИЛИТЫ
# ============================================================

def load_data():
    if os.path.exists(HISTORY_FILE):
        try:
            return json.load(open(HISTORY_FILE, "r", encoding="utf-8"))
        except:
            pass
    return {
        "bank": 10000.0,
        "bets": [],
        "forecasts": [],
        "stats": {"won": 0, "lost": 0, "profit": 0},
        "api_key": "",
        "backtest_results": None
    }

def save_data(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def fetch_api_matches(competition_code, api_key):
    url = f"https://api.football-data.org/v4/competitions/{competition_code}/matches"
    headers = {'X-Auth-Token': api_key.strip()}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json().get("matches", [])
        return []
    except:
        return []

def get_ai_deep_analysis(home, away, league_name, prob_h, prob_d, prob_a, openai_key):
    if not openai_key:
        return f"🛡️ **Анализ матча:** Встреча **{home} vs {away}** ({league_name}). Модель оценивает вероятность хозяев в {prob_h*100:.1f}%, гостей — в {prob_a*100:.1f}%. Учитывается текущая форма и плотность календаря."
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {openai_key.strip()}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Ты профессиональный спортивный аналитик. Дай краткий глубокий разбор матча на русском языке (до 3 предложений)."},
            {"role": "user", "content": f"Матч: {home} против {away}, турнир: {league_name}. Вероятности: П1 - {prob_h*100:.1f}%, Ничья - {prob_d*100:.1f}%, П2 - {prob_a*100:.1f}%."}
        ],
        "temperature": 0.5
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
    except:
        pass
    return "🛡️ Использован встроенный Dixon-Coles движок высокой точности."

# ============================================================
# ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ============================================================

if "data" not in st.session_state:
    st.session_state.data = load_data()

if "engine" not in st.session_state:
    st.session_state.engine = AdvancedAnalyticsEngine()

st.title("🚀 Football Betting AI Expert Pro")

with st.sidebar:
    st.header("⚙️ Панель управления")
    api_key = st.text_input("API Ключ (football-data.org)", type="password", value=st.session_state.data.get("api_key", ""))
    openai_key = st.text_input("OpenAI / Gemini API Key (опционально)", type="password", value="")
    
    if api_key:
        st.session_state.data["api_key"] = api_key
        save_data(st.session_state.data)
    
    bank = st.session_state.data["bank"]
    st.metric("💰 Текущий банк", f"{bank:.2f} у.е.")
    
    kelly_frac = st.slider("Риск-менеджмент (Келли)", 0.1, 0.4, 0.2, 0.05)
    min_prob = st.slider("Мин. проходимость прогноза (%)", 40, 75, 55) / 100
    
    st.markdown("---")
    st.markdown("### 🎯 Фильтры качества")
    min_confidence = st.slider("Мин. уверенность модели", 0.45, 0.70, 0.52, 0.01)
    use_ensemble = st.checkbox("Использовать ансамбль моделей", value=True)
    
    if st.button("🔄 Полный сброс системы"):
        st.session_state.data = {
            "bank": 10000.0,
            "bets": [],
            "forecasts": [],
            "stats": {"won": 0, "lost": 0, "profit": 0},
            "api_key": "",
            "backtest_results": None
        }
        st.session_state.engine = AdvancedAnalyticsEngine()
        save_data(st.session_state.data)
        st.rerun()

tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Глобальный сканер",
    "📋 Портфель ставок",
    "📊 Бэктестинг",
    "📈 Статистика"
])

with tab1:
    st.header("Интеллектуальный поиск валуйных матчей")
    days_ahead = st.slider("Горизонт анализа (дней вперед)", 1, 30, 14)
    
    if st.button("⚡ Запустить сканирование", type="primary"):
        if not api_key:
            st.error("❌ Введи API-ключ football-data.org в боковой панели!")
            st.stop()
        
        all_forecasts = []
        auto_added_count = 0
        existing_matches = {b["match"] for b in st.session_state.data["bets"]}
        
        with st.spinner("Загрузка данных и обучение модели..."):
            # Сначала загружаем все исторические матчи для обучения
            for l_name, code in LEAGUE_CODES.items():
                matches = fetch_api_matches(code, api_key)
                if matches:
                    # Обучение на завершённых матчах
                    for match in matches:
                        if match.get("status") == "FINISHED":
                            home = match.get("homeTeam", {}).get("name")
                            away = match.get("awayTeam", {}).get("name")
                            score = match.get("score", {}).get("fullTime", {})
                            h_goals = score.get("home")
                            a_goals = score.get("away")
                            
                            if home and away and h_goals is not None and a_goals is not None:
                                st.session_state.engine.update_from_match(home, away, h_goals, a_goals)
        
        with st.spinner("Сканирование будущих матчей и генерация прогнозов..."):
            for l_name, code in LEAGUE_CODES.items():
                matches = fetch_api_matches(code, api_key)
                if not matches:
                    continue
                
                now = datetime.utcnow()
                limit_date = now + timedelta(days=days_ahead)
                
                for match in matches:
                    if match.get("status") not in ["SCHEDULED", "TIMED"]:
                        continue
                    
                    utc_date_str = match.get("utcDate")
                    if not utc_date_str:
                        continue
                    
                    try:
                        match_date = datetime.strptime(utc_date_str[:19], "%Y-%m-%dT%H:%M:%S")
                    except:
                        continue
                    
                    if match_date > limit_date:
                        continue
                    
                    home = match.get("homeTeam", {}).get("name")
                    away = match.get("awayTeam", {}).get("name")
                    if not home or not away:
                        continue
                    
                    # Предсказание
                    if use_ensemble:
                        preds, confidence, (lam_h, lam_a) = st.session_state.engine.ensemble_prediction(home, away)
                    else:
                        p_h, p_d, p_a, lam_h, lam_a = st.session_state.engine.dixon_coles_prediction(home, away)
                        preds = [("П1", p_h), ("X", p_d), ("П2", p_a)]
                        confidence = max(p_h, p_d, p_a)
                    
                    best_pick, best_prob = max(preds, key=lambda x: x[1])
                    p_h, p_d, p_a = preds[0][1], preds[1][1], preds[2][1]
                    
                    # Фильтры
                    if best_prob < min_prob or confidence < min_confidence:
                        continue
                    
                    # Расчёт коэффициента и EV
                    fair_odds = 1 / best_prob
                    best_odd = round(fair_odds * 1.05, 2)  # 5% маржа
                    ev = (best_prob * best_odd) - 1.0
                    
                    stake = RiskManager.kelly_criterion(best_prob, best_odd, bank, kelly_frac)
                    commentary = get_ai_deep_analysis(home, away, l_name, p_h, p_d, p_a, openai_key)
                    
                    # Проверка рисков портфеля
                    can_add, risk_msg = RiskManager.check_portfolio_risk(
                        st.session_state.data["bets"],
                        max_exposure_per_league=0.15
                    )
                    
                    is_top = best_prob >= 0.58 and confidence >= 0.55
                    status_label = "🔥 ТОП ВАРИАНТ" if is_top else "🟢 РАБОЧИЙ"
                    
                    match_str = f"{home} vs {away}"
                    
                    forecast_item = {
                        "league": l_name,
                        "league_code": code,
                        "match": match_str,
                        "date": match_date.strftime('%d.%m.%Y %H:%M (UTC)'),
                        "pick": best_pick,
                        "prob": best_prob,
                        "confidence": confidence,
                        "odds": best_odd,
                        "ev": ev,
                        "lambda_home": lam_h,
                        "lambda_away": lam_a,
                        "status_label": status_label,
                        "stake": stake,
                        "commentary": commentary,
                        "is_top": is_top,
                        "risk_ok": can_add
                    }
                    
                    all_forecasts.append(forecast_item)
                    
                    # Автодобавление в портфель
                    if is_top and match_str not in existing_matches and stake > 0 and can_add:
                        st.session_state.data["bets"].append({
                            "match": match_str,
                            "league": l_name,
                            "league_code": code,
                            "pick": best_pick,
                            "odds": best_odd,
                            "stake": stake,
                            "status": "pending",
                            "prob": best_prob,
                            "confidence": confidence
                        })
                        existing_matches.add(match_str)
                        auto_added_count += 1
            
            # Сортировка по качеству
            all_forecasts.sort(key=lambda x: (x['prob'] * x['confidence'], x['ev']), reverse=True)
            st.session_state.data["forecasts"] = all_forecasts
            save_data(st.session_state.data)
            
            st.success(f"✅ Найдено матчей: {len(all_forecasts)}. Добавлено в портфель: {auto_added_count}")
            st.rerun()
    
    # Отображение результатов
    forecasts = st.session_state.data.get("forecasts", [])
    
    if forecasts:
        st.subheader(f"📊 Отсканированные матчи ({len(forecasts)})")
        
        # Статистика
        top_matches = [f for f in forecasts if f.get("is_top")]
        st.info(f"🔥 **ТОП матчей:** {len(top_matches)} | 💼 **Общая ставка:** {sum(f['stake'] for f in forecasts):.2f} у.е.")
        
        for idx, f in enumerate(forecasts):
            if f.get("is_top"):
                with st.container():
                    st.success(f"### 🟢 ТОП МАТЧ: {f['match']} ({f['league']})")
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    with c1:
                        st.markdown(f"**Выбор:** `{f['pick']}` | Ставка: **{f['stake']:.2f} у.е.**")
                        st.caption(f"📅 {f['date']}")
                    with c2:
                        st.metric("Проходимость", f"{f['prob']*100:.1f}%")
                    with c3:
                        st.metric("Уверенность", f"{f['confidence']*100:.1f}%")
                    with c4:
                        st.metric("Коэффициент", f"{f['odds']:.2f}")
                    
                    st.info(f"{f['commentary']}")
                    
                    # Детали модели
                    with st.expander("📊 Детали анализа"):
                        st.write(f"**Expected Goals:** {f['league']} {f['lambda_home']:.2f} - {f['lambda_away']:.2f}")
                        st.write(f"**Expected Value:** {f['ev']*100:.1f}%")
                        st.write(f"**Fair Odds:** {1/f['prob']:.2f}")
                    
                    st.markdown("---")
            else:
                with st.container():
                    st.markdown(f"### ⚽ {f['match']} ({f['league']})")
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c1:
                        st.markdown(f"**{f['status_label']}** | Выбор: **{f['pick']}** | Ставка: {f['stake']:.2f} у.е.")
                        st.caption(f"📅 {f['date']}")
                    with c2:
                        st.metric("Проходимость", f"{f['prob']*100:.1f}%")
                    with c3:
                        st.metric("Коэффициент", f"{f['odds']:.2f}")
                    
                    st.info(f"{f['commentary']}")
                    st.markdown("---")
    else:
        st.info("👆 Нажми кнопку для запуска сканирования")

with tab2:
    st.header("📋 Портфель ставок")
    
    # Проверка рисков
    can_add, risk_msg = RiskManager.check_portfolio_risk(st.session_state.data["bets"])
    if not can_add:
        st.warning(f"⚠️ {risk_msg}")
    
    if st.button("🔄 Синхронизировать результаты", type="primary"):
        if not api_key:
            st.error("❌ Введи API-ключ!")
        else:
            bets = st.session_state.data.get("bets", [])
            pending_bets = [b for b in bets if b.get("status") == "pending"]
            
            if not pending_bets:
                st.info("Нет ожидающих матчей")
            else:
                updated_count = 0
                leagues_to_check = set(b.get("league_code") for b in pending_bets if b.get("league_code"))
                
                league_matches_cache = {}
                for l_code in leagues_to_check:
                    league_matches_cache[l_code] = fetch_api_matches(l_code, api_key)
                
                for bet in pending_bets:
                    l_code = bet.get("league_code")
                    if not l_code or l_code not in league_matches_cache:
                        continue
                    
                    match_name = bet.get("match")
                    parts = match_name.split(" vs ")
                    if len(parts) != 2:
                        continue
                    h_target, a_target = parts[0].strip(), parts[1].strip()
                    
                    for api_m in league_matches_cache[l_code]:
                        if api_m.get("status") == "FINISHED":
                            h_name = api_m.get("homeTeam", {}).get("name")
                            a_name = api_m.get("awayTeam", {}).get("name")
                            
                            if h_name == h_target and a_name == a_target:
                                score = api_m.get("score", {}).get("fullTime", {})
                                h_goals = score.get("home")
                                a_goals = score.get("away")
                                
                                if h_goals is None or a_goals is None:
                                    continue
                                
                                actual_res = "П1" if h_goals > a_goals else ("X" if h_goals == a_goals else "П2")
                                
                                pick = bet.get("pick")
                                stake = bet.get("stake", 0)
                                odds = bet.get("odds", 0)
                                
                                if pick == actual_res:
                                    bet["status"] = "won"
                                    profit = stake * (odds - 1)
                                    st.session_state.data["bank"] += stake + profit
                                    st.session_state.data["stats"]["won"] += 1
                                    st.session_state.data["stats"]["profit"] += profit
                                else:
                                    bet["status"] = "lost"
                                    st.session_state.data["stats"]["lost"] += 1
                                    st.session_state.data["stats"]["profit"] -= stake
                                
                                # Обновление модели
                                st.session_state.engine.update_from_match(h_name, a_name, h_goals, a_goals)
                                
                                updated_count += 1
                                break
                
                save_data(st.session_state.data)
                st.success(f"✅ Обновлено матчей: {updated_count}")
                st.rerun()
    
    bets = st.session_state.data.get("bets", [])
    
    if not bets:
        st.info("Портфель пуст")
    else:
        pending = [b for b in bets if b.get("status") == "pending"]
        completed = [b for b in bets if b.get("status") in ["won", "lost"]]
        
        if pending:
            st.subheader(f"⏳ Ожидающие ({len(pending)})")
            total_pending_stake = sum(b.get("stake", 0) for b in pending)
            st.info(f"💰 **Общая сумма ставок:** {total_pending_stake:.2f} у.е.")
            
            for i, bet in enumerate(pending):
                with st.container():
                    c1, c2, c3 = st.columns([3, 1, 1])
                    with c1:
                        st.markdown(f"**{bet.get('league')}** | `{bet.get('match')}`")
                        st.write(f"Выбор: **{bet.get('pick')}** @ {bet.get('odds'):.2f}")
                    with c2:
                        st.metric("Ставка", f"{bet.get('stake'):.2f}")
                    with c3:
                        prob = bet.get('prob', 0)
                        st.metric("Вероятность", f"{prob*100:.0f}%")
                    st.markdown("---")
        
        if completed:
            st.subheader(f"📁 Архив ({len(completed)})")
            for bet in completed[-20:]:
                status_icon = "🟢" if bet.get("status") == "won" else "🔴"
                profit = bet.get("stake", 0) * (bet.get("odds", 1) - 1) if bet.get("status") == "won" else -bet.get("stake", 0)
                profit_color = "green" if profit > 0 else "red"
                
                st.markdown(f"{status_icon} **{bet.get('match')}** | {bet.get('pick')} @ {bet.get('odds'):.2f} | Ставка: {bet.get('stake'):.2f} | <span style='color:{profit_color}'>**{profit:+.2f}**</span>", unsafe_allow_html=True)

with tab3:
    st.header("📊 Бэктестинг стратегии")
    
    st.info("💡 Бэктестинг позволяет проверить эффективность модели на исторических данных перед использованием в реальных ставках")
    
    if st.button("🚀 Запустить бэктестинг", type="primary"):
        if not api_key:
            st.error("❌ Введи API-ключ!")
            st.stop()
        
        with st.spinner("Загрузка исторических данных..."):
            all_matches = []
            for l_name, code in LEAGUE_CODES.items():
                matches = fetch_api_matches(code, api_key)
                all_matches.extend(matches)
            
            if not all_matches:
                st.error("Не удалось загрузить данные")
                st.stop()
            
            st.info(f"Загружено {len(all_matches)} матчей для анализа")
        
        with st.spinner("Запуск бэктеста..."):
            # Создаём новый движок для бэктеста
            test_engine = AdvancedAnalyticsEngine()
            
            # Сортируем матчи по дате
            all_matches.sort(key=lambda x: x.get("utcDate", ""))
            
            results = BacktestEngine.run_backtest(
                all_matches,
                test_engine,
                initial_bank=10000,
                min_prob=min_prob
            )
            
            st.session_state.data["backtest_results"] = results
            save_data(st.session_state.data)
            st.rerun()
    
    # Отображение результатов бэктеста
    backtest = st.session_state.data.get("backtest_results")
    
    if backtest:
        st.subheader("📈 Результаты бэктестинга")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Всего ставок", backtest["total_bets"])
        c2.metric("Win Rate", f"{backtest['win_rate']:.1f}%")
        c3.metric("Финальный банк", f"{backtest['final_bank']:.2f}")
        c4.metric("ROI", f"{backtest['roi']:.2f}%")
        
        st.markdown("---")
        
        # Детальная статистика
        won = backtest["won"]
        lost = backtest["lost"]
        profit = backtest["profit"]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Выиграно", won)
        c2.metric("❌ Проиграно", lost)
        c3.metric("💰 Прибыль", f"{profit:+.2f} у.е.")
        
        st.markdown("---")
        
        # График роста банка
        if backtest["results"]:
            st.subheader("📊 Рост банка")
            
            banks = [10000] + [r["bank"] for r in backtest["results"]]
            
            chart_data = {
                "Ставка": list(range(len(banks))),
                "Банк": banks
            }
            
            st.line_chart(chart_data, x="Ставка", y="Банк")
        
        # Последние ставки
        with st.expander("📋 Показать все ставки бэктеста"):
            for r in backtest["results"][-50:]:
                status = "✅" if r["won"] else "❌"
                st.text(f"{status} {r['match']} | {r['pick']} @ {r['odds']:.2f} | Ставка: {r['stake']:.2f} | {r['profit']:+.2f}")
    else:
        st.info("👆 Нажми кнопку для запуска бэктестинга")

with tab4:
    st.header("📊 Статистика эффективности")
    
    stats = st.session_state.data.get("stats", {})
    bank = st.session_state.data["bank"]
    initial_bank = 10000.0
    
    won = stats.get("won", 0)
    lost = stats.get("lost", 0)
    profit = stats.get("profit", 0)
    total = won + lost
    
    win_rate = (won / total * 100) if total > 0 else 0
    roi = (profit / initial_bank * 100)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Текущий банк", f"{bank:.2f} у.е.", f"{bank - initial_bank:+.2f}")
    c2.metric("📊 Всего ставок", total)
    c3.metric("🎯 Win Rate", f"{win_rate:.1f}%")
    c4.metric("📈 ROI", f"{roi:.2f}%")
    
    st.markdown("---")
    
    # Детальная статистика
    if total > 0:
        st.subheader("📊 Детальный анализ")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("### ✅ Выигранные ставки")
            st.metric("Количество", won)
            st.metric("Прибыль", f"{profit:+.2f} у.е." if profit > 0 else "0.00 у.е.")
        
        with c2:
            st.markdown("### ❌ Проигранные ставки")
            st.metric("Количество", lost)
            avg_loss = -profit / lost if lost > 0 else 0
            st.metric("Средний убыток", f"{avg_loss:.2f} у.е.")
        
        st.markdown("---")
        
        # Эффективность по лигам
        bets = st.session_state.data.get("bets", [])
        completed = [b for b in bets if b.get("status") in ["won", "lost"]]
        
        if completed:
            st.subheader("🏆 Эффективность по лигам")
            
            league_stats = defaultdict(lambda: {"won": 0, "lost": 0, "profit": 0})
            
            for bet in completed:
                league = bet.get("league", "Unknown")
                status = bet.get("status")
                stake = bet.get("stake", 0)
                odds = bet.get("odds", 1)
                
                if status == "won":
                    league_stats[league]["won"] += 1
                    league_stats[league]["profit"] += stake * (odds - 1)
                else:
                    league_stats[league]["lost"] += 1
                    league_stats[league]["profit"] -= stake
            
            for league, stats in sorted(league_stats.items(), key=lambda x: x[1]["profit"], reverse=True):
                total_league = stats["won"] + stats["lost"]
                wr = (stats["won"] / total_league * 100) if total_league > 0 else 0
                
                with st.expander(f"{league} | {total_league} ставок | WR: {wr:.1f}%"):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("✅ Выиграно", stats["won"])
                    c2.metric("❌ Проиграно", stats["lost"])
                    c3.metric("💰 Прибыль", f"{stats['profit']:+.2f} у.е.")
