"""
run_inference.py – Primary CLI execution runner for PHC Supply Shortage Risk Prediction.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.inference import model_store, predict
from src.inventory_db import inventory_db
from src.schemas import BatchPredictionRequest, PredictionRequest

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def _print_formatted_report(res: dict) -> None:
    fid = res.get("facility_id", "N/A")
    state = res.get("state_name", "N/A")
    date = res.get("record_date", "N/A")
    alert = res.get("alert_level", "N/A")
    med_risk = res.get("essential_medicine_risk", {})
    vac_risk = res.get("critical_vaccine_risk", {})
    inv = res.get("inventory_insight", {})
    med_inv = inv.get("medicine", {})
    vac_inv = inv.get("vaccine", {})
    svc_hist = inv.get("service_history_4m", {})

    print("\n" + "=" * 76)
    print(f"=== PHC SHORTAGE RISK REPORT | Facility: {fid} ({state}) | Date: {date} ===")
    print("=" * 76)
    print(f"[ALERT LEVEL] {alert}")
    print("-" * 76)
    print("[1] ESSENTIAL MEDICINE RISK PREDICTION:")
    print(f"   * Status:      {med_risk.get('risk_label')}")
    print(f"   * Probability: {med_risk.get('risk_probability'):.1%} risk of essential medicine shortage")
    print("   * Supply Signals (Current State + Past 4 Months):")
    print(f"     - Current At-Risk Items:        {med_inv.get('at_risk_rate'):.1%} of medicines")
    print(f"     - Essential Stockout Rate:      {med_inv.get('essential_stockout_rate'):.1%}")
    print(f"     - Min Days of Stock Remaining:  {med_inv.get('min_days_stock_remaining')} days")
    print(f"     - Restocked in Last 4 Months:   {med_inv.get('restocked_in_last_4m_pct')}%")
    print(f"     - 4-Month Avg Availability:     {med_inv.get('availability_last_4m_avg')}/100 (trend: {med_inv.get('availability_trend_4m'):+0.2f})")

    print("\n[2] CRITICAL VACCINE RISK PREDICTION:")
    print(f"   * Status:      {vac_risk.get('risk_label')}")
    print(f"   * Probability: {vac_risk.get('risk_probability'):.1%} risk of critical vaccine shortage")
    print("   * Supply Signals (Current State + Past 4 Months):")
    print(f"     - Current At-Risk Vaccines:     {vac_inv.get('at_risk_rate'):.1%}")
    print(f"     - Min Days of Stock Remaining:  {vac_inv.get('min_days_stock_remaining')} days")
    print(f"     - Cold-Chain Uptime (90 days):  {vac_inv.get('cold_chain_uptime_pct')}%")
    print(f"     - Temperature Excursions:       {vac_inv.get('temperature_excursion_count')} events")
    print(f"     - Restocked in Last 4 Months:   {vac_inv.get('restocked_in_last_4m_pct')}%")
    print(f"     - 4-Month Avg Availability:     {vac_inv.get('availability_last_4m_avg')}/100 (trend: {vac_inv.get('availability_trend_4m'):+0.2f})")

    print("\n[3] OPERATIONAL DYNAMICS (PAST 4 MONTHS):")
    print(f"   * Average Monthly Outpatient Volume:  {svc_hist.get('outpatient_visits_4m_avg')} patients")
    print(f"   * Total Service Disruption Days:      {svc_hist.get('cumulative_disruption_days_4m')} days")
    print("=" * 76 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PHC Shortage Risk – Primary CLI Inference Runner"
    )
    parser.add_argument(
        "--facility-id", "-f", type=str, default=None,
        help="Primary execution: Facility ID (e.g., PHC000001). Resolves all inventory from database.",
    )
    parser.add_argument(
        "--record-date", "-d", type=str, default=None,
        help="Snapshot date for historical inference (e.g., 2025-12-31). Defaults to latest.",
    )
    parser.add_argument(
        "--input", "-i", type=Path, default=None,
        help="Path to a JSON file containing single or batch request payload.",
    )
    parser.add_argument(
        "--batch", "-b", action="store_true",
        help="Treat input as batch request ({'facilities': [...]})",
    )
    parser.add_argument(
        "--stdin", action="store_true",
        help="Read JSON from standard input.",
    )
    parser.add_argument(
        "--raw-json", action="store_true",
        help="Print raw JSON output instead of formatted summary report.",
    )
    args = parser.parse_args()

    # Startup & Database Load
    logger.info("Initializing models & server-side inventory database …")
    model_store.load()
    inventory_db.load()

    # Execution Mode
    if args.facility_id:
        req = PredictionRequest(facility_id=args.facility_id, record_date=args.record_date)
        res = predict(req).model_dump()
        if args.raw_json:
            print(json.dumps(res, indent=2, default=str))
        else:
            _print_formatted_report(res)
    elif args.input or args.stdin:
        if args.stdin:
            raw = sys.stdin.read()
        else:
            raw = args.input.read_text(encoding="utf-8")
        data = json.loads(raw)

        if args.batch:
            req_batch = BatchPredictionRequest.model_validate(data)
            results = [predict(item).model_dump() for item in req_batch.facilities]
            print(json.dumps({"total": len(results), "results": results}, indent=2, default=str))
        else:
            req = PredictionRequest.model_validate(data)
            res = predict(req).model_dump()
            if args.raw_json:
                print(json.dumps(res, indent=2, default=str))
            else:
                _print_formatted_report(res)
    else:
        # Default run with PHC000001 as primary demonstration
        print("No input specified. Executing primary test run with facility PHC000001:")
        req = PredictionRequest(facility_id="PHC000001")
        res = predict(req).model_dump()
        _print_formatted_report(res)


if __name__ == "__main__":
    main()
