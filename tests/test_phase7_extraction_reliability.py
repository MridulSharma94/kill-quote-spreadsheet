import shutil
import unittest
from pathlib import Path
import pandas as pd

from extract.structured import (
    parse_v3_docx, parse_v3_terms, parse_v4_image_ocr, parse_v4_terms,
    parse_v5_email, parse_v5_terms,
)

ROOT = Path(__file__).resolve().parents[1]
VENDORS = ROOT / "vendor_files"


class Phase7DeterministicExtractionTests(unittest.TestCase):
    def test_v3_docx_recovers_all_thirty_explicit_line_prices(self):
        rows = parse_v3_docx(VENDORS / "Anand_Box_V3.docx")
        self.assertEqual(len(rows), 30)
        self.assertEqual([r["line_id"] for r in rows], [f"L{i:02d}" for i in range(1, 31)])
        self.assertEqual(rows[0]["quoted_price"], 51722.0)
        self.assertEqual(rows[-1]["quoted_price"], 13541.0)
        terms = parse_v3_terms(VENDORS / "Anand_Box_V3.docx")
        self.assertEqual(terms["gst_treatment"], "inclusive")
        self.assertEqual(terms["gst_rate_in_quote"], 12.0)
        self.assertEqual(terms["freight_inr_per_box"], 0.90)

    @unittest.skipUnless(shutil.which("tesseract"), "Tesseract system binary is not installed")
    def test_v4_ocr_recovers_all_twenty_seven_rate_card_rows(self):
        rows = parse_v4_image_ocr(VENDORS / "Rajdhani_Pack_V4.jpg")
        self.assertEqual(len(rows), 27)
        self.assertEqual([r["line_id"] for r in rows], [f"L{i:02d}" for i in range(1, 28)])
        self.assertEqual(rows[4]["quoted_price"], 15.17)
        self.assertEqual(rows[-1]["quoted_price"], 6.46)
        terms = parse_v4_terms(VENDORS / "Rajdhani_Pack_V4_terms.txt")
        self.assertEqual(terms["freight_inr_per_box"], 1.50)

    def test_v5_held_lines_are_clarification_not_supplier_no_bid(self):
        lines = pd.read_csv(ROOT / "data" / "line_items.csv")
        last_year = pd.read_csv(ROOT / "data" / "last_year.csv")
        text = (VENDORS / "Eastern_Kraft_V5_email.txt").read_text()
        rows, held = parse_v5_email(text, lines, last_year)
        self.assertTrue(held)
        self.assertTrue(all("confirm" in note.lower() for note in held.values()))
        self.assertFalse(set(held).intersection(r["line_id"] for r in rows))
        terms = parse_v5_terms(text)
        self.assertEqual(terms["freight_treatment"], "extra_unknown")
        self.assertEqual(terms["payment_terms"], "45 days")


if __name__ == "__main__":
    unittest.main()
