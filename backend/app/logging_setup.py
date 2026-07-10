"""Application logging: stdout + rotating files under LOG_DIR."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_SERVICES = ("api", "avby-sync", "avby-vin-session")

_configured = False


def log_dir() -> Path:
    raw = (os.environ.get("LOG_DIR") or "logs").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def setup_logging(service: str | None = None) -> logging.Logger:
    global _configured
    service_name = (service or os.environ.get("LOG_SERVICE") or "api").strip()
    if service_name not in LOG_SERVICES:
        service_name = "api"

    level_name = (os.environ.get("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    if _configured:
        return logging.getLogger(service_name)

    root.setLevel(level)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    directory = log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    log_file = directory / f"{service_name}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    _configured = True
    logger = logging.getLogger(service_name)
    logger.info("Logging initialized service=%s file=%s level=%s", service_name, log_file, level_name)
    return logger


def tail_log(service: str, *, lines: int = 200) -> tuple[str, Path | None]:
    if service not in LOG_SERVICES:
        raise ValueError(f"Unknown service: {service}")

    safe_lines = max(10, min(lines, 2000))
    directory = log_dir()
    candidates = [directory / f"{service}.log"]
    for suffix in (".1", ".2", ".3", ".4", ".5"):
        rotated = directory / f"{service}.log{suffix}"
        if rotated.exists():
            candidates.append(rotated)

    chunks: list[str] = []
    used_path: Path | None = None
    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            continue
        file_lines = text.splitlines()
        if len(file_lines) >= safe_lines:
            chunks = file_lines[-safe_lines:]
            used_path = path
            break
        chunks = file_lines + chunks
        used_path = path
        if len(chunks) >= safe_lines:
            chunks = chunks[-safe_lines:]
            break

    if not chunks:
        main_path = directory / f"{service}.log"
        return f"(log empty or missing: {main_path})", main_path if main_path.exists() else None

    return "\n".join(chunks), used_path
