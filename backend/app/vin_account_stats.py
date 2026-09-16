"""Admin reporting helpers for per-account VIN fetch stats."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.avby_accounts import account_display_login, format_avby_phone_display
from app.models import AvbyServiceAccount, AvbyVinFetch


def build_vin_fetch_stats_by_day(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """VIN fetch counts grouped by calendar day, newest first.

    Each item:
      {
        "day": "YYYY-MM-DD",
        "day_label": "DD.MM.YYYY",
        "accounts": [{"id", "label", "count"}, ... sorted by count desc],
        "total": int,
      }
    """
    query = db.query(
        AvbyVinFetch.account_id,
        func.date(AvbyVinFetch.created_at).label("day"),
        func.count(AvbyVinFetch.id).label("cnt"),
    )
    if date_from is not None:
        query = query.filter(AvbyVinFetch.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        query = query.filter(
            AvbyVinFetch.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time())
        )
    rows = query.group_by(AvbyVinFetch.account_id, func.date(AvbyVinFetch.created_at)).all()

    by_day: dict[str, dict[int, int]] = defaultdict(dict)
    account_ids: set[int] = set()
    for account_id, day_value, cnt in rows:
        if account_id is None:
            continue
        if hasattr(day_value, "isoformat"):
            key = day_value.isoformat()
        else:
            key = str(day_value)[:10]
        count = int(cnt or 0)
        if count <= 0:
            continue
        by_day[key][account_id] = count
        account_ids.add(account_id)

    accounts_db = []
    if account_ids:
        accounts_db = (
            db.query(AvbyServiceAccount)
            .filter(AvbyServiceAccount.id.in_(account_ids))
            .all()
        )
    account_labels: dict[int, str] = {}
    for account in accounts_db:
        login = account_display_login(account)
        phone = format_avby_phone_display(account.phone) if account.phone else None
        label = login
        if phone and phone not in label:
            label = f"{login} ({phone})" if account.email else phone
        account_labels[account.id] = label

    groups: list[dict] = []
    for day_key in sorted(by_day.keys(), reverse=True):
        account_counts = by_day[day_key]
        accounts = [
            {
                "id": account_id,
                "label": account_labels.get(account_id, f"#{account_id}"),
                "count": count,
            }
            for account_id, count in account_counts.items()
        ]
        accounts.sort(key=lambda row: (-row["count"], row["label"].casefold(), row["id"]))
        total = sum(row["count"] for row in accounts)
        try:
            day_label = date.fromisoformat(day_key).strftime("%d.%m.%Y")
        except ValueError:
            day_label = day_key
        groups.append(
            {
                "day": day_key,
                "day_label": day_label,
                "accounts": accounts,
                "total": total,
            }
        )
    return groups


def build_vin_fetch_daily_stats(
    db: Session,
    *,
    days: int = 14,
    today: date | None = None,
) -> dict:
    """Return daily VIN fetch counts per account for admin UI.

    Shape:
      {
        "days": [date, ... newest first],
        "accounts": [{"id", "login", "label"}, ...],
        "matrix": {account_id: {iso_date: count}},
        "totals_by_account": {account_id: int},
        "totals_by_day": {iso_date: int},
        "grand_total": int,
      }
    """
    day_count = max(1, min(int(days), 90))
    end = today or date.today()
    start = end - timedelta(days=day_count - 1)
    start_dt = datetime.combine(start, datetime.min.time())

    day_list = [end - timedelta(days=offset) for offset in range(day_count)]
    day_keys = [d.isoformat() for d in day_list]

    rows = (
        db.query(
            AvbyVinFetch.account_id,
            func.date(AvbyVinFetch.created_at).label("day"),
            func.count(AvbyVinFetch.id).label("cnt"),
        )
        .filter(AvbyVinFetch.created_at >= start_dt)
        .group_by(AvbyVinFetch.account_id, func.date(AvbyVinFetch.created_at))
        .all()
    )

    matrix: dict[int, dict[str, int]] = defaultdict(dict)
    totals_by_account: dict[int, int] = defaultdict(int)
    totals_by_day: dict[str, int] = defaultdict(int)
    account_ids: set[int] = set()
    for account_id, day_value, cnt in rows:
        if account_id is None:
            continue
        if hasattr(day_value, "isoformat"):
            key = day_value.isoformat()
        else:
            key = str(day_value)
        count = int(cnt or 0)
        matrix[account_id][key] = count
        totals_by_account[account_id] += count
        totals_by_day[key] += count
        account_ids.add(account_id)

    accounts_db = []
    if account_ids:
        accounts_db = (
            db.query(AvbyServiceAccount)
            .filter(AvbyServiceAccount.id.in_(account_ids))
            .order_by(AvbyServiceAccount.id.asc())
            .all()
        )
    # Keep stable order: most VIN in window first, then id.
    accounts_db.sort(key=lambda row: (-totals_by_account.get(row.id, 0), row.id))

    accounts = []
    for account in accounts_db:
        login = account_display_login(account)
        phone = format_avby_phone_display(account.phone) if account.phone else None
        label = login
        if phone and phone not in label:
            label = f"{login} ({phone})" if account.email else phone
        accounts.append({"id": account.id, "login": login, "label": label})

    return {
        "days": day_keys,
        "accounts": accounts,
        "matrix": {account_id: dict(day_map) for account_id, day_map in matrix.items()},
        "totals_by_account": dict(totals_by_account),
        "totals_by_day": dict(totals_by_day),
        "grand_total": sum(totals_by_account.values()),
        "window_days": day_count,
    }
