import argparse
import hashlib
import mimetypes
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import CatalogItem, CatalogItemPhoto
from app.config import settings
from app.storage import ensure_bucket_exists, get_s3_client


def _extract_raw_photo_url(raw_specs: dict | None) -> str | None:
    if not isinstance(raw_specs, dict):
        return None
    detail = raw_specs.get("modification_detail") or {}
    if not isinstance(detail, dict):
        return None
    photos = detail.get("photos")
    if not isinstance(photos, list) or not photos:
        return None
    first = photos[0]
    if not isinstance(first, dict):
        return None
    big = first.get("big")
    if isinstance(big, dict) and big.get("url"):
        return str(big["url"])
    medium = first.get("medium")
    if isinstance(medium, dict) and medium.get("url"):
        return str(medium["url"])
    if first.get("url"):
        return str(first["url"])
    file_obj = first.get("file")
    if isinstance(file_obj, dict) and file_obj.get("url"):
        return str(file_obj["url"])
    return None


def _guess_ext_and_content_type(url: str, content_type_header: str | None) -> tuple[str, str]:
    content_type = (content_type_header or "").split(";")[0].strip().lower()
    if content_type in {"image/jpeg", "image/png", "image/webp"}:
        ext = mimetypes.guess_extension(content_type) or ".jpg"
        return ext, content_type

    parsed = urlparse(url)
    path_ext = Path(parsed.path).suffix.lower()
    if path_ext in {".jpg", ".jpeg"}:
        return ".jpg", "image/jpeg"
    if path_ext == ".png":
        return ".png", "image/png"
    if path_ext == ".webp":
        return ".webp", "image/webp"
    return ".jpg", "image/jpeg"


def _download_image(url: str, timeout: int) -> tuple[bytes, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Auto160/1.0; +https://auto160.local)",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        data = response.read()
        content_type = response.headers.get("Content-Type", "")
    return data, content_type


def _build_storage_key(catalog_item_id: int, source_url: str, ext: str) -> str:
    digest = hashlib.sha1(source_url.encode("utf-8")).hexdigest()[:16]
    return f"catalog/{catalog_item_id}/seed_{digest}{ext}"


def _sync_item_photo(
    db: Session,
    item: CatalogItem,
    s3_client,
    bucket: str,
    timeout: int,
    dry_run: bool,
    force: bool,
) -> tuple[str, str]:
    existing = (
        db.query(CatalogItemPhoto)
        .filter(CatalogItemPhoto.catalog_item_id == item.id)
        .order_by(CatalogItemPhoto.is_cover.desc(), CatalogItemPhoto.id.asc())
        .all()
    )
    if existing and not force:
        return "skip_has_photo", ""

    photo_url = _extract_raw_photo_url(item.raw_specs)
    if not photo_url:
        return "skip_no_source_url", ""

    try:
        payload, content_type_header = _download_image(photo_url, timeout=timeout)
    except Exception as exc:
        return "error_download", str(exc)

    if not payload:
        return "error_empty", "downloaded empty payload"

    ext, content_type = _guess_ext_and_content_type(photo_url, content_type_header)
    storage_key = _build_storage_key(item.id, photo_url, ext)

    if dry_run:
        return "would_upload", ""

    if not dry_run:
        try:
            s3_client.put_object(
                Bucket=bucket,
                Key=storage_key,
                Body=payload,
                ContentType=content_type,
            )
        except Exception as exc:
            return "error_upload", str(exc)

        if existing and force:
            db.query(CatalogItemPhoto).filter(CatalogItemPhoto.catalog_item_id == item.id).update(
                {"is_cover": False}
            )
        elif not existing:
            db.query(CatalogItemPhoto).filter(CatalogItemPhoto.catalog_item_id == item.id).update(
                {"is_cover": False}
            )

        photo = CatalogItemPhoto(
            catalog_item_id=item.id,
            storage_key=storage_key,
            content_type=content_type,
            sort_order=0,
            is_cover=True,
        )
        db.add(photo)
        db.commit()

    return "uploaded", ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync catalog cover photos from parsed AV.BY data to MinIO/S3")
    parser.add_argument("--make", default=None, help="Filter by make (exact match)")
    parser.add_argument("--model", default=None, help="Filter by model (exact canonical value)")
    parser.add_argument("--generation", default=None, help="Filter by generation (exact match)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of catalog items (0 = no limit)")
    parser.add_argument("--timeout", type=int, default=25, help="HTTP timeout for image download")
    parser.add_argument("--dry-run", action="store_true", help="Do not upload anything, only print what would happen")
    parser.add_argument("--force", action="store_true", help="Replace/append even if item already has photos")
    args = parser.parse_args()

    ensure_bucket_exists()
    s3_client = get_s3_client()
    bucket = settings.s3_bucket

    db = SessionLocal()
    try:
        query = db.query(CatalogItem).filter(CatalogItem.source_site == "av.by")
        if args.make:
            query = query.filter(CatalogItem.make == args.make)
        if args.model:
            query = query.filter(CatalogItem.model == args.model)
        if args.generation:
            query = query.filter(CatalogItem.generation == args.generation)

        query = query.order_by(CatalogItem.id.asc())
        if args.limit and args.limit > 0:
            query = query.limit(args.limit)
        items = query.all()

        stats = {
            "uploaded": 0,
            "would_upload": 0,
            "skip_has_photo": 0,
            "skip_no_source_url": 0,
            "error_download": 0,
            "error_upload": 0,
            "error_empty": 0,
        }

        for idx, item in enumerate(items, start=1):
            status, detail = _sync_item_photo(
                db=db,
                item=item,
                s3_client=s3_client,
                bucket=bucket,
                timeout=args.timeout,
                dry_run=args.dry_run,
                force=args.force,
            )
            stats[status] = stats.get(status, 0) + 1
            suffix = f" ({detail})" if detail else ""
            print(f"[{idx}/{len(items)}] item={item.id} {item.make} {item.model} -> {status}{suffix}")

        print(
            "sync-summary: "
            + " ".join(f"{key}={value}" for key, value in stats.items())
            + f" total={len(items)} dry_run={args.dry_run} force={args.force}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
