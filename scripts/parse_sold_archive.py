#!/usr/bin/env python3
"""Parse Scandi Motors «Архив проданных.xlsx» into normalized JSON for the desk portal.

Usage:
    python scripts/parse_sold_archive.py "/path/Архив проданных.xlsx" out.json
    python scripts/parse_sold_archive.py in.xlsx out.json --push http://93.125.82.184 \
        --login admin_roman1067 --password '…'

The workbook is hand-kept: one sheet per car, sometimes several cars side by side.
We extract expense rows (item / BYN / USD / EUR / payer) and key figures
(Продано, Комиссия, Себестоимость, Прибыль), verify sums against the sheet's own
«Итог» row when present, and flag every car whose numbers cannot be verified.
The raw cell grid of each car block is always stored so nothing is lost.

Requires: pip install openpyxl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

SKIP_SHEETS = {"Общак. Архив", "Якуб."}  # cash pool / settlements, not single cars
CASH_SHEETS = {"Общак. Архив", "Якуб."}

CUR_TOKENS = {
    "руб": "BYN",
    "руб.": "BYN",
    "byn": "BYN",
        "$": "USD",
    "usd": "USD",
    "eur": "EUR",
    "евро": "EUR",
}

TOTAL_EXACT = {"итог", "итого", "итого в $", "итого в usd"}
END_PREFIX = ("себес", "продано", "прибыль", "остаток=", "комиссия")
FIGURE_KEYS = {
    "sold": re.compile(r"^продано", re.I),
    "commission": re.compile(r"^(комиссия|-\s*комиссия)", re.I),
    "cost": re.compile(r"^себес", re.I),
    "profit": re.compile(r"^прибыль", re.I),
    "rate": re.compile(r"^курс", re.I),
}

_LATIN_TO_CYR = str.maketrans({"A": "А", "M": "М", "O": "О", "K": "К", "E": "Е", "C": "С", "P": "Р", "T": "Т", "H": "Н", "X": "Х", "B": "В"})


PAYER_RX = re.compile(r"^[A-Za-zА-Яа-яЁё]{1,6}$")


def norm_payer(raw) -> str | None:
    """Short alphabetic token only (А, М, R, О, IHR, MIR, Котел). Anything else is a note."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or not PAYER_RX.match(text):
        return None
    if len(text) <= 2:
        up = text.upper()
        return "R" if up == "R" else up.translate(_LATIN_TO_CYR)
    return text


def is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def cell_str(v) -> str:
    return str(v).strip() if v is not None else ""


def jsonable(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, float):
        return round(v, 4)
    return v


def grid(ws, r0, r1, c0, c1):
    rows = []
    for r in range(r0, r1 + 1):
        row = [jsonable(ws.cell(row=r, column=c).value) for c in range(c0, c1 + 1)]
        if any(v is not None for v in row):
            rows.append({"r": r, "cells": row})
    return rows


def find_blocks(ws):
    """Return car blocks: dict(title, c0, c1 (expenses width), span_c1, r0, r1, header_row)."""
    max_c, max_r = ws.max_column, ws.max_row
    raw_blocks = []

    # 1) Explicit «Статья расходов…» headers (any row) — the reliable anchor.
    header_cells = []
    for row in ws.iter_rows():
        for cell in row:
            if cell_str(cell.value).lower().startswith("статья расходов"):
                header_cells.append((cell.row, cell.column))
    for hr, c in header_cells:
        title = cell_str(ws.cell(row=1, column=c).value) if hr <= 3 else ""
        if not title:
            for dr in range(1, 4):
                t = cell_str(ws.cell(row=hr - dr, column=c).value) if hr - dr >= 1 else ""
                if t and not t.lower().startswith(("итог", "себес", "продано", "прибыль", "комиссия", "остаток", "курс", "сумма", "дата")):
                    title = t
                    break
        raw_blocks.append({"title": title, "c0": c, "header_row": hr})

    # 2) Row-1 titles with $ / Руб headers on row 2 (the «Архив» sheet has no «Статья расходов»).
    if not any(hr <= 3 for hr, _ in header_cells):
        for c in range(1, max_c + 1):
            title = cell_str(ws.cell(row=1, column=c).value)
            if title:
                raw_blocks.append({"title": title, "c0": c, "header_row": 2})
    else:
        # titles in row 1 not covered by a header (rare) are ignored on purpose.
        pass
    # Archive sheet also has a stacked «Статья расходов» block (AM2) handled above only if present;
    # make sure side-by-side titles exist in addition when sheet is the multi-car archive.
    if ws.title == "Архив":
        have = {(b["c0"], b["header_row"]) for b in raw_blocks}
        for c in range(1, max_c + 1):
            title = cell_str(ws.cell(row=1, column=c).value)
            if title and (c, 2) not in have:
                raw_blocks.append({"title": title, "c0": c, "header_row": 2})

    raw_blocks.sort(key=lambda b: (b["c0"], b["header_row"]))
    blocks = []
    for b in raw_blocks:
        low = (b["title"] or "").lower()
        if low.startswith(("остаток", "расходы на", "дата", "сумма")):
            continue
        blocks.append(b)

    for b in blocks:
        same_col_next = [x["header_row"] for x in blocks if x["c0"] == b["c0"] and x["header_row"] > b["header_row"]]
        b["r1"] = (min(same_col_next) - 1) if same_col_next else max_r
        b["c1"] = min(b["c0"] + 4, max_c)
        right = [x["c0"] for x in blocks if x["c0"] > b["c0"] and x["header_row"] <= b["header_row"] + 2 and x["header_row"] >= b["header_row"] - 2]
        b["span_c1"] = (min(right) - 1) if right else max_c
        if not b["title"]:
            b["title"] = f"{ws.title} (блок {get_column_letter(b['c0'])}{b['header_row']})"
    return blocks


def header_columns(ws, block):
    """Detect item / currency / payer columns for the block."""
    hr = block["header_row"]
    c0, c1 = block["c0"], block["c1"]
    cur_cols: dict[int, str] = {}
    payer_col = None
    for r in (hr, hr + 1):
        for c in range(c0, c1 + 1):
            s = cell_str(ws.cell(row=r, column=c).value).lower().strip()
            if s in CUR_TOKENS:
                cur_cols.setdefault(c, CUR_TOKENS[s])
            elif s.startswith("кто платил") and payer_col is None:
                payer_col = c
    return cur_cols, payer_col


def collect_expenses(ws, block, cur_cols, payer_col):
    hr = block["header_row"]
    # first data row: skip currency sub-header if it sits on hr+1
    start = hr + 1
    sub = [cell_str(ws.cell(row=start, column=c).value).lower() for c in range(block["c0"], block["c1"] + 1)]
    if any(s in CUR_TOKENS for s in sub) and not cell_str(ws.cell(row=start, column=block["c0"]).value):
        start += 1
    expenses = []
    totals_row = None
    blanks = 0
    r = start
    max_r = block["r1"]
    c0 = block["c0"]
    while r <= max_r:
        label = cell_str(ws.cell(row=r, column=c0).value)
        low = label.lower()
        nums = {c: ws.cell(row=r, column=c).value for c in cur_cols if is_num(ws.cell(row=r, column=c).value)}
        # stop at next block header on stacked sheets
        if low.startswith("статья расходов") and r != hr:
            break
        if low in TOTAL_EXACT:
            totals_row = {cur_cols[c]: ws.cell(row=r, column=c).value for c in cur_cols if is_num(ws.cell(row=r, column=c).value)}
            break
        if low.startswith(END_PREFIX):
            break
        if not label and not nums:
            blanks += 1
            if blanks >= 3:
                break
            r += 1
            continue
        blanks = 0
        if low.startswith("итого расходов") or low.startswith("было на карте") or low.startswith("остаток"):
            r += 1
            continue
        payer_raw = ws.cell(row=r, column=payer_col).value if payer_col else None
        payer = norm_payer(payer_raw)
        note_parts = []
        if payer is None and cell_str(payer_raw):
            note_parts.append(cell_str(payer_raw))
        for c in range(c0 + 1, block["c1"] + 1):
            if c in cur_cols or c == payer_col:
                continue
            v = ws.cell(row=r, column=c).value
            if isinstance(v, str) and v.strip():
                note_parts.append(v.strip())
        if nums:
            for c, v in nums.items():
                expenses.append(
                    {
                        "row": r,
                        "item": label or "(без названия)",
                        "amount": round(float(v), 2),
                        "currency": cur_cols[c],
                        "payer": payer,
                        "note": "; ".join(note_parts) or None,
                    }
                )
        elif label:
            # text-only row (section like «Из них:»)
            pass
        r += 1
    return expenses, totals_row, r


def collect_figures(ws, block, r_from):
    figs = []
    for r in range(block["header_row"], block["r1"] + 1):
        for c in range(block["c0"], block["span_c1"] + 1):
            s = cell_str(ws.cell(row=r, column=c).value)
            if not s:
                continue
            for key, rx in FIGURE_KEYS.items():
                if rx.match(s):
                    vals = []
                    for k in range(1, 4):
                        v = ws.cell(row=r, column=c + k).value
                        if is_num(v):
                            vals.append(round(float(v), 2))
                    if vals:
                        figs.append({"key": key, "label": s, "values": vals, "cell": f"{get_column_letter(c)}{r}"})
                    break
    return figs


def sums_by_currency(expenses):
    out: dict[str, float] = {}
    for e in expenses:
        out[e["currency"]] = out.get(e["currency"], 0.0) + e["amount"]
    return {k: round(v, 2) for k, v in out.items()}


def pick(figs, key):
    for f in figs:
        if f["key"] == key:
            return f
    return None


def parse_workbook(path: Path):
    wb = openpyxl.load_workbook(path, data_only=True)
    cars = []
    cash_sheets = []
    for ws in wb.worksheets:
        if ws.title in CASH_SHEETS:
            cash_sheets.append(
                {
                    "sheet": ws.title,
                    "grid": grid(ws, 1, ws.max_row, 1, ws.max_column),
                }
            )
            continue
        blocks = find_blocks(ws)
        for idx, block in enumerate(blocks, start=1):
            cur_cols, payer_col = header_columns(ws, block)
            flags: list[str] = []
            if not cur_cols:
                flags.append("не найдены колонки валют — проверьте вручную")
            expenses, totals_row, end_row = collect_expenses(ws, block, cur_cols, payer_col) if cur_cols else ([], None, block["header_row"] + 1)
            figs = collect_figures(ws, block, end_row)
            sums = sums_by_currency(expenses)

            verified = False
            if totals_row:
                ex_purchase = sums_by_currency([e for e in expenses if not e["item"].lower().startswith("покупк")])

                def _match(candidate):
                    return all(abs(candidate.get(cur, 0.0) - float(tot)) <= 1.0 for cur, tot in totals_row.items())

                if _match(sums):
                    verified = True
                elif _match(ex_purchase):
                    verified = True
                    flags.append("«Итог» в листе считается без строки «Покупка» — суммы сошлись")
                else:
                    diffs = {
                        cur: {"parsed": sums.get(cur, 0.0), "parsed_ex_purchase": ex_purchase.get(cur, 0.0), "sheet_total": round(float(tot), 2)}
                        for cur, tot in totals_row.items()
                    }
                    flags.append(f"суммы расходов не совпали с «Итог»: {json.dumps(diffs, ensure_ascii=False)}")
            else:
                flags.append("в листе нет строки «Итог» — суммы расходов не проверены")
            if not expenses:
                flags.append("расходы не распознаны")
            if not pick(figs, "sold"):
                flags.append("цена продажи не найдена")

            payers = sorted({e["payer"] for e in expenses if e["payer"]})
            last_fig_row = max([int(re.sub(r"\D", "", f["cell"])) for f in figs] + [end_row])
            r_end = min(block["r1"], last_fig_row + 2)
            raw = grid(ws, block["header_row"] - 1 if block["header_row"] > 1 else 1, r_end, block["c0"], min(block["span_c1"], block["c0"] + 14))

            sold = pick(figs, "sold")
            cost = pick(figs, "cost")
            profit = pick(figs, "profit")
            commission = pick(figs, "commission")
            rate = pick(figs, "rate")
            cars.append(
                {
                    "source_key": f"xlsx:{ws.title}:{idx}",
                    "sheet": ws.title,
                    "block_index": idx,
                    "title": block["title"],
                    "expenses": expenses,
                    "sums": sums,
                    "sheet_totals": totals_row,
                    "figures": figs,
                    "sold_price": sold["values"][0] if sold else None,
                    "cost_price": cost["values"][0] if cost else None,
                    "profit": profit["values"][0] if profit else None,
                    "commission": commission["values"][0] if commission else None,
                    "fx_rate": rate["values"][0] if rate else None,
                    "payers": payers,
                    "verified": verified,
                    "needs_review": (not verified) or (not expenses) or (pick(figs, "sold") is None),
                    "flags": flags,
                    "raw_grid": raw,
                }
            )
    return {"cars": cars, "cash_sheets": cash_sheets}


def push(data, base, login, password):
    import urllib.request

    def call(url, body=None, token=None, method="POST"):
        req = urllib.request.Request(url, method=method)
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        payload = json.dumps(body).encode() if body is not None else None
        with urllib.request.urlopen(req, payload, timeout=120) as resp:
            return json.loads(resp.read().decode())

    tok = call(f"{base}/api/v1/auth/login", {"login": login, "password": password})
    token = tok.get("access_token")
    if not token:
        raise SystemExit(f"login failed: {tok}")
    res = call(f"{base}/api/v1/admin/sold-cars/import", data, token)
    print(json.dumps(res, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("out")
    ap.add_argument("--push")
    ap.add_argument("--login")
    ap.add_argument("--password")
    args = ap.parse_args()

    data = parse_workbook(Path(args.xlsx))
    Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    ok = sum(1 for c in data["cars"] if c["verified"])
    print(f"cars: {len(data['cars'])}, verified: {ok}, need review: {len(data['cars']) - ok}")
    for c in data["cars"]:
        mark = "OK " if c["verified"] else "?? "
        print(f"{mark}{c['sheet']:<20} #{c['block_index']} {c['title'][:42]:<42} exp={len(c['expenses']):>3} sums={c['sums']} sold={c['sold_price']} profit={c['profit']}")
        for f in c["flags"]:
            print(f"      - {f}")
    if args.push:
        push(data, args.push.rstrip("/"), args.login, args.password)


if __name__ == "__main__":
    sys.exit(main())
