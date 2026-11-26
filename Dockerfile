# One image for the whole app: the React site is built first, then copied
# next to the FastAPI backend, which serves both the site and the API.

# ---- 1. Build the frontend ---------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. Backend + built site -------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    FRONTEND_DIST=/app/frontend/dist
WORKDIR /app/backend

# Install dependencies first so code changes don't reinstall everything.
COPY backend/pyproject.toml ./
RUN mkdir app && touch app/__init__.py && pip install . && rm -rf app build
COPY backend/ ./
RUN pip install --no-deps .
COPY --from=frontend /frontend/dist /app/frontend/dist

# Run as a normal user, not root.
RUN useradd --create-home appuser
USER appuser

# Render sets PORT. Migrations run on every start, so the database is always
# up to date (alembic skips migrations that already ran).
# --proxy-headers: trust Render's proxy for the visitor's IP (used by the limits).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
