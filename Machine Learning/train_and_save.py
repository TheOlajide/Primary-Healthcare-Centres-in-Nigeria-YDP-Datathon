"""
train_and_save.py – Training pipeline for PHC Shortage Risk Prediction models.

Trains two production-grade Random Forest models using 35 features:
  - 12 baseline facility infrastructure features
  - 5 current and 4-month operational disruption / workload features
  - 9 current and 4-month medicine inventory dynamics features
  - 9 current and 4-month vaccine inventory dynamics features

Outputs
-------
src/models/clf_medicine.joblib   – Essential Medicine Shortage Classifier
src/models/clf_vaccine.joblib    – Critical Vaccine Shortage Classifier
src/models/feature_medians.json  – Training medians for imputation fallback
"""

import json
import logging
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import (
    BASE_FACILITY_COLS,
    FACILITIES_CSV,
    FACILITY_SERVICES_CSV,
    FEATURE_COLS,
    IMPUTER_PATH,
    MED_STOCKOUT_THRESHOLD,
    MEDICINE_FEATURE_COLS,
    MEDICINE_INVENTORY_CSV,
    MODEL_MED_PATH,
    MODEL_VAC_PATH,
    SERVICE_FEATURE_COLS,
    VACCINE_FEATURE_COLS,
    VACCINE_INVENTORY_CSV,
    VAC_STOCKOUT_THRESHOLD,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

ESSENTIAL_MEDICINE_CATEGORIES = frozenset({
    "Antibiotic",
    "Antibiotic/Antiprotozoal",
    "Antimalarial",
    "Antimalarial (IPTp)",
    "Maternal health",
    "Analgesic/Antipyretic",
    "Emergency",
})


def build_full_dataset() -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Loads CSVs and computes all 35 feature columns and both binary risk targets."""
    logger.info("=" * 70)
    logger.info("BUILDING 35-FEATURE TRAINING DATASET WITH 4-MONTH DYNAMICS")
    logger.info("=" * 70)
    t0 = time.perf_counter()

    # 1. Facilities
    logger.info("1/4 Loading facilities.csv …")
    fac = pd.read_csv(FACILITIES_CSV)
    fac["is_functional"] = (fac["operational_status"] == "Functional").astype(float)
    fac["is_rural"] = (fac["urban_rural_class"] == "Rural").astype(float)
    for col in ["has_electricity", "has_water", "has_storage_room", "has_refrigerator", "has_cold_chain"]:
        fac[col] = fac[col].astype(float)

    fac_df = fac[["facility_id"] + BASE_FACILITY_COLS].copy()

    # 2. Services & 4-month history
    logger.info("2/4 Loading facility_services.csv & calculating 4-month rolling trends …")
    svc = pd.read_csv(FACILITY_SERVICES_CSV, usecols=[
        "facility_id", "record_date", "essential_medicine_availability",
        "immunization_service_availability", "outpatient_visits",
        "service_disruption_days", "service_readiness_score"
    ])
    latest_date = str(svc["record_date"].max())
    all_dates = sorted(svc["record_date"].unique())
    latest_idx = all_dates.index(latest_date) if latest_date in all_dates else len(all_dates) - 1
    prior_4_dates = all_dates[max(0, latest_idx - 4):latest_idx]

    svc_cur = svc[svc["record_date"] == latest_date].set_index("facility_id")
    svc_prev = svc[svc["record_date"].isin(prior_4_dates)]

    prev_agg = svc_prev.groupby("facility_id").agg(
        med_avail_last_4m_mean=("essential_medicine_availability", "mean"),
        vac_avail_last_4m_mean=("immunization_service_availability", "mean"),
        disruption_days_sum_4m=("service_disruption_days", "sum"),
        outpatient_visits_mean_4m=("outpatient_visits", "mean"),
    )

    svc_feats = svc_cur.join(prev_agg)
    svc_feats["med_avail_trend_4m"] = (
        svc_feats["essential_medicine_availability"] - svc_feats["med_avail_last_4m_mean"]
    )
    svc_feats["vac_avail_trend_4m"] = (
        svc_feats["immunization_service_availability"] - svc_feats["vac_avail_last_4m_mean"]
    )
    svc_df = svc_feats.reset_index()

    # 3. Medicine inventory (current state & 4-month restock)
    logger.info("3/4 Loading medicine_inventory.csv & computing current + 4m restock metrics …")
    med = pd.read_csv(MEDICINE_INVENTORY_CSV)
    ref_dt = pd.to_datetime(latest_date)

    med["restock_dt"] = pd.to_datetime(med["last_restock_date"], format="%d/%m/%Y", errors="coerce")
    med["days_since_restock"] = (ref_dt - med["restock_dt"]).dt.days
    med["restocked_last_4m"] = (med["days_since_restock"] <= 120).astype(float)
    med["is_stockout"] = (med["stock_status"] == "Stockout").astype(float)
    med["is_at_risk"] = (med["stock_status"].isin(["Stockout", "Low Stock", "Critical"])).astype(float)
    med["coverage"] = (
        pd.to_numeric(med["stock_level"], errors="coerce")
        / pd.to_numeric(med["maximum_stock_level"], errors="coerce").replace(0, np.nan)
    ).clip(upper=1.0)

    med["is_essential"] = med["medicine_category"].isin(ESSENTIAL_MEDICINE_CATEGORIES)
    med["essential_stockout"] = np.where(med["is_essential"], med["is_stockout"], np.nan)

    med_agg = med.groupby("facility_id").agg(
        med_stockout_rate=("is_stockout", "mean"),
        med_at_risk_rate=("is_at_risk", "mean"),
        med_days_stock_min=("days_of_stock_remaining", "min"),
        med_days_stock_mean=("days_of_stock_remaining", "mean"),
        med_stock_coverage_ratio=("coverage", "mean"),
        med_essential_stockout_rate=("essential_stockout", "mean"),
        med_restocked_last_4m_rate=("restocked_last_4m", "mean"),
        med_days_since_restock_mean=("days_since_restock", "mean"),
    ).reset_index()

    # 4. Vaccine inventory (current state & 4-month restock + cold chain)
    logger.info("4/4 Loading vaccine_inventory.csv & computing current + 4m cold-chain metrics …")
    vac = pd.read_csv(VACCINE_INVENTORY_CSV)

    vac["restock_dt"] = pd.to_datetime(vac["last_restock_date"], format="%d/%m/%Y", errors="coerce")
    vac["days_since_restock"] = (ref_dt - vac["restock_dt"]).dt.days
    vac["restocked_last_4m"] = (vac["days_since_restock"] <= 120).astype(float)
    vac["is_stockout"] = (vac["stock_status"] == "Stockout").astype(float)
    vac["is_at_risk"] = (vac["stock_status"].isin(["Stockout", "Low Stock", "Critical"])).astype(float)

    vac_agg = vac.groupby("facility_id").agg(
        vac_stockout_rate=("is_stockout", "mean"),
        vac_at_risk_rate=("is_at_risk", "mean"),
        vac_days_stock_min=("days_of_stock_remaining", "min"),
        vac_days_stock_mean=("days_of_stock_remaining", "mean"),
        vac_cold_chain_uptime_mean=("cold_chain_uptime_pct", "mean"),
        vac_temperature_excursions=("temperature_excursion_count", "sum"),
        vac_restocked_last_4m_rate=("restocked_last_4m", "mean"),
        vac_days_since_restock_mean=("days_since_restock", "mean"),
    ).reset_index()

    # Labels
    med_label = (med_agg.set_index("facility_id")["med_stockout_rate"] >= MED_STOCKOUT_THRESHOLD).astype(int).rename("risk_essential_medicine")
    vac_label = (vac_agg.set_index("facility_id")["vac_stockout_rate"] >= VAC_STOCKOUT_THRESHOLD).astype(int).rename("risk_critical_supply")

    # Merge into training dataset
    df = fac_df.merge(svc_df, on="facility_id", how="left")
    df = df.merge(med_agg, on="facility_id", how="left")
    df = df.merge(vac_agg, on="facility_id", how="left")

    logger.info("Dataset merged in %.2fs: %d rows × %d columns", time.perf_counter() - t0, len(df), df.shape[1])
    return df, med_label, vac_label


def train_eval_save(
    df: pd.DataFrame,
    y: pd.Series,
    target_name: str,
    model_save_path: Path,
) -> RandomForestClassifier:
    """Trains a Random Forest classifier, logs performance metrics, and persists to disk."""
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING: %s", target_name.upper())
    logger.info("=" * 70)

    # Align features and target
    valid_mask = ~y.isna()
    sub_df = df.loc[df["facility_id"].isin(y[valid_mask].index)].copy()
    y_aligned = y.loc[sub_df["facility_id"]].values

    X = sub_df[FEATURE_COLS]

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y_aligned, test_size=0.20, random_state=42, stratify=y_aligned
    )

    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=12,
        min_samples_split=4,
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_tr, y_tr)

    prob = clf.predict_proba(X_te)[:, 1]
    pred = clf.predict(X_te)
    auc = roc_auc_score(y_te, prob)

    logger.info("ROC-AUC Score: %.4f", auc)
    logger.info(
        "\n%s",
        classification_report(
            y_te, pred,
            target_names=[f"Adequate ({target_name}=0)", f"At Risk ({target_name}=1)"],
        )
    )

    imp = pd.Series(clf.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
    logger.info("Top 8 most predictive features:\n%s", imp.head(8).to_string())

    joblib.dump(clf, model_save_path)
    logger.info("Model artefact saved → %s", model_save_path)
    return clf


def main() -> None:
    t_start = time.perf_counter()

    df, med_label, vac_label = build_full_dataset()

    # Calculate training medians across all 35 features
    medians: dict[str, float] = {}
    for col in FEATURE_COLS:
        med_val = float(df[col].median(skipna=True))
        medians[col] = med_val
        df[col] = df[col].fillna(med_val)

    IMPUTER_PATH.write_text(json.dumps(medians, indent=2))
    logger.info("Feature imputation medians saved → %s (%d features)", IMPUTER_PATH, len(medians))

    # Train Model A
    train_eval_save(df, med_label, "risk_essential_medicine", MODEL_MED_PATH)

    # Train Model B
    train_eval_save(df, vac_label, "risk_critical_supply", MODEL_VAC_PATH)

    logger.info("\nTraining completed successfully in %d seconds.", int(time.perf_counter() - t_start))


if __name__ == "__main__":
    main()
