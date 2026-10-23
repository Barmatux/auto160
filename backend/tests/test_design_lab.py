from types import SimpleNamespace

from app.design_lab import DESIGN_LAB_EMAILS, is_design_lab_user


def test_design_lab_includes_cargo_account():
    assert "cargo.shleg@gmail.com" in DESIGN_LAB_EMAILS


def test_is_design_lab_user_matches_email_case_insensitively():
    assert is_design_lab_user(SimpleNamespace(email="Cargo.Shleg@gmail.com")) is True
    assert is_design_lab_user(SimpleNamespace(email="other@example.com")) is False
    assert is_design_lab_user(None) is False
