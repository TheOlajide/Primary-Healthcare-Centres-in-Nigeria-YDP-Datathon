"""
routers/predict.py – FastAPI router for all prediction endpoints.

Provides two convenient ways to predict:
  1. GET /predict/ – Enter parameters directly into Swagger fields (facility_id, record_date)
  2. POST /predict/ – Send parameters via JSON body or query parameters
  3. POST /predict/batch – Batch prediction for multiple facilities
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Body, HTTPException, Query, status

from src.inference import model_store, predict
from src.schemas import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    PredictionRequest,
    PredictionResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predict", tags=["Predictions"])


# ---------------------------------------------------------------------------
# GET /predict/ – Direct parameter inputs in Swagger UI
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=PredictionResponse,
    summary="Predict shortage risk (Interactive parameters input)",
    description=(
        "Enter `facility_id` and optional `record_date` in the parameter fields below. "
        "The server resolves inventory and 4-month operational history from the database."
    ),
    status_code=status.HTTP_200_OK,
)
async def predict_get(
    facility_id: str = Query(
        ...,
        description="Facility identifier (e.g., 'PHC000001' or 'PHC013578')",
        examples=["PHC000001"],
    ),
    record_date: str | None = Query(
        None,
        description="Snapshot date (e.g., '2025-12-31', '2025-09-30'). Defaults to latest.",
        examples=["2025-12-31"],
    ),
) -> PredictionResponse:
    if not model_store.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models are not loaded yet. Please try again shortly.",
        )

    t0 = time.perf_counter()
    try:
        req = PredictionRequest(facility_id=facility_id, record_date=record_date)
        result = predict(req)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facility not found: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Inference error for facility %s", facility_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failed: {exc}",
        ) from exc

    logger.info(
        "GET /predict/ facility=%s alert=%s med_prob=%.3f vac_prob=%.3f (%.1f ms)",
        result.facility_id, result.alert_level,
        result.essential_medicine_risk.risk_probability,
        result.critical_vaccine_risk.risk_probability,
        (time.perf_counter() - t0) * 1000,
    )
    return result


# ---------------------------------------------------------------------------
# POST /predict/ – Supports both JSON Body and Query Parameters
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=PredictionResponse,
    summary="Predict shortage risk (JSON Body or Query Parameters)",
    description=(
        "Send parameters via JSON body `{'facility_id': 'PHC000001'}` OR use query parameters."
    ),
    status_code=status.HTTP_200_OK,
)
async def predict_single(
    request: PredictionRequest | None = Body(None),
    facility_id: str | None = Query(None, description="Facility ID if not sending JSON body", examples=["PHC000001"]),
    record_date: str | None = Query(None, description="Snapshot date if not sending JSON body", examples=["2025-12-31"]),
) -> PredictionResponse:
    if not model_store.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models are not loaded yet. Please try again shortly.",
        )

    # Resolve from body or query parameters
    if request is not None:
        req = request
    elif facility_id:
        req = PredictionRequest(facility_id=facility_id, record_date=record_date)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either a JSON request body with 'facility_id' or a 'facility_id' parameter.",
        )

    t0 = time.perf_counter()
    try:
        result = predict(req)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facility not found: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during inference for facility %s", req.facility_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failed: {exc}",
        ) from exc

    logger.info(
        "POST /predict/ facility=%s alert=%s med_prob=%.3f vac_prob=%.3f (%.1f ms)",
        result.facility_id, result.alert_level,
        result.essential_medicine_risk.risk_probability,
        result.critical_vaccine_risk.risk_probability,
        (time.perf_counter() - t0) * 1000,
    )
    return result


# ---------------------------------------------------------------------------
# POST /predict/batch – Batch prediction
# ---------------------------------------------------------------------------

@router.post(
    "/batch",
    response_model=BatchPredictionResponse,
    summary="Predict shortage risk for multiple PHC facilities in one call",
    status_code=status.HTTP_200_OK,
)
async def predict_batch(request: BatchPredictionRequest) -> BatchPredictionResponse:
    if not model_store.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models are not loaded yet.",
        )

    results = []
    errors  = []
    for item in request.facilities:
        try:
            results.append(predict(item))
        except Exception as exc:
            logger.error("Failed on facility %s: %s", item.facility_id, exc)
            errors.append({"facility_id": item.facility_id, "error": str(exc)})

    if errors and not results:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "All facilities failed inference.", "errors": errors},
        )

    return BatchPredictionResponse(total=len(results), results=results)
