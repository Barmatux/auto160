from types import SimpleNamespace

from app.design_lab import is_design_lab_user


def test_design_lab_rolled_out_for_everyone():
    assert is_design_lab_user(SimpleNamespace(email="anyone@example.com")) is True
    assert is_design_lab_user(None) is True
