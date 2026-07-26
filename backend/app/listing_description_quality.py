"""Detect damaged / salvage listings from description text."""

from __future__ import annotations

import re

# Strip our import footer before analysis
_FOOTER_RE = re.compile(
    r"\n+Источник:\s*av\.by.*$",
    re.IGNORECASE | re.DOTALL,
)

# Strong damage signals (case-insensitive)
_DAMAGE_PHRASES = [
    r"после\s+дтп",
    r"после\s+авар",
    r"авто\s+после\s+дтп",
    r"автомобил(?:ь|я)\s+после\s+дтп",
    r"\bбит(?:ый|ая|ое|ые|ым|ом|ую|ыми)\b",
    r"\bб/u\b",
    r"\bб\\u\b",
    r"аварийн",
    r"на\s+запчаст",
    r"под\s+восстановлен",
    r"требует\s+ремонт",
    r"нужен\s+ремонт",
    r"ремонтн(?:ые|ая|ое)\s+и\s+покрасочн",
    r"геометри(?:я|и)\s+кузова\s+не\s+нарушена",
    r"поврежден(?:ы|а|о|)\s",
    r"повреждены\s+силов",
    r"силов(?:ые|ой)\s+элемент",
    r"подушк(?:и|а)\s+стрел",
    r"airbag",
    r"не\s+на\s+ходу",
    r"утоплен",
    r"утопл",
    r"salvage",
    r"total\s*loss",
    r"аукцион\s+по\s+продаже\s+автомобил",  # Vigo Finance salvage auctions
    r"лот\s+№",
    r"удар\s+был",
    r"пострадал(?:а|и|)\s",
    r"капот\s+и\s+передн",
    r"оптика\s+отсутств",
    r"лобов(?:ое|ая)\s+стекло\s+разб",
    r"бампер,?\s*крыло,?\s*капот",
    r"ходов(?:ая|ой)\s+не\s+пострадал",  # body likely did
    r"сработала\s+фронтальн",
    r"стружк(?:а|и)\s+в\s+поддон",
    r"маслян(?:ого|ый)\s+насос",
    r"открутилась\s+гайк",
    r"двигатель\s+забит",
    r"коробк(?:а|и)\s+требует",
    r"коробк(?:а|и)\s+бит",
]

# Negation: "без дтп", "не битый" — suppress nearby damage hits
_NEGATION_RE = re.compile(
    r"(?:"
    r"без\s+дтп|"
    r"без\s+авар|"
    r"не\s+бит(?:ый|ая|ое|ые)?|"
    r"не\s+б/u|"
    r"не\s+было\s+дтп|"
    r"кузов\s+без\s+дтп|"
    r"ни\s+одного\s+дтп|"
    r"0\s+дтп"
    r")",
    re.IGNORECASE,
)

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _DAMAGE_PHRASES]


def _clean_description(text: str | None) -> str:
    if not text:
        return ""
    body = _FOOTER_RE.sub("", text.strip())
    return body


def describe_damage_flags(text: str | None) -> list[str]:
    """Return matched damage phrase labels (empty if clean or negated)."""
    body = _clean_description(text)
    if not body:
        return []

    hits: list[str] = []
    lower = body.lower()
    for pat in _COMPILED:
        for match in pat.finditer(body):
            start = match.start()
            window = lower[max(0, start - 40) : start]
            if _NEGATION_RE.search(window):
                continue
            hits.append(pat.pattern)
            break
    return hits


def is_damaged_listing(text: str | None) -> bool:
    return bool(describe_damage_flags(text))


def is_clean_listing(text: str | None) -> bool:
    return not is_damaged_listing(text)
