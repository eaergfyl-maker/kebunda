"""Uniform JSON errors: {"error": code, "detail": message, "hint": what to do next}."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services.analysis import InvalidRotation
from app.services.field_store import FieldNotFound
from app.services.nasa_connectors.base import ConnectorError

log = logging.getLogger("kebunda.api")


def _body(error: str, detail: str, hint: str | None = None) -> dict:
    return {"error": error, "detail": detail, "hint": hint}


def install(app: FastAPI) -> None:
    @app.exception_handler(FieldNotFound)
    async def field_not_found(_: Request, exc: FieldNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content=_body(
            "field_not_found", f"No field with id {exc.args[0]!r}.",
            "List benchmark farms with GET /api/v1/farms, or create one with POST /api/v1/farms/custom."))

    @app.exception_handler(InvalidRotation)
    async def invalid_rotation(_: Request, exc: InvalidRotation) -> JSONResponse:
        return JSONResponse(status_code=422, content=_body(
            "invalid_rotation", str(exc), "Crop ids are listed at GET /api/v1/soil-crops/catalog."))

    @app.exception_handler(ConnectorError)
    async def upstream(_: Request, exc: ConnectorError) -> JSONResponse:
        return JSONResponse(status_code=503, content=_body(
            "data_source_unavailable", str(exc),
            "A live NASA or partner data service did not answer. Benchmark farms keep working offline; retry the live query shortly."))

    @app.exception_handler(RequestValidationError)
    async def validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errs = exc.errors()
        first = errs[0] if errs else {}
        where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        safe = [{"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")} for e in errs]
        return JSONResponse(status_code=422, content={
            **_body("invalid_request", f"{where}: {first.get('msg', 'invalid value')}", "See /docs for the request schema."),
            "errors": safe})

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content=_body(
            "internal_error", "Something went wrong while computing this response.",
            "The error was logged. Try again or simplify the request."))
