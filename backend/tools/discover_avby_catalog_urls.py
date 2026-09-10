"""Discover AV.BY catalog model URLs via web-api (safe input for import_avby.py).

Does not write to the database. Only builds a URL list.

Examples:
  python tools/discover_avby_catalog_urls.py -o data/avby_urls_full.txt
  python tools/discover_avby_catalog_urls.py --brand bmw --brand toyota -o data/avby_urls_smoke.txt
  python tools/discover_avby_catalog_urls.py --level generations -o data/avby_urls_gens.txt
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from curl_cffi import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
LAUNCH_CWD = Path.cwd()

API_BASE = "https://web-api.av.by/offer-types/cars/modifications-catalog"
CATALOG_BASE = "https://av.by/catalog"


def _resolve_out(path_arg: str) -> Path:
    candidate = Path(path_arg)
    if candidate.is_absolute():
        return candidate
    launch_relative = LAUNCH_CWD / candidate
    if launch_relative.parent.exists():
        return launch_relative
    return ROOT_DIR / candidate


def _api_get(path: str, user_agent: str, retries: int = 3) -> Any:
    url = f"{API_BASE}{path}"
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                url,
                impersonate="chrome124",
                timeout=30,
                headers={
                    "User-Agent": user_agent,
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://av.by/",
                    "Origin": "https://av.by",
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.4 * attempt)
    raise RuntimeError(f"API GET failed {url}: {last_error}")


def discover_urls(
    *,
    level: str,
    brand_slugs: set[str] | None,
    only_with_modifications: bool,
    user_agent: str,
    sleep_s: float,
) -> tuple[list[str], dict[str, int]]:
    brands = _api_get("/brands", user_agent=user_agent)
    if not isinstance(brands, list):
        raise RuntimeError("Unexpected brands payload")

    selected = []
    for brand in brands:
        slug = (brand.get("slug") or "").strip().lower()
        if not slug:
            continue
        if brand_slugs and slug not in brand_slugs:
            continue
        selected.append(brand)

    urls: list[str] = []
    seen: set[str] = set()
    stats = {
        "brands": len(selected),
        "models": 0,
        "generations": 0,
        "generations_skipped_empty": 0,
        "urls": 0,
    }

    for brand in selected:
        brand_id = brand["id"]
        brand_slug = brand["slug"]
        models = _api_get(f"/brands/{brand_id}/models", user_agent=user_agent)
        if not isinstance(models, list):
            print(f"warn: bad models for {brand_slug}", file=sys.stderr)
            continue
        if sleep_s:
            time.sleep(sleep_s)

        for model in models:
            model_slug = (model.get("slug") or "").strip()
            model_id = model.get("id")
            if not model_slug or model_id is None:
                continue
            stats["models"] += 1

            if level == "models":
                url = f"{CATALOG_BASE}/{brand_slug}_{model_slug}"
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
                continue

            generations = _api_get(f"/models/{model_id}/generations", user_agent=user_agent)
            if not isinstance(generations, list):
                print(f"warn: bad generations for {brand_slug}_{model_slug}", file=sys.stderr)
                continue
            if sleep_s:
                time.sleep(sleep_s)

            for generation in generations:
                gen_slug = (generation.get("slug") or "").strip()
                if not gen_slug:
                    continue
                stats["generations"] += 1
                if only_with_modifications and not generation.get("hasModifications", True):
                    stats["generations_skipped_empty"] += 1
                    continue
                url = f"{CATALOG_BASE}/{brand_slug}_{model_slug}_{gen_slug}"
                if url not in seen:
                    seen.add(url)
                    urls.append(url)

    stats["urls"] = len(urls)
    return urls, stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover AV.BY catalog URLs (no DB writes). Feed into import_avby.py."
    )
    parser.add_argument(
        "-o",
        "--output",
        default="data/avby_urls_full.txt",
        help="Output file path (default: data/avby_urls_full.txt)",
    )
    parser.add_argument(
        "--level",
        choices=("models", "generations"),
        default="models",
        help="Emit model URLs (import expands gens) or generation URLs directly",
    )
    parser.add_argument(
        "--brand",
        action="append",
        dest="brands",
        help="Limit to brand slug(s), e.g. --brand bmw --brand toyota",
    )
    parser.add_argument(
        "--include-empty-generations",
        action="store_true",
        help="When --level generations, also include gens with hasModifications=false",
    )
    parser.add_argument("--user-agent", default="Mozilla/5.0")
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.15,
        help="Pause between API calls (seconds)",
    )
    args = parser.parse_args()

    brand_slugs = {b.strip().lower() for b in (args.brands or []) if b.strip()} or None
    urls, stats = discover_urls(
        level=args.level,
        brand_slugs=brand_slugs,
        only_with_modifications=not args.include_empty_generations,
        user_agent=args.user_agent,
        sleep_s=max(0.0, args.sleep),
    )

    out_path = _resolve_out(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "# Auto-generated AV.BY catalog URLs (discover_avby_catalog_urls.py)",
        f"# level={args.level} brands={stats['brands']} models={stats['models']} "
        f"generations={stats['generations']} skipped_empty={stats['generations_skipped_empty']}",
        "# Safe for: python tools/import_avby.py --urls-file ... --skip-existing",
        "",
    ]
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(header))
        for url in urls:
            fh.write(url + "\n")

    print(
        f"wrote {out_path} urls={stats['urls']} brands={stats['brands']} "
        f"models={stats['models']} generations={stats['generations']} "
        f"skipped_empty={stats['generations_skipped_empty']}"
    )


if __name__ == "__main__":
    main()
