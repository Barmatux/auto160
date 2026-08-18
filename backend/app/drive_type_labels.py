"""Short drive labels for catalog modification tables."""

from __future__ import annotations


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
