"""Connect raw LLM extraction to deterministic normalization."""
from pathlib import Path
import json
import pandas as pd
from normalize.core import Quote, VendorTerms, normalize_all
from quality.specs import validate_quote_specs

def _float_or_none(x):
    try:
        if x is None or pd.isna(x): return None
        return float(x)
    except (TypeError,ValueError):
        return None

def build_vendor_terms(raw_terms):
    result={}
    for vid,t in raw_terms.items():
        gst=t.get("gst_treatment","unknown")
        gst_rate=_float_or_none(t.get("gst_rate_in_quote"))
        freight=t.get("freight_treatment","extra_unknown")
        freight_amount=_float_or_none(t.get("freight_inr_per_box"))
        # Normalize terms vocabulary from the model to the engine's controlled values.
        if gst not in ("extra","inclusive"): gst="unknown"
        if freight=="included":
            freight="included"; freight_amount=0.0
        elif freight in ("extra_known","extra (stated)") and freight_amount is not None:
            freight="extra_known"
        else:
            freight="extra_unknown"
        result[vid]=VendorTerms(
            vendor_id=vid,
            currency=t.get("currency","INR"),
            quote_unit=t.get("quote_unit","INR/BOX"),
            gst_treatment=gst,
            gst_rate_in_quote=gst_rate,
            discount_pct=float(t.get("discount_pct") or 0),
            freight_treatment=freight,
            freight_inr_per_box=freight_amount,
            moq_pcs=int(t["moq_pcs"]) if t.get("moq_pcs") not in (None,"") else None,
            payment_terms=t.get("payment_terms"),
            validity_days=int(t["validity_days"]) if t.get("validity_days") not in (None,"") else None
        )
    return result

def raw_frame_to_quotes(raw_df):
    quotes=[]
    for _,r in raw_df.iterrows():
        if not bool(r.get("quoted",False)): continue
        price=_float_or_none(r.get("quoted_price_as_stated"))
        unit=str(r.get("quoted_unit") or "").upper()
        if price is None: continue
        quotes.append(Quote(
            vendor_id=str(r.vendor_id), line_id=str(r.line_id),
            quoted_price=price, unit=unit,
            currency=str(r.get("currency") or "INR"),
            confidence=float(r.get("confidence") or 0),
            source_file=str(r.get("source_file") or ""),
            source_snippet=str(r.get("source_snippet") or ""),
            spec_deviation=str(r.get("spec_deviation") or ""),
            assumptions=str(r.get("assumptions") or "")
        ))
    return quotes

def run_full_pipeline(lines,last_year,vendor_dir,fx_inr_per_usd=88.0):
    from extract.pipeline import extract_vendor_files
    raw,raw_terms,assumptions,evidence=extract_vendor_files(
        lines,last_year,vendor_dir,fx_inr_per_usd,0.05
    )
    terms=build_vendor_terms(raw_terms)
    # Ensure every expected vendor exists even if extraction failed; missing terms are review-only.
    for vid in ["V1","V2","V3","V4","V5"]:
        terms.setdefault(vid,VendorTerms(
            vendor_id=vid,gst_treatment="unknown",freight_treatment="extra_unknown"
        ))
    quotes=raw_frame_to_quotes(raw)
    normalized=normalize_all(lines,quotes,terms,fx_inr_per_usd)
    # Preserve source-level clarification notes separately from supplier no-bids.
    note_map={(str(r.vendor_id),str(r.line_id)):str(r.get("extraction_note", "") or "")
              for _,r in raw.iterrows()}
    normalized["extraction_note"]=[note_map.get((str(v),str(l)), "")
                                   for v,l in zip(normalized.vendor_id,normalized.line_id)]
    state_map={(str(r.vendor_id),str(r.line_id)):str(getattr(r,"quote_state","quoted"))
               for r in raw.itertuples(index=False)}
    normalized["quote_state"]=[state_map.get((str(v),str(l)), "extraction_failed")
                               for v,l in zip(normalized.vendor_id,normalized.line_id)]
    for idx,row in normalized.iterrows():
        note=str(row.get("extraction_note", "") or "")
        if note and not bool(row.get("quoted", False)) and "No extracted quote" not in note:
            normalized.at[idx,"status"]="needs_review"
            reasons=row.get("reasons", [])
            if not isinstance(reasons,list): reasons=[str(reasons)] if str(reasons).strip() else []
            reasons.append(note)
            normalized.at[idx,"reasons"]=reasons
    # Add canonical item context, then compare disclosed vendor specifications.
    normalized=normalized.merge(lines[["line_id","item_name"]],on="line_id",how="left")
    normalized=validate_quote_specs(normalized,raw,lines)
    # Attach useful commercial metadata and reasons.
    normalized["payment_terms"]=normalized.vendor_id.map({k:v.payment_terms for k,v in terms.items()})
    normalized["validity_days"]=normalized.vendor_id.map({k:v.validity_days for k,v in terms.items()})
    normalized["moq_pcs"]=normalized.vendor_id.map({k:v.moq_pcs for k,v in terms.items()})
    normalized["gst_treatment"]=normalized.vendor_id.map({k:v.gst_treatment for k,v in terms.items()})
    normalized["discount_pct"]=normalized.vendor_id.map({k:v.discount_pct for k,v in terms.items()})
    normalized["freight_treatment"]=normalized.vendor_id.map({k:v.freight_treatment for k,v in terms.items()})
    # Export raw extracted facts, never overwrite them with normalized values.
    return raw,normalized,raw_terms,assumptions,evidence
