
import os, json, sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
from extract.integration import run_full_pipeline

ROOT = Path(__file__).parent
st.set_page_config(page_title="Kill the Quote Spreadsheet", layout="wide")
st.title("Kill the Quote Spreadsheet")
st.caption("Procurement decision workspace · Corrugated packaging · 5 vendors · 30 line items")

lines = pd.read_csv(ROOT/"data/line_items.csv")
last_year = pd.read_csv(ROOT/"data/last_year.csv")
gst_rate = st.sidebar.number_input("GST rate (%)", min_value=0.0, max_value=28.0, value=5.0, step=0.5)
fx = st.sidebar.number_input("USD → INR", min_value=1.0, value=88.0, step=0.5)
fx_date = st.sidebar.text_input("FX rate date", value="2026-11-20")
st.sidebar.caption("Tax and FX are buyer-configurable assumptions. Confirm applicability before award.")

@st.cache_data(show_spinner=False)
def load_demo():
    return normalize_quotes(lines, last_year, ROOT/"vendor_files", fx, gst_rate/100)

if st.button("Run extraction + normalization", type="primary"):
    with st.spinner("Reading vendor responses and normalizing commercial terms..."):
        raw, df, raw_terms, assumptions, evidence = run_full_pipeline(lines, last_year, ROOT/"vendor_files", fx)
        raw.to_csv(ROOT/"data/raw_extractions.csv", index=False)
        df.to_csv(ROOT/"data/normalized_quotes.csv", index=False)
        (ROOT/"data/vendor_terms.json").write_text(json.dumps(raw_terms, indent=2))
        (ROOT/"data/assumptions.json").write_text(json.dumps(assumptions, indent=2))
        (ROOT/"data/evidence.json").write_text(json.dumps(evidence, indent=2))
        st.session_state["quotes"] = df
        st.session_state["assumptions"] = assumptions
        st.session_state["evidence"] = evidence

if "quotes" not in st.session_state:
    if (ROOT/"data/normalized_quotes.csv").exists():
        st.session_state["quotes"] = pd.read_csv(ROOT/"data/normalized_quotes.csv")
        st.session_state["assumptions"] = json.loads((ROOT/"data/assumptions.json").read_text()) if (ROOT/"data/assumptions.json").exists() else []
        st.session_state["evidence"] = json.loads((ROOT/"data/evidence.json").read_text()) if (ROOT/"data/evidence.json").exists() else []
    else:
        st.info("Run extraction to create the comparison. Add or replace files in vendor_files/ first.")
        st.stop()

quotes = st.session_state["quotes"]
tabs = st.tabs(["Comparison", "Review queue", "Analyst", "Award scenarios", "Trust center", "RFx co-pilot"])
with tabs[0]:
    st.subheader("Normalized comparison · INR per box · ex-GST, ex-freight")
    pivot = quotes.pivot_table(index=["line_id","item_name"], columns="vendor_id", values="net_inr_per_box", aggfunc="first")
    status = quotes.pivot_table(index=["line_id","item_name"], columns="vendor_id", values="status", aggfunc="first")
    st.dataframe(pivot.style.format("₹{:,.2f}").highlight_null("lightgray"), use_container_width=True)
    st.caption("Grey/blank cells are not quotes. They are never treated as zero.")
    chosen = st.selectbox("Inspect a quote cell", quotes.apply(lambda r: f'{r.line_id} · {r.vendor_id}', axis=1).tolist())
    row = quotes.loc[quotes.apply(lambda r: f'{r.line_id} · {r.vendor_id}' == chosen, axis=1)].iloc[0]
    st.write({k: row[k] for k in ["line_id","vendor_id","status","net_inr_per_box","confidence","source_file","source_snippet","assumptions"] if k in row.index})
with tabs[1]:
    st.subheader("Human review queue")
    review = quotes[quotes.status.eq("needs_review")]
    st.metric("Cells requiring review", len(review))
    for idx, r in review.iterrows():
        with st.expander(f'{r.vendor_id} · {r.line_id} · confidence {r.confidence}'):
            st.write(r.get("source_snippet",""))
            edited = st.number_input("Confirmed INR / box (ex-GST, ex-freight)", min_value=0.0, value=float(r.net_inr_per_box or 0), key=f"edit_{idx}")
            if st.button("Confirm price", key=f"confirm_{idx}"):
                quotes.loc[idx,"net_inr_per_box"] = edited
                quotes.loc[idx,"status"] = "accepted"
                st.session_state["quotes"] = quotes
                quotes.to_csv(ROOT/"data/normalized_quotes.csv", index=False)
                st.rerun()
    st.subheader("Assumptions ledger")
    st.dataframe(pd.DataFrame(st.session_state["assumptions"]), use_container_width=True)
with tabs[2]:
    st.subheader("Analyst")
    question = st.text_input("Ask about the comparison", placeholder="Which vendor is cheapest on a spec-compliant basis?")
    if st.button("Analyze"):
        q = question.lower()
        if "coverage" in q or "missing" in q:
            ans = quotes.groupby("vendor_id").quoted.sum().sort_values(ascending=False).to_frame("lines_quoted")
            st.dataframe(ans)
        elif "cheapest" in q or "lowest" in q:
            eligible = quotes[(quotes.status=="accepted") & (~quotes.spec_deviation.fillna("").astype(bool))]
            best = eligible.sort_values("net_inr_per_box").groupby("line_id").first().reset_index()
            st.dataframe(best[["line_id","vendor_id","net_inr_per_box"]])
        elif "last year" in q or "savings" in q:
            totals = quotes[quotes.status=="accepted"].merge(lines[["line_id","qty"]],on="line_id")
            totals["extended"] = totals.net_inr_per_box*totals.qty
            st.dataframe(totals.groupby("vendor_id").extended.sum().to_frame("quoted_value_inr"))
        else:
            st.info("For this question, inspect the normalized table and evidence. This starter supports coverage, cheapest compliant price and spend comparisons. Connect an OpenAI-compatible model to enable free-form tool selection.")
    st.caption("Supported deterministic queries are calculated from the normalized data; no demo answers are hardcoded.")
with tabs[3]:
    st.subheader("Award scenarios")
    min_quality = st.slider("Minimum quality score", 0, 100, 80)
    quality = {"V1":90,"V2":82,"V3":95,"V4":78,"V5":92}
    eligible_vendors = [v for v,s in quality.items() if s>=min_quality]
    award = build_award(quotes, lines, eligible_vendors)
    st.write("Eligible vendors:", ", ".join(eligible_vendors) if eligible_vendors else "None")
    st.dataframe(award, use_container_width=True)
    if not award.empty:
        st.metric("Indicative award value (ex-GST/freight)", f"₹{award.extended_value.sum()/1e7:,.2f} crore")
    st.caption("Quality scores are illustrative demo inputs, not supplied questionnaire evidence. Replace them with verified responses before a real award.")
with tabs[4]:
    st.subheader("Pre-award trust checks")
    coverage = quotes[quotes.quoted].groupby("vendor_id").line_id.nunique()
    unresolved = int((quotes.status=="needs_review").sum())
    st.write({"canonical_lines":len(lines),"unresolved_review_cells":unresolved,"FX_rate":fx,"FX_date":fx_date,"GST_assumption":gst_rate})
    st.dataframe(coverage.rename("quoted_lines").to_frame())
    st.warning("Do not finalize an award while review cells, specification deviations, tax classification or freight terms remain unresolved.")
    st.download_button("Export normalized quotes (CSV)", quotes.to_csv(index=False), "normalized_quotes.csv", "text/csv")
    try:
        with pd.ExcelWriter(ROOT/"data/award_export.xlsx", engine="openpyxl") as w:
            quotes.to_excel(w,index=False,sheet_name="Normalized quotes")
            lines.to_excel(w,index=False,sheet_name="RFx lines")
            pd.DataFrame(st.session_state["assumptions"]).to_excel(w,index=False,sheet_name="Assumptions")
        st.download_button("Export workbook (XLSX)", (ROOT/"data/award_export.xlsx").read_bytes(), "award_comparison.xlsx")
    except Exception as e:
        st.caption(f"Excel export unavailable: {e}")
with tabs[5]:
    st.subheader("RFx co-pilot")
    scope = st.text_area("Scope", "Supply of corrugated packaging for FMCG distribution.")
    terms = st.text_area("Commercial terms", "Quote per box; state GST, freight, MOQ, payment terms, validity and delivery lead time.")
    if st.button("Generate vendor RFx emails"):
        for vendor in ["V1","V2","V3","V4","V5"]:
            (ROOT/"outbox"/f"{vendor}_RFx.txt").write_text(f"Subject: RFx – Corrugated Packaging\\n\\n{scope}\\n\\n{terms}\\n\\nPlease quote all 30 attached line items and disclose all deviations.")
        st.success("Five draft RFx emails written to outbox/. No email was sent.")
