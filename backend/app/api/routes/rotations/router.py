"""Generate, score and explain rotation strategies."""
from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas.requests import CompareRequest
from app.models.schemas.responses import CompareResponse, ErrorResponse
from app.services import analysis
from app.services.rotation_engine import scoring
from app.services.rotation_engine.context import load_catalog
from app.services.rotation_engine.simulate import TILLAGE

router = APIRouter(prefix="/rotations", tags=["rotations"])

PRIORITY_PRESETS = [
    {"id": "balanced", "label": "Balanced", "description": "Every goal counts the same.",
     "priorities": {"water": 6, "soil": 6, "erosion": 6, "pest": 6, "income": 6}},
    {"id": "water_first", "label": "Stretch the water", "description": "The well or the rain is the limit.",
     "priorities": {"water": 10, "soil": 5, "erosion": 4, "pest": 4, "income": 6}},
    {"id": "soil_builder", "label": "Build the soil", "description": "Organic matter, nitrogen and cover come first.",
     "priorities": {"water": 5, "soil": 10, "erosion": 9, "pest": 5, "income": 4}},
    {"id": "clean_fields", "label": "Break the cycles", "description": "Weeds, insects or disease are the main fight.",
     "priorities": {"water": 4, "soil": 5, "erosion": 5, "pest": 10, "income": 6}},
    {"id": "cash_flow", "label": "Protect cash flow", "description": "Any change has to pay its way.",
     "priorities": {"water": 4, "soil": 4, "erosion": 4, "pest": 4, "income": 10}},
]

PRIORITY_HELP = {
    "water": "Uses less irrigation or rain per dollar earned, and suffers less in a dry year.",
    "soil": "Raises organic matter, adds nitrogen from legumes, keeps roots alive more of the year.",
    "erosion": "Keeps the ground covered when hard rain falls, so soil and nutrients stay put.",
    "pest": "Changes crop families and planting seasons so pests, weeds and diseases cannot settle in.",
    "income": "Net return, how steady it is from year to year, forage value, and whether a buyer is nearby.",
}


@router.get("/options", summary="Labels, presets and choices for the farmer controls")
def options() -> dict:
    cat = load_catalog()
    return {
        "dimensions": [{"id": d, "label": scoring.DIMENSION_LABELS[d], "help": PRIORITY_HELP[d]} for d in scoring.DIMENSIONS],
        "priority_presets": PRIORITY_PRESETS,
        "tillage_systems": [{"id": k, "label": v["label"]} for k, v in TILLAGE.items()],
        "risk_tolerance": [
            {"id": "low", "label": "Cautious", "help": "Prefer small changes and proven local markets."},
            {"id": "medium", "label": "Open", "help": "Willing to try a new crop or practice if the case is good."},
            {"id": "high", "label": "Adventurous", "help": "Rank purely on the outcomes; do not penalise change."},
        ],
        "equipment": [{"id": k, "label": v} for k, v in cat["equipment_labels"].items()],
        "crops": [{"id": c["id"], "name": c["name"], "role": c["role"], "family": c["family"], "cycle": c["cycle"],
                   "functional_group": c["functional_group"], "legume": c["legume"]} for c in cat["crops"]],
    }


@router.post("/compare", response_model=CompareResponse,
             responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
             summary="Compare the current rotation with tailored alternatives")
def compare(body: CompareRequest) -> dict:
    """Returns at least three strategies, always including the field's existing rotation.
    Each carries its scores, month-by-month calendar, and the five explanations: why it was
    suggested, supporting evidence, expected benefits, information gaps, and risks needing
    local review. Changing only `priorities` is a fast re-rank of cached simulations."""
    return analysis.compare(
        body.field_id,
        priorities=body.priorities.clean() if body.priorities else None,
        constraints=body.constraints.clean() if body.constraints else None,
        scenario=body.scenario.model_dump() if body.scenario else None,
        baseline_override=body.baseline.model_dump() if body.baseline else None,
        custom_strategies=[s.model_dump() for s in body.custom_strategies] if body.custom_strategies else None,
    )
