from app.avby_offer_check import extract_avby_advert_status

INACTIVE_PAGE_SNIPPET = """
136369210,"daysOnSale":2,"advertType":"cars","isRent":false,"status":"removed",
<div class="gallery__status"><span>Неактивно</span></div>
{"id":999001,"advertType":"parts","status":"active","publicStatus":{"name":"active"}}
"""

ACTIVE_PAGE_SNIPPET = """
136369210,"daysOnSale":2,"advertType":"cars","isRent":false,"status":"active",
{"id":999001,"advertType":"parts","status":"active","publicStatus":{"name":"active"}}
"""


def test_extract_status_removed_for_target_advert():
    assert extract_avby_advert_status(INACTIVE_PAGE_SNIPPET, 136369210) == "removed"


def test_extract_status_active_for_target_advert():
    assert extract_avby_advert_status(ACTIVE_PAGE_SNIPPET, 136369210) == "active"


def test_inactive_page_not_confused_by_related_active_adverts():
    # Old bug: any "name":"active" on page marked listing as active.
    assert extract_avby_advert_status(INACTIVE_PAGE_SNIPPET, 136369210) == "removed"
