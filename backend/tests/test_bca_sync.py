from fastapi import HTTPException
import pytest

from app.bca_admin import REPLACE_MIN_LOTS, sync_parsed_lots
from app.routers import bca_sync


def test_bca_sync_fails_closed_when_unset(monkeypatch):
    monkeypatch.setattr(bca_sync.settings, "bca_sync_api_key", "")
    with pytest.raises(HTTPException) as exc:
        bca_sync.require_bca_sync_access(x_api_key="anything")
    assert exc.value.status_code == 503


def test_bca_sync_rejects_bad_key(monkeypatch):
    monkeypatch.setattr(bca_sync.settings, "bca_sync_api_key", "secret-bca")
    with pytest.raises(HTTPException) as exc:
        bca_sync.require_bca_sync_access(x_api_key="wrong")
    assert exc.value.status_code == 401


def test_bca_sync_accepts_matching_key(monkeypatch):
    monkeypatch.setattr(bca_sync.settings, "bca_sync_api_key", "secret-bca")
    assert bca_sync.require_bca_sync_access(x_api_key="secret-bca") is None


def test_short_snapshot_does_not_replace(monkeypatch):
    monkeypatch.setattr("app.bca_admin.upsert_parsed_lots", lambda db, items: len(items))
    result = sync_parsed_lots(None, [{"vehicle_id": "1"}], replace=True)
    assert result == {"saved": 1, "removed": 0}
    assert REPLACE_MIN_LOTS == 50
