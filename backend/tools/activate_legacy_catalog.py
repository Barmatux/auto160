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

from sqlalchemy import and_, or_, text, tuple_
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.catalog_ratings import generation_key  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import CatalogItem  # noqa: E402

DEFAULT_CUTOFF = "2026-09-10T15:30:00"  # UTC, before full av.by catalog import


def _parse_cutoff(raw: str) -> datetime:
    text_value = raw.strip().replace("Z", "")
    if "T" in text_value:
        return datetime.fromisoformat(text_value)
    return datetime.fromisoformat(f"{text_value}T00:00:00")


def _legacy_model_pairs(db: Session, cutoff: datetime) -> list[tuple[str, str]]:
    """Exact DB make/model values that existed before cutoff (or have rating)."""
    rows = (
        db.query(CatalogItem.make, CatalogItem.model)
        .filter(or_(CatalogItem.created_at < cutoff, CatalogItem.rating.isnot(None)))
        .distinct()
        .all()
    )
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for make, model in rows:
        if not (make or "").strip() or not (model or "").strip():
            continue
        key = (make, model)
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)
    return pairs


def _legacy_generation_keys(db: Session, cutoff: datetime) -> list[tuple[str, str, str | None]]:
    rows = (
        db.query(CatalogItem.make, CatalogItem.model, CatalogItem.generation)
        .filter(or_(CatalogItem.created_at < cutoff, CatalogItem.rating.isnot(None)))
        .distinct()
        .all()
    )
    keys: list[tuple[str, str, str | None]] = []
    seen: set[tuple[str, str, str]] = set()
    for make, model, generation in rows:
        if not (make or "").strip() or not (model or "").strip():
            continue
        gen = generation_key(generation) or None
        seen_key = (make, model, gen or "")
        if seen_key in seen:
            continue
        seen.add(seen_key)
        keys.append((make, model, gen))
    return keys


def print_stats(db: Session, cutoff: datetime) -> None:
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


def apply_activation(
    db: Session,
    *,
    cutoff: datetime,
    scope: str,
    dry_run: bool,
) -> dict[str, int]:
    if scope == "models":
        legacy = _legacy_model_pairs(db, cutoff)
        active_filter = tuple_(CatalogItem.make, CatalogItem.model).in_(legacy) if legacy else text("false")
    else:
        legacy = _legacy_generation_keys(db, cutoff)
        # generation_key strips whitespace; match with trim in SQL via Python keys already stripped.
        # Items store generation as-is; compare using coalesce(trim(generation), '').
        if not legacy:
            active_filter = text("false")
        else:
            clauses = []
            for make, model, gen in legacy:
                if gen:
                    clauses.append(
                        and_(
                            CatalogItem.make == make,
                            CatalogItem.model == model,
                            CatalogItem.generation == gen,
                        )
                    )
                else:
                    clauses.append(
                        and_(
                            CatalogItem.make == make,
                            CatalogItem.model == model,
                            or_(CatalogItem.generation.is_(None), CatalogItem.generation == ""),
                        )
                    )
            active_filter = or_(*clauses)

    would_activate = (
        db.query(CatalogItem)
        .filter(active_filter, CatalogItem.hidden_from_catalog.is_(True))
        .count()
    )
    would_deactivate = (
        db.query(CatalogItem)
        .filter(~active_filter, CatalogItem.hidden_from_catalog.is_(False))
        .count()
    )
    active_count = db.query(CatalogItem).filter(active_filter).count()

    if dry_run:
        return {
            "legacy_keys": len(legacy),
            "active_items": active_count,
            "activated": would_activate,
            "deactivated": would_deactivate,
            "visible_after": active_count,
            "hidden_after": db.query(CatalogItem).count() - active_count,
        }

    # Bulk flip: hide everything, then unhide legacy set.
    db.query(CatalogItem).update({CatalogItem.hidden_from_catalog: True}, synchronize_session=False)
    if legacy:
        db.query(CatalogItem).filter(active_filter).update(
            {CatalogItem.hidden_from_catalog: False},
            synchronize_session=False,
        )
    db.commit()

    return {
        "legacy_keys": len(legacy),
        "active_items": active_count,
        "activated": would_activate,
        "deactivated": would_deactivate,
        "visible_after": db.query(CatalogItem).filter(CatalogItem.hidden_from_catalog.is_(False)).count(),
        "hidden_after": db.query(CatalogItem).filter(CatalogItem.hidden_from_catalog.is_(True)).count(),
    }


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
            f"active_items={result['active_items']} activated={result['activated']} "
            f"deactivated={result['deactivated']} visible_after={result['visible_after']} "
            f"hidden_after={result['hidden_after']}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
