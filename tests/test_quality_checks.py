import unittest
import pandas as pd
from quality.checks import extraction_completeness, award_eligible_quotes, award_coverage

class QualityChecksTests(unittest.TestCase):
    def setUp(self):
        self.lines = pd.DataFrame({"line_id":["L01","L02"],"item_name":["A","B"],"qty":[10,20]})

    def test_missing_extraction_is_reported_as_gap(self):
        raw = pd.DataFrame([{"vendor_id":"V1","line_id":"L01","quoted":True}])
        result = extraction_completeness(self.lines, raw, ["V1"])
        self.assertEqual(result.iloc[0].extracted_quotes, 1)
        self.assertIn("L02", result.iloc[0].unextracted_line_ids)
        self.assertIn("Extraction gap", result.iloc[0].interpretation)

    def test_award_gate_excludes_unknown_freight_and_deviation(self):
        q = pd.DataFrame([
            {"vendor_id":"V1","line_id":"L01","status":"accepted","quoted":True,"net_inr_per_box":10,"landed_pre_gst_inr_per_box":10,"freight_treatment":"included","spec_deviation":"","confidence":.99},
            {"vendor_id":"V2","line_id":"L01","status":"accepted","quoted":True,"net_inr_per_box":8,"landed_pre_gst_inr_per_box":None,"freight_treatment":"extra_unknown","spec_deviation":"","confidence":.99},
            {"vendor_id":"V3","line_id":"L01","status":"accepted","quoted":True,"net_inr_per_box":7,"landed_pre_gst_inr_per_box":7,"freight_treatment":"included","spec_deviation":"Wrong ply","confidence":.99},
        ])
        eligible = award_eligible_quotes(q)
        self.assertEqual(eligible.vendor_id.tolist(), ["V1"])

    def test_coverage_shows_unawardable_lines(self):
        eligible = pd.DataFrame([{"vendor_id":"V1","line_id":"L01"}])
        result = award_coverage(eligible, self.lines)
        self.assertEqual(result.awardable.tolist(), [True, False])

if __name__ == "__main__": unittest.main()
