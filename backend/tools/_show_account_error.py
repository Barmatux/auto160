#!/usr/bin/env python3
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.db import SessionLocal
from app.models import AvbyServiceAccount

account_id = int(sys.argv[1]) if len(sys.argv) > 1 else 26
db = SessionLocal()
acc = db.get(AvbyServiceAccount, account_id)
if not acc:
    print(f"Account #{account_id} not found")
else:
    print(f"id={acc.id} phone={acc.phone} email={acc.email} active={acc.is_active} status={acc.status}")
    print(f"error_message={acc.error_message!r}")
db.close()
