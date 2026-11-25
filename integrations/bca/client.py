"""HTTP client for the public BCA Europe search API.

Anonymous search is POST /buyer/facetedsearch/GetViewModel after a cookie
from GET /search. Cloudflare rejects many datacenter addresses; set
HTTPS_PROXY or HTTP_PROXY when that happens.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

from integrations.bca.normalize import BASE

SEARCH_PATH = "/search"
API_PATH = "/buyer/facetedsearch/GetViewModel"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def proxy_url() -> str:
    for name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def _opener():
    handlers = [HTTPCookieProcessor(CookieJar())]
    proxy = proxy_url()
    if proxy:
        handlers.append(ProxyHandler({"http": proxy, "https": proxy}))
    return build_opener(*handlers)


@dataclass
class DownloadResult:
    http_status: int | None
    content_type: str
    body: bytes
    error: str


class BcaClient:
    def __init__(self) -> None:
        self._opener = _opener()

    def _read(self, request: Request, *, limit: int | None = None) -> tuple[int, str, bytes]:
        try:
            with self._opener.open(request, timeout=45) as response:
                body = response.read() if limit is None else response.read(limit)
                content_type = response.headers.get("Content-Type", "")
                return int(response.status), content_type, body
        except HTTPError as exc:
            body = exc.read() if limit is None else exc.read(limit or 0)
            content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
            return int(exc.code), content_type, body

    def fetch_sale_page(self, sale_id: str, page: int) -> dict[str, Any]:
        query = f"q=&page={page}&bq={quote('saleid_exact:' + sale_id, safe=':')}"
        search_url = f"{BASE}{SEARCH_PATH}?{query}"
        status, _, body = self._read(
            Request(search_url, headers={"User-Agent": UA, "Accept": "text/html"})
        )
        if status >= 400:
            raise RuntimeError(f"BCA search HTTP {status}")
        status, content_type, body = self._read(
            Request(
                f"{BASE}{API_PATH}?{query}",
                data=b"{}",
                method="POST",
                headers={
                    "User-Agent": UA,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Origin": BASE,
                    "Referer": search_url,
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
        )
        if status >= 400 or "json" not in content_type.lower():
            raise RuntimeError(f"BCA search API HTTP {status}")
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("BCA search API returned a non-object")
        return payload

    def fetch_sale(self, sale_id: str, *, max_pages: int = 20) -> tuple[list[dict[str, Any]], bool]:
        pages: list[dict[str, Any]] = []
        can_view_pricing = False
        for page in range(1, max_pages + 1):
            payload = self.fetch_sale_page(sale_id, page)
            can_view_pricing = bool(payload.get("CanViewPricing"))
            rows = payload.get("VehicleResults") or []
            if not isinstance(rows, list):
                raise RuntimeError("VehicleResults is not a list")
            pages.append(
                {
                    "page": page,
                    "total": payload.get("TotalVehicles"),
                    "can_view_pricing": can_view_pricing,
                    "anonymous": payload.get("IsUserAnonymous"),
                    "lots": rows,
                }
            )
            if len(rows) < 50:
                break
        return pages, can_view_pricing

    def download(self, url: str) -> DownloadResult:
        try:
            status, content_type, body = self._read(
                Request(
                    url,
                    headers={
                        "User-Agent": UA,
                        "Accept": "application/pdf,text/html,*/*",
                        "Referer": BASE + "/",
                    },
                )
            )
        except URLError as exc:
            return DownloadResult(None, "", b"", f"network error: {exc.reason}")
        if status >= 400:
            return DownloadResult(status, content_type, body[:200], f"HTTP {status}")
        return DownloadResult(status, content_type, body, "")
