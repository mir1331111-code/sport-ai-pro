import streamlit as st
from google import genai
import datetime

st.set_page_config(page_title="Flashscore & SofaScore Auto-Sniper", page_icon="🤖", layout="centered")

st.markdown("""
<h1 style='text-align: center;'>🤖 Auto-Sniper: Авто-поиск матчей</h1>
<p style='text-align: center; color: gray;'>ИИ анализирует текущие матчи и дает экспертные прогнозы.</p>
""", unsafe_allow_html=True)

if 'history' not in st.session_state:
    st.session_state.history = []

st.sidebar.header("⚙️ Настройки и Статистика")
api_key = st.sidebar.text_input("Ключ Gemini API", type="password")

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
st.info("Нажми кнопку ниже — ИИ сформирует экспертные прогнозы на актуальные матчи.")

num_signals = st.slider("Количество сигналов", 1, 3, 2)

if st.button("🔍 Авто-поиск матчей и анализ экспертов", type="primary"):
    if not api_key:
        st.error("⚠️ Введите ключ Gemini API в боковой панели слева!")
    else:
        with st.spinner("Анализируем матчи через gemini-3.6-flash..."):
            try:
                client = genai.Client(api_key=api_key)
                
                prompt = (
                    f"Сегодня {today_date}, текущее время {current_time} МСК. "
                    "Ты профессиональный спортивный аналитик и беттор. "
                    "Сформируй прогноз на актуальные матчи (футбол, теннис, баскетбол, волейбол и др.), которые идут или планируются сегодня. "
                    f"Выбери {num_signals} надежных матча. "
                    "Для каждого сигнала укажи: "
                    "- ⏱ Статус матча / Время. "
                    "- 🌐 Турнир. "
                    "- ⚠️ Уровень риска (🟢 Ультра-надежный или 🟡 Стандартный). "
                    "- 🏆 Событие (Команды/игроки). "
                    "- 🎯 Сигнал для ставки (Исход и коэффициент). "
                    "- 📈 Вероятность прохода (в %). "
                    "- 💡 Аналитика и обоснование прогноза."
                )
                
                response = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=prompt,
                )
                
                new_signal = {
                    "date": f"{today_date} в {current_time}",
                    "content": response.text,
                    "status": "⌛ Ожидание"
                }
                st.session_state.history.insert(0, new_signal)
                st.success("Сигналы успешно созданы!")
                
            except Exception as e:
                st.error(f"Ошибка при запросе к Gemini API: {e}")

st.markdown("---")
st.subheader("📊 Трекер исходов и история сигналов")

if not st.session_state.history:
    st.info("История пуста. Запусти поиск выше.")
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
        
