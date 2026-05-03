import requests

# ─────────────────────────────────────────────
# Firebase credentials
# ─────────────────────────────────────────────
FIREBASE_API_KEY    = "YOUR_FIREBASE_API_KEY"
FIREBASE_PROJECT_ID = "YOUR_FIREBASE_PROJECT_ID"

AUTH_BASE      = "https://identitytoolkit.googleapis.com/v1/accounts"
FIRESTORE_BASE = (
    f"https://firestore.googleapis.com/v1/projects/"
    f"{FIREBASE_PROJECT_ID}/databases/(default)/documents"
)

# ─────────────────────────────────────────────
# Email / Password
# ─────────────────────────────────────────────

def sign_up_email(email: str, password: str):
    url     = f"{AUTH_BASE}:signUp?key={FIREBASE_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    r       = requests.post(url, json=payload, timeout=10)
    data    = r.json()
    if "idToken" in data:
        return True, data
    return False, _friendly(data.get("error", {}).get("message", "Sign-up failed."))


def sign_in_email(email: str, password: str):
    url     = f"{AUTH_BASE}:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    r       = requests.post(url, json=payload, timeout=10)
    data    = r.json()
    if "idToken" in data:
        return True, data
    return False, _friendly(data.get("error", {}).get("message", "Sign-in failed."))


def send_password_reset(email: str):
    url     = f"{AUTH_BASE}:sendOobCode?key={FIREBASE_API_KEY}"
    payload = {"requestType": "PASSWORD_RESET", "email": email}
    r       = requests.post(url, json=payload, timeout=10)
    data    = r.json()
    if "email" in data:
        return True, "Password reset email sent! Check your inbox."
    return False, _friendly(data.get("error", {}).get("message", "Failed to send reset email."))


# ─────────────────────────────────────────────
# Google Sign-In (token comes from google_auth.html)
# google_auth.html does signInWithPopup in the browser,
# gets a Firebase idToken, and redirects to localhost:8501?g_id_token=...
# We verify that token here.
# ─────────────────────────────────────────────

def verify_google_firebase_token(firebase_id_token: str, uid: str, email: str, display_name: str):
    """
    Verify the Firebase ID token that came from google_auth.html.
    Uses the token lookup endpoint — does NOT do any OAuth redirect.
    """
    url     = f"{AUTH_BASE}:lookup?key={FIREBASE_API_KEY}"
    payload = {"idToken": firebase_id_token}
    try:
        r    = requests.post(url, json=payload, timeout=10)
        data = r.json()
        users = data.get("users", [])
        if users:
            u = users[0]
            return True, {
                "localId":     u.get("localId",     uid),
                "email":       u.get("email",       email),
                "displayName": u.get("displayName", display_name),
                "idToken":     firebase_id_token,
            }
        err = data.get("error", {}).get("message", "Token verification failed.")
        return False, _friendly(err)
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────
# Friendly error map
# ─────────────────────────────────────────────
_ERROR_MAP = {
    "EMAIL_EXISTS":                "This email is already registered. Please log in.",
    "INVALID_EMAIL":               "Please enter a valid email address.",
    "WEAK_PASSWORD":               "Password must be at least 6 characters.",
    "EMAIL_NOT_FOUND":             "No account found with this email.",
    "INVALID_PASSWORD":            "Incorrect password. Please try again.",
    "INVALID_LOGIN_CREDENTIALS":   "Incorrect email or password.",
    "USER_DISABLED":               "This account has been disabled.",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many failed attempts. Try again later.",
    "MISSING_PASSWORD":            "Please enter your password.",
    "OPERATION_NOT_ALLOWED":       "This sign-in method is not enabled.",
}

def _friendly(msg: str) -> str:
    for key, friendly in _ERROR_MAP.items():
        if key in msg:
            return friendly
    return msg.replace("_", " ").title()
