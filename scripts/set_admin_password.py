#!/usr/bin/env python3
import sys
from app.security import hash_password
from app.db import SessionLocal
from app.models import User

pwd = sys.argv[1]
db = SessionLocal()
try:
    user = db.query(User).filter(User.email == "admin@auto160.com").first()
    if not user:
        raise SystemExit("admin user not found")
    user.password_hash = hash_password(pwd)
    db.commit()
    print("DB_UPDATED")
finally:
    db.close()
