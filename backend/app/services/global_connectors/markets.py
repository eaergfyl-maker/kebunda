"""Farm-gate prices, volatility and local-buyer access for Malaysian crops.

Prices are multi-year (2021-2024) farm-gate averages curated from FAMA (Federal
Agricultural Marketing Authority) price bulletins, DOA Malaysia crop budgets ("kos
pengeluaran") and scheme prices (government paddy floor price, LKTN kenaf, MPIB
pineapple), stored in the crop catalogue in RM. No keyless live price API exists, so
the curated table keeps the tool keyless, and every row says it is curated.
"""
from __future__ import annotations

from app.services.nasa_connectors import base


def market_snapshot(crops: list[dict], local_market: dict | None = None) -> dict:
    """Price level, volatility and local-buyer access per crop."""
    local_market = local_market or {}
    rows = []
    for crop in crops:
        econ = crop.get("economics")
        if not econ or crop.get("role") == "cover":
            continue
        local = local_market.get(crop["id"], {})
        rows.append({
            "crop_id": crop["id"], "name": crop["name"],
            "price": econ["price"], "price_unit": f"RM/{econ['yield_unit']}",
            "price_volatility_cv": econ["price_cv"],
            "local_access": local.get("access", crop.get("market_default", 0.5)),
            "local_note": local.get("note", "No local buyer information on file. Ask FAMA, the area farmers' organisation (PPK) or a collector before planting."),
            "verified_locally": bool(local),
        })
    return {
        "rows": rows,
        "provenance": base.provenance(
            "FAMA / DOA Malaysia", "Multi-year average farm-gate prices and volatility (curated, RM)", base.ACCESS_CURATED,
            cadence="2021-2024 average", url="https://www.fama.gov.my/",
            note="Averages hide grade, middleman margins and haul distance. Use them to rank options, not to budget."),
    }
