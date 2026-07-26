from pathlib import Path

from app.logging_setup import tail_log


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
