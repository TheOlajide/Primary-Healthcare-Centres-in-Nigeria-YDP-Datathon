"""
schemas.py – Pydantic v2 schemas for the PHC Shortage Risk Inference Pipeline.

Clients send only `facility_id` (with optional overrides or target date).
The server automatically queries the inventory and operations database to derive
all 4-month rolling features, runs the classifiers, and returns predictions with
transparent supply insights.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class FacilityRecord(BaseModel):
    """Optional explicit facility metadata override."""
    operational_status:        str | None   = Field(None, examples=["Functional", "Non-Functional"])
    urban_rural_class:         str | None   = Field(None, examples=["Rural", "Urban"])
    distance_to_lga_hq_km:    float | None = Field(None, ge=0)
    distance_to_major_road_km: float | None = Field(None, ge=0)
    catchment_population:      float | None = Field(None, ge=0)
    number_of_beds:            float | None = Field(None, ge=0)
    total_health_workers:      float | None = Field(None, ge=0)
    has_electricity:           bool | None  = None
    has_water:                 bool | None  = None
    has_storage_room:          bool | None  = None
    has_refrigerator:          bool | None  = None
    has_cold_chain:            bool | None  = None
    state_name:                str | None   = None


class ServiceMetrics(BaseModel):
    """Optional explicit monthly service metrics override."""
    outpatient_visits:       float | None = Field(None, ge=0)
    service_disruption_days: float | None = Field(None, ge=0)
    service_readiness_score: float | None = Field(None, ge=0, le=100)


class PredictionRequest(BaseModel):
    """
    Primary execution request payload.
    The client provides the facility_id. The server resolves all current and
    4-month historical inventory and operational data from the CSV database.
    """
    facility_id: str = Field(
        ...,
        examples=["PHC000001"],
        description="Facility identifier (e.g., 'PHC000001'). Used to query server-side inventory and 4-month operational logs.",
    )
    record_date: str | None = Field(
        None,
        examples=["2025-12-31"],
        description="Target snapshot date (defaults to latest available report: 2025-12-31).",
    )
    facility: FacilityRecord | None = Field(
        None,
        description="Optional facility metadata override. If omitted, fetched automatically from facilities.csv.",
    )
    service: ServiceMetrics | None = Field(
        None,
        description="Optional latest monthly service override. If omitted, fetched automatically from facility_services.csv.",
    )


class BatchPredictionRequest(BaseModel):
    """Batch prediction request for multiple facilities."""
    facilities: list[PredictionRequest] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class RiskScore(BaseModel):
    """Risk probability, flag, and descriptive status."""
    risk_flag:        int   = Field(..., description="1 = At Risk of Shortage, 0 = Adequate Supply")
    risk_probability: float = Field(..., description="Model probability (0.00 – 1.00)")
    risk_label:       str   = Field(..., description="Descriptive status label with confidence")


class MedicineInsight(BaseModel):
    """Current state & 4-month dynamics for medicine inventory."""
    at_risk_rate:                 float = Field(..., description="Fraction of medicines with Stockout, Critical, or Low Stock status")
    essential_stockout_rate:      float = Field(..., description="Fraction of essential categories (antibiotics, antimalarials, maternal) stocked out")
    min_days_stock_remaining:     float = Field(..., description="Minimum days of stock remaining for the most urgent medicine")
    mean_days_stock_remaining:    float = Field(..., description="Average days of stock remaining across all medicines")
    stock_coverage_ratio:         float = Field(..., description="Average stock level relative to maximum capacity")
    restocked_in_last_4m_pct:     float = Field(..., description="Percentage of tracked medicines restocked in the past 4 months")
    mean_days_since_last_restock: float = Field(..., description="Average days since last restock")
    availability_last_4m_avg:     float = Field(..., description="Average essential medicine availability score over past 4 months")
    availability_trend_4m:        float = Field(..., description="Trend: current availability minus 4-month prior average")


class VaccineInsight(BaseModel):
    """Current state & 4-month dynamics for vaccine inventory."""
    at_risk_rate:                 float = Field(..., description="Fraction of vaccines with Stockout, Critical, or Low Stock status")
    min_days_stock_remaining:     float = Field(..., description="Minimum days of vaccine stock remaining for the most urgent vaccine")
    mean_days_stock_remaining:    float = Field(..., description="Average days of stock remaining across all vaccines")
    cold_chain_uptime_pct:        float = Field(..., description="Average cold-chain uptime percentage over past 90 days")
    temperature_excursion_count:  int   = Field(..., description="Total temperature excursions (spoilage risk)")
    restocked_in_last_4m_pct:     float = Field(..., description="Percentage of tracked vaccines restocked in the past 4 months")
    mean_days_since_last_restock: float = Field(..., description="Average days since last restock")
    availability_last_4m_avg:     float = Field(..., description="Average immunization availability score over past 4 months")
    availability_trend_4m:        float = Field(..., description="Trend: current availability minus 4-month prior average")


class ServiceHistoryInsight(BaseModel):
    """4-month operational disruption and workload metrics."""
    outpatient_visits_4m_avg:      float = Field(..., description="Average monthly outpatient visits over past 4 months")
    cumulative_disruption_days_4m: float = Field(..., description="Total service disruption days across past 4 months")


class InventoryInsight(BaseModel):
    """Complete transparency reporting structure."""
    medicine:           MedicineInsight
    vaccine:            VaccineInsight
    service_history_4m: ServiceHistoryInsight


class PredictionResponse(BaseModel):
    """Full inference response for a facility."""
    facility_id:             str
    state_name:              str | None
    record_date:             str | None
    essential_medicine_risk: RiskScore
    critical_vaccine_risk:   RiskScore
    inventory_insight:       InventoryInsight
    feature_vector:          dict[str, float]
    alert_level:             str = Field(..., description="HIGH (both at risk) | MEDIUM (one at risk) | LOW (both adequate)")


class BatchPredictionResponse(BaseModel):
    total:   int
    results: list[PredictionResponse]


class HealthResponse(BaseModel):
    status:          str
    models_loaded:   bool
    inventory_ready: bool
    version:         str
