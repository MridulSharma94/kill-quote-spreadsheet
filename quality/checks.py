"""Deterministic trust and award gates for extracted procurement quotes.

This module deliberately does not infer missing prices or specifications.
"""
from __future__ import annotations
import pandas as pd

EXPECTED_VENDOR_IDS = ("V1", "V2", "V3", "V4", "V5")


def extraction_completeness(lines: pd.DataFrame, raw: pd.DataFrame,
                            vendor_ids=EXPECTED_VENDOR_IDS) -> pd.DataFrame:
    """Return vendor-level coverage. A missing extraction is NOT proof of no quote."""
    expected = set(lines["line_id"].astype(str))
    rows = []
    for vendor in vendor_ids:
        part = raw[raw["vendor_id"].astype(str).eq(vendor)] if not raw.empty else raw
        extracted = set(part.loc[part.get("quoted", pd.Series(dtype=bool)).fillna(False).astype(bool), "line_id"].astype(str)) if not part.empty else set()
        extracted &= expected
        missing = sorted(expected - extracted)
        rows.append({
            "vendor_id": vendor,
            "expected_lines": len(expected),
            "extracted_quotes": len(extracted),
            "coverage_pct": round(100 * len(extracted) / len(expected), 1) if expected else 0.0,
            "unextracted_line_ids": ", ".join(missing),
            "interpretation": "Complete extraction" if not missing else "Extraction gap — inspect source; do not assume supplier did not quote",
        })
    return pd.DataFrame(rows)


def build_review_register(normalized: pd.DataFrame, raw: pd.DataFrame,
                          lines: pd.DataFrame) -> pd.DataFrame:
    """Add explicit trust blockers and extraction gaps to each vendor-line cell."""
    result = normalized.copy()
    raw_keys = set(zip(raw.get("vendor_id", []), raw.get("line_id", [])))
    result["review_blockers"] = ""
    result["evidence_present"] = [ (str(v), str(l)) in raw_keys and bool(
        raw.loc[(raw.vendor_id.astype(str) == str(v)) & (raw.line_id.astype(str) == str(l)), "quoted"].fillna(False).astype(bool).any()
    ) for v, l in zip(result.vendor_id, result.line_id)]

    for idx, row in result.iterrows():
        blockers = []
        state = str(row.get("quote_state", "quoted" if bool(row.get("quoted", False)) else "extraction_failed"))
        deviation = row.get("spec_deviation", "")
        if state == "extraction_failed":
            blockers.append("Extraction failed or no price was recovered — inspect original source; not a supplier no-bid")
        elif state == "needs_clarification":
            blockers.append("Supplier clarification required")
        elif state == "supplier_no_quote":
            blockers.append("Supplier source indicates no quote for this line")
        elif not bool(row.get("quoted", False)):
            blockers.append("No extracted quote — verify original source before classifying as supplier no-bid")
        if str(row.get("status", "")) == "needs_review":
            existing = row.get("reasons", "")
            if isinstance(existing, list): blockers.extend(str(x) for x in existing)
            elif pd.notna(existing) and str(existing).strip(): blockers.append(str(existing))
        if str(row.get("freight_treatment", "")) == "extra_unknown":
            blockers.append("Freight amount unknown")
        if pd.notna(deviation) and str(deviation).strip():
            blockers.append("Specification deviation unresolved")
        if not bool(row.get("evidence_present", False)) and bool(row.get("quoted", False)):
            blockers.append("Source evidence missing")
        result.at[idx, "review_blockers"] = " | ".join(dict.fromkeys(blockers))
    return result


def award_eligible_quotes(quotes: pd.DataFrame, eligible_vendors=None) -> pd.DataFrame:
    """Only return fully evidenced, accepted quotes with calculable landed cost.

    This is a gate, not an award recommendation. It excludes unknown freight,
    unresolved deviations, low-confidence/review rows and incomplete landed cost.
    """
    q = quotes.copy()
    if eligible_vendors is not None:
        q = q[q.vendor_id.isin(eligible_vendors)]
    required = ["status", "quoted", "net_inr_per_box", "landed_pre_gst_inr_per_box"]
    for col in required:
        if col not in q.columns:
            raise ValueError(f"Missing required award-gate column: {col}")
    mask = (
        q.status.astype(str).eq("accepted")
        & q.quoted.fillna(False).astype(bool)
        & pd.to_numeric(q.net_inr_per_box, errors="coerce").notna()
        & pd.to_numeric(q.landed_pre_gst_inr_per_box, errors="coerce").notna()
    )
    if "freight_treatment" in q.columns:
        mask &= ~q.freight_treatment.astype(str).eq("extra_unknown")
    if "spec_deviation" in q.columns:
        mask &= q.spec_deviation.fillna("").astype(str).str.strip().eq("")
    if "spec_validation" in q.columns:
        mask &= q.spec_validation.astype(str).eq("verified")
    if "quote_state" in q.columns:
        mask &= q.quote_state.astype(str).eq("quoted")
    if "confidence" in q.columns:
        mask &= pd.to_numeric(q.confidence, errors="coerce").fillna(0).ge(0.90)
    return q.loc[mask].copy()


def award_coverage(eligible: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    """Show which RFQ lines have at least one award-eligible quote."""
    counts = eligible.groupby("line_id").vendor_id.nunique() if not eligible.empty else pd.Series(dtype=int)
    out = lines[["line_id", "item_name", "qty"]].copy()
    out["eligible_vendor_count"] = out.line_id.map(counts).fillna(0).astype(int)
    out["awardable"] = out.eligible_vendor_count.gt(0)
    return out
