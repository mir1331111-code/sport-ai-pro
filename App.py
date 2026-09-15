import streamlit as st
import csv
import io
import requests
import json
import os
from datetime import datetime, timedelta
from scipy.stats import poisson
import numpy as np

st.set_page_config(page_title="Multi-Sport Betting AI", page_icon="🎯", layout="wide")

HISTORY_FILE = "multi_sport_data.json"

def load_data():
    if os.path.exists(HISTORY_FILE):
        try:
            return json.load(open(HISTORY_FILE, "r"))
        except:
            pass
    return {"bank": 10000.0, "bets": [], "forecasts": [], "stats": {"won": 0, "lost": 0, "profit": 0}}

def save_data(data):
    json.dump(data, open(HISTORY_FILE, "w"), indent=4)

def load_csv(url):
    """Загрузка CSV без pandas"""
    try:
        r = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        return list(csv.DictReader(io.StringIO(r.text)))
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
        return []

def find_active_season(sport_code):
    """Автоопределение активного сезона"""
    base_urls = {
        "football": "https://www.football-data.co.uk/mmz4281/",
        "tennis": "https://www.tennis-data.co.uk/",
        "basketball": "https://www.basketball-data.co.uk/"
    }
    
    seasons = ["2627", "2526", "2425", "2025", "2024"]
    
    for season in seasons:
        test_url = f"{base_urls.get('football', '')}{season}/E0.csv"
        try:
            r = requests.head(test_url, timeout=5)
            if r.status_code == 200:
                return season
        except:
            continue
    
    return "2526"  # fallback

def parse_date(date_str):
    """Парсинг даты"""
    formats = ["%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except:
            continue
    return None

def calculate_elo(data, home_col='HomeTeam', away_col='AwayTeam', score1_col='FTHG', score2_col='FTAG'):
    """Расчёт Elo рейтингов"""
    elo = {}
    for row in data:
        h = row.get(home_col, '')
        a = row.get(away_col, '')
        s1 = row.get(score1_col)
        s2 = row.get(score2_col)
        
        if not h or not a or not s1 or not s2:
            continue
        
        try:
            s1, s2 = float(s1), float(s2)
        except:
            continue
        
        if h not in elo: elo[h] = 1500
        if a not in elo: elo[a] = 1500
        
        r1, r2 = elo[h], elo[a]
        e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        result = 1 if s1 > s2 else (0.5 if s1 == s2 else 0)
        
        elo[h] = r1 + 32 * (result - e1)
        elo[a] = r2 + 32 * ((1-result) - (1-e1))
    
    return elo

def predict_match(elo, home, away, sport="football"):
    """Предсказание вероятностей"""
    r1 = elo.get(home, 1500)
    r2 = elo.get(away, 1500)
    
    if sport in ["basketball", "hockey"]:
        # Для баскетбола/хоккея - бинарный исход (без ничьей)
        p_home = 1 / (1 + 10 ** ((r2 - r1) / 400))
        p_away = 1 - p_home
        return [("П1", p_home), ("П2", p_away)]
    else:
        # Для футбола/тенниса - с ничьей
        p_home = 1 / (1 + 10 ** ((r2 - r1) / 400))
        p_away = 1 / (1 + 10 ** ((r1 - r2) / 400))
        p_draw = 0.25 * (1 - abs(p_home - p_away))
        
        total = p_home + p_draw + p_away
        return [
            ("П1", p_home/total),
            ("X", p_draw/total),
            ("П2", p_away/total)
        ]

def kelly_stake(prob, odds, bank, fraction=0.25):
    """Расчёт ставки по Келли"""
    if prob <= 0 or odds <= 1:
        return 0
    b = odds - 1
    kelly = (b * prob - (1 - prob)) / b
    stake = max(0, kelly * fraction) * bank
    return round(min(stake, bank * 0.05), 2)

# Инициализация
if "data" not in st.session_state:
    st.session_state.data = load_data()

st.title("🎯 Multi-Sport Betting AI")

# Боковая панель
with st.sidebar:
    st.header("⚙️ Настройки")
    bank = st.session_state.data["bank"]
    st.metric("💰 Банк", f"{bank:.2f} у.е.")
    
    kelly_frac = st.slider("Дробь Келли", 0.1, 0.5, 0.25, 0.05)
    min_ev = st.slider("Мин EV %", 1, 15, 5) / 100
    
    if st.button("🔄 Сброс системы"):
        st.session_state.data = {"bank": 10000.0, "bets": [], "forecasts": [], "stats": {"won": 0, "lost": 0, "profit": 0}}
        save_data(st.session_state.data)
        st.rerun()

# Вкладки
tab1, tab2, tab3 = st.tabs(["🎯 Прогнозы", "📋 Ставки", "📊 Статистика"])

with tab1:
    st.header("Анализ матчей")
    
    # Выбор вида спорта
    sport = st.selectbox("Вид спорта", ["⚽ Футбол", "🎾 Теннис", "🏀 Баскетбол", "🏒 Хоккей"])
    
    # Лиги в зависимости от спорта
    leagues = {
        "⚽ Футбол": {
            "🏴󠁢󠁿 Англия (АПЛ)": ("football", "E0"),
            "🇪 Испания": ("football", "SP1"),
            "🇮🇹 Италия": ("football", "I1"),
            "🇩🇪 Германия": ("football", "D1"),
            "🇫🇷 Франция": ("football", "F1"),
            "🇷🇺 Россия": ("football", "R1"),
            "🇹 Турция": ("football", "T1")
        },
        "🎾 Теннис": {
            "ATP Tour": ("tennis", "atp"),
            "WTA Tour": ("tennis", "wta")
        },
        "🏀 Баскетбол": {
            "NBA": ("basketball", "nba"),
            "EuroLeague": ("basketball", "euroleague")
        },
        "🏒 Хоккей": {
            "NHL": ("hockey", "nhl"),
            "KHL": ("hockey", "khl")
        }
    }
    
    selected_league = st.selectbox("Лига/Турнир", list(leagues[sport].keys()))
    days = st.slider("Период анализа (дней)", 1, 14, 7)
    
    col1, col2 = st.columns(2)
    with col1:
        show_all = st.checkbox("Показать все матчи (включая сыгранные)", False)
    with col2:
        debug_mode = st.checkbox("Режим отладки", False)
    
    if st.button("🚀 Запустить анализ", type="primary"):
        sport_type, league_code = leagues[sport][selected_league]
        
        # Определение URL
        if sport_type == "football":
            season = find_active_season("football")
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{league_code}.csv"
        elif sport_type == "tennis":
            url = f"https://www.tennis-data.co.uk/2025/{league_code}-2025.csv"
        elif sport_type == "basketball":
            url = f"https://www.basketball-data.co.uk/2025/{league_code}-2025.csv"
        else:
            url = f"https://www.hockey-data.co.uk/2025/{league_code}-2025.csv"
        
        if debug_mode:
            st.info(f"URL: {url}")
        
        with st.spinner("Загрузка данных..."):
            data = load_csv(url)
            
            if not data:
                st.error("❌ Не удалось загрузить данные. Возможно:")
                st.write("- Сезон ещё не начался")
                st.write("- Сайт временно недоступен")
                st.write("- Неправильный URL")
                
                if debug_mode:
                    st.code(f"URL: {url}")
                st.stop()
            
            st.success(f"✅ Загружено {len(data)} записей")
        
        with st.spinner("Обработка и анализ..."):
            today = datetime.now()
            limit = today + timedelta(days=days)
            
            # Обучение Elo
            elo = calculate_elo(data)
            
            if debug_mode:
                st.write(f"Команд в базе: {len(elo)}")
                st.write(f"Пример рейтингов: {dict(list(elo.items())[:5])}")
            
            # Фильтрация матчей
            forecasts = []
            processed = 0
            skipped_no_date = 0
            skipped_played = 0
            skipped_no_odds = 0
            
            for row in data:
                processed += 1
                
                # Получение команд
                home = row.get('HomeTeam', row.get('Player1', row.get('Team1', '')))
                away = row.get('AwayTeam', row.get('Player2', row.get('Team2', '')))
                
                if not home or not away:
                    continue
                
                # Парсинг даты
                date_str = row.get('Date', row.get('MatchDate', ''))
                match_date = parse_date(date_str) if date_str else None
                
                if not match_date:
                    skipped_no_date += 1
                    if not show_all:
                        continue
                
                # Проверка диапазона дат
                if match_date and (match_date < today.replace(hour=0, minute=0) or match_date > limit):
                    if not show_all:
                        continue
                
                # Проверка сыгранности
                score1 = row.get('FTHG', row.get('Set1', row.get('Score1', '')))
                if score1 and not show_all:
                    skipped_played += 1
                    continue
                
                # Коэффициенты
                try:
                    if sport_type == "football":
                        odds_h = float(row.get('B365H', row.get('PSH', '0')))
                        odds_x = float(row.get('B365D', row.get('PSD', '0')))
                        odds_a = float(row.get('B365A', row.get('PSA', '0')))
                        odds_dict = {"П1": odds_h, "X": odds_x, "П2": odds_a}
                    else:
                        odds_h = float(row.get('B365H', row.get('PSH', row.get('HomeOdds', '0'))))
                        odds_a = float(row.get('B365A', row.get('PSA', row.get('AwayOdds', '0'))))
                        odds_dict = {"П1": odds_h, "П2": odds_a}
                    
                    if all(v <= 1 for v in odds_dict.values()):
                        skipped_no_odds += 1
                        continue
                except:
                    skipped_no_odds += 1
                    continue
                
                # Предсказание
                predictions = predict_match(elo, home, away, sport_type.replace("⚽ ", "").replace("🎾 ", "").replace("🏀 ", "").replace("🏒 ", ""))
                
                # Поиск лучшего исхода
                best_pick = None
                best_ev = -1
                best_prob = 0
                best_odd = 0
                
                for pick, prob in predictions:
                    odd = odds_dict.get(pick, 0)
                    if odd > 1:
                        ev = (prob * odd) - 1.0
                        if ev > best_ev:
                            best_ev = ev
                            best_pick = pick
                            best_prob = prob
                            best_odd = odd
                
                # Фильтр по EV
                if best_ev > min_ev:
                    stake = kelly_stake(best_prob, best_odd, bank, kelly_frac)
                    
                    if stake > 0:
                        forecasts.append({
                            "sport": sport,
                            "league": selected_league,
                            "match": f"{home} vs {away}",
                            "date": match_date.strftime('%d.%m') if match_date else "N/A",
                            "pick": best_pick,
                            "prob": best_prob,
                            "odds": best_odd,
                            "ev": best_ev,
                            "stake": stake
                        })
            
            if debug_mode:
                st.write(f"""
                **Статистика обработки:**
                - Всего записей: {processed}
                - Без даты: {skipped_no_date}
                - Сыгранные: {skipped_played}
                - Без коэффициентов: {skipped_no_odds}
                - Найдено ставок: {len(forecasts)}
                """)
            
            st.session_state.data["forecasts"] = forecasts
            save_data(st.session_state.data)
            
            if forecasts:
                st.success(f"✅ Найдено {len(forecasts)} ставок с EV > {min_ev*100:.0f}%")
            else:
                st.warning("⚠️ Не найдено ставок с положительным EV. Попробуйте:")
                st.write("- Увеличить период анализа")
                st.write("- Снизить минимальный EV")
                st.write("- Выбрать другую лигу")
                st.write("- Включить 'Показать все матчи'")
            
            st.rerun()
    
    # Отображение прогнозов
    forecasts = st.session_state.data.get("forecasts", [])
    
    if forecasts:
        st.subheader(f"📊 Найдено {len(forecasts)} выгодных ставок")
        
        for f in forecasts:
            ev_color = "#10b981" if f['ev'] > 0.1 else "#facc15" if f['ev'] > 0.05 else "#94a3b8"
            
            st.markdown(f"""
            <div style="background:rgba(30,41,59,0.75);padding:18px;border-radius:12px;margin-bottom:12px;border-left:4px solid #38bdf8">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                    <span style="background:#38bdf8;padding:4px 12px;border-radius:6px;font-size:0.8rem;color:white;font-weight:700">{f['league']}</span>
                    <span style="color:#94a3b8;font-size:0.9rem">📅 {f['date']}</span>
                </div>
                
                <div style="font-size:1.2rem;font-weight:700;color:#f8fafc;margin-bottom:12px">
                    {f['sport']} {f['match']}
                </div>
                
                <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin-bottom:12px">
                    <div>
                        <div style="color:#94a3b8;font-size:0.75rem;margin-bottom:4px">ПРОГНОЗ</div>
                        <div style="color:#facc15;font-weight:700;font-size:1.2rem">{f['pick']}</div>
                    </div>
                    <div>
                        <div style="color:#94a3b8;font-size:0.75rem;margin-bottom:4px">ВЕРОЯТНОСТЬ</div>
                        <div style="color:#4ade80;font-weight:700;font-size:1.2rem">{f['prob']*100:.1f}%</div>
                    </div>
                    <div>
                        <div style="color:#94a3b8;font-size:0.75rem;margin-bottom:4px">КОЭФФИЦИЕНТ</div>
                        <div style="color:#facc15;font-weight:700;font-size:1.2rem">{f['odds']:.2f}</div>
                    </div>
                    <div>
                        <div style="color:#94a3b8;font-size:0.75rem;margin-bottom:4px">EV (ПЕРЕВЕС)</div>
                        <div style="color:{ev_color};font-weight:700;font-size:1.2rem">{f['ev']*100:.1f}%</div>
                    </div>
                </div>
                
                <div style="border-top:1px solid rgba(255,255,255,0.1);padding-top:12px;display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <span style="color:#94a3b8;font-size:0.9rem">Рекомендуемая ставка (Келли):</span>
                        <span style="color:#facc15;font-weight:700;font-size:1.3rem;margin-left:8px">{f['stake']:.2f} у.е.</span>
                    </div>
                    <div style="color:#64748b;font-size:0.8rem">
                        ROI потенциал: {(f['ev']*100):.1f}%
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("👆 Выберите вид спорта, лигу и нажмите «Запустить анализ»")

with tab2:
    st.header("📋 Управление ставками")
    
    bets = st.session_state.data.get("bets", [])
    
    if not bets:
        st.info("Нет активных ставок. Добавьте ставки из вкладки «Прогнозы»")
    else:
        pending = [b for b in bets if b.get("status") == "pending"]
        completed = [b for b in bets if b.get("status") in ["won", "lost"]]
        
        if pending:
            st.subheader(f"⏳ Активные ({len(pending)})")
            for i, bet in enumerate(pending):
                st.markdown(f"""
                <div style="background:rgba(30,41,59,0.75);padding:18px;border-radius:12px;margin-bottom:12px;border-left:4px solid #f59e0b">
                    <div style="font-size:1.1rem;font-weight:700;color:#f8fafc;margin-bottom:8px">
                        {bet.get('sport', '')} {bet.get('match', '')}
                    </div>
                    <div style="color:#94a3b8;margin-bottom:12px">
                        Прогноз: <b style="color:#4ade80">{bet.get('pick', '')}</b> @ 
                        <b style="color:#facc15">{bet.get('odds', 0):.2f}</b> | 
                        Ставка: <b style="color:#facc15">{bet.get('stake', 0):.2f} у.е.</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                cols = st.columns(2)
                with cols[0]:
                    if st.button(f"✅ Выиграла", key=f"win_{i}"):
                        bet["status"] = "won"
                        profit = bet.get("stake", 0) * (bet.get("odds", 1) - 1)
                        st.session_state.data["bank"] += bet.get("stake", 0) + profit
                        st.session_state.data["stats"]["won"] += 1
                        st.session_state.data["stats"]["profit"] += profit
                        save_data(st.session_state.data)
                        st.success(f"🎉 Выигрыш: +{profit:.2f} у.е.")
                        st.rerun()
                
                with cols[1]:
                    if st.button(f"❌ Проиграла", key=f"loss_{i}"):
                        bet["status"] = "lost"
                        st.session_state.data["stats"]["lost"] += 1
                        st.session_state.data["stats"]["profit"] -= bet.get("stake", 0)
                        save_data(st.session_state.data)
                        st.error(f"😢 Проигрыш: -{bet.get('stake', 0):.2f} у.е.")
                        st.rerun()
        
        if completed:
            st.subheader(f"✅ Завершённые ({len(completed)})")
            for bet in completed[-10:]:
                status_icon = "🎉" if bet.get("status") == "won" else "😢"
                border_color = "#10b981" if bet.get("status") == "won" else "#ef4444"
                
                st.markdown(f"""
                <div style="background:rgba(30,41,59,0.5);padding:15px;border-radius:10px;margin-bottom:10px;border-left:4px solid {border_color}">
                    <div style="font-size:1rem;font-weight:600;color:#f8fafc">
                        {status_icon} {bet.get('match', '')} - {bet.get('pick', '')} @ {bet.get('odds', 0):.2f}
                    </div>
                    <div style="color:#94a3b8;font-size:0.85rem;margin-top:5px">
                        Ставка: {bet.get('stake', 0):.2f} у.е. | Результат: {bet.get('status', '').upper()}
                    </div>
                </div>
                """, unsafe_allow_html=True)

with tab3:
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
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Текущий банк", f"{bank:.2f} у.е.", f"{bank - initial_bank:+.2f}")
    
    with col2:
        st.metric("📊 Всего ставок", total)
    
    with col3:
        st.metric("🎯 Win Rate", f"{win_rate:.1f}%")
    
    with col4:
        st.metric("📈 ROI", f"{roi:.2f}%")
    
    st.markdown("---")
    
    if total > 0:
        st.markdown(f"""
        <div style="background:rgba(30,41,59,0.8);padding:25px;border-radius:12px;border:1px solid rgba(56,189,248,0.3)">
            <h4 style="color:#f8fafc;margin-bottom:20px">📊 Детальная статистика</h4>
            <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:20px">
                <div>
                    <div style="color:#94a3b8;font-size:0.9rem;margin-bottom:5px">Выиграно</div>
                    <div style="color:#10b981;font-size:2rem;font-weight:700">{won}</div>
                </div>
                <div>
                    <div style="color:#94a3b8;font-size:0.9rem;margin-bottom:5px">Проиграно</div>
                    <div style="color:#ef4444;font-size:2rem;font-weight:700">{lost}</div>
                </div>
                <div>
                    <div style="color:#94a3b8;font-size:0.9rem;margin-bottom:5px">Общая прибыль</div>
                    <div style="color:{'#10b981' if profit > 0 else '#ef4444'};font-size:2rem;font-weight:700">{profit:+.2f} у.е.</div>
                </div>
                <div>
                    <div style="color:#94a3b8;font-size:0.9rem;margin-bottom:5px">Средний ROI</div>
                    <div style="color:#38bdf8;font-size:2rem;font-weight:700">{roi:.2f}%</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Сделайте первые ставки для отображения статистики")
    
    st.markdown("---")
    st.markdown("""
    ### ℹ️ Как работает система
    
    **1. Многоспортивная поддержка:**
    - ⚽ Футбол: Пуассон + Elo для точных прогнозов
    - 🎾 Теннис: Elo-рейтинги игроков
    - 🏀 Баскетбол: Адаптированная модель без ничьих
    - 🏒 Хоккей: Статистическая модель
    
    **2. Критерий Келли:**
    - Автоматический расчёт оптимального размера ставки
    - Защита от разорения (максимум 5% от банка)
    - Дробный Келли (25%) для снижения волатильности
    
    **3. Expected Value (EV):**
    - Ставим только при математическом перевесе
    - Фильтр слабых сигналов
    - Долгосрочная прибыльность
    
    **4. Источники данных:**
    - Football-data.co.uk (футбол)
    - Tennis-data.co.uk (теннис)
    - Basketball-data.co.uk (баскетбол)
    - Hockey-data.co.uk (хоккей)
    """)
