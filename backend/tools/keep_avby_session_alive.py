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
import logging
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

from app.avby_accounts import list_vin_accounts_for_keepalive
from app.avby_session import AvbySessionError, ensure_avby_session_fresh
from app.db import SessionLocal
from app.logging_setup import setup_logging

logger = logging.getLogger(__name__)
_stop = False


def _handle_stop(signum: int, _frame) -> None:
    global _stop
    logger.warning("received signal %s, stopping...", signum)
    _stop = True


def tick(*, refresh_if_minutes: int) -> int:
    from datetime import timedelta

    db = SessionLocal()
    errors = 0
    refreshed = 0
    try:
        accounts = list_vin_accounts_for_keepalive(db)
        if not accounts:
            logger.error("no active vin_test accounts in DB")
            return 1

        for account in accounts:
            try:
                session = ensure_avby_session_fresh(
                    db,
                    account,
                    refresh_if_within=timedelta(minutes=refresh_if_minutes),
                )
                remaining = session.expires_at - datetime.now(UTC).replace(tzinfo=None)
                logger.info(
                    "session ok account=%s expires_utc=%s ttl_min=%s",
                    account.email or account.phone,
                    session.expires_at.isoformat(),
                    max(0, int(remaining.total_seconds() // 60)),
                )
                refreshed += 1
            except AvbySessionError as exc:
                errors += 1
                logger.error("session error account=%s: %s", account.email or account.phone, exc)

        if refreshed == 0:
            return 1
        return 0
    finally:
        db.close()


def main() -> int:
    setup_logging("avby-vin-session")
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

    logger.info(
        "avby session keeper started interval=%sm refresh_if_within=%sm",
        args.interval_minutes,
        args.refresh_if_within_minutes,
    )

    while not _stop:
        code = tick(refresh_if_minutes=args.refresh_if_within_minutes)
        if args.run_once:
            return code

        sleep_seconds = args.interval_minutes * 60
        deadline = time.time() + sleep_seconds
        while time.time() < deadline and not _stop:
            time.sleep(min(5, deadline - time.time()))

    logger.info("avby session keeper stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
