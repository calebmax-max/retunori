# RETUNORI

Retreats · Experiences · Connections

RETUNORI is a dark, mobile-first retreat registration platform. This repository contains a separate Vite/React frontend and FastAPI/SQLAlchemy backend.

## Current foundation

- Public homepage, retreat listing and retreat detail routes
- Attendee registration and login with JWT sessions
- Role-aware admin and staff route boundaries
- SQLAlchemy models for users, profiles, retreats, courses, and retreat-course options
- PostgreSQL-ready configuration with SQLite as the zero-setup local fallback
- OpenAPI documentation at `/docs`
- Server-verified Daraja callback path with idempotent ticket issuance guard
- Staff assignment enforcement, check-in audit attempts, admin overview/report endpoints
- Public announcements, legal-page lookup, and contact-submission storage
- Admin-managed retreat image uploads with file type/size validation and public galleries
- Admin content, SEO, activity-log, notification, staff-management and backup routes
- Admin publishing, contact-submission, payment-record, issued-ticket and backup-management screens
- Public retreat countdown, map directions, support links and announcement context
- Staff scan history with automatic dashboard refresh; admin overview refreshes automatically
- Scheduled sales windows, automatic archival, online-only paid check-in and rate limiting

Daraja Sandbox credentials, SMTP delivery, PostgreSQL connectivity and production backup storage are deployment configuration requirements; the API does not fake payment success.

## Run locally

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

The API defaults to a local SQLite database. Set `DATABASE_URL` in `.env` to a PostgreSQL connection string for deployment.

Run `alembic upgrade head` after changing `DATABASE_URL` or deploying new migrations. The current migration head is `0008_ticket_receipt_snapshot`.

Create the first administrator from the backend directory after configuring the database:

```powershell
python scripts/create_admin.py --email admin@example.com --password "use-a-long-random-password"
```

This is intentionally a local/operations command; administrator creation is not exposed as a public API route.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000`.

## Verification

```powershell
cd backend
python -m pytest

cd ..\frontend
npm run build
```

The backend tests use an isolated per-run SQLite file under the system temporary directory, so verification does not modify the local development database.

Before production, configure a strong `JWT_SECRET`, PostgreSQL, HTTPS/CORS, SMTP values (`SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`) for password-reset delivery, and Daraja Sandbox credentials. Do not place any of these values in frontend code. Local retreat media is stored under `backend/media`; use private object storage for production deployments.

# retunori
