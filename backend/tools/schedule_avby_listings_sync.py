import argparse
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
IMPORTER_PATH = ROOT_DIR / "tools" / "import_avby_listings.py"


def _ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def run_once(max_hp: int, max_pages: int, per_model_limit: int, update_existing: bool, archive_overpowered: bool) -> int:
    cmd = [
        sys.executable,
        str(IMPORTER_PATH),
        "--max-hp",
        str(max_hp),
        "--max-pages",
        str(max_pages),
        "--per-model-limit",
        str(per_model_limit),
    ]
    if not update_existing:
        cmd.append("--no-update-existing")
    if archive_overpowered:
        cmd.append("--archive-overpowered")

    print(f"[{_ts()}] sync-start: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))
    print(f"[{_ts()}] sync-finish: exit_code={result.returncode}")
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AV.BY listings sync on a fixed interval")
    parser.add_argument("--interval-minutes", type=int, default=20, help="Sync interval in minutes")
    parser.add_argument("--max-hp", type=int, default=160, help="Import only adverts with power <= this value")
    parser.add_argument("--max-pages", type=int, default=30, help="Max paginated pages per brand")
    parser.add_argument("--per-model-limit", type=int, default=30, help="Max adverts per model per sync run")
    parser.add_argument("--no-update-existing", action="store_true", help="Do not update existing AV.BY adverts")
    parser.add_argument(
        "--archive-overpowered",
        action="store_true",
        help="Archive existing listing if AVBY advert power is above max-hp",
    )
    parser.add_argument("--run-once", action="store_true", help="Run sync once and exit")
    args = parser.parse_args()

    update_existing = not args.no_update_existing
    if args.run_once:
        raise SystemExit(
            run_once(
                max_hp=args.max_hp,
                max_pages=args.max_pages,
                per_model_limit=args.per_model_limit,
                update_existing=update_existing,
                archive_overpowered=args.archive_overpowered,
            )
        )

    interval_seconds = max(60, args.interval_minutes * 60)
    while True:
        run_once(
            max_hp=args.max_hp,
            max_pages=args.max_pages,
            per_model_limit=args.per_model_limit,
            update_existing=update_existing,
            archive_overpowered=args.archive_overpowered,
        )
        print(f"[{_ts()}] sleep: {interval_seconds}s")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
