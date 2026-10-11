"""
app.py – FastAPI application factory for PHC supply shortage prediction service.

Usage
-----
Development:
    uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import API_DESCRIPTION, API_TITLE, API_VERSION
from src.inference import model_store
from src.inventory_db import inventory_db
from src.routers import predict as predict_router
from src.schemas import HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: load models on startup, release on shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Loading ML models …")
    try:
        model_store.load()
        logger.info("Models ready.")
    except FileNotFoundError as exc:
        logger.error(
            "%s\n → Run `python src/train_and_save.py` to generate model artefacts.", exc
        )

    logger.info("Loading inventory database …")
    try:
        inventory_db.load()
        logger.info(
            "InventoryDB ready – %d facilities indexed.",
            inventory_db.facility_count,
        )
    except Exception as exc:
        logger.error("InventoryDB failed to load: %s", exc)

    yield
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-ms"] = f"{(time.perf_counter() - t0) * 1000:.2f}"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred.", "error": str(exc)},
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="API health check",
)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok" if (model_store.is_ready and inventory_db.is_ready) else "degraded",
        models_loaded=model_store.is_ready,
        inventory_ready=inventory_db.is_ready,
        version=API_VERSION,
    )


# ---------------------------------------------------------------------------
# Root Service Information Endpoint (GET /)
# ---------------------------------------------------------------------------

@app.get(
    "/",
    tags=["System"],
    summary="API Root & Service Information",
)
async def root() -> dict[str, str]:
    return {
        "service": API_TITLE,
        "version": API_VERSION,
        "description": API_DESCRIPTION,
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health",
        "predict_endpoint": "/predict/",
        "batch_predict_endpoint": "/predict/batch",
    }


# ---------------------------------------------------------------------------
# Attach routers
# ---------------------------------------------------------------------------

app.include_router(predict_router.router)
