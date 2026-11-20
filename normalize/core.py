"""Deterministic commercial normalization. No LLM calls in this module."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Iterable
import math
import pandas as pd

VALID_UNITS = {"INR/BOX", "USD/BOX", "INR/1000 PCS", "INR/KG"}

@dataclass
class VendorTerms:
    vendor_id: str
    currency: str = "INR"
    quote_unit: str = "INR/BOX"
    gst_treatment: str = "extra"       # extra | inclusive | unknown
    gst_rate_in_quote: Optional[float] = None
    discount_pct: float = 0.0
    freight_treatment: str = "extra_unknown"  # included | extra_known | extra_unknown
    freight_inr_per_box: Optional[float] = None
    moq_pcs: Optional[int] = None
    payment_terms: Optional[str] = None
    validity_days: Optional[int] = None

@dataclass
class Quote:
    vendor_id: str
    line_id: str
    quoted_price: Optional[float]
    unit: Optional[str]
    currency: Optional[str]
    confidence: float = 0.0
    source_file: str = ""
    source_snippet: str = ""
    spec_deviation: str = ""
    assumptions: str = ""
    quoted: bool = True

def _number(x, label):
    try:
        value=float(x)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be numeric")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be a finite non-negative number")
    return value

def normalize_quote(quote: Quote, line: pd.Series, terms: VendorTerms, fx_inr_per_usd: float):
    """Return comparable ex-GST, ex-freight INR/box plus explicit statuses."""
    if not quote.quoted or quote.quoted_price is None:
        return {"vendor_id":quote.vendor_id,"line_id":quote.line_id,"quoted":False,
                "net_inr_per_box":None,"freight_inr_per_box":None,"landed_pre_gst_inr_per_box":None,
                "status":"no_quote","reasons":["No quote received; missing is not zero."]}
    price=_number(quote.quoted_price,"quoted_price")
    unit=(quote.unit or terms.quote_unit).upper().replace("₹","INR").replace("RS.","INR").strip()
    currency=(quote.currency or terms.currency).upper()
    weight=_number(line["weight_kg_per_box"],"weight_kg_per_box")
    reasons=[]
    if unit in ("INR/BOX","INR PER BOX","PER BOX"):
        base=price
    elif unit in ("USD/BOX","USD PER BOX"):
        base=price*_number(fx_inr_per_usd,"fx_inr_per_usd")
    elif unit in ("INR/1000 PCS","INR PER 1000 PCS","PER 1000 PCS"):
        base=price/1000.0
    elif unit in ("INR/KG","INR PER KG","PER KG"):
        base=price*weight
    elif unit in ("SAME_AS_LAST_YEAR", "INR/BOX (LAST YEAR)"):
        # Extractor may use this only when vendor explicitly references last year's rate.
        base=price
    else:
        return {"vendor_id":quote.vendor_id,"line_id":quote.line_id,"quoted":True,
                "net_inr_per_box":None,"freight_inr_per_box":None,"landed_pre_gst_inr_per_box":None,
                "status":"needs_review","reasons":[f"Unsupported or ambiguous unit: {unit}"]}
    if currency=="USD" and unit not in ("USD/BOX","USD PER BOX"):
        return {"vendor_id":quote.vendor_id,"line_id":quote.line_id,"quoted":True,
                "net_inr_per_box":None,"freight_inr_per_box":None,"landed_pre_gst_inr_per_box":None,
                "status":"needs_review","reasons":["Currency/unit combination requires review."]}
    if currency not in ("INR","USD"):
        return {"vendor_id":quote.vendor_id,"line_id":quote.line_id,"quoted":True,
                "net_inr_per_box":None,"freight_inr_per_box":None,"landed_pre_gst_inr_per_box":None,
                "status":"needs_review","reasons":[f"Unsupported currency: {currency}"]}
    if terms.discount_pct < 0 or terms.discount_pct > 100:
        raise ValueError("discount_pct must be between 0 and 100")
    base_after_discount=base*(1-terms.discount_pct/100)
    # Convert GST-inclusive vendor quote back to ex-GST using the rate that was in force
    # in the quote. Never silently substitute the buyer's current tax scenario.
    if terms.gst_treatment=="inclusive":
        if terms.gst_rate_in_quote is None:
            reasons.append("GST-inclusive quote but quote-period GST rate is unknown.")
            net=None
        else:
            net=base_after_discount/(1+terms.gst_rate_in_quote)
    elif terms.gst_treatment=="extra":
        net=base_after_discount
    else:
        reasons.append("GST treatment is unknown.")
        net=None
    freight=0.0 if terms.freight_treatment=="included" else terms.freight_inr_per_box
    if terms.freight_treatment=="extra_unknown" or (terms.freight_treatment=="extra_known" and freight is None):
        reasons.append("Freight is extra but amount is not known; landed cost cannot be ranked.")
    if terms.moq_pcs and int(line["qty"]) < terms.moq_pcs:
        reasons.append(f"Line quantity {int(line['qty'])} is below MOQ {terms.moq_pcs}.")
    if quote.spec_deviation:
        reasons.append("Specification deviation: "+quote.spec_deviation)
    if quote.confidence < 0.90:
        reasons.append(f"Extraction confidence {quote.confidence:.0%} is below 90%.")
    if net is None:
        status="needs_review"
    elif quote.spec_deviation or quote.confidence < .90 or reasons:
        status="needs_review"
    else:
        status="accepted"
    landed=(net+freight) if net is not None and freight is not None else None
    return {"vendor_id":quote.vendor_id,"line_id":quote.line_id,"quoted":True,
            "quoted_price_as_stated":price,"quoted_unit":unit,"currency":currency,
            "net_inr_per_box":round(net,4) if net is not None else None,
            "freight_inr_per_box":round(freight,4) if freight is not None else None,
            "landed_pre_gst_inr_per_box":round(landed,4) if landed is not None else None,
            "status":status,"confidence":quote.confidence,"spec_deviation":quote.spec_deviation,
            "source_file":quote.source_file,"source_snippet":quote.source_snippet,
            "assumptions":quote.assumptions,"reasons":reasons}

def normalize_all(lines: pd.DataFrame, extracted_quotes: Iterable[Quote],
                  vendor_terms: dict[str,VendorTerms], fx_inr_per_usd: float=88.0):
    """Produce a complete vendor x line matrix, including explicit no_quote cells."""
    line_map={r.line_id:r for r in lines.itertuples(index=False)}
    line_series={str(r["line_id"]):r for _,r in lines.iterrows()}
    quote_map={}
    for q in extracted_quotes:
        key=(q.vendor_id,q.line_id)
        if key in quote_map: raise ValueError(f"Duplicate extracted quote: {key}")
        quote_map[key]=q
    vendors=sorted(vendor_terms)
    rows=[]
    for vendor_id in vendors:
        terms=vendor_terms[vendor_id]
        for line_id,line in line_series.items():
            q=quote_map.get((vendor_id,line_id), Quote(vendor_id,line_id,None,None,None,quoted=False))
            rows.append(normalize_quote(q,line,terms,fx_inr_per_usd))
    return pd.DataFrame(rows)

def landed_cost_including_gst(net_inr_per_box, freight_inr_per_box, gst_rate):
    """Scenario calculator; tax base treatment is an explicit simplifying assumption."""
    if net_inr_per_box is None or freight_inr_per_box is None:
        return None
    if not 0 <= gst_rate <= .28: raise ValueError("GST rate must be between 0 and 28%")
    return (net_inr_per_box+freight_inr_per_box)*(1+gst_rate)
