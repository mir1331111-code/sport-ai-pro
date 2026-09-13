import streamlit as st
import google.generativeai as genai
import datetime

st.set_page_config(page_title="Flashscore & SofaScore Auto-Sniper", page_icon="🤖", layout="centered")

st.markdown("""
<h1 style='text-align: center;'>🤖 Auto-Sniper: Авто-поиск с Flashscore & SofaScore</h1>
<p style='text-align: center; color: gray;'>ИИ самостоятельно сканирует интернет, Flashscore, SofaScore и мнения экспертов, находя реальные матчи и давая точные прогнозы.</p>
""", unsafe_allow_html=True)

# Инициализация истории в памяти сессии
if 'history' not in st.session_state:
    st.session_state.history = []

st.sidebar.header("⚙️ Настройки и Статистика")
api_key = st.sidebar.text_input("Ключ Gemini API", type="password")

if not api_key:
    st.sidebar.warning("⚠️ Укажите ключ для работы ИИ!")
else:
    genai.configure(api_key=api_key)

# Блок расчёта статистики
total_finished = 0
total_wins = 0
total_losses = 0

for item in st.session_state.history:
    if item['status'] == "✅ Проход":
        total_wins += 1
        total_finished += 1
    elif item['status'] == "❌ Проигрыш":
        total_losses += 1
        total_finished += 1

win_rate = (total_wins / total_finished * 100) if total_finished > 0 else 0

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Ваша статистика")
st.sidebar.write(f"🟢 Побед: **{total_wins}**")
st.sidebar.write(f"🔴 Поражений: **{total_losses}**")
st.sidebar.metric(label="Проходимость (Win Rate)", value=f"{win_rate:.1f}%" if total_finished > 0 else "0.0%")

today_date = datetime.date.today().strftime("%d.%m.%Y")
current_time = datetime.datetime.now().strftime("%H:%M")

st.subheader(f"⏱ Текущее время: {current_time} МСК ({today_date})")
st.info("Нажми кнопку ниже — ИИ сам через поиск в интернете просканирует Flashscore, SofaScore и сайты спортивных экспертов, найдет реальные матчи и выдаст экспертный прогноз.")

num_signals = st.slider("Количество сигналов", 1, 3, 2)

if st.button("🔍 Авто-поиск матчей с Flashscore/SofaScore и анализом экспертов", type="primary"):
    if not api_key:
        st.error("⚠️ Введите ключ Gemini API в боковой панели слева!")
    else:
        with st.spinner("Ищем матчи на Flashscore/SofaScore, анализируем мнения экспертов в сети..."):
            try:
                # Включаем инструмент веб-поиска для реального сканирования сети
                model = genai.GenerativeModel(
                    model_name='gemini-3.6-flash',
                    tools=[{"google_search": {}}]
                )
                
                prompt = f"""
                Сегодня {today_date}, текущее время {current_time} МСК.
                Ты профессиональный спортивный аналитик, скаут и беттор. 
