import streamlit as st
from PIL import Image
from google import genai
from google.genai import types
import io

# Настройка страницы Streamlit
st.set_page_config(
    page_title="Анализ скриншотов и матчей",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 Анализатор скриншотов с Gemini")

# Боковая панель для ввода API ключа
st.sidebar.header("Настройки")
gemini_key = st.sidebar.text_input("Введите ваш Gemini API ключ:", type="password")

# Загрузка скриншота
uploaded_file = st.sidebar.file_uploader("Загрузите скриншот", type=["png", "jpg", "jpeg"])

image = None
if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Загруженный скриншот", use_column_width=True)


def fetch_and_analyze_matches(prompt: str, api_key: str):
    """Функция для текстового анализа с использованием поиска Google"""
    error_log = []
    raw_text = ""
    
    if api_key:
        try:
            g_client = genai.Client(api_key=api_key)
            # Используем актуальную модель gemini-2.0-flash
            for g_model in ["gemini-2.0-flash"]:
                try:
                    response = g_client.models.generate_content(
                        model=g_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            tools=[{"google_search": {}}],
                            response_mime_type="application/json"
                        ),
                    )
                    if response and response.text:
                        raw_text = response.text.strip()
                        break
                except Exception as e:
                    error_log.append(f"Gemini ({g_model}): {e}")
                    continue
        except Exception as e:
            error_log.append(f"Gemini Init Error: {e}")
            
    return raw_text, error_log


def analyze_screenshot_with_two_brains(image_obj, prompt: str, api_key: str):
    """Функция для глубокого анализа скриншота с помощью Vision модели"""
    if not api_key:
        return "Ошибка: Не указан API ключ Gemini."
    
    try:
        g_client = genai.Client(api_key=api_key)
        raw_text = ""
        last_error = ""
        
        # Используем актуальную модель gemini-2.0-flash
        for g_model in ["gemini-2.0-flash"]:
            try:
                response = g_client.models.generate_content(
                    model=g_model,
                    contents=[image_obj, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    ),
                )
                if response and response.text:
                    raw_text = response.text.strip()
                    break
            except Exception as e:
                last_error = str(e)
                continue
                
        if not raw_text and last_error:
            return f"Ошибка API: {last_error}"
            
        return raw_text
    except Exception as e:
        return f"Критическая ошибка: {e}"


# Основной интерфейс приложения
user_prompt = st.text_area("Введите ваш запрос или промпт:", "Проанализируй данный интерфейс и дай детальный отчет.")

if st.button("🧠 Запустить глубокий анализ скриншота"):
    if not gemini_key:
        st.error("Пожалуйста, введите Gemini API ключ в боковой панели!")
    elif image is None:
        st.error("Пожалуйста, загрузите скриншот перед запуском анализа!")
    else:
        with st.spinner("Анализируем скриншот..."):
            result = analyze_screenshot_with_two_brains(image, user_prompt, gemini_key)
            st.subheader("Результат анализа:")
            st.markdown(result)
