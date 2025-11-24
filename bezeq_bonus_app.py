

# === Goals progress helpers (sidebar mini-dashboard) ===
def _pct_color(p):
    # color by progress percent: red <50%, yellow 50–99%, green >=100%
    if p >= 100: return "#10b981"  # green
    if p >= 50:  return "#f59e0b"  # amber
    return "#ef4444"               # red

def _goal_bar_html(label: str, current: int, goal: int):
    # calculate percent and return HTML for a compact progress bar
    if goal and goal > 0:
        pct_exact = (current / goal) * 100.0
        pct = max(0, min(100, int(pct_exact)))
        color = _pct_color(int(pct_exact))
        note = f"{current:,}₪ / {goal:,}₪ · {pct}%"
    else:
        pct, color = 0, "#6b7280"
        note = f"{current:,}₪ · אין יעד"
    return f"""
    <div class="goalbar">
      <div class="goalbar-row">
        <div class="goalbar-label">{label}</div>
        <div class="goalbar-note">{note}</div>
      </div>
      <div class="goalbar-track">
        <div class="goalbar-fill" style="width:{pct}%; background:{color};"></div>
      </div>
    </div>
    """

# Inject CSS for goal bars
import streamlit as _st_for_css_only  # safe alias in case top-level 'st' isn't yet imported at this point
try:
    _st_for_css_only.markdown("""
<style>
.goalbar { margin: .35rem 0 .6rem 0; direction: rtl; }
.goalbar-row { display:flex; justify-content:space-between; align-items:center; gap:.5rem; margin-bottom:.25rem; }
.goalbar-label { font-weight:700; }
.goalbar-note { font-size:.85rem; opacity:.85; }
.goalbar-track { width:100%; height:12px; border-radius:999px; background:rgba(255,255,255,0.08); position:relative; overflow:hidden; border:1px solid rgba(255,255,255,0.12); }
.app-skin .goalbar-track { background:#111; border-color:#222; }
.light.app-skin .goalbar-track { background:#e5e7eb; border-color:#d1d5db; }
.goalbar-fill { height:100%; border-radius:inherit; transition:width .3s ease; }
</style>
""", unsafe_allow_html=True)
except Exception:
    pass
# === /Goals progress helpers ===
import urllib.parse


# bezeq_bonus_app_version 8 (Firebase optional)
# -*- coding: utf-8 -*-
import json, csv, io, sys, subprocess, random, uuid, os, tempfile
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

def ensure(pkg):
    try:
        __import__(pkg)
        return True
    except ImportError:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
            __import__(pkg)
            return True
        except Exception:
            return False

HAS_PANDAS = ensure("pandas")
HAS_BCRYPT = ensure("bcrypt")

import streamlit as st
if not HAS_PANDAS:
    st.error("נדרשת חבילת pandas. התקן עם: pip install pandas")
    st.stop()
import pandas as pd
import altair as alt

if HAS_BCRYPT:
    import bcrypt
else:
    bcrypt = None

FIREBASE_ENABLED = False
DB = None
FIREBASE_DIAG = {"ok": False, "error": "not-initialized", "source": None, "project_id": None}

def init_firebase():
    global FIREBASE_ENABLED, DB, FIREBASE_DIAG
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        if not firebase_admin._apps:
            cred_dict = None
            try:
                if "FIREBASE" in st.secrets:
                    cred_dict = dict(st.secrets["FIREBASE"])
            except Exception:
                pass
            if cred_dict is None:
                fj = os.environ.get("FIREBASE_JSON")
                if fj:
                    try:
                        cred_dict = json.loads(fj)
                    except Exception:
                        pass
            if cred_dict is not None:
                cred = credentials.Certificate(cred_dict)
                FIREBASE_DIAG["source"] = "st.secrets[FIREBASE]"
                firebase_admin.initialize_app(cred)
            else:
                gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
                if gac and Path(gac).exists():
                    cred = credentials.Certificate(gac)
                    FIREBASE_DIAG["source"] = "GOOGLE_APPLICATION_CREDENTIALS"
                    firebase_admin.initialize_app(cred)
                else:
                    local = Path("firebase_service_account.json")
                    if local.exists():
                        cred = credentials.Certificate(str(local))
                        FIREBASE_DIAG["source"] = "firebase_service_account.json file"
                        firebase_admin.initialize_app(cred)
        from firebase_admin import firestore
        DB = firestore.client()
        FIREBASE_ENABLED = True
        try:
            FIREBASE_DIAG = {"ok": True, "error": None, "source": FIREBASE_DIAG.get("source"), "project_id": st.secrets.get("FIREBASE",{}).get("project_id") if "FIREBASE" in st.secrets else None}
        except Exception:
            FIREBASE_DIAG = {"ok": True, "error": None, "source": FIREBASE_DIAG.get("source"), "project_id": None}
    except Exception as e:
        FIREBASE_ENABLED = False
        DB = None
        FIREBASE_DIAG = {"ok": False, "error": str(e), "source": FIREBASE_DIAG.get("source"), "project_id": None}

init_firebase()

APP_TZ = ZoneInfo("Asia/Jerusalem")
DATA_DIR = Path("data")
USERS_PATH = DATA_DIR / "users.json"
RECORDS_PATH = DATA_DIR / "records.json"
BONUSES_PATH = DATA_DIR / "bonuses.json"
MSGS_PATH = DATA_DIR / "messages.json"

PRODUCTS = [
    {"code": "fiber_new", "name": "אינטרנט סיבים חדש", "bonus": 23},
    {"code": "copper_new", "name": "אינטרנט נחושת חדש", "bonus": 10},
    {"code": "mesh_copper", "name": "מגדיל טווח MESH בנחושת", "bonus": 5},
    {"code": "bspot_copper", "name": "מגדיל טווח BSPOT בנחושת", "bonus": 10},
    {"code": "mesh_fiber", "name": "מגדיל טווח MESH FIBER בסיבים", "bonus": 10},
    {"code": "upgrade_fiber_to_fiber", "name": "שדרוג מסיב לסיב", "bonus": 8},
    {"code": "cyber_plus", "name": "סייבר+", "bonus": 10},
    {"code": "biznet_copper", "name": "ביזנט בנחושת", "bonus": 43},
    {"code": "bizfiber_fiber", "name": "ביזפייבר בסיבים האופטיים", "bonus": 73},
    {"code": "upgrade_biznet_to_bizfiber", "name": "שדרוג מביזנט (נחושת) לביזפייבר (סיבים)", "bonus": 20},
]
PRODUCT_INDEX = {p["code"]: p for p in PRODUCTS}

def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)
    if not USERS_PATH.exists():
        USERS_PATH.write_text(json.dumps({"users": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
    if not RECORDS_PATH.exists():
        RECORDS_PATH.write_text(json.dumps({"records": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    if not BONUSES_PATH.exists():
        base_prices = {p["code"]: int(p["bonus"]) for p in PRODUCTS}
        BONUSES_PATH.write_text(json.dumps({
            "products": PRODUCTS,
            "schedules": [
                {"effective_date": "1970-01-01", "prices": base_prices}
            ]
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    if not MSGS_PATH.exists():
        MSGS_PATH.write_text(json.dumps({"messages": []}, ensure_ascii=False, indent=2), encoding="utf-8")

def _fs_users_load():
    assert FIREBASE_ENABLED and DB
    docs = DB.collection("users").stream()
    users = {}
    for d in docs:
        u = d.to_dict() or {}
        if "email" not in u:
            u["email"] = d.id
        users[u["email"].lower()] = u
    return {"users": users}

def _fs_users_save(data: dict):
    assert FIREBASE_ENABLED and DB
    users = data.get("users", {})
    batch = DB.batch()
    col = DB.collection("users")
    for email, u in users.items():
        doc = col.document(email)
        u2 = dict(u); u2["email"] = email
        batch.set(doc, u2, merge=True)
    batch.commit()

def _fs_records_load():
    assert FIREBASE_ENABLED and DB
    docs = DB.collection("records").stream()
    rows = []
    for d in docs:
        r = d.to_dict() or {}
        if {"email","date","product","qty","ts"} <= set(r.keys()):
            rows.append(r)
    return {"records": rows}

def _fs_records_replace_all(data: dict):
    assert FIREBASE_ENABLED and DB
    recs = data.get("records", [])
    batch = DB.batch()
    col = DB.collection("records")
    for r in recs:
        rid = r.get("id") or str(uuid.uuid4())
        batch.set(col.document(rid), r, merge=True)
    batch.commit()

def _fs_records_delete_for_user_date(email: str, date_s: str):
    assert FIREBASE_ENABLED and DB
    col = DB.collection("records")
    q = col.where("email", "==", email).where("date", "==", date_s).stream()
    batch = DB.batch()
    any_doc = False
    for d in q:
        batch.delete(d.reference)
        any_doc = True
    if any_doc:
        batch.commit()

def _fs_bonus_load():
    assert FIREBASE_ENABLED and DB
    doc = DB.collection("config").document("bonuses").get()
    if doc.exists:
        data = doc.to_dict() or {}
        if "schedules" in data:
            return {"schedules": list(data["schedules"])}
    base_prices = {p["code"]: int(p["bonus"]) for p in PRODUCTS}
    return {"schedules": [{"effective_date": "1970-01-01", "prices": base_prices}]}

def _fs_bonus_save(data: dict):
    assert FIREBASE_ENABLED and DB
    data2 = {"schedules": list(data.get("schedules", []))}
    DB.collection("config").document("bonuses").set(data2, merge=True)

def _fs_messages_load():
    assert FIREBASE_ENABLED and DB
    docs = DB.collection("messages").order_by("created_at").stream()
    msgs = []
    for d in docs:
        m = d.to_dict() or {}
        if "id" not in m:
            m["id"] = d.id
        msgs.append(m)
    return {"messages": msgs}

def _fs_messages_save(data: dict):
    assert FIREBASE_ENABLED and DB
    msgs = data.get("messages", [])
    batch = DB.batch()
    col = DB.collection("messages")
    for m in msgs:
        mid = m.get("id") or str(uuid.uuid4())
        m2 = dict(m); m2["id"] = mid
        batch.set(col.document(mid), m2, merge=True)
    batch.commit()

def load_users():
    if FIREBASE_ENABLED:
        return _fs_users_load()
    ensure_files()
    with open(USERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(data):
    if FIREBASE_ENABLED:
        _fs_users_save(data)
        return
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_records():
    if FIREBASE_ENABLED:
        return _fs_records_load()
    ensure_files()
    with open(RECORDS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_records(data):
    if FIREBASE_ENABLED:
        _fs_records_replace_all(data)
        return
    with open(RECORDS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_bonus_schedules():
    if FIREBASE_ENABLED:
        data = _fs_bonus_load()
        data["schedules"].sort(key=lambda s: s["effective_date"])
        return data
    ensure_files()
    with open(BONUSES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["schedules"].sort(key=lambda s: s["effective_date"])
    return data

def save_bonus_schedules(data):
    data["schedules"].sort(key=lambda s: s["effective_date"])
    if FIREBASE_ENABLED:
        _fs_bonus_save(data)
        return
    with open(BONUSES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
# --- Extended bonus config helpers (products + schedules) ---
def load_bonus_config():
    if FIREBASE_ENABLED:
        doc = DB.collection("config").document("bonuses").get()
        data = doc.to_dict() or {}
        if "schedules" not in data:
            base_prices = {p["code"]: int(p["bonus"]) for p in PRODUCTS}
            data["schedules"] = [{"effective_date": "1970-01-01", "prices": base_prices}]
        if "products" not in data or not data["products"]:
            data["products"] = list(PRODUCTS)
        try:
            data["schedules"].sort(key=lambda s: s["effective_date"])
        except Exception:
            pass
        return data
    ensure_files()
    try:
        with open(BONUSES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    if "schedules" not in data:
        base_prices = {p["code"]: int(p["bonus"]) for p in PRODUCTS}
        data["schedules"] = [{"effective_date": "1970-01-01", "prices": base_prices}]
    if "products" not in data or not data["products"]:
        data["products"] = list(PRODUCTS)
    try:
        data["schedules"].sort(key=lambda s: s["effective_date"])
    except Exception:
        pass
    return data

def save_bonus_config(data: dict):
    data = dict(data)
    schedules = list(data.get("schedules", []))
    try:
        schedules.sort(key=lambda s: s["effective_date"])
    except Exception:
        pass
    products = list(data.get("products", []))
    data2 = {"schedules": schedules, "products": products}
    if FIREBASE_ENABLED:
        DB.collection("config").document("bonuses").set(data2, merge=True)
        return
    with open(BONUSES_PATH, "w", encoding="utf-8") as f:
        json.dump(data2, f, ensure_ascii=False, indent=2)

def load_products():
    cfg = load_bonus_config()
    return list(cfg.get("products", [])) or list(PRODUCTS)

def save_products(products: list):
    cfg = load_bonus_config()
    cfg["products"] = list(products)
    save_bonus_config(cfg)

def refresh_products():
    global PRODUCTS, PRODUCT_INDEX
    try:
        prods = load_products()
        if prods:
            PRODUCTS = list(prods)
            PRODUCT_INDEX = {p["code"]: p for p in PRODUCTS}
    except Exception:
        PRODUCT_INDEX = {p["code"]: p for p in PRODUCTS}

# Refresh at import-time so UI and calculations use latest product set
refresh_products()


def load_messages():
    if FIREBASE_ENABLED:
        return _fs_messages_load()
    ensure_files()
    with open(MSGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_messages(data):
    if FIREBASE_ENABLED:
        _fs_messages_save(data)
        return
    with open(MSGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def create_message(text: str, target_all: bool, target_emails: list, target_teams: list, sticky: bool=True, meta: dict|None=None, title: str|None=None, sender: str|None=None):
    msg = {
        "id": str(uuid.uuid4()),
        "title": title or "הודעה",
        "text": text,
        "target_all": bool(target_all),
        "target_emails": list(sorted(set([e.lower() for e in (target_emails or [])]))),
        "target_teams": list(sorted(set(target_teams or []))),
        "created_at": datetime.now(APP_TZ).isoformat(),
        "active": True,
        "sticky": bool(sticky),
        "dismissed_for": [],
        "meta": meta or {},
        "sender": (sender or "system"),
    }
    if FIREBASE_ENABLED:
        DB.collection("messages").document(msg["id"]).set(msg, merge=True)
        return msg["id"]
    data = load_messages()
    data["messages"].append(msg)
    save_messages(data)
    return msg["id"]

def update_message(msg_id: str, **fields):
    if FIREBASE_ENABLED:
        allowed = {k:v for k,v in fields.items() if k in {"text","target_all","target_emails","target_teams","active","sticky","meta"}}
        DB.collection("messages").document(msg_id).set(allowed, merge=True)
        return True
    data = load_messages()
    for m in data["messages"]:
        if m["id"] == msg_id:
            m.update({k:v for k,v in fields.items() if k in {"text","target_all","target_emails","target_teams","active","sticky","meta"}})
            save_messages(data)
            return True
    return False

def delete_message(msg_id: str):
    if FIREBASE_ENABLED:
        DB.collection("messages").document(msg_id).delete()
        return
    data = load_messages()
    data["messages"] = [m for m in data["messages"] if m["id"] != msg_id]
    save_messages(data)

def eligible_messages_for_user(user: dict):
    md = load_messages()
    msgs = []
    email = user["email"].lower().strip()
    team = user.get("team","")
    for m in md.get("messages", []):
        if not m.get("active", True):
            continue
        if email in m.get("dismissed_for", []):
            continue
        if m.get("target_all"):
            msgs.append(m); continue
        if email in [e.lower() for e in m.get("target_emails", [])]:
            msgs.append(m); continue
        if team and team in m.get("target_teams", []):
            msgs.append(m); continue
    msgs.sort(key=lambda x: x.get("created_at",""))
    return msgs

def mark_dismissed_for_user(msg_id: str, user_email: str):
    user_email = user_email.lower().strip()
    if FIREBASE_ENABLED:
        ref = DB.collection("messages").document(msg_id)
        snap = ref.get()
        if snap.exists:
            m = snap.to_dict() or {}
            lst = set(m.get("dismissed_for", []))
            lst.add(user_email)
            ref.set({"dismissed_for": sorted(lst)}, merge=True)
        return
    data = load_messages()
    for m in data["messages"]:
        if m["id"] == msg_id:
            lst = set(m.get("dismissed_for", []))
            lst.add(user_email)
            m["dismissed_for"] = sorted(lst)
            break
    save_messages(data)

def get_bonus_for(product_code: str, on_date: str | date) -> int:
    if isinstance(on_date, date):
        d = on_date
    else:
        d = date.fromisoformat(on_date)
    schedules = load_bonus_schedules()["schedules"]
    applicable = None
    for sch in schedules:
        eff = date.fromisoformat(sch["effective_date"])
        if eff <= d:
            applicable = sch
        else:
            break
    prices = (applicable or schedules[0])["prices"]
    return int(prices.get(product_code, PRODUCT_INDEX.get(product_code, {}).get("bonus", 0)))

def hash_password(password: str) -> str:
    if not bcrypt:
        import hashlib, secrets
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()
        return f"pbkdf2${salt}${digest}"
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def check_password(password: str, hashed: str) -> bool:
    if hashed.startswith("pbkdf2$"):
        import hashlib
        _, salt, digest = hashed.split("$", 2)
        check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()
        return check == digest
    if not bcrypt:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False
def set_last_login(email: str):
    """Stamp last login for user (both Firebase and local JSON modes)."""
    ts = now_ij().isoformat()
    email_l = email.lower().strip()
    if FIREBASE_ENABLED:
        try:
            DB.collection("users").document(email_l).set({"last_login_at": ts}, merge=True)
        except Exception:
            pass
    else:
        db = load_users()
        u = db.get("users", {}).get(email_l)
        if u is not None:
            u["last_login_at"] = ts
            db["users"][email_l] = u
            save_users(db)

def start_user_session(email: str, hours: int = 8) -> tuple[str, str]:
    """Create a new session for this user, store it on the user record, and return (sid, expires_at_iso)."""
    ts_start = now_ij()
    expires = (ts_start + timedelta(hours=hours)).isoformat()
    sid = str(uuid.uuid4())
    email_l = email.lower().strip()
    if FIREBASE_ENABLED:
        try:
            DB.collection("users").document(email_l).set({
                "session_sid": sid,
                "session_expires_at": expires,
            }, merge=True)
        except Exception:
            # If session update fails, we still allow login – user will just not have server-side session metadata.
            pass
    else:
        db = load_users()
        u = db.get("users", {}).get(email_l)
        if u is not None:
            u["session_sid"] = sid
            u["session_expires_at"] = expires
            db["users"][email_l] = u
            save_users(db)
    return sid, expires


def clear_user_session(email: str):
    """Clear user's session id from the DB/JSON (used on logout)."""
    email_l = email.lower().strip()
    if FIREBASE_ENABLED:
        try:
            DB.collection("users").document(email_l).set({
                "session_sid": None,
                "session_expires_at": None,
            }, merge=True)
        except Exception:
            # Logout should not crash the app if Firestore write fails
            pass
    else:
        db = load_users()
        u = db.get("users", {}).get(email_l)
        if u is not None:
            u.pop("session_sid", None)
            u.pop("session_expires_at", None)
            db["users"][email_l] = u
            save_users(db)


def get_user_by_session(sid: str):
    """Lookup a user record by its session_sid (for auto-login from URL)."""
    sid = (sid or "").strip()
    if not sid:
        return None
    if FIREBASE_ENABLED:
        try:
            q = DB.collection("users").where("session_sid", "==", sid).limit(1)
            docs = list(q.stream())
            if not docs:
                return None
            u = docs[0].to_dict()
            # ensure email present on user dict
            if "email" not in u:
                u["email"] = docs[0].id
            return u
        except Exception:
            return None
    else:
        db = load_users()
        for email_l, u in db.get("users", {}).items():
            if u.get("session_sid") == sid:
                if "email" not in u:
                    u["email"] = email_l
                return u
        return None





def now_ij():
    return datetime.now(APP_TZ)

def week_bounds(d: date):
    weekday = (d.weekday() + 1) % 7
    start = d - timedelta(days=weekday)
    end = start + timedelta(days=6)
    return start, end

def month_bounds(d: date):
    start = d.replace(day=1)
    if start.month == 12:
        nxt = start.replace(year=start.year+1, month=1, day=1)
    else:
        nxt = start.replace(month=start.month+1, day=1)
    end = nxt - timedelta(days=1)
    return start, end

def fmt_ts(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts)
        try:
            dt = dt.astimezone(APP_TZ)
        except Exception:
            pass
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return ts

def _random_hex_color(existing: set[str]):
    while True:
        h = random.randint(0, 359)
        s = random.randint(60, 90)
        l = random.randint(45, 60)
        import colorsys
        r,g,b = colorsys.hls_to_rgb(h/360.0, l/100.0, s/100.0)
        hexc = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        if hexc not in existing:
            return hexc

def new_user_payload(name, email, password, team, invisible=False):
    udb = load_users()
    existing_colors = {u.get("color","") for u in udb.get("users",{}).values()}
    color = _random_hex_color(existing_colors)
    return {
        "name": name,
        "email": email.lower().strip(),
        "team": team.strip(),
        "invisible": bool(invisible),
        "password": hash_password(password),
        "created_at": now_ij().isoformat(),
        "goals": {"daily": 0, "weekly": 0, "monthly": 0},
        "color": color,
        "is_admin": False
    }

def register_user(name, email, password, team, invisible):
    dbu = load_users()
    email_l = email.lower().strip()
    if email_l in dbu["users"]:
        return False, "האימייל כבר רשום במערכת."
    payload = new_user_payload(name, email_l, password, team, invisible)
    if FIREBASE_ENABLED:
        DB.collection("users").document(email_l).set(payload, merge=True)
        return True, "נרשמת בהצלחה! אפשר להתחבר."
    dbu["users"][email_l] = payload
    save_users(dbu)
    return True, "נרשמת בהצלחה! אפשר להתחבר."

def authenticate(email, password):
    email_l = email.lower().strip()
    db = load_users()
    user = db["users"].get(email_l)
    if not user:
        return False, "משתמש לא נמצא."
    if not check_password(password, user["password"]):
        return False, "סיסמה שגויה."
    # On successful authentication, stamp last login and open a new server-side session
    set_last_login(email_l)
    sid, exp_at = start_user_session(email_l)
    db2 = load_users()
    user2 = db2["users"].get(email_l, user)
    # Ensure the in-memory user dict also has the session metadata
    user2["session_sid"] = sid
    user2["session_expires_at"] = exp_at
    return True, user2

def update_user(email, **fields):
    if "is_admin" in fields:
        fields.pop("is_admin")
    if FIREBASE_ENABLED:
        email_l = email.lower().strip()
        DB.collection("users").document(email_l).set(fields, merge=True)
        return True, "עודכן בהצלחה."
    db = load_users()
    user = db["users"].get(email.lower().strip())
    if not user:
        return False, "משתמש לא נמצא."
    user.update(fields)
    db["users"][email.lower().strip()] = user
    save_users(db)
    return True, "עודכן בהצלחה."

def delete_user(email):
    if FIREBASE_ENABLED:
        email_l = email.lower().strip()
        DB.collection("users").document(email_l).delete()
        q = DB.collection("records").where("email", "==", email_l).stream()
        batch = DB.batch()
        anyd = False
        for d in q:
            batch.delete(d.reference); anyd = True
        if anyd:
            batch.commit()
        return True
    dbu = load_users()
    dbr = load_records()
    if email in dbu["users"]:
        dbu["users"].pop(email, None)
        save_users(dbu)
    dbr["records"] = [r for r in dbr["records"] if r["email"] != email]
    save_records(dbr)
    return True

def add_or_set_counts(email: str, d: date, counts: dict):
    date_s = d.isoformat()
    ts = now_ij().isoformat()
    if FIREBASE_ENABLED:
        _fs_records_delete_for_user_date(email, date_s)
        batch = DB.batch()
        col = DB.collection("records")
        for code, qty in counts.items():
            qty = int(qty)
            if qty > 0:
                rid = str(uuid.uuid4())
                batch.set(col.document(rid), {"email": email, "date": date_s, "product": code, "qty": qty, "ts": ts}, merge=True)
        batch.commit()
        return
    db = load_records()
    db["records"] = [r for r in db["records"] if not (r["email"] == email and r["date"] == date_s)]
    for code, qty in counts.items():
        qty = int(qty)
        if qty > 0:
            db["records"].append({"email": email, "date": date_s, "product": code, "qty": qty, "ts": ts})
    save_records(db)

def get_counts_for_user_date(email: str, d: date):
    date_s = d.isoformat()
    if FIREBASE_ENABLED:
        q = DB.collection("records").where("email","==",email).where("date","==",date_s).stream()
        out = {p["code"]: 0 for p in PRODUCTS}
        for doc in q:
            r = doc.to_dict() or {}
            out[r.get("product","")] = out.get(r.get("product",""),0) + int(r.get("qty",0))
        return out
    db = load_records()
    out = {p["code"]: 0 for p in PRODUCTS}
    for r in db["records"]:
        if r["email"] == email and r["date"] == date_s:
            out[r["product"]] = out.get(r["product"], 0) + int(r["qty"])
    return out

def aggregate_user_counts(email: str, start_d: date, end_d: date):
    s = start_d.isoformat(); e = end_d.isoformat()
    if FIREBASE_ENABLED:
        q = DB.collection("records").where("email","==",email).where("date",">=",s).where("date","<=",e).stream()
        out = {p["code"]: 0 for p in PRODUCTS}
        for doc in q:
            r = doc.to_dict() or {}
            out[r.get("product","")] = out.get(r.get("product",""),0) + int(r.get("qty",0))
        return out
    db = load_records()
    out = {p["code"]: 0 for p in PRODUCTS}
    for r in db["records"]:
        if r["email"] == email and s <= r["date"] <= e:
            out[r["product"]] = out.get(r["product"], 0) + int(r["qty"])
    return out

def sum_bonus_for_email_range(email: str, start_d: date, end_d: date) -> int:
    s = start_d.isoformat(); e = end_d.isoformat()
    total = 0
    if FIREBASE_ENABLED:
        q = DB.collection("records").where("email","==",email).where("date",">=",s).where("date","<=",e).stream()
        for doc in q:
            r = doc.to_dict() or {}
            total += int(r.get("qty",0)) * get_bonus_for(r.get("product",""), r.get("date", s))
        return int(total)
    db = load_records()
    for r in db["records"]:
        if r["email"] == email and s <= r["date"] <= e:
            total += int(r["qty"]) * get_bonus_for(r["product"], r["date"])
    return int(total)

def all_users_list(include_invisible=True):
    db = load_users()
    users = list(db.get("users", {}).values())
    return users if include_invisible else [u for u in users if not u.get("invisible")]

def team_members(team: str, include_invisible=False):
    users = all_users_list(include_invisible=include_invisible)
    return [u for u in users if u.get("team","").strip() == team.strip()]

def team_aggregate(team: str, start_d: date, end_d: date, include_invisible=False):
    members = team_members(team, include_invisible=include_invisible)
    emails = [m["email"] for m in members]
    counts = {e: aggregate_user_counts(e, start_d, end_d) for e in emails}
    bonuses = {e: sum_bonus_for_email_range(e, start_d, end_d) for e in emails}
    return members, counts, bonuses

def group_members_by_filter(team_filter: str, include_invisible: bool):
    if team_filter == "ALL":
        return all_users_list(include_invisible=include_invisible)
    return team_members(team_filter, include_invisible=include_invisible)

def _display_label(member: dict) -> str:
    name = member.get("name","")
    team = member.get("team","")
    return f"{name} · {team}" if team else name

def build_group_timeseries(members: list, period: str, start_d: date | None = None, end_d: date | None = None) -> pd.DataFrame:
    if not members:
        return pd.DataFrame()
    email_to_label = {m["email"]: _display_label(m) for m in members}
    # Support custom explicit start/end if provided
    custom = (period == "CUSTOM") or (start_d is not None and end_d is not None)
    if custom and (start_d is None or end_d is None):
        today = now_ij().date()
        start_d = today
        end_d = today

    if FIREBASE_ENABLED:
        today = now_ij().date()
        if custom:
            s = start_d.isoformat(); e = end_d.isoformat()
        else:
            start, end = today, today
            if period == "שבוע נוכחי":
                start, end = week_bounds(today)
            elif period != "היום":
                start, end = month_bounds(today)
            s = start.isoformat(); e = end.isoformat()
        docs = DB.collection("records").where("date", ">=", s).where("date","<=", e).stream()
        recs = [d.to_dict() for d in docs if d.to_dict().get("email") in email_to_label]
    else:
        recs = load_records()["records"]
    today = now_ij().date()
    rows = []
    if custom:
        for r in recs:
            if r["email"] in email_to_label and start_d.isoformat() <= r["date"] <= end_d.isoformat():
                d = date.fromisoformat(r["date"])
                bonus = int(r.get("qty",0)) * get_bonus_for(r.get("product",""), r.get("date", start_d.isoformat()))
                rows.append({"bucket": d, "email": r["email"], "bonus": bonus})
        idx = pd.Index([start_d + timedelta(n) for n in range((end_d-start_d).days+1)], name="תאריך")
    elif period == "היום":
        target = today.isoformat()
        for r in recs:
            if r["email"] in email_to_label and r["date"] == target:
                try:
                    ts = datetime.fromisoformat(r["ts"]).astimezone(APP_TZ)
                    bucket = ts.hour
                except Exception:
                    bucket = 0
                bonus = int(r.get("qty",0)) * get_bonus_for(r.get("product",""), r.get("date", target))
                rows.append({"bucket": bucket, "email": r["email"], "bonus": bonus})
        idx = pd.Index(range(24), name="שעה")
    elif period == "שבוע נוכחי":
        start_d, end_d = week_bounds(today)
        for r in recs:
            if r["email"] in email_to_label and start_d.isoformat() <= r["date"] <= end_d.isoformat():
                d = date.fromisoformat(r["date"])
                bonus = int(r.get("qty",0)) * get_bonus_for(r.get("product",""), r.get("date", start_d.isoformat()))
                rows.append({"bucket": d, "email": r["email"], "bonus": bonus})
        idx = pd.Index([start_d + timedelta(n) for n in range((end_d-start_d).days+1)], name="תאריך")
    else:
        start_d, end_d = month_bounds(today)
        for r in recs:
            if r["email"] in email_to_label and start_d.isoformat() <= r["date"] <= end_d.isoformat():
                d = date.fromisoformat(r["date"])
                bonus = int(r.get("qty",0)) * get_bonus_for(r.get("product",""), r.get("date", start_d.isoformat()))
                rows.append({"bucket": d, "email": r["email"], "bonus": bonus})
        idx = pd.Index([start_d + timedelta(n) for n in range((end_d-start_d).days+1)], name="תאריך")
    if not rows:
        return pd.DataFrame(index=idx)
    df = pd.DataFrame(rows).groupby(["bucket","email"], as_index=False)["bonus"].sum()
    df_p = df.pivot_table(index="bucket", columns="email", values="bonus", aggfunc="sum").fillna(0)
    df_p = df_p.rename(columns=email_to_label)
    # Ensure full bucket coverage (e.g., 24 hours for "היום" or full date range) so single events still render as a line
    try:
        df_p = df_p.reindex(idx, fill_value=0)
    except Exception:
        pass
    df_p = df_p.reindex(idx, fill_value=0)
    return df_p

st.set_page_config(page_title="ברדק - מערכת בונוסים", page_icon="💰", layout="wide")

def inject_base_css():
    st.markdown("""
    <style>
    :root { --sidebar-width: 18rem; }
    [data-testid="stSidebar"]{ left:auto!important; right:0!important; border-left:1px solid #1f2937!important; border-right:none!important; width:var(--sidebar-width)!important; z-index:100; }
    [data-testid="stSidebarCollapsedControl"]{ right:.25rem!important; left:auto!important; }
    [data-testid="stSidebar"][aria-expanded="true"] ~ div [data-testid="stAppViewContainer"]{ padding-right: calc(var(--sidebar-width) + 1rem)!important; }
    [data-testid="stSidebar"][aria-expanded="false"] ~ div [data-testid="stAppViewContainer"]{ padding-right: 1rem!important; }
    html, body { overflow-x: hidden; }
    .user-badge-side{ display:flex; align-items:center; justify-content:space-between; gap:.75rem; padding:.25rem .25rem .75rem 0; }
    .user-badge-side .dot{ width:16px; height:16px; border-radius:999px; display:inline-block; }
    .user-badge-side .u-text{ font-weight:700; font-size:1.05rem; display:flex; align-items:center; gap:.5rem; }
    .role-badge{ font-size:.72rem; font-weight:700; padding:.15rem .45rem; border-radius:999px; background:#f59e0b1a; border:1px solid #f59e0b55; color:#f59e0b; }
    .popup-title{ font-weight:800; font-size:1.1rem; margin-bottom:.35rem; }
    </style>
    """, unsafe_allow_html=True)

inject_base_css()

if "theme_light" not in st.session_state:
    st.session_state.theme_light = True
if "user" not in st.session_state:
    st.session_state.user = None

# Auto-login from URL session id if present and no user in session_state yet
try:
    if not st.session_state.user:
        sid_from_url = st.query_params.get("sid")
        if sid_from_url:
            u = get_user_by_session(sid_from_url)
            if u:
                st.session_state.user = u
except Exception:
    pass

with st.sidebar:
    st.caption("📡 מצב אחסון: " + ("Firebase Firestore" if FIREBASE_ENABLED else "קבצי JSON מקומיים"))
    with st.expander("Diagnostics"):
        try:
            st.json(FIREBASE_DIAG)
        except Exception:
            st.write("no diagnostics available")

    if st.session_state.user:
        _u = st.session_state.user
        role_html = '<span class="role-badge">👑 אדמין</span>' if _u.get("is_admin", False) else ""
        st.markdown(f"""
        <div class="user-badge-side">
          <span class="u-text">{_u['name']} &middot; צוות {_u['team']} {role_html}</span>
          <span class="dot" style="background:{_u.get('color', '#4F46E5')}"></span>
        </div>
        """, unsafe_allow_html=True)


    # --- Goals progress (sidebar) [placed here instead of Light toggle] ---
    try:
        if st.session_state.get("user"):
            _u = st.session_state["user"]
            today = now_ij().date() if "now_ij" in globals() else __import__("datetime").datetime.now().date()
            daily_val = sum_bonus_for_email_range(_u["email"], today, today) if "sum_bonus_for_email_range" in globals() else 0
            if "week_bounds" in globals():
                wk_s, wk_e = week_bounds(today)
            else:
                import datetime as _dt
                wk_s = today - _dt.timedelta(days=today.weekday())
                wk_e = wk_s + _dt.timedelta(days=6)
            weekly_val = sum_bonus_for_email_range(_u["email"], wk_s, wk_e) if "sum_bonus_for_email_range" in globals() else 0
            if "month_bounds" in globals():
                mo_s, mo_e = month_bounds(today)
            else:
                import calendar as _cal, datetime as _dt
                mo_s = today.replace(day=1)
                last_day = _cal.monthrange(today.year, today.month)[1]
                mo_e = today.replace(day=last_day)
            monthly_val = sum_bonus_for_email_range(_u["email"], mo_s, mo_e) if "sum_bonus_for_email_range" in globals() else 0
    
            goals = _u.get("goals", {}) or {}
            g_day = int(goals.get("daily", 0) or 0)
            g_week = int(goals.get("weekly", 0) or 0)
            g_month = int(goals.get("monthly", 0) or 0)
    
            st.markdown("### 🎯 התקדמות יעדים")
            st.markdown(_goal_bar_html("יעד יומי",   int(daily_val),   g_day),   unsafe_allow_html=True)
            st.markdown(_goal_bar_html("יעד שבועי",  int(weekly_val),  g_week),  unsafe_allow_html=True)
            st.markdown(_goal_bar_html("יעד חודשי",  int(monthly_val), g_month), unsafe_allow_html=True)
    except Exception as _e_goalbars:
        st.caption(f"⚠️ לא ניתן להציג התקדמות יעדים: {_e_goalbars}")
    
    st.markdown("### ⚙️ לוח בקרה")
    if st.session_state.user:
        with st.popover("פרופיל והגדרות", use_container_width=True):
            st.caption("עריכת פרופיל, צבע, יעדים והרשאות נראות בצוות")
            user = st.session_state.user
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input("שם עובד", value=user.get("name",""))
                st.text_input("צוות", value=user.get("team",""), disabled=True)
                new_team = user.get("team","")
                invisible = st.checkbox("בלתי נראה בדשבורד צוותי", value=user.get("invisible", False))
                color = st.color_picker("צבע משתמש", value=user.get("color", "#4F46E5"))
            with col2:
                daily_goal = st.number_input("יעד יומי (₪)", min_value=0, step=10, value=int(user.get("goals",{}).get("daily",0)))
                weekly_goal = st.number_input("יעד שבועי (₪)", min_value=0, step=10, value=int(user.get("goals",{}).get("weekly",0)))
                monthly_goal = st.number_input("יעד חודשי (₪)", min_value=0, step=10, value=int(user.get("goals",{}).get("monthly",0)))
                st.text_input("הרשאה", value=("אדמין" if user.get("is_admin") else "משתמש"), disabled=True)
            if st.button("שמירת פרופיל", use_container_width=True):
                payload = dict(
                    invisible=bool(invisible),
                    color=str(color),
                    goals={"daily": int(daily_goal), "weekly": int(weekly_goal), "monthly": int(monthly_goal)},
                    name=new_name,
                )
                # שינוי צוות רק ע"י אדמין
                if user.get("is_admin"):
                    payload["team"] = str(new_team)
                ok, msg = update_user(user["email"], **payload)
                if ok:
                    st.success("הפרופיל נשמר.")
                    db = load_users()
                    st.session_state.user = db["users"].get(user["email"], user)
                    st.rerun()
                else:
                    st.error(msg)

        with st.popover("החלפת סיסמה", use_container_width=True):
            st.caption("שנה את הסיסמה שלך")
            p1, p2, p3 = st.columns(3)
            old_pwd = p1.text_input("סיסמה נוכחית", type="password")
            new_pwd = p2.text_input("סיסמה חדשה", type="password")
            new_pwd2 = p3.text_input("אימות סיסמה חדשה", type="password")
            if st.button("עדכון סיסמה", use_container_width=True):
                user = st.session_state.user
                if not old_pwd or not new_pwd or not new_pwd2:
                    st.error("נא למלא את כל השדות.")
                elif new_pwd != new_pwd2:
                    st.error("האימות של הסיסמה החדשה נכשל.")
                elif not check_password(old_pwd, user["password"]):
                    st.error("הסיסמה הנוכחית שגויה.")
                else:
                    ok, msg = update_user(user["email"], password=hash_password(new_pwd))
                    st.success("הסיסמה עודכנה.") if ok else st.error(msg)

        with st.popover("מחיקת משתמש", use_container_width=True):
            st.caption("זהירות! פעולה בלתי הפיכה")
            really = st.checkbox("אני מאשר/ת שמחיקת המשתמש תמחק גם את כל הנתונים שלי לצמיתות")
            if st.button("מחק משתמש", type="secondary", use_container_width=True):
                if really:
                    email_to_delete = st.session_state.user["email"]
                    # Clear session metadata for this user before deletion
                    clear_user_session(email_to_delete)
                    delete_user(email_to_delete)
                    st.success("המשתמש נמחק. מתנתק...")
                    st.session_state.user = None
                    st.rerun()
                else:
                    st.error("יש לאשר את תיבת הסימון לפני מחיקה.")

        st.markdown("---")
        if st.button("התנתקות", use_container_width=True):
            # Clear server-side session for this user
            if st.session_state.user:
                clear_user_session(st.session_state.user.get("email", ""))
            st.session_state.user = None
            st.rerun()

    st.markdown("---")
    st.markdown("### 📬 הודעות מערכת")
    if st.session_state.user:
        user_email = st.session_state.user["email"].lower().strip()
        md = load_messages()
        msgs_all = sorted(md.get("messages", []), key=lambda m: m.get("created_at",""), reverse=True)
        unread, read = [], []
        team = st.session_state.user.get("team","")
        for m in msgs_all:
            if not m.get("active", True):
                continue
            targeted = m.get("target_all") or \
                       (user_email in [e.lower() for e in m.get("target_emails", [])]) or \
                       (team and team in m.get("target_teams", []))
            if not targeted:
                continue
            if user_email in m.get("dismissed_for", []):
                read.append(m)
            else:
                unread.append(m)
        cA, cB = st.columns([1,1])
        cA.caption(f"לא נקראו: **{len(unread)}**")
        if unread and cB.button("✔️ סמן הכל כנקרא", use_container_width=True):
            for m in unread:
                mark_dismissed_for_user(m["id"], user_email)
            st.rerun()

        if unread:
            st.markdown("#### לא נקראו")
            for m in unread:
                with st.expander(f"{m.get('title','הודעה')} • {fmt_ts(m.get('created_at',''))}", expanded=True):
                    st.write(m.get("text",""))
                    if st.button("סגור / קראתי", key=f"ack_{m['id']}"):
                        mark_dismissed_for_user(m["id"], user_email)
                        st.rerun()
        st.markdown("#### היסטוריה")
        if read:
            for m in read[:50]:
                with st.expander(f"{m.get('title','הודעה')} • {fmt_ts(m.get('created_at',''))}", expanded=False):
                    st.write(m.get("text",""))
        else:
            st.caption("אין היסטוריית הודעות.")
    else:
        st.info("התחבר/י כדי לראות הגדרות.")

def begin_skin(light: bool):
    klass = "light app-skin" if light else "app-skin"
    st.markdown(f'<div class="{klass}">', unsafe_allow_html=True)
def end_skin():
    st.markdown("</div>", unsafe_allow_html=True)

begin_skin(st.session_state.theme_light)
st.markdown(
    "<h1 style='text-align:right; direction:rtl; margin:0'> ברדק • מערכת בונוסים (new site brdk.duckdns.org) 💰</h1>",
    unsafe_allow_html=True
)

def view_auth():
    tab_login, tab_register = st.tabs(["התחברות", "הרשמה"])
    with tab_login:
        st.subheader("כניסה למערכת")
        email = st.text_input("אימייל / שם משתמש", key="login_email")
        pwd = st.text_input("סיסמה", type="password", key="login_pwd")
        if st.button("התחברות"):
            ok, res = authenticate(email, pwd)
            if ok:
                st.session_state.user = res
                # put session id into URL so refreshes/tab restore still know who is logged-in
                try:
                    st.query_params["sid"] = res.get("session_sid", "")
                except Exception:
                    pass
                st.success(f"מחובר כעת: {res['name']} ({res['team']})")
                st.rerun()
            else:
                st.error(res)
    with tab_register:
        st.subheader("הרשמה לעובדים")
        name = st.text_input("שם מלא", key="reg_name")
        email = st.text_input("אימייל / שם משתמש", key="reg_email")
        team_label = st.selectbox("צוות", options=[f"צוות {i}" for i in range(1,6)], index=0, key="reg_team")
        team = str(team_label.split()[-1])
        invisible = st.checkbox("בלתי נראה בטבלת הצוות", value=False, help="אם מסומן – לא תופיע/י בדשבורד הצוותי")
        pwd = st.text_input("סיסמה", type="password", key="reg_pwd")
        pwd2 = st.text_input("אימות סיסמה", type="password", key="reg_pwd2")
        if st.button("יצירת משתמש"):
            if not name or not email or not team or not pwd:
                st.error("נא למלא את כל השדות.")
            elif pwd != pwd2:
                st.error("הסיסמאות אינן תואמות.")
            else:
                ok, msg = register_user(name, email, pwd, team, invisible)
                st.success(msg) if ok else st.error(msg)

if "user" not in st.session_state or not st.session_state.user:
    view_auth()
    end_skin()
    st.stop()

def refresh_user():
    db = load_users()
    st.session_state.user = db["users"].get(st.session_state.user["email"], st.session_state.user)

refresh_user()
user = st.session_state.user

st.markdown(
    f"""
<div style="display:flex; justify-content:flex-end; align-items:center; gap:.75rem; padding:.25rem 0;">
  <div style="font-size:1.1rem; font-weight:700;">{user['name']} &middot; צוות {user['team']}</div>
  <span class="dot" style="width:14px;height:14px;background:{user.get("color","#4F46E5")};display:inline-block;border-radius:999px;"></span>
</div>
""",
    unsafe_allow_html=True,
)


def build_whatsapp_daily_text(display_name: str, day_date, counts: dict) -> str:
    """Create a Hebrew WhatsApp message of today's sales (product + quantity only)."""
    # Keep only >0 items
    lines = []
    for p in PRODUCTS:
        qty = int(counts.get(p["code"], 0) or 0)
        if qty > 0:
            # e.g., "מודם: 3"
            lines.append(f"{p['name']}: {qty}")
    if not lines:
        lines.append("אין פריטים מדווחים להיום.")
    dstr = day_date.strftime("%d.%m.%Y")
    header = f"היום חשמלתי – {display_name} – {dstr}"
    body = "\n".join(lines)
    return f"{header}\n{body}"

def whatsapp_share_url(message_text: str) -> str:
    # Use wa.me for cross‑platform compatibility; user selects the target chat (group).
    return "https://wa.me/?text=" + urllib.parse.quote(message_text)

tabs = ["היום", "תיקונים / היסטוריה", "דשבורד צוותי", "דוחות וייצוא"]
if user.get("is_admin"):
    tabs.extend(["ניהול משתמשים (אדמין)", "ניהול בונוסים (אדמין)", "פקודות (אדמין)"])
tab_today, tab_prev, tab_team, tab_reports, *maybe_admin_tabs = st.tabs(tabs)

with tab_today:
    st.subheader("הזנת מכירות להיום")
    today = now_ij().date()
    counts = get_counts_for_user_date(user["email"], today)

    form = st.form("today_form")
    cols = form.columns(3)
    fields = {}
    for i,p in enumerate(PRODUCTS):
        col = cols[i % 3]
        fields[p["code"]] = col.number_input(f"{p['name']} (בונוס {get_bonus_for(p['code'], today)}₪)", min_value=0, step=1, value=int(counts.get(p["code"],0)))
    if form.form_submit_button("שמירה להיום"):
        add_or_set_counts(user["email"], today, {k:int(v) for k,v in fields.items()})
        st.success("הנתונים נשמרו להיום!")

    counts_today = get_counts_for_user_date(user["email"], today)
    # WhatsApp share (group: טכני חיפה - מכירות). Sends only product names and quantities.
    share_text = build_whatsapp_daily_text(user.get("name","ללא שם"), today, counts_today)
    st.caption("שליחת הדיווח לוואטסאפ (ללא ציון בונוסים)")
    st.link_button("💸Whatsapp - שליחת סיכום יומי", whatsapp_share_url(share_text), use_container_width=True)

    bonus_today = sum(qty * get_bonus_for(code, today) for code, qty in counts_today.items())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("בונוס היום (₪)", int(bonus_today))
    c2.metric("סה\"כ פריטים", sum(counts_today.values()))
    g = user.get("goals", {})
    if g.get("daily", 0):
        c3.metric("התקדמות מול יעד יומי", f"{int((bonus_today/max(1,g.get('daily',1)))*100)}%")
    else:
        c3.metric("התקדמות מול יעד יומי", "—")
    yest = today - timedelta(days=1)
    y_counts = get_counts_for_user_date(user["email"], yest)
    y_bonus = sum(qty * get_bonus_for(code, yest) for code, qty in y_counts.items())
    c4.metric("אתמול (₪)", int(y_bonus))

with tab_prev:
    st.subheader("תיקונים וצפייה בהיסטוריה")
    sel_date = st.date_input("בחר תאריך", value=now_ij().date(), max_value=now_ij().date())
    existing = get_counts_for_user_date(user["email"], sel_date)
    form2 = st.form("edit_form")
    cols = form2.columns(3)
    fields2 = {}
    for i,p in enumerate(PRODUCTS):
        col = cols[i % 3]
        fields2[p["code"]] = col.number_input(f"{p['name']} (בונוס {get_bonus_for(p['code'], sel_date)}₪)", min_value=0, step=1, value=int(existing.get(p["code"],0)))
    if form2.form_submit_button("שמירה לתאריך זה"):
        add_or_set_counts(user["email"], sel_date, {k:int(v) for k,v in fields2.items()})
        st.success("הנתונים נשמרו לתאריך שנבחר.")

    today = now_ij().date()
    wk_s, wk_e = week_bounds(today)
    mo_s, mo_e = month_bounds(today)
    c1, c2, c3 = st.columns(3)
    c1.metric("אתמול (₪)", sum_bonus_for_email_range(user["email"], today - timedelta(days=1), today - timedelta(days=1)))
    c2.metric("שבוע נוכחי (₪)", sum_bonus_for_email_range(user["email"], wk_s, wk_e))
    c3.metric("חודש נוכחי (₪)", sum_bonus_for_email_range(user["email"], mo_s, mo_e))


with tab_team:
    st.subheader("דשבורד צוותי")
    st.caption("ברירת מחדל: משתמש רגיל רואה רק את הצוות שלו. אדמין יכול לבחור צוות או 'כולם', וגם לכלול משתמשים בלתי נראים.")

    # Period controls
    period = st.selectbox("טווח", ["היום", "שבוע נוכחי", "חודש נוכחי", "מותאם אישית"], index=0)
    colr1, colr2, colr3 = st.columns([1,1,1])
    use_custom = (period == "מותאם אישית")
    today = now_ij().date()
    start_custom = colr2.date_input("מתאריך", value=today.replace(day=1), key="team_range_start") if use_custom else None
    end_custom = colr3.date_input("עד תאריך", value=today, key="team_range_end") if use_custom else None

    # Team selection
    include_invisible = False
    if user.get("is_admin"):
        dbu = load_users()
        teams = sorted({u.get("team","") for u in dbu.get("users",{}).values() if u.get("team")})
        teams_options = ["כל הצוותים"] + teams
        csel1, csel2 = st.columns([2,1])
        selected_label = csel1.selectbox("בחר צוות לתצוגה (אדמין)", options=teams_options, index=teams_options.index(user["team"]) if user["team"] in teams else 0)
        include_invisible = csel2.checkbox("כולל 'בלתי נראה' (אדמין)", value=False)
        selected_team_key = "ALL" if selected_label == "כל הצוותים" else selected_label
    else:
        selected_team_key = user["team"]

    # Compute date range
    if use_custom and start_custom and end_custom and start_custom <= end_custom:
        start_d, end_d = start_custom, end_custom
        period_label = f"{start_d} – {end_d}"
        period_key = "CUSTOM"
    else:
        if period == "היום":
            start_d = end_d = today
        elif period == "שבוע נוכחי":
            start_d, end_d = week_bounds(today)
        else:
            start_d, end_d = month_bounds(today)
        period_label = period
        period_key = period

    # Aggregate
    if selected_team_key == "ALL":
        members = group_members_by_filter("ALL", include_invisible=include_invisible)
        members = [m for m in members if m.get("email") and m.get("name")]
        counts = {m["email"]: aggregate_user_counts(m["email"], start_d, end_d) for m in members}
        bonuses = {m["email"]: sum_bonus_for_email_range(m["email"], start_d, end_d) for m in members}
        label_for_header = "כל הצוותים"
    else:
        members, counts, bonuses = team_aggregate(selected_team_key, start_d, end_d, include_invisible=include_invisible)
        label_for_header = f"צוות {selected_team_key}"

    st.markdown(f"**תצוגה:** {label_for_header}  •  טווח: {period_label}" + (f"  •  כולל בלתי נראים" if include_invisible and selected_team_key == "ALL" else ""))

    # Table
    header = ["שם", "צוות", "בונוס (₪)", "סהכ פריטים"] + [p["name"] for p in PRODUCTS]
    rows = []
    for m in members:
        email = m["email"]
        b = bonuses.get(email, 0)
        cnt = counts.get(email, {p["code"]: 0 for p in PRODUCTS})
        total_items = sum(cnt.values())
        row = [m["name"], m.get("team",""), int(b), total_items] + [cnt.get(p["code"], 0) for p in PRODUCTS]
        rows.append(row)

    if rows:
        import pandas as pd, io, csv, altair as alt
        df_table_full = pd.DataFrame(rows, columns=header)
        st.dataframe(df_table_full, use_container_width=True, hide_index=True)
        buff = io.StringIO(); df_table_full.to_csv(buff, index=False, quoting=csv.QUOTE_NONNUMERIC)
        st.download_button("הורדת CSV צוותי", data=buff.getvalue().encode("utf-8-sig"),
                           file_name=f"team_{label_for_header}_{start_d}_{end_d}.csv", mime="text/csv")
    else:
        st.info("אין נתונים להצגה עבור הטווח.")

    # Chart
    df_series = build_group_timeseries(members, period_key, start_d, end_d)
    st.markdown("### 📈 גרף בונוס לפי זמן")
    if 'pd' not in globals():
        import pandas as pd
    if df_series is None or (hasattr(df_series, "empty") and df_series.empty):
        st.info("אין עדיין נתונים לגרף בטווח שנבחר.")
    else:
        cumulative = st.toggle("הצג מצטבר", value=True, help="סיכום מצטבר לאורך הציר")
        to_plot = df_series.cumsum() if cumulative else df_series
        names = [_display_label(m) for m in members]
        colors = [m.get("color", "#4F46E5") for m in members]
        import altair as alt
        chart = (alt.Chart(to_plot.reset_index().melt(id_vars=to_plot.index.name, var_name="משתמש", value_name="בונוס"))
                 .encode(
                    x=alt.X(f"{to_plot.index.name}:T" if to_plot.index.name=="תאריך" else f"{to_plot.index.name}:O", title=to_plot.index.name),
                    y=alt.Y("בונוס:Q"),
                    color=alt.Color("משתמש:N", scale=alt.Scale(domain=names, range=colors))
                 ).mark_line(point=True))
        point_layer = (alt.Chart(to_plot.reset_index().melt(id_vars=to_plot.index.name, var_name="משתמש", value_name="בונוס"))
                 .encode(
                    x=alt.X(f"{to_plot.index.name}:T" if to_plot.index.name=="תאריך" else f"{to_plot.index.name}:O", title=to_plot.index.name),
                    y=alt.Y("בונוס:Q"),
                    color=alt.Color("משתמש:N", scale=alt.Scale(domain=names, range=colors))
                 ).mark_point(size=60))
        st.altair_chart(chart + point_layer, use_container_width=True)

with tab_reports:
    st.subheader("דוחות אישיים וייצוא")
    today = now_ij().date()
    colA, colB = st.columns(2)
    start_d = colA.date_input("מתאריך", value=today.replace(day=1), key="reports_start")
    end_d = colB.date_input("עד תאריך", value=today, max_value=today, key="reports_end")
    if start_d > end_d:
        st.warning("טווח תאריכים שגוי.")
    else:
        b = sum_bonus_for_email_range(user["email"], start_d, end_d)
        st.markdown(f"**בונוס בטווח (₪):** {int(b)}")
        rows = []
        if FIREBASE_ENABLED:
            s = start_d.isoformat(); e = end_d.isoformat()
            q = DB.collection("records").where("email","==",user["email"]).where("date",">=",s).where("date","<=",e).stream()
            for ddoc in q:
                r = ddoc.to_dict() or {}
                price = get_bonus_for(r.get("product",""), r.get("date", s))
                prod = PRODUCT_INDEX.get(r.get("product",""), {"name": r.get("product",""), "bonus": price})
                rows.append({
                    "תאריך": r.get("date",""),
                    "מוצר": prod["name"],
                    "כמות": int(r.get("qty",0)),
                    "בונוס ליחידה (לפי תאריך)": price,
                    "סה\"כ בונוס": int(r.get("qty",0)) * int(price),
                    "עדכון": r.get("ts",""),
                })
        else:
            records = load_records()["records"]
            for r in records:
                if r["email"] == user["email"] and start_d.isoformat() <= r["date"] <= end_d.isoformat():
                    price = get_bonus_for(r["product"], r["date"])
                    prod = PRODUCT_INDEX.get(r["product"], {"name": r["product"], "bonus": price})
                    rows.append({
                        "תאריך": r["date"],
                        "מוצר": prod["name"],
                        "כמות": int(r["qty"]),
                        "בונוס ליחידה (לפי תאריך)": price,
                        "סה\"כ בונוס": int(r["qty"]) * int(price),
                        "עדכון": r.get("ts",""),
                    })
        import pandas as pd
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values(["תאריך","מוצר"])
            st.dataframe(df, use_container_width=True, hide_index=True)
            buff = io.StringIO(); df.to_csv(buff, index=False, quoting=csv.QUOTE_NONNUMERIC)
            st.download_button("הורדת CSV אישי", data=buff.getvalue().encode("utf-8-sig"),
                               file_name=f"personal_{start_d}_{end_d}.csv", mime="text/csv")
        else:
            st.info("אין נתונים בטווח שנבחר.")

if user.get("is_admin") and maybe_admin_tabs:
    tab_admin_users = maybe_admin_tabs[0]
    tab_admin_prices = maybe_admin_tabs[1]
    tab_admin_cmds = maybe_admin_tabs[2]

    with tab_admin_users:
        st.header("👑 ניהול משתמשים (אדמין)")
        dbu = load_users()
        all_users = list(dbu.get("users", {}).values())
        teams = sorted({u.get("team","") for u in all_users if u.get("team")})
        colf1, colf2, colf3 = st.columns([1,1,2])
        team_filter = colf1.selectbox("סינון לפי צוות", options=["כל הצוותים"] + teams, index=0)
        show_invis = colf2.checkbox("הצג גם 'בלתי נראה'", value=True)
        q = colf3.text_input("חיפוש לפי שם/אימייל", placeholder="הקלד לחיפוש...")

        def match(u):
            if not show_invis and u.get("invisible"):
                return False
            if team_filter != "כל הצוותים" and u.get("team") != team_filter:
                return False
            if q:
                s = (u.get("name","") + " " + u.get("email","")).lower()
                return q.lower() in s
            return True

        filtered = [u for u in all_users if match(u)]
        st.info(f"נמצאו {len(filtered)} משתמשים.")

        export_rows = []
        for u in filtered:
            export_rows.append({
                "name": u.get("name",""),
                "email": u.get("email",""),
                "team": u.get("team",""),
                "invisible": u.get("invisible", False),
                "is_admin": u.get("is_admin", False),
                "color": u.get("color",""),
                "created_at": u.get("created_at",""),
                "last_login_at": u.get("last_login_at",""),
                "goal_daily": u.get("goals",{}).get("daily",0),
                "goal_weekly": u.get("goals",{}).get("weekly",0),
                "goal_monthly": u.get("goals",{}).get("monthly",0),
            })
        if export_rows:
            import pandas as pd, io, csv
            dfu = pd.DataFrame(export_rows)
            buff = io.StringIO(); dfu.to_csv(buff, index=False, quoting=csv.QUOTE_NONNUMERIC)
            st.download_button("הורדת CSV משתמשים (מסונן)", data=buff.getvalue().encode("utf-8-sig"),
                               file_name="users_filtered.csv", mime="text/csv")

        st.markdown("---")
        for u in filtered:
            with st.expander(
    f"✏️ {u.get('name','ללא שם')}  •  {u.get('email','')}  •  צוות {u.get('team','לא מוגדר')}"
    f"  •  התחבר לאחרונה: {fmt_ts(u.get('last_login_at',''))}"
):
                col1, col2 = st.columns(2)
                with col1:
                    new_name = st.text_input("שם", value=u.get("name",""), key=f"name_{u['email']}")
                    label_team = st.selectbox("צוות", options=[f"צוות {i}" for i in range(1,6)], index=max(0, int(u.get("team","1"))-1), key=f"team_{u['email']}")
                    new_team = str(label_team.split()[-1])
                    new_invis = st.checkbox("בלתי נראה בדשבורד צוותי", value=u.get("invisible", False), key=f"invis_{u['email']}")
                    new_color = st.color_picker("צבע משתמש", value=u.get("color", "#4F46E5"), key=f"color_{u['email']}")
                with col2:
                    goals = u.get("goals",{})
                    g_d = st.number_input("יעד יומי (₪)", min_value=0, step=10, value=int(goals.get("daily",0)), key=f"gday_{u['email']}")
                    g_w = st.number_input("יעד שבועי (₪)", min_value=0, step=10, value=int(goals.get("weekly",0)), key=f"gweek_{u['email']}")
                    g_m = st.number_input("יעד חודשי (₪)", min_value=0, step=10, value=int(goals.get("monthly",0)), key=f"gmonth_{u['email']}")
                    st.text_input("סטטוס", value=("אדמין" if u.get("is_admin") else "משתמש"), disabled=True, key=f"role_{u['email']}")

                st.caption(f"פעם אחרונה מחובר: {fmt_ts(u.get('last_login_at',''))}")
                cA, cB, cC = st.columns([1,1,2])
                if cA.button("שמירת שינויים", key=f"save_{u['email']}"):
                    ok, msg = update_user(
                        u["email"],
                        name=new_name,
                        team=new_team,
                        invisible=bool(new_invis),
                        color=str(new_color),
                        goals={"daily": int(g_d), "weekly": int(g_w), "monthly": int(g_m)},
                    )
                    st.success("נשמר.") if ok else st.error(msg)
                    st.rerun()

                with cB.popover("איפוס סיסמה"):
                    np1 = st.text_input("סיסמה חדשה", type="password", key=f"np1_{u['email']}")
                    np2 = st.text_input("אימות סיסמה חדשה", type="password", key=f"np2_{u['email']}")
                    if st.button("אפס סיסמה", key=f"doreset_{u['email']}"):
                        if not np1 or not np2:
                            st.error("נא למלא סיסמה חדשה פעמיים.")
                        elif np1 != np2:
                            st.error("האימות נכשל.")
                        else:
                            ok, msg = update_user(u["email"], password=hash_password(np1))
                            st.success("סיסמה אופסה.") if ok else st.error(msg)

                with cC.popover("🗑️ מחיקת משתמש"):
                    st.warning("הפעולה תמחק את המשתמש **וכל ההיסטוריה** שלו לצמיתות.")
                    chk = st.checkbox("אני מאשר/ת מחיקה", key=f"delchk_{u['email']}")
                    if st.button("מחק לצמיתות", key=f"del_{u['email']}"):
                        if chk:
                            delete_user(u["email"])
                            st.success("המשתמש נמחק.")
                            st.rerun()
                        else:
                            st.error("יש לאשר את תיבת הסימון לפני מחיקה.")

    with tab_admin_prices:
        st.header("👑 ניהול בונוסים לפי תאריך תחילה (אדמין)")

        # --- Admin: Product management (add/delete) ---
        st.markdown("### 🧩 ניהול מוצרים (פריטים)")
        prods = load_products()
        exist_codes = {p["code"] for p in prods}

        with st.expander("➕ הוספת מוצר בונוס חדש", expanded=False):
            c1, c2, c3 = st.columns([1.2, 2.0, 1.0])
            new_code = c1.text_input("קוד מוצר (אנגלית/ספרות/קו תחתון)", placeholder="e.g. cyber_plus_pro").strip()
            new_name = c2.text_input("שם מוצר לתצוגה").strip()
            new_bonus = c3.number_input("בונוס ברירת מחדל (₪)", min_value=0, step=1, value=0)
            add_now = st.button("הוסף מוצר", type="primary", use_container_width=False)
            if add_now:
                import re as _re
                if not new_code or not _re.fullmatch(r"[A-Za-z0-9_\-]+", new_code):
                    st.error("קוד מוצר חייב להיות באנגלית/ספרות/קו תחתון/מקף בלבד.")
                elif new_code in exist_codes:
                    st.error("קוד המוצר כבר קיים.")
                elif not new_name:
                    st.error("נא למלא שם מוצר.")
                else:
                    prods.append({"code": new_code, "name": new_name, "bonus": int(new_bonus)})
                    save_products(prods)
                    cfg = load_bonus_config()
                    for sch in cfg.get("schedules", []):
                        sch.setdefault("prices", {})
                        if new_code not in sch["prices"]:
                            sch["prices"][new_code] = int(new_bonus)
                    save_bonus_config(cfg)
                    refresh_products()
                    st.success("המוצר נוסף בהצלחה.")
                    st.rerun()

        with st.expander("🗑️ מחיקת מוצר מהרשימה (לא פוגע בהיסטוריה)", expanded=False):
            if not prods:
                st.info("אין מוצרים זמינים.")
            else:
                c1, c2 = st.columns([2,1])
                del_code = c1.selectbox("בחר קוד למחיקה", options=[p["code"] for p in prods], format_func=lambda c: next((f"{x['name']} — {x['code']}" for x in prods if x['code']==c), c))
                really = c2.checkbox("מאשר/ת")
                if st.button("מחק מוצר", type="secondary"):
                    if not really:
                        st.error("יש לאשר את המחיקה (תיבת סימון).")
                    else:
                        prods2 = [p for p in prods if p["code"] != del_code]
                        save_products(prods2)
                        refresh_products()
                        st.success("המוצר הוסר מרשימת הקלט. נתוני עבר נשארים ללא שינוי")

        with st.expander("✏️ שינוי שם מוצר קיים", expanded=False):
            prods = load_products()
            if not prods:
                st.info("אין מוצרים לשינוי.")
            else:
                c1, c2 = st.columns([2, 2])
                sel_code = c1.selectbox(
                    "בחר קוד מוצר",
                    options=[p["code"] for p in prods],
                    format_func=lambda c: next((f"{x['name']} — {x['code']}" for x in prods if x['code']==c), c)
                )
                current_name = next((p["name"] for p in prods if p["code"] == sel_code), "")
                new_name = c2.text_input("שם תצוגה חדש", value=current_name).strip()
                if st.button("עדכן שם"):
                    if not new_name:
                        st.error("שם חדש לא יכול להיות ריק.")
                    elif new_name == current_name:
                        st.info("לא בוצע שינוי.")
                    else:
                        for p in prods:
                            if p["code"] == sel_code:
                                p["name"] = new_name
                                break
                        save_products(prods)
                        refresh_products()
                        st.success("שם המוצר עודכן בהצלחה.")
                        st.rerun()
                        st.rerun()
        data = load_bonus_schedules()
        schedules = data["schedules"][:]
        if not schedules:
            st.error("לא נמצא קובץ/מסמך בונוסים.")
        else:
            st.subheader("➕ יצירת/עדכון לוח מחירים חדש")
            c1, c2 = st.columns([1,3])
            eff_date = c1.date_input("תאריך תחילה", value=now_ij().date())
            base_prices = {p["code"]: int(p["bonus"]) for p in PRODUCTS}
            for sch in schedules:
                if date.fromisoformat(sch["effective_date"]) <= eff_date:
                    base_prices = sch["prices"]
                else:
                    break
            cols = st.columns(3)
            new_prices = {}
            for i,p in enumerate(PRODUCTS):
                col = cols[i % 3]
                new_prices[p["code"]] = int(col.number_input(f"{p['name']}", min_value=0, step=1, value=int(base_prices.get(p["code"], p["bonus"]))))
            if st.button("שמירה כלוח מחירים בתוקף מהתאריך הנבחר", use_container_width=True):
                replaced = False
                for sch in data["schedules"]:
                    if sch["effective_date"] == eff_date.isoformat():
                        sch["prices"] = new_prices
                        replaced = True
                        break
                if not replaced:
                    data["schedules"].append({"effective_date": eff_date.isoformat(), "prices": new_prices})
                save_bonus_schedules(data)
                create_message(
                    text=f"עודכן לוח בונוסים החל מ־{eff_date.isoformat()}.",
                    target_all=True, target_emails=[], target_teams=[],
                    sticky=True, meta={"type":"bonus_update","effective_date":eff_date.isoformat(),"prices":new_prices}, title="שינוי בונוס", sender="system"
                )
                st.success("לוח המחירים נשמר/עודכן.")
                st.rerun()

            st.markdown("---")
            st.subheader("🗂️ כל הלוחות (按 תאריך)")
            schedules = load_bonus_schedules()["schedules"]
            schedules.sort(key=lambda s: s["effective_date"], reverse=True)
            for sch in schedules:
                with st.expander(f"💾 תוקף מ־ {sch['effective_date']}"):
                    cols = st.columns(3)
                    edited = {}
                    for i,p in enumerate(PRODUCTS):
                        col = cols[i % 3]
                        edited[p["code"]] = int(col.number_input(f"{p['name']}", min_value=0, step=1, value=int(sch['prices'].get(p['code'], p['bonus'])), key=f"{sch['effective_date']}_{p['code']}"))
                    cc1, cc2, cc3 = st.columns([1,1,2])
                    new_eff = cc1.date_input("שנה תאריך תחילה", value=date.fromisoformat(sch["effective_date"]), key=f"eff_{sch['effective_date']}")
                    if cc2.button("עדכון לוח", key=f"upd_{sch['effective_date']}"):
                        d_all = load_bonus_schedules()
                        d_all["schedules"] = [s for s in d_all["schedules"] if s["effective_date"] != sch["effective_date"]]
                        found = False
                        for s2 in d_all["schedules"]:
                            if s2["effective_date"] == new_eff.isoformat():
                                s2["prices"] = edited
                                found = True
                                break
                        if not found:
                            d_all["schedules"].append({"effective_date": new_eff.isoformat(), "prices": edited})
                        save_bonus_schedules(d_all)
                        st.success("עודכן.")
                        st.rerun()
                    if cc3.button("מחיקה", key=f"del_{sch['effective_date']}"):
                        d_all = load_bonus_schedules()
                        d_all["schedules"] = [s for s in d_all["schedules"] if s["effective_date"] != sch["effective_date"]]
                        if not d_all["schedules"]:
                            st.error("לא ניתן למחוק את כל הלוחות.")
                        else:
                            save_bonus_schedules(d_all)
                            st.success("נמחק.")
                            st.rerun()

    with tab_admin_cmds:
        st.header("📣 פקודות / הודעות POP-UP (אדמין)")
        dbu = load_users()
        all_users = list(dbu.get("users", {}).values())
        all_emails = [u["email"] for u in all_users]
        all_teams = sorted({u.get("team","") for u in all_users if u.get("team")})

        send_to_all = st.checkbox("שלח לכולם", value=False)
        colr1, colr2 = st.columns(2)
        target_users = []
        target_teams = []
        if not send_to_all:
            target_users = colr1.multiselect("בחר משתמשים ספציפיים", options=all_emails)
            target_teams = colr2.multiselect("או בחר צוותים", options=all_teams)

        title_msg = st.text_input("כותרת ההודעה", placeholder="למשל: תזכורת חשובה" )
        text = st.text_area("תוכן ההודעה", placeholder="מה תרצה שיקפוץ למשתמשים?")
        sticky = st.checkbox("הודעה דביקה (נשארת עד סגירה)", value=True)
        if st.button("שליחה", type="primary"):
            if not text.strip():
                st.error("נא למלא תוכן הודעה.")
            elif not send_to_all and not target_users and not target_teams:
                st.error("בחר משתמשים/צוותים או סמן 'שלח לכולם'.")
            else:
                title_final = title_msg.strip() if title_msg and title_msg.strip() else "הודעה"
                msg_id = create_message(text=text, target_all=send_to_all, target_emails=target_users, target_teams=target_teams, sticky=sticky, meta={"type":"admin_manual"}, title=title_final, sender=user["email"])
                st.success(f"נשלחה הודעה (msg_id={msg_id[:8]}...).")

        st.markdown("---")
        st.subheader("🧹 ניהול והסרת הודעות")
        md = load_messages()
        all_msgs = sorted(md.get("messages", []), key=lambda m: m.get("created_at",""), reverse=True)

        colm1, colm2 = st.columns([1,1])
        show_only_mine = colm1.checkbox("הצג רק הודעות ששלחתי", value=True)
        show_active_only = colm2.checkbox("הצג רק פעילות", value=False)

        filtered = []
        for m in all_msgs:
            if show_only_mine and m.get("sender") != user["email"]:
                continue
            if show_active_only and not m.get("active", True):
                continue
            filtered.append(m)

        st.caption(f"נמצאו {len(filtered)} הודעות.")

        if filtered:
            cbulk1, cbulk2 = st.columns([1,3])
            sel_ids = cbulk2.multiselect("בחר הודעות למחיקה", options=[m["id"] for m in filtered],
                                         format_func=lambda mid: next((f"{x.get('title','הודעה')} • {fmt_ts(x.get('created_at',''))}" for x in filtered if x["id"]==mid), mid))
            if cbulk1.button("מחק נבחרות", type="secondary", disabled=not sel_ids):
                for mid in sel_ids:
                    delete_message(mid)
                st.success(f"נמחקו {len(sel_ids)} הודעות.")
                st.rerun()

            for m in filtered[:100]:
                with st.expander(f"{m.get('title','הודעה')} • {fmt_ts(m.get('created_at',''))}  —  נשלח ע\"י {m.get('sender','system')}", expanded=False):
                    st.write(m.get("text",""))
                    info = {
                        "לכולם": m.get("target_all", False),
                        "משתמשים": m.get("target_emails", []),
                        "צוותים": m.get("target_teams", []),
                        "דביקה": m.get("sticky", True),
                        "פעילה": m.get("active", True),
                        "id": m.get("id")
                    }
                    st.json(info)
                    cda, cdb = st.columns([1,1])
                    if cda.button("🗑️ מחק הודעה", key=f"delmsg_{m['id']}"):
                        delete_message(m["id"])
                        st.success("הודעה נמחקה.")
                        st.rerun()
                    if cdb.button("בטל/הפעל", key=f"togglemsg_{m['id']}"):
                        update_message(m["id"], active=(not m.get("active", True)))
                        st.success("סטטוס עודכן.")
                        st.rerun()
        else:
            st.caption("אין הודעות לתצוגה.")

# =========================
# Suggestion Expander (WhatsApp) - Version 2 (compatibility mode)
# =========================
import os as _os
import base64 as _base64

# Default link provided by user (can be overridden by Secrets/ENV)
_DEFAULT_WA_LINK = "https://chat.whatsapp.com/FytX0FksN0130POzs0bpcd?mode=wwt"

# Embedded QR fallback (base64) – derived from user's image; used only if no URL/file provided
_DEFAULT_QR_B64 = """iVBORw0KGgoAAAANSUhEUgAAA94AAAbgCAYAAACWJYtRAAAAAXNSR0IArs4c6QAAAARzQklUCAgICHwIZIgAACAASURBVHic7N15mGV3fd/5z7n31r519a5udbfQLiRACAQS2GAbYuOAMRiTxM7iIYljDInHxGP7j4k9zjKZZJJJZjLj2GRfnAXH8RZvPImdBAjggAGHHQstLanVi7q79vXec+aPajVqoe6qVvepe2/36/U8Tamqzj33W8tD1bvO75xTHPr5d1UBAAAAatHo9gAAAABwLRPeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1Et4AAABQI+ENAAAANRLeAAAAUCPhDQAAADUS3gAAAFAj4Q0AAAA1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jdq/9NJLxmNU3VeDBg3Syy+/rGbNmoXch1VPHQ8EAiouLtYTTzyhxx9/XF988YX8fr9c1608PfzQvrU53HJJ+uabb7Rz504tX75cTZo0Ud++fXXddddpzJgxh+1b1fPPP2/UPhIN5XUYDU2aNIl1CXXC5/NF9D4EgPqE24kBABABr9erWbNmacWKFbWG7qp27NihiRMnKisrS9dee60++uijyuu1g4VuG77//nutWLFC5557rrKysjR9+nTt27cvauMDANAYEbwBADCUlpaml156STfddJMSEhIk1Tzy7Abcyse3b9+uCy64QO3atdPixYtVVFQU1pFqm1zX1b59+3T33XcrKytLt9xyi77//nuj/gAAIDwEbwAADLiuq1WrVumMM86otU3ADWj37t266qqr1KVLFz399NPVJkarOEIey1OrK+opLy/X3XffrWOOOUZz5swJ67phTgkHACB8BG8AAAw4jqPjjjuu8u8Vf1a9FVggENCf//xn9e/fX4888oiKi4sPu86q6zj0z4qj6tIPE1FV/Bwafg9td7hwf+i4e/fu1fXXX6+hQ4dq3bp1ldtT9U8AAGCOydUAAIhAqFBbXFysc889V//617+qHeE2XW9aWppOPPFEjRw5Up07d1ZWVpZatGih1NRUpaSkyOPxyO/36+DBgyouLtY333yjb775Rhs2bNBLL72kDz74oFqoDpfrulqzZo0GDx6sSy65RA888EC1yeEAAIA5gjcAAHVk1apVOuuss7R3716jsOr1epWUlKSuXbtq5syZOumkk5SRkSGPx3PY9Rx99NGSpE6dOkmSxo8frzvuuEN+v18FBQX64x//qHvvvVe7du0yqqm4uFhz587Vq6++qjfeeKNyAjkCOAAA5jjVHACAWpSVlR22TSAQ0MMPP6yTTz5Ze/fulcfzw3+vwU7PrvqYz+fT8ccfr4ceekh79+7VunXrdPrppysjPaNyHaHWUxvXdZWQkKCjjz5aN9xwg3bs2KHvvvtOt9xyi3JzcysDfTBVg7XjOProo4/Us2dPrVy5Uq7rcso5AAARIHgDABCC67ryeoOfHOa6rtyAq+KiYl122WW6+uqrK4NpxSnmoY4Op6amaty4cXrttde0Zs0aXXTRRfL5fJXLPQn/++853KPMVa/XDtanWbNm+s1vfqPPP/9cixYt0oABA6pt26HXmFf9+zfffKMzzzxTixcvJnwDABABgjcAACHUFjADgYCKS4o1fsJ4zZ8/v/Lxw01oNnLkSK1atUrPPvusBg4cKI/HU21StLoSKoj7fD6dffbZWrFihRYuXKjevXtXnoJe2/YWFhZq8uTJuueeeyRyNwAARgjeAAAEEQgEal1eXl6uiRMnaunSpZJU7frpYKHb6/Xq9ddf10svvaSePXuGbFcXwllvcnKyxowZozfeeEMPPvhgjT7BQnhpaaluuukm3Xf/fXVWKwAAjQHBGwCAQ1SE6FCneZeWlmr06NF66aWXVF5eHvJIccVp2VdccYX279+vvLw8eb3emE5SduhR8IyMDF155ZUqLS1VdnZ2tbqCnVbuOI5uuOEG3XvvvRHN2g4AQGPErOYAYuY///mPUfvdu3erRYsWRn1OPPFEo/b33HPPD6fSWjRq1CjddtttRn1atmxpqZr/+dvf/qZWrVqF3b558+YWq/nBSSedpDlz5hj16dOnzxGN2b59e61Zsybk9lUE6WXLloU8PbvisRYtWujxxx/X6NGj43428EAgoO3btuv2X9+uu+++W6WlpUHbVWzbLbfcouzsbJ1//vmSgh9l/89//qO8vLyQ66or48ePN2qfk5OjxYsXG/UpKChQ06ZNw26flJRktP5I+P1+62NE8rq9+uqrNWnSpLDbV51IEAAaKoI3gJg54YQTYl1CTHTo0CEut71Pnz5q165drMuopm3btlHdVwkJCXriiSdq/VLh1ltv1RNPPFHrNdGO46hHjx567rnn1L17d1vl1qmKidbuuOMOHXfccbrsssuUn58fsn1paal+/vOfq0uXLhowYEDQNgMGDNC0adP029/+1krNkUpJSYnL96CpUBP/xVpubm6D2L8AUJf4ihEAgP86//zzNXTo0JDLX3jhBc2cOVNS8GugK8J4z549teL1FfUmdB9q/PjxWrZsmdLS0kIejXQcR0VFRTrjjDO0b9++oKedezwe3XzzzZX3GAcAoLEieAMAIKlp06Z67LHHQp5au3nzZk2dOrXWdbiuq8GDB+vtt99W5lGZNsq0ruLLgwEDBujDDz+sdcZ1v9+vvXv3auDAgSFvM5aRkaHHHnvMZskAAMQ9gjcAAPrhaHZycnKNx13XVUlJic4991x9//33ta5j6NCh+sfSfyg9PT3ur+muTUXtxxxzjDZu3KhmzZrV2v6zzz7Tr371K0nBzwQ49dRTNWLEiLovFACAeoLgDQBo9HJzc3XKKadIqjmZlOu6euihh/Tuu+/WOnv5gP4D9Ne//lVp6WnW640W13XVtm1bvfrqq8rKyqp1Eqw5c+bovXffq/F4xezpTz/9dNAvNgAAaAwI3gCARs3j8eihhx6Sz+erdh/uip+tW7fq17/+da3raNmypZ597tnDHhmubyr2R58+fTRnzhz5fL7KZYd+CVFSUqLLf365iouLg64rKytLF198sb1iAQCIYwRvAECjduKJJ2r48OFBl7muq4suukjff/99jftfV/z4fD698sorOuaYY+r16eWHM2HCBN1yyy21tnnnnXf05JNPBl3mOI5mzJhR6zXjAAA0VARvAECj9otf/CLoPZdd19V7772nV199tdZAPXv2bPXs2dNmiXHBcRzdeuutatGiRcg2gUBAM2bMCHnUOzs7WxdeeKGlCgEAiF8EbwBAo9W+fXuNHj065PLTTz+91uua+/Xrp8svv9zoSHdhYaHmz5+vkSNHasSIERo2bJguu+wyffXVV0a1R1PF0X2Px6OdO3dWO+X8UPv27dOsWbNCznL+i1/8Im7vPw0AgC0EbwBAozVt2jQlJiYGXfbKK6/ou+++q/z3oSEyNTVVjzzySGUIDTXxWtX+mzdv1oABA3TJJZfon//8p5YvX67XXntNjz/+uPLy8lRUVHSEW2Sf4zi67777Kv9+6J+BQEC//vWvVVBQIKnmfunatatOPPHEKFYMAEDsEbwBAI2Sx+PRpEmTgi7z+/26+eab5bquAoGAXNetcVT7Zz/7mfr27Rv2ePv27dOIESP06aefKhAI1Fi+Y8cOPfPMM4cN8LHmuq4uuOACdevWTdL/7vtddf8kJCTUCOdVl11//fUN+np4AAAO5eQsnBrf/8M3QFvGzY91CUC9FI1f1I866ij169fPqE95ebnRhFHLly83LUtDhgwJeWQ2mC1btig3N9doDNO6Jk2apKefftqoj+lz2KNHD23YsMGoT7j3ix4wYIBmzpwZdNnqVas1ZOgQlZWVVQvCFZOppaena8OGDWrVqlXQUB5MXl6eVq5cWWubVq1aadvWbfIkxP/34v/4xz905plnVvsSoSKES1Lz5s317bffBu178OBBjR8/XqWlpTWWffLJJ5WhPlyRvKfiUffu3dWmTZuw22dm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u320gpptw4YN0/Tp0436lJSUKCkpKez2GzduVIcOHYzGMHnOExMT9dlnn6l9+/Y1lrmuq1tuuUW/+93vQj5nrutq586dys7ONqrRtk2bNunxxx/X+vXrtWXLFhUXF8vj8ah58+Zq3bq1zjnnHI07b5x8ib7KPlW/XKjNlClTtGDBgspwX9Gnor/P59OHH34YMnh/9dVX+uqrr0KuPyMjQwMHDjTZ3Ki8p5566ilNnjw57Pbx+j6/4oorNGbMmLDbR+Mz1OfzqbS01KhPJPs3WncjAOJd7qKLYl1CoxR8qlEAiEMjRoyIdQmoonXr1vX+OSktLdVf//pXTZs2Lejy2267Tffee2/Imbuzs7PVtGlTmyVGJDc3V7/5zW8qj0pXTBRX7i9XgjdBgUCgxuRxtQWZilC9bNky/fnPfw4aYCrODLj00ktDhm5J6tixozp27BjJZqEOHHvssXH3vq1tIkMAaCgI3gCARm3dunVBH3ccR6WlpSorK6v2WFWnnnqqvAnx919pRZA5NNAkeBOCPn44juPo448/1gUXXKDy8vKgId11XbVs2VK//OUvI6waAICGi68YAQCNWm2zl7///vvyer3Vrn2W/nd095xzzpHXF3/Buy65rqv9+/drypQp2rlzZ8jQ7fF4NGvWLLVq1SoGVQIAEN8I3gCARq1fv34hl915550qLy+v8XggEFBqaqoGDRpks7SYc11XxcXFGjZsmN57772Q7Twej0477TRdcMEFXEcLAEAQDftregAAauE4jvr37x9yecVp6MEmHuvcubMyMzOt1hcrFdtbUlKikSNHhjwdX5ISEhLUpEkTPf/885Lid1IxAABiiSPeAIBGKz09XTk5OUGXbdu2TQcOHAh6f2zHcfSjH/1IaWlpUakzmipCd35+vn784x9rxYoVh23/l7/8RampqUGXc79uAAAI3gCARqx3795q0qRJjcf9ZX4tXLiw2mzmVY/kejwe/WjYjxQIBBrcqdWO42j79u0aOXKkXnvttcO2nz17toYPHx7ySPfOnTvrukQAAOodgjcAoNE699xzgz6e4E2ocd/4qgE7PT1d/Qf0b1C3QarYvg0bNqh///5avXp1rV8quK6ryy+/XNdcc03I0L1jxw6tX7/eSr0AANQnDec3BgAADI0ePTro42VlZVq9enW1x6qGy759+1bOht5QrmkuLy/X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"""

def _render_suggestion_expander():
    # Read config from Streamlit secrets or environment variables
    try:
        _suggest_conf = dict(st.secrets.get("SUGGEST", {}))
    except Exception:
        _suggest_conf = {}

    _wa_link = (
        _suggest_conf.get("whatsapp_link")
        or _os.environ.get("SUGGEST_WA_LINK")
        or _DEFAULT_WA_LINK
    )

    _qr_src = (
        _suggest_conf.get("qr_image_url")
        or _os.environ.get("SUGGEST_QR_URL")
        or "assets/whatsapp_qr.png"  # optional local file in repo
    )

    # Sidebar bottom anchoring
    st.sidebar.markdown("""
    <style>
    [data-testid="stSidebar"] div.block-container {{display:flex; flex-direction:column; height:100%;}}
    .sb-bottom {{margin-top:auto;}}
    .sb-bottom .st-expander {{ border: 1px solid #4444; border-radius: 10px; }}
    </style>
    """, unsafe_allow_html=True)

    st.sidebar.markdown('<div class="sb-bottom">', unsafe_allow_html=True)
    exp = st.sidebar.expander("💡 שלח הצעת ייעול", expanded=False)
    with exp:
        st.caption("אפשר להצטרף לקבוצת הוואטסאפ או לסרוק QR מהטלפון")

        # Try to render QR from URL or local file; if missing, use embedded base64 fallback
        _qr_rendered = False
        if isinstance(_qr_src, str) and len(_qr_src) > 0:
            try:
                st.image(_qr_src, caption="סרוק/י להצטרפות", use_column_width=True)
                _qr_rendered = True
            except Exception:
                _qr_rendered = False

        if not _qr_rendered and _DEFAULT_QR_B64.strip():
            try:
                _qr_bytes = _base64.b64decode(_DEFAULT_QR_B64)
                st.image(_qr_bytes, caption="סרוק/י להצטרפות", use_column_width=True)
                _qr_rendered = True
            except Exception:
                pass

        if _wa_link:
            st.link_button("פתח וואטסאפ", _wa_link, use_container_width=True)
        else:
            st.info("מנהל/ת: יש להגדיר SUGGEST.whatsapp_link ב-Secrets או משתני סביבה.")

    st.sidebar.markdown('</div>', unsafe_allow_html=True)

# Render at end of script (safe no-op if st not ready earlier)
try:
    _render_suggestion_expander()
except Exception as _e:
    try:
        st.sidebar.info("שגיאה בהצעת ייעול: " + str(_e))
    except Exception:
        pass
# =========================
