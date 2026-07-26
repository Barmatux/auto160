from pathlib import Path
from datetime import UTC, datetime
import logging

from app.logging_setup import _attach_uvicorn_handlers, build_log_formatter, format_log_time, tail_log


def test_log_formatter_includes_timezone_offset(monkeypatch):
    monkeypatch.setenv("LOG_TIMEZONE", "Europe/Minsk")
    formatter = build_log_formatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert " INFO [test] hello" in formatted
    assert formatted[:4].isdigit()
    assert "+0300" in formatted or "+0200" in formatted


def test_format_log_time_uses_configured_timezone(monkeypatch):
    monkeypatch.setenv("LOG_TIMEZONE", "Europe/Minsk")
    text = format_log_time(datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC))
    assert text.endswith("+0300") or text.endswith("+0200")
    assert text.startswith("2026-07-26")


def test_attach_uvicorn_handlers_clears_default_uvicorn_handlers():
    import logging

    logging.getLogger("uvicorn.access").addHandler(logging.StreamHandler())
    handler = logging.NullHandler()
    _attach_uvicorn_handlers([handler], logging.INFO)
    logger = logging.getLogger("uvicorn.access")
    assert logger.handlers == [handler]


def test_attach_uvicorn_handlers_writes_access_log_to_file(tmp_path: Path, monkeypatch):
    import logging

    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    log_file = tmp_path / "api.log"
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))

    _attach_uvicorn_handlers([handler], logging.INFO)
    logging.getLogger("uvicorn.access").info('127.0.0.1:8000 - "GET /health HTTP/1.1" 200')

    assert 'GET /health HTTP/1.1" 200' in log_file.read_text(encoding="utf-8")


def test_tail_log_prefers_active_file_over_rotated_backup(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    service = "api"
    rotated = tmp_path / "api.log.1"
    rotated.write_text("\n".join(f"old-{i}" for i in range(300)), encoding="utf-8")
    active = tmp_path / "api.log"
    active.write_text("fresh-line-1\nfresh-line-2\n", encoding="utf-8")

    content, path = tail_log(service, lines=5)

    assert path == active
    assert "fresh-line-2" in content
    assert content.splitlines()[-1] == "fresh-line-2"


def test_tail_log_merges_rotated_files_in_order(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    service = "avby-archive"
    (tmp_path / "avby-archive.log.1").write_text("line-1\nline-2\n", encoding="utf-8")
    (tmp_path / "avby-archive.log").write_text("line-3\n", encoding="utf-8")

    content, _ = tail_log(service, lines=10)

    assert content.splitlines() == ["line-1", "line-2", "line-3"]
