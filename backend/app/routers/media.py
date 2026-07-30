import io
from urllib.error import URLError
from urllib.request import Request, urlopen

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.config import settings
from app.storage import get_s3_client, is_remote_catalog_image_url

router = APIRouter(prefix="/media", tags=["media"])


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

    request = Request(
        url.strip(),
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Auto160/1.0; +https://av.by/)",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://av.by/",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read()
            content_type = (response.headers.get("Content-Type") or "application/octet-stream").split(";")[0].strip()
    except (URLError, TimeoutError, ValueError):
        raise HTTPException(status_code=404, detail="Image not available")

    if not payload:
        raise HTTPException(status_code=404, detail="Image not available")
    return StreamingResponse(io.BytesIO(payload), media_type=content_type)
