"""Sold-cars archive: import is idempotent, hand edits are never overwritten."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import SoldCar, SoldCarExpense, SoldPartner
from app.routers.sold_cars import (
    ImportCar,
    ImportRequest,
    SoldCarPatch,
    ExpenseIn,
    PartnerPatch,
    delete_sold_car,
    get_sold_car,
    import_sold_cars,
    list_partners,
    list_sold_cars,
    patch_partner,
    patch_sold_car,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    for model in (SoldPartner, SoldCar, SoldCarExpense):
        model.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _car(**over):
    base = {
        "source_key": "xlsx:NV300:1",
        "sheet": "NV300",
        "title": "Nissan NV300",
        "expenses": [
            {"row": 4, "item": "Покупка", "amount": 11350, "currency": "EUR", "payer": "А"},
            {"row": 5, "item": "Таможня", "amount": 9434, "currency": "BYN", "payer": "А"},
            {"row": 6, "item": "Мойка", "amount": 65, "currency": "BYN", "payer": "М"},
        ],
        "sums": {"EUR": 11350, "BYN": 9499},
        "sold_price": 57000,
        "profit": 2951.8,
        "verified": True,
        "needs_review": False,
        "flags": [],
    }
    base.update(over)
    return ImportCar(**base)


def test_import_creates_car_expenses_and_partners(db):
    res = import_sold_cars(ImportRequest(cars=[_car()]), None, db)
    assert (res.created, res.updated, res.partners_added) == (1, 0, 2)

    cars = list_sold_cars(None, db)
    assert len(cars) == 1
    assert cars[0]["expenses_count"] == 3
    assert cars[0]["payers"] == ["А", "М"]
    assert cars[0]["sold_price"] == 57000.0


def test_reimport_updates_without_duplicates(db):
    import_sold_cars(ImportRequest(cars=[_car()]), None, db)
    res = import_sold_cars(ImportRequest(cars=[_car(sold_price=58000)]), None, db)
    assert (res.created, res.updated) == (0, 1)
    assert db.query(SoldCar).count() == 1
    assert db.query(SoldCarExpense).count() == 3
    assert db.query(SoldCar).one().sold_price == 58000


def test_manual_edit_locks_car_against_reimport(db):
    import_sold_cars(ImportRequest(cars=[_car(needs_review=True, verified=False)]), None, db)
    car_id = db.query(SoldCar).one().id

    detail = patch_sold_car(
        car_id,
        SoldCarPatch(
            sold_price=60000,
            needs_review=False,
            expenses=[ExpenseIn(item="Покупка", amount=11000, currency="eur", payer="А")],
        ),
        None,
        db,
    )
    assert detail["locked"] is True
    assert detail["needs_review"] is False
    assert [e["amount"] for e in detail["expenses"]] == [11000.0]
    assert detail["expenses"][0]["currency"] == "EUR"

    res = import_sold_cars(ImportRequest(cars=[_car(sold_price=1)]), None, db)
    assert res.skipped_locked == 1
    assert get_sold_car(car_id, None, db)["sold_price"] == 60000.0


def test_clear_fields_resets_value(db):
    import_sold_cars(ImportRequest(cars=[_car()]), None, db)
    car_id = db.query(SoldCar).one().id
    detail = patch_sold_car(car_id, SoldCarPatch(clear_fields=["profit"]), None, db)
    assert detail["profit"] is None


def test_partner_names_and_delete(db):
    import_sold_cars(ImportRequest(cars=[_car()]), None, db)
    partner = next(p for p in list_partners(None, db) if p["code"] == "А")
    assert partner["expenses_count"] == 2
    assert patch_partner(partner["id"], PartnerPatch(name="Андрей"), None, db)["name"] == "Андрей"

    delete_sold_car(db.query(SoldCar).one().id, None, db)
    assert db.query(SoldCarExpense).count() == 0
