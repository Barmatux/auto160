import io
from urllib.error import URLError
from urllib.request import Request, urlopen

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.listing_photos import listing_photo_candidate_urls
from app.models import CarListing, ListingStatus
from app.storage import extract_remote_source_url, get_s3_client, is_remote_catalog_image_url

router = APIRouter(prefix="/media", tags=["media"])

_REMOTE_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Auto160/1.0; +https://av.by/)",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://av.by/",
}

_OG_HEADERS = {
    "Cache-Control": "public, max-age=86400",
    "Content-Disposition": "inline; filename=og-preview.jpg",
}


def _fetch_remote_image(url: str) -> tuple[bytes, str]:
    request = Request(url.strip(), headers=_REMOTE_FETCH_HEADERS)
    with urlopen(request, timeout=20) as response:
        payload = response.read()
        content_type = (response.headers.get("Content-Type") or "application/octet-stream").split(";")[0].strip()
    if not payload:
        raise HTTPException(status_code=404, detail="Image not available")
    return payload, content_type


def _to_jpeg_bytes(payload: bytes, *, max_side: int = 1200, quality: int = 85) -> bytes:
    try:
        image = Image.open(io.BytesIO(payload))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=404, detail="Image not decodable") from exc

    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    elif image.mode == "L":
        image = image.convert("RGB")

    width, height = image.size
    longest = max(width, height)
    if longest > max_side:
        scale = max_side / float(longest)
        image = image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()


def _jpeg_response(jpeg: bytes, *, request: Request) -> Response:
    headers = {
        **_OG_HEADERS,
        "Content-Length": str(len(jpeg)),
    }
    if request.method == "HEAD":
        return Response(status_code=200, media_type="image/jpeg", headers=headers)
    return Response(content=jpeg, media_type="image/jpeg", headers=headers)


def _source_url_for_listing(listing: CarListing) -> str | None:
    for candidate in listing_photo_candidate_urls(listing):
        source = extract_remote_source_url(candidate) or (
            candidate if is_remote_catalog_image_url(candidate) else None
        )
        if source:
            return source
    return None


@router.get("/object")
def get_media_object(key: str = Query(..., min_length=1)):
    # Serve media through app domain so browser doesn't need direct MinIO access.
    if ".." in key or key.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid object key")
    try:
        response = get_s3_client().get_object(Bucket=settings.s3_bucket, Key=key)
    except (ClientError, BotoCoreError):
        raise HTTPException(status_code=404, detail="Object not found")

    body = response.get("Body")
    if body is None:
        raise HTTPException(status_code=404, detail="Object body missing")
    content_type = response.get("ContentType") or "application/octet-stream"
    return StreamingResponse(body, media_type=content_type)


@router.get("/remote")
def get_remote_image(url: str = Query(..., min_length=8)):
    if not is_remote_catalog_image_url(url):
        raise HTTPException(status_code=400, detail="URL not allowed")

    try:
        payload, content_type = _fetch_remote_image(url)
    except (URLError, TimeoutError, ValueError):
        raise HTTPException(status_code=404, detail="Image not available")

    return StreamingResponse(io.BytesIO(payload), media_type=content_type)


@router.api_route("/og-image", methods=["GET", "HEAD"])
def get_og_image(request: Request, url: str = Query(..., min_length=8)):
    """JPEG preview for messengers (Telegram etc. reject AVIF og:image)."""
    if not is_remote_catalog_image_url(url):
        raise HTTPException(status_code=400, detail="URL not allowed")

    try:
        payload, _content_type = _fetch_remote_image(url)
    except (URLError, TimeoutError, ValueError):
        raise HTTPException(status_code=404, detail="Image not available")

    return _jpeg_response(_to_jpeg_bytes(payload), request=request)


@router.api_route("/og/listing/{listing_id}.jpg", methods=["GET", "HEAD"])
def get_listing_og_image(listing_id: int, request: Request, db: Session = Depends(get_db)):
    """Clean JPEG URL for listing previews (no query string; supports HEAD)."""
    listing = db.query(CarListing).filter(CarListing.id == listing_id).first()
    if listing is None or listing.status != ListingStatus.published:
        raise HTTPException(status_code=404, detail="Listing not found")

    source = _source_url_for_listing(listing)
    if not source:
        raise HTTPException(status_code=404, detail="Listing has no photo")

    try:
        payload, _content_type = _fetch_remote_image(source)
    except (URLError, TimeoutError, ValueError):
        raise HTTPException(status_code=404, detail="Image not available")

    return _jpeg_response(_to_jpeg_bytes(payload), request=request)
