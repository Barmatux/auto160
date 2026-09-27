"""Visitor↔manager messaging API (Autoplius-style inbox)."""

from __future__ import annotations

import re
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import get_optional_user_flexible, require_admin_flexible
from app.models import (
    CarListing,
    ListingStatus,
    Message,
    MessageSender,
    MessageThread,
    MessageThreadStatus,
    User,
)

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])
admin_router = APIRouter(prefix="/api/v1/admin/messages", tags=["admin-messages"])

GUEST_COOKIE = "auto160_msg"
GUEST_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
_RATE_LIMIT = 30
_RATE_WINDOW = 3600.0
_rate_lock = Lock()
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)

_PHONE_RE = re.compile(r"[^\d+]+")


class StartThreadRequest(BaseModel):
    listing_id: int
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=5, max_length=40)
    message: str = Field(min_length=1, max_length=4000)
    email: str | None = Field(default=None, max_length=255)


class PostMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    id: int
    sender: str
    body: str
    created_at: datetime
    sender_user_id: int | None = None


class ThreadListItem(BaseModel):
    id: int
    listing_id: int
    listing_title: str
    listing_url: str
    contact_name: str
    contact_phone: str
    status: str
    last_message_at: datetime
    last_preview: str | None = None
    unread_count: int = 0


class ThreadDetail(BaseModel):
    id: int
    listing_id: int
    listing_title: str
    listing_url: str
    contact_name: str
    contact_phone: str
    contact_email: str | None
    status: str
    last_message_at: datetime
    messages: list[MessageOut]


class UnreadCountOut(BaseModel):
    count: int


def _client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _check_rate_limit(key: str) -> None:
    now = time.time()
    with _rate_lock:
        bucket = _rate_buckets[key]
        while bucket and now - bucket[0] > _RATE_WINDOW:
            bucket.popleft()
        if len(bucket) >= _RATE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много сообщений. Попробуйте позже.",
            )
        bucket.append(now)


def _normalize_phone(raw: str) -> str:
    cleaned = _PHONE_RE.sub("", (raw or "").strip())
    if len(cleaned) < 5:
        raise HTTPException(status_code=400, detail="Укажите корректный телефон")
    return cleaned[:40]


def _normalize_name(raw: str) -> str:
    cleaned = " ".join((raw or "").split())
    if not cleaned:
        raise HTTPException(status_code=400, detail="Укажите имя")
    return cleaned[:120]


def _guest_token_from_request(request: Request) -> str | None:
    token = (request.cookies.get(GUEST_COOKIE) or "").strip()
    if token and len(token) <= 64:
        return token
    return None


def _ensure_guest_token(request: Request, response: Response) -> str:
    existing = _guest_token_from_request(request)
    if existing:
        return existing
    token = uuid.uuid4().hex
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    secure = request.url.scheme == "https" or forwarded_proto == "https"
    response.set_cookie(
        key=GUEST_COOKIE,
        value=token,
        max_age=GUEST_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )
    return token


def _listing_title(listing: CarListing) -> str:
    parts = [listing.brand or "", listing.model or "", str(listing.year or "")]
    title = " ".join(p for p in parts if p).strip()
    return title or listing.title or f"Объявление #{listing.id}"


def _message_out(msg: Message) -> MessageOut:
    return MessageOut(
        id=msg.id,
        sender=msg.sender.value if hasattr(msg.sender, "value") else str(msg.sender),
        body=msg.body,
        created_at=msg.created_at,
        sender_user_id=msg.sender_user_id,
    )


def _visitor_owns_thread(thread: MessageThread, *, user: User | None, guest_token: str | None) -> bool:
    if user is not None and thread.user_id == user.id:
        return True
    if guest_token and thread.guest_token and thread.guest_token == guest_token:
        return True
    return False


def _count_unread_for_visitor(db: Session, thread: MessageThread) -> int:
    q = db.query(func.count(Message.id)).filter(
        Message.thread_id == thread.id,
        Message.sender == MessageSender.manager,
    )
    if thread.visitor_last_read_at is not None:
        q = q.filter(Message.created_at > thread.visitor_last_read_at)
    return int(q.scalar() or 0)


def _count_unread_for_managers(db: Session, thread: MessageThread) -> int:
    q = db.query(func.count(Message.id)).filter(
        Message.thread_id == thread.id,
        Message.sender == MessageSender.visitor,
    )
    if thread.manager_last_read_at is not None:
        q = q.filter(Message.created_at > thread.manager_last_read_at)
    return int(q.scalar() or 0)


def _last_preview(db: Session, thread_id: int) -> str | None:
    msg = (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .first()
    )
    if not msg:
        return None
    text = " ".join(msg.body.split())
    return text[:140] + ("…" if len(text) > 140 else "")


def _thread_list_item(db: Session, thread: MessageThread, *, for_manager: bool) -> ThreadListItem:
    listing = thread.listing
    unread = _count_unread_for_managers(db, thread) if for_manager else _count_unread_for_visitor(db, thread)
    return ThreadListItem(
        id=thread.id,
        listing_id=thread.listing_id,
        listing_title=_listing_title(listing) if listing else f"#{thread.listing_id}",
        listing_url=f"/listings/{thread.listing_id}",
        contact_name=thread.contact_name,
        contact_phone=thread.contact_phone,
        status=thread.status.value if hasattr(thread.status, "value") else str(thread.status),
        last_message_at=thread.last_message_at,
        last_preview=_last_preview(db, thread.id),
        unread_count=unread,
    )


def _thread_detail(db: Session, thread: MessageThread) -> ThreadDetail:
    listing = thread.listing
    messages = (
        db.query(Message)
        .filter(Message.thread_id == thread.id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )
    return ThreadDetail(
        id=thread.id,
        listing_id=thread.listing_id,
        listing_title=_listing_title(listing) if listing else f"#{thread.listing_id}",
        listing_url=f"/listings/{thread.listing_id}",
        contact_name=thread.contact_name,
        contact_phone=thread.contact_phone,
        contact_email=thread.contact_email,
        status=thread.status.value if hasattr(thread.status, "value") else str(thread.status),
        last_message_at=thread.last_message_at,
        messages=[_message_out(m) for m in messages],
    )


@router.post("/threads", response_model=ThreadDetail)
def start_thread(
    body: StartThreadRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user_flexible),
):
    _check_rate_limit(f"ip:{_client_ip(request)}")
    listing = (
        db.query(CarListing)
        .filter(CarListing.id == body.listing_id, CarListing.status == ListingStatus.published)
        .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    name = _normalize_name(body.name)
    phone = _normalize_phone(body.phone)
    text = body.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Введите сообщение")

    guest_token = None
    if user is None:
        guest_token = _ensure_guest_token(request, response)
        _check_rate_limit(f"guest:{guest_token}")
    else:
        _check_rate_limit(f"user:{user.id}")

    thread_q = db.query(MessageThread).filter(
        MessageThread.listing_id == listing.id,
        MessageThread.status == MessageThreadStatus.open,
    )
    if user is not None:
        thread_q = thread_q.filter(MessageThread.user_id == user.id)
    else:
        thread_q = thread_q.filter(MessageThread.guest_token == guest_token)
    thread = thread_q.first()

    now = datetime.utcnow()
    if thread is None:
        thread = MessageThread(
            listing_id=listing.id,
            user_id=user.id if user else None,
            guest_token=guest_token,
            contact_name=name,
            contact_phone=phone,
            contact_email=(body.email or "").strip() or None,
            status=MessageThreadStatus.open,
            visitor_last_read_at=now,
            manager_last_read_at=None,
            last_message_at=now,
            created_at=now,
        )
        db.add(thread)
        db.flush()
    else:
        thread.contact_name = name
        thread.contact_phone = phone
        if body.email:
            thread.contact_email = body.email.strip() or thread.contact_email

    msg = Message(
        thread_id=thread.id,
        sender=MessageSender.visitor,
        sender_user_id=user.id if user else None,
        body=text[:4000],
        created_at=now,
    )
    db.add(msg)
    thread.last_message_at = now
    thread.visitor_last_read_at = now
    db.commit()
    db.refresh(thread)
    thread = (
        db.query(MessageThread)
        .options(joinedload(MessageThread.listing))
        .filter(MessageThread.id == thread.id)
        .first()
    )
    return _thread_detail(db, thread)


@router.get("/threads", response_model=list[ThreadListItem])
def list_visitor_threads(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user_flexible),
):
    guest_token = _guest_token_from_request(request)
    if user is None and not guest_token:
        return []
    q = db.query(MessageThread).options(joinedload(MessageThread.listing))
    if user is not None:
        q = q.filter(or_(MessageThread.user_id == user.id, MessageThread.guest_token == guest_token))
    else:
        q = q.filter(MessageThread.guest_token == guest_token)
    threads = q.order_by(MessageThread.last_message_at.desc()).limit(100).all()
    return [_thread_list_item(db, t, for_manager=False) for t in threads]


@router.get("/threads/{thread_id}", response_model=ThreadDetail)
def get_visitor_thread(
    thread_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user_flexible),
):
    thread = (
        db.query(MessageThread)
        .options(joinedload(MessageThread.listing))
        .filter(MessageThread.id == thread_id)
        .first()
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    guest_token = _guest_token_from_request(request)
    if not _visitor_owns_thread(thread, user=user, guest_token=guest_token):
        raise HTTPException(status_code=403, detail="Нет доступа")
    thread.visitor_last_read_at = datetime.utcnow()
    db.commit()
    return _thread_detail(db, thread)


@router.post("/threads/{thread_id}/messages", response_model=ThreadDetail)
def post_visitor_message(
    thread_id: int,
    body: PostMessageRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user_flexible),
):
    _check_rate_limit(f"ip:{_client_ip(request)}")
    thread = (
        db.query(MessageThread)
        .options(joinedload(MessageThread.listing))
        .filter(MessageThread.id == thread_id)
        .first()
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    guest_token = _guest_token_from_request(request)
    if not _visitor_owns_thread(thread, user=user, guest_token=guest_token):
        raise HTTPException(status_code=403, detail="Нет доступа")
    if thread.status != MessageThreadStatus.open:
        raise HTTPException(status_code=400, detail="Диалог закрыт")
    text = body.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Введите сообщение")
    if user is not None:
        _check_rate_limit(f"user:{user.id}")
    elif guest_token:
        _check_rate_limit(f"guest:{guest_token}")

    now = datetime.utcnow()
    db.add(
        Message(
            thread_id=thread.id,
            sender=MessageSender.visitor,
            sender_user_id=user.id if user else None,
            body=text[:4000],
            created_at=now,
        )
    )
    thread.last_message_at = now
    thread.visitor_last_read_at = now
    db.commit()
    db.refresh(thread)
    return _thread_detail(db, thread)


@router.get("/unread-count", response_model=UnreadCountOut)
def visitor_unread_count(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user_flexible),
):
    guest_token = _guest_token_from_request(request)
    if user is None and not guest_token:
        return UnreadCountOut(count=0)
    threads_q = db.query(MessageThread.id, MessageThread.visitor_last_read_at)
    if user is not None:
        threads_q = threads_q.filter(or_(MessageThread.user_id == user.id, MessageThread.guest_token == guest_token))
    else:
        threads_q = threads_q.filter(MessageThread.guest_token == guest_token)
    total = 0
    for thread_id, last_read in threads_q.all():
        q = db.query(func.count(Message.id)).filter(
            Message.thread_id == thread_id,
            Message.sender == MessageSender.manager,
        )
        if last_read is not None:
            q = q.filter(Message.created_at > last_read)
        total += int(q.scalar() or 0)
    return UnreadCountOut(count=total)


@admin_router.get("/threads", response_model=list[ThreadListItem])
def admin_list_threads(
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_flexible),
):
    threads = (
        db.query(MessageThread)
        .options(joinedload(MessageThread.listing))
        .order_by(MessageThread.last_message_at.desc())
        .limit(200)
        .all()
    )
    items = [_thread_list_item(db, t, for_manager=True) for t in threads]
    if unread_only:
        items = [i for i in items if i.unread_count > 0]
    return items


@admin_router.get("/unread-count", response_model=UnreadCountOut)
def admin_unread_count(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_flexible),
):
    threads = db.query(MessageThread.id, MessageThread.manager_last_read_at).all()
    total = 0
    for thread_id, last_read in threads:
        q = db.query(func.count(Message.id)).filter(
            Message.thread_id == thread_id,
            Message.sender == MessageSender.visitor,
        )
        if last_read is not None:
            q = q.filter(Message.created_at > last_read)
        total += int(q.scalar() or 0)
    return UnreadCountOut(count=total)


@admin_router.get("/threads/{thread_id}", response_model=ThreadDetail)
def admin_get_thread(
    thread_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_flexible),
):
    thread = (
        db.query(MessageThread)
        .options(joinedload(MessageThread.listing))
        .filter(MessageThread.id == thread_id)
        .first()
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    thread.manager_last_read_at = datetime.utcnow()
    db.commit()
    return _thread_detail(db, thread)


@admin_router.post("/threads/{thread_id}/messages", response_model=ThreadDetail)
def admin_post_message(
    thread_id: int,
    body: PostMessageRequest,
    db: Session = Depends(get_db),
    manager: User = Depends(require_admin_flexible),
):
    thread = (
        db.query(MessageThread)
        .options(joinedload(MessageThread.listing))
        .filter(MessageThread.id == thread_id)
        .first()
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    text = body.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Введите сообщение")
    now = datetime.utcnow()
    db.add(
        Message(
            thread_id=thread.id,
            sender=MessageSender.manager,
            sender_user_id=manager.id,
            body=text[:4000],
            created_at=now,
        )
    )
    thread.last_message_at = now
    thread.manager_last_read_at = now
    if thread.status != MessageThreadStatus.open:
        thread.status = MessageThreadStatus.open
    db.commit()
    db.refresh(thread)
    return _thread_detail(db, thread)
