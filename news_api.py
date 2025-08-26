import requests

API_KEY = "7b19a1553606f09a781a97e4c173d775"  # replace with your key
BASE_URL = "https://gnews.io/api/v4/top-headlines"

def fetch_news(query="latest", lang="en"):
    params = {
        "q": query,
        "lang": lang,
        "country": "us",
        "max": 10,
        "apikey": API_KEY
    }
    response = requests.get(BASE_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        return data.get("articles", [])
    else:
        return []
