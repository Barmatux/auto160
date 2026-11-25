"""Upload BCA photos and documents to the same bucket as the other scrapers.

Uses S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET, S3_REGION and
optional S3_PUBLIC_BASE_URL. Object keys live under ``bca/``.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class S3Settings:
    endpoint_url: str
    access_key: str
    secret_key: str
    bucket: str
    region: str
    public_base: str


def settings_from_env() -> S3Settings | None:
    access_key = os.environ.get("S3_ACCESS_KEY", "").strip()
    secret_key = os.environ.get("S3_SECRET_KEY", "").strip()
    if not access_key or not secret_key:
        return None
    return S3Settings(
        endpoint_url=os.environ.get("S3_ENDPOINT_URL", "").strip(),
        access_key=access_key,
        secret_key=secret_key,
        bucket=os.environ.get("S3_BUCKET", "").strip() or "auto160-media",
        region=os.environ.get("S3_REGION", "").strip() or "ru-central1",
        public_base=os.environ.get("S3_PUBLIC_BASE_URL", "").strip().rstrip("/"),
    )


def object_key(folder: str, name: str, *, source: str, ext: str) -> str:
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
    suffix = ext if ext.startswith(".") else f".{ext}"
    return f"{folder.strip('/')}/{name}_{digest}{suffix}"


def media_url(settings: S3Settings, key: str) -> str:
    if settings.public_base:
        return f"{settings.public_base}/{key.lstrip('/')}"
    from urllib.parse import quote

    return f"/media/object?key={quote(key, safe='')}"


def _client(settings: S3Settings):
    import boto3
    from botocore.client import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.endpoint_url or None,
        aws_access_key_id=settings.access_key,
        aws_secret_access_key=settings.secret_key,
        region_name=settings.region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def put_bytes(settings: S3Settings, *, key: str, body: bytes, content_type: str) -> None:
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        _client(settings).put_object(
            Bucket=settings.bucket,
            Key=key,
            Body=body,
            ContentType=content_type or "application/octet-stream",
        )
    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError(f"S3 put failed for {key}: {type(exc).__name__}") from exc


def head_size(settings: S3Settings, key: str) -> int | None:
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        response = _client(settings).head_object(Bucket=settings.bucket, Key=key)
    except (ClientError, BotoCoreError):
        return None
    return int(response.get("ContentLength") or 0)
