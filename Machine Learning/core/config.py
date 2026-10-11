"""
config.py – Central configuration for the PHC Risk Prediction production pipeline.
All thresholds, paths, and feature names live here so every module stays in sync.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root & artifact paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent   # competition/
DATA_DIR = BASE_DIR / "Hackaton data files"

# Server-side CSV paths
FACILITIES_CSV         = DATA_DIR / "facilities.csv"
FACILITY_SERVICES_CSV  = DATA_DIR / "facility_services.csv"
MEDICINE_INVENTORY_CSV = DATA_DIR / "medicine_inventory.csv"
VACCINE_INVENTORY_CSV  = DATA_DIR / "vaccine_inventory.csv"

MODELS_DIR = BASE_DIR / "src" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_MED_PATH = MODELS_DIR / "clf_medicine.joblib"
MODEL_VAC_PATH = MODELS_DIR / "clf_vaccine.joblib"
IMPUTER_PATH   = MODELS_DIR / "feature_medians.json"

# ---------------------------------------------------------------------------
# Feature columns – MUST match training column order exactly
# ---------------------------------------------------------------------------

# Block 1: Baseline facility features (12 features)
BASE_FACILITY_COLS: list[str] = [
    "is_functional",
    "is_rural",
    "distance_to_lga_hq_km",
    "distance_to_major_road_km",
    "catchment_population",
    "number_of_beds",
    "total_health_workers",
    "has_electricity",
    "has_water",
    "has_storage_room",
    "has_refrigerator",
    "has_cold_chain",
]

# Block 2: Current month service metrics + 4-month rolling dynamics (5 features)
SERVICE_FEATURE_COLS: list[str] = [
    "outpatient_visits",          # Current month outpatient visits
    "service_disruption_days",    # Current month disruption days
    "service_readiness_score",    # Current month readiness score
    "disruption_days_sum_4m",     # Total disruption days in past 4 months
    "outpatient_visits_mean_4m",  # Mean outpatient visits across past 4 months
]

# Block 3: Medicine inventory – current state & 4-month dynamics (9 features)
MEDICINE_FEATURE_COLS: list[str] = [
    "med_at_risk_rate",            # Current fraction low / critical / stockout
    "med_days_stock_min",          # Min days of stock remaining across medicines
    "med_days_stock_mean",         # Mean days of stock remaining across medicines
    "med_stock_coverage_ratio",    # Mean(stock_level / max_stock_level)
    "med_essential_stockout_rate", # Current stockout rate in essential categories
    "med_restocked_last_4m_rate",  # Fraction of medicines restocked in last 4 months
    "med_days_since_restock_mean", # Mean days since last restock across medicines
    "med_avail_last_4m_mean",      # Mean essential medicine availability over past 4 months
    "med_avail_trend_4m",          # Current availability minus 4-month average (trend)
]

# Block 4: Vaccine inventory – current state & 4-month dynamics (9 features)
VACCINE_FEATURE_COLS: list[str] = [
    "vac_at_risk_rate",            # Current fraction low / critical / stockout
    "vac_days_stock_min",          # Min days of vaccine stock remaining
    "vac_days_stock_mean",         # Mean days of vaccine stock remaining
    "vac_cold_chain_uptime_mean",  # Mean cold-chain uptime % (quality of preservation)
    "vac_temperature_excursions",  # Total temperature excursions (spoilage risk)
    "vac_restocked_last_4m_rate",  # Fraction of vaccines restocked in last 4 months
    "vac_days_since_restock_mean", # Mean days since last restock across vaccines
    "vac_avail_last_4m_mean",      # Mean immunization service availability over past 4 months
    "vac_avail_trend_4m",          # Current availability minus 4-month average (trend)
]

# Combined ordered feature list used for model training and inference (35 features)
FEATURE_COLS: list[str] = (
    BASE_FACILITY_COLS
    + SERVICE_FEATURE_COLS
    + MEDICINE_FEATURE_COLS
    + VACCINE_FEATURE_COLS
)

# ---------------------------------------------------------------------------
# Risk label thresholds
# ---------------------------------------------------------------------------
MED_STOCKOUT_THRESHOLD: float = 0.25   # >= 25 % stockout → essential medicine shortage risk
VAC_STOCKOUT_THRESHOLD: float = 0.50   # >= 50 % stockout → critical vaccine shortage risk

# ---------------------------------------------------------------------------
# Columns requiring imputation fallback if missing
# ---------------------------------------------------------------------------
SERVICE_IMPUTE_COLS: list[str] = [
    "outpatient_visits",
    "service_disruption_days",
    "service_readiness_score",
    "disruption_days_sum_4m",
    "outpatient_visits_mean_4m",
]

# ---------------------------------------------------------------------------
# API settings
# ---------------------------------------------------------------------------
API_TITLE       = "PHC Supply Shortage Risk API"
API_DESCRIPTION = (
    "Production inference API for predicting Essential Medicine and "
    "Critical Vaccine shortage risk using current inventory snapshots and 4-month history."
)
API_VERSION = "2.0.0"
API_HOST    = "0.0.0.0"
API_PORT    = 8000
