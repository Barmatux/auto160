"""Nightly schedule: refresh av.by ocenka / price-statistics analytics."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.logging_setup import setup_logging

COLLECTOR_PATH = ROOT_DIR / "tools" / "collect_avby_price_stats.py"
logger = logging.getLogger(__name__)


def _lock_path() -> Path:
    log_dir = Path(os.getenv("LOG_DIR") or (ROOT_DIR.parent / "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "avby-price-stats.lock"


def run_once(
    *,
    min_delay: float,
    max_delay: float,
    pause_every: int,
    pause_seconds: float,
    skip_active: bool,
    refresh: bool,
    max_consecutive_errors: int,
) -> int:
    lock_file = _lock_path()
    handle = open(lock_file, "a+", encoding="utf-8")
    try:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logger.warning("price-stats-skip: previous run still holds %s", lock_file)
            return 0
        except ImportError:
            # Windows local: best-effort without flock.
            pass

        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()} started={datetime.now().isoformat()}\n")
        handle.flush()

        cmd = [
            sys.executable,
            "-u",
            str(COLLECTOR_PATH),
            "--min-delay",
            str(min_delay),
            "--max-delay",
            str(max_delay),
            "--pause-every",
            str(pause_every),
            "--pause-seconds",
            str(pause_seconds),
            "--max-consecutive-errors",
            str(max_consecutive_errors),
        ]
        if skip_active:
            cmd.append("--skip-active")
        if refresh:
            cmd.append("--refresh")

        logger.info("price-stats-start: %s", " ".join(cmd))
        result = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
        if result.stdout:
            for line in result.stdout.splitlines()[-80:]:
                logger.info("price-stats | %s", line)
        if result.stderr:
            for line in result.stderr.splitlines()[-40:]:
                logger.warning("price-stats ! %s", line)
        logger.info("price-stats-finish: exit_code=%s", result.returncode)
        return result.returncode
    finally:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        handle.close()


def main() -> None:
    setup_logging("avby-price-stats")
    parser = argparse.ArgumentParser(description="Schedule nightly av.by price-stats refresh")
    parser.add_argument("--run-at-hour", type=int, default=1, help="Local hour to run (0-23)")
    parser.add_argument("--min-delay", type=float, default=12.0)
    parser.add_argument("--max-delay", type=float, default=20.0)
    parser.add_argument("--pause-every", type=int, default=12)
    parser.add_argument("--pause-seconds", type=float, default=90.0)
    parser.add_argument("--max-consecutive-errors", type=int, default=5)
    parser.add_argument(
        "--include-active",
        action="store_true",
        help="Also fetch active-adverts (more requests / WAF risk)",
    )
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Only fill missing year rows (default refreshes existing snapshots)",
    )
    parser.add_argument("--run-once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    run_hour = max(0, min(23, args.run_at_hour))
    kwargs = dict(
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        pause_every=args.pause_every,
        pause_seconds=args.pause_seconds,
        skip_active=not args.include_active,
        refresh=not args.no_refresh,
        max_consecutive_errors=args.max_consecutive_errors,
    )

    if args.run_once:
        raise SystemExit(run_once(**kwargs))

    last_run_date: str | None = None
    logger.info(
        "price-stats-scheduler-ready run_at_hour=%s refresh=%s skip_active=%s",
        run_hour,
        kwargs["refresh"],
        kwargs["skip_active"],
    )
    while True:
        now = datetime.now()
        today = now.date().isoformat()
        if now.hour == run_hour and last_run_date != today:
            run_once(**kwargs)
            last_run_date = today
        elif now.hour != run_hour:
            last_run_date = None
        time.sleep(60)


if __name__ == "__main__":
    main()
