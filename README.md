
# Bezeq Bonus – Streamlit App

Modern, real-time sales & bonus tracking portal built with **Streamlit**, **Firebase/Firestore**, and **GitHub-based deployment**.  
Supports user registration/login, personal & team dashboards, admin tools, JSON data import/export, and a **WhatsApp “Improvement Suggestion”** expander with QR + deep link.

---

## Table of Contents
- [Live Demo](#live-demo)
- [Features](#features)
- [Screenshots](#screenshots)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
  - [Option A: Streamlit Cloud](#option-a-streamlit-cloud)
  - [Option B: Local--Server-UbuntuWindows](#option-b-local--server-ubuntuwindows)
- [Configuration](#configuration)
  - [Secrets / .env](#secrets--env)
  - [Firebase / Firestore](#firebase--firestore)
  - [WhatsApp Suggestion Expander](#whatsapp-suggestion-expander)
- [Data Files](#data-files)
- [Admin Panel](#admin-panel)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Security Checklist](#security-checklist)
- [Contributing](#contributing)
- [License](#license)

---

## Live Demo
> Add your Streamlit Cloud URL here once deployed.  
> Example: `https://bezeq-bonus.streamlit.app/`

---

## Features
- **User Auth**: Email-based login/registration with profile management.
- **Personal Dashboard**: Daily / weekly / monthly performance, charts, and metrics.
- **Team Dashboard**: Aggregated KPIs with sortable/filterable tables.
- **Admin Tools**: Manage users, roles, data files (bonuses/messages/records), system notices.
- **Data Storage**: Firestore collections; JSON helpers for local development/import/export.
- **WhatsApp Suggestion Expander**: Bottom-anchored sidebar button to submit improvement ideas  
  (opens WhatsApp Web on desktop or the app on mobile; shows QR for quick join).
- **Right-to-Left (RTL) Ready**: Hebrew layout/texts supported.
- **GitHub-first Workflow**: App updates via pull requests; Streamlit Cloud auto-deploy.

---

## Screenshots
> Replace with real images/GIFs from your running app.

- Sidebar & Admin badge  
  `docs/screenshots/sidebar_admin.png`

- Team dashboard with charts  
  `docs/screenshots/team_dashboard.png`

- Suggestion expander (QR + link)  
  `docs/screenshots/suggestion_popover.png`

---

## Architecture
```
Streamlit UI  ─────┐
                   ├── Firestore (users, bonuses, messages, records)
Helper scripts  ───┘
Local JSON (dev only)  → import/export via upload_json_to_firestore.py
Secrets / ENV → Firebase credentials, WhatsApp config, etc.
```

---

## Tech Stack
- **Frontend/Backend**: Streamlit (Python 3.10+)
- **Database**: Firebase Firestore
- **Auth & Secrets**: Streamlit Secrets (Cloud) / .env (server)
- **CI/CD**: Streamlit Cloud (or your own runner)
- **Data**: JSON mirrors for dev & bootstrapping

---

## Quick Start

### Option A: Streamlit Cloud
1. **Fork/Clone** this repo to your GitHub.
2. Go to **streamlit.io → Deploy an app → Connect GitHub repo**.
3. **App file**: `bezeq_bonus_app.py` (or your preferred entry point).
4. **Secrets** → paste your config (see [Secrets / .env](#secrets--env)).
5. Click **Deploy**.

### Option B: Local / Server (Ubuntu/Windows)
```bash
# Python 3.11+ recommended
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# (optional) set env vars; or use .streamlit/secrets.toml
export SUGGEST_WA_LINK="https://chat.whatsapp.com/...."

# Run
streamlit run bezeq_bonus_app.py
```
> To expose publicly on a server: `streamlit run bezeq_bonus_app.py --server.port 8501 --server.address 0.0.0.0` and put it behind **Nginx/Caddy** with HTTPS.

---

## Configuration

### Secrets / .env
Prefer **Streamlit Secrets** on Cloud. Locally, you can also use env variables.

`.streamlit/secrets.toml`:
```toml
[firebase]
project_id = "YOUR_PROJECT_ID"
# If using a service account JSON, do NOT paste it here. Use environment variable or a secure mount.

[SUGGEST]
# WhatsApp group deep link
whatsapp_link = "https://chat.whatsapp.com/XXXXXXXXXXXXXX"
# Optional: direct URL for the QR image (CDN). If empty, the app will try assets/whatsapp_qr.png
qr_image_url  = ""
```

`.env` (optional for self-hosted):
```bash
SUGGEST_WA_LINK="https://chat.whatsapp.com/XXXXXXXXXXXXXX"
# SUGGEST_QR_URL="https://raw.githubusercontent.com/<user>/<repo>/main/assets/whatsapp_qr.png"
```

> **Never commit real service account keys to Git!**  
> Use Streamlit Secrets or a secure secret manager (GitHub Actions secrets, Docker secrets, etc.)

### Firebase / Firestore
- Create a Firebase project and enable **Firestore in Native mode**.
- Use the **service account JSON** privately on your server, or a custom token strategy.  
- When you see `The query requires an index` errors, open the provided Firebase console link and **create the composite index** suggested by Firestore.

### WhatsApp Suggestion Expander
- Button appears at the **bottom of the sidebar** under “Logout”.
- On click, an **expander** opens with:
  - A **QR code** (from `SUGGEST.qr_image_url`, or local `assets/whatsapp_qr.png`, or built-in fallback).
  - **Link button** to open WhatsApp Web/app (`SUGGEST.whatsapp_link`).
- To replace the QR image, add your own `assets/whatsapp_qr.png` or set `qr_image_url` in secrets.

---

## Data Files
Local JSONs for development / bootstrapping:
```
bonuses.json
messages.json
records.json
users.json
```
Helper:
```
upload_json_to_firestore.py   # import your JSONs into Firestore safely
```
> In production, Firestore is the source of truth. JSONs are for local workflows and initial import.

---

## Admin Panel
- Admin users see additional sidebar sections (user management, system notices, data controls).
- Admin status can be stored in Firestore (e.g., `users` collection `role = "admin"`) or a JSON bootstrap during development.

---

## Deployment

**Streamlit Cloud**
- Push to `main` (or the branch configured) → auto-deploy.
- Manage secrets in the app settings panel.

**Self-Hosted (Ubuntu)**
```bash
# Install system deps
sudo apt update && sudo apt install -y python3-venv

# App
git clone https://github.com/<you>/<repo>.git
cd repo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# (optional) set env; or create .streamlit/secrets.toml
export SUGGEST_WA_LINK="https://chat.whatsapp.com/XXXXXXXXXXXXXX"

# Run
streamlit run bezeq_bonus_app.py --server.port 8501 --server.address 0.0.0.0
```
> Put Streamlit behind **Nginx**/**Caddy** with SSL (Let’s Encrypt) for public access.

---

## Troubleshooting
**Firestore “requires an index” (400 FailedPrecondition)**  
- Follow the console link shown in the error to **create a composite index** for the exact fields in your query.

**I don’t see the “Suggestion” button**  
- Ensure you’re running the latest app file that includes the expander code.
- Confirm secrets/env values are set; if not, the control still appears with guidance.
- If using assets, make sure `assets/whatsapp_qr.png` exists in the repo and is referenced correctly.

**Service account / PEM errors**  
- Do **not** paste PEM into secrets incorrectly. Keep the **full JSON** on the server and point to it securely (e.g., `GOOGLE_APPLICATION_CREDENTIALS=/secure/path/key.json`).  
- On Cloud, use Streamlit Secrets to store structured values (but avoid the raw service account file when possible).

**Duplicate Streamlit keys / rerun changes**  
- Ensure elements have unique `key=` if dynamically created.
- Use `st.rerun()` (newer) instead of deprecated `st.experimental_rerun()`.

---

## Security Checklist
- ☐ **Never commit** `firebase_service_account.json` publicly.  
- ☐ Restrict Firestore rules (read/write) to authenticated users & least privilege.  
- ☐ Validate/clean any user-provided content.  
- ☐ Rotate keys regularly.  
- ☐ Use HTTPS for public deployments.  

---

## Contributing
Pull requests are welcome. For big changes, open an issue to discuss what you’d like to change.  
Please ensure PRs are well-scoped and include tests or screenshots when UI is affected.

---

## License
MIT — see `LICENSE` (or update to your preferred license).

---

### Badges (optional)
Add shields.io badges once public:
```
[![Streamlit App](https://img.shields.io/badge/Streamlit-Live-green)](YOUR_APP_URL)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Firebase](https://img.shields.io/badge/Firebase-Firestore-orange)](#)
```
