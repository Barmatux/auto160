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
from integrations.bca.store import connect, upsert_auction, upsert_document, upsert_lot

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
    seen_at: datetime,
) -> None:
    storage_path = ""
    if status == "downloaded":
        doc_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{kind}-{lot_pk or auction_id}.pdf"
        target = doc_dir / filename
        target.write_bytes(body)
        storage_path = str(target)
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
        documents: list[tuple[str, str, int | None]] = []
        seen_docs: set[tuple[str, str]] = set()
        for lot in lots:
            lot_pk = lot_ids[lot["vehicle_id"]]
            for field, kind in DOCUMENT_KINDS:
                url = lot.get(field) or ""
                if not url or (kind, url) in seen_docs:
                    continue
                seen_docs.add((kind, url))
                owner = None if kind in {"sale_catalogue", "sale_section"} else lot_pk
                documents.append((kind, url, owner))
        for kind, url, lot_pk in documents:
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
                seen_at=seen_at,
            )
        connection.commit()
    finally:
        connection.close()
    return {"db": str(db_path), "sale_id": auction["sale_id"], "lots": len(lots)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Store one BCA auction and its documents")
    parser.add_argument("--sale-id", default="")
    parser.add_argument("--pages-json", default="")
    parser.add_argument("--db", required=True)
    parser.add_argument("--doc-dir", default="")
    parser.add_argument("--fetch-report", default="")
    args = parser.parse_args()
    if not args.doc_dir:
        args.doc_dir = str(Path(args.db).with_suffix("")) + "-docs"
    summary = run(args)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
