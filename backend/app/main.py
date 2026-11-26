"""FastAPI entry point.

`create_app()` builds the application. Using a factory (instead of a global
object built at import time) lets tests create a fresh app with their own
settings. Uvicorn runs the module-level `app` below.

In production the same server also serves the built React app, so the site
and the API share one address (no CORS setup, one free Render service).
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app import __version__
from app.api.routes import campaigns, health, meta, posts
from app.core.config import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def create_app(frontend_dir: Path | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        # All API routes live under /api so the React app can be served from "/".
        docs_url="/docs",
        openapi_url="/api/openapi.json",
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(meta.router, prefix="/api")
    app.include_router(campaigns.router, prefix="/api")
    app.include_router(posts.router, prefix="/api")

    if frontend_dir is None:
        frontend_dir = Path(settings.frontend_dist or REPO_ROOT / "frontend" / "dist")
    if (frontend_dir / "index.html").is_file():
        _serve_frontend(app, frontend_dir.resolve())
    return app


def _serve_frontend(app: FastAPI, root: Path) -> None:
    """Serve built files, and index.html for any other page (the React router
    decides what to show for /campaigns/3 etc.). Unknown /api paths stay 404."""
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        file = (root / path).resolve()
        # is_relative_to blocks "../" tricks that try to read files outside dist.
        if path and file.is_relative_to(root) and file.is_file():
            # Vite puts a content hash in asset names, so they can be cached forever.
            cache = (
                "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
            )
            return FileResponse(file, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
