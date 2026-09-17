# NEURO BET PRO v10.4-cloud

Футбольная аналитика + ставки. Streamlit Cloud ready.

## Деплой на Streamlit Cloud

1. Fork / clone этот репо
2. https://share.streamlit.io/ → New app → выбрать репо
3. Main file: `neuro_bet_pro.py`
4. Advanced settings → Secrets → вставить:
   ```toml
   GEMINI_KEY = ""
   GROK_KEY = ""
   API_FOOTBALL_KEY = "твой_ключ"
   GIST_ID = "id_gist_файла"
   GIST_TOKEN = "ghp_токен_с_scope_gist"
