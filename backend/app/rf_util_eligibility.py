"""RF preferential util-sbor eligibility verdict for the public Проверка page."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Literal

from app.catalog_engine_cc import engine_capacity_cc_from_liters
from app.listing_import_age import (
    IMPORT_AGE_OVER_10M_MONTHS,
    IMPORT_AGE_RF_MONTHS,
    add_calendar_months,
)
from app.vin_analytics import parse_filter_date

PREFERENTIAL_HP_MAX = 160.0
PREFERENTIAL_CC_MAX = 3000

VerdictTone = Literal["green", "yellow", "red", "neutral"]
VerdictCode = Literal[
    "pass_ready",
    "pass_after_date",
    "fail_power",
    "fail_volume",
    "fail_until_date",
    "no_date",
    "no_power",
    "vin_only",
    "not_found",
    "customs_unavailable",
]


@dataclass(frozen=True)
class RfUtilVerdict:
    code: VerdictCode
    tone: VerdictTone
    title: str
    detail: str | None = None
    eligible_from_date: str | None = None  # DD.MM.YYYY
    cta: Literal["inspect", "select", "notify", "none"] = "none"
    # Per-parameter preferential checks: True=ok, False=fail, None=unknown/n/a
    checks: dict[str, bool | None] | None = None
    reasons: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def not_found_reasons(*, input_kind: str) -> list[str]:
    first = (
        "в объявлении указан неверный VIN (ошибка или намеренно)"
        if input_kind == "avby_url"
        else "неправильно введён VIN"
    )
    return [
        first,
        "автомобиль продан новым на территории Беларуси",
        "автомобиль ввезён из РФ",
        "автомобиль оформлен в особом порядке без растаможки на территории ЕАЭС",
    ]


def format_display_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def eligible_from_date_label(release_date_raw: str | None) -> str | None:
    parsed = parse_filter_date(release_date_raw)
    if parsed is None:
        return None
    return format_display_date(add_calendar_months(parsed, IMPORT_AGE_RF_MONTHS))


def resolve_engine_cc(*, engine_cc: float | int | None = None, engine_capacity_l: float | None = None) -> int | None:
    if engine_cc is not None:
        try:
            cc = int(round(float(engine_cc)))
        except (TypeError, ValueError):
            cc = None
        else:
            if 0 < cc <= 20000:
                return cc
    return engine_capacity_cc_from_liters(engine_capacity_l)


def months_since_release(release_date_raw: str | None, *, today: date | None = None) -> float | None:
    parsed = parse_filter_date(release_date_raw)
    if parsed is None:
        return None
    today_value = today or date.today()
    days = (today_value - parsed).days
    return days / 30.4375


def build_param_checks(
    *,
    release_date: str | None,
    power_hp: float | None,
    engine_cc: int | None,
    today: date,
) -> dict[str, bool | None]:
    """Independent preferential checks for UI markers."""
    power_ok: bool | None
    if power_hp is None or power_hp <= 0:
        power_ok = None
    else:
        power_ok = power_hp <= PREFERENTIAL_HP_MAX

    volume_ok: bool | None
    if engine_cc is None:
        volume_ok = None
    else:
        volume_ok = engine_cc <= PREFERENTIAL_CC_MAX

    date_ok: bool | None = None
    parsed = parse_filter_date(release_date)
    if parsed is not None:
        cutoff_12 = add_calendar_months(today, -IMPORT_AGE_RF_MONTHS)
        date_ok = parsed <= cutoff_12

    return {
        "import_date": date_ok,
        "power": power_ok,
        "volume": volume_ok,
    }


def evaluate_rf_util_eligibility(
    *,
    release_date: str | None,
    power_hp: float | None,
    engine_cc: int | None = None,
    engine_capacity_l: float | None = None,
    input_kind: str = "avby_url",
    customs_found: bool | None = None,
    customs_status: str | None = None,
    today: date | None = None,
) -> RfUtilVerdict:
    """Classify a car for preferential RF util-sbor messaging.

    Rules (av.by URL path with specs):
    1. power ≤160, cc ≤3000, age ≥12m → green pass
    2. power ≤160, cc ≤3000, age 10–12m → yellow after (release+1y)
    3. power >160 or cc >3000 → red fail (reason)
    4. power ≤160, cc ≤3000, age <10m → red until (release+1y)
    """
    today_value = today or date.today()
    cc = resolve_engine_cc(engine_cc=engine_cc, engine_capacity_l=engine_capacity_l)
    checks = build_param_checks(
        release_date=release_date,
        power_hp=power_hp,
        engine_cc=cc,
        today=today_value,
    )

    status = customs_status
    if status is None:
        if customs_found is False:
            status = "not_found"
        elif customs_found is True:
            status = "found"

    if status == "unavailable":
        return RfUtilVerdict(
            code="customs_unavailable",
            tone="neutral",
            title="Сайт таможни временно не отвечает",
            detail=(
                "ГТК сейчас не отдал результат. Сохраните ссылку на эту проверку и зайдите позже "
                "или оставьте контакт — пришлём дату ввоза, как только база ответит. "
                "Также можно написать нам в Telegram @auto160."
            ),
            cta="notify",
            checks={**checks, "import_date": None},
        )

    if input_kind == "vin":
        # VIN-only: no power/volume from the advert — show customs date context only.
        if status == "not_found" or customs_found is False:
            return RfUtilVerdict(
                code="not_found",
                tone="neutral",
                title="В базе ГТК (физлица) запись не найдена",
                detail="Это не означает нелегальный ввоз.",
                cta="none",
                checks={"import_date": False, "power": None, "volume": None},
                reasons=not_found_reasons(input_kind="vin"),
            )
        if not release_date:
            return RfUtilVerdict(
                code="no_date",
                tone="neutral",
                title="Дата ввоза не определена",
                detail="Для оценки льготного утильсбора укажите ссылку на объявление av.by.",
                cta="none",
                checks={"import_date": None, "power": None, "volume": None},
            )
        eligible = eligible_from_date_label(release_date)
        return RfUtilVerdict(
            code="vin_only",
            tone="neutral",
            title="Дата ввоза найдена",
            detail=(
                "Чтобы проверить льготный утильсбор (мощность и объём), вставьте ссылку на объявление av.by."
                + (f" Льготный срок — с {eligible}." if eligible else "")
            ),
            eligible_from_date=eligible,
            cta="none",
            checks=checks,
        )

    # av.by URL path
    if status == "not_found" or customs_found is False:
        return RfUtilVerdict(
            code="not_found",
            tone="neutral",
            title="В базе ГТК (физлица) запись не найдена",
            detail="Без даты ввоза нельзя подтвердить проходной срок для льготного утильсбора.",
            cta="select",
            checks={**checks, "import_date": False},
            reasons=not_found_reasons(input_kind="avby_url"),
        )

    if power_hp is None or power_hp <= 0:
        return RfUtilVerdict(
            code="no_power",
            tone="neutral",
            title="Не удалось определить мощность",
            detail="В объявлении нет мощности двигателя — оценка льготного утильсбора недоступна.",
            eligible_from_date=eligible_from_date_label(release_date),
            cta="select",
            checks=checks,
        )

    if power_hp > PREFERENTIAL_HP_MAX:
        return RfUtilVerdict(
            code="fail_power",
            tone="red",
            title="Автомобиль не проходит на РФ под льготный утильсбор — мощность более 160 л.с.",
            cta="select",
            checks=checks,
        )

    if cc is not None and cc > PREFERENTIAL_CC_MAX:
        return RfUtilVerdict(
            code="fail_volume",
            tone="red",
            title="Автомобиль не проходит на РФ под льготный утильсбор — объём двигателя более 3000 см³",
            cta="select",
            checks=checks,
        )

    if not release_date:
        return RfUtilVerdict(
            code="no_date",
            tone="neutral",
            title="Дата ввоза не определена",
            detail="Мощность подходит под льготу, но без даты ввоза из ГТК срок проходности неизвестен.",
            cta="inspect",
            checks=checks,
        )

    parsed = parse_filter_date(release_date)
    if parsed is None:
        return RfUtilVerdict(
            code="no_date",
            tone="neutral",
            title="Дата ввоза не распознана",
            detail=f"Сырая дата из ГТК: {release_date}",
            cta="inspect",
            checks=checks,
        )

    cutoff_12 = add_calendar_months(today_value, -IMPORT_AGE_RF_MONTHS)
    cutoff_10 = add_calendar_months(today_value, -IMPORT_AGE_OVER_10M_MONTHS)
    eligible = format_display_date(add_calendar_months(parsed, IMPORT_AGE_RF_MONTHS))

    if parsed <= cutoff_12:
        return RfUtilVerdict(
            code="pass_ready",
            tone="green",
            title="Автомобиль проходной на РФ под льготный утильсбор",
            eligible_from_date=eligible,
            cta="inspect",
            checks=checks,
        )

    if parsed <= cutoff_10:
        return RfUtilVerdict(
            code="pass_after_date",
            tone="yellow",
            title=f"Автомобиль проходной на РФ под льготный утильсбор после {eligible}",
            eligible_from_date=eligible,
            cta="inspect",
            checks=checks,
        )

    return RfUtilVerdict(
        code="fail_until_date",
        tone="red",
        title=f"Автомобиль не проходит на РФ под льготный утильсбор до {eligible}",
        eligible_from_date=eligible,
        cta="select",
        checks=checks,
    )
