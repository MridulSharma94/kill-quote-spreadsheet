"""Deterministic comparison of disclosed vendor specs with RFQ requirements."""
from __future__ import annotations
import re
import pandas as pd

_DIM = re.compile(r"(?<![A-Za-z0-9])([A-Za-z0-9]{2,4})\s*[x×X]\s*([A-Za-z0-9]{2,4})\s*[x×X]\s*([A-Za-z0-9]{1,4})(?![A-Za-z0-9])")
_NUMERIC = re.compile(r"^\d{1,4}$")
_PLY = re.compile(r"\b(3|5|7)\s*[- ]?ply\b", re.I)
_BF = re.compile(r"\bBF\s*[-:]?\s*(\d{1,2})\b", re.I)


def _expected(row):
    return {
        "dimensions": (int(row.length_mm), int(row.width_mm), int(row.height_mm)),
        "ply": int(row.ply),
        "bf": int(re.search(r"BF\s*(\d+)", str(row.spec), re.I).group(1)) if re.search(r"BF\s*(\d+)", str(row.spec), re.I) else None,
    }


def validate_quote_specs(normalized: pd.DataFrame, raw: pd.DataFrame,
                         lines: pd.DataFrame) -> pd.DataFrame:
    """Add spec_validation and gate unverified/mismatched quotes for review.

    A mismatch is reported only when the vendor source explicitly discloses a
    conflicting value. Missing disclosure is labelled unverified, never a
    confirmed deviation.
    """
    out = normalized.copy()
    raw_lookup = {(str(r.vendor_id), str(r.line_id)): r for r in raw.itertuples(index=False)}
    line_lookup = {str(r.line_id): r for r in lines.itertuples(index=False)}
    validations, deviations, reasons_out = [], [], []
    for _, q in out.iterrows():
        if not bool(q.get("quoted", False)):
            validations.append("not_applicable"); deviations.append(q.get("spec_deviation", "")); reasons_out.append(q.get("reasons", [])); continue
        source = raw_lookup.get((str(q.vendor_id), str(q.line_id)))
        snippet = str(getattr(source, "source_snippet", "") or "") if source else ""
        existing_dev = str(q.get("spec_deviation", "") or "").strip()
        expected = _expected(line_lookup[str(q.line_id)])
        mismatches, missing = [], []
        dims = _DIM.search(snippet)
        if dims:
            tokens = dims.groups()
            # OCR-confusable letters (e.g. "g00x600x600") are not numeric
            # evidence. Never turn a likely OCR substitution into a supplier mismatch.
            if not all(_NUMERIC.fullmatch(token) for token in tokens):
                missing.append("dimensions (OCR-ambiguous; verify source image)")
            else:
                observed = tuple(int(x) for x in tokens)
                if observed != expected["dimensions"]:
                    mismatches.append(f"Dimensions {observed} differ from RFQ {expected['dimensions']}")
        else:
            missing.append("dimensions")
        ply = _PLY.search(snippet)
        if ply:
            if int(ply.group(1)) != expected["ply"]:
                mismatches.append(f"{ply.group(1)}-ply offered; RFQ requires {expected['ply']}-ply")
        else:
            missing.append("ply")
        bf = _BF.search(snippet)
        if expected["bf"] is not None:
            if bf:
                if int(bf.group(1)) != expected["bf"]:
                    mismatches.append(f"BF {bf.group(1)} offered; RFQ requires BF {expected['bf']}")
            else:
                missing.append("burst factor")
        if existing_dev:
            mismatches.append(existing_dev)
        blockers = q.get("reasons", [])
        if not isinstance(blockers, list):
            blockers = [str(blockers)] if str(blockers).strip() else []
        if mismatches:
            validation = "mismatch"
            deviation = "; ".join(dict.fromkeys(mismatches))
            blockers.append("Specification mismatch: " + deviation)
            out.at[q.name, "status"] = "needs_review"
        elif missing:
            validation = "unverified"
            deviation = ""
            blockers.append("Vendor source does not disclose: " + ", ".join(missing))
            out.at[q.name, "status"] = "needs_review"
        else:
            validation = "verified"
            deviation = ""
        validations.append(validation); deviations.append(deviation); reasons_out.append(blockers)
    out["spec_validation"] = validations
    out["spec_deviation"] = deviations
    out["reasons"] = reasons_out
    return out
