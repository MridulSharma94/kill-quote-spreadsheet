
import os, json, sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
from extract.integration import run_full_pipeline
from quality.checks import award_eligible_quotes, award_coverage, build_review_register

ROOT = Path(__file__).parent
st.set_page_config(page_title="Kill the Quote Spreadsheet", layout="wide")
st.title("Kill the Quote Spreadsheet")
st.caption("Procurement decision workspace · Corrugated packaging · 5 vendors · 30 line items")

lines = pd.read_csv(ROOT/"data/line_items.csv")
last_year = pd.read_csv(ROOT/"data/last_year.csv")
gst_rate = st.sidebar.number_input("GST rate (%)", min_value=0.0, max_value=28.0, value=5.0, step=0.5)
fx = st.sidebar.number_input("USD → INR", min_value=1.0, value=92.6, step=0.5)
fx_date = st.sidebar.text_input("FX rate date", value="2026-11-20")
st.sidebar.caption("Tax and FX are buyer-configurable assumptions. Confirm applicability before award.")


def build_award(quotes, lines, eligible_vendors):
    eligible = award_eligible_quotes(quotes, eligible_vendors)

    if eligible.empty:
        return pd.DataFrame()

    price_col = "landed_pre_gst_inr_per_box"
    eligible[price_col] = pd.to_numeric(
        eligible[price_col], errors="coerce"
    )
    eligible = eligible.dropna(subset=[price_col])

    winners = (
        eligible.sort_values(price_col)
        .drop_duplicates(subset=["line_id"], keep="first")
    )

    award = winners.merge(
        lines[["line_id", "qty"]],
        on="line_id",
        how="left",
        validate="one_to_one"
    )

    award["selected_inr_per_box"] = award[price_col]
    award["extended_value"] = (
        award["selected_inr_per_box"] * award["qty"]
    )

    return award

if st.button("Run extraction + normalization", type="primary"):
    with st.spinner("Reading vendor responses and normalizing commercial terms..."):
        raw, df, raw_terms, assumptions, evidence = run_full_pipeline(lines, last_year, ROOT/"vendor_files", fx)
        raw.to_csv(ROOT/"data/raw_extractions.csv", index=False)
        df.to_csv(ROOT/"data/normalized_quotes.csv", index=False)
        (ROOT/"data/vendor_terms.json").write_text(json.dumps(raw_terms, indent=2))
        (ROOT/"data/assumptions.json").write_text(json.dumps(assumptions, indent=2))
        (ROOT/"data/evidence.json").write_text(json.dumps(evidence, indent=2))
        st.session_state["quotes"] = df
        st.session_state["raw"] = raw
        st.session_state["assumptions"] = assumptions
        st.session_state["evidence"] = evidence

if "quotes" not in st.session_state:
    if (ROOT/"data/normalized_quotes.csv").exists():
        st.session_state["quotes"] = pd.read_csv(ROOT/"data/normalized_quotes.csv")
        st.session_state["assumptions"] = json.loads((ROOT/"data/assumptions.json").read_text()) if (ROOT/"data/assumptions.json").exists() else []
        st.session_state["evidence"] = json.loads((ROOT/"data/evidence.json").read_text()) if (ROOT/"data/evidence.json").exists() else []
        raw_path = ROOT / "data/raw_extractions.csv"
        st.session_state["raw"] = (
            pd.read_csv(raw_path) if raw_path.exists()
            else pd.DataFrame()
        )
    else:
        st.info("Run extraction to create the comparison. Add or replace files in vendor_files/ first.")
        st.stop()

quotes = st.session_state["quotes"]
tabs = st.tabs(["Comparison", "Review queue", "Analyst", "Award scenarios", "Trust center", "RFx co-pilot"])
with tabs[0]:
    st.subheader("Normalized comparison · INR per box · ex-GST, ex-freight")
    pivot = quotes.pivot_table(index=["line_id","item_name"], columns="vendor_id", values="net_inr_per_box", aggfunc="first")
    status = quotes.pivot_table(index=["line_id","item_name"], columns="vendor_id", values="status", aggfunc="first")
    st.dataframe(pivot.style.format("₹{:,.2f}").highlight_null("lightgray"), width='stretch')
    st.caption("Grey/blank cells are not quotes. They are never treated as zero.")
    chosen = st.selectbox("Inspect a quote cell", quotes.apply(lambda r: f'{r.line_id} · {r.vendor_id}', axis=1).tolist())
    row = quotes.loc[quotes.apply(lambda r: f'{r.line_id} · {r.vendor_id}' == chosen, axis=1)].iloc[0]
    st.write({k: row[k] for k in ["line_id","vendor_id","status","net_inr_per_box","confidence","source_file","source_snippet","assumptions"] if k in row.index})
with tabs[1]:
    st.subheader("Human review queue")

    raw = st.session_state.get("raw", pd.DataFrame())
    review_register = build_review_register(quotes, raw, lines)

    review_items = review_register[review_register["review_blockers"].fillna("").str.strip().ne("")]

    st.metric("Cells requiring review or source verification", len(review_items))

    st.dataframe(
        review_items[
            [
                "vendor_id", "line_id", "quote_state", "status",
                "spec_validation", "review_blockers", "source_file",
                "source_snippet"
            ]
        ],
        width="stretch"
    )

    st.subheader("Assumptions ledger")
    st.dataframe(pd.DataFrame(st.session_state["assumptions"]), width="stretch")
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
    quality = {"V1": 90, "V2": 82, "V3": 95, "V4": 78, "V5": 92}
    eligible_vendors = [
        vendor for vendor, score in quality.items()
        if score >= min_quality
    ]

    eligible_quotes = award_eligible_quotes(quotes, eligible_vendors)
    coverage = award_coverage(eligible_quotes, lines)
    award = build_award(quotes, lines, eligible_vendors)

    st.write(
        "Eligible vendors:",
        ", ".join(eligible_vendors) if eligible_vendors else "None"
    )

    st.subheader("Award-eligible quotes")
    st.dataframe(eligible_quotes, width="stretch")

    st.subheader("Line-level award coverage")
    st.dataframe(coverage, width="stretch")

    st.metric(
        "RFx lines with at least one eligible quote",
        f"{int(coverage['awardable'].sum())} / {len(coverage)}"
    )

    st.subheader("Indicative award")
    st.dataframe(award, width="stretch")

    if not award.empty:
        st.metric(
            "Indicative award value (pre-GST, including stated freight)",
            f"₹{award.extended_value.sum()/1e7:,.2f} crore"
        )
    else:
        st.warning(
            "No quotes passed all award eligibility checks. "
            "Resolve evidence, specification, confidence and commercial blockers."
        )

    st.caption(
        "Quality scores are illustrative demo inputs, not verified supplier "
        "questionnaire evidence. This is an eligibility gate, not an award recommendation."
    )
with tabs[4]:
    st.subheader("Pre-award trust checks")
    coverage = quotes[quotes.quoted].groupby("vendor_id").line_id.nunique()
    unresolved = int((quotes.status=="needs_review").sum())
    st.write({"canonical_lines":len(lines),"unresolved_review_cells":unresolved,"FX_rate":fx,"FX_date":fx_date,"GST_assumption":gst_rate})
    st.dataframe(coverage.rename("quoted_lines").to_frame())
    st.warning("Do not finalize an award while review cells, specification deviations, tax classification or freight terms remain unresolved.")
    st.download_button("Export normalized quotes (CSV)", quotes.to_csv(index=False), "normalized_quotes.csv", "text/csv")
    try:
        raw = st.session_state.get("raw", pd.DataFrame())
        review_register = build_review_register(quotes, raw, lines)
        eligible_quotes = award_eligible_quotes(quotes)
        coverage = award_coverage(eligible_quotes, lines)

        export_path = ROOT / "data/award_export.xlsx"

        with pd.ExcelWriter(export_path, engine="openpyxl") as writer:
            quotes.to_excel(
                writer, index=False, sheet_name="Normalized quotes"
            )
            lines.to_excel(
                writer, index=False, sheet_name="RFx lines"
            )
            pd.DataFrame(
                st.session_state["assumptions"]
            ).to_excel(
                writer, index=False, sheet_name="Assumptions"
            )
            eligible_quotes.to_excel(
                writer, index=False, sheet_name="Award eligible quotes"
            )
            coverage.to_excel(
                writer, index=False, sheet_name="Award coverage"
            )
            review_register.to_excel(
                writer, index=False, sheet_name="Review register"
            )

        st.download_button(
            "Export workbook (XLSX)",
            export_path.read_bytes(),
            "award_comparison.xlsx"
        )

    except Exception as e:
        st.caption(f"Excel export unavailable: {e}")

with tabs[5]:
    st.subheader("RFx co-pilot")
    scope = st.text_area("Scope", "Supply of corrugated packaging for FMCG distribution.")
    terms = st.text_area("Commercial terms", "Quote per box; state GST, freight, MOQ, payment terms, validity and delivery lead time.")
    if st.button("Generate vendor RFx emails"):
        (ROOT / "outbox").mkdir(exist_ok=True)
        for vendor in ["V1","V2","V3","V4","V5"]:
            (ROOT/"outbox"/f"{vendor}_RFx.txt").write_text(f"Subject: RFx – Corrugated Packaging\\n\\n{scope}\\n\\n{terms}\\n\\nPlease quote all 30 attached line items and disclose all deviations.")
        st.success("Five draft RFx emails written to outbox/. No email was sent.")
