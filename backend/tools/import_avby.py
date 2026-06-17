import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from curl_cffi import requests
from bs4 import BeautifulSoup

# Allow running script directly: `python tools/import_avby.py ...`
ROOT_DIR = Path(__file__).resolve().parents[1]
LAUNCH_CWD = Path.cwd()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
# Keep SQLite relative paths stable regardless of launch directory.
os.chdir(ROOT_DIR)

from app.db import SessionLocal
from app.models import CatalogItem


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^\d]", "", value)
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip().replace(",", ".")
    cleaned = re.sub(r"[^0-9.]", "", cleaned)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_generation_from_slug(slug: str | None) -> tuple[str | None, int | None, int | None]:
    # Example slug: "u11-2022-" or "e84-2009-2015"
    if not slug:
        return None, None, None
    match = re.search(r"^([a-z0-9]+)-(\d{4})-(\d{4})?$", slug, flags=re.IGNORECASE)
    if not match:
        return None, None, None
    generation = match.group(1).upper()
    year_from = _to_int(match.group(2))
    year_to = _to_int(match.group(3))
    return generation, year_from, year_to


def _normalize_model_name(name: str | None) -> str | None:
    if not name:
        return None
    source = name.strip()
    normalized = source.lower().replace("ё", "е")
    normalized = re.sub(r"[-_]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    m = re.match(r"^(\d+)\s*(series|серия)$", normalized)
    if m:
        return f"{m.group(1)} серия"
    m = re.match(r"^(\d+)\s*(series|серия)\s*gran\s*tourer$", normalized)
    if m:
        return f"{m.group(1)} серия Gran Tourer"
    m = re.match(r"^(\d+)\s*(series|серия)\s*active\s*tourer$", normalized)
    if m:
        return f"{m.group(1)} серия Active Tourer"
    m = re.match(r"^x\s*([0-9]+)$", normalized)
    if m:
        return f"X{m.group(1)}"
    m = re.match(r"^i\s*([0-9]+)$", normalized)
    if m:
        return f"i{m.group(1)}"
    return source


def _extract_power_hp(modification_name: str | None) -> int | None:
    if not modification_name:
        return None
    match = re.search(r"\((\d+)\s*[лl]\.?\s*[сc]\.?\)", modification_name, flags=re.IGNORECASE)
    if match:
        return _to_int(match.group(1))
    fallback = re.search(r"(\d{2,4})\s*[лl]\.?\s*[сc]\.?", modification_name, flags=re.IGNORECASE)
    if fallback:
        return _to_int(fallback.group(1))
    return None


def _extract_engine_volume(modification_name: str | None) -> float | None:
    if not modification_name:
        return None
    # Takes first decimal-looking token in the name, e.g. "2.0d xDrive ..."
    match = re.search(r"(\d+[.,]\d+)", modification_name)
    if not match:
        return None
    return _to_float(match.group(1))


def _extract_initial_state(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        payload = (script.string or script.get_text() or "").strip()
        if payload.startswith("{") and '"props"' in payload and "initialState" in payload:
            parsed = json.loads(payload)
            return parsed["props"]["initialState"]
    raise ValueError("Unable to find initialState in AV.BY page")


def _resolve_urls_file(path_arg: str) -> Path:
    candidate = Path(path_arg)
    if candidate.exists():
        return candidate

    launch_relative = LAUNCH_CWD / candidate
    if launch_relative.exists():
        return launch_relative

    backend_relative = ROOT_DIR / candidate
    if backend_relative.exists():
        return backend_relative

    raise FileNotFoundError(
        f"URLs file not found: '{path_arg}'. "
        f"Tried: '{candidate.resolve()}', '{launch_relative.resolve()}', and '{backend_relative.resolve()}'. "
        "Create the file with one AV.BY URL per line or pass an absolute path."
    )


def fetch_page(url: str, user_agent: str) -> str:
    response = requests.get(
        url,
        impersonate="chrome124",
        timeout=30,
        headers={
            "User-Agent": user_agent,
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    response.raise_for_status()
    return response.text


def fetch_modification_detail(modification_id: int, user_agent: str) -> dict[str, Any]:
    api_url = f"https://web-api.av.by/offer-types/cars/modifications-catalog/modifications/{modification_id}"
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = requests.get(
                api_url,
                impersonate="chrome124",
                timeout=30,
                headers={
                    "User-Agent": user_agent,
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://av.by/",
                    "Origin": "https://av.by",
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(0.3 * attempt)
    raise RuntimeError(f"modification detail fetch failed for id={modification_id}: {last_error}")


def _engine_volume_from_detail(detail: dict[str, Any], fallback_name: str | None) -> float | None:
    by_capacity = _to_float(detail.get("engineCapacity"))
    if by_capacity:
        return round(by_capacity / 1000, 3)
    return _extract_engine_volume(fallback_name)


def parse_generation_page(url: str, state: dict[str, Any], user_agent: str) -> list[dict[str, Any]]:
    catalog = state.get("catalog", {})
    landing = catalog.get("landing", {})
    generation_obj = landing.get("generation") or {}
    model_obj = generation_obj.get("model") or {}
    brand_obj = model_obj.get("parent") or {}

    make = brand_obj.get("name")
    model = _normalize_model_name(model_obj.get("name"))
    generation_name = generation_obj.get("name")
    generation_slug = generation_obj.get("slug")
    generation_from_slug, year_from, year_to = _extract_generation_from_slug(generation_slug)

    modifications = catalog.get("modifications") or []
    payloads: list[dict[str, Any]] = []
    for mod in modifications:
        if not isinstance(mod, dict):
            continue
        mod_id = mod.get("id")
        mod_name = mod.get("name")
        body_type = (mod.get("bodyType") or {}).get("name")
        fuel_type = (mod.get("engineType") or {}).get("label")
        transmission = (mod.get("gearBoxType") or {}).get("label")
        drivetrain = (mod.get("driveType") or {}).get("label")
        source_url = f"{url}#mod-{mod_id}" if mod_id is not None else url
        source_external_id = f"mod-{mod_id}" if mod_id is not None else url.rstrip("/").split("/")[-1]
        mod_detail: dict[str, Any] = {}
        if isinstance(mod_id, int):
            try:
                mod_detail = fetch_modification_detail(mod_id, user_agent=user_agent)
                source_url = f"{url}/modification/{mod_id}"
            except Exception:
                mod_detail = {}

        full_power = _to_int(mod_detail.get("maxPowerHP") or mod_detail.get("enginePower"))
        full_body_type = mod_detail.get("bodyType")
        full_fuel = mod_detail.get("fuel")
        full_transmission = mod_detail.get("gearBoxType")
        full_drive = mod_detail.get("driveType")
        full_country = mod_detail.get("countryBrandItem")
        full_steering = mod_detail.get("steeringWheel")

        payloads.append(
            {
                "make": make,
                "model": model,
                "generation": generation_name or generation_from_slug,
                "year_from": year_from,
                "year_to": year_to,
                "min_price_rub": None,
                "body_type": full_body_type or body_type,
                "export_country": full_country,
                "steering_wheel": full_steering,
                "fuel_type": full_fuel or fuel_type,
                "engine_power_hp": full_power or _extract_power_hp(mod_name),
                "engine_volume_l": _engine_volume_from_detail(mod_detail, mod_name),
                "drivetrain": full_drive or drivetrain,
                "transmission": full_transmission or transmission,
                "source_url": source_url,
                "source_external_id": source_external_id,
                "raw_specs": {
                    "landing": landing,
                    "modification": mod,
                    "modification_detail": mod_detail,
                },
            }
        )
    return payloads


def parse_model_page_generation_urls(state: dict[str, Any]) -> list[str]:
    catalog = state.get("catalog", {})
    landing = catalog.get("landing", {})
    if landing.get("type") != "model":
        return []
    model_obj = landing.get("model") or {}
    brand_obj = model_obj.get("parent") or {}
    brand_slug = brand_obj.get("slug")
    model_slug = model_obj.get("slug")
    if not brand_slug or not model_slug:
        return []

    urls: list[str] = []
    for generation in (catalog.get("generations") or []):
        generation_slug = (generation or {}).get("slug")
        if not generation_slug:
            continue
        urls.append(f"https://av.by/catalog/{brand_slug}_{model_slug}_{generation_slug}")
    return urls


def upsert_catalog_item(payload: dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        source_external_id = payload.get("source_external_id")
        if source_external_id:
            existing = (
                db.query(CatalogItem)
                .filter(CatalogItem.source_site == "av.by", CatalogItem.source_external_id == source_external_id)
                .first()
            )
        else:
            existing = (
                db.query(CatalogItem)
                .filter(CatalogItem.source_site == "av.by", CatalogItem.source_url == payload["source_url"])
                .first()
            )
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
        else:
            item = CatalogItem(
                **payload,
                source_site="av.by",
            )
            db.add(item)
        db.commit()
    finally:
        db.close()


def enrich_missing_spec_details(user_agent: str) -> None:
    db = SessionLocal()
    try:
        rows = db.query(CatalogItem).filter(CatalogItem.source_site == "av.by").all()
        total = 0
        enriched = 0
        skipped = 0
        failed = 0
        for item in rows:
            total += 1
            raw = item.raw_specs or {}
            detail = raw.get("modification_detail")
            if isinstance(detail, dict) and len(detail) > 10:
                skipped += 1
                continue

            ext = item.source_external_id or ""
            if not ext.startswith("mod-"):
                skipped += 1
                continue
            mod_id = _to_int(ext.replace("mod-", ""))
            if mod_id is None:
                skipped += 1
                continue

            try:
                mod_detail = fetch_modification_detail(mod_id, user_agent=user_agent)
            except Exception as exc:
                failed += 1
                print(f"enrich-fail: {item.id} ({ext}) -> {exc}")
                continue

            raw["modification_detail"] = mod_detail
            item.raw_specs = raw
            item.source_url = item.source_url or f"https://av.by/catalog/modification/{mod_id}"
            if mod_detail.get("fuel"):
                item.fuel_type = mod_detail.get("fuel")
            if mod_detail.get("gearBoxType"):
                item.transmission = mod_detail.get("gearBoxType")
            if mod_detail.get("driveType"):
                item.drivetrain = mod_detail.get("driveType")
            if mod_detail.get("bodyType"):
                item.body_type = mod_detail.get("bodyType")
            if mod_detail.get("countryBrandItem"):
                item.export_country = mod_detail.get("countryBrandItem")
            if mod_detail.get("steeringWheel"):
                item.steering_wheel = mod_detail.get("steeringWheel")
            if mod_detail.get("maxPowerHP") or mod_detail.get("enginePower"):
                item.engine_power_hp = _to_int(mod_detail.get("maxPowerHP") or mod_detail.get("enginePower"))
            item.engine_volume_l = _engine_volume_from_detail(mod_detail, item.model)
            enriched += 1
            if enriched % 25 == 0:
                db.commit()
        db.commit()
        print(f"enrich-summary: total={total} enriched={enriched} skipped={skipped} failed={failed}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import AV.BY detail pages into catalog_items")
    parser.add_argument(
        "--urls-file", required=True, help="Text file with AV.BY model/generation URLs (one per line)"
    )
    parser.add_argument("--user-agent", default="Mozilla/5.0", help="Browser User-Agent")
    parser.add_argument(
        "--enrich-missing",
        action="store_true",
        help="Backfill missing detailed specs for existing av.by rows in DB",
    )
    args = parser.parse_args()

    if args.enrich_missing:
        enrich_missing_spec_details(user_agent=args.user_agent)
        return

    urls_file = _resolve_urls_file(args.urls_file)
    with open(urls_file, "r", encoding="utf-8") as fh:
        seed_urls = [line.strip() for line in fh.readlines() if line.strip() and not line.strip().startswith("#")]

    queue = list(seed_urls)
    visited: set[str] = set()
    while queue:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            html = fetch_page(url, user_agent=args.user_agent)
            state = _extract_initial_state(html)
            landing_type = (((state.get("catalog") or {}).get("landing") or {}).get("type") or "").lower()

            if landing_type == "model":
                discovered = parse_model_page_generation_urls(state)
                for generation_url in discovered:
                    if generation_url not in visited:
                        queue.append(generation_url)
                print(f"expand: {url} -> {len(discovered)} generations")
                continue

            if landing_type == "generation":
                payloads = parse_generation_page(url, state, user_agent=args.user_agent)
                saved = 0
                for payload in payloads:
                    if not payload.get("make") or not payload.get("model"):
                        continue
                    upsert_catalog_item(payload)
                    saved += 1
                print(f"ok: {url} -> {saved} modifications")
                continue

            print(f"skip: unsupported landing type ({landing_type or 'unknown'}) {url}")
        except Exception as exc:
            print(f"fail: {url} -> {exc}")


if __name__ == "__main__":
    main()
