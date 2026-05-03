import streamlit as st
import re
from datetime import datetime

# ── project modules ───────────────────────────────────────────
from firebase_config import (
    sign_up_email, sign_in_email, send_password_reset,
)
from database import (save_article, fetch_saved_articles,
                      delete_article, count_saved_articles)
from news_api import fetch_news

# ── optional deps ─────────────────────────────────────────────
try:
    import altair as alt
    import pandas as pd
    _ALTAIR = True
except ImportError:
    _ALTAIR = False

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _vader = SentimentIntensityAnalyzer()
except Exception:
    _vader = None

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NewsPulse",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────
# SESSION STATE DEFAULTS
# ─────────────────────────────────────────────────────────────
for k, v in {
    "authenticated": False,
    "uid":           None,
    "id_token":      None,
    "email":         None,
    "display_name":  None,
    "page":          "home",
    "articles":      [],
    "current_query": "",
    "time_filter":   "Anytime",
    "auth_view":     "login",
    "google_error":  None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$", email.strip()))

def analyze_sentiment(text: str):
    if not text:
        return "neutral", 0.0
    if _vader:
        s = _vader.polarity_scores(text)
        c = s["compound"]
        if   c >=  0.05: return "positive", c
        elif c <= -0.05: return "negative", c
        else:            return "neutral",  c
    pos = sum(w in text.lower() for w in ["good","great","win","growth","success","surge","record"])
    neg = sum(w in text.lower() for w in ["bad","crash","fail","loss","decline","drop","worst"])
    if pos > neg: return "positive",  0.5
    if neg > pos: return "negative", -0.5
    return "neutral", 0.0

def sentiment_badge(label):
    cfg = {
        "positive": ("#10b981","😊"),
        "neutral":  ("#94a3b8","😐"),
        "negative": ("#f43f5e","😟"),
    }.get(label, ("#94a3b8","😐"))
    return (
        f'<span style="background:{cfg[0]}22;color:{cfg[0]};'
        f'border:1px solid {cfg[0]}44;padding:3px 10px;'
        f'border-radius:999px;font-size:0.78em;font-weight:600;">'
        f'{cfg[1]} {label.title()}</span>'
    )

def summarize_text(text: str, sentences: int = 2) -> str:
    if not text or len(text.strip()) < 40:
        return "Not enough content to summarize."
    try:
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.nlp.tokenizers    import Tokenizer
        from sumy.summarizers.luhn  import LuhnSummarizer
        import nltk
        for tok in ("punkt", "punkt_tab"):
            try:    nltk.data.find(f"tokenizers/{tok}")
            except LookupError: nltk.download(tok, quiet=True)
        parser     = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = LuhnSummarizer()
        result     = summarizer(parser.document, sentences)
        out        = " ".join(str(s) for s in result).strip()
        return out if out else text[:300] + "…"
    except Exception:
        return text[:300] + "…"

def draw_sentiment_chart(counts: dict, title: str = "Sentiment"):
    if not _ALTAIR or not counts:
        return
    df = pd.DataFrame([
        {"Sentiment": "Positive", "Count": counts.get("positive", 0)},
        {"Sentiment": "Neutral",  "Count": counts.get("neutral",  0)},
        {"Sentiment": "Negative", "Count": counts.get("negative", 0)},
    ])
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
        .encode(
            x=alt.X("Sentiment:N", sort=["Positive","Neutral","Negative"],
                    axis=alt.Axis(labelColor="#94a3b8", tickColor="#1e293b", domainColor="#1e293b")),
            y=alt.Y("Count:Q",
                    axis=alt.Axis(labelColor="#94a3b8", tickColor="#1e293b",
                                  domainColor="#1e293b", gridColor="#1e293b")),
            color=alt.Color("Sentiment:N", scale=alt.Scale(
                domain=["Positive","Neutral","Negative"],
                range= ["#10b981","#94a3b8","#f43f5e"]
            ), legend=None),
            tooltip=["Sentiment","Count"],
        )
        .properties(
            title=alt.TitleParams(title, color="#e2e8f0"),
            background="transparent", height=200
        )
    )
    st.altair_chart(chart, use_container_width=True)

def format_date(raw: str) -> str:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%b %d, %Y")
    except Exception:
        return raw or "Unknown"

# ─────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────
def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,400&display=swap');

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body, [data-testid="stAppViewContainer"] {
        background: #080c14 !important;
        color: #e2e8f0;
        font-family: 'DM Sans', sans-serif;
    }
    [data-testid="stAppViewContainer"]  { padding: 0 !important; }
    [data-testid="stHeader"]            { display: none !important; }
    [data-testid="stSidebar"]           { display: none !important; }
    #MainMenu, footer, .stDeployButton  { display: none !important; }
    section[data-testid="stMain"] > div { padding: 0 !important; }
    [data-testid="stMainBlockContainer"]{ padding: 0 !important; max-width: 100% !important; }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

    h1,h2,h3 { font-family: 'Syne', sans-serif; }

    /* ── navbar ─────────────────────────────────── */
    .np-nav {
        position: sticky; top: 0; z-index: 1000;
        display: flex; align-items: center; justify-content: space-between;
        padding: 0 40px; height: 64px;
        background: rgba(8,12,20,0.95);
        backdrop-filter: blur(18px);
        border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .np-nav-logo {
        font-family: 'Syne', sans-serif;
        font-size: 1.4rem; font-weight: 800;
        background: linear-gradient(135deg, #38bdf8, #818cf8);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text; letter-spacing: -0.5px;
    }
    .np-nav-user {
        display: flex; align-items: center; gap: 10px;
        padding: 6px 14px; border-radius: 999px;
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.08);
        font-size: 0.85rem; color: #94a3b8;
    }
    .np-nav-avatar {
        width: 28px; height: 28px; border-radius: 50%;
        background: linear-gradient(135deg, #38bdf8, #818cf8);
        display: flex; align-items: center; justify-content: center;
        font-size: 0.75rem; font-weight: 700; color: #fff;
    }

    /* ── hero ────────────────────────────────────── */
    .np-hero {
        padding: 72px 40px 48px; text-align: center;
        background: radial-gradient(ellipse 80% 50% at 50% -10%,
                    rgba(56,189,248,0.12) 0%, transparent 70%);
    }
    .np-hero-tag {
        display: inline-block; margin-bottom: 20px;
        padding: 4px 14px; border-radius: 999px;
        background: rgba(56,189,248,0.1);
        border: 1px solid rgba(56,189,248,0.3);
        color: #38bdf8; font-size: 0.78rem; font-weight: 600;
        letter-spacing: 1.5px; text-transform: uppercase;
    }
    .np-hero-title {
        font-family: 'Syne', sans-serif;
        font-size: clamp(2.4rem, 5vw, 4rem);
        font-weight: 800; line-height: 1.08;
        letter-spacing: -1.5px; color: #f1f5f9; margin-bottom: 16px;
    }
    .np-hero-title span {
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .np-hero-sub { color: #64748b; font-size: 1.05rem; margin-bottom: 36px; }

    /* ── trending ────────────────────────────────── */
    .np-trending {
        padding: 0 40px 32px;
        display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
    }
    .np-trending-label {
        font-size: 0.75rem; font-weight: 700;
        letter-spacing: 1.5px; text-transform: uppercase;
        color: #475569; white-space: nowrap;
    }

    /* ── section heading ─────────────────────────── */
    .np-section-head {
        padding: 0 40px 20px;
        font-family: 'Syne', sans-serif;
        font-size: 1.1rem; font-weight: 700;
        color: #94a3b8; letter-spacing: -0.3px;
    }
    .np-section-head span { color: #e2e8f0; }

    /* ── article card ────────────────────────────── */
    .np-card {
        background: #0f172a;
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 16px; overflow: hidden;
        transition: transform 0.22s ease, border-color 0.22s ease, box-shadow 0.22s ease;
        display: flex; flex-direction: column;
        margin-bottom: 20px;
    }
    .np-card:hover {
        transform: translateY(-4px);
        border-color: rgba(56,189,248,0.25);
        box-shadow: 0 20px 40px -10px rgba(0,0,0,0.5);
    }
    .np-card-img { width: 100%; height: 190px; object-fit: cover; display: block; background: #1e293b; }
    .np-card-img-placeholder {
        width: 100%; height: 190px;
        background: linear-gradient(135deg, #0f2a44 0%, #1a1040 100%);
        display: flex; align-items: center; justify-content: center;
        font-size: 2.5rem; color: rgba(255,255,255,0.12);
    }
    .np-card-body { padding: 18px 18px 14px; flex: 1; display: flex; flex-direction: column; }
    .np-card-source {
        font-size: 0.72rem; font-weight: 700; letter-spacing: 1.2px;
        text-transform: uppercase; color: #38bdf8; margin-bottom: 8px;
    }
    .np-card-title {
        font-family: 'Syne', sans-serif;
        font-size: 1rem; font-weight: 700; line-height: 1.45;
        color: #e2e8f0; margin-bottom: 10px; flex: 1;
    }
    .np-card-desc {
        font-size: 0.85rem; color: #64748b; line-height: 1.55; margin-bottom: 12px;
        display: -webkit-box; -webkit-line-clamp: 2;
        -webkit-box-orient: vertical; overflow: hidden;
    }
    .np-card-meta {
        display: flex; align-items: center; justify-content: space-between;
        font-size: 0.78rem; color: #475569; margin-bottom: 12px;
    }
    .np-btn {
        padding: 7px 14px; border-radius: 8px;
        font-size: 0.8rem; font-weight: 600;
        border: 1px solid rgba(255,255,255,0.1);
        color: #94a3b8; cursor: pointer;
        text-decoration: none; display: inline-block;
        background: rgba(255,255,255,0.04);
        transition: all 0.15s;
    }
    .np-btn:hover { background: rgba(255,255,255,0.09); color: #e2e8f0; }
    .np-btn-primary {
        background: rgba(56,189,248,0.12);
        border-color: rgba(56,189,248,0.3); color: #38bdf8;
    }
    .np-btn-primary:hover { background: rgba(56,189,248,0.22); }
    .np-summary {
        margin-top: 10px; padding: 12px 15px;
        background: rgba(129,140,248,0.08);
        border-left: 3px solid #818cf8; border-radius: 8px;
        color: #c7d2fe; font-size: 0.85rem; line-height: 1.65;
    }
    .np-summary strong { color: #818cf8; }

    /* ── auth card ───────────────────────────────── */
    .np-auth-card {
        width: 100%; max-width: 440px;
        background: #0f172a;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 24px; padding: 44px 40px;
        margin: 60px auto;
    }
    .np-auth-logo {
        text-align: center; margin-bottom: 8px;
        font-family: 'Syne', sans-serif;
        font-size: 2rem; font-weight: 800;
        background: linear-gradient(135deg, #38bdf8, #818cf8);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .np-auth-tagline {
        text-align: center; color: #475569;
        font-size: 0.88rem; margin-bottom: 36px;
    }
    .np-auth-title {
        font-family: 'Syne', sans-serif;
        font-size: 1.5rem; font-weight: 700;
        color: #e2e8f0; margin-bottom: 24px; text-align: center;
    }
    .np-auth-divider {
        display: flex; align-items: center; gap: 14px;
        margin: 20px 0; color: #334155; font-size: 0.82rem;
    }
    .np-auth-divider::before, .np-auth-divider::after {
        content: ''; flex: 1; height: 1px;
        background: rgba(255,255,255,0.06);
    }
    .np-auth-footer {
        text-align: center; margin-top: 20px;
        color: #475569; font-size: 0.88rem;
    }
/* streamlit input overrides */
    .stTextInput > div > div > input {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 10px !important;
        color: #e2e8f0 !important;
        font-family: 'DM Sans', sans-serif !important;
        padding: 12px 14px !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #38bdf8 !important;
        box-shadow: 0 0 0 3px rgba(56,189,248,0.12) !important;
    }
    div.stButton > button {
        background: linear-gradient(135deg, #0ea5e9, #6366f1) !important;
        color: #fff !important; border: none !important;
        border-radius: 10px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important; font-size: 0.9rem !important;
        padding: 10px 20px !important;
        transition: opacity 0.18s, transform 0.18s !important;
        box-shadow: 0 4px 14px rgba(14,165,233,0.25) !important;
    }
    div.stButton > button:hover {
        opacity: 0.9 !important; transform: translateY(-1px) !important;
    }

    /* stats */
    .np-stat {
        background: #0f172a;
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 14px; padding: 18px 20px;
        position: relative; overflow: hidden; margin-bottom: 8px;
    }
    .np-stat::before {
        content: ''; position: absolute;
        top: 0; left: 0; right: 0; height: 2px;
        background: linear-gradient(90deg, #38bdf8, #818cf8);
    }
    .np-stat-val {
        font-family: 'Syne', sans-serif;
        font-size: 1.8rem; font-weight: 800;
        color: #38bdf8; line-height: 1; margin-bottom: 4px;
    }
    .np-stat-lbl { font-size: 0.8rem; color: #475569; font-weight: 500; }

    /* empty state */
    .np-empty { text-align: center; padding: 80px 20px; color: #334155; }
    .np-empty-icon { font-size: 3rem; margin-bottom: 16px; opacity: 0.5; }
    .np-empty-title {
        font-family: 'Syne', sans-serif;
        font-size: 1.4rem; font-weight: 700; color: #475569; margin-bottom: 8px;
    }
    .np-empty-sub { font-size: 0.9rem; color: #334155; }

    /* features */
    .np-feature {
        background: #0f172a;
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 16px; padding: 24px 20px;
        transition: border-color 0.2s, transform 0.2s; height: 100%;
    }
    .np-feature:hover { border-color: rgba(56,189,248,0.2); transform: translateY(-2px); }
    .np-feature-icon { font-size: 1.8rem; margin-bottom: 12px; }
    .np-feature-title {
        font-family: 'Syne', sans-serif;
        font-size: 0.95rem; font-weight: 700;
        color: #e2e8f0; margin-bottom: 6px;
    }
    .np-feature-desc { font-size: 0.83rem; color: #475569; line-height: 1.55; }

    /* footer */
    .np-footer {
        text-align: center; padding: 32px;
        border-top: 1px solid rgba(255,255,255,0.05);
        color: #334155; font-size: 0.82rem;
    }
    </style>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# NAVBAR
# ─────────────────────────────────────────────────────────────
def render_navbar():
    email   = st.session_state.email or ""
    initial = email[0].upper() if email else "U"
    st.markdown(f"""
    <div class="np-nav">
      <div class="np-nav-logo">⚡ NewsPulse</div>
      <div class="np-nav-user">
        <div class="np-nav-avatar">{initial}</div>
        <span style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{email}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    nc1, nc2, nc3, nc4, _ = st.columns([1, 1, 1, 1, 6])
    with nc1:
        if st.button("🏠 Home", key="nav_home"):
            st.session_state.page = "home"
            st.rerun()
    with nc2:
        if st.button("🔥 Trending", key="nav_trending"):
            st.session_state.page = "home"
            with st.spinner("Loading trending…"):
                st.session_state.articles      = fetch_news("trending", st.session_state.time_filter, 10)
                st.session_state.current_query = "Trending"
            st.rerun()
    with nc3:
        if st.button("💾 Saved", key="nav_saved"):
            st.session_state.page = "saved"
            st.rerun()
    with nc4:
        if st.button("🚪 Logout", key="nav_logout"):
            for k in ("authenticated","uid","id_token","email","display_name","current_query"):
                st.session_state[k] = False if k == "authenticated" else None
            st.session_state.articles    = []
            st.session_state.auth_view   = "login"
            st.rerun()

# ─────────────────────────────────────────────────────────────
# AUTH PAGE
# ─────────────────────────────────────────────────────────────
def auth_page():
    view = st.session_state.auth_view
    col  = st.columns([1, 1.2, 1])[1]

    with col:
         
        st.markdown('<div class="np-auth-logo">⚡ NewsPulse</div>', unsafe_allow_html=True)
        st.markdown('<div class="np-auth-tagline">The pulse of the world, in real time.</div>', unsafe_allow_html=True)

        # Show Google error if any
        if st.session_state.google_error:
            st.error(f"Google Sign-In failed: {st.session_state.google_error}")
            st.session_state.google_error = None

        # ── LOGIN ─────────────────────────────────────────────
        if view == "login":
            st.markdown('<div class="np-auth-title">Welcome back</div>', unsafe_allow_html=True)

            email_in    = st.text_input("Email address", placeholder="you@example.com", key="li_email")
            password_in = st.text_input("Password", placeholder="••••••••", type="password", key="li_pass")

            

            if st.button("Sign In →", key="do_login", use_container_width=True):
                if not email_in.strip():
                    st.error("Please enter your email address.")
                elif not is_valid_email(email_in):
                    st.error("Please enter a valid email address (e.g. name@example.com).")
                elif not password_in:
                    st.error("Please enter your password.")
                else:
                    with st.spinner("Signing in…"):
                        ok, data = sign_in_email(email_in.strip(), password_in)
                    if ok:
                        st.session_state.authenticated = True
                        st.session_state.uid           = data["localId"]
                        st.session_state.id_token      = data["idToken"]
                        st.session_state.email         = data["email"]
                        st.session_state.display_name  = data.get("displayName", data["email"].split("@")[0])
                        st.rerun()
                    else:
                        st.error(data)
                    
            fc1, fc2, fc3 = st.columns([1, 1, 1])
            with fc2:
                if st.button("Forgot password?", key="goto_forgot"):
                    st.session_state.auth_view = "forgot"
                    st.rerun()
            with fc3:
                if st.button("Create Account", key="goto_signup"):
                    st.session_state.auth_view = "signup"
                    st.rerun()

        # ── SIGN UP ────────────────────────────────────────────
        elif view == "signup":
            st.markdown('<div class="np-auth-title">Create account</div>', unsafe_allow_html=True)

            email_in = st.text_input("Email address", placeholder="you@example.com", key="su_email")
            pass1    = st.text_input("Password", placeholder="Min. 6 characters", type="password", key="su_pass1")
            pass2    = st.text_input("Confirm password", placeholder="Repeat password", type="password", key="su_pass2")

            if st.button("Create Account →", key="do_signup", use_container_width=True):
                if not email_in.strip():
                    st.error("Please enter your email address.")
                elif not is_valid_email(email_in):
                    st.error("Please enter a valid email address (e.g. name@example.com).")
                elif len(pass1) < 6:
                    st.error("Password must be at least 6 characters.")
                elif pass1 != pass2:
                    st.error("Passwords do not match.")
                else:
                    with st.spinner("Creating account…"):
                        ok, data = sign_up_email(email_in.strip(), pass1)
                    if ok:
                        st.session_state.authenticated = True
                        st.session_state.uid           = data["localId"]
                        st.session_state.id_token      = data["idToken"]
                        st.session_state.email         = data["email"]
                        st.session_state.display_name  = data["email"].split("@")[0]
                        st.rerun()
                    else:
                        st.error(data)

            st.markdown('<div class="np-auth-footer">', unsafe_allow_html=True)
            if st.button("← Already have an account? Sign in", key="goto_login_s", use_container_width=True):
                st.session_state.auth_view = "login"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # ── FORGOT PASSWORD ────────────────────────────────────
        elif view == "forgot":
            st.markdown('<div class="np-auth-title">Reset password</div>', unsafe_allow_html=True)
            st.markdown('<p style="color:#475569;font-size:0.88rem;margin-bottom:20px;text-align:center;">Enter your email and we\'ll send a reset link.</p>', unsafe_allow_html=True)

            email_in = st.text_input("Email address", placeholder="you@example.com", key="fp_email")

            if st.button("Send Reset Email →", key="do_reset", use_container_width=True):
                if not email_in.strip():
                    st.error("Please enter your email address.")
                elif not is_valid_email(email_in):
                    st.error("Please enter a valid email address.")
                else:
                    with st.spinner("Sending…"):
                        ok, msg = send_password_reset(email_in.strip())
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

            fc1, fc2 = st.columns([3, 1])
            with fc1:
                if st.button("← Back to Sign In", key="goto_login_f"):
                    st.session_state.auth_view = "login"
                    st.rerun()
            with fc2:
                if st.button("Create Account", key="goto_signup_f"):
                    st.session_state.auth_view = "signup"
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# ARTICLE CARD
# ─────────────────────────────────────────────────────────────
def render_article_card(article: dict, idx: int, is_saved: bool = False):
    title    = article.get("title", "Untitled")
    url      = article.get("url", article.get("link", "#"))
    desc     = article.get("description", article.get("desc", ""))
    image    = article.get("image", article.get("image_url", ""))
    source   = article.get("source", {})
    src_name = source.get("name", article.get("source","Unknown")) if isinstance(source, dict) else str(source)
    pub_date = format_date(article.get("publishedAt", article.get("published_at", "")))
    category = article.get("category", st.session_state.current_query or "General")

    sent_label, _ = analyze_sentiment(desc or title)
    desc_short     = (desc[:110] + "…") if desc and len(desc) > 110 else (desc or "")

    img_html = (
        f'<img class="np-card-img" src="{image}" alt="" '
        f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
        f'<div class="np-card-img-placeholder" style="display:none">📰</div>'
        if image else
        '<div class="np-card-img-placeholder">📰</div>'
    )

    st.markdown(f"""
    <div class="np-card">
      {img_html}
      <div class="np-card-body">
        <div class="np-card-source">📡 {src_name}</div>
        <div class="np-card-title">{title}</div>
        {"" if not desc_short else f'<div class="np-card-desc">{desc_short}</div>'}
        <div class="np-card-meta">
          <span>📅 {pub_date}</span>
          {sentiment_badge(sent_label)}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    bc1, bc2, bc3 = st.columns(3)
    with bc1:
        st.markdown(
            f'<a class="np-btn np-btn-primary" href="{url}" target="_blank">🔗 Read</a>',
            unsafe_allow_html=True
        )
    with bc2:
        if is_saved:
            if st.button("🗑️ Delete", key=f"del_{idx}", use_container_width=True):
                if delete_article(st.session_state.uid, st.session_state.id_token, url):
                    st.success("Removed!")
                    st.rerun()
        else:
            if st.button("💾 Save", key=f"save_{idx}", use_container_width=True):
                ok, msg = save_article(
                    st.session_state.uid, st.session_state.id_token,
                    title, url, pub_date, image, src_name, category
                )
                st.success(f"✅ {msg}") if ok else st.warning(f"⚠️ {msg}")
    with bc3:
        if st.button("✨ Summarize", key=f"sum_{idx}", use_container_width=True):
            full_text = f"{title}. {desc or ''} {article.get('content','')}"
            with st.spinner("Summarizing…"):
                result = summarize_text(full_text.strip())
            st.markdown(
                f'<div class="np-summary"><strong>🤖 AI Summary</strong><br>{result}</div>',
                unsafe_allow_html=True
            )
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# HOME PAGE
# ─────────────────────────────────────────────────────────────
def home_page():
    st.markdown("""
    <div class="np-hero">
      <div class="np-hero-tag">🌐 Live News Feed</div>
      <div class="np-hero-title">Stay ahead of <span>every story</span></div>
      <div class="np-hero-sub">Real-time news · AI summaries · Sentiment analysis</div>
    </div>
    """, unsafe_allow_html=True)

    sc1, sc2, sc3 = st.columns([1, 2, 1])
    with sc2:
        query = st.text_input("", placeholder="🔍  Search any topic…",
                              key="search_input", label_visibility="collapsed")
        tf_options = ["Anytime", "Past 24h", "Past week"]
        tf = st.radio("", tf_options,
                      index=tf_options.index(st.session_state.time_filter),
                      horizontal=True, key="time_radio", label_visibility="collapsed")
        st.session_state.time_filter = tf

        sa, sb = st.columns([3, 1])
        with sa:
            max_art = st.slider("Articles", 5, 20, 10, key="max_art_slider", label_visibility="collapsed")
        with sb:
            if st.button("Search →", key="do_search", use_container_width=True):
                if not query.strip():
                    st.warning("Please enter a search term.")
                else:
                    with st.spinner(f"Fetching '{query}'…"):
                        st.session_state.articles      = fetch_news(query.strip(), tf, max_art)
                        st.session_state.current_query = query.strip()
                    st.rerun()

    st.markdown('<div class="np-trending"><span class="np-trending-label">🔥 Trending</span>', unsafe_allow_html=True)
    topics = [("🤖","AI"),("₿","Bitcoin"),("🚗","Tesla"),("🏏","Cricket"),
              ("🛸","SpaceX"),("💊","Health"),("🌍","Climate"),("🚀","Startups")]
    tcols = st.columns(len(topics))
    for i, (icon, name) in enumerate(topics):
        with tcols[i]:
            if st.button(f"{icon} {name}", key=f"tr_{i}", use_container_width=True):
                with st.spinner(f"Loading {name}…"):
                    st.session_state.articles      = fetch_news(name, st.session_state.time_filter, 10)
                    st.session_state.current_query = name
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    articles = st.session_state.articles
    if articles:
        q = st.session_state.current_query
        st.markdown(f'<div class="np-section-head">Results for <span>"{q}"</span> — {len(articles)} articles</div>', unsafe_allow_html=True)

        sources_set = set()
        sent_counts = {}
        for a in articles:
            s = a.get("source", {})
            n = s.get("name","?") if isinstance(s, dict) else str(s)
            sources_set.add(n)
            lb, _ = analyze_sentiment(a.get("description","") or a.get("title",""))
            sent_counts[lb] = sent_counts.get(lb, 0) + 1

        s1, s2, s3 = st.columns(3)
        with s1:
            st.markdown(f'<div class="np-stat"><div class="np-stat-val">{len(articles)}</div><div class="np-stat-lbl">Articles</div></div>', unsafe_allow_html=True)
        with s2:
            st.markdown(f'<div class="np-stat"><div class="np-stat-val">{len(sources_set)}</div><div class="np-stat-lbl">Sources</div></div>', unsafe_allow_html=True)
        with s3:
            top_sent = max(sent_counts, key=sent_counts.get) if sent_counts else "neutral"
            st.markdown(f'<div class="np-stat"><div class="np-stat-val" style="font-size:1.2rem">{top_sent.title()}</div><div class="np-stat-lbl">Dominant Tone</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        col_l, col_r = st.columns(2)
        for i, art in enumerate(articles):
            with col_l if i % 2 == 0 else col_r:
                render_article_card(art, i)

        draw_sentiment_chart(sent_counts, "Sentiment Analysis")

    else:
        hour  = datetime.now().hour
        greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
        name  = st.session_state.display_name or (st.session_state.email or "there").split("@")[0]
        st.markdown(f'<div style="padding:0 40px 12px;color:#475569;font-size:1rem;">{greet}, <strong style="color:#94a3b8">{name}</strong> 👋</div>', unsafe_allow_html=True)
        st.markdown('<div class="np-section-head"><span>What you can do</span></div>', unsafe_allow_html=True)

        features = [
            ("🔍","Search News","Find articles on any topic instantly."),
            ("🤖","AI Summaries","Click ✨ Summarize for instant NLP summaries."),
            ("📊","Sentiment Meter","Every article is analysed for emotional tone."),
            ("💾","Save Articles","Bookmark to Firestore — accessible anywhere."),
            ("🔥","Trending","One click to load what the world is reading."),
        ]
        fcols = st.columns(len(features))
        for i, (icon, t, d) in enumerate(features):
            with fcols[i]:
                st.markdown(f"""
                <div class="np-feature">
                  <div class="np-feature-icon">{icon}</div>
                  <div class="np-feature-title">{t}</div>
                  <div class="np-feature-desc">{d}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown('<div class="np-section-head" style="padding-top:24px"><span>Quick Start</span></div>', unsafe_allow_html=True)
        cats  = [("💻","Technology"),("💼","Business"),("⚽","Sports"),("🔬","Science"),("🎬","Entertainment")]
        ccols = st.columns(len(cats))
        for i, (icon, name_) in enumerate(cats):
            with ccols[i]:
                if st.button(f"{icon} {name_}", key=f"qs_{i}", use_container_width=True):
                    with st.spinner(f"Loading {name_}…"):
                        st.session_state.articles      = fetch_news(name_, "Anytime", 10)
                        st.session_state.current_query = name_
                    st.rerun()

# ─────────────────────────────────────────────────────────────
# SAVED PAGE
# ─────────────────────────────────────────────────────────────
def saved_page():
    st.markdown('<div class="np-section-head" style="padding-top:32px"><span>Your Saved Articles</span></div>', unsafe_allow_html=True)

    with st.spinner("Loading your saved articles…"):
        saved = fetch_saved_articles(st.session_state.uid, st.session_state.id_token)

    if not saved:
        st.markdown("""
        <div class="np-empty">
          <div class="np-empty-icon">📚</div>
          <div class="np-empty-title">Nothing saved yet</div>
          <div class="np-empty-sub">Search for news and click 💾 Save on any article.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    sources_set = set(a.get("source","?") for a in saved)
    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown(f'<div class="np-stat"><div class="np-stat-val">{len(saved)}</div><div class="np-stat-lbl">Saved</div></div>', unsafe_allow_html=True)
    with s2:
        st.markdown(f'<div class="np-stat"><div class="np-stat-val">{len(sources_set)}</div><div class="np-stat-lbl">Sources</div></div>', unsafe_allow_html=True)
    with s3:
        latest = saved[0].get("saved_at","")[:10] if saved else "—"
        st.markdown(f'<div class="np-stat"><div class="np-stat-val" style="font-size:1.1rem">{latest}</div><div class="np-stat-lbl">Latest Save</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    sent_counts = {}
    col_l, col_r = st.columns(2)
    for i, art in enumerate(saved):
        mapped = {
            "title":       art.get("title",""),
            "url":         art.get("url",""),
            "link":        art.get("url",""),
            "description": art.get("desc",""),
            "image":       art.get("image_url",""),
            "image_url":   art.get("image_url",""),
            "source":      art.get("source","Unknown"),
            "publishedAt": art.get("published_at",""),
            "category":    art.get("category","General"),
        }
        lb, _ = analyze_sentiment(mapped.get("title",""))
        sent_counts[lb] = sent_counts.get(lb, 0) + 1
        with col_l if i % 2 == 0 else col_r:
            render_article_card(mapped, i, is_saved=True)

    draw_sentiment_chart(sent_counts, "Saved Articles Sentiment")

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    inject_css()

    if not st.session_state.authenticated:
        auth_page()
        return

    render_navbar()

    if st.session_state.page == "saved":
        saved_page()
    else:
        home_page()

    st.markdown(
        '<div class="np-footer">⚡ NewsPulse — Powered by GNews &amp; sumy NLP · Built with Streamlit</div>',
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
