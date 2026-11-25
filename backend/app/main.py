"""FastAPI entry point.

`create_app()` builds the application. Using a factory (instead of a global
object built at import time) lets tests create a fresh app with their own
settings. Uvicorn runs the module-level `app` below.
"""

from fastapi import FastAPI

from app import __version__
from app.api.routes import health
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        # All API routes live under /api so the React app can be served from "/" later.
        docs_url="/docs",
        openapi_url="/api/openapi.json",
    )
    app.include_router(health.router, prefix="/api")
    return app


app = create_app()
