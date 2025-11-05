# bezeq_bonus_app_version 2.py
# -*- coding: utf-8 -*-
import json, csv, io, sys, subprocess, random
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

# --- Ensure required packages (pandas REQUIRED) ---
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

APP_TZ = ZoneInfo("Asia/Jerusalem")
DATA_DIR = Path("data")
USERS_PATH = DATA_DIR / "users.json"
RECORDS_PATH = DATA_DIR / "records.json"

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

# ---------------- Storage ----------------
def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)
    if not USERS_PATH.exists():
        USERS_PATH.write_text(json.dumps({"users": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
    if not RECORDS_PATH.exists():
        RECORDS_PATH.write_text(json.dumps({"records": []}, ensure_ascii=False, indent=2), encoding="utf-8")

def load_users():
    ensure_files()
    with open(USERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(data):
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_records():
    ensure_files()
    with open(RECORDS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_records(data):
    with open(RECORDS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------------- Auth ----------------
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

# ---------------- Time helpers ----------------
def now_ij():
    return datetime.now(APP_TZ)

def week_bounds(d: date):
    weekday = (d.weekday() + 1) % 7  # Sunday=0
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

# ---------------- Users ----------------
def _random_hex_color(existing: set[str]):
    # generate distinct-ish colors
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
        # Admin flag is set only via JSON edit, not via UI
        "is_admin": False
    }

def register_user(name, email, password, team, invisible):
    db = load_users()
    email_l = email.lower().strip()
    if email_l in db["users"]:
        return False, "האימייל כבר רשום במערכת."
    db["users"][email_l] = new_user_payload(name, email_l, password, team, invisible)
    save_users(db)
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
    db = load_users()
    user = db["users"].get(email.lower().strip())
    if not user:
        return False, "משתמש לא נמצא."
    if "is_admin" in fields:  # not allowed from UI
        fields.pop("is_admin")
    user.update(fields)
    db["users"][email.lower().strip()] = user
    save_users(db)
    return True, "עודכן בהצלחה."

def delete_user(email):
    dbu = load_users()
    dbr = load_records()
    if email in dbu["users"]:
        dbu["users"].pop(email, None)
        save_users(dbu)
    dbr["records"] = [r for r in dbr["records"] if r["email"] != email]
    save_records(dbr)
    return True

# ---------------- Records ----------------
def add_or_set_counts(email: str, d: date, counts: dict):
    db = load_records()
    date_s = d.isoformat()
    db["records"] = [r for r in db["records"] if not (r["email"] == email and r["date"] == date_s)]
    ts = now_ij().isoformat()
    for code, qty in counts.items():
        if int(qty) > 0:
            db["records"].append({"email": email, "date": date_s, "product": code, "qty": int(qty), "ts": ts})
    save_records(db)

def get_counts_for_user_date(email: str, d: date):
    db = load_records()
    date_s = d.isoformat()
    out = {p["code"]: 0 for p in PRODUCTS}
    for r in db["records"]:
        if r["email"] == email and r["date"] == date_s:
            out[r["product"]] = out.get(r["product"], 0) + int(r["qty"])
    return out

def aggregate_user(email: str, start_d: date, end_d: date):
    db = load_records()
    out = {p["code"]: 0 for p in PRODUCTS}
    for r in db["records"]:
        if r["email"] == email and start_d.isoformat() <= r["date"] <= end_d.isoformat():
            out[r["product"]] = out.get(r["product"], 0) + int(r["qty"])
    return out

def compute_bonus(counts: dict) -> int:
    total = 0
    for code, qty in counts.items():
        b = PRODUCT_INDEX.get(code, {}).get("bonus", 0)
        total += int(qty) * int(b)
    return total

def team_members(team: str):
    db = load_users()
    return [u for u in db["users"].values() if u.get("team","").strip() == team.strip()]

def team_visible_members(team: str):
    return [m for m in team_members(team) if not m.get("invisible")]

def team_aggregate(team: str, start_d: date, end_d: date, include_invisible=False):
    members = team_members(team) if include_invisible else team_visible_members(team)
    emails = [m["email"] for m in members]
    totals = {}
    for e in emails:
        totals[e] = aggregate_user(e, start_d, end_d)
    return members, totals

# ---------------- UI skin/RTL ----------------
def inject_base_css():
    st.markdown("""
    
    <style>
    :root { --sidebar-width: 18rem; }
    [data-testid="stSidebar"]{
        left: auto !important;
        right: 0 !important;
        border-left: 1px solid #1f2937 !important;
        border-right: none !important;
        width: var(--sidebar-width) !important;
        z-index: 100;
    }
    [data-testid="stSidebarCollapsedControl"]{
        right: 0.25rem !important;
        left: auto !important;
    }
    [data-testid="stSidebar"][aria-expanded="true"] ~ div [data-testid="stAppViewContainer"]{
        padding-right: calc(var(--sidebar-width) + 1rem) !important;
    }
    [data-testid="stSidebar"][aria-expanded="false"] ~ div [data-testid="stAppViewContainer"]{
        padding-right: 1rem !important;
    }
    html, body { overflow-x: hidden; }
    .user-badge-side{ display:flex; align-items:center; justify-content:space-between; gap:.75rem; padding:.25rem .25rem .75rem 0; }
    .user-badge-side .dot{ width:16px; height:16px; border-radius:999px; display:inline-block; }
    .user-badge-side .u-text{ font-weight:700; font-size:1.05rem; display:flex; align-items:center; gap:.5rem; }
    .role-badge{ font-size:.72rem; font-weight:700; padding:.15rem .45rem; border-radius:999px; background:#f59e0b1a; border:1px solid #f59e0b55; color:#f59e0b; }
    </style>

    """, unsafe_allow_html=True)

def begin_skin(light: bool):
    klass = "light app-skin" if light else "app-skin"
    st.markdown(f'<div class="{klass}">', unsafe_allow_html=True)

def end_skin():
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- Charts helpers ----------------
def build_team_timeseries(team: str, period: str) -> pd.DataFrame:
    members = team_visible_members(team)
    if not members:
        return pd.DataFrame()
    email_to_name = {m["email"]: m["name"] for m in members}
    recs = load_records()["records"]
    today = now_ij().date()
    rows = []
    if period == "היום":
        target = today.isoformat()
        for r in recs:
            if r["email"] in email_to_name and r["date"] == target:
                try:
                    ts = datetime.fromisoformat(r["ts"]).astimezone(APP_TZ)
                    hour = ts.hour
                except Exception:
                    hour = 0
                bonus = int(r["qty"]) * int(PRODUCT_INDEX[r["product"]]["bonus"])
                rows.append({"bucket": hour, "email": r["email"], "bonus": bonus})
        idx = pd.Index(range(24), name="שעה")
    elif period == "שבוע נוכחי":
        start_d, end_d = week_bounds(today)
        for r in recs:
            if r["email"] in email_to_name and start_d.isoformat() <= r["date"] <= end_d.isoformat():
                d = date.fromisoformat(r["date"])
                bonus = int(r["qty"]) * int(PRODUCT_INDEX[r["product"]]["bonus"])
                rows.append({"bucket": d, "email": r["email"], "bonus": bonus})
        idx = pd.Index([start_d + timedelta(n) for n in range((end_d-start_d).days+1)], name="תאריך")
    else:
        start_d, end_d = month_bounds(today)
        for r in recs:
            if r["email"] in email_to_name and start_d.isoformat() <= r["date"] <= end_d.isoformat():
                d = date.fromisoformat(r["date"])
                bonus = int(r["qty"]) * int(PRODUCT_INDEX[r["product"]]["bonus"])
                rows.append({"bucket": d, "email": r["email"], "bonus": bonus})
        idx = pd.Index([start_d + timedelta(n) for n in range((end_d-start_d).days+1)], name="תאריך")
    if not rows:
        return pd.DataFrame(index=idx)
    df = pd.DataFrame(rows).groupby(["bucket","email"], as_index=False)["bonus"].sum()
    df_p = df.pivot_table(index="bucket", columns="email", values="bonus", aggfunc="sum").fillna(0)
    df_p = df_p.reindex(idx, fill_value=0)
    df_p.index.name = "תאריך" if isinstance(df_p.index[0], (pd.Timestamp, date)) else "שעה"
    df_p = df_p.rename(columns=email_to_name)
    return df_p

def build_personal_timeseries(email: str, start_d: date, end_d: date) -> pd.DataFrame:
    recs = load_records()["records"]
    rows = []
    if start_d == end_d:
        for r in recs:
            if r["email"] == email and r["date"] == start_d.isoformat():
                try:
                    ts = datetime.fromisoformat(r["ts"]).astimezone(APP_TZ)
                    bucket = ts.hour
                except Exception:
                    bucket = 0
                bonus = int(r["qty"]) * int(PRODUCT_INDEX[r["product"]]["bonus"])
                rows.append({"bucket": bucket, "bonus": bonus})
        idx = pd.Index(range(24), name="שעה")
    else:
        for r in recs:
            if r["email"] == email and start_d.isoformat() <= r["date"] <= end_d.isoformat():
                bucket = date.fromisoformat(r["date"])
                bonus = int(r["qty"]) * int(PRODUCT_INDEX[r["product"]]["bonus"])
                rows.append({"bucket": bucket, "bonus": bonus})
        idx = pd.Index([start_d + timedelta(n) for n in range((end_d-start_d).days+1)], name="תאריך")
    if not rows:
        return pd.DataFrame(index=idx, data={"בונוס": [0]*len(idx)})
    df = pd.DataFrame(rows).groupby("bucket", as_index=True)["bonus"].sum()
    df = df.reindex(idx, fill_value=0).to_frame(name="בונוס")
    return df

def altair_team_chart(df: pd.DataFrame, team: str):
    if df.empty:
        return None
    long = df.reset_index().melt(id_vars=df.index.name, var_name="משתמש", value_name="בונוס")
    members = team_visible_members(team)
    name_to_color = {m["name"]: m.get("color", "#4F46E5") for m in members}
    domain = list(df.columns)
    range_colors = [name_to_color.get(name, "#4F46E5") for name in domain]
    x_field = df.index.name
    base = alt.Chart(long).encode(
        x=alt.X(f"{x_field}:T" if x_field=="תאריך" else f"{x_field}:Q", title=x_field),
        y=alt.Y("בונוס:Q", title="בונוס (₪)"),
        color=alt.Color("משתמש:N", scale=alt.Scale(domain=domain, range=range_colors), legend=alt.Legend(title="משתמש"))
    ).properties(width="container")
    line = base.mark_line(point=False)
    points = base.transform_filter(alt.datum.בונוס > 0).mark_circle(size=60, opacity=1)
    return (line + points)

def altair_personal_chart(df: pd.DataFrame, color: str):
    if df.empty:
        return None
    long = df.reset_index().rename(columns={df.index.name:"bucket"})
    x_type = "T" if df.index.name=="תאריך" else "Q"
    chart = alt.Chart(long).mark_line(point=True, color=color).encode(
        x=alt.X(f"bucket:{x_type}", title=df.index.name),
        y=alt.Y("בונוס:Q", title="בונוס (₪)")
    ).properties(width="container")
    return chart

# ---------------- App ----------------
st.set_page_config(page_title="בזק • בונוס מכירות – מוקד תמיכה", page_icon="📊", layout="wide")
inject_base_css()

if "theme_light" not in st.session_state:
    st.session_state.theme_light = True
if "user" not in st.session_state:
    st.session_state.user = None

with st.sidebar:
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
    </style>
    """, unsafe_allow_html=True)

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
                    st.error("נא למלא את כל שדות הסיסמה.")
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
    else:
        st.info("התחבר/י כדי לראות הגדרות.")

begin_skin(st.session_state.theme_light)

st.title("📊 בזק • מערכת בונוסים למוקד תמיכה")

# -------- Auth Views --------
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

# Top badge
badge_html = f"""
<div style="display:flex; justify-content:flex-end; align-items:center; gap:.75rem; padding:.25rem 0;">
  <div style="font-size:1.1rem; font-weight:700;">{user['name']} &middot; צוות {user['team']}</div>
  <span class="dot" style="width:14px;height:14px;background:{user.get('color','#4F46E5')};display:inline-block;border-radius:999px;"></span>
</div>
"""
st.markdown(badge_html, unsafe_allow_html=True)

# -------- Tabs --------
tabs = ["היום", "תיקונים / היסטוריה", "דשבורד צוותי", "דוחות וייצוא"]
if user.get("is_admin"):
    tabs.append("ניהול משתמשים (אדמין)")
tab_today, tab_prev, tab_team, tab_reports, *maybe_admin = st.tabs(tabs)

with tab_today:
    st.subheader("הזנת מכירות להיום")
    today = now_ij().date()
    counts = get_counts_for_user_date(user["email"], today)

    form = st.form("today_form")
    cols = form.columns(3)
    fields = {}
    for i,p in enumerate(PRODUCTS):
        col = cols[i % 3]
        fields[p["code"]] = col.number_input(f"{p['name']} (בונוס {p['bonus']}₪)", min_value=0, step=1, value=int(counts.get(p["code"],0)))
    if form.form_submit_button("שמירה להיום"):
        add_or_set_counts(user["email"], today, {k:int(v) for k,v in fields.items()})
        st.success("הנתונים נשמרו להיום!")

    counts_today = get_counts_for_user_date(user["email"], today)
    bonus_today = compute_bonus(counts_today)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("בונוס היום (₪)", bonus_today)
    c2.metric("סה\"כ פריטים", sum(counts_today.values()))
    g = user.get("goals", {})
    c3.metric("התקדמות מול יעד יומי", f"{int((bonus_today/max(1,g.get('daily',1)))*100)}%") if g.get("daily", 0) else c3.metric("התקדמות מול יעד יומי", "—")
    yest = today - timedelta(days=1)
    c4.metric("אתמול (₪)", compute_bonus(get_counts_for_user_date(user["email"], yest)))

with tab_prev:
    st.subheader("תיקונים וצפייה בהיסטוריה")
    sel_date = st.date_input("בחר תאריך", value=now_ij().date(), max_value=now_ij().date())
    existing = get_counts_for_user_date(user["email"], sel_date)
    form2 = st.form("edit_form")
    cols = form2.columns(3)
    fields2 = {}
    for i,p in enumerate(PRODUCTS):
        col = cols[i % 3]
        fields2[p["code"]] = col.number_input(f"{p['name']} (בונוס {p['bonus']}₪)", min_value=0, step=1, value=int(existing.get(p["code"],0)))
    if form2.form_submit_button("שמירה לתאריך זה"):
        add_or_set_counts(user["email"], sel_date, {k:int(v) for k,v in fields2.items()})
        st.success("הנתונים נשמרו לתאריך שנבחר.")

    today = now_ij().date()
    wk_s, wk_e = week_bounds(today)
    mo_s, mo_e = month_bounds(today)
    agg_yesterday = aggregate_user(user["email"], today - timedelta(days=1), today - timedelta(days=1))
    agg_week = aggregate_user(user["email"], wk_s, wk_e)
    agg_month = aggregate_user(user["email"], mo_s, mo_e)
    c1, c2, c3 = st.columns(3)
    c1.metric("אתמול (₪)", compute_bonus(agg_yesterday))
    c2.metric("שבוע נוכחי (₪)", compute_bonus(agg_week))
    c3.metric("חודש נוכחי (₪)", compute_bonus(agg_month))

with tab_team:
    st.subheader("דשבורד צוותי")
    st.caption("משתמשים שסימנו 'בלתי נראה' לא יוצגו כאן.")
    period = st.selectbox("טווח", ["היום", "שבוע נוכחי", "חודש נוכחי"], index=0)
    today = now_ij().date()
    if period == "היום":
        start_d = end_d = today
    elif period == "שבוע נוכחי":
        start_d, end_d = week_bounds(today)
    else:
        start_d, end_d = month_bounds(today)

    members, totals = team_aggregate(user["team"], start_d, end_d, include_invisible=False)

    # Table (no email column) + column selector
    header = ["שם", "בונוס (₪)", "סה\"כ פריטים"] + [p["name"] for p in PRODUCTS]
    rows = []
    for m in members:
        counts = totals.get(m["email"], {p["code"]: 0 for p in PRODUCTS})
        b = compute_bonus(counts)
        total_items = sum(counts.values())
        row = [m["name"], b, total_items] + [counts.get(p["code"], 0) for p in PRODUCTS]
        rows.append(row)
    if rows:
        df_table_full = pd.DataFrame(rows, columns=header)
        selected_cols = st.multiselect("בחר עמודות להצגה בטבלה", options=header, default=header, key="team_table_columns_select")
        df_table = df_table_full[selected_cols] if selected_cols else df_table_full
        st.dataframe(df_table, use_container_width=True, hide_index=True)

        buff = io.StringIO(); df_table_full.to_csv(buff, index=False, quoting=csv.QUOTE_NONNUMERIC)
        st.download_button("הורדת CSV צוותי", data=buff.getvalue().encode("utf-8-sig"),
                           file_name=f"team_{user['team']}_{start_d}_{end_d}.csv", mime="text/csv")
    else:
        st.info("אין נתונים להצגה עבור הטווח.")

    st.markdown("### 📈 גרף צוות – בונוס לפי זמן")
    df_series = build_team_timeseries(user["team"], period)
    if df_series.empty:
        st.info("אין עדיין נתונים לגרף בטווח שנבחר.")
    else:
        cumulative = st.toggle("הצג מצטבר", value=True, help="סיכום מצטבר לאורך הציר")
        to_plot = df_series.cumsum() if cumulative else df_series
        chart = altair_team_chart(to_plot, user["team"])
        if chart:
            st.altair_chart(chart, use_container_width=True)

with tab_reports:
    st.subheader("דוחות אישיים וייצוא")
    today = now_ij().date()
    colA, colB = st.columns(2)
    start_d = colA.date_input("מתאריך", value=today.replace(day=1))
    end_d = colB.date_input("עד תאריך", value=today, max_value=today)
    if start_d > end_d:
        st.warning("טווח תאריכים שגוי.")
    else:
        agg = aggregate_user(user["email"], start_d, end_d)
        b = compute_bonus(agg)
        st.markdown(f"**בונוס בטווח (₪):** {b}")
        records = load_records()["records"]
        rows = []
        for r in records:
            if r["email"] == user["email"] and start_d.isoformat() <= r["date"] <= end_d.isoformat():
                prod = PRODUCT_INDEX[r["product"]]
                rows.append({
                    "תאריך": r["date"],
                    "מוצר": prod["name"],
                    "כמות": int(r["qty"]),
                    "בונוס ליחידה": prod["bonus"],
                    "סה\"כ בונוס": int(r["qty"]) * int(prod["bonus"]),
                    "עדכון": r["ts"],
                })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values(["תאריך","מוצר"])
            st.dataframe(df, use_container_width=True, hide_index=True)
            buff = io.StringIO(); df.to_csv(buff, index=False, quoting=csv.QUOTE_NONNUMERIC)
            st.download_button("הורדת CSV אישי", data=buff.getvalue().encode("utf-8-sig"),
                               file_name=f"personal_{start_d}_{end_d}.csv", mime="text/csv")
        else:
            st.info("אין נתונים בטווח שנבחר.")

        st.markdown("### 📈 גרף אישי לטווח הנבחר")
        ts_df = build_personal_timeseries(user["email"], start_d, end_d)
        chart = altair_personal_chart(ts_df, color=user.get("color", "#4F46E5"))
        if chart:
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("אין נתונים לגרף.")

# ------------- Admin Dashboard -------------
if user.get("is_admin") and maybe_admin:
    tab_admin = maybe_admin[0]
    with tab_admin:
        st.header("👑 ניהול משתמשים (אדמין)")
        st.caption("שינוי הרשאות אדמין נעשה **רק** בעריכת הקובץ data/users.json (כדרישתך). כאן אפשר למחוק, לערוך פרופיל, לאפס סיסמה ולסנן משתמשים.")

        db = load_users()
        all_users = list(db.get("users", {}).values())

        # Filters
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

        # Export users CSV
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
            dfu = pd.DataFrame(export_rows)
            buff = io.StringIO(); dfu.to_csv(buff, index=False, quoting=csv.QUOTE_NONNUMERIC)
            st.download_button("הורדת CSV משתמשים (מסונן)", data=buff.getvalue().encode("utf-8-sig"),
                               file_name="users_filtered.csv", mime="text/csv")

        st.markdown("---")
        # Per-user editors
        for u in filtered:
            with st.expander(f"✏️ {u.get('name',' ללא שם')}  •  {u.get('email','')}  •  צוות {u.get('team','לא מוגדר')}"):
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

                # Reset password
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

                # Delete user
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

end_skin()
