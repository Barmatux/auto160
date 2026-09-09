"""Short drive labels for catalog modification tables."""

from __future__ import annotations

from sqlalchemy import ColumnElement, or_


def normalize_drive_display_label(value: str | None) -> str:
    if value is None:
        return "—"
    trimmed = value.strip()
    if not trimmed:
        return "—"

    key = trimmed.lower().replace("ё", "е")
    if "полный" in key or key in {"awd", "4wd", "4x4"}:
        return "Полный"
    if key.startswith("перед") or key in {"fwd", "front"}:
        return "Передний"
    if key.startswith("зад") or key in {"rwd", "rear"}:
        return "Задний"

    return trimmed[0].upper() + trimmed[1:]


def drive_type_sql_predicate(column, value: str | None) -> ColumnElement[bool] | None:
    """Match listing drive_type values to a catalog drivetrain label."""
    label = normalize_drive_display_label(value)
    if not label or label == "—":
        return None
    key = label.lower().replace("ё", "е")
    if key == "полный":
        return or_(
            column.ilike("%полн%"),
            column.ilike("%awd%"),
            column.ilike("%4wd%"),
            column.ilike("%4x4%"),
        )
    if key == "передний":
        return or_(column.ilike("%перед%"), column.ilike("%fwd%"), column.ilike("%front%"))
    if key == "задний":
        return or_(column.ilike("%зад%"), column.ilike("%rwd%"), column.ilike("%rear%"))
    return column.ilike(label)
