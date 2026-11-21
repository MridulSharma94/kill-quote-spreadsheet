import os, json, sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
from extract.integration import run_full_pipeline
from quality.checks import award_eligible_quotes, award_coverage, build_review_register

ROOT = Path(__file__).parent
st.set_page_config(
    page_title="Kill the Quote Spreadsheet | Procurement Workspace",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root {
  --ink: #172B4D; --muted: #66758A; --navy: #102A43; --navy2: #183B56;
  --teal: #0F9D91; --teal-soft: #E7F6F3; --line: #E5EAF0;
  --canvas: #F5F7FA; --white: #FFFFFF;
}
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: var(--ink); }
.stApp { background: var(--canvas); }
.block-container { max-width: 1500px; padding-top: 1.5rem !important; padding-bottom: 3rem; }
[data-testid="stHeader"] { background: rgba(245,247,250,.92); }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #102A43 0%, #163B56 100%); border-right: 0; }
[data-testid="stSidebar"] * { color: #F3F7FA !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #C8D6E2 !important; }
[data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea {
  background: #FFFFFF !important; color: #172B4D !important; border-radius: 9px !important;
}
[data-testid="stSidebar"] [data-testid="stNumberInput"] button { color: #172B4D !important; }
.hero {
  background: linear-gradient(115deg, #102A43 0%, #183B56 62%, #176B70 100%);
  border-radius: 18px; padding: 34px 36px 30px; margin: 8px 0 26px 0;
  box-shadow: 0 12px 30px rgba(16,42,67,.12); color: #fff;
  overflow: hidden; position: relative; margin-top: 2rem !important;
}
.hero-kicker {
  display: block; color: #A9E8DF !important; text-transform: uppercase;
  letter-spacing: .14em; font-size: 11px; line-height: 1.6; margin-top: 0 !important; padding-top:0 !important;
  font-weight: 700; margin: 0 0 9px 0; position: relative;
}
.hero h1 {
  color: #FFFFFF !important; font: 800 32px 'Manrope', sans-serif;
  line-height: 1.2; margin: 0 0 9px 0; letter-spacing: -.7px;
}
.hero p { color: #E0EAF0 !important; margin: 0; font-size: 14px; line-height: 1.6; }
.hero-meta { display: flex; flex-wrap: wrap; gap: 9px; margin-top: 18px; }
.hero-chip { background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.17); color: #F5FAFC; border-radius: 30px; padding: 6px 11px; font-size: 12px; }
h1, h2, h3 { font-family: 'Manrope', sans-serif !important; color: var(--navy) !important; letter-spacing: -.35px; }
h2 { font-size: 22px !important; font-weight: 800 !important; }
h3 { font-size: 17px !important; font-weight: 700 !important; }
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 7px; border-bottom: 1px solid var(--line); padding: 0 2px 10px; }
[data-testid="stTabs"] button[data-baseweb="tab"] { background: #EDF1F5; border-radius: 9px; padding: 10px 15px; border: 1px solid transparent; color: #52657A; font-weight: 600; }
[data-testid="stTabs"] button[aria-selected="true"] { background: var(--navy); color: #fff; border-color: var(--navy); }
[data-testid="stTabs"] button[aria-selected="true"] p { color: #fff !important; }
[data-testid="stMetric"] { background: #fff; border: 1px solid var(--line); border-radius: 13px; padding: 16px 18px; box-shadow: 0 3px 12px rgba(16,42,67,.035); }
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-weight: 600; }
[data-testid="stMetricValue"] { color: var(--navy) !important; font-family: 'Manrope', sans-serif; }
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: #fff; box-shadow: 0 3px 12px rgba(16,42,67,.025); }
[data-testid="stDataFrame"] [role="columnheader"] {
  background: #EEF3F7 !important; color: #29445E !important;
  font-weight: 700 !important; border-bottom: 1px solid #DCE5EC !important;
}
[data-testid="stDataFrame"] [role="gridcell"] { border-color: #EDF1F5 !important; }
[data-testid="stSubheader"] { margin-top: 1.4rem; }
[data-testid="stAlert"] p { line-height: 1.55; }
[data-testid="stExpander"] { background: #fff; border: 1px solid var(--line); border-radius: 11px; }
.stButton > button, .stDownloadButton > button { border-radius: 9px; font-weight: 700; min-height: 42px; border: 1px solid #D7E0E8; }
.stButton > button[kind="primary"] { background: var(--teal); border-color: var(--teal); color: #fff; }
.stButton > button[kind="primary"]:hover { background: #0B8178; border-color: #0B8178; color: #fff; }
.stDownloadButton > button { background: #fff; color: var(--navy); }
[data-testid="stAlert"] { border-radius: 11px; }
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-testid="stSelectbox"] > div {
  border-radius: 9px !important; border-color: #D8E1E9 !important; background: #fff;
}
[data-testid="stCaptionContainer"] { color: #718096; }
hr { border-color: var(--line); }
@media (max-width: 800px) {
  .block-container { padding: 1rem 1rem 2rem; }
  .hero { padding: 25px 22px; margin-top: 4px; }
  .hero h1 { font-size: 25px; }
  [data-testid="stTabs"] [data-baseweb="tab-list"] { overflow-x: auto; }
}
</style>
<div class="hero">
  <div class="hero-kicker">Procurement intelligence workspace</div>
  <h1>Kill the Quote Spreadsheet</h1>
  <p>From scattered supplier quotes to a traceable, defensible sourcing decision.</p>
  <div class="hero-meta">
    <span class="hero-chip">Corrugated packaging</span>
    <span class="hero-chip">5 suppliers</span>
    <span class="hero-chip">30 RFQ line items</span>
    <span class="hero-chip">Evidence-led evaluation</span>
  </div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### PROCUREMENT CONTROLS")
    st.caption("Buyer assumptions · editable")

lines = pd.read_csv(ROOT/"data/line_items.csv")
last_year = pd.read_csv(ROOT/"data/last_year.csv")
gst_rate = st.sidebar.number_input("GST rate (%)", min_value=0.0, max_value=28.0, value=5.0, step=0.5)
fx = st.sidebar.number_input("USD → INR", min_value=1.0, value=92.6, step=0.5)
fx_date = st.sidebar.text_input("FX rate date", value="2026-11-21")
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
tabs = st.tabs(["Comparison", "Review queue", "Analyst", "Award scenarios", "Trust center", "RFQ co-pilot"])
with tabs[0]:
    st.subheader("Normalized comparison · INR per box · ex-GST, ex-freight")
    pivot = quotes.pivot_table(index=["line_id","item_name"], columns="vendor_id", values="net_inr_per_box", aggfunc="first")
    status = quotes.pivot_table(index=["line_id","item_name"], columns="vendor_id", values="status", aggfunc="first")
    styled_pivot = (
        pivot.style
        .format("₹{:,.2f}", na_rep="—", escape="html")
        .highlight_null(props="color: #94A3B8; background-color: #F1F5F9;")
        .set_properties(**{
            "text-align": "right",
            "padding": "11px 14px",
            "border-bottom": "1px solid #E2E8F0",
        })
        .set_table_styles([
            {
                "selector": "th",
                "props": [
                    ("background-color", "#EAF0F5"),
                    ("color", "#18344D"),
                    ("font-weight", "700"),
                    ("padding", "12px 14px"),
                    ("border-bottom", "2px solid #CBD5E1"),
                    ("text-align", "left"),
                ],
            },
            {
                "selector": "tbody tr:hover",
                "props": [("background-color", "#F0FDFA")],
            },
        ])
    )
    st.dataframe(
        styled_pivot,
        width="stretch",
        hide_index=False,
    )
    st.caption("Grey/blank cells are not quotes. They are never treated as zero.")
    chosen = st.selectbox("Inspect a quote cell", quotes.apply(lambda r: f'{r.line_id} · {r.vendor_id}', axis=1).tolist())
    row = quotes.loc[quotes.apply(lambda r: f'{r.line_id} · {r.vendor_id}' == chosen, axis=1)].iloc[0]
    st.write({k: row[k] for k in ["line_id","vendor_id","status","net_inr_per_box","confidence","source_file","source_snippet","assumptions"] if k in row.index})
with tabs[1]:
    st.subheader("Human review queue")

    raw = st.session_state.get("raw", pd.DataFrame())
    review_register = build_review_register(quotes, raw, lines)

    review_items = review_register[
        review_register["review_blockers"].fillna("").str.strip().ne("")
    ]

    st.metric("Cells requiring review or source verification", len(review_items))

    # Create a display-only copy
    review_display = review_items[
        [
            "vendor_id", "line_id", "quote_state", "status",
            "spec_validation", "review_blockers", "source_file",
            "source_snippet"
        ]
    ].copy()

    import ast

    def format_blockers(value):
        if pd.isna(value):
            return "—"

        if isinstance(value, str):
            try:
                parsed = ast.literal_eval(value)
                if isinstance(parsed, (list, tuple)):
                    return " · ".join(map(str, parsed))
            except (ValueError, SyntaxError):
                pass

        if isinstance(value, (list, tuple)):
            return " · ".join(map(str, value))

        return str(value)

    review_display["review_blockers"] = (
        review_display["review_blockers"].apply(format_blockers)
    )

    # Convert blocker lists into readable text
    review_display["review_blockers"] = review_display[
        "review_blockers"
    ].apply(
        lambda x: " · ".join(map(str, x))
        if isinstance(x, (list, tuple))
        else str(x) if pd.notna(x) else "—"
    )

    # Colour specification validation statuses
    def style_spec_status(value):
        colors = {
            "verified": "background-color: #DCFCE7; color: #166534;",
            "unverified": "background-color: #FEF3C7; color: #92400E;",
            "mismatch": "background-color: #FEE2E2; color: #991B1B;",
            "not_applicable": "background-color: #F1F5F9; color: #64748B;",
        }
        return colors.get(value, "")

    styled_review = review_display.style.map(
        style_spec_status,
        subset=["spec_validation"]
    )

    st.dataframe(
        styled_review,
        width="stretch"
    )

    st.subheader("Commercial terms & evidence")

    st.caption(
        "Commercial terms below are extracted from supplier responses. "
        "Review the supporting evidence and confirm applicability before award."
    )

    assumptions_df = pd.DataFrame(st.session_state["assumptions"]).copy()

    if not assumptions_df.empty:
        assumptions_df = assumptions_df.rename(columns={
            "vendor_id": "Vendor",
            "assumption": "Review note",
            "terms_evidence": "Extracted terms / source evidence",
            "terms_confidence": "Extraction confidence"
        })

        # Replace generic internal wording with a clear user-facing note.
        if "Review note" in assumptions_df.columns:
            assumptions_df["Review note"] = (
                "Verify commercial terms against the original supplier response."
            )

        # Make confidence easier to scan.
        if "Extraction confidence" in assumptions_df.columns:
            assumptions_df["Extraction confidence"] = (
                pd.to_numeric(
                    assumptions_df["Extraction confidence"],
                    errors="coerce"
                ) * 100
            ).round(1).map(
                lambda x: f"{x:.1f}%" if pd.notna(x) else "Not available"
            )

        st.dataframe(
            assumptions_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Vendor": st.column_config.TextColumn(
                    "Vendor",
                    width="small"
                ),
                "Review note": st.column_config.TextColumn(
                    "Review note",
                    width="medium"
                ),
                "Extracted terms / source evidence": st.column_config.TextColumn(
                    "Extracted terms / source evidence",
                    width="large"
                ),
                "Extraction confidence": st.column_config.TextColumn(
                    "Extraction confidence",
                    width="small"
                )
            }
        )
    else:
        st.info("No commercial terms have been extracted yet.")

with tabs[2]:
    st.subheader("Analyst")

    st.caption(
        "Explore supplier coverage, award eligibility and price comparisons "
        "using the extracted procurement data."
    )

    suggested_questions = [
        "Show quote coverage by vendor",
        "Which vendor is cheapest on a spec-compliant basis?",
        "Which RFQ lines have no eligible supplier?",
        "Compare quoted spend with last year"
    ]

    selected_prompt = st.selectbox(
        "Suggested questions",
        ["Choose a question..."] + suggested_questions
    )

    question = st.text_input(
        "Ask about the comparison",
        value=(
            selected_prompt
            if selected_prompt != "Choose a question..."
            else ""
        ),
        placeholder="Enter your procurement question..."
    )

    if st.button("Analyze", type="primary"):
        st.subheader("Analysis results")
        q = question.lower()
        raw = st.session_state.get("raw", pd.DataFrame())

        if "coverage" in q or "missing" in q:
            states = quotes.copy()
            if "quote_state" not in states.columns:
                states["quote_state"] = "quoted"

            coverage_rows = []
            for vendor in sorted(quotes.vendor_id.unique()):
                part = states[states.vendor_id.eq(vendor)]
                coverage_rows.append({
                    "vendor_id": vendor,
                    "quoted": int((part.quote_state.eq("quoted") & part.quoted.fillna(False).astype(bool)).sum()),
                    "supplier_no_quote": int(part.quote_state.eq("supplier_no_quote").sum()),
                    "needs_clarification": int(part.quote_state.eq("needs_clarification").sum()),
                    "extraction_failed": int(part.quote_state.eq("extraction_failed").sum())
                })

            st.dataframe(pd.DataFrame(coverage_rows), width="stretch")

        elif "cheapest" in q or "lowest" in q:
            eligible = award_eligible_quotes(quotes)

            if eligible.empty:
                st.warning("No quotes passed all award eligibility checks.")
            else:
                price_col = "landed_pre_gst_inr_per_box"
                best = (eligible.sort_values(price_col).drop_duplicates("line_id")[["line_id", "vendor_id", price_col]])

                coverage = award_coverage(eligible, lines)
                result = coverage.merge(best, on="line_id", how="left")

                st.dataframe(result, width="stretch")
                st.caption(
                    "Only quotes passing the strict award eligibility gate "
                    "are included. Lines without an eligible quote remain blank."
                )

        elif "last year" in q or "savings" in q or "spend" in q:
            eligible = award_eligible_quotes(quotes)

            current = eligible[["line_id", "vendor_id", "net_inr_per_box"]].copy()

            comparison = current.merge(
                last_year[["line_id", "last_year_price_inr_per_box", "vendor"]],
                on="line_id",
                how="left",
                validate="one_to_one"
            ).merge(
                lines[["line_id", "qty"]],
                on="line_id",
                how="left",
                validate="one_to_one"
            )

            comparison["current_extended_inr"] = (comparison.net_inr_per_box * comparison.qty)
            comparison["last_year_extended_inr"] = (comparison.last_year_price_inr_per_box * comparison.qty)
            comparison["directional_delta_inr"] = (comparison.current_extended_inr - comparison.last_year_extended_inr)
            comparison["directional_delta_pct"] = (comparison.directional_delta_inr / comparison.last_year_extended_inr * 100)

            st.dataframe(comparison, width="stretch")

            current_total = comparison.current_extended_inr.sum()
            previous_total = comparison.last_year_extended_inr.sum()
            delta = current_total - previous_total

            st.metric("Current quoted value for comparable eligible lines", f"₹{current_total:,.2f}")
            st.metric("Last-year value for the same quantities and lines", f"₹{previous_total:,.2f}")
            st.metric(
                "Directional price difference", f"₹{delta:,.2f}", f"{delta / previous_total * 100:.2f}%"
                if previous_total else None
            )

            st.warning(
                "Directional comparison only. It uses current RFQ quantities "
                "for both periods and assumes comparable GST and freight "
                "treatment. The last-year file does not document those bases. "
                "This is not verified savings."
            )

        else:
            st.info(
                "Supported queries: quote coverage, cheapest compliant price, "
                "and last-year price comparison."
            )

    st.info(
    "Results are calculated from extracted supplier quotes, "
    "source evidence and configured eligibility checks. "
    "Unresolved evidence is not treated as verified."
    )

with tabs[3]:
    st.subheader("Award decision workspace")
    st.caption(
        "Evaluate line-level award eligibility and indicative spend "
        "before making a sourcing decision."
    )

    # Scenario control
    min_quality = st.slider(
        "Minimum supplier quality score",
        min_value=0,
        max_value=100,
        value=80,
        help="Illustrative demo scores, not verified supplier assessments."
    )

    quality = {"V1": 90, "V2": 82, "V3": 95, "V4": 78, "V5": 92}

    eligible_vendors = [
        vendor for vendor, score in quality.items()
        if score >= min_quality
    ]

    # Existing award logic
    eligible_quotes = award_eligible_quotes(quotes, eligible_vendors)
    coverage = award_coverage(eligible_quotes, lines)
    award = build_award(quotes, lines, eligible_vendors)

    awardable_count = int(coverage["awardable"].sum())
    total_lines = len(coverage)
    blocked_count = total_lines - awardable_count

    award_value = (
        award["extended_value"].sum()
        if not award.empty else 0
    )

    # Summary metrics
    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Eligible suppliers",
        len(eligible_vendors)
    )

    col2.metric(
        "Awardable RFQ lines",
        f"{awardable_count} / {total_lines}"
    )

    col3.metric(
        "Indicative award value",
        f"₹{award_value / 1e7:,.2f} Cr"
    )

    st.divider()

    # Supplier eligibility
    st.markdown("**Suppliers passing quality threshold**")

    if eligible_vendors:
        st.write(" · ".join(eligible_vendors))
    else:
        st.warning("No suppliers meet the selected quality threshold.")

    
    # Main decision table
    st.markdown("**Line-level award assessment**")

    display_coverage = coverage.copy()

    # Add the selected vendor and price from the existing award output
    if not award.empty:
        award_details = award[
            ["line_id", "vendor_id", "landed_pre_gst_inr_per_box"]
        ].drop_duplicates(subset=["line_id"])

        display_coverage = display_coverage.merge(
            award_details,
            on="line_id",
            how="left"
        )
    else:
        display_coverage["vendor_id"] = None
        display_coverage["landed_pre_gst_inr_per_box"] = None

    display_columns = [
        "line_id",
        "item_name",
        "qty",
        "vendor_id",
        "landed_pre_gst_inr_per_box",
        "eligible_vendor_count",
        "awardable"
    ]

    display_columns = [
        col for col in display_columns
        if col in display_coverage.columns
    ]

    st.dataframe(
        display_coverage[display_columns],
        width="stretch",
        hide_index=True,
        column_config={
            "vendor_id": st.column_config.TextColumn(
                "Selected vendor",
                help="Vendor selected by the existing award calculation."
            ),
            "landed_pre_gst_inr_per_box": st.column_config.NumberColumn(
                "Landed price / box (pre-GST)",
                format="₹%.2f"
            ),
            "eligible_vendor_count": st.column_config.NumberColumn(
                "Award-eligible quotes"
            ),
            "awardable": st.column_config.CheckboxColumn(
                "Awardable"
            )
        }
    )

    # Decision status
    if blocked_count:
        st.warning(
            f"{blocked_count} of {total_lines} RFQ lines do not currently "
            "have an award-eligible quote. Review the Human review queue "
            "before proceeding."
        )
    else:
        st.success(
            "All RFQ lines have at least one award-eligible quote. "
            "Complete final commercial and procurement approvals."
        )

    st.caption(
        "Indicative award value is pre-GST and includes stated freight. "
        "Supplier quality scores are illustrative demo inputs. "
        "Eligibility does not constitute an award recommendation or approval."
    )

with tabs[4]:
    st.subheader("Pre-award assurance")
    st.caption(
        "A consolidated view of quote coverage, unresolved evidence "
        "and buyer-configured assumptions."
    )

    # Core trust metrics
    unresolved = int((quotes.status == "needs_review").sum())
    canonical_lines = len(lines)
    supplier_count = quotes.vendor_id.nunique()
    total_quote_rows = len(quotes)

    quoted_total = int(quotes.quoted.sum())

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("RFQ line items", canonical_lines)
    col2.metric("Suppliers assessed", supplier_count)
    col3.metric("Quoted lines", f"{quoted_total} / {total_quote_rows}")
    col4.metric("Unresolved review cells", unresolved)

    st.divider()

    # Overall readiness
    st.markdown("**Award readiness**")

    if unresolved > 0:
        st.warning(
            f"{unresolved} quote cells still require review or source "
            "verification. Do not finalize an award until material "
            "blockers are resolved."
        )
    else:
        st.success(
            "No unresolved review cells detected. Complete final "
            "procurement and commercial approvals before award."
        )

    # Buyer-configured assumptions
    st.markdown("**Buyer-configured assumptions**")

    assumptions_display = pd.DataFrame([
        {
            "Assumption": "USD to INR exchange rate",
            "Current value": f"₹{float(fx):,.2f}",
            "Reference": f"Buyer-entered rate dated {fx_date}"
        },
        {
            "Assumption": "GST assumption",
            "Current value": f"{float(gst_rate):.2f}%",
            "Reference": "Buyer-configured; confirm applicability"
        }
    ])

    st.dataframe(
        assumptions_display,
        width="stretch",
        hide_index=True
    )

    st.caption(
        "These are modelling assumptions, not independently verified "
        "market rates or tax advice."
    )

    st.divider()

    # Supplier quote coverage
    st.markdown("**Supplier quote coverage**")

    if "quote_state" in quotes.columns:
        vendor_summary = (
            quotes.pivot_table(
                index="vendor_id",
                columns="quote_state",
                values="line_id",
                aggfunc="nunique",
                fill_value=0
            )
            .reset_index()
        )

        vendor_summary.columns.name = None

        for state in [
            "quoted",
            "supplier_no_quote",
            "needs_clarification",
            "extraction_failed"
        ]:
            if state not in vendor_summary.columns:
                vendor_summary[state] = 0

        vendor_summary = vendor_summary.rename(columns={
            "quoted": "Quoted lines",
            "supplier_no_quote": "Supplier no-quote",
            "needs_clarification": "Clarification required",
            "extraction_failed": "Extraction failed"
        })

        vendor_summary = vendor_summary[
            [
                "vendor_id",
                "Quoted lines",
                "Supplier no-quote",
                "Clarification required",
                "Extraction failed"
            ]
        ]

    else:
        vendor_summary = (
            quotes[quotes.quoted]
            .groupby("vendor_id")
            .line_id.nunique()
            .rename("Quoted lines")
            .reset_index()
        )

    st.dataframe(
        vendor_summary,
        width="stretch",
        hide_index=True
    )

    st.divider()

    # Safeguards
    st.markdown("**Pre-award safeguards**")

    safeguards = [
        "Specification deviations and unverified specifications must be reviewed.",
        "Missing quotes and clarification holds must not be treated as zero-priced offers.",
        "GST treatment and tax classification must be confirmed.",
        "Freight and other commercial terms must be verified before comparing landed costs.",
        "Buyer-configured FX and GST assumptions must be confirmed before award."
    ]

    for safeguard in safeguards:
        st.markdown(f"- {safeguard}")

    # Exports
    st.divider()
    st.markdown("**Export and audit trail**")

    st.download_button(
        "Export normalized quotes (CSV)",
        quotes.to_csv(index=False),
        "normalized_quotes.csv",
        "text/csv"
    )

    try:
        raw = st.session_state.get("raw", pd.DataFrame())
        review_register = build_review_register(quotes, raw, lines)
        eligible_quotes = award_eligible_quotes(quotes)
        award_coverage_df = award_coverage(eligible_quotes, lines)

        export_path = ROOT / "data/award_export.xlsx"

        with pd.ExcelWriter(export_path, engine="openpyxl") as writer:
            quotes.to_excel(
                writer, index=False, sheet_name="Normalized quotes"
            )
            lines.to_excel(
                writer, index=False, sheet_name="RFQ lines"
            )

            assumptions_df = pd.DataFrame(
                st.session_state["assumptions"]
            )

            model_assumptions = pd.DataFrame([
                {
                    "vendor_id": "BUYER",
                    "assumption": f"USD to INR FX rate: {fx}",
                    "terms_evidence": f"Buyer-configured FX rate dated {fx_date}",
                    "terms_confidence": "User-entered"
                },
                {
                    "vendor_id": "BUYER",
                    "assumption": f"GST assumption: {gst_rate}%",
                    "terms_evidence": "Buyer-configured GST assumption",
                    "terms_confidence": "User-entered"
                }
            ])

            assumptions_df = pd.concat(
                [assumptions_df, model_assumptions],
                ignore_index=True
            )

            assumptions_df.to_excel(
                writer, index=False, sheet_name="Assumptions"
            )
            eligible_quotes.to_excel(
                writer, index=False, sheet_name="Award eligible quotes"
            )
            award_coverage_df.to_excel(
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
    st.subheader("RFQ drafting workspace")
    st.caption(
        "Prepare consistent requests for quotation across suppliers. "
        "Review each draft before sending."
    )

    st.markdown("#### 1. Procurement requirements")

    scope = st.text_area(
        "Procurement scope",
        "Supply of corrugated packaging for FMCG distribution.",
        height=110,
        help="Describe the products or services being sourced."
    )

    terms = st.text_area(
        "Commercial requirements",
        "Quote per box; state GST, freight, MOQ, payment terms, "
        "validity and delivery lead time.",
        height=130,
        help="Specify the commercial information suppliers must disclose."
    )

    st.caption(
        "These requirements will be included in each supplier's RFQ draft."
    )

    st.divider()

    if st.button(
        "Generate 5 supplier-specific drafts",
        type="primary",
        use_container_width=False
    ):
        (ROOT / "outbox").mkdir(exist_ok=True)

        drafts = []

        for vendor in ["V1", "V2", "V3", "V4", "V5"]:
            subject = "RFQ – Corrugated Packaging"

            body = (
                f"{scope}\n\n"
                f"{terms}\n\n"
                "Please quote all 30 attached line items and "
                "disclose all deviations."
            )

            draft = (
                f"Subject: {subject}\n\n"
                f"{body}"
            )

            (ROOT / "outbox" / f"{vendor}_RFQ.txt").write_text(
                draft,
                encoding="utf-8"
            )

            drafts.append({
                "vendor": vendor,
                "subject": subject,
                "body": body,
                "full_text": draft
            })

        st.session_state["RFQ_drafts"] = drafts

        st.success(
            "Five supplier-specific drafts created successfully. "
            "No email was sent."
        )

    # Display generated drafts
    drafts = st.session_state.get("RFQ_drafts", [])

    if drafts:
        st.divider()
        st.markdown("#### 2. Review supplier drafts")

        st.caption(
            "Open each supplier draft to review its subject and message. "
            "Use the copy control to copy the draft."
        )

        for draft in drafts:
            with st.expander(
                f"Supplier {draft['vendor']} · RFQ draft",
                expanded=False
            ):
                st.markdown("**Email subject**")
                st.text(draft["subject"])

                st.markdown("**Email body**")
                st.code(draft["body"], language=None)

                st.caption(
                    f"Saved to outbox/{draft['vendor']}_RFQ.txt"
                )

        st.info(
            "All drafts are saved locally for review. "
            "No emails are sent automatically."
        )