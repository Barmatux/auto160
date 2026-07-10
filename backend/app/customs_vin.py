"""Lookup VIN in the Belarus customs imported-vehicles database (GTK).

Database 1 (ajax_1): personal import, released to free circulation.
Official page: https://www.customs.gov.by/baza-dannykh-vvezyennogo-avtotransporta/
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from curl_cffi import requests
from sqlalchemy.orm import Session

from app.models import VinCustomsCheck

CUSTOMS_BASE_URL = "https://www.customs.gov.by/baza-dannykh-vvezyennogo-avtotransporta/"
CUSTOMS_SOURCE_PAGE = CUSTOMS_BASE_URL
CACHE_TTL = timedelta(days=7)

DATABASE_PERSONAL = "personal_free_circulation"
DATABASE_INTERNAL = "internal_consumption"

DATABASE_AJAX: dict[str, str] = {
    DATABASE_PERSONAL: "1",
    DATABASE_INTERNAL: "2",
}

DATABASE_LABELS: dict[str, str] = {
    DATABASE_PERSONAL: "Физлица, свободное обращение (база 1)",
    DATABASE_INTERNAL: "Внутреннее потребление (база 2)",
}


class CustomsVinError(Exception):
    pass


@dataclass
class CustomsVinResult:
    vin: str
    database: str
    found: bool
    release_date: str | None
    raw_fields: dict[str, str] = field(default_factory=dict)
    source_url: str = CUSTOMS_SOURCE_PAGE
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    cached: bool = False
    parse_error: str | None = None


def normalize_vin(vin: str | None) -> str:
    if not vin:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", vin).upper()


def vin_is_valid(vin: str) -> bool:
    if len(vin) != 17:
        return False
    if any(ch in vin for ch in ("I", "O", "Q")):
        return False
    return bool(re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", vin))


def _decode_response(content: bytes) -> str:
    for encoding in ("utf-8", "cp1251", "windows-1251"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _fetch_customs_html(vin: str, database: str) -> str:
    ajax_key = DATABASE_AJAX.get(database)
    if not ajax_key:
        raise CustomsVinError(f"Unknown customs database: {database}")

    params = urlencode(
        {
            f"ajax_{ajax_key}": "y",
            "query": vin,
            "submit": "Искать",
        }
    )
    url = f"{CUSTOMS_BASE_URL}?{params}"
    try:
        response = requests.post(
            url,
            impersonate="chrome",
            timeout=45,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Auto160/1.0; +https://auto160)"},
        )
    except Exception as exc:
        raise CustomsVinError(f"Не удалось связаться с сайтом таможни: {exc}") from exc

    if response.status_code >= 400:
        raise CustomsVinError(f"Сайт таможни вернул HTTP {response.status_code}")

    return _decode_response(response.content)


def _parse_message_html(html: str) -> tuple[bool, dict[str, str], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    bold = soup.find("b")
    if bold:
        message = bold.get_text(" ", strip=True)
        lowered = message.lower()
        if "ничего не найдено" in lowered:
            return False, {}, None
        if "введите корректный" in lowered:
            return False, {}, message

    table = soup.find("table")
    if table is None:
        if bold:
            return False, {}, bold.get_text(" ", strip=True)
        text = soup.get_text(" ", strip=True)
        if text:
            return False, {}, text
        return False, {}, "Пустой ответ таможни"

    fields = _parse_table(table)
    if fields:
        return True, fields, None
    return False, {}, "Не удалось разобрать таблицу ответа таможни"


def _parse_table(table) -> dict[str, str]:
    rows = table.find_all("tr")
    if not rows:
        return {}

    header_cells = rows[0].find_all(["th", "td"])
    if rows[0].find("th") and len(header_cells) >= 2:
        headers = [cell.get_text(" ", strip=True) for cell in header_cells]
        fields: dict[str, str] = {}
        for row in rows[1:]:
            values = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
            for header, value in zip(headers, values):
                if header and value:
                    fields[header] = value
        return fields

    fields = {}
    for row in rows:
        cells = row.find_all(["th", "td"])
        if len(cells) >= 2:
            key = cells[0].get_text(" ", strip=True)
            value = cells[1].get_text(" ", strip=True)
            if key and value:
                fields[key] = value
    return fields


def _extract_release_date(fields: dict[str, str]) -> str | None:
    for key, value in fields.items():
        if "дата" in key.lower() and value.strip():
            return value.strip()
    for value in fields.values():
        if re.search(r"\d{2}[./]\d{2}[./]\d{4}", value):
            return value.strip()
    return None


def _row_to_result(row: VinCustomsCheck) -> CustomsVinResult:
    raw_fields = row.raw_fields if isinstance(row.raw_fields, dict) else {}
    return CustomsVinResult(
        vin=row.vin,
        database=row.database,
        found=row.found,
        release_date=row.release_date,
        raw_fields={str(k): str(v) for k, v in raw_fields.items()},
        source_url=row.source_url or CUSTOMS_SOURCE_PAGE,
        checked_at=row.checked_at.replace(tzinfo=UTC) if row.checked_at.tzinfo is None else row.checked_at,
        cached=True,
        parse_error=row.error_message,
    )


def _persist_result(db: Session, result: CustomsVinResult) -> VinCustomsCheck:
    row = (
        db.query(VinCustomsCheck)
        .filter(VinCustomsCheck.vin == result.vin, VinCustomsCheck.database == result.database)
        .first()
    )
    payload: dict[str, Any] = {
        "found": result.found,
        "release_date": result.release_date,
        "raw_fields": result.raw_fields,
        "source_url": result.source_url,
        "error_message": result.parse_error,
        "checked_at": result.checked_at.replace(tzinfo=None),
    }
    if row is None:
        row = VinCustomsCheck(vin=result.vin, database=result.database, **payload)
        db.add(row)
    else:
        for key, value in payload.items():
            setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def lookup_customs_vin(
    db: Session,
    vin: str,
    *,
    database: str = DATABASE_PERSONAL,
    force_refresh: bool = False,
) -> CustomsVinResult:
    normalized = normalize_vin(vin)
    if not vin_is_valid(normalized):
        raise CustomsVinError("Некорректный VIN. Используй 17 символов без I, O, Q.")

    if database not in DATABASE_AJAX:
        raise CustomsVinError(f"Неизвестная база таможни: {database}")

    if not force_refresh:
        cached = (
            db.query(VinCustomsCheck)
            .filter(VinCustomsCheck.vin == normalized, VinCustomsCheck.database == database)
            .first()
        )
        if cached and cached.checked_at >= datetime.utcnow() - CACHE_TTL:
            return _row_to_result(cached)

    html = _fetch_customs_html(normalized, database)
    found, fields, parse_error = _parse_message_html(html)
    result = CustomsVinResult(
        vin=normalized,
        database=database,
        found=found,
        release_date=_extract_release_date(fields) if found else None,
        raw_fields=fields,
        parse_error=parse_error,
    )
    _persist_result(db, result)
    return result


def report_rows(result: CustomsVinResult) -> dict[str, str]:
    rows: dict[str, str] = {
        "VIN": result.vin,
        "База ГТК": DATABASE_LABELS.get(result.database, result.database),
    }
    if result.found:
        rows["Статус"] = "Найдено в базе таможни"
        if result.release_date:
            rows["Дата выпуска в РБ"] = result.release_date
        reserved = set(rows.keys())
        for key, value in result.raw_fields.items():
            if key not in reserved and value:
                rows[key] = value
    else:
        rows["Статус"] = "Не найдено в этой базе"
        rows["Примечание"] = (
            "Отсутствие записи не означает нелегальный ввоз. "
            "Авто могло быть оформлено по другой процедуре или ещё не попало в выгрузку."
        )
        if result.parse_error:
            rows["Ответ таможни"] = result.parse_error

    checked = result.checked_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    rows["Проверено"] = checked
    if result.cached:
        rows["Кэш"] = "да (повторный запрос к ГТК не выполнялся)"
    rows["Официальный источник"] = result.source_url
    return rows
