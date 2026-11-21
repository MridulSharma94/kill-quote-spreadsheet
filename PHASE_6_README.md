# Phase 6 — Extraction reliability and specification validation

This patch improves extraction where vendor files have stable structure and adds a deterministic RFQ-vs-vendor spec check.

## What changes

1. **V1 Excel:** reads the Commercial Offer table by header names and line IDs, independent of shuffled row order. This should recover all rows present in the workbook without relying on LLM table reading.
2. **V2 PDF:** parses explicit `Lxx ... USD n/box` lines from searchable PDF text. The parser preserves the quoted dimensions as source evidence.
3. **V4 image:** sends three overlapping, contrast-enhanced, enlarged horizontal crops to the vision model and merges duplicate line IDs by confidence. This is intended to improve coverage of the 27 visible rate-card rows.
4. **V5 email:** deterministically applies the stated INR/kg rates by ply and the explicit “same as last year” statement for 7-ply. Die-cut and printed lines are held for clarification, not called supplier no-bids.
5. **Specification validation:** dimensions, ply and BF are compared only when the vendor source discloses them. Explicit conflicts become `mismatch`; absent disclosure becomes `unverified`. Both require review. The system does not claim an undisclosed spec is a confirmed deviation.
6. **Audit trail:** held V5 lines carry an `extraction_note`; this is distinct from an ordinary missing quote.

No ground-truth generator or hidden benchmark values are imported by inference code.

## Apply

From the project root, with `.venv` active:

```bash
unzip -o ~/Downloads/kill_quote_phase6_patch.zip
cp kill_quote_spreadsheet/extract/pipeline.py extract/pipeline.py
cp kill_quote_spreadsheet/extract/structured.py extract/structured.py
cp kill_quote_spreadsheet/extract/integration.py extract/integration.py
cp kill_quote_spreadsheet/quality/specs.py quality/specs.py
cp kill_quote_spreadsheet/tests/test_phase6_extraction.py tests/test_phase6_extraction.py
cp kill_quote_spreadsheet/PHASE_6_README.md .
```

The patch requires Pillow for V4 image crops. If not already installed:

```bash
pip install Pillow
```

## Validate

```bash
python -m py_compile extract/pipeline.py extract/structured.py extract/integration.py quality/specs.py
python -m unittest discover -s tests -v
```

Expected: 21 tests pass (16 existing + 5 new). If V1 parser reports changed headers, stop and inspect the workbook rather than falling back to guessed columns.

## Run the app

Run Streamlit and click **Run extraction + normalization** again. This is important: old CSVs remain unchanged until a fresh extraction is run.

After rerun, inspect:
- V1 should approach 30/30 extracted rows (subject to source table contents).
- V2 should parse 30/30 explicit price rows. L30's 450x300x12 vs RFQ 450x300x120 should be flagged as a dimension mismatch.
- V4 should improve beyond the prior 16/30; the source image visibly contains L01–L27. If any remain missing, inspect the crop evidence and do not invent prices.
- V5 should retain 7-ply last-year references, hold die-cut/printed applicability lines for clarification, and preserve unknown freight as a blocker.

**Important:** V2's PDF does not disclose ply/BF details. Those attributes are therefore `unverified`, not confirmed deviations. Do not claim the benchmark's suspected BF/ply differences as source-proven unless another vendor-facing document explicitly states them.

## Commit after reviewing results

Do not commit regenerated CSV/JSON outputs. Once tests and the Streamlit run are reviewed:

```bash
git add extract/pipeline.py extract/structured.py extract/integration.py quality/specs.py tests/test_phase6_extraction.py PHASE_6_README.md
git commit -m "Improve vendor extraction and validate quote specifications"
git push
```
