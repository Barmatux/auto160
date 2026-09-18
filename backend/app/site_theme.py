"""Site theme cookie resolution (logo dark/light for visitors)."""

from __future__ import annotations

SITE_THEME_COOKIE = "auto160_site_theme"
SITE_THEME_STANDARD = "standard"
SITE_THEME_LOGO = "logo"
SITE_THEME_LOGO_LIGHT = "logo-light"
SITE_THEMES = {SITE_THEME_STANDARD, SITE_THEME_LOGO, SITE_THEME_LOGO_LIGHT}
SITE_THEMES_PUBLIC = {SITE_THEME_LOGO, SITE_THEME_LOGO_LIGHT}
SITE_THEME_DEFAULT = SITE_THEME_LOGO_LIGHT

SITE_THEME_LABELS = {
    SITE_THEME_STANDARD: "Стандарт",
    SITE_THEME_LOGO: "Стиль логотипа",
    SITE_THEME_LOGO_LIGHT: "Стиль логотипа (светлый)",
}


def resolve_site_theme(raw_cookie: str | None, *, is_admin: bool) -> str:
    raw = (raw_cookie or SITE_THEME_DEFAULT).strip().lower()
    if is_admin:
        return raw if raw in SITE_THEMES else SITE_THEME_DEFAULT
    # Visitors only get logo dark/light; unknown or legacy "standard" → light logo style.
    return raw if raw in SITE_THEMES_PUBLIC else SITE_THEME_DEFAULT


def site_theme_uses_logo(theme: str) -> bool:
    return theme in SITE_THEMES_PUBLIC
