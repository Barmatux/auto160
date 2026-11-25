from app.customs_duty_calc import (
    CustomsCalcInput,
    age_band,
    calculate_customs,
    car_age_years,
    clearance_fee_rub,
    normalize_age_band,
    preferential_util_eligible,
    util_coefficient,
)


def test_age_bands():
    assert age_band(1.5) == "under3"
    assert age_band(3.2) == "from3to5"
    assert age_band(6.0) == "over5"


def test_normalize_age_band():
    assert normalize_age_band("under3") == "under3"
    assert normalize_age_band("from3to5") == "from3to5"
    try:
        normalize_age_band("nope")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_preferential_util_for_personal_under_160():
    assert preferential_util_eligible(
        importer="personal", power_hp=150, engine_cc=1598, engine_kind="ice"
    )
    assert not preferential_util_eligible(
        importer="personal", power_hp=170, engine_cc=1598, engine_kind="ice"
    )
    assert not preferential_util_eligible(
        importer="commercial", power_hp=150, engine_cc=1598, engine_kind="ice"
    )


def test_preferential_util_amounts():
    k_new, pref = util_coefficient(
        importer="personal",
        age_years=2.0,
        power_hp=150,
        engine_cc=1998,
        engine_kind="ice",
    )
    assert pref is True
    assert k_new == 0.17

    k_old, pref_old = util_coefficient(
        importer="personal",
        age_years=4.0,
        power_hp=150,
        engine_cc=1998,
        engine_kind="ice",
    )
    assert pref_old is True
    assert k_old == 0.26


def test_commercial_util_for_over_160():
    k, pref = util_coefficient(
        importer="personal",
        age_years=4.0,
        power_hp=238,
        engine_cc=1969,
        engine_kind="ice",
    )
    assert pref is False
    assert k == 83.88


def test_clearance_fee_brackets():
    assert clearance_fee_rub(100_000) == 1_231
    assert clearance_fee_rub(500_000) == 4_924
    assert clearance_fee_rub(6_000_000) == 49_240


def test_calculate_personal_preferential_duty_and_util():
    result = calculate_customs(
        CustomsCalcInput(
            age_band="from3to5",
            engine_cc=1598,
            power_hp=150,
            price=10_000,
            currency="EUR",
            importer="personal",
            engine_kind="ice",
        ),
        eur_rub=100.0,
        usd_rub=90.0,
        byn_rub=30.0,
    )
    assert result.ok is True
    assert result.age_band == "from3to5"
    assert result.age_band_label == "от 3 до 5 лет"
    assert result.util_preferential is True
    assert result.util_sbor_rub == 5_200.0
    assert result.customs_value_rub == 1_000_000.0
    # EAEU personal 3–5y, 1501–1800 cm³ → 2.5 €/cm³
    assert result.duty_rub == round(2.5 * 1598 * 100.0, 2)
    assert result.total_rub == round(
        (result.duty_rub or 0)
        + (result.clearance_fee_rub or 0)
        + (result.util_sbor_rub or 0),
        2,
    )


def test_personal_duty_from3to5_xc40_1500_band():
    """Volvo XC40 1.5 / 1477 cm³: unified 1.7 €/cm³, not the old 54%/7€ bug."""
    eur = 96.6719
    result = calculate_customs(
        CustomsCalcInput(
            age_band="from3to5",
            engine_cc=1477,
            power_hp=150,
            price=12_000,
            currency="EUR",
            importer="personal",
            engine_kind="ice",
        ),
        eur_rub=eur,
        usd_rub=86.3,
        byn_rub=28.81,
    )
    assert result.ok is True
    assert result.util_sbor_rub == 5_200.0
    assert result.duty_rub == round(1.7 * 1477 * eur, 2)
    assert result.duty_rub < 300_000
    assert "1.7" in (result.breakdown.get("duty_rule") or "")


def test_car_age_years_rejects_bad_year():
    try:
        car_age_years(1800)
        assert False, "expected ValueError"
    except ValueError:
        pass
