# Changelog

## 1.0.1 (2026-10-23): security release

Fixes every finding from the v1.0 security review (`docs/QE_Compass_Security_and_SOC2_Control_Mapping.pdf`).
Upgrading is automatic: `start.bat` / `start.sh` install the new components, and the database is
upgraded on first start. Existing users keep access to existing engagements.

**Dependencies (F-01)**
- FastAPI 0.162.0 with Starlette 1.7.0, Uvicorn 0.54.0, python-multipart 0.0.32, pypdf 6.21.2,
  python-docx 1.2.0, SQLAlchemy 2.0.55; front end React Router 7.18.4, Vite 6.4.5.
  `pip-audit` and `npm audit` report no known vulnerabilities.

**Sign-in and sessions**
- Two-step verification with any authenticator app; optional per user, or required for all with
  `QEC_REQUIRE_MFA=true`. Administrators can reset it; codes can't be reused (F-02).
- Failed sign-ins are counted in the database: 5 per account and 20 per address per 15 minutes,
  and limits survive restarts (F-06).
- Sessions end after 60 minutes of inactivity (`QEC_IDLE_MINUTES`) (F-08).

**Audit and access**
- Security log of sign-ins, failures, lockouts, sign-outs, password and two-step changes, user and
  role changes, engagement access changes, deletions and exports, in **Users → Security log** and the
  server log (F-03).
- Engagement team: people see only engagements they created or were added to; administrators see all (F-05).

**Transport and hardening**
- Built-in HTTPS with `QEC_TLS_CERT` / `QEC_TLS_KEY`; Secure cookies and HSTS automatically over
  HTTPS; trusted proxy setting `QEC_TRUSTED_PROXIES`; server version header removed (F-04).
- Uploads use an allow list of document, data and image types; file types are taken from the file
  extension, not the browser (F-07).
- Evidence links must be http(s) (F-09).
- API documentation is off unless `QEC_API_DOCS=true` (F-10).

## 1.0.0 (2026-10-20)

First release.
