# News_pulse-app
This project, News Sentiment Dashboard, is a web application built using Streamlit that provides real-time news headlines and performs sentiment analysis on them. The application allows users to quickly gauge the overall emotional tone of current events, classifying news articles as positive, negative, or neutral.
Core Features
User Authentication: Secure user login and registration to ensure a personalized experience.

Real-time News Feed: Fetches live news headlines from a public API to keep the content fresh and relevant.

Sentiment Analysis: Utilizes a robust sentiment analysis system to classify the tone of each article title. The application's core logic for sentiment analysis is located in the analyze_sentiment function, which uses the VADER (Valence Aware Dictionary and sEntiment Reasoner) library.

Data Visualization: Presents the sentiment data in a clear, interactive bar chart, offering a visual summary of the positive, negative, and neutral articles.

Fallback Heuristic: The application is designed for resilience. If the VADER library is not available, a simple fallback system based on a dictionary of positive and negative words is used to ensure the sentiment analysis feature remains functional.

