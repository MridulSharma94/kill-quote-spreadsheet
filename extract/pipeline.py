"""LLM extraction adapters. No ground-truth imports are permitted here."""
from __future__ import annotations
import os, json, re, base64
from pathlib import Path
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
from extract.structured import (parse_v1_xlsx, parse_v2_pdf_text, parse_v3_docx, parse_v3_terms, parse_v4_image_ocr, parse_v4_terms, parse_v5_email, parse_v5_terms)

VENDOR_FILES = {
 "V1":"Shree_Ganesh_V1.xlsx",
 "V2":"Mekong_Pack_V2.pdf",
 "V3":"Anand_Box_V3.docx",
 "V4":"Rajdhani_Pack_V4.jpg",
 "V5":"Eastern_Kraft_V5_email.txt",
}
TERMS_FILES = {"V4":"Rajdhani_Pack_V4_terms.txt"}

def _client():
    key=os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key: raise RuntimeError("Set GROQ_API_KEY (or OPENAI_API_KEY) before extraction.")
    return OpenAI(base_url=os.getenv("OPENAI_BASE_URL","https://api.groq.com/openai/v1"),api_key=key)

def _read_text(path):
    ext=path.suffix.lower()
    if ext==".txt": return path.read_text(errors="ignore")
    if ext==".pdf":
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    if ext==".docx":
        from docx import Document
        d=Document(path)
        return "\n".join([p.text for p in d.paragraphs]+[" | ".join(c.text for c in row.cells) for t in d.tables for row in t.rows])
    if ext==".xlsx":
        x=pd.ExcelFile(path)
        return "\n".join(f"SHEET {s}\n"+pd.read_excel(path,sheet_name=s,header=None).fillna("").to_string(index=False,header=False) for s in x.sheet_names)
    if ext in (".jpg",".jpeg",".png"): return ""
    return ""

def _canonical_context(lines,last_year):
    ly=last_year.set_index("line_id").iloc[:,0].to_dict()
    return "\n".join(
        f'{r.line_id} | {r.item_name} | {r.spec} | qty={int(r.qty)} | weight_kg_per_box={r.weight_kg_per_box}'
        + (f' | last_year_INR_per_box={ly[r.line_id]}' if r.line_id in ly else "")
        for r in lines.itertuples(index=False)
    )

def _call_model(vendor_id,path,lines,last_year,text,model):
    terms_text=""
    if vendor_id in TERMS_FILES:
        terms_text=_read_text(path.parent/TERMS_FILES[vendor_id])
    prompt=f"""
You are extracting a supplier quotation for procurement. Return a JSON object with keys:
vendor_id, commercial_terms, quotes.
commercial_terms keys: currency, quote_unit, gst_treatment (extra/inclusive/unknown),
gst_rate_in_quote (number or null), discount_pct (number), discount_scope, freight_treatment
(included/extra_known/extra_unknown), freight_inr_per_box (number or null), moq_pcs (integer or null),
payment_terms, validity_days, terms_confidence (0..1), terms_evidence (string).
quotes is an array. Each quote has line_id, quoted_price (number), unit (one of INR/BOX, USD/BOX,
INR/1000 PCS, INR/KG, SAME_AS_LAST_YEAR), currency, confidence (0..1), source_snippet,
spec_deviation (string; empty if none), assumptions (array of strings).
Do not invent missing lines. Do not infer a quote for an unquoted line except when supplier explicitly says
"same as last year"; in that case copy the corresponding last-year INR/box value provided in context,
set unit SAME_AS_LAST_YEAR, confidence 0.85 and document that it is a contextual reference, not a newly
quoted price. For per-kg prices, preserve the quoted per-kg rate; do not multiply by weight.
Identify specification deviations exactly. For V5, mark die-cut and printed items as needs clarification
because per-kg applicability is ambiguous. For the 7-ply V5 items, use last-year prices only because the
email explicitly says rest same as last year.
Never use the hidden ground truth. Use only the vendor content below.
Canonical items:
{_canonical_context(lines,last_year)}
Vendor ID: {vendor_id}
Vendor text:
{text}
Supplemental vendor terms:
{terms_text}
"""
    if path.suffix.lower() in (".jpg",".jpeg",".png"):
        mime="image/jpeg" if path.suffix.lower() in (".jpg",".jpeg") else "image/png"
        b64=base64.b64encode(path.read_bytes()).decode()
        content=[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}"}}]
        messages=[{"role":"user","content":content}]
        selected=os.getenv("GROQ_VISION_MODEL","qwen/qwen3.8-27b")
    else:
        messages=[{"role":"user","content":prompt}]
        selected=model
    client = _client()
    output_limit = 600 if path.suffix.lower() in (".jpg", ".jpeg", ".png") else 1800
    try:
        response = client.chat.completions.create(
            model=selected, messages=messages,
            response_format={"type": "json_object"},
            temperature=0, max_tokens=output_limit,
        )
    except Exception as exc:
        message = str(exc).lower()
        # Some OpenAI-compatible providers reject JSON mode for selected models.
        if not any(token in message for token in ("failed to validate json", "failed_generation", "response_format")):
            raise
        fallback_messages = [
            {"role": "system", "content": "Return only one valid JSON object. Do not use markdown fences or commentary."},
            *messages,
        ]
        response = client.chat.completions.create(
            model=selected, messages=fallback_messages,
            temperature=0, max_tokens=output_limit,
        )
    raw = response.choices[0].message.content or ""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{vendor_id}: model returned invalid JSON: {exc}; response={raw[:500]}")
    if not isinstance(parsed, dict) or not isinstance(parsed.get("quotes", []), list):
        raise ValueError(f"{vendor_id}: model response must be an object with a quotes array")
    return parsed

def _call_image_in_chunks(vendor_id, path, lines, last_year, model):
    """Run vision extraction over overlapping, enhanced horizontal crops.

    The rate card is a tall image. Smaller overlapping crops reduce missed rows
    while preserving the original source file as the evidence reference.
    """
    from PIL import Image, ImageEnhance, ImageOps
    import tempfile
    image = Image.open(path).convert("RGB")
    width, height = image.size
    spans = [(0, int(height * .43)), (int(height * .36), int(height * .76)),
             (int(height * .69), height)]
    merged = {}
    terms = {}
    for start, end in spans:
        crop = image.crop((0, start, width, end))
        crop = ImageOps.autocontrast(crop)
        crop = ImageEnhance.Sharpness(crop).enhance(1.4)
        crop = crop.resize((int(crop.width * 1.5), int(crop.height * 1.5)))
        with tempfile.NamedTemporaryFile(suffix=".jpg", dir=path.parent) as tmp:
            crop.save(tmp.name, quality=95)
            result = _call_model(vendor_id, Path(tmp.name), lines, last_year,
                                 "Image crop of the supplier rate card. Extract only line items visible in this crop; do not infer rows outside it.", model)
        if not terms:
            terms = result.get("commercial_terms", {})
        for q in result.get("quotes", []):
            lid = str(q.get("line_id", "")).strip().upper()
            if not lid:
                continue
            prior = merged.get(lid)
            if prior is None or float(q.get("confidence", 0) or 0) > float(prior.get("confidence", 0) or 0):
                merged[lid] = q
    return {"vendor_id": vendor_id, "commercial_terms": terms, "quotes": list(merged.values())}


def extract_vendor_files(lines,last_year,vendor_dir,fx,gst):
    """Extract source facts; deterministic parsers override LLM guesses where possible."""
    vendor_dir=Path(vendor_dir)
    model=os.getenv("OPENAI_MODEL","openai/gpt-oss-120b")
    all_quotes=[]; terms_by_vendor={}; evidence=[]; assumptions=[]
    held_by_vendor={}
    for vid,filename in VENDOR_FILES.items():
        path=vendor_dir/filename
        if not path.exists():
            assumptions.append({"vendor_id":vid,"assumption":f"Missing source file: {filename}"})
            continue
        text=_read_text(path)
        # Prefer deterministic extraction for stable source layouts. Vision/LLM
        # remains a fallback only where a deterministic parser cannot be used.
        if vid == "V3":
            model_quotes = parse_v3_docx(path)
            result = {"commercial_terms": parse_v3_terms(path), "quotes": model_quotes}
        elif vid == "V4":
            try:
                model_quotes = parse_v4_image_ocr(path)
                result = {"commercial_terms": parse_v4_terms(vendor_dir/TERMS_FILES[vid]), "quotes": model_quotes}
            except Exception as ocr_error:
                result = _call_image_in_chunks(vid,path,lines,last_year,model)
                result["commercial_terms"] = parse_v4_terms(vendor_dir/TERMS_FILES[vid])
                assumptions.append({"vendor_id":vid,"assumption":f"V4 OCR fallback used: {ocr_error}"})
        elif vid == "V5":
            result = {"commercial_terms": parse_v5_terms(text), "quotes": []}
        else:
            result = _call_model(vid,path,lines,last_year,text,model)
        t=result.get("commercial_terms",{})
        terms_by_vendor[vid]=t
        assumptions.append({"vendor_id":vid,"assumption":"Commercial terms extracted from source; verify terms_evidence before award.",
                            "terms_evidence":t.get("terms_evidence",""),"terms_confidence":t.get("terms_confidence",0)})
        model_quotes=result.get("quotes",[])
        # Deterministic source parsers take precedence over LLM line-item extraction.
        if vid == "V1":
            model_quotes = parse_v1_xlsx(path)
        elif vid == "V2":
            parsed = parse_v2_pdf_text(text)
            if parsed:
                model_quotes = parsed
        elif vid == "V3":
            model_quotes = parse_v3_docx(path)
        elif vid == "V4":
            # The deterministic OCR result is already in model_quotes when available.
            if not model_quotes:
                model_quotes = parse_v4_image_ocr(path)
        elif vid == "V5":
            parsed, held_by_vendor[vid] = parse_v5_email(text, lines, last_year)
            model_quotes = parsed
        seen=set()
        for q in model_quotes:
            lid=str(q.get("line_id","")).strip().upper()
            if lid not in set(lines.line_id): continue
            if lid in seen:
                assumptions.append({"vendor_id":vid,"assumption":f"Duplicate line {lid}; requires manual reconciliation."})
                continue
            seen.add(lid)
            rec={"vendor_id":vid,"line_id":lid,"quoted":True,
                 "quoted_price_as_stated":q.get("quoted_price",q.get("price")),"quoted_unit":q.get("unit"),
                 "currency":q.get("currency",t.get("currency","INR")),
                 "confidence":float(q.get("confidence",0)),
                 "source_file":filename,"source_snippet":q.get("source_snippet",""),
                 "spec_deviation":q.get("spec_deviation",""),
                 "assumptions":"; ".join(q.get("assumptions",[])) if isinstance(q.get("assumptions",[]),list) else str(q.get("assumptions", "")),
                 "extraction_note":""}
            all_quotes.append(rec)
            evidence.append({"vendor_id":vid,"line_id":lid,"source_file":filename,
                             "source_snippet":rec["source_snippet"],"confidence":rec["confidence"]})
    # Explicit matrix: a missing extraction is not silently converted to a no-bid.
    df=pd.DataFrame(all_quotes)
    columns=["vendor_id","line_id","quoted","quoted_price_as_stated","quoted_unit","currency","confidence","source_file","source_snippet","spec_deviation","assumptions","extraction_note"]
    if df.empty: df=pd.DataFrame(columns=columns)
    if "quote_state" not in df.columns:
        df["quote_state"] = "quoted"
    for vid in VENDOR_FILES:
        existing=set(df.loc[df.vendor_id.eq(vid),"line_id"].astype(str)) if not df.empty else set()
        for lid in lines.line_id.astype(str):
            if lid in existing: continue
            note=held_by_vendor.get(vid,{}).get(lid, "")
            if note:
                quote_state = "needs_clarification"
            elif vid == "V4" and int(lid[1:]) > 27:
                quote_state = "supplier_no_quote"
                note = "Vendor terms addendum states the rate card contains 27 quoted lines; this line is unlisted."
            else:
                quote_state = "extraction_failed"
                note = "No price extracted from source; verify original source. This is not a supplier no-bid."
            df.loc[len(df)]={"vendor_id":vid,"line_id":lid,"quoted":False,"quoted_price_as_stated":None,
                "quoted_unit":None,"currency":None,"confidence":0,"source_file":VENDOR_FILES[vid],
                "source_snippet":"","spec_deviation":"","assumptions":"",
                "extraction_note":note,"quote_state":quote_state}
    df.loc[df["quoted"].fillna(False).astype(bool), "quote_state"] = "quoted"
    return df,terms_by_vendor,assumptions,evidence
