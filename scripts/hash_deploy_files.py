#!/usr/bin/env python3
import hashlib
import pathlib
import sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
files = [
    "backend/app/avby_accounts.py",
    "backend/app/avby_session.py",
    "backend/docker-compose.vm.yml",
    "backend/docker-compose.yml",
    "scripts/smoke-vm.sh",
    "backend/README.md",
    "backend/app/avby_offer_check.py",
    "backend/app/avby_public_photos.py",
]
for rel in files:
    path = root / rel
    if path.exists():
        print(hashlib.md5(path.read_bytes()).hexdigest(), rel)
    else:
        print("MISSING", rel)
