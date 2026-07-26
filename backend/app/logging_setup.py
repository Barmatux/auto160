"""Application logging: stdout + rotating files under LOG_DIR."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_SERVICES = ("api", "avby-sync", "avby-vin-session", "avby-archive")

LOG_SERVICE_LABELS: dict[str, str] = {
    "api": "API (uvicorn)",
    "avby-sync": "Парсинг av.by",
    "avby-vin-session": "VIN session keeper",
    "avby-archive": "Архивация av.by",
}

_configured = False
_handlers: list[logging.Handler] = []
_log_level = logging.INFO


def _attach_uvicorn_handlers(handlers: list[logging.Handler], level: int) -> None:
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False
        for handler in handlers:
            if handler not in logger.handlers:
                logger.addHandler(handler)


def ensure_uvicorn_file_logging() -> None:
    """Re-attach file/stdout handlers after uvicorn configures its loggers."""
    if _handlers:
        _attach_uvicorn_handlers(_handlers, _log_level)


def log_dir() -> Path:
    raw = (os.environ.get("LOG_DIR") or "logs").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def setup_logging(service: str | None = None) -> logging.Logger:
    global _configured, _handlers, _log_level
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

    _handlers = [stream_handler, file_handler]
    _log_level = level
    if service_name == "api":
        _attach_uvicorn_handlers(_handlers, level)

    _configured = True
    logger = logging.getLogger(service_name)
    logger.info("Logging initialized service=%s file=%s level=%s", service_name, log_file, level_name)
    return logger


def _log_file_candidates(directory: Path, service: str) -> list[Path]:
    """Oldest → newest: .5 … .1, then the active log file."""
    paths: list[Path] = []
    for suffix in (".5", ".4", ".3", ".2", ".1", ""):
        path = directory / f"{service}.log{suffix}"
        if path.exists():
            paths.append(path)
    return paths


def tail_log(service: str, *, lines: int = 200) -> tuple[str, Path | None]:
    if service not in LOG_SERVICES:
        raise ValueError(f"Unknown service: {service}")

    safe_lines = max(10, min(lines, 2000))
    directory = log_dir()
    main_path = directory / f"{service}.log"
    candidates = _log_file_candidates(directory, service)

    all_lines: list[str] = []
    for path in candidates:
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            all_lines.extend(text.splitlines())

    if not all_lines:
        return f"(log empty or missing: {main_path})", main_path if main_path.exists() else None

    used_path = main_path if main_path.exists() else candidates[-1]
    return "\n".join(all_lines[-safe_lines:]), used_path
