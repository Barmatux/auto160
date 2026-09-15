from functools import lru_cache
from urllib.parse import quote, urlparse

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

_S3_CONFIG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "path"},
)


@lru_cache(maxsize=1)
def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region or "ru-central1",
        config=_S3_CONFIG,
    )


def ensure_bucket_exists() -> None:
    """Verify bucket is reachable. Prefer creating buckets in Yandex Cloud console."""
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
        return
    except ClientError:
        pass
    except BotoCoreError:
        return

    try:
        region = (settings.s3_region or "ru-central1").strip()
        if region and region != "us-east-1":
            client.create_bucket(
                Bucket=settings.s3_bucket,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        else:
            client.create_bucket(Bucket=settings.s3_bucket)
    except (ClientError, BotoCoreError):
        # Storage may be unavailable during startup; app should remain usable.
        return


def generate_upload_url(storage_key: str, content_type: str) -> str:
    """Presigned PUT for browser uploads (must use a public S3 endpoint)."""
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


def build_autoplius_media_url(storage_key: str) -> str:
    return f"/media/autoplius?key={quote(storage_key, safe='')}"


@lru_cache(maxsize=1)
def get_autoplius_s3_client():
    endpoint = (settings.autoplius_s3_endpoint_url or "").strip() or None
    access = (settings.autoplius_s3_access_key or "").strip()
    secret = (settings.autoplius_s3_secret_key or "").strip()
    if not access or not secret:
        raise RuntimeError("Autoplius S3 credentials are not configured")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=(settings.autoplius_s3_region or "ru-central1").strip(),
        config=_S3_CONFIG,
    )


def autoplius_bucket() -> str:
    return (settings.autoplius_s3_bucket or "autoplius-media").strip()


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
