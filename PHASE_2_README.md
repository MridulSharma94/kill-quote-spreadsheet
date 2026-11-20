# Phase 2 patch: normalization + evaluation foundation

## 1. Groq setup (macOS zsh)
```bash
export GROQ_API_KEY='YOUR_KEY'
python test_groq.py
```
Groq OpenAI-compatible endpoint: `https://api.groq.com/openai/v1`.
Use `openai/gpt-oss-120b` or another currently enabled model for text extraction. For image extraction, select a currently enabled vision model such as `qwen/qwen3.8-27b`; verify availability in your own account first.

## 2. Run deterministic unit tests
```bash
python -m unittest discover -s tests -v
```
Expected: 9 tests pass.

## 3. Important normalization contract
- `net_inr_per_box` is ex-GST and ex-freight.
- Freight is a separate field. Unknown freight makes landed cost unavailable and status `needs_review`.
- GST-inclusive vendor prices must be reversed using `gst_rate_in_quote`, not the buyer's current GST scenario.
- `no_quote` is explicit and never becomes zero.
- Specification deviations and low confidence block automatic acceptance.
- Buyer GST scenario is applied only by `landed_cost_including_gst`; actual tax treatment must be verified.

## 4. Benchmark evaluation
`evaluation/score_quotes.py` regenerates the hidden benchmark in a temporary directory and scores an already-normalized output. It does not run from the buyer-facing app. Do not import the scoring script or generator into extraction/normalization.

## 5. Known data-quality issue to discuss
The benchmark generator uses GST_RATE=12% for V3's GST-inclusive synthetic prices, while the product's buyer-facing tax assumption may be 5%. Preserve 12% only to reverse-engineer the synthetic quoted gross amount for benchmark comparability; do not treat that as current tax advice. Keep the buyer's current GST scenario separate and configurable.
