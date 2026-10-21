"""Public legal operator details for Auto160 (ООО «Сканди Моторс»)."""

from __future__ import annotations

COMPANY_SHORT_NAME = "ООО «Сканди Моторс»"
COMPANY_FULL_NAME = 'Общество с ограниченной ответственностью «Сканди Моторс»'
COMPANY_UNP = "193866357"
COMPANY_UNPF = "524104711"  # УНПФ (ФСЗН)
COMPANY_LEGAL_ADDRESS = "г. Минск, ул. Скрыганова, дом 6, помещение 7"
COMPANY_YARD_ADDRESS = "г. Минск, ул. Максима Горецкого, 30"

COMPANY_BANK_NAME = 'ЗАО «Альфа-Банк»'
COMPANY_BANK_ADDRESS = "ул. Сурганова, 43-47, 220013 Минск, Республика Беларусь"
COMPANY_BANK_ACCOUNT_BYN = "BY58 ALFA 3012 2G91 3900 1027 0000"
COMPANY_BANK_SWIFT = "ALFABY2X"
COMPANY_BANK_UNP = "101541947"
COMPANY_BANK_OKPO = "37526626"

# Optional contacts — fill when provided (shown only if non-empty).
COMPANY_EMAIL = ""
COMPANY_PHONE = ""


def company_public_context() -> dict[str, str]:
    return {
        "company_short_name": COMPANY_SHORT_NAME,
        "company_full_name": COMPANY_FULL_NAME,
        "company_unp": COMPANY_UNP,
        "company_unpf": COMPANY_UNPF,
        "company_legal_address": COMPANY_LEGAL_ADDRESS,
        "company_yard_address": COMPANY_YARD_ADDRESS,
        "company_bank_name": COMPANY_BANK_NAME,
        "company_bank_address": COMPANY_BANK_ADDRESS,
        "company_bank_account_byn": COMPANY_BANK_ACCOUNT_BYN,
        "company_bank_swift": COMPANY_BANK_SWIFT,
        "company_bank_unp": COMPANY_BANK_UNP,
        "company_bank_okpo": COMPANY_BANK_OKPO,
        "company_email": COMPANY_EMAIL,
        "company_phone": COMPANY_PHONE,
    }
