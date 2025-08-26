📰 News Sentiment Analyzer
📌 Overview

This project is a Streamlit web application that performs sentiment analysis on news headlines and text data.
It helps users quickly determine whether a piece of news or content is positive, negative, or neutral, using VADER Sentiment Analysis.

The app also supports user authentication with a local SQLite database and provides visual insights with interactive charts.

🚀 Features

🔐 User Authentication (Sign Up & Login) using SQLite.

🤖 Sentiment Analysis powered by VADER SentimentIntensityAnalyzer.

If VADER is unavailable, a fallback keyword-based heuristic is used.

📊 Visualization with Altair and Pandas.

📰 News/Text Input – users can paste news or custom text for sentiment check.

🏷️ Sentiment Badges with labels (Positive / Negative / Neutral) and scores.

🛠️ Tech Stack

Frontend/Framework: Streamlit

Database: SQLite

Data Analysis: Pandas, Altair

Sentiment Model: VADER SentimentIntensityAnalyzer

