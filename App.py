import os
import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="Sport AI Pro - Multi-Sport Scanner", page_icon="⚽", layout="wide")

st.title("⚽ Sport AI Pro: Multi-Sport Scanner & Analyzer")
st.markdown("Автоматизированный сканер и оценка предматчевых и лайв-коэффициентов с помощью ИИ.")

api_key = st.sidebar.text_input("Введите Gemini API Key", type="password")

sport = st.selectbox("Выберите вид спорта", ["Футбол", "Хоккей", "Баскетбол", "Теннис", "Волейбол"])
match_info = st.text_area("Введите данные матча и коэффициенты:", height=150, placeholder="Например: Команда А - Команда Б, КФ: 1.85 / 3.40 / 4.20...")

if st.button("Запустить анализ"):
    if not api_key:
        st.error("Пожалуйста, укажите Gemini API Key в боковой панели.")
    elif not match_info:
        st.error("Пожалуйста, введите информацию о матче.")
    else:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            
            prompt = f"""
Ты профессиональный спортивный аналитик и эксперт по статистике и беттингу. 
Проанализируй следующие данные для дисциплины {sport}:
{match_info}

Предоставь структурированный отчёт, включающий:
1. Оценку вероятностей и поиск валуйных исходов (Value Betting).
2. Ключевые риски и статистические факторы.
3. Итоговую рекомендацию по прогнозу.
"""
            with st.spinner("Анализируем данные..."):
                response = model.generate_content(prompt)
                st.subheader("Результаты анализа")
                st.markdown(response.text)
        except Exception as e:
            st.error(f"Произошла ошибка при обращении к API: {e}")
            
