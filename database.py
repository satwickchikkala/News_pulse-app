import requests
from datetime import datetime
from firebase_config import FIREBASE_API_KEY, FIRESTORE_BASE

def _fs_val(v):
    if isinstance(v, str):  return {"stringValue": v}
    if isinstance(v, bool): return {"booleanValue": v}
    if isinstance(v, int):  return {"integerValue": str(v)}
    if isinstance(v, float):return {"doubleValue": v}
    return {"stringValue": str(v)}

def _unwrap(fields: dict) -> dict:
    result = {}
    for k, v in fields.items():
        for _, fval in v.items():
            result[k] = fval
            break
    return result

def _auth_header(id_token: str):
    return {"Authorization": f"Bearer {id_token}"}

def save_article(uid, id_token, title, url, published_at, image_url, source="Unknown", category="General"):
    import base64
    doc_id   = base64.urlsafe_b64encode(url.encode()).decode()[:100]
    endpoint = f"{FIRESTORE_BASE}/users/{uid}/saved_articles/{doc_id}"
    params   = {"key": FIREBASE_API_KEY}
    check    = requests.get(endpoint, params=params, headers=_auth_header(id_token), timeout=10)
    if check.status_code == 200:
        return False, "Article already saved!"
    body = {"fields": {
        "title":        _fs_val(title or "No Title"),
        "url":          _fs_val(url or ""),
        "published_at": _fs_val(published_at or "Unknown"),
        "image_url":    _fs_val(image_url or ""),
        "source":       _fs_val(source),
        "category":     _fs_val(category),
        "saved_at":     _fs_val(datetime.now().isoformat()),
    }}
    r = requests.patch(endpoint, json=body, params=params, headers=_auth_header(id_token), timeout=10)
    if r.status_code in (200, 201):
        return True, "Article saved!"
    return False, f"Failed to save: {r.text[:120]}"

def fetch_saved_articles(uid, id_token):
    endpoint = f"{FIRESTORE_BASE}/users/{uid}/saved_articles"
    params   = {"key": FIREBASE_API_KEY, "pageSize": 100}
    r = requests.get(endpoint, params=params, headers=_auth_header(id_token), timeout=10)
    if r.status_code != 200:
        return []
    docs = r.json().get("documents", [])
    articles = [_unwrap(doc.get("fields", {})) for doc in docs]
    articles.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
    return articles

def delete_article(uid, id_token, url):
    import base64
    doc_id   = base64.urlsafe_b64encode(url.encode()).decode()[:100]
    endpoint = f"{FIRESTORE_BASE}/users/{uid}/saved_articles/{doc_id}"
    params   = {"key": FIREBASE_API_KEY}
    r = requests.delete(endpoint, params=params, headers=_auth_header(id_token), timeout=10)
    return r.status_code == 200

def count_saved_articles(uid, id_token):
    return len(fetch_saved_articles(uid, id_token))
