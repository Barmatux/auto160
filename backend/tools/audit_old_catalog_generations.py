#!/usr/bin/env python3
"""List catalog generations whose production ended before a cutoff year."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request

SITE = "https://auto160.by"
CONFIG_RE = re.compile(r"data-vehicle-hierarchy-config='({.*?})'", re.DOTALL)
YEARS_RE = re.compile(r"Годы выпуска:\s*(\d{4})\s*[–-]\s*(\d{4})")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "auto160-catalog-audit/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_generation_map(html: str) -> dict[str, dict[str, list[str]]]:
    match = CONFIG_RE.search(html)
    if not match:
        raise RuntimeError("generationMap not found on page")
    config = json.loads(match.group(1))
    return config.get("generationMap") or {}


def fetch_generation_years(site: str, *, make: str, model: str, generation: str) -> tuple[int | None, int | None]:
    params = urllib.parse.urlencode({"make": make, "model": model, "generation": generation})
    html = fetch(f"{site}/catalog/modifications?{params}")
    match = YEARS_RE.search(html)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def format_years(year_from: int | None, year_to: int | None) -> str:
    if year_from and year_to:
        return f"{year_from}–{year_to}"
    if year_from:
        return f"{year_from}–?"
    if year_to:
        return f"?–{year_to}"
    return "?"


def is_old_generation(year_from: int | None, year_to: int | None, *, cutoff_year: int) -> bool:
    if year_to is not None:
        return year_to < cutoff_year
    if year_from is not None:
        return year_from < cutoff_year
    return False


def collect_generations(site: str) -> list[dict]:
    catalog_html = fetch(f"{site}/catalog")
    generation_map = parse_generation_map(catalog_html)
    rows: list[dict] = []
    for make, models in sorted(generation_map.items()):
        for model, generations in sorted(models.items()):
            for generation in generations:
                year_from, year_to = fetch_generation_years(site, make=make, model=model, generation=generation)
                rows.append(
                    {
                        "make": make,
                        "model": model,
                        "generation": generation,
                        "year_from": year_from,
                        "year_to": year_to,
                    }
                )
    return rows


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Audit old catalog generations on live site")
    parser.add_argument(
        "--cutoff-year",
        type=int,
        default=2010,
        help="Treat generations with year_to before this year as old (default: 2010)",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--site", default=SITE)
    args = parser.parse_args()

    all_generations = collect_generations(args.site)
    old = [
        row
        for row in all_generations
        if is_old_generation(row["year_from"], row["year_to"], cutoff_year=args.cutoff_year)
    ]
    unknown = [row for row in all_generations if row["year_from"] is None and row["year_to"] is None]
    old.sort(key=lambda row: (row["make"], row["model"], row.get("year_from") or 0, row["generation"]))

    if args.json:
        print(
            json.dumps(
                {
                    "cutoff_year": args.cutoff_year,
                    "old_generations": old,
                    "unknown_years_count": len(unknown),
                    "total_generations": len(all_generations),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print(f"Всего поколений в каталоге: {len(all_generations)}")
    print(f"Критерий «старое поколение»: выпуск завершился до {args.cutoff_year} года")
    print(f"Найдено старых поколений: {len(old)}")
    if unknown:
        print(f"Без данных о годах: {len(unknown)}")
    print()
    for row in old:
        years = format_years(row["year_from"], row["year_to"])
        print(f"- {row['make']} {row['model']} · {row['generation']} ({years})")


if __name__ == "__main__":
    main()
