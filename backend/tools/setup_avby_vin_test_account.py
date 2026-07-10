"""Create a single av.by account for VIN testing (30 checks/day limit).

Registers via Mail.tm + 2captcha, stores as purpose=vin_test.
Phone verification is manual — use your real +375 number:

  python tools/verify_avby_phone.py --from-db --email YOU@EMAIL \\
    --manual-phone 291234567

  python tools/verify_avby_phone.py --from-db --email YOU@EMAIL \\
    --manual-phone 291234567 --sms-code 1234

On VM:
  docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \\
    python tools/setup_avby_vin_test_account.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.avby_accounts import VIN_TEST_DAILY_LIMIT, get_vin_test_account, upsert_avby_service_account
from app.db import SessionLocal
from tools.register_avby_accounts import obtain_captcha_token, parse_args as register_parse_args, register_one_account


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create av.by VIN test account (30 checks/day)")
    parser.add_argument("--prefix", default="vintest", help="Mail.tm local-part prefix")
    parser.add_argument("--name", default="Сервис Авто", help="Display name on av.by (Cyrillic only)")
    parser.add_argument("--output", default="data/avby_vin_test_account.json", help="Save credentials here")
    parser.add_argument("--force", action="store_true", help="Create another account even if vin_test exists")
    parser.add_argument("--dry-run", action="store_true", help="Only check if vin_test account already exists")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    db = SessionLocal()
    try:
        existing = get_vin_test_account(db)
        if existing and not args.force:
            print("VIN test account already exists:")
            print(f"  email: {existing.email}")
            print(f"  status: {existing.status}")
            print(f"  phone verified: {existing.status == 'phone_verified'}")
            print(f"  daily limit: {existing.daily_vin_limit or VIN_TEST_DAILY_LIMIT}")
            print(f"  checks today: {existing.vin_checks_today}")
            print("\nUse --force to register another account.")
            return 0
    finally:
        db.close()

    if args.dry_run:
        print("No vin_test account in DB. Run without --dry-run to create one.")
        return 0

    reg_args = register_parse_args()
    reg_args.count = 1
    reg_args.prefix = args.prefix
    reg_args.name = args.name
    reg_args.dry_run = False

    print("Registering av.by account for VIN testing...")
    captcha_token = obtain_captcha_token(reg_args, user_agent=reg_args.user_agent, index=1)
    account = register_one_account(
        index=1,
        local_prefix=f"{args.prefix}_",
        display_name=args.name,
        user_agent=reg_args.user_agent,
        captcha_token=captcha_token,
        mail_wait_seconds=reg_args.mail_wait_seconds,
    )

    payload = asdict(account)
    payload.update(
        {
            "purpose": "vin_test",
            "daily_vin_limit": VIN_TEST_DAILY_LIMIT,
            "vin_checks_today": 0,
            "is_active": False,
            "notes": f"vin_test account; daily_vin_limit={VIN_TEST_DAILY_LIMIT}; phone=manual",
        }
    )

    db = SessionLocal()
    try:
        row = upsert_avby_service_account(db, payload)
    finally:
        db.close()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n=== VIN test account created ===")
    print(f"email:          {row.email}")
    print(f"avby_password:  {payload['avby_password']}")
    print(f"mailtm_password:{payload['mailtm_password']}")
    print(f"api_key:        {payload.get('api_key')}")
    print(f"daily limit:    {VIN_TEST_DAILY_LIMIT} VIN checks/day")
    print(f"saved to:       {output_path.resolve()}")
    print("\nNext: verify phone with your real BY number (+375):")
    print(f"  python tools/verify_avby_phone.py --from-db --email {row.email} --manual-phone 29XXXXXXX")
    print(f"  python tools/verify_avby_phone.py --from-db --email {row.email} --manual-phone 29XXXXXXX --sms-code CODE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
