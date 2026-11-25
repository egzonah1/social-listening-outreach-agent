# Social Listening Outreach Agent

A tool that helps a life-insurance team find public conversations about life events
(a new baby, buying a home, losing a parent, starting a business) and prepare
thoughtful, human-reviewed replies.

> **Nothing is ever sent automatically.** The app suggests drafts; a person edits,
> approves and posts every message themselves.

Built for the AMANET Stage 2 take-home task.

## Status

Work in progress. This README grows with the project.

## Planned stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query |
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Database | PostgreSQL |
| Data sources | Bluesky (official AT Protocol API), Mastodon hashtags, labelled sample data |
| Hosting | Google Cloud Run + Neon Postgres |

## Run the backend locally (Windows, Git Bash)

Prerequisites: Python 3.12+, Docker Desktop (running).

```bash
# 1. Start Postgres (from the repo root)
docker compose up -d

# 2. Install the backend
cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev]"

# 3. Create the database tables
alembic upgrade head

# 4. Run the API
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/api/health and http://127.0.0.1:8000/docs.

Run the checks (Postgres must be running; tests use the separate `outreach_test` database):

```bash
pytest
ruff check .
mypy app tests migrations
```
