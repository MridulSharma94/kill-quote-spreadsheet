"""Deterministic parsers for vendor formats with stable, machine-readable structure.

These parsers only read vendor-facing source files. They never import benchmark
or hidden ground-truth data.
"""
from __future__ import annotations
import re
from pathlib import Path
import pandas as pd


def parse_v1_xlsx(path: Path) -> list[dict]:
    """Read Shree Ganesh's quote table by header names, not row order."""
    frame = pd.read_excel(path, sheet_name="Commercial Offer", header=1)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    required = {"reference", "quoted rate", "unit"}
    if not required.issubset(set(frame.columns)):
        raise ValueError("V1 quote table headers changed; manual review required")
    rows = []
    for _, r in frame.iterrows():
        lid = str(r.get("reference", "")).strip().upper()
        if not re.fullmatch(r"L\d{2}", lid):
            continue
        try:
            price = float(r["quoted rate"])
        except (TypeError, ValueError):
            continue
        unit = str(r.get("unit", "INR / box")).upper().replace(" ", "")
        unit = "INR/BOX" if "INR/BOX" in unit else str(r.get("unit", "INR/BOX")).upper()
        remarks = "" if pd.isna(r.get("remarks")) else str(r.get("remarks"))
        desc = "" if pd.isna(r.get("product description")) else str(r.get("product description"))
        rows.append({"line_id": lid, "quoted_price": price, "unit": unit,
                     "currency": "INR", "confidence": 0.995,
                     "source_snippet": f"{lid} | {desc} | {price} {r.get('unit')} | {remarks}",
                     "spec_deviation": "", "assumptions": "Deterministic table parse; verify source row."})
    return rows


def parse_v2_pdf_text(text: str) -> list[dict]:
    """Parse explicit line IDs and USD/box amounts from the searchable PDF text."""
    rows = []
    pattern = re.compile(r"\b(L\d{2})\s+(.+?)\s+USD\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*box\b", re.I)
    for m in pattern.finditer(text):
        rows.append({"line_id": m.group(1).upper(), "quoted_price": float(m.group(3)),
                     "unit": "USD/BOX", "currency": "USD", "confidence": 0.995,
                     "source_snippet": m.group(0).strip(), "spec_deviation": "",
                     "assumptions": "Deterministic PDF text parse; quoted dimensions/spec disclosure checked separately."})
    return rows


def parse_v5_email(text: str, lines: pd.DataFrame, last_year: pd.DataFrame) -> tuple[list[dict], dict[str, str]]:
    """Apply only the explicit per-kg and same-as-last-year statements in V5's email.

    Die-cut and printed lines are held out because the email explicitly asks the
    buyer to confirm applicability. They are not represented as supplier no-bids.
    """
    m5 = re.search(r"INR\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*kg\s+for\s+5[- ]ply", text, re.I)
    m3 = re.search(r"INR\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*kg\s+for\s+3[- ]ply", text, re.I)
    if not (m5 and m3):
        raise ValueError("V5 per-kg rates not found in email; manual extraction required")
    last = last_year.set_index("line_id").iloc[:, 0].to_dict()
    rows, held = [], {}
    for r in lines.itertuples(index=False):
        lid = str(r.line_id)
        desc = f"{r.item_name} {r.spec}".lower()
        if "diecut" in str(r.style).lower() or "printed" in desc:
            held[lid] = "Vendor asks buyer to confirm whether per-kg rates include die-cut/printing conversion premiums."
            continue
        if int(r.ply) == 7:
            if lid not in last:
                held[lid] = "Vendor says same as last year, but no corresponding baseline price is available."
                continue
            rows.append({"line_id": lid, "quoted_price": float(last[lid]), "unit": "SAME_AS_LAST_YEAR",
                         "currency": "INR", "confidence": 0.85,
                         "source_snippet": f"{lid} | {r.item_name} | For 7-ply items, retain same prices as last year.",
                         "spec_deviation": "", "assumptions": "Contextual last-year reference explicitly authorized by vendor; not a new price."})
        else:
            rate = float(m5.group(1)) if int(r.ply) == 5 else float(m3.group(1))
            unit_label = f"{int(r.ply)}-ply"
            rows.append({"line_id": lid, "quoted_price": rate, "unit": "INR/KG",
                         "currency": "INR", "confidence": 0.97,
                         "source_snippet": f"{unit_label}: INR {rate:g}/kg; applied to {lid} ({r.item_name})",
                         "spec_deviation": "", "assumptions": "Rate applied by stated ply; freight amount remains unknown."})
    return rows, held
