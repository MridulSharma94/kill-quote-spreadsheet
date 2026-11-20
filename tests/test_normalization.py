import unittest
import pandas as pd
from normalize.core import Quote, VendorTerms, normalize_quote, landed_cost_including_gst

LINE=pd.Series({"line_id":"L01","qty":10000,"weight_kg_per_box":2.5})

class TestNormalization(unittest.TestCase):
    def test_inr_box(self):
        q=Quote("V1","L01",100,"INR/BOX","INR",.99)
        t=VendorTerms("V1",currency="INR",quote_unit="INR/BOX",gst_treatment="extra",freight_treatment="included")
        r=normalize_quote(q,LINE,t,88)
        self.assertAlmostEqual(r["net_inr_per_box"],100)
        self.assertEqual(r["status"],"accepted")
    def test_usd_and_discount(self):
        q=Quote("V2","L01",2,"USD/BOX","USD",.99)
        t=VendorTerms("V2",currency="USD",gst_treatment="extra",discount_pct=5,freight_treatment="included")
        r=normalize_quote(q,LINE,t,88)
        self.assertAlmostEqual(r["net_inr_per_box"],167.2)
    def test_per_thousand(self):
        q=Quote("V3","L01",112000,"INR/1000 PCS","INR",.99)
        t=VendorTerms("V3",gst_treatment="inclusive",gst_rate_in_quote=.12,freight_treatment="included")
        r=normalize_quote(q,LINE,t,88)
        self.assertAlmostEqual(r["net_inr_per_box"],100)
    def test_per_kg(self):
        q=Quote("V5","L01",42,"INR/KG","INR",.99)
        t=VendorTerms("V5",gst_treatment="extra",freight_treatment="included")
        r=normalize_quote(q,LINE,t,88)
        self.assertAlmostEqual(r["net_inr_per_box"],105)
    def test_missing_is_not_zero(self):
        q=Quote("V4","L01",None,None,None,quoted=False)
        t=VendorTerms("V4")
        r=normalize_quote(q,LINE,t,88)
        self.assertIsNone(r["net_inr_per_box"])
        self.assertEqual(r["status"],"no_quote")
    def test_freight_unknown_blocks_acceptance(self):
        q=Quote("V5","L01",42,"INR/KG","INR",.99)
        t=VendorTerms("V5",gst_treatment="extra",freight_treatment="extra_unknown")
        r=normalize_quote(q,LINE,t,88)
        self.assertEqual(r["status"],"needs_review")
        self.assertIsNone(r["landed_pre_gst_inr_per_box"])
    def test_spec_deviation_blocks_acceptance(self):
        q=Quote("V2","L01",100,"INR/BOX","INR",.99,spec_deviation="wrong ply")
        t=VendorTerms("V2",gst_treatment="extra",freight_treatment="included")
        r=normalize_quote(q,LINE,t,88)
        self.assertEqual(r["status"],"needs_review")
    def test_landed_cost(self):
        self.assertAlmostEqual(landed_cost_including_gst(100,10,.05),115.5)
    def test_invalid_discount(self):
        q=Quote("V1","L01",100,"INR/BOX","INR",.99)
        t=VendorTerms("V1",discount_pct=101)
        with self.assertRaises(ValueError): normalize_quote(q,LINE,t,88)

if __name__=="__main__": unittest.main()
