from pathlib import Path
import os
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.db import SessionLocal
from app.models import CatalogItem

urls = []
for line in Path("data/avby_urls_from_telegram_chat.txt").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#"):
        urls.append(line.rstrip("/").rstrip("-"))

db = SessionLocal()
try:
    total = db.query(CatalogItem).count()
    hidden = db.query(CatalogItem).filter(CatalogItem.hidden_from_catalog.is_(True)).count()
    visible = db.query(CatalogItem).filter(CatalogItem.hidden_from_catalog.is_(False)).count()
    print(f"before total={total} visible={visible} hidden={hidden}")
    updated = 0
    # Unhide all av.by items that came from this curated list OR are currently the only catalog
    # Prefer matching by slug; also unhide everything imported today that is still hidden if matched.
    for item in db.query(CatalogItem).filter(CatalogItem.source_site == "av.by").all():
        src = (item.source_url or "").split("#", 1)[0].rstrip("/").rstrip("-")
        matched = False
        for u in urls:
            if src == u or src.startswith(u) or (u and u in src):
                matched = True
                break
            slug = u.rsplit("/catalog/", 1)[-1]
            if slug and f"/catalog/{slug}" in src:
                matched = True
                break
        if matched and item.hidden_from_catalog:
            item.hidden_from_catalog = False
            updated += 1
    db.commit()
    visible2 = db.query(CatalogItem).filter(CatalogItem.hidden_from_catalog.is_(False)).count()
    hidden2 = db.query(CatalogItem).filter(CatalogItem.hidden_from_catalog.is_(True)).count()
    print(f"unhidden={updated} visible_after={visible2} hidden_after={hidden2}")
finally:
    db.close()