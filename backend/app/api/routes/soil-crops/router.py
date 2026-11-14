"""Soil survey, crop catalogue, crop history, suitability and markets."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.schemas.responses import ErrorResponse
from app.services import analysis
from app.services.rotation_engine.context import crops_by_id, load_catalog
from app.services.rotation_engine.simulate import TILLAGE
from app.services.usda_connectors import cropland, ssurgo

router = APIRouter(prefix="/soil-crops", tags=["soil-crops"])
NOT_FOUND = {404: {"model": ErrorResponse}}
UPSTREAM = {503: {"model": ErrorResponse}}

Lat = Query(..., ge=-60, le=72)
Lon = Query(..., ge=-180, le=180)


@router.get("/catalog", summary="Crop and cover-crop catalogue")
def catalog() -> dict:
    """Agronomic traits for every crop the engine can place in a rotation: season, water use,
    rooting depth, nitrogen, residue, pest groups, equipment and economics."""
    cat = load_catalog()
    return {**cat, "tillage_systems": [{"id": k, "label": v["label"]} for k, v in TILLAGE.items()]}


@router.get("/soil", responses=UPSTREAM, summary="Live USDA SSURGO soil profile at a coordinate")
def soil_point(lat: float = Lat, lon: float = Lon) -> dict:
    return ssurgo.fetch_soil_profile(lat, lon)


@router.get("/history", summary="Crop history at a coordinate from the Cropland Data Layer")
def crop_history(lat: float = Lat, lon: float = Lon, start: int = Query(2019, ge=2008, le=2024),
                 end: int = Query(2023, ge=2008, le=2024)) -> dict:
    return cropland.cdl_history(lat, lon, list(range(start, max(start, end) + 1)))


@router.get("/suitability/{field_id}", responses=NOT_FOUND, summary="Which crops fit this field")
def suitability(field_id: str) -> dict:
    """Every harvestable crop is grown alone on the field in the model. Returns whether it
    matures, its relative yield after water, heat and soil limits, and what limits it."""
    return analysis.crop_suitability(field_id)


@router.get("/market/{field_id}", responses=NOT_FOUND, summary="Prices, volatility and local buyers")
def market(field_id: str) -> dict:
    b = analysis.bundle(field_id)
    return {"field_id": field_id, **cropland.market_snapshot(list(crops_by_id().values()), b["farm"].get("local_market"))}
