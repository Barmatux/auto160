from datetime import datetime, timedelta

from app.customs_vin import (
    CACHE_TTL_FOUND,
    CACHE_TTL_NOT_FOUND,
    _cache_is_fresh,
    _parse_message_html,
    normalize_vin,
    vin_is_valid,
)
from app.models import VinCustomsCheck


def test_vin_normalization_and_validation():
    assert normalize_vin(" vf3mrhnsuls192570 ") == "VF3MRHNSULS192570"
    assert vin_is_valid("VF3MRHNSULS192570") is True
    assert vin_is_valid("VF3MRHNSULS19257O") is False


def test_parse_message_html_found_table():
    html = """
    <table>
        <tbody>
            <tr>
                <th>Дата выпуска</th>
                <th>vin-номер</th>
            </tr>
            <tr>
                <td>05.03.2026</td>
                <td>VF3MRHNSULS192570</td>
            </tr>
        </tbody>
    </table>
    """
    found, fields, err = _parse_message_html(html)
    assert found is True
    assert fields["vin-номер"] == "VF3MRHNSULS192570"
    assert err is None


def test_parse_message_html_not_found():
    html = "<b>Ничего не найдено</b>"
    found, fields, err = _parse_message_html(html)
    assert found is False
    assert fields == {}
    assert err is None


def test_cache_ttl_differs_for_found_and_not_found():
    now = datetime(2026, 7, 29, 12, 0, 0)
    found_row = VinCustomsCheck(
        vin="VF3MRHNSULS192570",
        database="personal_free_circulation",
        found=True,
        checked_at=now - CACHE_TTL_FOUND + timedelta(hours=1),
    )
    missing_row = VinCustomsCheck(
        vin="VF3MRHNSULS192570",
        database="personal_free_circulation",
        found=False,
        checked_at=now - CACHE_TTL_NOT_FOUND + timedelta(hours=1),
    )
    stale_missing_row = VinCustomsCheck(
        vin="VF3MRHNSULS192570",
        database="personal_free_circulation",
        found=False,
        checked_at=now - CACHE_TTL_NOT_FOUND - timedelta(hours=1),
    )

    assert _cache_is_fresh(found_row, now=now) is True
    assert _cache_is_fresh(missing_row, now=now) is True
    assert _cache_is_fresh(stale_missing_row, now=now) is False
