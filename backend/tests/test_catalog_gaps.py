from datetime import datetime
from types import SimpleNamespace

from app.catalog_gaps import enqueue_catalog_gap
from app.catalog_match import CatalogMatchInput


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDb:
    def __init__(self, existing=None):
        self.existing = existing or []
        self.added = []
        self.flushed = False
        self.committed = False

    def query(self, model):
        return _FakeQuery(self.existing)

    def add(self, row):
        self.added.append(row)

    def flush(self):
        self.flushed = True
        for idx, row in enumerate(self.added, start=1):
            if getattr(row, "id", None) is None:
                row.id = idx

    def commit(self):
        self.committed = True

    def refresh(self, row):
        return row


def test_enqueue_catalog_gap_creates_open_row():
    db = _FakeDb()
    gap = enqueue_catalog_gap(
        db,
        CatalogMatchInput(external_ref="eu2-9", make="Ford", model="Focus", year=2012, engine_power_hp=125),
        source="eu2",
    )
    assert db.flushed is True
    assert len(db.added) == 1
    assert gap.make == "Ford"
    assert gap.model == "Focus"
    assert gap.status == "open"
    assert gap.external_ref == "eu2-9"


def test_enqueue_catalog_gap_updates_existing_open():
    existing = SimpleNamespace(
        id=7,
        source="eu2",
        external_ref="eu2-9",
        status="open",
        generation=None,
        year=2010,
        body_type=None,
        fuel_type=None,
        engine_power_hp=100,
        engine_volume_l=None,
        drivetrain=None,
        transmission=None,
        source_external_id=None,
        payload=None,
        notes=None,
        updated_at=datetime(2026, 1, 1),
    )
    db = _FakeDb(existing=[existing])
    gap = enqueue_catalog_gap(
        db,
        CatalogMatchInput(external_ref="eu2-9", make="Ford", model="Focus", year=2012, engine_power_hp=125),
        source="eu2",
    )
    assert db.added == []
    assert gap.id == 7
    assert gap.year == 2012
    assert gap.engine_power_hp == 125
