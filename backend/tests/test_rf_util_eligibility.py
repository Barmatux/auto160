from datetime import date

from app.rf_util_eligibility import evaluate_rf_util_eligibility


TODAY = date(2026, 10, 27)


def test_pass_ready_over_12_months():
    verdict = evaluate_rf_util_eligibility(
        release_date="15.08.2025",
        power_hp=150,
        engine_cc=1598,
        input_kind="avby_url",
        customs_found=True,
        today=TODAY,
    )
    assert verdict.code == "pass_ready"
    assert verdict.tone == "green"
    assert verdict.cta == "inspect"
    assert "проходной" in verdict.title.lower()
    assert verdict.checks == {"import_date": True, "power": True, "volume": True}


def test_pass_after_date_10_to_12_months():
    verdict = evaluate_rf_util_eligibility(
        release_date="15.12.2025",
        power_hp=150,
        engine_cc=1598,
        input_kind="avby_url",
        customs_found=True,
        today=TODAY,
    )
    assert verdict.code == "pass_after_date"
    assert verdict.tone == "yellow"
    assert verdict.cta == "inspect"
    assert "после" in verdict.title.lower()
    assert verdict.eligible_from_date == "15.12.2026"
    assert verdict.detail is None
    assert verdict.checks == {"import_date": False, "power": True, "volume": True}


def test_fail_until_date_under_10_months():
    verdict = evaluate_rf_util_eligibility(
        release_date="01.05.2026",
        power_hp=150,
        engine_cc=1598,
        input_kind="avby_url",
        customs_found=True,
        today=TODAY,
    )
    assert verdict.code == "fail_until_date"
    assert verdict.tone == "red"
    assert verdict.cta == "select"
    assert "до" in verdict.title.lower()
    assert verdict.detail is None
    assert verdict.checks == {"import_date": False, "power": True, "volume": True}


def test_fail_power():
    verdict = evaluate_rf_util_eligibility(
        release_date="15.08.2024",
        power_hp=170,
        engine_cc=1998,
        input_kind="avby_url",
        customs_found=True,
        today=TODAY,
    )
    assert verdict.code == "fail_power"
    assert verdict.tone == "red"
    assert "160" in verdict.title
    assert verdict.checks == {"import_date": True, "power": False, "volume": True}


def test_fail_volume():
    verdict = evaluate_rf_util_eligibility(
        release_date="15.08.2024",
        power_hp=150,
        engine_cc=3200,
        input_kind="avby_url",
        customs_found=True,
        today=TODAY,
    )
    assert verdict.code == "fail_volume"
    assert verdict.tone == "red"
    assert "3000" in verdict.title


def test_vin_only_neutral():
    verdict = evaluate_rf_util_eligibility(
        release_date="15.08.2024",
        power_hp=None,
        input_kind="vin",
        customs_found=True,
        today=TODAY,
    )
    assert verdict.code == "vin_only"
    assert verdict.tone == "neutral"


def test_gtk_not_found_without_status_treated_as_unavailable():
    """Legacy callers that only pass customs_found=False → unavailable."""
    verdict = evaluate_rf_util_eligibility(
        release_date=None,
        power_hp=110,
        engine_cc=1461,
        input_kind="avby_url",
        customs_found=False,
        today=TODAY,
    )
    assert verdict.code == "customs_unavailable"
    assert verdict.cta == "notify"


def test_gtk_not_found_confirmed_shown_as_unavailable():
    """Public page never shows definitive «не найдено» — same as downtime."""
    verdict = evaluate_rf_util_eligibility(
        release_date=None,
        power_hp=110,
        engine_cc=1461,
        input_kind="avby_url",
        customs_found=False,
        customs_status="not_found",
        today=TODAY,
    )
    assert verdict.code == "customs_unavailable"
    assert verdict.cta == "notify"


def test_customs_unavailable():
    verdict = evaluate_rf_util_eligibility(
        release_date=None,
        power_hp=110,
        engine_cc=1461,
        input_kind="avby_url",
        customs_found=None,
        customs_status="unavailable",
        today=TODAY,
    )
    assert verdict.code == "customs_unavailable"
    assert verdict.cta == "notify"
