from functools import lru_cache
from urllib.parse import parse_qs, quote, unquote, urlparse

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings


@lru_cache(maxsize=1)
def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket_exists() -> None:
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
        return
    except ClientError:
        pass
    except BotoCoreError:
        return

    try:
        client.create_bucket(Bucket=settings.s3_bucket)
    except (ClientError, BotoCoreError):
        # Storage may be unavailable during startup; app should remain usable.
        return


def generate_upload_url(storage_key: str, content_type: str) -> str:
    client = get_s3_client()
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": storage_key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.s3_presign_expires_seconds,
    )


def generate_download_url(storage_key: str) -> str:
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": storage_key},
        ExpiresIn=settings.s3_presign_expires_seconds,
    )


def object_exists(storage_key: str) -> bool:
    client = get_s3_client()
    try:
        client.head_object(Bucket=settings.s3_bucket, Key=storage_key)
        return True
    except (ClientError, BotoCoreError):
        return False


def build_app_download_url(storage_key: str) -> str:
    return f"/media/object?key={quote(storage_key, safe='')}"


_REMOTE_IMAGE_HOSTS = {"avcdn.av.by"}


def is_remote_catalog_image_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and parsed.netloc in _REMOTE_IMAGE_HOSTS


def build_remote_image_url(url: str) -> str:
    return f"/media/remote?url={quote(url.strip(), safe='')}"


def normalize_display_image_url(url: str | None) -> str | None:
    if not url:
        return None
    cleaned = url.strip()
    if not cleaned:
        return None
    if cleaned.startswith("/media/"):
        return cleaned
    if is_remote_catalog_image_url(cleaned):
        return build_remote_image_url(cleaned)
    return cleaned


def extract_remote_source_url(url: str | None) -> str | None:
    """Return raw avcdn URL from a display/proxy URL when possible."""
    if not url:
        return None
    cleaned = url.strip()
    if not cleaned:
        return None
    if is_remote_catalog_image_url(cleaned):
        return cleaned

    parsed = urlparse(cleaned)
    path = parsed.path or ""
    if path.endswith("/media/remote") or path == "/media/remote" or "/media/remote" in path:
        values = parse_qs(parsed.query).get("url") or []
        if values:
            candidate = unquote(values[0]).strip()
            if is_remote_catalog_image_url(candidate):
                return candidate
    return None


def build_og_image_path(url: str | None) -> str:
    """Path for messenger-friendly JPEG og:image (AVIF is not accepted by Telegram)."""
    if not url:
        return "/static/og-default.png"
    cleaned = url.strip()
    if cleaned.startswith("/media/og/listing/") and (".jpg" in cleaned):
        return cleaned
    source = extract_remote_source_url(cleaned)
    if source:
        return f"/media/og-image?url={quote(source, safe='')}"
    if cleaned.startswith("/"):
        return cleaned
    return "/static/og-default.png"
