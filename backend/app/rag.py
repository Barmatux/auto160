"""RAG chunk indexing and semantic retrieval for chat."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.listing_embeddings import embed_texts, resolved_embedding_model
from app.models import RagChunk
from app.rag_seed import SEED_CHUNKS

logger = logging.getLogger(__name__)


def _content_hash(title: str, content: str, url: str | None) -> str:
    payload = f"{title}\n{url or ''}\n{content}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def reindex_rag_chunks(db: Session, *, force: bool = False) -> dict:
    """Upsert seed guide/FAQ chunks into rag_chunks with embeddings."""
    model_name = resolved_embedding_model()
    existing = {row.source_key: row for row in db.query(RagChunk).all()}
    now = datetime.utcnow()

    to_embed: list[tuple[object, str, str]] = []  # seed, digest, embed_text
    skipped = 0
    for seed in SEED_CHUNKS:
        digest = _content_hash(seed.title, seed.content, seed.url)
        row = existing.get(seed.source_key)
        if row is not None and not force and row.content_hash == digest and row.model == model_name:
            skipped += 1
            continue
        embed_text = f"{seed.title}\n{seed.content}"
        to_embed.append((seed, digest, embed_text))

    embedded = 0
    if to_embed:
        vectors = embed_texts([text for _, _, text in to_embed])
        for (seed, digest, _), vector in zip(to_embed, vectors, strict=True):
            row = existing.get(seed.source_key)
            if row is None:
                row = RagChunk(source_key=seed.source_key)
                db.add(row)
                existing[seed.source_key] = row
            row.title = seed.title
            row.content = seed.content
            row.url = seed.url
            row.embedding = vector
            row.content_hash = digest
            row.model = model_name
            row.updated_at = now
            embedded += 1
        db.commit()
        logger.info("rag-chunks embedded=%s skipped=%s", embedded, skipped)

    # Drop stale keys no longer in seed
    seed_keys = {s.source_key for s in SEED_CHUNKS}
    deleted = 0
    for key, row in list(existing.items()):
        if key not in seed_keys:
            db.delete(row)
            deleted += 1
    if deleted:
        db.commit()

    return {
        "seed_total": len(SEED_CHUNKS),
        "embedded": embedded,
        "skipped": skipped,
        "deleted_stale": deleted,
    }


def search_rag(
    db: Session,
    query: str,
    *,
    limit: int = 4,
) -> list[tuple[RagChunk, float]]:
    q = (query or "").strip()
    if not q:
        return []
    vector = embed_texts([q])[0]
    distance = RagChunk.embedding.cosine_distance(vector)
    rows = db.execute(
        select(RagChunk, distance.label("distance")).order_by(distance).limit(limit)
    ).all()
    return [(chunk, float(dist)) for chunk, dist in rows]


def format_rag_context(hits: list[tuple[RagChunk, float]]) -> str:
    if not hits:
        return ""
    parts: list[str] = []
    for chunk, dist in hits:
        link = f" ({chunk.url})" if chunk.url else ""
        parts.append(f"### {chunk.title}{link}\n{chunk.content}\n(distance={dist:.3f})")
    return "\n\n".join(parts)
