from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.bootstrap import safe_bootstrap_admin
from app.avby_session import warm_vin_test_session
from app.db import SessionLocal, engine
from app.logging_setup import ensure_uvicorn_file_logging, setup_logging
from app.middleware.analytics import AnalyticsMiddleware
from app.routers import admin, auth, catalog_photos, internal_catalog, listings, market_prices, media, pages
from app.storage import ensure_bucket_exists

setup_logging("api")

app = FastAPI(title="Auto160 Backend", version="0.1.0")
app.add_middleware(AnalyticsMiddleware)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_FAVICON_ICO = _STATIC_DIR / "icons" / "favicon.ico"
if not _FAVICON_ICO.is_file():
    _FAVICON_ICO = _STATIC_DIR / "favicon.ico"


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Browsers cache /favicon.ico by URL alone; never long-cache so tab icons can update.
    return FileResponse(
        _FAVICON_ICO,
        media_type="image/x-icon",
        headers={"Cache-Control": "no-store"},
    )


@app.on_event("startup")
def on_startup() -> None:
    ensure_uvicorn_file_logging()
    ensure_bucket_exists()
    safe_bootstrap_admin(SessionLocal, engine)
    warm_vin_test_session(SessionLocal)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(listings.router)
app.include_router(catalog_photos.router)
app.include_router(internal_catalog.router)
app.include_router(market_prices.router)
app.include_router(media.router)
app.include_router(pages.router)
app.include_router(admin.router)
