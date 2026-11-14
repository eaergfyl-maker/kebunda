"""What-if climate and water stress tests."""
from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas.requests import StressTestRequest, SweepRequest
from app.models.schemas.responses import ErrorResponse, StressTestResponse, SweepResponse
from app.services.scenario_simulator import simulator

router = APIRouter(prefix="/scenarios", tags=["scenarios"])
ERRORS = {404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}


@router.get("/presets", summary="Scenario dials, their ranges and ready-made presets")
def presets() -> dict:
    return {"limits": simulator.LIMITS, "presets": simulator.PRESETS,
            "note": "Scenarios shift the observed 2001-2024 record. They are stress tests, not forecasts."}


@router.post("/stress-test", response_model=StressTestResponse, responses=ERRORS,
             summary="Re-run strategies under a climate or water scenario")
def stress_test(body: StressTestRequest) -> dict:
    """Runs each rotation under today's climate and under the scenario with the same models
    (crop calendar, water balance, erosion, economics, 24-year weather replay) and returns
    both, the change, and any rotation that stops fitting the season or runs out of water."""
    return simulator.stress_test(
        body.field_id, [s.model_dump() for s in body.strategies], body.scenario.model_dump(),
        priorities=body.priorities.clean() if body.priorities else None,
        constraints=body.constraints.clean() if body.constraints else None,
    )


@router.post("/sweep", response_model=SweepResponse, responses=ERRORS,
             summary="Vary one scenario dial to find where rotations trade places")
def sweep(body: SweepRequest) -> dict:
    return simulator.sweep(
        body.field_id, [s.model_dump() for s in body.strategies], body.parameter,
        priorities=body.priorities.clean() if body.priorities else None,
        constraints=body.constraints.clean() if body.constraints else None,
        steps=body.steps, base_scenario=body.base_scenario.model_dump() if body.base_scenario else None,
    )
