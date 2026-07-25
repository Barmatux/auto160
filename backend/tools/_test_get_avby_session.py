#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.avby_session import get_avby_session
from app.models import AvbyServiceAccount

account_id = int(sys.argv[1]) if len(sys.argv) > 1 else 29
db = SessionLocal()
acc = db.get(AvbyServiceAccount, account_id)
if not acc:
    raise SystemExit("not found")
session = get_avby_session(db, acc)
print("ok", acc.id, "api_key", session.api_key[:8] + "...", "expires", session.expires_at)
db.close()
