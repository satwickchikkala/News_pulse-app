import streamlit as st
import sqlite3
import requests
from datetime import datetime, timedelta
from auth import create_user, verify_user  # Import auth functions

import altair as alt
import pandas as pd

# Sentiment analysis setup
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _vader_analyzer = SentimentIntensityAnalyzer()
except Exception:
    _vader_analyzer = None

def analyze_sentiment(text: str):
    """Return (label, score) using VADER if available, else a simple heuristic."""
    if not text:
        return "neutral", 0.0
    text = text.strip()
    if _vader_analyzer is not None:
        scores = _vader_analyzer.polarity_scores(text)
        compound = scores.get("compound", 0.0)
        if compound >= 0.05:
            return "positive", compound
        elif compound <= -0.05:
            return "negative", compound
        else:
            return "neutral", compound
    # Fallback heuristic
    pos_words = ["good","great","excellent","positive","growth","win","success","benefit","surge","record","best","strong"]
    neg_words = ["bad","poor","terrible","negative","loss","fail","decline","drop","worst","weak","fraud","lawsuit"]
    pos = sum(w in text.lower() for w in pos_words)
    neg = sum(w in text.lower() for w in neg_words)
    if pos > neg:
        return "positive", (pos-neg)/10.0
    if neg > pos:
        return "negative", -(neg-pos)/10.0
    return "neutral", 0.0

def sentiment_badge(label: str) -> str:
    color = {"positive":"#10b981","neutral":"#6b7280","negative":"#ef4444"}.get(label,"#6b7280")
    emoji = {"positive":"😊","neutral":"😐","negative":"☹️"}.get(label,"😐")
    return f'<span style="background:{color}1A;color:{color};padding:6px 10px;border-radius:999px;font-size:0.9em;">{emoji} {label.title()}</span>'

def draw_sentiment_chart(sentiment_counts, title='Sentiment Analysis'):
    """Draw a bar chart of sentiment counts using Altair."""
    # Convert dict to DataFrame
    data = pd.DataFrame([
        {"sentiment": "Positive", "count": sentiment_counts.get("positive", 0)},
        {"sentiment": "Neutral", "count": sentiment_counts.get("neutral", 0)},
        {"sentiment": "Negative", "count": sentiment_counts.get("negative", 0)},
    ])

    # Create the Altair chart
    chart = alt.Chart(data).mark_bar().encode(
        x=alt.X('sentiment', sort=['Positive', 'Neutral', 'Negative']),
        y='count',
        color=alt.Color('sentiment', scale=alt.Scale(domain=['Positive', 'Neutral', 'Negative'], range=['#10b981', '#6b7280', '#ef4444'])),
        tooltip=['sentiment', 'count']
    ).properties(
        title=title
    ).interactive()

    # Display the chart in Streamlit
    st.altair_chart(chart, use_container_width=True)

# -------------------------------
# Page Configuration
# -------------------------------
st.set_page_config(
    page_title="News Pulse",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------
# Authentication Setup
# -------------------------------
# Initialize session state variables
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None
if "register" not in st.session_state:
    st.session_state.register = False

# -------------------------------
# Database setup
# -------------------------------
def get_connection():
    return sqlite3.connect("news_pulse.db")

def create_table():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT,
            published_at TEXT,
            image_url TEXT,
            source TEXT,
            category TEXT,
            saved_at TEXT DEFAULT CURRENT_TIMESTAMP,
            username TEXT
        )
    """)
    
    # Check current columns
    cursor.execute("PRAGMA table_info(articles)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Add any missing new columns (including username)
    new_columns = {
        'image_url': 'TEXT',
        'source': 'TEXT',
        'category': 'TEXT',
        'saved_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
        'username': 'TEXT'
    }
    for col_name, col_type in new_columns.items():
        if col_name not in columns:
            cursor.execute(f"ALTER TABLE articles ADD COLUMN {col_name} {col_type}")
    
    # Add a uniqueness constraint per-user to avoid duplicates of the same link
    # SQLite can't add UNIQUE easily post-hoc; create an index that enforces uniqueness pair if not exists
    # (Creates a unique index on (username, link))
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_user_link_unique
        ON articles(username, link)
    """)

    conn.commit()
    conn.close()

create_table()

def save_article(title, link, published_at, image_url, source="Unknown", category="General", username=None):
    """Save an article uniquely per user."""
    if not username:
        return False, "Not logged in."
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if article already exists for this user to avoid duplicates
        cursor.execute("SELECT COUNT(*) FROM articles WHERE link = ? AND username = ?", (link, username))
        if cursor.fetchone()[0] > 0:
            conn.close()
            return False, "Article already saved!"
        
        # Insert new article
        cursor.execute(
            "INSERT INTO articles (title, link, published_at, image_url, source, category, saved_at, username) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(title) if title else "No Title", 
             str(link) if link else "", 
             str(published_at) if published_at else "Unknown", 
             str(image_url) if image_url else "",
             str(source) if source else "Unknown",
             str(category) if category else "General",
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             str(username)),
        )
        conn.commit()
        conn.close()
        return True, "Article saved successfully!"
    except sqlite3.IntegrityError:
        # Unique index hit (username, link)
        if 'conn' in locals():
            conn.close()
        return False, "Article already saved!"
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return False, f"Error saving article: {str(e)}"

def fetch_articles_from_db(username=None):
    """Fetch saved articles for the logged-in user only."""
    if not username:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT title, link, published_at, image_url, source, category, saved_at 
        FROM articles 
        WHERE username = ?
        ORDER BY id DESC
    """, (username,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_saved_articles_count(username=None):
    if not username:
        return 0
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM articles WHERE username = ?", (username,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def delete_saved_article(link: str, username: str) -> bool:
    """Delete a saved article for the given user by its link."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM articles WHERE username = ? AND link = ?", (username, link))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted
    except Exception:
        try:
            conn.close()
        except:
            pass
        return False

# -------------------------------
# API Fetch (with caching)
# -------------------------------
API_KEY = "YOUR_API_KEY"  # Replace with st.secrets["GNEWS_API_KEY"] in production

@st.cache_data(ttl=300, show_spinner=False)
def fetch_news(query="technology", time_filter="Anytime", max_articles=10):
    # Build URL
    url = f"https://gnews.io/api/v4/search?q={query}&lang=en&max={max_articles}&token={API_KEY}"

    if time_filter == "Past 24h":
        from_date = (datetime.utcnow() - timedelta(days=1)).isoformat("T") + "Z"
        url += f"&from={from_date}"
    elif time_filter == "Past week":
        from_date = (datetime.utcnow() - timedelta(days=7)).isoformat("T") + "Z"
        url += f"&from={from_date}"

    # Make request
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        return data.get("articles", [])
    else:
        # Return empty list on API error; UI handles messaging
        return []

# -------------------------------
# Theme Toggle (Dark/Light)
# -------------------------------
if "theme" not in st.session_state:
    st.session_state["theme"] = "dark"

def toggle_theme():
    st.session_state["theme"] = "light" if st.session_state["theme"] == "dark" else "dark"

# -------------------------------
# Login/Register Form
# -------------------------------
def show_login_form():
    """Display login form with enhanced UI"""
    # Create centered layout
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style="text-align: center; padding: 50px 0 30px 0;">
            <h1 style="font-size: 4em; margin-bottom: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
                📰 News Pulse
            </h1>
            <p style="font-size: 1.2em; color: rgba(255,255,255,0.8); margin-bottom: 30px;">
                Your Gateway to Global News
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Login/Register container
        with st.container():
            if st.session_state.register:
                st.markdown("""
                <div style="background: rgba(255,255,255,0.1); backdrop-filter: blur(20px); 
                     border-radius: 20px; padding: 40px; border: 1px solid rgba(255,255,255,0.1);">
                    <h2 style="text-align: center; color: white; margin-bottom: 30px; font-size: 2em;">
                        🎯 Create Your Account
                    </h2>
                </div>
                """, unsafe_allow_html=True)
                
                with st.form("register_form"):
                    new_username = st.text_input("👤 Username", placeholder="Enter your username")
                    new_email = st.text_input("📧 Email", placeholder="Enter your email")
                    new_password = st.text_input("🔒 Password", type="password", placeholder="Create a strong password")
                    confirm_password = st.text_input("🔐 Confirm Password", type="password", placeholder="Confirm your password")
                    
                    submitted = st.form_submit_button("🚀 Create Account", use_container_width=True)
                    
                    if submitted:
                        if not new_username or not new_password:
                            st.error("Username and password are required!")
                        elif len(new_password) < 6:
                            st.error("Password must be at least 6 characters long!")
                        elif new_password != confirm_password:
                            st.error("Passwords do not match!")
                        else:
                            success, message = create_user(new_username, new_password, new_email)
                            if success:
                                st.success("✅ " + message)
                                st.balloons()
                                st.session_state.register = False
                                st.rerun()
                            else:
                                st.error("❌ " + message)
                
                st.markdown("<div style='text-align: center; margin-top: 20px; color: rgba(255,255,255,0.8);'>Already have an account?</div>", unsafe_allow_html=True)
                if st.button("🔑 Login instead", use_container_width=True):
                    st.session_state.register = False
                    st.rerun()
                    
            else:
                st.markdown("""
                <div style="background: rgba(255,255,255,0.1); backdrop-filter: blur(20px); 
                     border-radius: 20px; padding: 40px; border: 1px solid rgba(255,255,255,0.1);">
                    <h2 style="text-align: center; color: white; margin-bottom: 30px; font-size: 2em;">
                        🔐 Welcome Back
                    </h2>
                </div>
                """, unsafe_allow_html=True)
                
                with st.form("login_form"):
                    username = st.text_input("👤 Username", placeholder="Enter your username")
                    password = st.text_input("🔒 Password", type="password", placeholder="Enter your password")
                    
                    submitted = st.form_submit_button("🚀 Login", use_container_width=True)
                    
                    if submitted:
                        if not username or not password:
                            st.error("Please enter both username and password!")
                        else:
                            success, message = verify_user(username, password)
                            if success:
                                st.session_state.authenticated = True
                                st.session_state.username = username
                                st.success("✅ " + message)
                                st.balloons()
                                st.rerun()
                            else:
                                st.error("❌ " + message)
                
                st.markdown("<div style='text-align: center; margin-top: 20px; color: rgba(255,255,255,0.8);'>Don't have an account?</div>", unsafe_allow_html=True)
                if st.button("📝 Register now", use_container_width=True):
                    st.session_state.register = True
                    st.rerun()

        # Demo credentials info
        with st.expander("🎯 Demo Credentials", expanded=False):
            st.info("""
            **For testing purposes:**
            - Username: demo
            - Password: demo123
            
            Or create your own account above!
            """)

# Enhanced CSS with modern animations and glassmorphism
def load_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css');

    * {{
        font-family: 'Inter', sans-serif;
    }}

    /* Hide Streamlit elements */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    .stDeployButton {{display:none;}}

    /* Custom scrollbar */
    ::-webkit-scrollbar {{
        width: 8px;
    }}

    ::-webkit-scrollbar-track {{
        background: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
    }}

    ::-webkit-scrollbar-thumb {{
        background: linear-gradient(45deg, #667eea, #764ba2);
        border-radius: 10px;
    }}

    ::-webkit-scrollbar-thumb:hover {{
        background: linear-gradient(45deg, #764ba2, #667eea);
    }}

    /* Animated background */
    .stApp {{
        background: linear-gradient(-45deg, #1a1a2e, #16213e, #0f3460, #1a1a2e);
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite;
        min-height: 100vh;
        color: #ffffff;
    }}

    @keyframes gradientShift {{
        0% {{ background-position: 0% 50%; }}
        50% {{ background-position: 100% 50%; }}
        100% {{ background-position: 0% 50%; }}
    }}

    /* Main header */
    .main-header {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 3.5em;
        font-weight: 800;
        text-align: center;
        margin: 20px 0;
        animation: glow 2s ease-in-out infinite alternate;
    }}

    @keyframes glow {{
        from {{ filter: drop-shadow(0 0 20px rgba(102, 126, 234, 0.3)); }}
        to {{ filter: drop-shadow(0 0 40px rgba(118, 75, 162, 0.5)); }}
    }}

    /* Glassmorphism cards */
    .glass-card {{
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 25px;
        margin: 20px 0;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }}

    .glass-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 20px 40px 0 rgba(31, 38, 135, 0.5);
    }}

    /* Article cards */
    .article-card {{
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 20px;
        margin: 15px 0;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
        cursor: pointer;
    }}

    .article-card::after {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #667eea, #764ba2, #f093fb);
        transform: scaleX(0);
        transition: transform 0.3s ease;
    }}

    .article-card:hover::after {{
        transform: scaleX(1);
    }}

    .article-card:hover {{
        transform: translateY(-8px);
        background: rgba(255, 255, 255, 0.12);
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }}

    /* Enhanced buttons */
    .stButton > button {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 15px 0 rgba(102, 126, 234, 0.3) !important;
    }}

    .stButton > button:hover {{
        transform: translateY(-2px) scale(1.05) !important;
        box-shadow: 0 8px 25px 0 rgba(102, 126, 234, 0.5) !important;
    }}

    /* Sidebar styling */
    .css-1d391kg {{
        background: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(20px) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.1) !important;
    }}

    /* Text styling */
    .article-title {{
        color: #ffffff !important;
        font-size: 1.4em !important;
        font-weight: 600 !important;
        margin-bottom: 15px !important;
        line-height: 1.4 !important;
    }}

    .article-date {{
        color: #667eea !important;
        font-size: 0.9em !important;
        margin-bottom: 15px !important;
        font-weight: 500 !important;
    }}

    .article-source {{
        color: #f093fb !important;
        font-size: 0.85em !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 1px !important;
    }}

    .news-header {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.5em;
        font-weight: 700;
        text-align: center;
        margin: 30px 0;
        animation: fadeInUp 0.8s ease-out;
    }}

    /* Stats cards */
    .stats-card {{
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }}

    .stats-card::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #667eea, #764ba2);
    }}

    .stats-card:hover {{
        transform: translateY(-5px);
        background: rgba(255, 255, 255, 0.15);
    }}

    .stats-number {{
        font-size: 2.5em;
        font-weight: 800;
        color: #667eea;
        margin-bottom: 10px;
    }}

    .stats-label {{
        color: rgba(255, 255, 255, 0.8);
        font-size: 1.1em;
        font-weight: 500;
    }}

    /* Image styling */
    .article-image {{
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
        transition: transform 0.3s ease;
        height: 200px;
        object-fit: cover;
        width: 100%;
    }}

    .article-image:hover {{
        transform: scale(1.05);
    }}

    /* Welcome section */
    .welcome-section {{
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 60px 40px;
        text-align: center;
        margin: 40px 0;
        position: relative;
        overflow: hidden;
    }}

    .welcome-section::before {{
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: conic-gradient(from 0deg, transparent, rgba(102, 126, 234, 0.1), transparent);
        animation: rotate 10s linear infinite;
    }}

    @keyframes rotate {{
        100% {{ transform: rotate(360deg); }}
    }}

    .welcome-content {{
        position: relative;
        z-index: 1;
    }}

    /* Trending topics */
    .trending-topic {{
        background: rgba(255, 255, 255, 0.1) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: white !important;
        border-radius: 20px !important;
        padding: 8px 16px !important;
        margin: 5px !important;
        font-size: 12px !important;
        transition: all 0.3s ease !important;
    }}

    .trending-topic:hover {{
        background: rgba(102, 126, 234, 0.3) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3) !important;
    }}

    /* Loading animation */
    .loading {{
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid rgba(102, 126, 234, 0.3);
        border-radius: 50%;
        border-top-color: #667eea;
        animation: spin 1s ease-in-out infinite;
    }}

    @keyframes spin {{
        to {{ transform: rotate(360deg); }}
    }}

    /* Animations */
    @keyframes fadeInUp {{
        from {{
            opacity: 0;
            transform: translateY(30px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}

    /* Empty state styling */
    .empty-state {{
        text-align: center;
        padding: 60px 20px;
        background: rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        margin: 20px 0;
        border: 2px dashed rgba(255, 255, 255, 0.2);
    }}

    .empty-state-icon {{
        font-size: 4em;
        margin-bottom: 20px;
        opacity: 0.6;
    }}

    .empty-state-title {{
        font-size: 1.8em;
        color: white;
        margin-bottom: 15px;
        font-weight: 600;
    }}

    .empty-state-subtitle {{
        color: rgba(255, 255, 255, 0.7);
        font-size: 1.1em;
        margin-bottom: 25px;
    }}

    /* Input styling */
    .stTextInput > div > div > input {{
        background: rgba(255, 255, 255, 0.1) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: white !important;
        border-radius: 10px !important;
    }}

    .stTextInput > div > div > input:focus {{
        border-color: #667eea !important;
        box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.3) !important;
    }}

    /* Radio button styling */
    .stRadio > div {{
        background: rgba(255, 255, 255, 0.05) !important;
        border-radius: 10px !important;
        padding: 10px !important;
    }}

    /* Form styling */
    .stForm {{
        background: rgba(255, 255, 255, 0.05) !important;
        border-radius: 15px !important;
        padding: 20px !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
    }}
    </style>
    """, unsafe_allow_html=True)

# -------------------------------
# Main Application Logic
# -------------------------------
def main():
    load_css()
    
    if not st.session_state.authenticated:
        show_login_form()
    else:
        # Display the main app content for authenticated users
        show_main_app()

def show_main_app():
    # Sidebar
    show_sidebar()
    
    # Main content
    show_main_content()

def show_sidebar():
    """Enhanced sidebar with better organization"""
    with st.sidebar:
        # User info section
        st.markdown(f"""
        <div class="glass-card" style="text-align: center;">
            <div style="font-size: 3em; margin-bottom: 10px;">👤</div>
            <h3 style="color: #667eea; margin-bottom: 5px;">Welcome</h3>
            <p style="color: rgba(255,255,255,0.8); margin-bottom: 15px;">{st.session_state.username}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Quick stats (user-specific)
        saved_count = get_saved_articles_count(st.session_state.username)
        st.markdown(f"""
        <div class="stats-card">
            <div class="stats-number">{saved_count}</div>
            <div class="stats-label">Saved Articles</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Navigation buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏠 Home", key="home_button", use_container_width=True):
                st.session_state["show_saved"] = False
                st.session_state["articles"] = []
                st.rerun()
        
        with col2:
            if st.button("💾 Saved", key="saved_button", use_container_width=True):
                st.session_state["show_saved"] = True
                st.session_state["articles"] = []
                st.rerun()
        
        if st.button("🚪 Logout", key="logout_button", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.rerun()
        
        st.markdown("---")
        
        # Search section
        st.markdown("""
        <div class="glass-card">
            <h3 style='text-align:center; color:#667eea; font-size: 1.5em; margin-bottom: 20px;'>
                🔍 Search News
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        query = st.text_input("Enter keyword:", value="technology", key="search_query")
        
        time_filter = st.radio(
            "Time Filter:",
            ["Anytime", "Past 24h", "Past week"],
            index=0,
            key="time_filter"
        )
        
        max_articles = st.slider(
            "Number of articles:",
            min_value=5,
            max_value=20,
            value=10,
            key="max_articles"
        )
        
        if st.button("🚀 Search News", key="search_button", use_container_width=True):
            with st.spinner("🔄 Fetching latest news... (cached up to 5 mins)"):
                articles = fetch_news(query, time_filter, max_articles)
                st.session_state["articles"] = articles if articles else []
                st.session_state["show_saved"] = False
                st.session_state["current_query"] = query
                if articles:
                    st.success(f"Found {len(articles)} articles!")
                else:
                    st.warning("No articles found. Try different keywords.")
        
        st.markdown("---")
        
        # Trending topics
        st.markdown("""
        <div class="glass-card">
            <h3 style='color: #667eea; text-align: center; margin-bottom: 15px;'>
                🔥 Trending Topics
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        trending_topics = [
            {"name": "AI", "icon": "🤖"},
            {"name": "Tesla", "icon": "🚗"},
            {"name": "iPhone", "icon": "📱"},
            {"name": "Cricket", "icon": "🏏"},
            {"name": "Startups", "icon": "🚀"},
            {"name": "SpaceX", "icon": "🛸"},
            {"name": "Bitcoin", "icon": "₿"},
            {"name": "Climate", "icon": "🌍"}
        ]
        
        cols = st.columns(2)
        for i, topic in enumerate(trending_topics):
            col = cols[i % 2]
            if col.button(f"{topic['icon']} {topic['name']}", key=f"trend_{i}", use_container_width=True):
                with st.spinner(f"Loading {topic['name']} news... (cached up to 5 mins)"):
                    articles = fetch_news(topic['name'], time_filter, max_articles)
                    st.session_state["articles"] = articles
                    st.session_state["show_saved"] = False
                    st.session_state["current_query"] = topic['name']
                    if articles:
                        st.success(f"Found {len(articles)} articles about {topic['name']}!")
                    else:
                        st.warning(f"No articles found for {topic['name']}.")

def show_main_content():
    """Main content area with improved layouts"""
    
    # Header
    st.markdown('<h1 class="main-header">📰 News Pulse</h1>', unsafe_allow_html=True)
    
    # Initialize session state
    if "articles" not in st.session_state:
        st.session_state["articles"] = []
    if "show_saved" not in st.session_state:
        st.session_state["show_saved"] = False
    
    # Show saved articles
    if st.session_state.get("show_saved", False):
        show_saved_articles()
    # Show search results
    elif st.session_state.get("articles"):
        show_search_results()
    # Show welcome screen
    else:
        show_welcome_screen()

def show_saved_articles():
    """Display saved articles with enhanced UI (user-specific)"""
    st.markdown('<h2 class="news-header">💾 Your Saved Articles</h2>', unsafe_allow_html=True)
    
    saved_articles = fetch_articles_from_db(st.session_state.username)
    
    if saved_articles:
        # Stats section
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-number">{len(saved_articles)}</div>
                <div class="stats-label">Total Saved</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            # Get latest article save date
            latest_date = "N/A"
            if saved_articles:
                try:
                    latest_date = datetime.strptime(saved_articles[0][6], "%Y-%m-%d %H:%M:%S").strftime("%b %d")
                except:
                    latest_date = "Today"
            
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-number" style="font-size: 1.8em;">{latest_date}</div>
                <div class="stats-label">Latest Save</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            # Count unique sources
            sources = set()
            for article in saved_articles:
                if article[4]:  # source column
                    sources.add(article[4])
            
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-number">{len(sources)}</div>
                <div class="stats-label">Sources</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Articles grid
        sentiment_counts_saved = {}
        for i, (title, link, published_at, image_url, source, category, saved_at) in enumerate(saved_articles):
            with st.container():
                st.markdown('<div class="article-card">', unsafe_allow_html=True)
                
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    if image_url and image_url.strip():
                        try:
                            st.image(image_url, use_column_width=True, caption="")
                        except:
                            st.markdown("""
                            <div style="height:200px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            border-radius:12px; display:flex; align-items:center; justify-content:center; 
                            color:white; font-size: 4em;">📰</div>
                            """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div style="height:200px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        border-radius:12px; display:flex; align-items:center; justify-content:center; 
                        color:white; font-size: 4em;">📰</div>
                        """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f'<div class="article-source">📡 {source or "Unknown Source"}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="article-title">{title}</div>', unsafe_allow_html=True)
                    
                    # Date and category info
                    col2a, col2b = st.columns(2)
                    with col2a:
                        st.markdown(f'<div class="article-date">📅 {published_at}</div>', unsafe_allow_html=True)
                    with col2b:
                        st.markdown(f'<div class="article-date">💾 Saved: {saved_at[:10] if saved_at else "Unknown"}</div>', unsafe_allow_html=True)
                    
                    # Action buttons
                    btn_col1, btn_col2 = st.columns([1, 1])
                    with btn_col1:
                        st.markdown(f"[🔗 Read Article]({link})", unsafe_allow_html=True)
                    with btn_col2:
                        st.markdown(f'<span style="color: #f093fb; font-size: 0.9em;">🏷️ {category or "General"}</span>', unsafe_allow_html=True)
                    
                    # Delete button
                    if st.button("🗑️ Delete", key=f"delete_{i}", use_container_width=True):
                        if delete_saved_article(link, st.session_state.username):
                            st.success("✅ Article deleted successfully!")
                            st.rerun() # Rerun to refresh the list
                        else:
                            st.error("❌ Failed to delete article.")
                
                st.markdown('</div><br>', unsafe_allow_html=True)
        
        # Analyze and draw sentiment chart for saved articles
        saved_articles_titles = [article[0] for article in saved_articles]
        sentiment_counts_saved = {}
        for title in saved_articles_titles:
            _label, _score = analyze_sentiment(title)
            sentiment_counts_saved[_label] = sentiment_counts_saved.get(_label, 0) + 1
            
        draw_sentiment_chart(sentiment_counts_saved, title='Saved Articles Sentiment')

    else:
        # Empty state for saved articles
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">📚</div>
            <div class="empty-state-title">No Saved Articles Yet</div>
            <div class="empty-state-subtitle">Start exploring news and save articles that interest you!</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Quick action buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔍 Search Tech News", use_container_width=True):
                articles = fetch_news("technology", "Anytime", 10)
                st.session_state["articles"] = articles
                st.session_state["show_saved"] = False
                st.session_state["current_query"] = "technology"
                st.rerun()
        
        with col2:
            if st.button("📱 Search AI News", use_container_width=True):
                articles = fetch_news("artificial intelligence", "Anytime", 10)
                st.session_state["articles"] = articles
                st.session_state["show_saved"] = False
                st.session_state["current_query"] = "artificial intelligence"
                st.rerun()
        
        with col3:
            if st.button("🌍 World News", use_container_width=True):
                articles = fetch_news("world news", "Anytime", 10)
                st.session_state["articles"] = articles
                st.session_state["show_saved"] = False
                st.session_state["current_query"] = "world news"
                st.rerun()

def show_search_results():
    """Display search results with enhanced UI"""
    current_query = st.session_state.get("current_query", "news")
    articles = st.session_state["articles"]
    
    st.markdown(f'<h2 class="news-header">🌟 Latest Results for "{current_query}" ({len(articles)} articles)</h2>', unsafe_allow_html=True)
    
    if articles:
        sentiment_counts = {}
        # Quick stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-number">{len(articles)}</div>
                <div class="stats-label">Articles Found</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            # Count unique sources
            sources = set()
            for article in articles:
                if article.get("source", {}).get("name"):
                    sources.add(article["source"]["name"])
            
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-number">{len(sources)}</div>
                <div class="stats-label">News Sources</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            # Show time filter applied
            time_filter = st.session_state.get("time_filter", "Anytime")
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-number" style="font-size: 1.5em;">⏰</div>
                <div class="stats-label">{time_filter}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Articles display
        for i, article in enumerate(articles):
            with st.container():
                st.markdown('<div class="article-card">', unsafe_allow_html=True)
                
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    if article.get("image"):
                        try:
                            st.image(article.get("image"), use_column_width=True, caption="")
                        except:
                            st.markdown("""
                            <div style="height:200px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            border-radius:12px; display:flex; align-items:center; justify-content:center; 
                            color:white; font-size: 4em;">📰</div>
                            """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div style="height:200px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        border-radius:12px; display:flex; align-items:center; justify-content:center; 
                        color:white; font-size: 4em;">📰</div>
                        """, unsafe_allow_html=True)
                
                with col2:
                    # Source name
                    source_name = article.get("source", {}).get("name", "Unknown Source")
                    st.markdown(f'<div class="article-source">📡 {source_name}</div>', unsafe_allow_html=True)
                    
                    # Title
                    st.markdown(f'<div class="article-title">{article["title"]}</div>', unsafe_allow_html=True)
                    
                    # Description (if available)
                    if article.get("description"):
                        description = article["description"][:150] + "..." if len(article["description"]) > 150 else article["description"]
                        st.markdown(f'<div style="color: rgba(255,255,255,0.7); margin-bottom: 15px; line-height: 1.5;">{description}</div>', unsafe_allow_html=True)
                    
                    # Sentiment badge
                    _text_for_sent = article.get('description') or article.get('title','')
                    _label, _score = analyze_sentiment(_text_for_sent)
                    st.markdown(sentiment_badge(_label), unsafe_allow_html=True)
                    sentiment_counts[_label] = sentiment_counts.get(_label,0)+1

                    # Date
                    published_date = article.get("publishedAt", "Unknown")
                    if published_date != "Unknown":
                        try:
                            # Format the date nicely
                            date_obj = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
                            formatted_date = date_obj.strftime("%B %d, %Y at %I:%M %p")
                        except:
                            formatted_date = published_date
                    else:
                        formatted_date = "Unknown"
                    
                    st.markdown(f'<div class="article-date">📅 {formatted_date}</div>', unsafe_allow_html=True)
                    
                    # Action buttons
                    btn_col1, btn_col2 = st.columns([1, 1])
                    with btn_col1:
                        st.markdown(f"[🔗 Read Full Article]({article['url']})", unsafe_allow_html=True)
                    with btn_col2:
                        if st.button(f"💾 Save Article", key=f"save_{i}", use_container_width=True):
                            success, message = save_article(
                                article["title"],
                                article["url"],
                                article.get("publishedAt", "Unknown"),
                                article.get("image", ""),
                                source_name,
                                current_query,  # Use search query as category
                                username=st.session_state.username
                            )
                            if success:
                                st.success(f"✅ {message}")
                                st.balloons()
                            else:
                                st.warning(f"⚠️ {message}")
                
                st.markdown('</div><br>', unsafe_allow_html=True)
            # Draw sentiment chart for the current results
        draw_sentiment_chart(sentiment_counts, title='Results Sentiment')
    else:
        # No results found
        st.markdown(f"""
        <div class="empty-state">
            <div class="empty-state-icon">🔍</div>
            <div class="empty-state-title">No Results Found</div>
            <div class="empty-state-subtitle">Try searching with different keywords or adjust your time filter</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Suggested searches
        st.markdown("### 💡 Try These Popular Topics:")
        suggestion_cols = st.columns(4)
        suggestions = [
            {"name": "Technology", "icon": "💻"},
            {"name": "Sports", "icon": "⚽"},
            {"name": "Business", "icon": "💼"},
            {"name": "Science", "icon": "🔬"}
        ]
        
        for i, suggestion in enumerate(suggestions):
            with suggestion_cols[i]:
                if st.button(f"{suggestion['icon']} {suggestion['name']}", use_container_width=True):
                    articles = fetch_news(suggestion['name'].lower(), "Anytime", 10)
                    st.session_state["articles"] = articles
                    st.session_state["current_query"] = suggestion['name']
                    st.rerun()

def show_welcome_screen():
    """Enhanced welcome screen with interactive elements"""
    st.markdown("""
    <div class="welcome-section">
        <div class="welcome-content">
            <h2 style='color: white; margin-bottom: 20px; font-size: 3em; font-weight: 700;'>
                🚀 Welcome to News Pulse!
            </h2>
            <p style='color: rgba(255,255,255,0.9); font-size: 1.4em; margin-bottom: 30px; line-height: 1.6;'>
                Stay informed with the latest news from around the globe. Search, discover, and save articles that matter to you.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Feature highlights
    st.markdown("### ✨ What You Can Do")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="stats-card" style="height: 220px;">
            <div style='font-size: 3.5em; margin-bottom: 15px;'>🔍</div>
            <h3 style='color: #667eea; margin-bottom: 10px;'>Search News</h3>
            <p style='color: rgba(255,255,255,0.8); line-height: 1.4;'>
                Find articles on any topic with our powerful search engine. Filter by time and get the most relevant results.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="stats-card" style="height: 220px;">
            <div style='font-size: 3.5em; margin-bottom: 15px;'>💾</div>
            <h3 style='color: #764ba2; margin-bottom: 10px;'>Save Articles</h3>
            <p style='color: rgba(255,255,255,0.8); line-height: 1.4;'>
                Bookmark interesting articles for later reading. Build your personal news library and never lose track of important stories.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="stats-card" style="height: 220px;">
            <div style='font-size: 3.5em; margin-bottom: 15px;'>🔥</div>
            <h3 style='color: #f093fb; margin-bottom: 10px;'>Trending Topics</h3>
            <p style='color: rgba(255,255,255,0.8); line-height: 1.4;'>
                Explore trending topics and stay updated with the latest happenings in technology, sports, business, and more.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Quick start section
    st.markdown("### 🚀 Quick Start")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("**🌟 Popular Categories**")
        categories = [
            {"name": "Technology", "icon": "💻", "desc": "Latest tech news and innovations"},
            {"name": "Business", "icon": "💼", "desc": "Market updates and business trends"},
            {"name": "Sports", "icon": "⚽", "desc": "Sports news and match updates"},
            {"name": "Health", "icon": "🏥", "desc": "Health and medical breakthroughs"}
        ]
        
        for cat in categories:
            with st.container():
                if st.button(f"{cat['icon']} {cat['name']}", key=f"cat_{cat['name']}", use_container_width=True):
                    with st.spinner(f"Loading {cat['name']} news... (cached up to 5 mins)"):
                        articles = fetch_news(cat['name'].lower(), "Anytime", 10)
                        st.session_state["articles"] = articles
                        st.session_state["show_saved"] = False
                        st.session_state["current_query"] = cat['name']
                        st.rerun()
                st.caption(cat['desc'])
    
    with col2:
        st.markdown("**📊 Your Stats**")
        saved_count = get_saved_articles_count(st.session_state.username)
        
        # User statistics
        st.markdown(f"""
        <div class="glass-card">
            <div style="text-align: center;">
                <div style="font-size: 2.5em; color: #667eea; margin-bottom: 10px;">{saved_count}</div>
                <h4 style="color: white; margin-bottom: 15px;">Articles Saved</h4>
                <p style="color: rgba(255,255,255,0.7); margin-bottom: 20px;">
                    {"Great start! Keep exploring and saving interesting articles." if saved_count > 0 else "Start saving articles to build your personal news collection."}
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Today's date and greeting
        today = datetime.now()
        greeting = "Good morning" if today.hour < 12 else "Good afternoon" if today.hour < 17 else "Good evening"
        
        st.markdown(f"""
        <div class="glass-card" style="text-align: center;">
            <h4 style="color: #764ba2; margin-bottom: 10px;">{greeting}, {st.session_state.username}!</h4>
            <p style="color: rgba(255,255,255,0.8);">📅 {today.strftime("%A, %B %d, %Y")}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Recent news preview
    st.markdown("---")
    st.markdown("### 📈 Recent News Headlines")
    
    with st.spinner("Fetching latest news for preview..."):
        try:
            # Fetch a small number of recent articles on a general topic
            preview_articles = fetch_news("headlines", time_filter="Past 24h", max_articles=5)
            if preview_articles:
                for article in preview_articles:
                    st.markdown(f"**{article['title']}** \n*{article.get('source', {}).get('name', 'Unknown Source')}*")
            else:
                st.info("Couldn't fetch news at this time. Please use the search bar to find articles.")
        except Exception as e:
            st.error(f"An error occurred while fetching news preview: {e}")
    
# Run the main application
if __name__ == "__main__":
    main()
