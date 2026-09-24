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


@app.get("/api/v1/ops/customs-night-stats", include_in_schema=False)
def customs_night_stats():
    """Aggregate GTK customs backfill stats for the last nightly window (no VIN values)."""
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    from sqlalchemy import case, func

    from app.customs_vin import DATABASE_PERSONAL
    from app.db import SessionLocal
    from app.models import VinCustomsCheck

    minsk = ZoneInfo("Europe/Minsk")
    now_msk = datetime.now(minsk)
    run_day = now_msk.date() if now_msk.hour >= 2 else (now_msk.date() - timedelta(days=1))
    window_start_msk = datetime(run_day.year, run_day.month, run_day.day, 2, 0, tzinfo=minsk)
    window_end_msk = window_start_msk + timedelta(hours=8)
    start_utc = window_start_msk.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = window_end_msk.astimezone(timezone.utc).replace(tzinfo=None)

    def _bucket(db, *, since: datetime | None = None, until: datetime | None = None) -> dict:
        filters = [VinCustomsCheck.database == DATABASE_PERSONAL]
        if since is not None:
            filters.append(VinCustomsCheck.checked_at >= since)
        if until is not None:
            filters.append(VinCustomsCheck.checked_at < until)
        row = (
            db.query(
                func.count(VinCustomsCheck.id).label("total"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (VinCustomsCheck.found.is_(True))
                                & (VinCustomsCheck.release_date.isnot(None)),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("found_with_date"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (VinCustomsCheck.found.is_(True))
                                & (VinCustomsCheck.release_date.is_(None)),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("found_no_date"),
                func.coalesce(
                    func.sum(case((VinCustomsCheck.found.is_(False), 1), else_=0)),
                    0,
                ).label("not_found"),
                func.coalesce(
                    func.sum(case((VinCustomsCheck.error_message.isnot(None), 1), else_=0)),
                    0,
                ).label("with_error"),
            )
            .filter(*filters)
            .one()
        )
        total = int(row.total or 0)
        found_with_date = int(row.found_with_date or 0)
        found_no_date = int(row.found_no_date or 0)
        not_found = int(row.not_found or 0)
        with_error = int(row.with_error or 0)
        return {
            "total": total,
            "found_with_date": found_with_date,
            "found_no_date": found_no_date,
            "not_found": not_found,
            "with_error": with_error,
            "success": found_with_date,
            "unsuccessful": not_found + found_no_date,
        }

    db = SessionLocal()
    try:
        log_tail: list[str] = []
        log_path = Path("/app/logs/customs-import-dates.log")
        if log_path.is_file():
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            interesting = [
                line
                for line in lines
                if any(
                    marker in line
                    for marker in (
                        "customs-import-dates-start",
                        "customs-import-dates-finish",
                        "candidates=",
                        "done ",
                        "customs-import |",
                    )
                )
            ]
            log_tail = interesting[-40:]

        return {
            "timezone": "Europe/Minsk",
            "night_window": {
                "start": window_start_msk.isoformat(),
                "end": window_end_msk.isoformat(),
            },
            "night": _bucket(db, since=start_utc, until=end_utc),
            "last_24h": _bucket(db, since=datetime.utcnow() - timedelta(hours=24)),
            "all_time": _bucket(db),
            "log_tail": log_tail,
        }
    finally:
        db.close()


app.include_router(auth.router)
app.include_router(listings.router)
app.include_router(catalog_photos.router)
app.include_router(internal_catalog.router)
app.include_router(market_prices.router)
app.include_router(chat.router)
app.include_router(media.router)
app.include_router(pages.router)
app.include_router(admin.router)
