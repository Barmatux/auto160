"""Activate legacy catalog models and hide the full AV.BY dump overflow.

Uses CatalogItem.hidden_from_catalog as the active flag:
  active  => hidden_from_catalog=False  (public catalog + listings sync)
  inactive => hidden_from_catalog=True

Legacy = make/model (or generation) that already existed before the full-catalog
import cutoff, or any make/model that has a rating.

Does NOT archive listings — only flips the visibility flag.

Examples:
  python tools/activate_legacy_catalog.py --dry-run
  python tools/activate_legacy_catalog.py --cutoff 2026-09-10T15:30:00
  python tools/activate_legacy_catalog.py --scope generations
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from sqlalchemy import or_  # noqa: E402

from app.catalog_ratings import generation_key  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import CatalogItem  # noqa: E402

DEFAULT_CUTOFF = "2026-09-10T15:30:00"  # UTC, before full av.by catalog import


def _parse_cutoff(raw: str) -> datetime:
    text = raw.strip().replace("Z", "")
    if "T" in text:
        return datetime.fromisoformat(text)
    return datetime.fromisoformat(f"{text}T00:00:00")


def _model_key(item: CatalogItem) -> tuple[str, str]:
    return ((item.make or "").strip(), (item.model or "").strip())


def _generation_tuple(item: CatalogItem) -> tuple[str, str, str]:
    make, model = _model_key(item)
    return (make, model, generation_key(item.generation))


def collect_legacy_keys(db, *, cutoff: datetime, scope: str) -> set[tuple]:
    rows = (
        db.query(CatalogItem)
        .filter(or_(CatalogItem.created_at < cutoff, CatalogItem.rating.isnot(None)))
        .all()
    )
    keys: set[tuple] = set()
    for item in rows:
        make, model = _model_key(item)
        if not make or not model:
            continue
        if scope == "models":
            keys.add((make, model))
        else:
            keys.add((make, model, generation_key(item.generation)))
    return keys


def apply_activation(
    db,
    *,
    cutoff: datetime,
    scope: str,
    dry_run: bool,
) -> dict[str, int]:
    legacy = collect_legacy_keys(db, cutoff=cutoff, scope=scope)
    activated = 0
    deactivated = 0
    unchanged = 0

    for item in db.query(CatalogItem).order_by(CatalogItem.id.asc()).all():
        make, model = _model_key(item)
        if not make or not model:
            unchanged += 1
            continue
        if scope == "models":
            should_active = (make, model) in legacy
        else:
            should_active = (make, model, generation_key(item.generation)) in legacy

        want_hidden = not should_active
        if item.hidden_from_catalog is want_hidden:
            unchanged += 1
            continue
        if want_hidden:
            deactivated += 1
        else:
            activated += 1
        if not dry_run:
            item.hidden_from_catalog = want_hidden

    if not dry_run:
        db.commit()

    return {
        "legacy_keys": len(legacy),
        "activated": activated,
        "deactivated": deactivated,
        "unchanged": unchanged,
        "visible_after": db.query(CatalogItem)
        .filter(CatalogItem.hidden_from_catalog.is_(False))
        .count()
        if not dry_run
        else -1,
        "hidden_after": db.query(CatalogItem)
        .filter(CatalogItem.hidden_from_catalog.is_(True))
        .count()
        if not dry_run
        else -1,
    }


def print_stats(db, cutoff: datetime) -> None:
    total = db.query(CatalogItem).count()
    visible = db.query(CatalogItem).filter(CatalogItem.hidden_from_catalog.is_(False)).count()
    hidden = db.query(CatalogItem).filter(CatalogItem.hidden_from_catalog.is_(True)).count()
    rated = db.query(CatalogItem).filter(CatalogItem.rating.isnot(None)).count()
    pre = db.query(CatalogItem).filter(CatalogItem.created_at < cutoff).count()
    post = db.query(CatalogItem).filter(CatalogItem.created_at >= cutoff).count()
    print(
        f"stats: total={total} visible={visible} hidden={hidden} rated={rated} "
        f"pre_cutoff={pre} post_cutoff={post} cutoff={cutoff.isoformat()}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Activate legacy catalog; hide full-dump overflow")
    parser.add_argument(
        "--cutoff",
        default=DEFAULT_CUTOFF,
        help=f"UTC datetime; items created before this are legacy (default {DEFAULT_CUTOFF})",
    )
    parser.add_argument(
        "--scope",
        choices=("models", "generations"),
        default="models",
        help="Activate whole make+model (default) or only legacy generations",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show counts without writing")
    parser.add_argument("--stats-only", action="store_true", help="Print current stats and exit")
    args = parser.parse_args()

    cutoff = _parse_cutoff(args.cutoff)
    db = SessionLocal()
    try:
        print_stats(db, cutoff)
        if args.stats_only:
            return
        result = apply_activation(db, cutoff=cutoff, scope=args.scope, dry_run=args.dry_run)
        mode = "dry-run" if args.dry_run else "applied"
        print(
            f"activation-{mode}: scope={args.scope} legacy_keys={result['legacy_keys']} "
            f"activated={result['activated']} deactivated={result['deactivated']} "
            f"unchanged={result['unchanged']} visible_after={result['visible_after']} "
            f"hidden_after={result['hidden_after']}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
