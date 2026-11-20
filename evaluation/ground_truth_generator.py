"""
Day 1, H1-2: build the canonical dataset + hidden ground truth.

Run from the project folder:   python data_gen/ground_truth.py

Creates:
  data/line_items.csv              -> the 30 lines in YOUR RFx (the AI may see this)
  data/last_year.csv               -> what the buyer paid last year (the AI may see this)
  ground_truth/vendors.csv         -> true terms of each vendor (HIDDEN from the AI)
  ground_truth/ground_truth_prices.csv -> true price per vendor per line (HIDDEN)

Rule: the AI never reads anything in ground_truth/. Only your scoring code does.
"""
import random
import pandas as pd

rng = random.Random(42)          # fixed seed -> same data every run. Do not change after freezing.

# ---------- Global config (change in ONE place) ----------
GST_RATE = 0.12                  # verify the current rate for HSN 4819 and update if needed
FX_INR_PER_USD = 88.0            # fixed demo rate, treat as "dated" in the UI
FX_DATE = "2026-11-20"
QTY_SCALE = 4                    # scales volumes so the award is ~Rs 4 crore, like the brief
RATE_PER_KG = {3: 38.0, 5: 42.0, 7: 46.0}      # market board rate, INR/kg, by ply
BOARD_GSM   = {3: 380, 5: 650, 7: 950}          # total board weight, g/m2
SPEC_TEXT   = {3: "3-ply, 150 GSM kraft, BF 18",
               5: "5-ply, 180 GSM kraft, BF 22",
               7: "7-ply, 200 GSM kraft, BF 25"}

# ---------- 1. The 30 canonical line items ----------
# (name, style, ply, L, W, H, qty, extra)   style: RSC / DIECUT / PARTITION / PAD
# extra: "" | "heavy" | "print2" | "print3"
ITEMS = [
 ("RSC Carton 600x400x400",           "RSC", 5, 600,400,400, 12000, ""),
 ("RSC Carton 500x350x350",           "RSC", 5, 500,350,350, 18000, ""),
 ("RSC Carton 450x300x300",           "RSC", 5, 450,300,300, 25000, ""),
 ("RSC Carton 400x300x250",           "RSC", 5, 400,300,250, 30000, ""),
 ("RSC Carton 350x250x200",           "RSC", 5, 350,250,200, 40000, ""),
 ("RSC Carton 300x200x150",           "RSC", 5, 300,200,150, 50000, ""),
 ("RSC Carton 550x380x320 Heavy Duty","RSC", 5, 550,380,320,  8000, "heavy"),
 ("RSC Carton 650x450x450",           "RSC", 5, 650,450,450,  6000, ""),
 ("RSC Carton 480x320x280",           "RSC", 5, 480,320,280, 14000, ""),
 ("RSC Carton 420x280x220",           "RSC", 5, 420,280,220, 22000, ""),
 ("RSC Carton 300x200x150",           "RSC", 3, 300,200,150, 60000, ""),
 ("RSC Carton 250x180x120",           "RSC", 3, 250,180,120, 70000, ""),
 ("RSC Carton 350x250x200",           "RSC", 3, 350,250,200, 35000, ""),
 ("RSC Carton 400x300x200",           "RSC", 3, 400,300,200, 28000, ""),
 ("RSC Carton 200x150x100",           "RSC", 3, 200,150,100, 80000, ""),
 ("RSC Carton 320x220x180",           "RSC", 3, 320,220,180, 45000, ""),
 ("RSC Carton 280x200x160",           "RSC", 3, 280,200,160, 52000, ""),
 ("RSC Carton 380x260x220",           "RSC", 3, 380,260,220, 20000, ""),
 ("Export RSC 700x500x500",           "RSC", 7, 700,500,500,  3000, ""),
 ("Export RSC 600x450x450",           "RSC", 7, 600,450,450,  4500, ""),
 ("Export RSC 800x600x600",           "RSC", 7, 800,600,600,  1500, ""),
 ("Export RSC 650x400x400",           "RSC", 7, 650,400,400,  3500, ""),
 ("Die-cut Mailer Box 320x240x80",    "DIECUT", 5, 320,240, 80, 25000, ""),
 ("Die-cut Mailer Box 280x200x60",    "DIECUT", 3, 280,200, 60, 40000, ""),
 ("Die-cut Tray with Lid 400x300x100","DIECUT", 5, 400,300,100, 10000, ""),
 ("Partition Set 12-cell 380x280",    "PARTITION", 3, 380,280, 0, 20000, ""),
 ("Corrugated Pad 600x400",           "PAD", 5, 600,400, 0, 50000, ""),
 ("Printed RSC 2-colour 450x300x300", "RSC", 5, 450,300,300, 10000, "print2"),
 ("Printed RSC 3-colour 500x350x350", "RSC", 5, 500,350,350,  8000, "print3"),
 ("Die-cut Retail Display Tray 450x300x120","DIECUT", 5, 450,300,120, 5000, ""),
]

def blank_area_m2(style, L, W, H):
    if style == "RSC":       return (2*(L+W)+50) * (H+W) / 1e6
    if style == "DIECUT":    return (L+2*H+30) * (W+2*H+30) / 1e6
    if style == "PARTITION": return L * W * 1.5 / 1e6
    return L * W / 1e6                                  # PAD

def premium(style, extra):
    p = 0.0
    if style == "DIECUT": p += 0.06                     # tooling / conversion
    if extra == "print2": p += 0.07
    if extra == "print3": p += 0.09
    if extra == "heavy":  p += 0.05
    return p

rows = []
for i, (name, style, ply, L, W, H, qty, extra) in enumerate(ITEMS, start=1):
    weight = round(blank_area_m2(style, L, W, H) * BOARD_GSM[ply] / 1000, 3)   # kg per box
    spec = SPEC_TEXT[ply] + (", heavy duty BF 28" if extra == "heavy" else "")
    if extra.startswith("print"): spec += f", {extra[-1]}-colour flexo print"
    rows.append(dict(line_id=f"L{i:02d}", item_name=name, style=style, ply=ply,
                     length_mm=L, width_mm=W, height_mm=H, spec=spec,
                     weight_kg_per_box=weight, qty=qty * QTY_SCALE, uom="pcs",
                     _premium=premium(style, extra)))
lines = pd.DataFrame(rows)
# market price per box = weight x kg rate x (1 + premium)
lines["_market"] = lines.apply(lambda r: r.weight_kg_per_box * RATE_PER_KG[r.ply] * (1 + r._premium), axis=1)

# ---------- 2. Last year's price (the incumbent is V5) ----------
lines["_last_year"] = lines["_market"].apply(lambda m: round(m * rng.uniform(0.94, 1.06), 2))
last_year = lines[["line_id", "_last_year"]].rename(columns={"_last_year": "last_year_price_inr_per_box"})
last_year["vendor"] = "V5 (incumbent)"

# ---------- 3. Vendors: true terms ----------
vendors = pd.DataFrame([
 dict(vendor_id="V1", vendor_name="Shree Ganesh Packaging",   file_format="xlsx",  currency="INR", quote_unit="per box",
      gst_treatment="extra", freight_terms="included", freight_inr_per_box=0.0, discount_pct=0.0,
      discount_location="", moq_pcs=8000, payment_terms="45 days", validity_days=30, price_factor=1.00, incumbent=False),
 dict(vendor_id="V2", vendor_name="Mekong Pack Industries (Vietnam)", file_format="pdf", currency="USD", quote_unit="per box",
      gst_treatment="extra", freight_terms="extra (stated)", freight_inr_per_box=1.20, discount_pct=5.0,
      discount_location="footnote", moq_pcs=0, payment_terms="30 days LC", validity_days=21, price_factor=0.93, incumbent=False),
 dict(vendor_id="V3", vendor_name="Anand Box Industries",     file_format="docx",  currency="INR", quote_unit="per 1000 pcs",
      gst_treatment="inclusive", freight_terms="extra (stated)", freight_inr_per_box=0.90, discount_pct=0.0,
      discount_location="", moq_pcs=0, payment_terms="60 days", validity_days=45, price_factor=1.03, incumbent=False),
 dict(vendor_id="V4", vendor_name="Rajdhani Pack Solutions",  file_format="jpg",   currency="INR", quote_unit="per box",
      gst_treatment="extra", freight_terms="extra (stated)", freight_inr_per_box=1.50, discount_pct=0.0,
      discount_location="", moq_pcs=0, payment_terms="30 days", validity_days=30, price_factor=0.97, incumbent=False),
 dict(vendor_id="V5", vendor_name="Eastern Kraft Mills",      file_format="email", currency="INR", quote_unit="per kg (3-ply, 5-ply); rest same as last year",
      gst_treatment="extra", freight_terms="extra (AMOUNT NOT STATED)", freight_inr_per_box=2.00, discount_pct=0.0,
      discount_location="", moq_pcs=0, payment_terms="45 days", validity_days=30, price_factor=1.00, incumbent=True),
])

# Traps: lines V4 does NOT quote (27 of 30), lines where V2 offers a cheaper alternate spec
V4_MISSING = {"L28", "L29", "L30"}                      # the printed + display lines
V2_SPEC_DEVIATION = {"L07": "Offered BF 22 instead of BF 28 (heavy duty)",
                     "L19": "Offered 5-ply instead of 7-ply",
                     "L20": "Offered 5-ply instead of 7-ply"}

# ---------- 4. Ground-truth prices ----------
# true_inr_per_box_net = INR per box, EXCLUDING GST, EXCLUDING freight, AFTER vendor discount.
# This is the number your normalization pipeline should arrive at.
gt = []
for _, r in lines.iterrows():
    for _, v in vendors.iterrows():
        vid = v.vendor_id
        rec = dict(vendor_id=vid, line_id=r.line_id, quoted=True, quoted_price_as_stated=None,
                   quoted_unit=None, currency=v.currency, true_inr_per_box_net=None, notes="")
        if vid == "V4" and r.line_id in V4_MISSING:
            rec.update(quoted=False, notes="not quoted")
            gt.append(rec); continue

        noise = rng.uniform(-0.02, 0.02)
        if vid == "V5":
            if r.ply in (3, 5):
                net = round(r.weight_kg_per_box * RATE_PER_KG[r.ply], 2)
                rec.update(quoted_price_as_stated=RATE_PER_KG[r.ply], quoted_unit="INR/kg")
                if r._premium > 0:
                    rec["notes"] = "email says 5-ply/3-ply rate; applies to die-cut/printed lines is an ambiguity"
            else:
                net = float(last_year.loc[last_year.line_id == r.line_id, "last_year_price_inr_per_box"].iloc[0])
                rec.update(quoted_price_as_stated=net, quoted_unit="same_as_last_year")
        else:
            f = v.price_factor
            if vid == "V2" and r.line_id in V2_SPEC_DEVIATION:
                f *= 0.88; rec["notes"] = "SPEC DEVIATION: " + V2_SPEC_DEVIATION[r.line_id]
            list_price = round(r._market * f * (1 + noise), 2)          # INR/box, ex-GST, before discount
            net = round(list_price * (1 - v.discount_pct / 100), 2)
            if vid == "V1":
                rec.update(quoted_price_as_stated=list_price, quoted_unit="INR/box")
                if r.qty < v.moq_pcs: rec["notes"] = f"qty {r.qty} is below vendor MOQ {v.moq_pcs}"
            elif vid == "V2":
                rec.update(quoted_price_as_stated=round(list_price / FX_INR_PER_USD, 3), quoted_unit="USD/box")
            elif vid == "V3":
                rec.update(quoted_price_as_stated=round(list_price * (1 + GST_RATE) * 1000), quoted_unit="INR/1000 pcs, GST incl.")
            elif vid == "V4":
                rec.update(quoted_price_as_stated=list_price, quoted_unit="INR/box")
        rec["true_inr_per_box_net"] = net
        gt.append(rec)
gt = pd.DataFrame(gt)

# ---------- 5. Save ----------
public_cols = ["line_id","item_name","style","ply","length_mm","width_mm","height_mm","spec","weight_kg_per_box","qty","uom"]
lines[public_cols].to_csv("data/line_items.csv", index=False)
last_year.to_csv("data/last_year.csv", index=False)
vendors.to_csv("ground_truth/vendors.csv", index=False)
gt.to_csv("ground_truth/ground_truth_prices.csv", index=False)

# ---------- 6. Sanity report ----------
q = gt.merge(lines[["line_id","qty"]], on="line_id")
q["value"] = q.true_inr_per_box_net * q.qty
print("Lines:", len(lines), "| total qty:", int(lines.qty.sum()))
print("\nCoverage + total net value (INR lakh, ex-GST, ex-freight) per vendor:")
print(q.groupby("vendor_id").agg(lines_quoted=("quoted","sum"), value_lakh=("value", lambda s: round(s.sum()/1e5,1))))
print("\nPrice range per box:", gt.true_inr_per_box_net.min(), "to", gt.true_inr_per_box_net.max())
print("Wrote data/ and ground_truth/")
