import streamlit as st
import google.generativeai as genai
import datetime

st.set_page_config(page_title="Flashscore & SofaScore Auto-Sniper", page_icon="🤖", layout="centered")

st.markdown("""
<h1 style='text-align: center;'>🤖 Auto-Sniper: Авто-поиск с Flashscore & SofaScore</h1>
<p style='text-align: center; color: gray;'>ИИ самостоятельно сканирует интернет, Flashscore, SofaScore и мнения экспертов, находя реальные матчи и давая точные прогнозы.</p>
""", unsafe_allow_html=True)

if 'history' not in st.session_state:
    st.session_state.history = []

st.sidebar.header("⚙️ Настройки и Статистика")
api_key = st.sidebar.text_input("Ключ Gemini API", type="password")

# Выбор модели прямо в интерфейсе на случай ограничений ключа
selected_model = st.sidebar.selectbox(
    "Модель Gemini",
    ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
)

if api_key:
    genai.configure(api_key=api_key)

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
        with st.spinner(f"Ищем матчи через модель {selected_model} (Flashscore/SofaScore)..."):
            try:
                # Подключаем поиск, если модель поддерживает инструменты
                if "1.5" in selected_model:
                    model = genai.GenerativeModel(
                        model_name=selected_model,
                        tools='google_search_retrieval'
                    )
                else:
                    model = genai.GenerativeModel(model_name=selected_model)
                
                prompt = (
                    f"Сегодня {today_date}, текущее время {current_time} МСК. "
                    "Ты профессиональный спортивный аналитик, скаут и беттор. "
                    "Используй поиск в интернете, чтобы найти реальные матчи, которые идут прямо сейчас в лайве или начнутся в ближайшее время сегодня на спортивных порталах Flashscore и SofaScore (футбол, теннис, баскетбол, волейбол и др.). "
                    "Также изучи актуальные мнения, прогнозы и аналитику спортивных экспертов и капперов по этим матчам в сети. "
                    f"На основе реальных данных из поиска выбери {num_signals} самых надежных матча с высокой вероятностью прохода. "
                    "Для каждого сигнала укажи: "
                    "- ⏱ Статус матча (Идет в лайве, счет/минута/сет или Старт во столько-то). "
                    "- 🌐 Источник / Турнир (Название турнира и данные с Flashscore/SofaScore). "
                    "- ⚠️ Уровень риска (🟢 Ультра-надежный или 🟡 Стандартный). "
                    "- 🏆 Событие (Точные команды/игроки). "
                    "- 🎯 Сигнал для ставки (Точный рынок, исход и коэффициент). "
                    "- 📈 Вероятность прохода (в %). "
                    "- 💡 Аналитика и мнения экспертов (Сводка того, что говорят эксперты в сети по этому матчу, текущая статистика, почему прогноз обоснован)."
                )
                
                response = model.generate_content(prompt)
                
                new_signal = {
                    "date": f"{today_date} в {current_time}",
                    "content": response.text,
                    "status": "⌛ Ожидание"
                }
                st.session_state.history.insert(0, new_signal)
                st.success("Сигналы успешно найдены и проанализированы!")
                
            except Exception as e:
                st.error(f"Ошибка при запросе к Gemini API: {e}\n\n💡 Попробуй переключить модель на `gemini-1.5-pro` или `gemini-pro` в боковой панели слева.")

st.markdown("---")
st.subheader("📊 Трекер исходов и история сигналов")

if not st.session_state.history:
    st.info("История пуста. Запусти авто-поиск выше.")
else:
    if st.button("🗑 Очистить всю историю"):
        st.session_state.history = []
        st.rerun()

    for idx, item in enumerate(st.session_state.history):
        status = item['status']
        
        if status == "✅ Проход":
            bg_color, border_color, text_color = "#d4edda", "#28a745", "#155724"
        elif status == "❌ Проигрыш":
            bg_color, border_color, text_color = "#f8d7da", "#dc3545", "#721c24"
        else:
            bg_color, border_color, text_color = "#fff3cd", "#ffc107", "#856404"

        signal_num = len(st.session_state.history) - idx
        
        st.markdown(f"""
        <div style="background-color: {bg_color}; border-left: 6px solid {border_color}; padding: 12px; border-radius: 6px; margin-top: 15px; margin-bottom: 5px; color: {text_color};">
            <b>Сигнал #{signal_num}</b> (Запрошен: {item['date']}) &nbsp;|&nbsp; Статус: <b>{status}</b>
        </div>
        """, unsafe_allow_html=True)

        with st.expander(f"📄 Показать аналитику и прогноз #{signal_num}"):
            st.write(item['content'])

        col1, col2, col3 = st.columns(3)
        if col1.button("🟢 Проход", key=f"win_{idx}"):
            st.session_state.history[idx]['status'] = "✅ Проход"
            st.rerun()
        if col2.button("🔴 Проигрыш", key=f"loss_{idx}"):
            st.session_state.history[idx]['status'] = "❌ Проигрыш"
            st.rerun()
        if col3.button("⏳ Ожидание", key=f"pend_{idx}"):
            st.session_state.history[idx]['status'] = "⌛ Ожидание"
            st.rerun()
        
        st.markdown("---")
