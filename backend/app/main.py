from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.bootstrap import safe_bootstrap_admin
from app.db import SessionLocal, engine
from app.routers import admin, auth, catalog_photos, listings, pages
from app.storage import ensure_bucket_exists

app = FastAPI(title="Auto160 Backend", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def on_startup() -> None:
    ensure_bucket_exists()
    safe_bootstrap_admin(SessionLocal, engine)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(listings.router)
app.include_router(catalog_photos.router)
app.include_router(pages.router)
app.include_router(admin.router)
