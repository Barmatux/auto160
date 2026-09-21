"""Listing text embeddings (pgvector) for semantic search."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from datetime import datetime
from typing import Sequence

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CarListing, ListingEmbedding, ListingStatus

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_DIM = 1536
DESCRIPTION_MAX_CHARS = 1200
_TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё]+", re.UNICODE)


def build_listing_embed_text(listing: CarListing) -> str:
    desc = (listing.description or "").strip().replace("\n", " ")
    if len(desc) > DESCRIPTION_MAX_CHARS:
        desc = desc[:DESCRIPTION_MAX_CHARS].rstrip() + "…"
    parts = [
        listing.source or "",
        f"{listing.brand or ''} {listing.model or ''} {listing.year or ''}".strip(),
        listing.city or "",
        f"price BYN {listing.price}" if listing.price is not None else "price BYN unknown",
        " / ".join(
            str(x)
            for x in (
                f"{listing.engine_power_hp} hp" if listing.engine_power_hp else None,
                f"{listing.engine_capacity_l} L" if listing.engine_capacity_l else None,
                listing.engine_type,
                listing.transmission_type,
                listing.body_type,
            )
            if x
        ),
        desc,
    ]
    return " | ".join(p for p in parts if p)


def content_hash(text_value: str) -> str:
    return hashlib.sha256(text_value.encode("utf-8")).hexdigest()


def resolved_embedding_provider() -> str:
    configured = (settings.embedding_provider or "openai").strip().lower()
    if configured == "local":
        return "local"
    if (settings.openai_api_key or "").strip():
        return "openai"
    return "local"


def resolved_embedding_model() -> str:
    if resolved_embedding_provider() == "local":
        return "local-hash-v1"
    return (settings.embedding_model or "text-embedding-3-small").strip()


def _embedding_client() -> OpenAI:
    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    kwargs: dict = {"api_key": api_key}
    base = (settings.openai_base_url or "").strip()
    if base:
        kwargs["base_url"] = base
    return OpenAI(**kwargs)


def _local_embed_text(text_value: str, dim: int = DEFAULT_EMBEDDING_DIM) -> list[float]:
    """Deterministic bag-of-tokens hash embedding (unit L2). Plumbing/smoke until OpenAI key is set."""
    vec = [0.0] * dim
    tokens = _TOKEN_RE.findall((text_value or "").lower())
    if not tokens:
        tokens = ["empty"]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for offset in range(0, 32, 4):
            idx = int.from_bytes(digest[offset : offset + 4], "little") % dim
            sign = 1.0 if digest[(offset + 3) % 32] % 2 == 0 else -1.0
            vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    if not texts:
        return []
    if resolved_embedding_provider() == "local":
        return [_local_embed_text(value) for value in texts]

    client = _embedding_client()
    model = resolved_embedding_model()
    response = client.embeddings.create(model=model, input=list(texts))
    ordered = sorted(response.data, key=lambda row: row.index)
    return [list(row.embedding) for row in ordered]


def reindex_listings(
    db: Session,
    *,
    listing_ids: Sequence[int] | None = None,
    limit: int = 0,
    force: bool = False,
    batch_size: int = 64,
    only_published: bool = True,
) -> dict[str, int]:
    """Upsert embeddings for published listings. Skips unchanged content_hash unless force."""
    provider = resolved_embedding_provider()
    model_name = resolved_embedding_model()
    if provider == "local":
        logger.warning(
            "embedding provider=local (hash vectors); set OPENAI_API_KEY for production quality"
        )

    query = db.query(CarListing)
    if only_published:
        query = query.filter(CarListing.status == ListingStatus.published)
    if listing_ids:
        query = query.filter(CarListing.id.in_(list(listing_ids)))
    query = query.order_by(CarListing.id.asc())
    if limit and limit > 0:
        query = query.limit(limit)

    listings = query.all()
    existing = {
        row.listing_id: row
        for row in db.query(ListingEmbedding)
        .filter(ListingEmbedding.listing_id.in_([item.id for item in listings] or [-1]))
        .all()
    }

    pending: list[tuple[CarListing, str, str]] = []
    skipped = 0
    for listing in listings:
        text_value = build_listing_embed_text(listing)
        digest = content_hash(text_value)
        current = existing.get(listing.id)
        if (
            not force
            and current is not None
            and current.content_hash == digest
            and current.model == model_name
        ):
            skipped += 1
            continue
        pending.append((listing, text_value, digest))

    embedded = 0
    for start in range(0, len(pending), max(1, batch_size)):
        chunk = pending[start : start + batch_size]
        vectors = embed_texts([item[1] for item in chunk])
        now = datetime.utcnow()
        for (listing, _text, digest), vector in zip(chunk, vectors, strict=True):
            row = (
                db.query(ListingEmbedding)
                .filter(ListingEmbedding.listing_id == listing.id)
                .one_or_none()
            )
            if row is None:
                row = ListingEmbedding(listing_id=listing.id)
                db.add(row)
            row.embedding = vector
            row.content_hash = digest
            row.model = model_name
            row.updated_at = now
            existing[listing.id] = row
            embedded += 1
        try:
            db.commit()
        except Exception:
            db.rollback()
            # Retry one-by-one to survive concurrent reindex from sync containers.
            for (listing, text_value, digest), vector in zip(chunk, vectors, strict=True):
                row = (
                    db.query(ListingEmbedding)
                    .filter(ListingEmbedding.listing_id == listing.id)
                    .one_or_none()
                )
                if row is None:
                    row = ListingEmbedding(listing_id=listing.id)
                    db.add(row)
                row.embedding = vector
                row.content_hash = digest
                row.model = model_name
                row.updated_at = now
                db.commit()
            logger.warning("listing-embeddings batch retried one-by-one after conflict")
        logger.info("listing-embeddings batch embedded=%s total_done=%s", len(chunk), embedded)

    deleted = 0
    if only_published and not listing_ids and not (limit and limit > 0):
        stale = (
            db.query(ListingEmbedding)
            .join(CarListing, CarListing.id == ListingEmbedding.listing_id)
            .filter(CarListing.status != ListingStatus.published)
            .all()
        )
        for row in stale:
            db.delete(row)
            deleted += 1
        if deleted:
            db.commit()

    return {
        "scanned": len(listings),
        "embedded": embedded,
        "skipped": skipped,
        "deleted_stale": deleted,
    }


def search_similar(
    db: Session,
    query: str,
    *,
    limit: int = 20,
    status: ListingStatus = ListingStatus.published,
) -> list[tuple[CarListing, float]]:
    """Return published listings ordered by cosine distance (lower is closer)."""
    q = (query or "").strip()
    if not q:
        return []
    vector = embed_texts([q])[0]
    distance = ListingEmbedding.embedding.cosine_distance(vector)
    rows = db.execute(
        select(CarListing, distance.label("distance"))
        .join(ListingEmbedding, ListingEmbedding.listing_id == CarListing.id)
        .where(CarListing.status == status)
        .order_by(distance)
        .limit(limit)
    ).all()
    return [(listing, float(dist)) for listing, dist in rows]
