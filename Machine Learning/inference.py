"""
inference.py – Production Inference Engine for PHC Shortage Risk Prediction.

Flow at inference time
----------------------
1. Client sends minimal payload with `facility_id` (e.g. 'PHC000001').
2. Server fetches baseline facility metadata (or uses client overrides).
3. Server queries InventoryDB for current state + 4-month dynamic trends.
4. Feature row is assembled into the exact 35 FEATURE_COLS order.
5. Classifiers predict probabilities for Essential Medicine and Vaccine Shortage.
6. Returns PredictionResponse with actionable transparency insights and alert level.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from src.core.config import (
    FEATURE_COLS,
    IMPUTER_PATH,
    MED_STOCKOUT_THRESHOLD,
    MODEL_MED_PATH,
    MODEL_VAC_PATH,
    VAC_STOCKOUT_THRESHOLD,
)
from src.features import build_feature_row
from src.inventory_db import inventory_db
from src.schemas import (
    InventoryInsight,
    MedicineInsight,
    PredictionRequest,
    PredictionResponse,
    RiskScore,
    ServiceHistoryInsight,
    VaccineInsight,
)

logger = logging.getLogger(__name__)


@dataclass
class ModelStore:
    clf_medicine: RandomForestClassifier | None = field(default=None, repr=False)
    clf_vaccine:  RandomForestClassifier | None = field(default=None, repr=False)
    medians:      dict[str, float] = field(default_factory=dict)
    _loaded:      bool = False

    def load(self) -> None:
        """Loads trained model artifacts and feature imputation medians from disk."""
        if self._loaded:
            return

        if not MODEL_MED_PATH.exists() or not MODEL_VAC_PATH.exists():
            raise FileNotFoundError(
                f"Model artefacts not found at {MODEL_MED_PATH} / {MODEL_VAC_PATH}. "
                "Run `python src/train_and_save.py` first."
            )

        self.clf_medicine = joblib.load(MODEL_MED_PATH)
        self.clf_vaccine  = joblib.load(MODEL_VAC_PATH)

        if IMPUTER_PATH.exists():
            self.medians = json.loads(IMPUTER_PATH.read_text())
            logger.info("Imputation medians loaded: %d features.", len(self.medians))
        else:
            logger.warning("feature_medians.json not found – using fallback defaults.")

        self._loaded = True
        logger.info(
            "ModelStore ready: %s, %s loaded.",
            type(self.clf_medicine).__name__, type(self.clf_vaccine).__name__
        )

    @property
    def is_ready(self) -> bool:
        return self._loaded and self.clf_medicine is not None and self.clf_vaccine is not None


model_store = ModelStore()


def _alert_level(med_flag: int, vac_flag: int) -> str:
    if med_flag == 1 and vac_flag == 1:
        return "HIGH"
    if med_flag == 1 or vac_flag == 1:
        return "MEDIUM"
    return "LOW"


def _risk_label(flag: int, prob: float) -> str:
    if flag == 1:
        return f"AT RISK ({prob:.0%} confidence)"
    return f"ADEQUATE ({(1 - prob):.0%} confidence)"


def predict(request: PredictionRequest) -> PredictionResponse:
    """
    Run risk inference for a single facility.
    Fetches required facility metadata and 4-month dynamic inventory metrics server-side.
    """
    if not model_store.is_ready:
        raise RuntimeError("Models not loaded. Call model_store.load() first.")
    if not inventory_db.is_ready:
        raise RuntimeError("InventoryDB not loaded. Call inventory_db.load() first.")

    facility_id = request.facility_id

    # 1. Resolve facility metadata (client override or server database)
    if request.facility is not None:
        fac_record = request.facility.model_dump(exclude_none=True)
    else:
        fac_record = inventory_db.get_facility_record(facility_id)

    # 2. Resolve service metrics
    svc_record = request.service.model_dump(exclude_none=True) if request.service is not None else None

    record_date = request.record_date or inventory_db.latest_record_date

    # 3. Fetch 4-month dynamic inventory and service metrics from database
    dynamic_feats = inventory_db.get_dynamic_features(facility_id, target_date=record_date)

    # 4. Build feature row
    X: pd.DataFrame = build_feature_row(
        facility=fac_record,
        service=svc_record,
        dynamic_feats=dynamic_feats,
        medians=model_store.medians,
    )

    feature_vector: dict[str, float] = X.iloc[0].to_dict()

    # 5. Predict probabilities and risk flags
    prob_med = float(model_store.clf_medicine.predict_proba(X)[0, 1])
    prob_vac = float(model_store.clf_vaccine.predict_proba(X)[0, 1])
    flag_med = int(prob_med >= MED_STOCKOUT_THRESHOLD)
    flag_vac = int(prob_vac >= VAC_STOCKOUT_THRESHOLD)

    # 6. Retrieve structured transparency insights
    insights_raw = inventory_db.get_transparency_insights(facility_id, target_date=record_date)
    inventory_insight = InventoryInsight(
        medicine=MedicineInsight(**insights_raw["medicine"]),
        vaccine=VaccineInsight(**insights_raw["vaccine"]),
        service_history_4m=ServiceHistoryInsight(**insights_raw["service_history_4m"]),
    )

    state_name = fac_record.get("state_name")
    record_date = request.record_date or inventory_db.latest_record_date

    return PredictionResponse(
        facility_id=facility_id,
        state_name=state_name,
        record_date=record_date,
        essential_medicine_risk=RiskScore(
            risk_flag=flag_med,
            risk_probability=round(prob_med, 4),
            risk_label=_risk_label(flag_med, prob_med),
        ),
        critical_vaccine_risk=RiskScore(
            risk_flag=flag_vac,
            risk_probability=round(prob_vac, 4),
            risk_label=_risk_label(flag_vac, prob_vac),
        ),
        inventory_insight=inventory_insight,
        feature_vector=feature_vector,
        alert_level=_alert_level(flag_med, flag_vac),
    )
