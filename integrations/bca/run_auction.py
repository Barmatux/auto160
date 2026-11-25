"""Load one BCA sale into the local auction tables and fetch its documents.

    python integrations/bca/run_auction.py --sale-id <guid> --db .tmp-bca/bca.sqlite
    python integrations/bca/run_auction.py --pages-json sale.json --db .tmp-bca/bca.sqlite

Direct requests from a datacenter address are often blocked. ``--fetch-report``
supplies document bodies already retrieved through a residential session.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.bca.client import BcaClient, DownloadResult
from integrations.bca.normalize import auction_from_lots, lot_from_row
from integrations.bca.s3 import object_key, put_bytes, settings_from_env
from integrations.bca.store import connect, set_photo_s3_key, upsert_auction, upsert_document, upsert_lot

DOCUMENT_KINDS = (
    ("condition_report_url", "inspection"),
    ("mechanical_report_url", "mechanical"),
    ("catalogue_url", "sale_catalogue"),
    ("section_url", "sale_section"),
)


def _pages_from_file(path: Path) -> tuple[list[dict], bool]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    pages = payload.get("pages") if isinstance(payload, dict) else payload
    if not isinstance(pages, list):
        raise SystemExit("pages JSON must contain a pages list")
    can_view_pricing = any(bool(page.get("can_view_pricing")) for page in pages)
    return pages, can_view_pricing


def _lots_from_pages(pages: list[dict]) -> list[dict]:
    lots: list[dict] = []
    seen: set[str] = set()
    for page in pages:
        for row in page.get("lots") or []:
            if not isinstance(row, dict):
                continue
            lot = lot_from_row(row)
            if not lot["vehicle_id"] or lot["vehicle_id"] in seen:
                continue
            seen.add(lot["vehicle_id"])
            lots.append(lot)
    return lots


def _classify(result: DownloadResult) -> tuple[str, str]:
    if result.error:
        return "blocked", result.error
    if result.body.startswith(b"%PDF"):
        return "downloaded", ""
    head = result.body.lstrip()[:80].lower()
    if b"<html" in head or b"<!doctype" in head or "html" in result.content_type.lower():
        return "not_pdf", "response is HTML, not a PDF"
    return "unexpected", f"content-type {result.content_type or 'unknown'}"


def _load_report(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise SystemExit("fetch report must be a list")
    return {str(item["url"]): item for item in items if item.get("url")}


def _image_ext(body: bytes, content_type: str) -> str:
    if body.startswith(b"\xff\xd8") or "jpeg" in content_type:
        return ".jpg"
    if body.startswith(b"\x89PNG") or "png" in content_type:
        return ".png"
    if body.startswith(b"RIFF") or "webp" in content_type:
        return ".webp"
    return ""


def _publish(body: bytes, key: str, content_type: str, local_path: Path) -> tuple[str, str]:
    settings = settings_from_env()
    if settings is not None:
        put_bytes(settings, key=key, body=body, content_type=content_type)
        return key, ""
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(body)
    return str(local_path), "S3 credentials are not set; saved locally"


def _store_body(
    connection,
    *,
    auction_id: int,
    lot_pk: int | None,
    kind: str,
    url: str,
    body: bytes,
    content_type: str,
    status: str,
    detail: str,
    doc_dir: Path,
    sale_id: str,
    vehicle_id: str,
    seen_at: datetime,
) -> None:
    storage_path = ""
    if status == "downloaded" and body:
        if vehicle_id:
            key = object_key(f"bca/{vehicle_id}", kind, source=url, ext=".pdf")
        else:
            key = object_key(f"bca/sales/{sale_id}", kind, source=url, ext=".pdf")
        storage_path, note = _publish(body, key, content_type or "application/pdf", doc_dir / Path(key).name)
        if note:
            detail = f"{detail}; {note}".strip("; ")
    upsert_document(
        connection,
        auction_id=auction_id,
        lot_pk=lot_pk,
        kind=kind,
        source_url=url,
        content_type=content_type,
        byte_size=len(body) if body else None,
        storage_path=storage_path,
        status=status,
        detail=detail,
        fetched_at=seen_at,
    )


def _apply_report_item(item: dict, doc_dir: Path) -> tuple[bytes, str, str, str]:
    content_type = str(item.get("content_type") or "")
    status = str(item.get("status") or "")
    detail = str(item.get("detail") or "body from residential session")
    path = item.get("path")
    if path:
        body = Path(path).read_bytes()
        if not status:
            status = "downloaded" if body.startswith(b"%PDF") else "not_pdf"
        return body, content_type or "application/pdf", status, detail
    size = item.get("byte_size")
    body = b""
    if not status:
        status = "not_pdf" if "html" in content_type.lower() else "unexpected"
    if size and not body:
        detail = detail or f"observed {size} bytes"
    return body, content_type, status, detail


def _load_photo(client: BcaClient, lot: dict, photo_dir: Path | None) -> tuple[bytes, str]:
    if photo_dir is not None:
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            candidate = photo_dir / f"{lot['vehicle_id']}{ext}"
            if candidate.is_file():
                return candidate.read_bytes(), "image/jpeg" if ext in {".jpg", ".jpeg"} else f"image/{ext[1:]}"
    if not lot.get("image_url"):
        return b"", ""
    result = client.download(lot["image_url"])
    if result.error:
        return b"", ""
    return result.body, result.content_type


def _store_photos(connection, client: BcaClient, lots: list[dict], *, photo_dir: Path | None, doc_dir: Path) -> int:
    uploaded = 0
    for lot in lots:
        body, content_type = _load_photo(client, lot, photo_dir)
        ext = _image_ext(body, content_type)
        if not ext or not lot.get("image_url"):
            continue
        key = object_key(f"bca/{lot['vehicle_id']}", "000", source=lot["image_url"], ext=ext)
        stored, _note = _publish(body, key, content_type or "image/jpeg", doc_dir / "photos" / f"{lot['vehicle_id']}{ext}")
        if stored == key:
            set_photo_s3_key(connection, lot["vehicle_id"], key)
            uploaded += 1
    return uploaded


def run(args: argparse.Namespace) -> dict:
    seen_at = datetime.now(timezone.utc)
    if args.pages_json:
        pages, can_view_pricing = _pages_from_file(Path(args.pages_json))
    else:
        if not args.sale_id:
            raise SystemExit("pass --sale-id or --pages-json")
        pages, can_view_pricing = BcaClient().fetch_sale(args.sale_id)
    lots = _lots_from_pages(pages)
    if args.sale_id:
        lots = [lot for lot in lots if lot["sale_id"] == args.sale_id]
    if not lots:
        raise SystemExit("sale returned no lots")
    auction = auction_from_lots(lots, can_view_pricing=can_view_pricing)
    db_path = Path(args.db)
    doc_dir = Path(args.doc_dir)
    report = _load_report(Path(args.fetch_report) if args.fetch_report else None)
    client = BcaClient()
    connection = connect(db_path)
    try:
        auction_id = upsert_auction(connection, auction, seen_at=seen_at)
        lot_ids: dict[str, int] = {}
        for lot in lots:
            lot_ids[lot["vehicle_id"]] = upsert_lot(connection, auction_id, lot, seen_at=seen_at)
        documents: list[tuple[str, str, int | None, str]] = []
        seen_docs: set[tuple[str, str]] = set()
        for lot in lots:
            lot_pk = lot_ids[lot["vehicle_id"]]
            for field, kind in DOCUMENT_KINDS:
                url = lot.get(field) or ""
                if not url or (kind, url) in seen_docs:
                    continue
                seen_docs.add((kind, url))
                owner = None if kind in {"sale_catalogue", "sale_section"} else lot_pk
                owner_vehicle = "" if owner is None else lot["vehicle_id"]
                documents.append((kind, url, owner, owner_vehicle))
        photos_uploaded = _store_photos(
            connection,
            client,
            lots,
            photo_dir=Path(args.photo_dir) if args.photo_dir else None,
            doc_dir=doc_dir,
        )
        for kind, url, lot_pk, vehicle_id in documents:
            result = client.download(url)
            status, detail = _classify(result)
            body = result.body if status == "downloaded" else b""
            content_type = result.content_type
            if status != "downloaded" and url in report:
                body, content_type, status, detail = _apply_report_item(report[url], doc_dir)
                if status == "not_pdf" and not body and report[url].get("byte_size"):
                    upsert_document(
                        connection,
                        auction_id=auction_id,
                        lot_pk=lot_pk,
                        kind=kind,
                        source_url=url,
                        content_type=content_type,
                        byte_size=int(report[url]["byte_size"]),
                        storage_path="",
                        status=status,
                        detail=detail,
                        fetched_at=seen_at,
                    )
                    continue
            _store_body(
                connection,
                auction_id=auction_id,
                lot_pk=lot_pk,
                kind=kind,
                url=url,
                body=body,
                content_type=content_type,
                status=status,
                detail=detail,
                doc_dir=doc_dir,
                sale_id=auction["sale_id"],
                vehicle_id=vehicle_id,
                seen_at=seen_at,
            )
        connection.commit()
    finally:
        connection.close()
    return {
        "db": str(db_path),
        "sale_id": auction["sale_id"],
        "lots": len(lots),
        "photos_uploaded": photos_uploaded,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Store one BCA auction and its documents")
    parser.add_argument("--sale-id", default="")
    parser.add_argument("--pages-json", default="")
    parser.add_argument("--db", required=True)
    parser.add_argument("--doc-dir", default="")
    parser.add_argument("--fetch-report", default="")
    parser.add_argument("--photo-dir", default="", help="Directory of {vehicle_id}.jpg files")
    args = parser.parse_args()
    if not args.doc_dir:
        args.doc_dir = str(Path(args.db).with_suffix("")) + "-docs"
    summary = run(args)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
