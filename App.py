    selected_leagues = st.multiselect(
        "Отметьте лиги и турниры для анализа:",
        options=list(leagues_dict.keys()),
        default=[
            "󠁧󠁢󠁮󠁿 Англия (АПЛ)", 
            "🇸 Испания (Ла Лига)", 
            "🇷🇺 Россия (РПЛ)",
            "🏆 Лига Чемпионов (УЕФА)"
        ]
    )
