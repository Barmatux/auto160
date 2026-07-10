"""Keep av.by VIN test session alive by refreshing JWT before expiry.

Runs in a loop (default every 15 min). JWT from av.by lives ~30 min;
refresh via refreshToken is fast and needs no 2captcha.

Examples:
  python tools/keep_avby_session_alive.py
  python tools/keep_avby_session_alive.py --interval-minutes 10 --run-once

On VM (docker service avby-vin-session):
  docker compose --env-file .env.vm -f docker-compose.vm.yml up -d avby-vin-session
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.avby_accounts import get_vin_test_account
from app.avby_session import AvbySessionError, ensure_avby_session_fresh
from app.db import SessionLocal

_stop = False


def _ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _handle_stop(signum: int, _frame) -> None:
    global _stop
    print(f"[{_ts()}] received signal {signum}, stopping...")
    _stop = True


def tick(*, refresh_if_minutes: int) -> int:
    from datetime import timedelta

    db = SessionLocal()
    try:
        account = get_vin_test_account(db)
        if account is None:
            print(f"[{_ts()}] error: no vin_test account in DB")
            return 1

        session = ensure_avby_session_fresh(
            db,
            account,
            refresh_if_within=timedelta(minutes=refresh_if_minutes),
        )
        remaining = session.expires_at - datetime.now(UTC).replace(tzinfo=None)
        print(
            f"[{_ts()}] session ok account={account.email} "
            f"expires_utc={session.expires_at.isoformat()} "
            f"ttl_min={max(0, int(remaining.total_seconds() // 60))}"
        )
        return 0
    except AvbySessionError as exc:
        print(f"[{_ts()}] session error: {exc}")
        return 1
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep av.by VIN session alive")
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=15,
        help="How often to refresh session (default 15)",
    )
    parser.add_argument(
        "--refresh-if-within-minutes",
        type=int,
        default=15,
        help="Proactively refresh when JWT expires within N minutes (default 15)",
    )
    parser.add_argument("--run-once", action="store_true", help="Refresh once and exit")
    args = parser.parse_args()

    if args.interval_minutes < 1:
        raise SystemExit("--interval-minutes must be >= 1")

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    print(
        f"[{_ts()}] avby session keeper started "
        f"interval={args.interval_minutes}m refresh_if_within={args.refresh_if_within_minutes}m"
    )

    while not _stop:
        code = tick(refresh_if_minutes=args.refresh_if_within_minutes)
        if args.run_once:
            return code

        sleep_seconds = args.interval_minutes * 60
        deadline = time.time() + sleep_seconds
        while time.time() < deadline and not _stop:
            time.sleep(min(5, deadline - time.time()))

    print(f"[{_ts()}] avby session keeper stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
