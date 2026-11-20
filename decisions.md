# Product decisions
- Canonical line IDs are the join key; vendor descriptions are never trusted as IDs without matching evidence.
- LLM extracts and classifies; Python performs unit, FX, GST, freight and award arithmetic.
- Missing quotes are represented as `no_quote`, never zero.
- Low confidence and spec deviations block automatic acceptance.
- GST and FX are explicit, dated buyer assumptions.
- Quality scores are demo placeholders until questionnaire answers are ingested.
- Hidden ground truth is isolated under `evaluation/` and must never be available to inference code.
- Email is stubbed to `outbox/`; no messages are sent.
