import unittest
import pandas as pd
from extract.integration import build_vendor_terms, raw_frame_to_quotes

class TestIntegration(unittest.TestCase):
    def test_terms_mapping(self):
        t=build_vendor_terms({"V2":{"currency":"USD","gst_treatment":"extra","discount_pct":5,
            "freight_treatment":"extra_known","freight_inr_per_box":1.2,"moq_pcs":0}})
        self.assertEqual(t["V2"].discount_pct,5)
        self.assertEqual(t["V2"].freight_treatment,"extra_known")
        self.assertAlmostEqual(t["V2"].freight_inr_per_box,1.2)
    def test_unknown_freight_stays_unknown(self):
        t=build_vendor_terms({"V5":{"currency":"INR","gst_treatment":"extra","freight_treatment":"extra_unknown"}})
        self.assertEqual(t["V5"].freight_treatment,"extra_unknown")
    def test_raw_quote_conversion(self):
        df=pd.DataFrame([{"vendor_id":"V1","line_id":"L01","quoted":True,
            "quoted_price_as_stated":123,"quoted_unit":"INR/BOX","currency":"INR","confidence":.95,
            "source_file":"a.xlsx","source_snippet":"123 per box","spec_deviation":"","assumptions":""}])
        q=raw_frame_to_quotes(df)
        self.assertEqual(len(q),1)
        self.assertEqual(q[0].quoted_price,123)
    def test_unquoted_rows_not_converted(self):
        df=pd.DataFrame([{"vendor_id":"V4","line_id":"L30","quoted":False,
            "quoted_price_as_stated":None}])
        self.assertEqual(raw_frame_to_quotes(df),[])

if __name__=="__main__": unittest.main()
