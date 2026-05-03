import requests
import streamlit as st
from datetime import datetime, timedelta

GNEWS_API_KEY = "YOUR_API_KEY"

@st.cache_data(ttl=300, show_spinner=False)
def fetch_news(query="technology", time_filter="Anytime", max_articles=10):
    url = f"https://gnews.io/api/v4/search?q={query}&lang=en&max={max_articles}&token={GNEWS_API_KEY}"
    if time_filter == "Past 24h":
        from_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        url += f"&from={from_date}"
    elif time_filter == "Past week":
        from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        url += f"&from={from_date}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json().get("articles", [])
    except Exception:
        pass
    return []
