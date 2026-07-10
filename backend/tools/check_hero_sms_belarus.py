"""Verify HeroSMS Belarus (+375) SMS availability via live API."""

from __future__ import annotations

import json
import os
import sys

from curl_cffi import requests

HERO_BASE = "https://hero-sms.com/stubs/handler_api.php"


def hero(api_key: str, **params: str) -> str:
    params["api_key"] = api_key
    r = requests.get(HERO_BASE, params=params, timeout=30)
    return r.text.strip()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    api_key = os.environ.get("HERO_SMS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set HERO_SMS_API_KEY")

    print("=== Balance ===")
    print(hero(api_key, action="getBalance"))

    print("\n=== Countries list: Belarus ===")
    countries_raw = hero(api_key, action="getCountries")
    try:
        countries = json.loads(countries_raw)
        for cid, info in countries.items():
            if isinstance(info, dict) and info.get("eng") == "Belarus":
                print(f"  id={cid}: {json.dumps(info, ensure_ascii=False)}")
    except json.JSONDecodeError:
        print("  parse error:", countries_raw[:300])

    print("\n=== Numbers status for country=51 (Belarus) ===")
    status_raw = hero(api_key, action="getNumbersStatus", country=51)
    try:
        status = json.loads(status_raw)
        print(f"  services with stock: {len(status)}")
        for svc, qty in sorted(status.items(), key=lambda x: -int(x[1] if str(x[1]).isdigit() else 0)):
            if int(qty) if str(qty).isdigit() else 0:
                print(f"    {svc}: {qty} numbers")
        ot = status.get("ot")
        print(f"  'ot' (Any other): {ot}")
    except json.JSONDecodeError:
        print("  raw:", status_raw[:500])

    print("\n=== Prices: service=ot, country=51 ===")
    prices_raw = hero(api_key, action="getPrices", country=51, service="ot")
    print(" ", prices_raw)

    print("\n=== Try getNumber (only if balance > 0) ===")
    bal = hero(api_key, action="getBalance")
    if bal.startswith("ACCESS_BALANCE:"):
        amount = float(bal.split(":", 1)[1])
        if amount > 0:
            buy = hero(api_key, action="getNumber", service="ot", country=51)
            print(" ", buy)
            if buy.startswith("ACCESS_NUMBER:"):
                act_id = buy.split(":")[1]
                print("\n  Cancelling test number immediately...")
                print(" ", hero(api_key, action="setStatus", status=8, id=act_id))
        else:
            print("  skipped: balance is 0 (expected NO_BALANCE)")
            print(" ", hero(api_key, action="getNumber", service="ot", country=51))

    # cross-check OnlineSIM for comparison
    print("\n=== OnlineSIM Belarus (reference) ===")
    r = requests.get("https://onlinesim.io/api/getTariffs.php?country=375", timeout=30)
    if r.status_code == 200:
        data = r.json()
        c = (data.get("countries") or {}).get("_375")
        print("  country:", json.dumps(c, ensure_ascii=False) if c else "not found")
        sv = data.get("services") or {}
        in_stock = sum(1 for v in sv.values() if int(v.get("count") or 0) > 0)
        print(f"  services in stock: {in_stock}/{len(sv)}")


if __name__ == "__main__":
    main()
