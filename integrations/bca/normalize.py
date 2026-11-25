"""Map a BCA search row into auction, lot, and document records."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

BASE = "https://ee.bca-europe.com"
_ASP_DATE = re.compile(r"/Date\((-?\d+)\)/")


def parse_asp_date(value: Any) -> datetime | None:
    if value is None:
        return None
    match = _ASP_DATE.search(str(value))
    if not match:
        return None
    return datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc)


def absolute_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("//"):
        return "https:" + text
    if text.startswith("/"):
        return BASE + text
    return text


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    digits = re.sub(r"[^\d]", "", str(value))
    if not digits:
        return None
    return int(digits)


def lot_from_row(row: dict[str, Any]) -> dict[str, Any]:
    registration_date = _text(row.get("registration_date") or row.get("RegistrationDate"))
    if registration_date.endswith("Z") and "T" not in registration_date:
        registration_date = registration_date.replace(" ", "T")
    return {
        "vehicle_id": _text(row.get("vehicle_id") or row.get("VehicleId")),
        "lot_id": _text(row.get("lot_id") or row.get("LotId")),
        "lot_number": _text(row.get("lot_number") or row.get("LotNumber")),
        "lot_url": absolute_url(row.get("lot_url") or row.get("ViewLotUrl")),
        "headline": _text(row.get("headline") or row.get("VehicleInfoHeadline")),
        "make": _text(row.get("make") or row.get("Make")),
        "model": _text(row.get("model") or row.get("Model")),
        "derivative": _text(row.get("derivative") or row.get("Derivative")),
        "vin": _text(row.get("vin") or row.get("VIN")),
        "mileage_km": _int(row.get("mileage") if "mileage" in row else row.get("Mileage")),
        "registration": _text(row.get("registration") or row.get("RegistrationNumber")),
        "registration_date": registration_date,
        "fuel_type": _text(row.get("fuel_type") or row.get("FuelType")),
        "power_kw": _int(row.get("power_kw") if "power_kw" in row else row.get("PowerKw")),
        "power_ps": _int(row.get("power_ps") if "power_ps" in row else row.get("PowerPs")),
        "sale_location": _text(row.get("sale_location") or row.get("SaleLocation")),
        "vehicle_location": _text(row.get("vehicle_location") or row.get("VehicleLocation")),
        "image_url": absolute_url(row.get("image_url") or row.get("ImageUrl")),
        "bid_now": _text(row.get("bid_now") if "bid_now" in row else row.get("BidNow")),
        "buy_now": _text(row.get("buy_now") if "buy_now" in row else row.get("BuyNow")),
        "condition_report_url": absolute_url(
            row.get("condition_report_url") or row.get("ConditionReportUrl")
        ),
        "mechanical_report_url": absolute_url(
            row.get("mechanical_report_url") or row.get("MechanicalReportUrl")
        ),
        "sale_id": _text(row.get("sale_id") or row.get("SaleId")),
        "sale_name": _text(row.get("sale_name") or row.get("SaleName")),
        "sale_country": _text(row.get("sale_country") or row.get("SaleCountry")),
        "sale_type": _text(row.get("sale_type") or row.get("SaleType")),
        "sale_channel": _text(row.get("sale_channel") or row.get("SaleChannel")),
        "starts_at": parse_asp_date(row.get("sale_date") or row.get("SaleDate")),
        "catalogue_url": absolute_url(row.get("catalogue_url") or row.get("FullDayCatalogueUrl")),
        "section_url": absolute_url(row.get("section_url") or row.get("PrintSaleSectionUrl")),
    }


def auction_from_lots(lots: list[dict[str, Any]], *, can_view_pricing: bool) -> dict[str, Any]:
    if not lots:
        raise ValueError("auction has no lots")
    first = lots[0]
    return {
        "sale_id": first["sale_id"],
        "name": first["sale_name"],
        "country": first["sale_country"],
        "sale_type": first["sale_type"],
        "channel": first["sale_channel"],
        "location": first["sale_location"],
        "starts_at": first["starts_at"],
        "catalogue_url": first["catalogue_url"],
        "section_url": first["section_url"],
        "lot_count": len(lots),
        "can_view_pricing": can_view_pricing,
    }
