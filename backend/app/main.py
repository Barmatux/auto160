from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.bootstrap import safe_bootstrap_admin
from app.avby_session import warm_vin_test_session
from app.db import SessionLocal, engine
from app.logging_setup import ensure_uvicorn_file_logging, setup_logging
from app.middleware.analytics import AnalyticsMiddleware
from app.routers import admin, auth, catalog_photos, chat, internal_catalog, listings, market_prices, media, pages
from app.storage import ensure_bucket_exists

setup_logging("api")

app = FastAPI(title="Auto160 Backend", version="0.1.0")
app.add_middleware(AnalyticsMiddleware)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_FAVICON_ICO = _STATIC_DIR / "icons" / "favicon.ico"
if not _FAVICON_ICO.is_file():
    _FAVICON_ICO = _STATIC_DIR / "favicon.ico"
_APPLE_TOUCH = _STATIC_DIR / "icons" / "apple-touch-icon.png"
if not _APPLE_TOUCH.is_file():
    _APPLE_TOUCH = _STATIC_DIR / "apple-touch-icon.png"

# Safari Favorites probe root apple-touch-icon with HEAD and need a cacheable PNG.
_ICON_CACHE_HEADERS = {
    "Cache-Control": "public, max-age=604800",
}


def _png_icon_response(path: Path) -> FileResponse:
    return FileResponse(
        path,
        media_type="image/png",
        headers=_ICON_CACHE_HEADERS,
    )


@app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
def favicon():
    return FileResponse(
        _FAVICON_ICO,
        media_type="image/x-icon",
        headers=_ICON_CACHE_HEADERS,
    )


def apple_touch_icon():
    return _png_icon_response(_APPLE_TOUCH)


for _apple_touch_path in (
    "/apple-touch-icon.png",
    "/apple-touch-icon-precomposed.png",
    "/apple-touch-icon-180x180.png",
):
    app.add_api_route(
        _apple_touch_path,
        apple_touch_icon,
        methods=["GET", "HEAD"],
        include_in_schema=False,
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
app.include_router(chat.router)
app.include_router(media.router)
app.include_router(pages.router)
app.include_router(admin.router)
