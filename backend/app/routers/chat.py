"""Public chat API."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.chat_service import chat_available, run_chat
from app.config import settings
from app.db import get_db

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

_rate_lock = Lock()
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


class ChatHistoryItem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatHistoryItem] = Field(default_factory=list, max_length=8)
    session_id: str | None = Field(default=None, max_length=64)


class ChatCitation(BaseModel):
    title: str
    url: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[ChatCitation] = Field(default_factory=list)


def _client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _check_rate_limit(ip: str) -> None:
    limit = max(1, int(settings.chat_rate_limit_per_hour or 30))
    now = time.time()
    window = 3600.0
    with _rate_lock:
        bucket = _rate_buckets[ip]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много запросов. Попробуйте позже.",
            )
        bucket.append(now)


@router.get("/status")
def chat_status():
    return {
        "enabled": bool(settings.chat_enabled) and chat_available(),
        "model": settings.chat_model if chat_available() else None,
    }


@router.post("", response_model=ChatResponse)
def post_chat(
    body: ChatRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    if not settings.chat_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Chat disabled")
    if not chat_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat is not configured (OPENAI_API_KEY)",
        )

    ip = _client_ip(request)
    _check_rate_limit(ip)

    history = [{"role": h.role, "content": h.content} for h in body.history]
    result = run_chat(
        db,
        question=body.message,
        history=history,
        client_ip=ip,
        session_id=body.session_id,
    )
    if result.error == "empty question":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty message")
    if result.error == "question too long":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message too long")

    return ChatResponse(
        answer=result.answer,
        citations=[ChatCitation(title=c["title"], url=c["url"]) for c in result.citations],
    )
