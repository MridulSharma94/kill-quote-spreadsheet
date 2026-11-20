"""LLM extraction adapters. No ground-truth imports are permitted here."""
from __future__ import annotations
import os, json, re, base64
from pathlib import Path
import pandas as pd
from openai import OpenAI

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
    response=_client().chat.completions.create(
        model=selected,
        messages=messages,
        response_format={"type":"json_object"},
        temperature=0
    )
    raw=response.choices[0].message.content
    try: return json.loads(raw)
    except json.JSONDecodeError as e: raise ValueError(f"{vendor_id}: model returned invalid JSON: {e}; response={raw[:500]}")

def extract_vendor_files(lines,last_year,vendor_dir,fx,gst):
    """Extract raw facts; normalization is a separate deterministic step."""
    vendor_dir=Path(vendor_dir)
    model=os.getenv("OPENAI_MODEL","openai/gpt-oss-120b")
    all_quotes=[]; terms_by_vendor={}; evidence=[]; assumptions=[]
    for vid,filename in VENDOR_FILES.items():
        path=vendor_dir/filename
        if not path.exists():
            assumptions.append({"vendor_id":vid,"assumption":f"Missing source file: {filename}"})
            continue
        text=_read_text(path)
        result=_call_model(vid,path,lines,last_year,text,model)
        t=result.get("commercial_terms",{})
        terms_by_vendor[vid]=t
        assumptions.append({"vendor_id":vid,"assumption":"Commercial terms extracted from source; verify terms_evidence before award.",
                            "terms_evidence":t.get("terms_evidence",""),"terms_confidence":t.get("terms_confidence",0)})
        seen=set()
        for q in result.get("quotes",[]):
            lid=str(q.get("line_id","")).strip().upper()
            if lid not in set(lines.line_id): continue
            if lid in seen:
                assumptions.append({"vendor_id":vid,"assumption":f"Duplicate line {lid}; requires manual reconciliation."})
                continue
            seen.add(lid)
            rec={"vendor_id":vid,"line_id":lid,"quoted":True,
                 "quoted_price_as_stated":q.get("quoted_price"),"quoted_unit":q.get("unit"),
                 "currency":q.get("currency",t.get("currency","INR")),
                 "confidence":float(q.get("confidence",0)),
                 "source_file":filename,"source_snippet":q.get("source_snippet",""),
                 "spec_deviation":q.get("spec_deviation",""),
                 "assumptions":"; ".join(q.get("assumptions",[]))}
            all_quotes.append(rec)
            evidence.append({"vendor_id":vid,"line_id":lid,"source_file":filename,
                             "source_snippet":rec["source_snippet"],"confidence":rec["confidence"]})
    # Keep missing rows explicit. No price is ever imputed here.
    df=pd.DataFrame(all_quotes)
    if df.empty:
        df=pd.DataFrame(columns=["vendor_id","line_id","quoted","quoted_price_as_stated","quoted_unit","currency","confidence","source_file","source_snippet","spec_deviation","assumptions"])
    existing=set(zip(df.vendor_id,df.line_id))
    for vid in VENDOR_FILES:
        for lid in lines.line_id:
            if (vid,lid) not in existing:
                df.loc[len(df)]={"vendor_id":vid,"line_id":lid,"quoted":False,"quoted_price_as_stated":None,
                    "quoted_unit":None,"currency":None,"confidence":0,"source_file":VENDOR_FILES[vid],
                    "source_snippet":"","spec_deviation":"","assumptions":"No extracted quote; verify source before treating as no_quote."}
    return df,terms_by_vendor,assumptions,evidence
