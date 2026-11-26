"""Telegram bot webhook (operator replies and funnel buttons)."""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.telegram_bridge import bot_enabled, handle_update, webhook_secret

router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"], include_in_schema=False)


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if not bot_enabled() or not hmac.compare_digest(
        x_telegram_bot_api_secret_token or "", webhook_secret()
    ):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        update = await request.json()
    except ValueError:
        return {"ok": True}
    handle_update(db, update if isinstance(update, dict) else {})
    return {"ok": True}
