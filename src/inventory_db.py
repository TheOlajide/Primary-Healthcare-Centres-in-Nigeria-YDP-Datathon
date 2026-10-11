"""
inventory_db.py – High-Performance Server-Side Inventory & Operations Engine.

Loads facilities.csv, facility_services.csv, medicine_inventory.csv, and
vaccine_inventory.csv once at startup. Computes:
  - Current state of the medicine inventory
  - 4-month dynamic restock & availability features for medicines
  - Current state of the vaccine inventory
  - 4-month dynamic restock, cold-chain & availability features for vaccines
  - 4-month operational disruption and patient volume trends

Supports both:
  1. Default latest snapshot lookups (pre-computed, ~1 microsecond)
  2. Any custom historical date requested by the client (computed dynamically for that facility)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.core.config import (
    FACILITIES_CSV,
    FACILITY_SERVICES_CSV,
    MEDICINE_INVENTORY_CSV,
    VACCINE_INVENTORY_CSV,
)

logger = logging.getLogger(__name__)

ESSENTIAL_MEDICINE_CATEGORIES: frozenset[str] = frozenset({
    "Antibiotic",
    "Antibiotic/Antiprotozoal",
    "Antimalarial",
    "Antimalarial (IPTp)",
    "Maternal health",
    "Analgesic/Antipyretic",
    "Emergency",
})


@dataclass
class InventoryDB:
    """
    High-performance in-memory database of facility baseline and dynamic inventory records.
    """
    _facilities_dict: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    _dynamic_features_dict: dict[str, dict[str, float]] = field(default_factory=dict, repr=False)
    _svc_df: pd.DataFrame = field(default_factory=pd.DataFrame, repr=False)
    _med_df: pd.DataFrame = field(default_factory=pd.DataFrame, repr=False)
    _vac_df: pd.DataFrame = field(default_factory=pd.DataFrame, repr=False)
    _latest_record_date: str = "2025-12-31"
    _loaded: bool = False

    def load(self) -> None:
        """Loads and precomputes all facility baseline and dynamic inventory features."""
        if self._loaded:
            return

        t0 = time.perf_counter()
        logger.info("Initializing server-side InventoryDB …")

        # 1. Baseline facility records
        logger.info("1/4 Loading facilities.csv …")
        fac = pd.read_csv(FACILITIES_CSV)
        self._facilities_dict = fac.set_index("facility_id").to_dict(orient="index")

        # 2. Monthly service records & 4-month trend aggregation
        logger.info("2/4 Loading facility_services.csv & computing 4-month trends …")
        svc = pd.read_csv(FACILITY_SERVICES_CSV, usecols=[
            "facility_id", "record_date", "essential_medicine_availability",
            "immunization_service_availability", "outpatient_visits",
            "service_disruption_days", "service_readiness_score"
        ])

        latest_date = str(svc["record_date"].max())
        self._latest_record_date = latest_date
        self._svc_df = svc.set_index("facility_id")

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

        # 3. Medicine inventory snapshot & 4-month restock recency
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
        )
        self._med_df = med.set_index("facility_id")

        # 4. Vaccine inventory snapshot & 4-month restock recency
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
        )
        self._vac_df = vac.set_index("facility_id")

        # Merge dynamic features table
        dynamic_df = svc_feats.join(med_agg, how="left").join(vac_agg, how="left")
        self._dynamic_features_dict = dynamic_df.to_dict(orient="index")

        self._loaded = True
        logger.info(
            "InventoryDB ready in %.2fs: %d facilities indexed.",
            time.perf_counter() - t0, len(self._facilities_dict),
        )

    @property
    def is_ready(self) -> bool:
        return self._loaded

    @property
    def facility_count(self) -> int:
        return len(self._facilities_dict)

    @property
    def medicine_facility_count(self) -> int:
        return len(self._dynamic_features_dict)

    @property
    def vaccine_facility_count(self) -> int:
        return len(self._dynamic_features_dict)

    @property
    def latest_record_date(self) -> str:
        return self._latest_record_date

    def get_facility_record(self, facility_id: str) -> dict[str, Any]:
        """Return baseline facility metadata dictionary from facilities.csv."""
        if not self._loaded:
            raise RuntimeError("InventoryDB not loaded. Call inventory_db.load() first.")
        rec = self._facilities_dict.get(facility_id)
        if not rec:
            raise KeyError(f"facility_id '{facility_id}' not found in facilities.csv")
        return rec

    def get_dynamic_features(
        self,
        facility_id: str,
        target_date: str | None = None,
    ) -> dict[str, float]:
        """
        Return all server-side inventory and 4-month dynamic features for facility_id.
        If target_date is omitted or matches latest snapshot, uses cached dictionary (~1us).
        If target_date is a custom past date, calculates exact 4-month metrics for that date.
        """
        if not self._loaded:
            raise RuntimeError("InventoryDB not loaded. Call inventory_db.load() first.")

        target = str(target_date) if target_date else self._latest_record_date

        # Fast path: latest snapshot is precomputed
        if target == self._latest_record_date:
            feats = self._dynamic_features_dict.get(facility_id)
            if not feats:
                logger.warning("facility_id '%s' not found in dynamic inventory records.", facility_id)
                return {}
            return feats

        # Dynamic path: custom historical date requested
        if facility_id not in self._svc_df.index:
            return self._dynamic_features_dict.get(facility_id, {})

        f_svc = self._svc_df.loc[[facility_id]].sort_values("record_date")
        f_svc_up_to_target = f_svc[f_svc["record_date"] <= target]
        if f_svc_up_to_target.empty:
            f_svc_up_to_target = f_svc.head(1)

        cur_svc = f_svc_up_to_target.iloc[-1]
        prior_svcs = f_svc_up_to_target.iloc[-5:-1] if len(f_svc_up_to_target) > 1 else f_svc_up_to_target.iloc[-1:]

        med_avail_prior = prior_svcs["essential_medicine_availability"].dropna()
        vac_avail_prior = prior_svcs["immunization_service_availability"].dropna()
        disruption_prior = prior_svcs["service_disruption_days"].dropna()
        visits_prior = prior_svcs["outpatient_visits"].dropna()

        cur_med_avail = float(cur_svc.get("essential_medicine_availability", 0.0))
        cur_vac_avail = float(cur_svc.get("immunization_service_availability", 0.0))

        med_avail_last_4m_mean = float(med_avail_prior.mean()) if not med_avail_prior.empty else cur_med_avail
        vac_avail_last_4m_mean = float(vac_avail_prior.mean()) if not vac_avail_prior.empty else cur_vac_avail

        ref_dt = pd.to_datetime(target)

        # Medicine metrics relative to target date
        if facility_id in self._med_df.index:
            med_f = self._med_df.loc[[facility_id]].copy()
            restock_dt = pd.to_datetime(med_f["last_restock_date"], format="%d/%m/%Y", errors="coerce")
            days_since = (ref_dt - restock_dt).dt.days
            restocked_4m = float((days_since <= 120).mean())
            mean_days_restock = float(days_since.mean(skipna=True))
            status = med_f["stock_status"].astype(str).str.strip()
            at_risk = float((status.isin(["Stockout", "Low Stock", "Critical"])).mean())
            days_stock = pd.to_numeric(med_f["days_of_stock_remaining"], errors="coerce")
            stock_lvl = pd.to_numeric(med_f["stock_level"], errors="coerce")
            max_lvl = pd.to_numeric(med_f["maximum_stock_level"], errors="coerce").replace(0, np.nan)
            coverage = float(((stock_lvl / max_lvl).clip(upper=1.0)).mean(skipna=True))
            is_essential = med_f["medicine_category"].isin(ESSENTIAL_MEDICINE_CATEGORIES)
            essential_so = float((status[is_essential] == "Stockout").mean()) if is_essential.any() else 0.0
            min_days_med = float(days_stock.min(skipna=True))
            mean_days_med = float(days_stock.mean(skipna=True))
        else:
            at_risk = 0.0; min_days_med = 0.0; mean_days_med = 0.0; coverage = 0.0
            essential_so = 0.0; restocked_4m = 0.0; mean_days_restock = 120.0

        # Vaccine metrics relative to target date
        if facility_id in self._vac_df.index:
            vac_f = self._vac_df.loc[[facility_id]].copy()
            restock_dt_v = pd.to_datetime(vac_f["last_restock_date"], format="%d/%m/%Y", errors="coerce")
            days_since_v = (ref_dt - restock_dt_v).dt.days
            restocked_4m_v = float((days_since_v <= 120).mean())
            mean_days_restock_v = float(days_since_v.mean(skipna=True))
            status_v = vac_f["stock_status"].astype(str).str.strip()
            at_risk_v = float((status_v.isin(["Stockout", "Low Stock", "Critical"])).mean())
            days_stock_v = pd.to_numeric(vac_f["days_of_stock_remaining"], errors="coerce")
            min_days_vac = float(days_stock_v.min(skipna=True))
            mean_days_vac = float(days_stock_v.mean(skipna=True))
            cold_uptime = float(pd.to_numeric(vac_f["cold_chain_uptime_pct"], errors="coerce").mean(skipna=True))
            temp_excursions = float(pd.to_numeric(vac_f["temperature_excursion_count"], errors="coerce").sum(skipna=True))
        else:
            at_risk_v = 0.0; min_days_vac = 0.0; mean_days_vac = 0.0; cold_uptime = 0.0
            temp_excursions = 0.0; restocked_4m_v = 0.0; mean_days_restock_v = 120.0

        return {
            "outpatient_visits": float(cur_svc.get("outpatient_visits", 0.0)),
            "service_disruption_days": float(cur_svc.get("service_disruption_days", 0.0)),
            "service_readiness_score": float(cur_svc.get("service_readiness_score", 0.0)),
            "disruption_days_sum_4m": float(disruption_prior.sum()) if not disruption_prior.empty else 0.0,
            "outpatient_visits_mean_4m": float(visits_prior.mean()) if not visits_prior.empty else 0.0,
            "med_avail_last_4m_mean": med_avail_last_4m_mean,
            "med_avail_trend_4m": cur_med_avail - med_avail_last_4m_mean,
            "vac_avail_last_4m_mean": vac_avail_last_4m_mean,
            "vac_avail_trend_4m": cur_vac_avail - vac_avail_last_4m_mean,
            "med_at_risk_rate": at_risk,
            "med_days_stock_min": min_days_med,
            "med_days_stock_mean": mean_days_med,
            "med_stock_coverage_ratio": coverage,
            "med_essential_stockout_rate": essential_so,
            "med_restocked_last_4m_rate": restocked_4m,
            "med_days_since_restock_mean": mean_days_restock,
            "vac_at_risk_rate": at_risk_v,
            "vac_days_stock_min": min_days_vac,
            "vac_days_stock_mean": mean_days_vac,
            "vac_cold_chain_uptime_mean": cold_uptime,
            "vac_temperature_excursions": temp_excursions,
            "vac_restocked_last_4m_rate": restocked_4m_v,
            "vac_days_since_restock_mean": mean_days_restock_v,
        }

    def get_transparency_insights(
        self,
        facility_id: str,
        target_date: str | None = None,
    ) -> dict[str, Any]:
        """Return human-readable transparency breakdown for API response and audit logs."""
        feats = self.get_dynamic_features(facility_id, target_date)
        return {
            "medicine": {
                "at_risk_rate": round(float(feats.get("med_at_risk_rate", 0.0)), 3),
                "essential_stockout_rate": round(float(feats.get("med_essential_stockout_rate", 0.0)), 3),
                "min_days_stock_remaining": round(float(feats.get("med_days_stock_min", 0.0)), 1),
                "mean_days_stock_remaining": round(float(feats.get("med_days_stock_mean", 0.0)), 1),
                "stock_coverage_ratio": round(float(feats.get("med_stock_coverage_ratio", 0.0)), 3),
                "restocked_in_last_4m_pct": round(float(feats.get("med_restocked_last_4m_rate", 0.0)) * 100, 1),
                "mean_days_since_last_restock": round(float(feats.get("med_days_since_restock_mean", 0.0)), 1),
                "availability_last_4m_avg": round(float(feats.get("med_avail_last_4m_mean", 0.0)), 1),
                "availability_trend_4m": round(float(feats.get("med_avail_trend_4m", 0.0)), 2),
            },
            "vaccine": {
                "at_risk_rate": round(float(feats.get("vac_at_risk_rate", 0.0)), 3),
                "min_days_stock_remaining": round(float(feats.get("vac_days_stock_min", 0.0)), 1),
                "mean_days_stock_remaining": round(float(feats.get("vac_days_stock_mean", 0.0)), 1),
                "cold_chain_uptime_pct": round(float(feats.get("vac_cold_chain_uptime_mean", 0.0)), 1),
                "temperature_excursion_count": int(feats.get("vac_temperature_excursions", 0.0)),
                "restocked_in_last_4m_pct": round(float(feats.get("vac_restocked_last_4m_rate", 0.0)) * 100, 1),
                "mean_days_since_last_restock": round(float(feats.get("vac_days_since_restock_mean", 0.0)), 1),
                "availability_last_4m_avg": round(float(feats.get("vac_avail_last_4m_mean", 0.0)), 1),
                "availability_trend_4m": round(float(feats.get("vac_avail_trend_4m", 0.0)), 2),
            },
            "service_history_4m": {
                "outpatient_visits_4m_avg": round(float(feats.get("outpatient_visits_mean_4m", 0.0)), 1),
                "cumulative_disruption_days_4m": round(float(feats.get("disruption_days_sum_4m", 0.0)), 1),
            }
        }


# Global singleton
inventory_db = InventoryDB()
