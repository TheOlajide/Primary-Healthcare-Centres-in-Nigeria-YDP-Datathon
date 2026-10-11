"""
features.py – Feature Engineering and Feature Vector Assembly.

Builds the complete 35-feature vector for inference:
  - 12 baseline facility infrastructure features
  - 5 service & 4-month disruption/volume features
  - 9 medicine inventory & 4-month dynamic features
  - 9 vaccine inventory & 4-month dynamic features
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from src.core.config import (
    BASE_FACILITY_COLS,
    FEATURE_COLS,
    MEDICINE_FEATURE_COLS,
    SERVICE_FEATURE_COLS,
    SERVICE_IMPUTE_COLS,
    VACCINE_FEATURE_COLS,
)

logger = logging.getLogger(__name__)


def _to_int_flag(value: Any) -> int:
    """Safely convert boolean/string flag to 0 or 1."""
    if isinstance(value, (bool, np.bool_)):
        return int(value)
    if isinstance(value, str):
        return 1 if value.strip().lower() in {"true", "yes", "1", "functional", "rural"} else 0
    return int(bool(value))


def build_facility_features(facility: dict[str, Any]) -> dict[str, float]:
    """Extract and encode the 12 static baseline features from a facility record."""
    return {
        "is_functional": float(_to_int_flag(
            facility.get("operational_status", "") == "Functional"
            if isinstance(facility.get("operational_status"), str)
            else facility.get("operational_status", 1)
        )),
        "is_rural": float(_to_int_flag(
            facility.get("urban_rural_class", "") == "Rural"
            if isinstance(facility.get("urban_rural_class"), str)
            else facility.get("urban_rural_class", 0)
        )),
        "distance_to_lga_hq_km":     float(facility.get("distance_to_lga_hq_km", 0.0)),
        "distance_to_major_road_km":  float(facility.get("distance_to_major_road_km", 0.0)),
        "catchment_population":       float(facility.get("catchment_population", 0.0)),
        "number_of_beds":             float(facility.get("number_of_beds", 0.0)),
        "total_health_workers":       float(facility.get("total_health_workers", 0.0)),
        "has_electricity":            float(_to_int_flag(facility.get("has_electricity", 0))),
        "has_water":                  float(_to_int_flag(facility.get("has_water", 0))),
        "has_storage_room":           float(_to_int_flag(facility.get("has_storage_room", 0))),
        "has_refrigerator":           float(_to_int_flag(facility.get("has_refrigerator", 0))),
        "has_cold_chain":             float(_to_int_flag(facility.get("has_cold_chain", 0))),
    }


def build_service_features(
    service: dict[str, Any] | None,
    dynamic_feats: dict[str, float],
    medians: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    Extract current service metrics and 4-month disruption/volume history.
    Prioritizes explicit client service payload if provided, otherwise
    falls back to server-computed dynamic metrics, then training medians.
    """
    svc = service or {}
    fallback = medians or {}

    outpatient = svc.get("outpatient_visits")
    if outpatient is None:
        outpatient = dynamic_feats.get("outpatient_visits", fallback.get("outpatient_visits", 0.0))

    disruption = svc.get("service_disruption_days")
    if disruption is None:
        disruption = dynamic_feats.get("service_disruption_days", fallback.get("service_disruption_days", 0.0))

    readiness = svc.get("service_readiness_score")
    if readiness is None:
        readiness = dynamic_feats.get("service_readiness_score", fallback.get("service_readiness_score", 0.0))

    disruption_4m = dynamic_feats.get(
        "disruption_days_sum_4m", fallback.get("disruption_days_sum_4m", float(disruption))
    )
    visits_4m = dynamic_feats.get(
        "outpatient_visits_mean_4m", fallback.get("outpatient_visits_mean_4m", float(outpatient))
    )

    return {
        "outpatient_visits": float(outpatient),
        "service_disruption_days": float(disruption),
        "service_readiness_score": float(readiness),
        "disruption_days_sum_4m": float(disruption_4m),
        "outpatient_visits_mean_4m": float(visits_4m),
    }


def build_feature_row(
    facility: dict[str, Any],
    service: dict[str, Any] | None,
    dynamic_feats: dict[str, float],
    medians: dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    Combines facility, service, medicine, and vaccine features into a single-row
    DataFrame with columns matching FEATURE_COLS in exact order.
    """
    feats: dict[str, float] = {}

    # Block 1: Facility baseline (12)
    feats.update(build_facility_features(facility))

    # Block 2: Service & 4-month operational history (5)
    feats.update(build_service_features(service, dynamic_feats, medians))

    # Block 3: Medicine inventory & 4-month dynamics (9)
    for col in MEDICINE_FEATURE_COLS:
        val = dynamic_feats.get(col)
        if val is None or np.isnan(val):
            val = (medians or {}).get(col, 0.0)
        feats[col] = float(val)

    # Block 4: Vaccine inventory & 4-month dynamics (9)
    for col in VACCINE_FEATURE_COLS:
        val = dynamic_feats.get(col)
        if val is None or np.isnan(val):
            val = (medians or {}).get(col, 0.0)
        feats[col] = float(val)

    # Reorder according to FEATURE_COLS
    row = {col: feats.get(col, 0.0) for col in FEATURE_COLS}
    df = pd.DataFrame([row], columns=FEATURE_COLS)
    return df
