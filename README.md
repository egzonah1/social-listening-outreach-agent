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
| AI | Claude API (Opus 5.5 for drafting, Haiku 5.5 for triage) |
| Data sources | Bluesky (official AT Protocol API), Mastodon hashtags, labelled sample data |
| Hosting | Google Cloud Run + Neon Postgres |

## Run the backend locally (Windows, Git Bash)

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/api/health and http://127.0.0.1:8000/docs.

Run the tests:

```bash
pytest
```
