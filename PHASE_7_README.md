# Phase 7 — Deterministic extraction and explicit quote states

## Fixes

- V3's DOCX schedule is parsed directly from its 30 explicit `Lxx | description | INR ... per 1000 pcs` paragraphs. Its commercial terms are parsed from the same document; this avoids an LLM truncating a complete schedule.
- V4's JPG rate card is OCR'd as a whole. The parser accepts the OCR result only when all 27 price-bearing rows declared by the vendor's terms addendum are found. The printed line IDs are sometimes misread by OCR, so IDs are mapped by sequential row order only after the full 27-row check succeeds. If OCR is incomplete, the existing vision-model crop fallback runs; it does not fabricate missing prices.
- V3, V4, and V5 commercial terms are parsed from their vendor documents, rather than inferred by the LLM.
- Missing cells now carry a separate `quote_state`: `extraction_failed`, `needs_clarification`, or `supplier_no_quote`. A missing extraction is not silently represented as a supplier no-bid.
- The review queue surfaces missing/held cells and prevents a user from confirming a blank cell as a price.

## V4 OCR dependency

Python dependency: `pytesseract`. macOS system dependency:

```bash
brew install tesseract
pip install -r requirements.txt
```

If Tesseract is unavailable or OCR does not recover exactly 27 price rows, the app falls back to the vision model. Any remaining gaps stay explicitly unresolved.

## Validation

```bash
python -m py_compile app.py extract/pipeline.py extract/structured.py extract/integration.py quality/specs.py
python -m unittest discover -s tests -v
```

The V4 test is skipped when the Tesseract binary is not installed. The app should be rerun to regenerate extraction outputs; generated CSV/JSON/XLSX files should not be committed.

## Limits retained intentionally

- V2's supplier PDF does not disclose ply/BF, so these remain unverified, not assumed mismatches.
- V5 freight amount remains unknown and blocks landed-cost ranking. Per-kg applicability to die-cut/printed lines remains a clarification item.
- V4's 27 extracted rates are OCR-derived and must be checked against the source image before award; extraction completeness is not the same as specification compliance.
- No hidden ground-truth data is imported or used by inference code.
