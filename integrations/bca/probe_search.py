"""One-page probe of the public BCA Europe search API.

The catalog is not in the homepage HTML. Anonymous clients POST
``/buyer/facetedsearch/GetViewModel`` and get JSON. Prices stay empty
until a buyer session exists (``CanViewPricing`` is false).

Cloudflare blocks many datacenter IPs. From a residential network the
call often works directly. Otherwise set ``HTTPS_PROXY`` or ``HTTP_PROXY``.

Usage:
    python integrations/bca/probe_search.py
    python integrations/bca/probe_search.py --page 1 --out /tmp/bca-sample.json
    HTTPS_PROXY=http://user:pass@host:port python integrations/bca/probe_search.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from typing import Any

BASE = "https://ee.bca-europe.com"
SEARCH_PATH = "/search"
API_PATH = "/buyer/facetedsearch/GetViewModel"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _proxy_url() -> str:
    for name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def _opener() -> urllib.request.OpenerDirector:
    handlers: list[urllib.request.BaseHandler] = [
        urllib.request.HTTPCookieProcessor(CookieJar())
    ]
    proxy = _proxy_url()
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def _read(opener: urllib.request.OpenerDirector, request: urllib.request.Request) -> tuple[int, str]:
    try:
        with opener.open(request, timeout=40) as response:
            body = response.read().decode("utf-8", errors="replace")
            return int(response.status), body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), body


def _blocked(status: int, body: str) -> bool:
    head = body[:4000].lower()
    return status in {403, 429, 503} and (
        "attention required" in head
        or "just a moment" in head
        or "cloudflare" in head
        or "cf-browser-verification" in head
    )


def _search_query(*, page: int, bq: str) -> str:
    parts = ["q=", f"page={page}"]
    if bq:
        parts.append("bq=" + urllib.parse.quote(bq, safe=":"))
    return "&".join(parts)


def fetch_page(*, page: int, bq: str) -> dict[str, Any]:
    opener = _opener()
    query = _search_query(page=page, bq=bq)
    search_url = f"{BASE}{SEARCH_PATH}?{query}"
    status, body = _read(
        opener,
        urllib.request.Request(
            search_url,
            headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"},
        ),
    )
    if _blocked(status, body):
        raise SystemExit(
            f"BCA blocked the session cookie request (HTTP {status}). "
            "Retry from the home network or set HTTPS_PROXY."
        )
    if status >= 400:
        raise SystemExit(f"Search page HTTP {status}: {body[:240]}")

    api_url = f"{BASE}{API_PATH}?{query}"
    status, body = _read(
        opener,
        urllib.request.Request(
            api_url,
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
        ),
    )
    if _blocked(status, body):
        raise SystemExit(
            f"BCA blocked the search API (HTTP {status}). "
            "Retry from the home network or set HTTPS_PROXY."
        )
    if status >= 400:
        raise SystemExit(f"Search API HTTP {status}: {body[:240]}")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Search API did not return JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Search API returned a non-object JSON payload")
    return payload


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _image_url(value: Any) -> str:
    text = _text(value)
    if text.startswith("//"):
        return "https:" + text
    return text


def normalize(row: dict[str, Any]) -> dict[str, Any]:
    lot_id = _text(row.get("LotId"))
    vehicle_id = _text(row.get("VehicleId"))
    lot_url = ""
    if lot_id and vehicle_id:
        lot_url = f"{BASE}/Lot?id={lot_id}&ItemId={vehicle_id}"
    return {
        "lot_id": lot_id,
        "vehicle_id": vehicle_id,
        "lot_url": lot_url,
        "headline": _text(row.get("VehicleInfoHeadline")),
        "make": _text(row.get("Make")),
        "model": _text(row.get("Model")),
        "vin": _text(row.get("VIN")),
        "mileage_km": row.get("Mileage"),
        "registration": _text(row.get("RegistrationNumber")),
        "sale_location": _text(row.get("SaleLocation")),
        "sale_information": _text(row.get("SaleInformation")),
        "image_url": _image_url(row.get("ImageUrl")),
        "bid_now": _text(row.get("BidNow")),
        "buy_now": _text(row.get("BuyNow")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch one page of public BCA Europe lots")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument(
        "--bq",
        default="",
        help="Optional facet query, e.g. suppresssaleinformation_exact:true for EuroShop",
    )
    parser.add_argument("--out", default="", help="Write the JSON sample to this path")
    args = parser.parse_args()
    if args.page < 1:
        raise SystemExit("--page must be >= 1")

    payload = fetch_page(page=args.page, bq=args.bq)
    rows = payload.get("VehicleResults") or []
    if not isinstance(rows, list):
        raise SystemExit("VehicleResults is not a list")
    lots = [normalize(row) for row in rows if isinstance(row, dict)]
    sample = {
        "source": "bca",
        "page": args.page,
        "bq": args.bq,
        "total": payload.get("TotalVehicles"),
        "can_view_pricing": payload.get("CanViewPricing"),
        "anonymous": payload.get("IsUserAnonymous"),
        "culture": payload.get("CurrentCulture"),
        "count": len(lots),
        "lots": lots,
    }
    text = json.dumps(sample, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")
    summary = {
        "total": sample["total"],
        "count": sample["count"],
        "can_view_pricing": sample["can_view_pricing"],
        "anonymous": sample["anonymous"],
        "culture": sample["culture"],
        "first": lots[0] if lots else None,
        "out": args.out or None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
