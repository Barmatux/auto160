import csv
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import CatalogItem


def _to_int(value: str) -> int | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _to_float(value: str) -> float | None:
    cleaned = (value or "").strip().replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def seed_catalog_from_csv(db: Session) -> int:
    if db.query(CatalogItem).count() > 0:
        return 0

    csv_path = Path(settings.catalog_seed_csv_path)
    if not csv_path.exists():
        return 0

    created = 0
    with csv_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        for row in reader:
            make = (row.get("make") or "").strip()
            model = (row.get("model") or "").strip()
            if not make or not model:
                continue

            item = CatalogItem(
                make=make,
                model=model,
                generation=(row.get("generation") or "").strip() or None,
                year_from=_to_int(row.get("year_from") or ""),
                year_to=_to_int(row.get("year_to") or ""),
                min_price_rub=_to_float(row.get("min_price_rub") or ""),
                body_type=(row.get("body_type") or "").strip() or None,
                export_country=(row.get("export_country") or "").strip() or None,
                steering_wheel=(row.get("steering_wheel") or "").strip() or None,
                fuel_type=(row.get("fuel_type") or "").strip() or None,
                engine_power_hp=_to_int(row.get("engine_power_hp") or ""),
                engine_volume_l=_to_float(row.get("engine_volume_l") or ""),
                drivetrain=(row.get("drivetrain") or "").strip() or None,
                transmission=(row.get("transmission") or "").strip() or None,
                source_site="seed_csv",
                raw_specs={k: (v or "").strip() for k, v in row.items()},
            )
            db.add(item)
            created += 1

    if created > 0:
        db.commit()
    return created
