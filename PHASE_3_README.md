# Phase 3 — Real vendor extraction

## Apply patch
Unzip the Phase 3 patch into the project root, preserving folder paths.

## Set environment
```bash
export GROQ_API_KEY='your-key'
export OPENAI_API_KEY="$GROQ_API_KEY"
export OPENAI_BASE_URL="https://api.groq.com/openai/v1"
export OPENAI_MODEL="openai/gpt-oss-120b"
export GROQ_VISION_MODEL="qwen/qwen3.8-27b"
```

## First smoke test
```bash
python -m py_compile extract/pipeline.py normalize/core.py app.py
```

The extractor returns raw quoted prices, commercial terms, evidence, and missing cells.
It does NOT silently convert prices. Next integration step will map extracted terms and rows into
`Quote` and `VendorTerms` objects and call `normalize_all`.

## Synthetic document correction
The initial synthetic V1/V2/V4 files omitted some terms that existed in the hidden benchmark.
This patch adds buyer-visible terms to vendor-facing artifacts:
- V1 workbook Commercial Terms sheet
- V2 PDF commercial terms addendum including INR 1.20/box freight
- V4 separate commercial terms attachment including INR 1.50/box freight
- V3 Word commercial terms line
V5 freight remains intentionally unpriced and should trigger clarification.
