"""RF customs duty + recycling fee (утильсбор) calculator for passenger cars (M1).

Rates reflect EAEU personal-use duty bands and PP RF No. 1291 as amended by
PP RF No. 1713 (in force from 1 Dec 2025; 2026 commercial coefficients).
Indicative only — confirm against FTS / current regulations for a specific import.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Literal

ImporterKind = Literal["personal", "commercial"]
EngineKind = Literal["ice", "electric"]
CurrencyCode = Literal["RUB", "EUR", "USD", "BYN"]

UTIL_BASE_RATE_RUB = 20_000.0
PREFERENTIAL_HP_MAX = 160.0
PREFERENTIAL_CC_MAX = 3000.0
PREFERENTIAL_EV_HP_MAX = 80.0
PREFERENTIAL_K_NEW = 0.17
PREFERENTIAL_K_OLD = 0.26

# Commercial util coefficients 2026: (k_new, k_old) by volume band + power band.
# Volume bands: cc_max exclusive upper except last.
# Power bands: hp_max inclusive upper for that row.
_COMMERCIAL_BY_VOLUME_POWER: dict[str, list[tuple[float, float, float]]] = {
    # hp_max, k_new, k_old
    "cc_1001_2000": [
        (160, 40.04, 70.44),
        (190, 45.00, 74.64),
        (220, 47.64, 79.20),
        (250, 50.52, 83.88),
        (280, 57.12, 91.92),
        (310, 64.56, 100.56),
        (340, 72.96, 110.16),
        (370, 83.16, 120.60),
        (400, 94.80, 132.00),
        (430, 108.00, 144.60),
        (460, 123.24, 158.40),
        (500, 140.40, 173.40),
        (10_000, 160.08, 189.84),
    ],
    "cc_2001_3000": [
        (160, 93.78, 165.00),
        (190, 112.52, 170.36),
        (220, 115.34, 172.80),
        (250, 118.20, 175.08),
        (280, 120.12, 177.60),
        (310, 126.00, 183.00),
        (10_000, 131.04, 188.52),
    ],
    "cc_le_1000": [
        (160, 17.00, 29.90),
        (190, 22.00, 36.00),
        (220, 26.00, 42.00),
        (10_000, 33.37, 58.70),
    ],
    "cc_3001_3500": [
        (160, 107.67, 189.50),
        (190, 120.00, 200.00),
        (220, 130.00, 210.00),
        (10_000, 140.00, 220.00),
    ],
    "cc_gt_3500": [
        (160, 137.12, 241.30),
        (190, 150.00, 255.00),
        (220, 165.00, 270.00),
        (10_000, 180.00, 290.00),
    ],
    "electric": [
        (80, 40.04, 70.44),
        (160, 45.00, 74.64),
        (220, 57.12, 91.92),
        (310, 72.96, 110.16),
        (10_000, 108.00, 144.60),
    ],
}

# Personal-use ICE duty: (cc_max inclusive, pct or None, eur_per_cc)
# age: under3 | from3to5 | over5
_DUTY_PERSONAL: dict[str, list[tuple[int, float | None, float]]] = {
    "under3": [
        (1000, 0.54, 2.5),
        (1500, 0.48, 3.5),
        (1800, 0.48, 5.5),
        (2300, 0.48, 7.5),
        (3000, 0.48, 12.0),
        (10_000_000, 0.48, 15.5),
    ],
    "from3to5": [
        (1000, 0.54, 5.0),
        (1500, 0.54, 7.0),
        (1800, 0.54, 8.5),
        (2300, 0.54, 12.0),
        (3000, 0.54, 15.0),
        (10_000_000, 0.54, 20.0),
    ],
    "over5": [
        (1000, None, 5.0),
        (1500, None, 7.0),
        (1800, None, 8.5),
        (2300, None, 12.0),
        (3000, None, 15.0),
        (10_000_000, None, 20.0),
    ],
}

# Customs clearance fee by customs value in RUB (PP RF fee schedule 2026).
_CLEARANCE_FEES: list[tuple[float, float]] = [
    (200_000, 1_231),
    (450_000, 2_462),
    (1_200_000, 4_924),
    (2_700_000, 13_541),
    (4_200_000, 18_465),
    (5_500_000, 21_344),
    (float("inf"), 49_240),
]


@dataclass(frozen=True)
class CustomsCalcInput:
    year: int
    engine_cc: float
    power_hp: float
    price: float
    currency: CurrencyCode = "EUR"
    importer: ImporterKind = "personal"
    engine_kind: EngineKind = "ice"
    as_of: date | None = None


@dataclass(frozen=True)
class CustomsCalcResult:
    ok: bool
    error: str | None
    age_years: float | None
    age_band: str | None
    customs_value_rub: float | None
    duty_rub: float | None
    clearance_fee_rub: float | None
    util_sbor_rub: float | None
    util_coefficient: float | None
    util_preferential: bool
    total_rub: float | None
    eur_rub: float | None
    usd_rub: float | None
    byn_rub: float | None
    notes: list[str]
    breakdown: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def car_age_years(year: int, as_of: date | None = None) -> float:
    today = as_of or date.today()
    if year < 1950 or year > today.year + 1:
        raise ValueError("Некорректный год выпуска")
    # Approximate age from mid-year of manufacture (common customs practice for bands).
    months = (today.year - year) * 12 + (today.month - 6)
    return max(0.0, months / 12.0)


def age_band(age_years: float) -> str:
    if age_years < 3:
        return "under3"
    if age_years < 5:
        return "from3to5"
    return "over5"


def util_age_is_new(age_years: float) -> bool:
    """Утильсбор: «новые» — до 3 лет с даты выпуска."""
    return age_years < 3


def _volume_key(engine_cc: float, engine_kind: EngineKind) -> str:
    if engine_kind == "electric":
        return "electric"
    if engine_cc <= 1000:
        return "cc_le_1000"
    if engine_cc <= 2000:
        return "cc_1001_2000"
    if engine_cc <= 3000:
        return "cc_2001_3000"
    if engine_cc <= 3500:
        return "cc_3001_3500"
    return "cc_gt_3500"


def _lookup_row(rows: list[tuple[float, float, float]], power_hp: float) -> tuple[float, float]:
    for hp_max, k_new, k_old in rows:
        if power_hp <= hp_max:
            return k_new, k_old
    return rows[-1][1], rows[-1][2]


def preferential_util_eligible(
    *,
    importer: ImporterKind,
    power_hp: float,
    engine_cc: float,
    engine_kind: EngineKind,
) -> bool:
    if importer != "personal":
        return False
    if engine_kind == "electric":
        return power_hp <= PREFERENTIAL_EV_HP_MAX
    return power_hp <= PREFERENTIAL_HP_MAX and engine_cc <= PREFERENTIAL_CC_MAX


def util_coefficient(
    *,
    importer: ImporterKind,
    age_years: float,
    power_hp: float,
    engine_cc: float,
    engine_kind: EngineKind,
) -> tuple[float, bool]:
    is_new = util_age_is_new(age_years)
    if preferential_util_eligible(
        importer=importer,
        power_hp=power_hp,
        engine_cc=engine_cc,
        engine_kind=engine_kind,
    ):
        return (PREFERENTIAL_K_NEW if is_new else PREFERENTIAL_K_OLD), True

    key = _volume_key(engine_cc, engine_kind)
    rows = _COMMERCIAL_BY_VOLUME_POWER[key]
    k_new, k_old = _lookup_row(rows, power_hp)
    return (k_new if is_new else k_old), False


def _duty_row(band: str, engine_cc: float) -> tuple[float | None, float]:
    for cc_max, pct, eur_per_cc in _DUTY_PERSONAL[band]:
        if engine_cc <= cc_max:
            return pct, eur_per_cc
    last = _DUTY_PERSONAL[band][-1]
    return last[1], last[2]


def customs_duty_rub(
    *,
    age_years: float,
    engine_cc: float,
    customs_value_rub: float,
    eur_rub: float,
    engine_kind: EngineKind,
    power_hp: float,
) -> tuple[float, str]:
    if engine_kind == "electric":
        # Personal EV: 15% of customs value, not less than 12.5 EUR per kW.
        kw = power_hp / 1.35962
        pct_part = customs_value_rub * 0.15
        min_part = 12.5 * kw * eur_rub
        duty = max(pct_part, min_part)
        return duty, "Электромобиль: 15% стоимости, но не менее 12,5 €/кВт"

    band = age_band(age_years)
    pct, eur_per_cc = _duty_row(band, engine_cc)
    min_part = eur_per_cc * engine_cc * eur_rub
    if pct is None:
        return min_part, f"Единая ставка {eur_per_cc:g} €/см³ (возраст ≥ 5 лет)"
    pct_part = customs_value_rub * pct
    duty = max(pct_part, min_part)
    return duty, f"{pct * 100:.0f}% стоимости, но не менее {eur_per_cc:g} €/см³"


def clearance_fee_rub(customs_value_rub: float) -> float:
    for limit, fee in _CLEARANCE_FEES:
        if customs_value_rub <= limit:
            return fee
    return _CLEARANCE_FEES[-1][1]


def price_to_rub(
    price: float,
    currency: CurrencyCode,
    *,
    eur_rub: float,
    usd_rub: float,
    byn_rub: float,
) -> float:
    if price < 0:
        raise ValueError("Цена не может быть отрицательной")
    if currency == "RUB":
        return price
    if currency == "EUR":
        return price * eur_rub
    if currency == "USD":
        return price * usd_rub
    if currency == "BYN":
        return price * byn_rub
    raise ValueError("Неизвестная валюта")


def calculate_customs(
    payload: CustomsCalcInput,
    *,
    eur_rub: float,
    usd_rub: float,
    byn_rub: float,
) -> CustomsCalcResult:
    notes: list[str] = [
        "Расчёт справочный по ставкам ЕАЭС / ПП РФ № 1291 (ред. № 1713). "
        "Не является официальным заключением таможни.",
    ]
    try:
        if payload.engine_cc <= 0 and payload.engine_kind == "ice":
            raise ValueError("Укажите объём двигателя")
        if payload.power_hp <= 0:
            raise ValueError("Укажите мощность двигателя")
        if eur_rub <= 0 or usd_rub <= 0 or byn_rub <= 0:
            raise ValueError("Недоступны курсы валют для расчёта")

        age = car_age_years(payload.year, payload.as_of)
        band = age_band(age)
        customs_value = price_to_rub(
            payload.price,
            payload.currency,
            eur_rub=eur_rub,
            usd_rub=usd_rub,
            byn_rub=byn_rub,
        )
        duty, duty_note = customs_duty_rub(
            age_years=age,
            engine_cc=max(payload.engine_cc, 0),
            customs_value_rub=customs_value,
            eur_rub=eur_rub,
            engine_kind=payload.engine_kind,
            power_hp=payload.power_hp,
        )
        notes.append(duty_note)

        fee = clearance_fee_rub(customs_value)
        k, preferential = util_coefficient(
            importer=payload.importer,
            age_years=age,
            power_hp=payload.power_hp,
            engine_cc=max(payload.engine_cc, 0),
            engine_kind=payload.engine_kind,
        )
        util = UTIL_BASE_RATE_RUB * k
        if preferential:
            notes.append(
                "Льготный утильсбор для физлица (до 160 л.с., объём до 3 л, "
                "личное пользование, без перепродажи 12 мес.)."
            )
        else:
            notes.append("Коммерческий коэффициент утильсбора (база 20 000 ₽ × коэффициент).")

        if payload.importer == "commercial":
            notes.append(
                "Для коммерческого ввоза отдельно начисляются НДС и акциз — "
                "в этом калькуляторе они не включены."
            )

        total = duty + fee + util
        return CustomsCalcResult(
            ok=True,
            error=None,
            age_years=round(age, 2),
            age_band=band,
            customs_value_rub=round(customs_value, 2),
            duty_rub=round(duty, 2),
            clearance_fee_rub=round(fee, 2),
            util_sbor_rub=round(util, 2),
            util_coefficient=k,
            util_preferential=preferential,
            total_rub=round(total, 2),
            eur_rub=round(eur_rub, 4),
            usd_rub=round(usd_rub, 4),
            byn_rub=round(byn_rub, 4),
            notes=notes,
            breakdown={
                "duty_rule": duty_note,
                "importer": payload.importer,
                "engine_kind": payload.engine_kind,
                "year": payload.year,
                "engine_cc": payload.engine_cc,
                "power_hp": payload.power_hp,
            },
        )
    except ValueError as exc:
        return CustomsCalcResult(
            ok=False,
            error=str(exc),
            age_years=None,
            age_band=None,
            customs_value_rub=None,
            duty_rub=None,
            clearance_fee_rub=None,
            util_sbor_rub=None,
            util_coefficient=None,
            util_preferential=False,
            total_rub=None,
            eur_rub=round(eur_rub, 4) if eur_rub else None,
            usd_rub=round(usd_rub, 4) if usd_rub else None,
            byn_rub=round(byn_rub, 4) if byn_rub else None,
            notes=notes,
            breakdown={},
        )
