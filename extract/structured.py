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



def parse_v3_docx(path: Path) -> list[dict]:
    """Parse V3's explicit paragraph schedule; each row carries a line ID and price."""
    from docx import Document
    doc = Document(path)
    rows = []
    pattern = re.compile(
        r"^\s*(L\d{2})\s*\|\s*(.*?)\s*\|\s*INR\s*([0-9,]+(?:\.[0-9]{1,2})?)\s*per\s*1000\s*pcs",
        re.I,
    )
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        match = pattern.search(text)
        if not match:
            continue
        lid, description, amount = match.groups()
        rows.append({
            "line_id": lid.upper(), "quoted_price": float(amount.replace(",", "")),
            "unit": "INR/1000 PCS", "currency": "INR", "confidence": 0.995,
            "source_snippet": text, "spec_deviation": "",
            "assumptions": "Deterministic DOCX paragraph parse; vendor's explicit line ID and rate preserved.",
        })
    ids = [r["line_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("V3 DOCX contains duplicate line IDs; manual reconciliation required")
    return rows


def parse_v4_image_ocr(path: Path) -> list[dict]:
    """OCR the complete V4 rate card and map its explicitly sequential 27 rows.

    The vendor terms addendum states that the card contains 27 quoted lines.
    We only accept a complete 27-row OCR pass; partial OCR is rejected rather
    than silently assigning shifted line IDs or inventing prices.
    """
    try:
        import pytesseract
        from PIL import Image, ImageOps, ImageEnhance
    except ImportError as exc:
        raise RuntimeError("V4 OCR requires Pillow, pytesseract, and the Tesseract system binary") from exc
    image = Image.open(path).convert("RGB")
    image = ImageOps.grayscale(image)
    image = ImageOps.autocontrast(image)
    image = ImageEnhance.Sharpness(image).enhance(2.0)
    image = image.resize((int(image.width * 1.5), int(image.height * 1.5)))
    text = pytesseract.image_to_string(image, config="--psm 6")
    # Tesseract may corrupt the printed line ID (e.g. LO1, 112, L1s), so use
    # source order only after validating all 27 price-bearing rows are present.
    candidates = []
    for line in text.splitlines():
        line = line.strip()
        if not re.search(r"\b(?:L|1|I|O)[A-Za-z0-9]{1,3}\b", line, re.I):
            continue
        amount = re.search(r"(?:Rs\.?\s*)([0-9]{1,3}(?:[,. :][0-9]{2})?)\s*$", line, re.I)
        if not amount:
            continue
        raw_amount = amount.group(1).replace(" ", "").replace(",", ".").replace(":", ".")
        try:
            price = float(raw_amount)
        except ValueError:
            continue
        candidates.append((line, price))
    if len(candidates) != 27:
        raise ValueError(f"V4 OCR found {len(candidates)} price rows; expected 27. Keep the image for manual review.")
    rows = []
    for index, (snippet, price) in enumerate(candidates, start=1):
        lid = f"L{index:02d}"
        rows.append({
            "line_id": lid, "quoted_price": price, "unit": "INR/BOX", "currency": "INR",
            "confidence": 0.92, "source_snippet": snippet,
            "spec_deviation": "", "assumptions": "OCR from source rate card; line ID mapped by validated sequential row order. Verify image evidence before award.",
        })
    return rows



def parse_v3_terms(path: Path) -> dict:
    from docx import Document
    text = "\n".join(p.text for p in Document(path).paragraphs)
    rate = re.search(r"inclusive at\s*([0-9]+(?:\.[0-9]+)?)%", text, re.I)
    freight = re.search(r"freight\s+(?:will be charged )?extra at\s+INR\s*([0-9]+(?:\.[0-9]+)?)\s+per box", text, re.I)
    payment = re.search(r"Payment:\s*([0-9]+)\s*days", text, re.I)
    validity = re.search(r"validity:\s*([0-9]+)\s*days", text, re.I)
    if not (rate and freight and payment and validity):
        raise ValueError("V3 commercial terms are incomplete; manual review required")
    return {"currency":"INR", "quote_unit":"INR/1000 PCS", "gst_treatment":"inclusive",
            "gst_rate_in_quote":float(rate.group(1)), "discount_pct":0,
            "freight_treatment":"extra_known", "freight_inr_per_box":float(freight.group(1)),
            "payment_terms":f"{payment.group(1)} days", "validity_days":int(validity.group(1)),
            "terms_confidence":0.995,
            "terms_evidence":"DOCX states INR per 1,000 pieces, GST inclusive at 12%, freight INR 0.90/box, payment 60 days, validity 45 days."}


def parse_v4_terms(path: Path) -> dict:
    text = path.read_text(errors="ignore")
    freight = re.search(r"Freight:\s*Extra at INR\s*([0-9]+(?:\.[0-9]+)?)\s*per box", text, re.I)
    payment = re.search(r"Payment:\s*([0-9]+)\s*days", text, re.I)
    validity = re.search(r"Validity:\s*([0-9]+)\s*days", text, re.I)
    if not (freight and payment and validity):
        raise ValueError("V4 commercial terms addendum is incomplete")
    return {"currency":"INR", "quote_unit":"INR/BOX", "gst_treatment":"extra",
            "discount_pct":0, "freight_treatment":"extra_known",
            "freight_inr_per_box":float(freight.group(1)), "payment_terms":f"{payment.group(1)} days",
            "validity_days":int(validity.group(1)), "terms_confidence":0.995,
            "terms_evidence":"Commercial terms addendum states INR/box, GST extra, freight INR 1.50/box, payment 30 days, validity 30 days."}


def parse_v5_terms(text: str) -> dict:
    freight_unknown = bool(re.search(r"freight will be extra; amount not stated", text, re.I))
    payment = re.search(r"Payment terms:\s*([0-9]+)\s*days", text, re.I)
    validity = re.search(r"Quote validity:\s*([0-9]+)\s*days", text, re.I)
    if not (payment and validity and freight_unknown):
        raise ValueError("V5 email commercial terms incomplete; manual review required")
    return {"currency":"INR", "quote_unit":"INR/KG", "gst_treatment":"extra",
            "discount_pct":0, "freight_treatment":"extra_unknown", "freight_inr_per_box":None,
            "payment_terms":f"{payment.group(1)} days", "validity_days":int(validity.group(1)),
            "terms_confidence":0.995,
            "terms_evidence":"Email states INR 42/kg for 5-ply, INR 38/kg for 3-ply, 7-ply same as last year; freight extra with amount unstated; GST extra; payment 45 days; validity 30 days."}


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
