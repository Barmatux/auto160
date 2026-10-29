"""EU hybrid exclusions for sanctions: full HEV + PHEV are not importable.

Mild hybrids, e-Power, and unclear petrol+electric labels stay importable so we
do not drop exportable cars. Only flag powertrains we can confidently call
self-charging full HEV or plug-in hybrid.
"""

from __future__ import annotations

from typing import Any

from app.fuel_type_labels import is_hybrid_fuel, is_pure_electric_fuel, normalize_fuel_type_key

# Explicit mild / micro-hybrid wording in ads.
_MILD_MARKERS = (
    "mild",
    "mhev",
    "48v",
    "48 v",
    "12v hybrid",
    "12 v hybrid",
    "microhybrid",
    "micro-hybrid",
    "микрогибрид",
    "e-tec",
    "etec",
    "etsi",
    "e-tsi",
    "shvs",
    "soft hybrid",
    "bsg",
)

# Plug-in hybrids.
_PHEV_MARKERS = (
    "подключаем",
    "plug-in",
    "plug in",
    "plugin",
    "phev",
    "gte",
    "recharge",
    "twin engine",
    "twinengine",
    "4xe",
    "eq power",
    "eq-power",
    "eqpower",
    "e-hybrid",
    "ehybrid",
    "e hybrid",
)

# Series hybrid (Nissan) — not classic full HEV / not PHEV; leave for now.
_EPOWER_MARKERS = ("e-power", "epower", "e power")

# Toyota / Lexus / Honda e:HEV families that are always full HEV when hybrid-labelled.
_TOYOTA_FULL_MODELS = (
    "c-hr",
    "chr",
    "corolla",
    "yaris",
    "auris",
    "rav4",
    "rav 4",
    "camry",
    "highlander",
    "bZ",  # unused for hybrid fuel
    "prius",  # also model_exclusions
)

_LEXUS_FULL_MODELS = ("lbx", "ct", "ux", "es", "nx", "rx", "ls")

_HONDA_FULL_MODELS = ("cr-v", "crv", "hr-v", "hrv", "jazz", "accord")


def _norm(value: str | None) -> str:
    return normalize_fuel_type_key(value or "")


def _blob(*parts: str | None) -> str:
    return " ".join(_norm(p) for p in parts if p)


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(m in text for m in markers)


def _is_diesel_electric(engine_type: str) -> bool:
    return ("дизель" in engine_type or "diesel" in engine_type) and (
        "электр" in engine_type or "electric" in engine_type or "гибрид" in engine_type or "hybrid" in engine_type
    )


def is_phev_listing(
    *,
    brand: str | None = None,
    model: str | None = None,
    title: str | None = None,
    engine_type: str | None = None,
    engine_capacity_l: float | None = None,
    engine_power_hp: int | None = None,
    year: int | None = None,
) -> bool:
    """True only for confident plug-in hybrids (EU sanction scope)."""
    del year  # reserved for future year-gated rules
    if is_pure_electric_fuel(engine_type):
        return False
    if not is_hybrid_fuel(engine_type):
        return False

    brand_n = _norm(brand)
    model_n = _norm(model)
    title_n = _norm(title)
    engine_n = _norm(engine_type)
    text = _blob(brand, model, title, engine_type)
    liters = _to_float(engine_capacity_l)
    hp = _to_int(engine_power_hp)

    # Mild / e-Power stay exportable.
    if _has_any(text, _MILD_MARKERS):
        return False
    if _has_any(text, _EPOWER_MARKERS):
        return False

    # Explicit plug-in wording (incl. «Подключаемый гибрид», GTE, Recharge…).
    if _has_any(text, _PHEV_MARKERS):
        return True
    # Skoda / VW iV badge as its own token.
    padded = f" {text} "
    if " iv " in padded or " i.v " in padded or " i.v. " in padded:
        return True
    # MINI Cooper SE Countryman = PHEV even when fuel label is generic hybrid.
    if brand_n.startswith("mini") and ("countryman" in model_n or "countryman" in title_n):
        if "cooper se" in text or " se all4" in padded or " se " in padded:
            return True

    # Diesel+electric without plug-in markers ≈ 48V mild — keep.
    if _is_diesel_electric(engine_n):
        return False

    # VW Group 1.4 petrol hybrids in our feed are GTE / eHybrid / iV PHEV
    # (mild eTSI is 1.0 / 1.5).
    if brand_n.startswith("volkswagen") or brand_n.startswith("vw") or brand_n.startswith("skoda"):
        if liters is not None and 1.35 <= liters <= 1.45:
            if any(
                m in model_n or m in title_n
                for m in ("passat", "superb", "golf", "tiguan", "arteon", "kodiaq")
            ):
                return True

    # Mercedes CLA/A/B/GLA/GLB 250 e — ads often say CLA250 + petrol/electric.
    if brand_n.startswith("mercedes"):
        compact = (model_n + " " + title_n).replace(" ", "")
        if any(m in compact for m in ("cla250", "a250", "b250", "gla250", "glb250")):
            return True
        if any(m in model_n or m in title_n for m in ("cla 250", "a 250", "b 250", "gla 250", "glb 250")):
            return True

    # BMW Active Tourer 225e / 225xe is the PHEV; 218/223 are mild.
    if brand_n.startswith("bmw"):
        if "225" in model_n or "225" in title_n:
            return True
        if any(
            tok in model_n or tok in title_n
            for tok in ("25e", "30e", "225e", "225xe", "330e", "530e", "xdrive25e", "xdrive30e")
        ):
            return True

    # Audi A3 hybrid-labelled (e-tron / 40 TFSI e) — not sold as mild in our years.
    if brand_n.startswith("audi") and ("a3" in model_n or "a3" in title_n):
        return True

    # Volvo Recharge / Twin Engine already covered by markers; do not ban B-series mild.
    # Ambiguous XC40/V60 / BMW X1 / Sportage without markers — keep.
    _ = hp
    return False

def is_full_hybrid_listing(
    *,
    brand: str | None = None,
    model: str | None = None,
    title: str | None = None,
    engine_type: str | None = None,
    engine_capacity_l: float | None = None,
    engine_power_hp: int | None = None,
    year: int | None = None,
) -> bool:
    """True only for confident self-charging full HEV (EU sanction scope)."""
    if is_pure_electric_fuel(engine_type):
        return False
    if not is_hybrid_fuel(engine_type):
        return False

    brand_n = _norm(brand)
    model_n = _norm(model)
    title_n = _norm(title)
    engine_n = _norm(engine_type)
    text = _blob(brand, model, title, engine_type)
    liters = _to_float(engine_capacity_l)
    hp = _to_int(engine_power_hp)
    year_i = _to_int(year)

    # Keep exportable / out-of-scope classes.
    if _has_any(text, _MILD_MARKERS):
        return False
    if _has_any(text, _PHEV_MARKERS):
        return False
    if _has_any(text, _EPOWER_MARKERS):
        return False
    if _is_diesel_electric(engine_n):
        # EU diesel+electric without plug-in is almost always 48V mild.
        return False

    # Ford EcoBoost Hybrid = mild only.
    if brand_n.startswith("ford") and any(m in model_n or m in title_n for m in ("focus", "puma", "fiesta", "kuga")):
        return False

    # VW/Skoda mild eTSI / e-TEC when not GTE/iV (PHEV already excluded above).
    if brand_n.startswith("volkswagen") or brand_n.startswith("vw") or brand_n.startswith("skoda"):
        if any(m in model_n or m in title_n for m in ("golf", "t-roc", "troc", "octavia", "fabia", "kamiq", "scala")):
            return False

    # Stellantis 48V Hybrid / mild families — keep unless clearly labelled full (rare).
    if any(brand_n.startswith(b) for b in ("peugeot", "citroen", "opel", "jeep", "fiat", "alfa")):
        if liters is not None and liters <= 1.35:
            return False
        if any(m in model_n or m in title_n for m in ("avenger", "c3", "208", "2008", "308", "tonale")):
            return False

    # Suzuki: SHVS mild is common; do not ban on fuel label alone.
    if brand_n.startswith("suzuki"):
        return False

    # Nissan X-Trail: e-Power kept above; ~160 hp 1.5 = mild VC-Turbo — keep.
    if brand_n.startswith("nissan") and "x-trail" in model_n:
        if hp is not None and hp < 190:
            return False
        if liters is not None and 1.4 <= liters <= 1.6 and (hp is None or hp < 190):
            return False

    # Renault: distinguish E-Tech full vs 1.3 mild by displacement / power.
    if brand_n.startswith("renault"):
        if "arkana" in model_n or "arkana" in title_n:
            # Full E-Tech ≈ 1.6 / ~145; mild ≈ 1.3 / 140–160.
            if liters is not None and liters < 1.45:
                return False
            if liters is not None and liters >= 1.5:
                return True
            if hp is not None and 140 <= hp <= 150 and (liters is None or liters >= 1.5):
                return True
            return False
        if "captur" in model_n or "captur" in title_n:
            if liters is not None and liters < 1.45:
                return False
            if liters is not None and liters >= 1.5:
                return True
            return False
        if "austral" in model_n or "austral" in title_n:
            # Full E-Tech ≈ 1.2 / ~200; mild ≈ 1.3 / 140–160.
            if liters is not None and 1.25 < liters < 1.4:
                return False
            if hp is not None and hp >= 190:
                return True
            if liters is not None and liters <= 1.25 and (hp is None or hp >= 180):
                return True
            return False
        if "clio" in model_n or "symbioz" in model_n:
            if liters is not None and liters >= 1.5:
                return True
            return False
        # Unknown Renault hybrid — do not ban.
        return False

    # Dacia: Hybrid 140/155 full ≈ 1.6–1.8; 1.2 = mild (incl. LPG).
    if brand_n.startswith("dacia"):
        if liters is not None and liters <= 1.35:
            return False
        if liters is not None and liters >= 1.5:
            return True
        return False

    # Toyota: hybrid label ⇒ full HSD for these models.
    if brand_n.startswith("toyota"):
        if any(m in model_n or m in title_n for m in _TOYOTA_FULL_MODELS):
            return True
        # Other Toyota hybrid-labelled cars (Camry already in list) — still full HEV family.
        return True

    if brand_n.startswith("lexus"):
        if _has_any(text, _PHEV_MARKERS):
            return False
        if any(m in model_n or m in title_n for m in _LEXUS_FULL_MODELS):
            return True
        return True  # Lexus hybrid line is full / PHEV; PHEV already filtered.

    # Honda e:HEV / i-MMD.
    if brand_n.startswith("honda"):
        if "civic" in model_n or "civic" in title_n:
            # Pre-e:HEV IMA (~2013) is mild-ish — keep.
            if year_i is not None and year_i <= 2016:
                return False
            # Newer Civic e:HEV is full.
            if year_i is not None and year_i >= 2022:
                return True
            return False
        if any(m in model_n or m in title_n for m in _HONDA_FULL_MODELS):
            return True
        return False

    # Kia Niro HEV (not PHEV — already filtered).
    if brand_n.startswith("kia") and "niro" in model_n:
        return True

    # Hyundai dedicated HEV models.
    if brand_n.startswith("hyundai"):
        if any(m in model_n or m in title_n for m in ("ioniq", "elantra")):
            return True
        if "kona" in model_n or "kona" in title_n:
            # Kona Hybrid 1.6 ≈ full HEV; don't ban other Kona flavours without liters.
            if liters is None or (1.5 <= liters <= 1.7):
                return True
            return False
        # Tucson / Santa Fe / etc. can be mild, HEV, or PHEV — leave.
        return False

    # Everything else ambiguous (Sportage petrol hybrid, Ceed, BMW, Mercedes, …) — keep.
    return False


def is_banned_eu_hybrid_listing(
    *,
    brand: str | None = None,
    model: str | None = None,
    title: str | None = None,
    engine_type: str | None = None,
    engine_capacity_l: float | None = None,
    engine_power_hp: int | None = None,
    year: int | None = None,
) -> bool:
    """True for EU hybrids we must not publish: full HEV or PHEV."""
    kwargs = dict(
        brand=brand,
        model=model,
        title=title,
        engine_type=engine_type,
        engine_capacity_l=engine_capacity_l,
        engine_power_hp=engine_power_hp,
        year=year,
    )
    return is_phev_listing(**kwargs) or is_full_hybrid_listing(**kwargs)


def listing_is_full_hybrid(listing: Any) -> bool:
    return is_full_hybrid_listing(
        brand=getattr(listing, "brand", None),
        model=getattr(listing, "model", None),
        title=getattr(listing, "title", None),
        engine_type=getattr(listing, "engine_type", None),
        engine_capacity_l=getattr(listing, "engine_capacity_l", None),
        engine_power_hp=getattr(listing, "engine_power_hp", None),
        year=getattr(listing, "year", None),
    )


def listing_is_phev(listing: Any) -> bool:
    return is_phev_listing(
        brand=getattr(listing, "brand", None),
        model=getattr(listing, "model", None),
        title=getattr(listing, "title", None),
        engine_type=getattr(listing, "engine_type", None),
        engine_capacity_l=getattr(listing, "engine_capacity_l", None),
        engine_power_hp=getattr(listing, "engine_power_hp", None),
        year=getattr(listing, "year", None),
    )


def listing_is_banned_eu_hybrid(listing: Any) -> bool:
    return is_banned_eu_hybrid_listing(
        brand=getattr(listing, "brand", None),
        model=getattr(listing, "model", None),
        title=getattr(listing, "title", None),
        engine_type=getattr(listing, "engine_type", None),
        engine_capacity_l=getattr(listing, "engine_capacity_l", None),
        engine_power_hp=getattr(listing, "engine_power_hp", None),
        year=getattr(listing, "year", None),
    )
