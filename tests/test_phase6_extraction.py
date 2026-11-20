import tempfile
import unittest
from pathlib import Path
import pandas as pd

from extract.structured import parse_v1_xlsx, parse_v2_pdf_text, parse_v5_email
from quality.specs import validate_quote_specs


class StructuredExtractionTests(unittest.TestCase):
    def test_v2_pdf_parser_extracts_only_explicit_lines(self):
        rows = parse_v2_pdf_text("L01 RSC Carton 600x400x400 USD 0.478/box\nnoise")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["line_id"], "L01")
        self.assertAlmostEqual(rows[0]["quoted_price"], 0.478)
        self.assertEqual(rows[0]["unit"], "USD/BOX")

    def test_v1_xlsx_parser_uses_headers_and_line_ids(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "v1.xlsx"
            frame = pd.DataFrame([
                ["SHREE GANESH", None, None, None, None],
                ["Reference", "Product description", "Quoted rate", "Unit", "Remarks"],
                ["L02", "Carton", 12.5, "INR / box", "5-ply, BF 22"],
                ["Notes", "not a quote", None, None, None],
            ])
            with pd.ExcelWriter(p, engine="openpyxl") as w:
                frame.to_excel(w, sheet_name="Commercial Offer", header=False, index=False)
            rows = parse_v1_xlsx(p)
            self.assertEqual([r["line_id"] for r in rows], ["L02"])
            self.assertEqual(rows[0]["unit"], "INR/BOX")

    def test_v5_holds_diecut_and_printed_lines(self):
        lines = pd.DataFrame([
            {"line_id":"L01", "item_name":"RSC carton", "style":"RSC", "ply":5, "spec":"5-ply", "weight_kg_per_box":1},
            {"line_id":"L19", "item_name":"Export RSC", "style":"RSC", "ply":7, "spec":"7-ply", "weight_kg_per_box":2},
            {"line_id":"L23", "item_name":"Die-cut mailer", "style":"DIECUT", "ply":5, "spec":"5-ply", "weight_kg_per_box":1},
            {"line_id":"L28", "item_name":"Printed RSC", "style":"RSC", "ply":5, "spec":"5-ply printed", "weight_kg_per_box":1},
        ])
        last = pd.DataFrame({"line_id":["L19"], "last_year_inr_per_box":[111.06]})
        text = "INR 42/kg for 5-ply and INR 38/kg for 3-ply. For 7-ply items, retain the same prices as last year."
        rows, held = parse_v5_email(text, lines, last)
        self.assertEqual({r["line_id"] for r in rows}, {"L01", "L19"})
        self.assertEqual(rows[0]["unit"], "INR/KG")
        self.assertEqual(rows[1]["unit"], "SAME_AS_LAST_YEAR")
        self.assertIn("L23", held); self.assertIn("L28", held)


class SpecValidationTests(unittest.TestCase):
    def test_dimension_mismatch_is_flagged(self):
        lines = pd.DataFrame([{"line_id":"L30", "item_name":"Tray", "length_mm":450, "width_mm":300,
                               "height_mm":120, "ply":5, "spec":"5-ply, BF 22"}])
        raw = pd.DataFrame([{"vendor_id":"V2", "line_id":"L30", "quoted":True,
                             "source_snippet":"L30 Die-cut Retail Display Tray 450x300x12 USD 0.127/box"}])
        norm = pd.DataFrame([{"vendor_id":"V2", "line_id":"L30", "quoted":True, "status":"accepted",
                              "spec_deviation":"", "reasons":[], "confidence":.99}])
        result = validate_quote_specs(norm, raw, lines)
        self.assertEqual(result.iloc[0].spec_validation, "mismatch")
        self.assertEqual(result.iloc[0].status, "needs_review")
        self.assertIn("Dimensions", result.iloc[0].spec_deviation)

    def test_missing_spec_disclosure_is_unverified_not_mismatch(self):
        lines = pd.DataFrame([{"line_id":"L07", "item_name":"Heavy duty carton", "length_mm":550,
                               "width_mm":380, "height_mm":320, "ply":5, "spec":"5-ply, BF 28"}])
        raw = pd.DataFrame([{"vendor_id":"V2", "line_id":"L07", "quoted":True,
                             "source_snippet":"L07 RSC Carton 550x380x320 Heavy Duty USD 0.358/box"}])
        norm = pd.DataFrame([{"vendor_id":"V2", "line_id":"L07", "quoted":True, "status":"accepted",
                              "spec_deviation":"", "reasons":[], "confidence":.99}])
        result = validate_quote_specs(norm, raw, lines)
        self.assertEqual(result.iloc[0].spec_validation, "unverified")
        self.assertEqual(result.iloc[0].spec_deviation, "")
        self.assertEqual(result.iloc[0].status, "needs_review")


if __name__ == "__main__":
    unittest.main()
