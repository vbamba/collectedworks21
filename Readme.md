# CollectedWorks Project

## Overview

CollectedWorks is a Flask + React search application for PDF corpus retrieval.  
The backend combines FAISS-based semantic search with text search APIs and chapter/content routes.

## Operations Runbook

- [docs/DEPLOY.md](docs/DEPLOY.md) — full deploy walkthrough (rsync to EC2,
  chapters.db fixups, frontend build, smoke tests, rollback) plus the
  search-query analytics section (§ 7) covering `query_log.db` and the
  `query_stats.py` CLI for "top queries" / "zero-result queries" reports.
- [docs/OPERATIONS_HARDENING.md](docs/OPERATIONS_HARDENING.md) — hardening,
  CORS, service restart policy, incident recovery.

## Repository Layout

```text
backend/
  app/            Flask app package (routes, app factory, templates)
  scripts/        Search and indexing helpers
  tests/          Backend tests
  wsgi.py         WSGI entrypoint (app = create_app())
frontend/
  src/            React app source
  public/         Static assets
docs/
  OPERATIONS_HARDENING.md
```

## Local Development

### Backend (Flask)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools
pip install -r requirements.txt
python wsgi.py
```

Default local backend URL: `http://127.0.0.1:5000` (unless `PORT` overrides it).

### Frontend (React)

```bash
cd frontend
npm install
npm start
```

If needed for local API routing, set:

```bash
REACT_APP_BACKEND_URL=http://127.0.0.1:5000
```

## Testing

### Backend

```bash
pytest backend/tests/
```

### Frontend

```bash
cd frontend
npm test
```

## Production Notes

- CollectedWorks backend service is expected to run via `gunicorn` using `wsgi:app`.
- Nginx is expected to proxy frontend/API traffic.
- For hardening, CORS, service restart policy, and incident recovery, use the runbook in `docs/OPERATIONS_HARDENING.md`.
