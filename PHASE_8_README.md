# Phase 8 — OCR uncertainty and award audit trail

This patch is based on the supplied Phase 7 source archive.

## Changes
- Treat alphanumeric OCR dimensions (for example `g00x600x600`) as ambiguous evidence, not a confirmed specification mismatch.
- Require `spec_validation == verified` and `quote_state == quoted` in the reusable award eligibility gate.
- Surface extraction-failed, clarification-required, and supplier-no-quote states in the review queue.
- Add award-eligible quotes, line-level award coverage, and a review register to the Excel export.
- Preserve the existing app and pipeline architecture; no replacement app is introduced.

## Apply
Copy the included files into the matching project paths. Do not overwrite `.env`, generated data, or vendor source files.

Run:
`python -m py_compile app.py quality/specs.py quality/checks.py`
`python -m unittest tests.test_phase8_trust_gates -v`

The source archive did not include `vendor_files/`, so source-document integration tests cannot be rerun from this patch alone.
