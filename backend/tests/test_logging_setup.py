from pathlib import Path

from app.logging_setup import _attach_uvicorn_handlers, tail_log


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
