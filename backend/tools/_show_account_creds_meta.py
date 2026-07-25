#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.models import AvbyServiceAccount

account_id = int(sys.argv[1]) if len(sys.argv) > 1 else 29
db = SessionLocal()
acc = db.get(AvbyServiceAccount, account_id)
if acc:
    print("phone", acc.phone)
    print("email", acc.email)
    print("pw_len", len(acc.avby_password or ""))
    print("pw_repr", repr(acc.avby_password))
db.close()
