# QE Compass

An enterprise quality-engineering assessment platform. Teams capture interviews, evidence and maturity scores for lines of business, programs and applications. The platform then rolls these up into maturity maps, gap analysis, an analyst you can question, and versioned dashboards and reports.

It runs as a standalone application on your own computer today, and can move to a client server or cloud later without changes to the code.

---

## Quick start

**You need:** Python 3.10 or newer ([python.org/downloads](https://www.python.org/downloads/); on Windows tick *Add python.exe to PATH*). Node.js is not needed; the web interface comes pre-built.

| Windows | macOS / Linux |
|---|---|
| Double-click **`start.bat`** | Run **`./start.sh`** in a terminal |

The first start takes about a minute while it sets up a private Python environment in `.venv`. Later starts take a few seconds. Your browser opens at **http://localhost:8000**. Keep the window open while you work; close it (or press Ctrl+C) to stop.

### First run

1. **Create the administrator account.** The first person to open a new installation becomes its administrator.
2. **Engagements → Load BC Ferries sample** to explore with illustrative data, or **Start a new engagement** for real work. New engagements get the standard 5-pillar / 25-focus-area framework.
3. **Users** (admin only) → add your team as *Assessors* (capture and edit) or *Viewers* (read-only). Each person sets their own password on first sign-in.

---

## How the assessment runs

| Area | What it's for |
|---|---|
| **Scope & Entities** | Engagement dates and targets. Add **lines of business**, **programs** and **applications**, and nest them with *+ Child*. Any entity can be assessed directly. A parent that isn't scored on a focus area takes the weighted score of its children, and the enterprise rolls up from top-level entities only. |
| **Interviews** | Schedule and log stakeholder sessions against an entity. On a completed interview, **Extract findings** turns the notes into per-focus-area findings with a suggested level, which you review and **apply** to the assessment. |
| **Evidence Library** | Upload Word, Excel, PDF, CSV, text, YAML and similar files, or register links. Each file is read, summarized and mapped to focus areas, then stored in `data/uploads`. Linked evidence raises confidence automatically. |
| **Assessment** | Score each focus area 1–5 per entity, override confidence, and write notes (saved automatically). Each score shows its linked evidence and a level suggested from the notes. **History** shows every change. |
| **AI Analyst** | Ask about gaps, missing evidence, follow-up interview questions, conflicting signals, quick wins, strengths, comparisons, or a named entity or focus area. |
| **Maturity Map** | Heatmap by entity × focus area or pillar. Click a cell for its evidence. |
| **Dashboards** | Live draft report. **Publish** freezes a numbered version with an editable executive summary; versions trend over time. **Print / save as PDF** produces a clean report. |
| **Framework** | Edit pillars, focus areas, guiding questions, recommendations, roadmap horizons, maturity level definitions, targets, weights and status thresholds, per engagement. |

**Roles:** *Administrator* has full access, plus users and deleting engagements. *Assessor* can capture data, edit scope and framework, and publish. *Viewer* can read everything and use the analyst.

---

## Your data

Everything lives in the **`data`** folder next to `start.bat`:

- `data/qecompass.db` holds the database (SQLite).
- `data/uploads/` holds the evidence files.

**Back up** by stopping the app and copying the `data` folder. To **move** an engagement to another installation, use **Scope & Entities → Export engagement (JSON)**, then **Engagements → Import** on the other side. The export carries scores, interviews, evidence records and dashboards, but not the uploaded files themselves. **CSV export** gives every score for Excel.

By default the app listens only on this computer (`127.0.0.1`).

---

## Configuration

Copy `.env.example` to `.env` and uncomment what you need:

| Setting | Default | Purpose |
|---|---|---|
| `QEC_PORT` | `8000` | Port |
| `QEC_HOST` | `127.0.0.1` | `0.0.0.0` lets colleagues on your network connect at `http://your-machine:8000` |
| `QEC_DATA_DIR` | `./data` | Database and uploads location (e.g. a OneDrive or network folder) |
| `QEC_DATABASE_URL` | SQLite in data dir | PostgreSQL for server deployments |
| `QEC_SESSION_HOURS` | `12` | How long a sign-in lasts |
| `QEC_COOKIE_SECURE` | `false` | Set `true` when served over HTTPS |
| `QEC_MAX_UPLOAD_MB` | `25` | Largest evidence file |
| `QEC_AI_PROVIDER` | `rules` | Analysis engine (see below) |

**Locked out?** From the `backend` folder run `..\.venv\Scripts\python -m app reset-password --email you@example.com` (on macOS/Linux use `../.venv/bin/python`). `create-admin` and `load-sample` work the same way.

---

## The analysis engine and connecting AI later

Finding extraction, evidence classification, level suggestions, the analyst and report summaries all go through one interface: `backend/app/ai/base.py` (`AIProvider`). The bundled **rules engine** (`app/ai/rules.py`) is offline, deterministic and explainable, so nothing leaves the machine.

To connect a model approved by the client (Claude, Azure OpenAI or a self-hosted model):

1. Add `backend/app/ai/llm.py` with a class implementing the five `AIProvider` methods. Each method receives plain data. The analyst receives a structured JSON view of the workspace (`app/ai/context.py`), ready to place in a prompt.
2. Register it in `PROVIDERS` in `app/ai/__init__.py`.
3. Set `QEC_AI_PROVIDER=llm` in `.env`, and keep `rules` as the fallback.

No routes, database tables or screens change.

---

## Moving to client infrastructure

When the client's environment is known:

- **Docker + PostgreSQL:** set `QEC_DB_PASSWORD` in `deploy/.env`, then run `docker compose -f deploy/docker-compose.yml up -d --build`. The image builds the front end and runs as a non-root user, and database migrations run automatically at start-up.
- **Any Linux VM:** install Python 3.10+, set `QEC_DATABASE_URL`, install `deploy/requirements-postgres.txt` alongside `backend/requirements.txt`, and run `python -m app` from `backend` under systemd.
- **Azure / AWS / Kubernetes:** use the same container with managed PostgreSQL. Mount persistent storage at `/data` for uploads.
- Put it behind the client's HTTPS reverse proxy or load balancer, and set `QEC_COOKIE_SECURE=true`.
- Carry engagements across with JSON export/import.

---

## Security notes

- **Passwords:** hashed with scrypt; at least 10 characters, mixed case and a number.
- **Sign-in:** 5 failed attempts lock that email for 15 minutes. Sessions are server-side, revocable, HttpOnly, SameSite=Strict cookies, and only a hash of each session token is stored.
- **Request checks:** state-changing requests require a custom header (CSRF defence). A strict Content-Security-Policy and anti-framing headers are applied.
- **Uploads:** executable and script files are rejected, and stored files are served only to signed-in users.
- **Audit trail:** every score change is kept in the assessment history, and every change appears in the activity log.
- **Not yet built:** SSO (Entra ID), per-engagement access control and at-rest encryption. These are natural next steps for a client-hosted deployment.

---

## Development

```
backend/    FastAPI + SQLAlchemy + Alembic (Python)
  app/routers/      REST API (/api/docs when running)
  app/analytics.py  roll-up scoring, coverage, gaps, conflicts, snapshots
  app/ai/           provider interface + offline rules engine
  migrations/       database migrations (applied automatically at start)
  tests/            pytest suite
frontend/   React + TypeScript + Vite (pre-built into frontend/dist)
deploy/     Dockerfile and docker-compose for server hosting
```

- **Backend tests:** from `backend`, `pip install -r requirements-dev.txt`, then `pytest`.
- **Front end:** from `frontend`, `npm install`, then `npm run dev` (proxies `/api` to port 8000) and `npm run build`.
- **Schema change:** edit `app/models.py`, then `alembic revision --autogenerate -m "describe change"` from `backend` (with `sqlalchemy.url` set).

## Troubleshooting

- **"Python was not found":** install Python 3.10+ and tick *Add to PATH*. On managed laptops, the Microsoft Store version also works.
- **Setup fails on a corporate network:** pip needs your proxy. Run `set HTTPS_PROXY=http://proxy:port` (Windows) or `export HTTPS_PROXY=…` before `start.bat` / `start.sh`.
- **Port 8000 in use:** set `QEC_PORT=8010` in `.env`.
- **Start over:** stop the app and delete the `data` folder. The next start is a fresh installation.
