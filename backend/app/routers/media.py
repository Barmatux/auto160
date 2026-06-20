from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings
from app.storage import get_s3_client

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
