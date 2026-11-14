# FieldShift — Adapting Farms with NASA Data

> **2026 NASA Space Apps Challenge:** [Field Shift: Adapting Farms with NASA Data](https://www.spaceappschallenge.org/2026/challenges/adapting-farms-with-nasa-data/?tab=details)

## Mission & Overview

**FieldShift** is a farmer-centered agricultural decision-support platform that combines **NASA Earth observations** with **local soil information, crop characteristics, and farmer priorities** to help growers explore, evaluate, and compare multi-year crop-rotation strategies that strengthen soil health and build resilience to changing climate and water conditions.

This tool is built to **support—never replace—farmer judgment and local agricultural expertise**, translating multi-resolution satellite telemetry and agro-climatic models into clear, actionable insights alongside transparent uncertainty and local review checklists.

---

## Core Capabilities

- **Multi-Sensor NASA & Ground Data Fusion:**
  Integrates and harmonizes signals across NASA Earth observation missions and agricultural datasets, including:
  - **Soil Moisture & Groundwater:** NASA SMAP, NLDAS/GLDAS, GRACE / GRACE-FO
  - **Thermal & Evapotranspiration Stress:** ECOSTRESS, OpenET, NASA POWER
  - **Precipitation & Extremes:** GPM / IMERG, PRISM, ERA5, CoCoRaHS
  - **Vegetation Vigor & Bare-Field Detection:** Landsat, MODIS / VIIRS, Copernicus Sentinel-2, NAIP
  - **Terrain & Landscape Context:** SRTM, GEDI, USGS NLCD, USFS LANDFIRE
  - **Local Soil, Crop History & Markets:** USDA NRCS SSURGO / Web Soil Survey, USDA Cropland Data Layer (CDL / CropScape), USDA NASS QuickStats, FAO GAEZ, USGS NWIS, USDA AMS Market News
- **3+ Strategy Side-by-Side Comparison (Including Baseline):**
  Evaluates the farm's existing baseline rotation against tailored adaptive rotation strategies across five required decision pillars:
  1. **Why It Was Suggested** — Alignment with climate trends, soil limits, and farmer priorities.
  2. **Supporting Evidence** — Quantified indicators from NASA Earth observations and local soil/crop records.
  3. **Expected Benefits** — Water savings, organic matter, nitrogen fixation, infiltration, erosion reduction, pest-cycle disruption, and market stability.
  4. **Information Gaps & Model Uncertainty** — Clear disclosure of resolution limits and what satellites cannot directly observe underground or on-farm.
  5. **Risks Needing Local Review** — Practical verification items for farmers, local extension specialists, and agronomists.
- **Seasonal Bare-Field & Vulnerability Detection:**
  Identifies months when fields sit bare or face peak heat, frost, drought, or storm-runoff exposure.
- **Interactive Climate Scenario Stress-Testing:**
  Lets growers simulate shifting rainfall, heat spikes, extreme storm intensity, and irrigation caps across candidate rotations.

---

## Repository Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── middleware/             # CORS, error handling, request logging
│   │   │   └── routes/
│   │   │       ├── farms/              # Benchmark farms & custom field endpoints
│   │   │       ├── nasa/               # Live NASA POWER & satellite telemetry endpoints
│   │   │       ├── rotations/          # Multi-strategy rotation scoring & comparison
│   │   │       ├── scenarios/          # "What-if" climate stress-testing endpoints
│   │   │       └── soil-crops/         # Soil profile, CDL crop history & market suitability
│   │   ├── models/
│   │   │   ├── domain/                 # Core agronomic, soil, and climate domain entities
│   │   │   └── schemas/                # Request/response validation schemas
│   │   ├── services/
│   │   │   ├── fusion_engine/          # Multi-resolution spatial/temporal harmonization
│   │   │   ├── nasa_connectors/        # NASA POWER, GIBS, SMAP, ECOSTRESS, GPM, GRACE connectors
│   │   │   ├── rotation_engine/        # Rotation recommendation & 5-pillar explanation engine
│   │   │   ├── scenario_simulator/     # Climate & water-budget scenario modeling
│   │   │   ├── usda_connectors/        # SSURGO, CDL, NASS QuickStats, FAO GAEZ, AMS connectors
│   │   │   └── vulnerability_analyzer/ # Bare-field windows, heat/frost & erosion risk scoring
│   │   └── utils/                      # Geospatial helpers, caching, unit conversions
│   └── tests/                          # Unit & integration test suites
├── data/
│   ├── benchmark-farms/                # Curated multi-sensor farm profiles
│   ├── cache/                          # Local runtime response cache (gitignored)
│   ├── crop-catalog/                   # Crop traits, water demand, N-fixation & pest-break rules
│   └── soil-profiles/                  # Pre-harmonized SSURGO / STATSGO2 soil references
├── docs/
│   ├── agronomy-models/                # Modeling assumptions, formulas & uncertainty methodology
│   ├── api-contracts/                  # OpenAPI / endpoint contracts between backend & frontend
│   └── architecture/                   # System architecture & data-flow diagrams
├── frontend/
│   ├── public/
│   │   └── assets/                     # Static icons, imagery, and visual assets
│   └── src/
│       ├── components/
│       │   ├── common/
│       │   │   ├── export/             # Printable/exportable agronomy field briefs
│       │   │   └── glossary/           # Plain-language satellite & soil jargon translator
│       │   ├── farmer-controls/
│       │   │   ├── priority-sliders/   # Farmer priority weights & farm constraint inputs
│       │   │   └── scenario-sliders/   # Interactive climate & water-cap stress-test sliders
│       │   ├── map/
│       │   │   ├── controls/           # Layer toggles, coordinate picker & legend controls
│       │   │   ├── layers/             # NASA GIBS/Worldview, NDVI, SMAP, GPM & SRTM layers
│       │   │   └── overlays/           # Field boundary, erosion & microclimate hotspot overlays
│       │   ├── rotation-explorer/
│       │   │   ├── cards/              # Side-by-side 5-pillar rotation strategy cards
│       │   │   ├── evidence-panels/    # Sensor evidence, uncertainty & local-review panels
│       │   │   └── sequence-builder/   # Multi-year crop rotation sequence visualizer
│       │   └── timelines/              # Bare-field vulnerability & seasonal phenology charts
│       ├── hooks/                      # Shared React/UI state & data-fetching hooks
│       ├── pages/                      # Main application views and layouts
│       ├── services/                   # Typed frontend API client layer
│       ├── styles/                     # Theme tokens & global stylesheets
│       └── types/                      # Shared TypeScript interfaces
├── .env.example                        # Environment configuration template
├── .gitignore                          # Git ignore rules
└── README.md                           # Project overview & repository guide
```

---

## Team Git & Branching Workflow

1. Never commit directly to `main`. Create feature branches off `main`:
   - Backend & data pipelines: `feat/backend-<topic>`
   - Geospatial map & timelines: `feat/map-<topic>`
   - Decision-support UI & controls: `feat/ui-<topic>`
2. Copy `.env.example` to `.env` before local development (never commit `.env`).
3. Keep `docs/api-contracts/` updated before changing shared JSON payloads so backend and frontend stay aligned.
4. Open a Pull Request into `main` for review once your module compiles and passes tests.
