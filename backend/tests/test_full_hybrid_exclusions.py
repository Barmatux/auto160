from app.full_hybrid_exclusions import is_full_hybrid_listing


def test_toyota_family_is_full_hev():
    assert is_full_hybrid_listing(
        brand="Toyota", model="C-HR", engine_type="Бензин / электричество", engine_capacity_l=1.8, engine_power_hp=122
    )
    assert is_full_hybrid_listing(
        brand="Toyota", model="Yaris Cross", engine_type="Гибрид (бензин / электричество)", engine_capacity_l=1.5
    )
    assert is_full_hybrid_listing(brand="Lexus", model="LBX", engine_type="Бензин / электричество", engine_capacity_l=1.5)


def test_keeps_mild_renault_and_dacia():
    assert not is_full_hybrid_listing(
        brand="Renault", model="Arkana", engine_type="Бензин / электричество", engine_capacity_l=1.3, engine_power_hp=140
    )
    assert not is_full_hybrid_listing(
        brand="Renault", model="Arkana", engine_type="Гибрид (бензин / электричество)", engine_capacity_l=1.3, engine_power_hp=158
    )
    assert not is_full_hybrid_listing(
        brand="Renault", model="Austral", engine_type="бензин (гибрид)", engine_capacity_l=1.3, engine_power_hp=160
    )
    assert not is_full_hybrid_listing(
        brand="Renault", model="Captur", engine_type="Бензин / электричество", engine_capacity_l=1.3, engine_power_hp=140
    )
    assert not is_full_hybrid_listing(
        brand="Dacia",
        model="Bigster",
        engine_type="Бензин / электричество / газ",
        engine_capacity_l=1.2,
        engine_power_hp=140,
    )
    assert not is_full_hybrid_listing(
        brand="Dacia",
        model="Duster",
        engine_type="Бензин / электричество / газ",
        engine_capacity_l=1.2,
        engine_power_hp=150,
    )


def test_renault_e_tech_full_is_banned():
    assert is_full_hybrid_listing(
        brand="Renault", model="Arkana", engine_type="бензин (гибрид)", engine_capacity_l=1.6, engine_power_hp=143
    )


def test_keeps_ford_vw_diesel_mild_and_phev():
    assert not is_full_hybrid_listing(
        brand="Ford", model="Focus", engine_type="Бензин / электричество", engine_capacity_l=1.0, engine_power_hp=125
    )
    assert not is_full_hybrid_listing(
        brand="Volkswagen", model="Golf", engine_type="Бензин / электричество", engine_capacity_l=1.5
    )
    assert not is_full_hybrid_listing(
        brand="Kia", model="Sportage", engine_type="Дизель / электричество", engine_capacity_l=1.6
    )
    assert not is_full_hybrid_listing(
        brand="Kia",
        model="XCeed",
        title="Kia XCeed Plug-In",
        engine_type="Подключаемый гибрид (бензин / электричество)",
        engine_capacity_l=1.6,
    )


def test_keeps_ambiguous_tucson_sportage_petrol_hybrid():
    # Could be mild or HEV — do not ban.
    assert not is_full_hybrid_listing(
        brand="Hyundai", model="Tucson", engine_type="Бензин / электричество", engine_capacity_l=1.6
    )
    assert not is_full_hybrid_listing(
        brand="Kia", model="Sportage", engine_type="Бензин / электричество", engine_capacity_l=1.6
    )


def test_honda_and_niro():
    assert is_full_hybrid_listing(
        brand="Honda", model="CR-V", engine_type="бензин (гибрид)", engine_capacity_l=2.0, engine_power_hp=145
    )
    assert is_full_hybrid_listing(
        brand="Honda", model="HR-V", engine_type="Бензин / электричество", engine_capacity_l=1.5, engine_power_hp=107
    )
    assert not is_full_hybrid_listing(
        brand="Honda", model="Civic", engine_type="бензин (гибрид)", engine_capacity_l=1.5, engine_power_hp=112, year=2013
    )
    assert is_full_hybrid_listing(
        brand="Kia", model="Niro", engine_type="Бензин / электричество", engine_capacity_l=1.6, engine_power_hp=141
    )


def test_keeps_xtrail_mild_and_epower_marker():
    assert not is_full_hybrid_listing(
        brand="Nissan", model="X-Trail", engine_type="Бензин / электричество", engine_capacity_l=1.5, engine_power_hp=158
    )
    assert not is_full_hybrid_listing(
        brand="Nissan",
        model="Qashqai",
        title="Nissan Qashqai e-Power",
        engine_type="Бензин / электричество",
        engine_capacity_l=1.5,
    )
