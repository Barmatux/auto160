from app.company import COMPANY_SHORT_NAME, COMPANY_UNP, company_public_context
from app.seo import STATIC_SEO, organization_json_ld


def test_company_public_context_has_unp_and_address():
    ctx = company_public_context()
    assert ctx["company_short_name"] == COMPANY_SHORT_NAME
    assert ctx["company_unp"] == COMPANY_UNP
    assert "Скрыганова" in ctx["company_legal_address"]
    assert ctx["company_bank_swift"] == "ALFABY2X"


def test_organization_json_ld_includes_legal_operator():
    block = organization_json_ld("https://auto160.ru")
    assert block["legalName"] == COMPANY_SHORT_NAME
    assert block["taxID"] == COMPANY_UNP
    assert block["address"]["addressCountry"] == "BY"


def test_requisites_seo_static_entry():
    title, description = STATIC_SEO["/requisites"]
    assert "Сканди" in title
    assert "193866357" in description
