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

db = SessionLocal()
for acc in db.query(AvbyServiceAccount).order_by(AvbyServiceAccount.id):
    label = acc.email or acc.phone or "?"
    err = acc.error_message or "(нет)"
    print(f"#{acc.id} active={acc.is_active} {label}: {err}")
db.close()