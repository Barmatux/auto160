"""eu2.by client for auto160 internal Catalog Match API.

Copy this module into the eu2 service (or install as a shared util) and call
`reconcile_after_parse` after each successful parse run.

Env:
  AUTO160_CATALOG_BASE_URL  e.g. http://127.0.0.1:8000
  AUTO160_CATALOG_API_KEY   same as INTERNAL_CATALOG_API_KEY on auto160
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class CatalogCandidate:
    """Modification-level row to match against auto160 catalog_items."""

    make: str
    model: str
    external_ref: str | None = None
    generation: str | None = None
    year: int | None = None
    body_type: str | None = None
    fuel_type: str | None = None
    engine_power_hp: int | None = None
    engine_volume_l: float | None = None
    drivetrain: str | None = None
    transmission: str | None = None
    source_external_id: str | None = None

    def to_payload(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


@dataclass
class MatchResult:
    external_ref: str | None
    matched_catalog_item_id: int | None
    match_confidence: int
    reason: str
    make: str
    model: str
    gap_id: int | None = None


class Auto160CatalogError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class Auto160CatalogClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        *,
        timeout_sec: float = 30.0,
        max_retries: int = 3,
        retry_backoff_sec: float = 1.5,
    ) -> None:
        self.base_url = (base_url or os.environ.get("AUTO160_CATALOG_BASE_URL") or "").rstrip("/")
        self.api_key = api_key or os.environ.get("AUTO160_CATALOG_API_KEY") or ""
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.retry_backoff_sec = retry_backoff_sec
        if not self.base_url:
            raise ValueError("AUTO160_CATALOG_BASE_URL is required")
        if not self.api_key:
            raise ValueError("AUTO160_CATALOG_API_KEY is required")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "X-Api-Key": self.api_key,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="replace")
                if exc.code in {408, 429, 500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(self.retry_backoff_sec * attempt)
                    last_error = Auto160CatalogError(
                        f"HTTP {exc.code} {err_body[:200]}",
                        status_code=exc.code,
                        body=err_body,
                    )
                    continue
                raise Auto160CatalogError(
                    f"HTTP {exc.code} {err_body[:200]}",
                    status_code=exc.code,
                    body=err_body,
                ) from exc
            except urllib.error.URLError as exc:
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_sec * attempt)
                    last_error = Auto160CatalogError(str(exc))
                    continue
                raise Auto160CatalogError(str(exc)) from exc
        if last_error:
            raise last_error
        raise Auto160CatalogError("request failed")

    def match(
        self,
        candidates: Sequence[CatalogCandidate],
        *,
        enqueue_gaps: bool = True,
        source: str = "eu2",
        chunk_size: int = 200,
    ) -> list[MatchResult]:
        results: list[MatchResult] = []
        chunk: list[CatalogCandidate] = []
        for candidate in candidates:
            chunk.append(candidate)
            if len(chunk) >= chunk_size:
                results.extend(self._match_chunk(chunk, enqueue_gaps=enqueue_gaps, source=source))
                chunk = []
        if chunk:
            results.extend(self._match_chunk(chunk, enqueue_gaps=enqueue_gaps, source=source))
        return results

    def _match_chunk(
        self,
        chunk: Sequence[CatalogCandidate],
        *,
        enqueue_gaps: bool,
        source: str,
    ) -> list[MatchResult]:
        data = self._request(
            "POST",
            "/api/v1/internal/catalog/match",
            {
                "candidates": [row.to_payload() for row in chunk],
                "enqueue_gaps": enqueue_gaps,
                "source": source,
            },
        )
        out: list[MatchResult] = []
        for row in data.get("results") or []:
            out.append(
                MatchResult(
                    external_ref=row.get("external_ref"),
                    matched_catalog_item_id=row.get("matched_catalog_item_id"),
                    match_confidence=int(row.get("match_confidence") or 0),
                    reason=row.get("reason") or "not_found",
                    make=row.get("make") or "",
                    model=row.get("model") or "",
                    gap_id=row.get("gap_id"),
                )
            )
        return out

    def get_item(self, item_id: int) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/internal/catalog/items/{item_id}")

    def list_gaps(self, *, status: str = "open", source: str | None = "eu2", limit: int = 100) -> list[dict[str, Any]]:
        query = f"?status={status}&limit={limit}"
        if source:
            query += f"&source={source}"
        return self._request("GET", f"/api/v1/internal/catalog/gaps{query}") or []


def reconcile_after_parse(
    candidates: Iterable[CatalogCandidate],
    *,
    on_matched: Callable[[MatchResult], None] | None = None,
    on_not_found: Callable[[MatchResult], None] | None = None,
    client: Auto160CatalogClient | None = None,
    enqueue_gaps: bool = True,
) -> list[MatchResult]:
    """Call after eu2 parse succeeds. Does not block saving raw ads — run as a separate step.

    on_matched: persist catalog_item_id for the eu2 entity (external_ref).
    on_not_found: optional local logging; gaps are also queued on auto160 when enqueue_gaps=True.
    """
    api = client or Auto160CatalogClient()
    rows = list(candidates)
    if not rows:
        return []
    results = api.match(rows, enqueue_gaps=enqueue_gaps)
    for result in results:
        if result.matched_catalog_item_id is not None:
            if on_matched:
                on_matched(result)
        elif on_not_found:
            on_not_found(result)
    return results


if __name__ == "__main__":
    # Smoke: python auto160_catalog_client.py
    demo = [
        CatalogCandidate(external_ref="demo-1", make="BMW", model="3 серия", year=2015, engine_power_hp=136),
    ]
    print(json.dumps([asdict(r) for r in reconcile_after_parse(demo)], ensure_ascii=False, indent=2))
