# Phase 4 — Extraction/normalization integration

1. Apply this patch preserving the project folder structure.
2. Run:
```bash
python -m py_compile app.py extract/pipeline.py extract/integration.py normalize/core.py
python -m unittest discover -s tests -v
```
3. The app now calls `run_full_pipeline`, saves raw and normalized outputs separately, and retains extracted terms/evidence.
4. Run `streamlit run app.py`, click Run extraction + normalization only after all tests pass.
5. Inspect `data/raw_extractions.csv` and `data/normalized_quotes.csv`. Do not award while any line is needs_review or no_quote.
