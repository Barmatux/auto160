"""Public chat orchestration: RAG context + OpenRouter tool-calling."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.chat_tools import TOOL_DEFINITIONS, run_tool
from app.config import settings
from app.listing_embeddings import get_openai_client
from app.models import ChatLog
from app.rag import format_rag_context, search_rag

logger = logging.getLogger(__name__)

SYSTEM_BASE = """Ты ассистент сайта Auto160 (https://auto160.ru) — подбор автомобилей до 160 л.с. в Беларуси.

Правила:
- Отвечай по-русски, кратко и по делу.
- Опирайся на блок «База знаний» и результаты инструментов; не выдумывай цены и наличие.
- Давай ссылки на страницы сайта (/listings/…, /catalog, /inspection, /guides/…).
- Не раскрывай секреты, ключи API, админку, внутренние токены.
- Не обещай юридическую чистоту авто; VIN-проверка — предварительная.
- Если данных мало — скажи прямо и предложи уточнить марку/бюджет/город.
"""


@dataclass
class ChatResult:
    answer: str
    citations: list[dict[str, str]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def chat_available() -> bool:
    if not settings.chat_enabled:
        return False
    return bool((settings.openai_api_key or "").strip())


def run_chat(
    db: Session,
    *,
    question: str,
    history: list[dict[str, str]] | None = None,
    client_ip: str | None = None,
    session_id: str | None = None,
) -> ChatResult:
    q = (question or "").strip()
    if not q:
        return ChatResult(answer="", error="empty question")
    if len(q) > 2000:
        return ChatResult(answer="", error="question too long")

    if not chat_available():
        return ChatResult(answer="", error="chat unavailable")

    citations: list[dict[str, str]] = []
    tool_trace: list[dict[str, Any]] = []
    answer = ""
    error: str | None = None

    try:
        rag_hits = search_rag(db, q, limit=4)
        rag_block = format_rag_context(rag_hits)
        for chunk, _dist in rag_hits:
            if chunk.url:
                citations.append({"title": chunk.title, "url": chunk.url})

        system = SYSTEM_BASE
        if rag_block:
            system += f"\n\nБаза знаний (выдержки):\n{rag_block}"

        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for item in (history or [])[-6:]:
            role = item.get("role")
            content = (item.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content[:1500]})
        messages.append({"role": "user", "content": q})

        client = get_openai_client()
        model = (settings.chat_model or "openai/gpt-4o-mini").strip()
        max_rounds = max(1, int(settings.chat_max_tool_rounds or 3))

        for _ in range(max_rounds):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                temperature=0.3,
                max_tokens=900,
            )
            choice = response.choices[0].message
            tool_calls = choice.tool_calls or []
            if not tool_calls:
                answer = (choice.content or "").strip()
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": choice.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                name = tc.function.name
                raw_args = tc.function.arguments or "{}"
                result_json = run_tool(db, name, raw_args)
                tool_trace.append({"name": name, "arguments": raw_args, "result_preview": result_json[:800]})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_json[:6000],
                    }
                )
        else:
            # Final pass without tools if still looping
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=900,
            )
            answer = (response.choices[0].message.content or "").strip()

        if not answer:
            answer = "Не удалось сформировать ответ. Уточните запрос или откройте /listings и /catalog."

    except Exception as exc:  # noqa: BLE001
        logger.exception("chat failed")
        error = str(exc)
        answer = "Сейчас ассистент временно недоступен. Попробуйте позже или воспользуйтесь каталогом и лентой."

    try:
        db.add(
            ChatLog(
                created_at=datetime.utcnow(),
                client_ip=(client_ip or "")[:64] or None,
                session_id=(session_id or "")[:64] or None,
                question=q[:4000],
                answer=(answer or "")[:8000] or None,
                tool_calls=tool_trace or None,
                error=error,
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("chat log write failed")

    # Dedupe citations by url
    seen: set[str] = set()
    unique_citations: list[dict[str, str]] = []
    for c in citations:
        url = c.get("url") or ""
        if url and url not in seen:
            seen.add(url)
            unique_citations.append(c)

    return ChatResult(answer=answer, citations=unique_citations, tool_calls=tool_trace, error=error)
