"""Run only in evaluation context. Never import this module from the app."""
from pathlib import Path
import subprocess, sys, tempfile
import pandas as pd

PROJECT=Path(__file__).resolve().parents[1]
def generate_truth():
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); (td/"data").mkdir(); (td/"ground_truth").mkdir()
        script=PROJECT/"evaluation/ground_truth_generator.py"
        subprocess.run([sys.executable,str(script)],cwd=td,check=True,capture_output=True,text=True)
        return pd.read_csv(td/"ground_truth/ground_truth_prices.csv")

def score(normalized_csv):
    pred=pd.read_csv(normalized_csv)
    truth=generate_truth()
    merged=pred.merge(truth[["vendor_id","line_id","quoted","true_inr_per_box_net"]],
                      on=["vendor_id","line_id"],suffixes=("_pred","_truth"),how="outer")
    actual=merged[(merged.quoted_truth==True)&merged.net_inr_per_box.notna()].copy()
    actual["abs_pct_error"]=((actual.net_inr_per_box-actual.true_inr_per_box_net).abs()/actual.true_inr_per_box_net)*100
    exact=actual.abs_pct_error.le(0.01).mean()*100 if len(actual) else 0
    report=actual.groupby("vendor_id").agg(
        evaluated_quotes=("line_id","count"),
        mean_absolute_pct_error=("abs_pct_error","mean"),
        within_1pct=("abs_pct_error",lambda s:(s<=1).mean()*100)
    ).round(2)
    print("IMPORTANT: benchmark ground truth is used only in this script.")
    print(f"Evaluated cells: {len(actual)}")
    print(f"Within 0.01% tolerance: {exact:.2f}%")
    print(report.to_string())
    return report

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--normalized",default="data/normalized_quotes.csv")
    args=p.parse_args()
    score(PROJECT/args.normalized)
