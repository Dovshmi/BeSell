# 📊 BeSell — Sales & Bonus Tracking Dashboard

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Streamlit-1.38%2B-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit" />
  <img src="https://img.shields.io/badge/Pandas-2.0%2B-150458?style=for-the-badge&logo=pandas&logoColor=white" alt="Pandas" />
  <img src="https://img.shields.io/badge/Altair-5.0%2B-4B8BBE?style=for-the-badge" alt="Altair" />
  <img src="https://img.shields.io/badge/Firebase-Admin-FFCA28?style=for-the-badge&logo=firebase&logoColor=black" alt="Firebase Admin" />
  <img src="https://img.shields.io/badge/Firestore-Cloud_DB-F57C00?style=for-the-badge&logo=firebase&logoColor=white" alt="Firestore" />
  <img src="https://img.shields.io/badge/bcrypt-Password_Hashing-111827?style=for-the-badge" alt="bcrypt" />
  <img src="https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white" alt="GitHub Actions" />
  <img src="https://img.shields.io/badge/WhatsApp_Suggestions-25D366?style=for-the-badge&logo=whatsapp&logoColor=white" alt="WhatsApp Suggestions" />
  <img src="https://img.shields.io/badge/RTL-Hebrew-0F172A?style=for-the-badge" alt="RTL Hebrew" />
  <img src="https://img.shields.io/badge/License-Apache--2.0-4B5563?style=for-the-badge" alt="Apache-2.0 License" />
</div>

<div align="center">
  <p><strong>A Hebrew RTL Streamlit dashboard for tracking sales, bonuses, team performance, personal goals, and admin-managed sales data.</strong></p>
  <p>
    <a href="#getting-started"><strong>Run Locally</strong></a>
    ·
    <a href="https://github.com/Dovshmi/BeSell"><strong>GitHub Repository</strong></a>
  </p>
</div>

---

## Overview

**BeSell** is a Streamlit-based sales and bonus tracking dashboard. It is built for Hebrew RTL workflows and focuses on daily sales entry, bonus calculation, user dashboards, team visibility, admin tools, and Firebase/Firestore-backed persistence.

The app can run with Firebase Firestore as the production data layer, while also supporting local JSON files as a fallback/development mode. This makes it practical for both quick local testing and a more persistent cloud-connected deployment.

> This is an independent software project. It is not presented as an official Bezeq product or official internal system.

---

## Product Goals

- Give users a simple place to record sales and track their bonus progress.
- Show personal and team performance in a clear Hebrew RTL interface.
- Support admins with user management, messages, sales records, and bonus configuration.
- Keep Firestore as the production-ready data layer while preserving local JSON fallback for development.
- Make deployment simple through Streamlit and GitHub-based workflows.

---

## Core Features

### User Experience

- **Hebrew RTL layout** designed for right-to-left usage.
- **User registration and login** with hashed password storage.
- **Personal dashboard** for daily, weekly, and monthly sales performance.
- **Goal progress bars** for quick visual tracking against personal targets.
- **Sales entry workflow** using predefined products and bonus values.
- **Performance charts** powered by Pandas and Altair.
- **WhatsApp suggestion panel** with QR/link support for improvement ideas.

### Admin Experience

- **Admin panel** for privileged users.
- **User management** for editing profile data, permissions, and roles.
- **Bonus schedule management** for changing product bonus values over time.
- **Messages/notices** for sending updates inside the dashboard.
- **Records management** for reviewing, editing, importing, and exporting data.
- **Firebase diagnostics** to understand whether the app is running on Firestore or local JSON.

### Data Layer

- **Firestore mode** for persistent cloud-backed data.
- **Local JSON mode** for development, fallback, or offline-style testing.
- **Automatic seed files** for users, records, bonuses, and messages when local files do not exist.
- **Configurable Firebase credentials** through Streamlit secrets, environment variables, or a local service-account file.

---

## Tech Stack

| Area | Technology |
| :--- | :--- |
| App Framework | Streamlit 1.38+ |
| Language | Python 3.10+ recommended |
| Data Processing | Pandas 2.0+ |
| Charts | Altair 5.0+ |
| Database | Firebase Firestore |
| Firebase SDK | firebase-admin 6.5+ |
| Password Hashing | bcrypt 4.1+ with PBKDF2 fallback |
| Local Data | JSON files in `data/` |
| UI Direction | Hebrew RTL |
| CI / Automation | GitHub Actions |
| License | Apache-2.0 |

---

## Project Structure

```text
BeSell/
├── .devcontainer/              # Optional development container setup
├── .github/
│   └── workflows/              # GitHub workflow files
├── assets/                     # Static images such as QR assets
├── .gitignore
├── LICENSE                     # Apache-2.0 license
├── README.md
├── bezeq_bonus_app.py          # Main Streamlit application
└── requirements.txt            # Python dependencies
```

At runtime, local fallback mode uses:

```text
data/
├── users.json
├── records.json
├── bonuses.json
└── messages.json
```

In production, Firestore should be treated as the main source of truth.

---

## Getting Started

### Prerequisites

Use Python 3.10 or newer.

```bash
python --version
pip --version
```

### 1. Clone the repository

```bash
git clone https://github.com/Dovshmi/BeSell.git
cd BeSell
```

### 2. Create a virtual environment

#### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run locally

```bash
streamlit run bezeq_bonus_app.py
```

Then open the local Streamlit URL shown in the terminal.

---

## Configuration

BeSell supports multiple configuration methods. Use only one production-safe method and avoid committing secrets.

### Option A: Streamlit Secrets

Create:

```text
.streamlit/secrets.toml
```

Example structure:

```toml
[FIREBASE]
type = "service_account"
project_id = "YOUR_PROJECT_ID"
private_key_id = "YOUR_PRIVATE_KEY_ID"
private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_KEY\n-----END PRIVATE KEY-----\n"
client_email = "firebase-adminsdk@example.iam.gserviceaccount.com"
client_id = "YOUR_CLIENT_ID"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "YOUR_CERT_URL"

[SUGGEST]
whatsapp_link = "https://chat.whatsapp.com/XXXXXXXXXXXXXX"
qr_image_url = ""
```

### Option B: Environment Variables

```bash
export FIREBASE_JSON='{"type":"service_account","project_id":"..."}'
export SUGGEST_WA_LINK="https://chat.whatsapp.com/XXXXXXXXXXXXXX"
export SUGGEST_QR_URL="https://example.com/qr.png"
```

### Option C: Local Service Account File

```text
firebase_service_account.json
```

This is convenient for local development, but it must stay out of Git.

---

## Data Model

| Collection / File | Purpose |
| :--- | :--- |
| `users` / `users.json` | User accounts, display details, roles, and profile state. |
| `records` / `records.json` | Sales records by user, date, product, quantity, and timestamp. |
| `config/bonuses` / `bonuses.json` | Product definitions and bonus schedules. |
| `messages` / `messages.json` | Admin messages, notices, and dashboard updates. |

---

## Security Notes

- Do not commit Firebase service-account JSON files.
- Use Streamlit Secrets or environment variables for production credentials.
- Passwords are stored as hashes, not plaintext.
- `bcrypt` is used when available; PBKDF2 is used as a fallback.
- Restrict Firestore read/write rules according to role and least privilege.
- Use HTTPS when deploying publicly.
- Local JSON fallback is useful for development, but Firestore is better for real multi-user usage.

---

## Deployment

### Streamlit Community Cloud

1. Push this repository to GitHub.
2. Create a new Streamlit app.
3. Select this repository and set the main file to:

```text
bezeq_bonus_app.py
```

4. Add Firebase and WhatsApp configuration in Streamlit Secrets.
5. Deploy and test login, admin tools, records, and charts.

### Self-Hosted Server

```bash
git clone https://github.com/Dovshmi/BeSell.git
cd BeSell
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run bezeq_bonus_app.py --server.port 8501 --server.address 0.0.0.0
```

For public hosting, put the app behind a reverse proxy such as Nginx or Caddy with HTTPS.

---

## Quality Checks

Before pushing changes:

```bash
python -m compileall bezeq_bonus_app.py
pip check
streamlit run bezeq_bonus_app.py
```

Manual checks:

- Login and registration work.
- Admin and non-admin users see the correct UI.
- Firestore mode loads correctly when credentials are configured.
- Local JSON fallback works when Firebase is not configured.
- Charts render correctly.
- RTL Hebrew layout stays aligned.
- WhatsApp suggestion link and QR image work.

---

## Troubleshooting

### Firebase does not connect

Check which configuration source is being used. The app supports Streamlit secrets, `FIREBASE_JSON`, `GOOGLE_APPLICATION_CREDENTIALS`, and a local `firebase_service_account.json` file.

### App falls back to JSON files

This usually means Firebase credentials were not loaded or Firestore initialization failed. The sidebar diagnostics section can help identify the active storage mode.

### WhatsApp suggestion panel does not open correctly

Confirm that one of these is configured:

```text
SUGGEST.whatsapp_link
SUGGEST_WA_LINK
```

For QR rendering, use either:

```text
SUGGEST.qr_image_url
SUGGEST_QR_URL
assets/whatsapp_qr.png
```

### Charts fail to render

Reinstall requirements:

```bash
pip install -r requirements.txt --upgrade
```

---

## Roadmap

- Add automated tests for bonus calculations and data loading.
- Split the large Streamlit file into modules.
- Add a formal `config/` layer for products and bonus rules.
- Add stronger role-based Firestore rules documentation.
- Add screenshot assets to the README.
- Add Docker deployment files for self-hosting.
- Add import/export admin tooling documentation.

---

## License

This project is licensed under the **Apache License 2.0**. See [`LICENSE`](LICENSE) for details.

---

<div align="center">
  Built by <strong>Rony Shmidov</strong><br />
  A practical RTL dashboard for sales tracking, bonus visibility, and admin-managed team workflows.
</div>
