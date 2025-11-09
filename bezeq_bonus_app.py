
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
    db = load_users()
    user = db["users"].get(email.lower().strip())
    if not user:
        return False, "משתמש לא נמצא."
    if not check_password(password, user["password"]):
        return False, "סיסמה שגויה."
    return True, user

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
    df_p = df_p.reindex(idx, fill_value=0)
    return df_p

st.set_page_config(page_title="ברדק • בונוס מכירות – מוקד תמיכה", page_icon="📊", layout="wide")

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

    st.markdown("### ⚙️ לוח בקרה")
    st.session_state.theme_light = st.toggle("מצב Light", value=st.session_state.get("theme_light", True))

    if st.session_state.user:
        with st.popover("פרופיל והגדרות", use_container_width=True):
            st.caption("עריכת פרופיל, צבע, יעדים והרשאות נראות בצוות")
            user = st.session_state.user
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input("שם עובד", value=user.get("name",""))
                new_team = st.text_input("צוות", value=user.get("team",""))
                invisible = st.checkbox("בלתי נראה בדשבורד צוותי", value=user.get("invisible", False))
                color = st.color_picker("צבע משתמש", value=user.get("color", "#4F46E5"))
            with col2:
                daily_goal = st.number_input("יעד יומי (₪)", min_value=0, step=10, value=int(user.get("goals",{}).get("daily",0)))
                weekly_goal = st.number_input("יעד שבועי (₪)", min_value=0, step=10, value=int(user.get("goals",{}).get("weekly",0)))
                monthly_goal = st.number_input("יעד חודשי (₪)", min_value=0, step=10, value=int(user.get("goals",{}).get("monthly",0)))
                st.text_input("הרשאה", value=("אדמין" if user.get("is_admin") else "משתמש"), disabled=True)
            if st.button("שמירת פרופיל", use_container_width=True):
                ok, msg = update_user(
                    user["email"],
                    invisible=bool(invisible),
                    color=str(color),
                    goals={"daily": int(daily_goal), "weekly": int(weekly_goal), "monthly": int(monthly_goal)},
                    name=new_name,
                    team=new_team,
                )
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
                    delete_user(st.session_state.user["email"])
                    st.success("המשתמש נמחק. מתנתק...")
                    st.session_state.user = None
                    st.rerun()
                else:
                    st.error("יש לאשר את תיבת הסימון לפני מחיקה.")

        st.markdown("---")
        if st.button("התנתקות", use_container_width=True):
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
st.title("📊 ברדק • מערכת בונוסים למוקד תמיכה")

def view_auth():
    tab_login, tab_register = st.tabs(["התחברות", "הרשמה"])
    with tab_login:
        st.subheader("כניסה למערכת")
        email = st.text_input("אימייל", key="login_email")
        pwd = st.text_input("סיסמה", type="password", key="login_pwd")
        if st.button("התחברות"):
            ok, res = authenticate(email, pwd)
            if ok:
                st.session_state.user = res
                st.success(f"מחובר כעת: {res['name']} ({res['team']})")
                st.rerun()
            else:
                st.error(res)
    with tab_register:
        st.subheader("הרשמה לעובדים")
        name = st.text_input("שם מלא", key="reg_name")
        email = st.text_input("אימייל", key="reg_email")
        team = st.text_input("צוות", key="reg_team", placeholder="למשל: חיפה, דרום, ירושלים...")
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
        import altair as alt
        chart = (alt.Chart(to_plot.reset_index().melt(id_vars=to_plot.index.name, var_name="משתמש", value_name="בונוס"))
                 .encode(
                    x=alt.X(f"{to_plot.index.name}:T" if to_plot.index.name=="תאריך" else f"{to_plot.index.name}:O", title=to_plot.index.name),
                    y=alt.Y("בונוס:Q"),
                    color=alt.Color("משתמש:N")
                 ).mark_line())
        st.altair_chart(chart, use_container_width=True)
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
            with st.expander(f"✏️ {u.get('name','ללא שם')}  •  {u.get('email','')}  •  צוות {u.get('team','לא מוגדר')}"):
                col1, col2 = st.columns(2)
                with col1:
                    new_name = st.text_input("שם", value=u.get("name",""), key=f"name_{u['email']}")
                    new_team = st.text_input("צוות", value=u.get("team",""), key=f"team_{u['email']}")
                    new_invis = st.checkbox("בלתי נראה בדשבורד צוותי", value=u.get("invisible", False), key=f"invis_{u['email']}")
                    new_color = st.color_picker("צבע משתמש", value=u.get("color", "#4F46E5"), key=f"color_{u['email']}")
                with col2:
                    goals = u.get("goals",{})
                    g_d = st.number_input("יעד יומי (₪)", min_value=0, step=10, value=int(goals.get("daily",0)), key=f"gday_{u['email']}")
                    g_w = st.number_input("יעד שבועי (₪)", min_value=0, step=10, value=int(goals.get("weekly",0)), key=f"gweek_{u['email']}")
                    g_m = st.number_input("יעד חודשי (₪)", min_value=0, step=10, value=int(goals.get("monthly",0)), key=f"gmonth_{u['email']}")
                    st.text_input("סטטוס", value=("אדמין" if u.get("is_admin") else "משתמש"), disabled=True, key=f"role_{u['email']}")

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

    
