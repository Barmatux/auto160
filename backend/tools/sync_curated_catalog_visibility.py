"""Public catalog = Telegram curated URLs only; everything else stays hidden.

Admins still see the full catalog via include_hidden in pages.py.
New import_avby rows start hidden; this script re-applies the curated allowlist.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.db import SessionLocal
from app.models import CatalogItem

URLS_FILE = Path("data/avby_urls_from_telegram_chat.txt")


def _normalize_url(value: str) -> str:
    return value.split("#", 1)[0].rstrip("/").rstrip("-")


def _load_curated_urls() -> list[str]:
    urls: list[str] = []
    for line in URLS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(_normalize_url(line))
    return urls


def _url_matches_curated(source_url: str | None, curated: list[str]) -> bool:
    src = _normalize_url(source_url or "")
    if not src:
        return False
    for u in curated:
        if not u:
            continue
        if src == u or src.startswith(u) or u in src:
            return True
        slug = u.rsplit("/catalog/", 1)[-1]
        if slug and f"/catalog/{slug}" in src:
            return True
    return False


def main() -> None:
    curated = _load_curated_urls()
    db = SessionLocal()
    try:
        items = db.query(CatalogItem).filter(CatalogItem.source_site == "av.by").all()
        before_visible = sum(1 for i in items if not i.hidden_from_catalog)
        before_hidden = len(items) - before_visible
        print(f"curated_urls={len(curated)} total_avby={len(items)} visible={before_visible} hidden={before_hidden}")

        unhidden = 0
        hidden = 0
        for item in items:
            should_show = _url_matches_curated(item.source_url, curated)
            if should_show and item.hidden_from_catalog:
                item.hidden_from_catalog = False
                unhidden += 1
            elif not should_show and not item.hidden_from_catalog:
                item.hidden_from_catalog = True
                hidden += 1
        db.commit()

        after_visible = (
            db.query(CatalogItem)
            .filter(CatalogItem.source_site == "av.by", CatalogItem.hidden_from_catalog.is_(False))
            .count()
        )
        after_hidden = (
            db.query(CatalogItem)
            .filter(CatalogItem.source_site == "av.by", CatalogItem.hidden_from_catalog.is_(True))
            .count()
        )
        print(f"changed unhidden={unhidden} newly_hidden={hidden}")
        print(f"after visible={after_visible} hidden={after_hidden}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
