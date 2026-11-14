# FieldShift API contract

Base URL: `http://localhost:8000/api/v1` · JSON in, JSON out · no authentication · no API keys needed.

| File | What it is |
| --- | --- |
| `openapi.json` | The full OpenAPI 3.1 schema, generated from the code. Interactive version at `http://localhost:8000/docs`. |
| `examples/*.json` | Real request and response payloads for the Iowa benchmark farm. Mock against these. |
| `frontend/src/types/api.ts` | The same shapes as TypeScript types. |

Regenerate the first two after any backend change:

```bash
cd backend && python -m scripts.export_contracts
```

**Contract rule:** change the schema (`backend/app/models/schemas/`), regenerate, update
`frontend/src/types/api.ts`, and put all three in the same pull request.

## Conventions

- **Units are metric** (mm, °C, t/ha, kg N/ha) except money and yields, which are per acre in
  US units (`$/ac`, `bu/ac`), and soil loss, which is given both ways. The frontend converts
  for display in `hooks/useUnits.ts`.
- **Months** are `0` (January) to `11`. A rotation timeline index runs `0 .. n_years*12-1`.
- **Scores** are `0-100`, higher is better, with fixed anchors (see
  `docs/agronomy-models/scoring.md`).
- **Provenance** travels with data. Any `provenance.access` is one of
  `live`, `cache`, `curated`, `proxy`, `unavailable` (and `model` for computed evidence).
- **Errors** always have the same body: `{"error": "<code>", "detail": "<message>", "hint": "<what to do>"}`.

| Status | `error` | When |
| --- | --- | --- |
| 404 | `field_not_found` | Unknown `field_id` |
| 422 | `invalid_rotation` | Unknown crop id, empty rotation, more than 6 years |
| 422 | `invalid_request` | Body fails validation (also returns `errors[]`) |
| 503 | `data_source_unavailable` | A live NASA/USDA service did not answer and nothing is cached |

## Endpoints

### Farms

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/farms` | `FarmSummary[]`: the five benchmark farms |
| GET | `/farms/{field_id}` | `FieldOverview`: farm, soil, terrain, climate, satellite series, fusion report, hazards, insights |
| GET | `/farms/{field_id}/vulnerability` | Hazard calendar and the baseline rotation's month-by-month risk grid |
| POST | `/farms/custom` | `FieldOverview` for a field built live from `{lat, lon}`; its `id` works everywhere else |

`FieldOverview` blocks the UI uses most:

| Block | Contents |
| --- | --- |
| `farm` | Name, story, management (irrigation, tillage, equipment), `baseline_rotation`, `default_priorities` |
| `soil` | SSURGO profile: texture, organic matter, AWC, pH, EC, Kw, T factor, hydrologic group, drainage |
| `climate.monthly` | 12-value arrays: `tmax`, `tmin`, `precip`, `et0`, `wet_root`, `frost_days`, `heat_days_35`, `erosive_days`, `erosivity_share`, ... |
| `climate.annual`, `.trends` | One value per year (2001-2024) and its Theil-Sen trend with significance |
| `series` | Year-by-month grids: `precip`, `wet_root`, `wet_root_z`, `heat_days_35`, `tmax`, `erosivity` |
| `vegetation`, `surface_temperature`, `evapotranspiration` | MODIS NDVI / LST / ET by month and by year (`null` if not retrieved) |
| `fusion.precip` | Fused monthly rainfall, uncertainty, per-source weights |
| `fusion.layers` | One row per data layer: pixel size, pixel-to-field ratio, representativeness, confidence |
| `fusion.confidence` | Data, model and combined confidence per decision dimension |
| `hazards.months` | Field-level hazard calendar (storm, heat, frost, wetness, observed NDVI) |
| `insights.facts` | Plain-language facts with source and access level |

### Rotations

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/rotations/options` | Dimension labels, priority presets, tillage systems, risk-tolerance choices, equipment and crop lists |
| POST | `/rotations/compare` | `CompareResponse`: at least 3 strategies, always including the baseline |

`POST /rotations/compare` body (everything except `field_id` is optional):

```jsonc
{
  "field_id": "ogallala-ks",
  "priorities": { "water": 9, "soil": 5, "erosion": 5, "pest": 4, "income": 7 },   // 0-10 each
  "constraints": {
    "irrigation_available": true, "water_allocation_mm": 350,
    "equipment": ["row_planter", "combine"], "custom_hire_available": true, "livestock": false,
    "risk_tolerance": "low",                    // low | medium | high
    "tillage": "reduced",                       // override the baseline tillage
    "allow_cover_crops": true, "allow_tillage_change": true, "allow_fallow": false,
    "max_rotation_years": 4, "exclude_crops": ["alfalfa"], "must_include_crops": ["sorghum"]
  },
  "baseline": { "years": [["corn"], ["sorghum"]], "tillage": "conventional" },    // farmer's correction
  "custom_strategies": [{ "name": "My idea", "years": [["corn"], ["soybean"], ["oats", "crimson_clover"]] }]
}
```

A rotation is `years: string[][]`: one list of crop ids per year, in planting order. `[]` is
a fallow year. A fall-sown crop goes in the year it is harvested. A cover crop listed after
a cash crop grows until the next crop is planted.

Each `Strategy` carries:

| Field | Meaning |
| --- | --- |
| `role` | `baseline`, `step` (same crops, covered soil), `match` (best fit), `resilient`, `income`, `custom` |
| `scores`, `fit` | Five 0-100 scores; priority-weighted `fit.fit` with `penalties` and `change` |
| `phases`, `months` | Crops on the calendar; per-month cover, water balance, erosion, leaching |
| `metrics` | About 35 annualised outcomes (irrigation, stress, soil loss, SOC change, N, pest score, net return, ...) |
| `history` | Net return, irrigation and stress for each weather year 2002-2024; bad-year income |
| `vulnerability` | Month-by-month hazard x exposure grid and summary windows |
| `explanation.why` | 1. Why it was suggested |
| `explanation.evidence` | 2. Supporting evidence (`observed` and `modelled`) |
| `explanation.benefits` | 3. Expected benefits and costs against the baseline, with ranges and confidence |
| `explanation.gaps` | 4. Information gaps, per-dimension confidence, score uncertainty |
| `explanation.risks` | 5. Risks needing local review, each with who should review it |

Changing only `priorities` re-ranks cached simulations (tens of milliseconds). Changing
`constraints`, `baseline` or the scenario re-runs the search (about a second).

### Scenarios

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/scenarios/presets` | Dial ranges (`limits`) and ready-made presets |
| POST | `/scenarios/stress-test` | Each strategy under today's climate and under the scenario |
| POST | `/scenarios/sweep` | Fit and net return of each strategy across one dial's range, plus where the leader changes |

Scenario dials: `temp_delta_c` (-1..5), `rain_pct` (-50..30), `storm_intensity_pct` (0..60),
`water_cap_pct` (0..100, share of today's irrigation allocation).

### NASA

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/nasa/power?lat=&lon=` | Live NASA POWER climate summary for any coordinate (24 years, keyless) |
| GET | `/nasa/terrain?lat=&lon=` | SRTM elevation, slope, relief |
| GET | `/nasa/gibs/layers[?check=true]` | NASA GIBS map layers with XYZ tile templates and legends |
| GET | `/nasa/missions` | What each mission contributes and how it is accessed |
| GET | `/nasa/sources` | Every dataset on the challenge list and its status in FieldShift |

### Soil and crops

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/soil-crops/catalog` | Crop and cover-crop traits, equipment labels, tillage systems |
| GET | `/soil-crops/soil?lat=&lon=` | Live SSURGO profile at a coordinate |
| GET | `/soil-crops/history?lat=&lon=` | Cropland Data Layer crop type by year |
| GET | `/soil-crops/suitability/{field_id}` | Which crops fit the field and what limits each |
| GET | `/soil-crops/market/{field_id}` | Prices, volatility and local buyer notes |

### Meta

`GET /health` and `GET /api/v1/meta` (version, disclaimer, source registry).
