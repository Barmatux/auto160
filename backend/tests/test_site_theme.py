from app.site_theme import (
    SITE_THEME_DEFAULT,
    SITE_THEME_LOGO,
    SITE_THEME_LOGO_GRAPHITE,
    SITE_THEME_LOGO_LIGHT,
    SITE_THEME_STANDARD,
    resolve_site_theme,
    site_theme_body_class,
    site_theme_logo_src,
    site_theme_uses_logo,
)


def test_visitor_default_theme_is_logo_light():
    assert resolve_site_theme(None, is_admin=False) == SITE_THEME_LOGO_LIGHT
    assert resolve_site_theme("", is_admin=False) == SITE_THEME_DEFAULT


def test_visitor_can_use_logo_dark_light_and_graphite():
    assert resolve_site_theme(SITE_THEME_LOGO, is_admin=False) == SITE_THEME_LOGO
    assert resolve_site_theme(SITE_THEME_LOGO_LIGHT, is_admin=False) == SITE_THEME_LOGO_LIGHT
    assert resolve_site_theme(SITE_THEME_LOGO_GRAPHITE, is_admin=False) == SITE_THEME_LOGO_GRAPHITE


def test_visitor_standard_cookie_falls_back_to_logo_light():
    assert resolve_site_theme(SITE_THEME_STANDARD, is_admin=False) == SITE_THEME_DEFAULT
    assert resolve_site_theme("nope", is_admin=False) == SITE_THEME_DEFAULT


def test_admin_can_use_standard_theme():
    assert resolve_site_theme(SITE_THEME_STANDARD, is_admin=True) == SITE_THEME_STANDARD
    assert resolve_site_theme(SITE_THEME_LOGO, is_admin=True) == SITE_THEME_LOGO
    assert resolve_site_theme(SITE_THEME_LOGO_GRAPHITE, is_admin=True) == SITE_THEME_LOGO_GRAPHITE
    assert resolve_site_theme("nope", is_admin=True) == SITE_THEME_DEFAULT


def test_site_theme_uses_logo():
    assert site_theme_uses_logo(SITE_THEME_LOGO) is True
    assert site_theme_uses_logo(SITE_THEME_LOGO_LIGHT) is True
    assert site_theme_uses_logo(SITE_THEME_LOGO_GRAPHITE) is True
    assert site_theme_uses_logo(SITE_THEME_STANDARD) is False


def test_site_theme_body_class_and_logo_src():
    assert site_theme_body_class(SITE_THEME_LOGO) == "theme-admin"
    assert "theme-admin-graphite" in site_theme_body_class(SITE_THEME_LOGO_GRAPHITE)
    assert "theme-admin-light" in site_theme_body_class(SITE_THEME_LOGO_LIGHT)
    assert "graphite" in site_theme_logo_src(SITE_THEME_LOGO_GRAPHITE)
    assert "graphite" not in site_theme_logo_src(SITE_THEME_LOGO)
