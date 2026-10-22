"""Site theme cookie resolution (logo dark/light/graphite for visitors)."""

from __future__ import annotations

SITE_THEME_COOKIE = "auto160_site_theme"
SITE_THEME_STANDARD = "standard"
SITE_THEME_LOGO = "logo"
SITE_THEME_LOGO_GRAPHITE = "logo-graphite"
SITE_THEME_LOGO_LIGHT = "logo-light"
SITE_THEMES = {
    SITE_THEME_STANDARD,
    SITE_THEME_LOGO,
    SITE_THEME_LOGO_GRAPHITE,
    SITE_THEME_LOGO_LIGHT,
}
SITE_THEMES_PUBLIC = {SITE_THEME_LOGO, SITE_THEME_LOGO_GRAPHITE, SITE_THEME_LOGO_LIGHT}
SITE_THEME_DEFAULT = SITE_THEME_LOGO_LIGHT

# Pure black plaque of logo-admin-v8-horizontal.png
LOGO_PLAQUE_BLACK = "#000000"
# Softened charcoal header used before / graphite logo fill
LOGO_PLAQUE_GRAPHITE = "#10131a"

SITE_THEME_LABELS = {
    SITE_THEME_STANDARD: "Стандарт",
    SITE_THEME_LOGO: "Стиль логотипа (чёрный)",
    SITE_THEME_LOGO_GRAPHITE: "Стиль логотипа (графит)",
    SITE_THEME_LOGO_LIGHT: "Стиль логотипа (светлый)",
}

SITE_THEME_LOGO_SRC = {
    SITE_THEME_LOGO: "/static/brand/logo-admin-v8-header.png?v=20261022-black",
    SITE_THEME_LOGO_GRAPHITE: "/static/brand/logo-admin-v8-header-graphite.png?v=20261022-01",
    SITE_THEME_LOGO_LIGHT: "/static/brand/logo-admin-v8-header.png?v=20261022-black",
}


def resolve_site_theme(raw_cookie: str | None, *, is_admin: bool) -> str:
    raw = (raw_cookie or SITE_THEME_DEFAULT).strip().lower()
    if is_admin:
        return raw if raw in SITE_THEMES else SITE_THEME_DEFAULT
    # Visitors only get logo variants; unknown or legacy "standard" → light logo style.
    return raw if raw in SITE_THEMES_PUBLIC else SITE_THEME_DEFAULT


def site_theme_uses_logo(theme: str) -> bool:
    return theme in SITE_THEMES_PUBLIC


def site_theme_logo_src(theme: str) -> str:
    return SITE_THEME_LOGO_SRC.get(theme, SITE_THEME_LOGO_SRC[SITE_THEME_LOGO_LIGHT])


def site_theme_body_class(theme: str) -> str:
    if theme == SITE_THEME_LOGO:
        return "theme-admin"
    if theme == SITE_THEME_LOGO_GRAPHITE:
        return "theme-admin theme-admin-graphite"
    if theme == SITE_THEME_LOGO_LIGHT:
        return "theme-admin theme-admin-light"
    return ""
