import unittest
import pandas as pd
from quality.specs import validate_quote_specs
from quality.checks import award_eligible_quotes

class Phase8TrustGateTests(unittest.TestCase):
    def test_ocr_confusable_dimension_is_unverified_not_mismatch(self):
        lines = pd.DataFrame([{"line_id":"L21","length_mm":800,"width_mm":600,"height_mm":600,"ply":7,"spec":"7-ply BF 25"}])
        raw = pd.DataFrame([{"vendor_id":"V4","line_id":"L21","source_snippet":"L21 Export RSC g00x600x600 Rs. 147.56"}])
        normalized = pd.DataFrame([{"vendor_id":"V4","line_id":"L21","quoted":True,"status":"accepted","spec_deviation":"","reasons":[]}])
        result = validate_quote_specs(normalized, raw, lines)
        self.assertEqual(result.loc[0,"spec_validation"], "unverified")
        self.assertEqual(result.loc[0,"status"], "needs_review")
        self.assertIn("OCR-ambiguous", result.loc[0,"reasons"][0])

    def test_award_gate_requires_verified_specs_and_known_quote_state(self):
        base = {"vendor_id":"V1","line_id":"L01","status":"accepted","quoted":True,
                "net_inr_per_box":10,"landed_pre_gst_inr_per_box":10,
                "freight_treatment":"included","spec_deviation":"","confidence":.99,
                "quote_state":"quoted"}
        q = pd.DataFrame([{**base,"spec_validation":"unverified"},
                          {**base,"line_id":"L02","spec_validation":"verified"},
                          {**base,"line_id":"L03","spec_validation":"verified","quote_state":"extraction_failed"}])
        eligible = award_eligible_quotes(q)
        self.assertEqual(eligible.line_id.tolist(), ["L02"])

if __name__ == "__main__":
    unittest.main()
