from fastapi import FastAPI
from fastapi.responses import RedirectResponse
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

FAVICON_URL = "/static/favicon.svg?v=20260824-01"


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse(url=FAVICON_URL, status_code=301)


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
