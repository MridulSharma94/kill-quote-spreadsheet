
# Kill the Quote Spreadsheet — prototype

## Run
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your model API key and endpoint
streamlit run app.py
```

## Important separation
- `data/line_items.csv` and `data/last_year.csv` are buyer-visible inputs.
- `evaluation/ground_truth_generator.py` is evaluation-only. Never import it from `app.py`, `extract/`, or `normalize/`.
- `vendor_files/` holds vendor responses.
- `outbox/` contains drafts only; SMTP is intentionally stubbed.

## Model configuration
Set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` for an OpenAI-compatible hosted model. Extraction is not fabricated: without credentials, the app explicitly reports that extraction has not run and does not create accepted prices.

## Prototype limitations to disclose
1. The starter extraction schema is a first pass. Vendor-specific commercial terms (discounts, freight, GST treatment, MOQ, payment and validity) require explicit term extraction and review before landed-cost award.
2. The award tab uses illustrative quality scores; replace these with questionnaire-derived scores.
3. GST defaults to 5% as a configurable scenario assumption for corrugated cartons under HSN 4819 10; validate exact classification and applicable notification with tax counsel.
4. USD conversion is a dated fixed-rate assumption, not a live FX feed.
5. `needs_review` cells must be resolved before award. Do not treat missing quotes as zero.
6. Never evaluate the model using files from `evaluation/` at inference time.

## Suggested demo
1. Run extraction and open the comparison.
2. Show missing lines and spec deviations.
3. Confirm a review item and show the assumptions ledger.
4. Run cheapest compliant award, then change the quality threshold.
5. Export the normalized workbook.
6. Explain why an apparently cheap non-equivalent offer is not awardable.
