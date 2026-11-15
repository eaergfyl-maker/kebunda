# FieldShift — Adapting Farms with NASA Data

> **2026 NASA Space Apps Challenge:** [Field Shift: Adapting Farms with NASA Data](https://www.spaceappschallenge.org/2026/challenges/adapting-farms-with-nasa-data/?tab=details)

## Mission & Overview

**FieldShift** is a farmer-centered agricultural decision-support platform that combines **NASA Earth observations** with **local soil information, crop characteristics, and farmer priorities** to help growers explore, evaluate, and compare multi-year crop-rotation strategies that strengthen soil health and build resilience to changing climate and water conditions.

This tool is built to **support—never replace—farmer judgment and local agricultural expertise**, translating multi-resolution satellite telemetry and agro-climatic models into clear, actionable insights alongside transparent uncertainty and local review checklists.

---

## Quick Start

Needs Python 3.11+ and Node 20+. **No API keys.**

```bash
# terminal 1: API on http://localhost:8000 (interactive docs at /docs)
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# terminal 2: app on http://localhost:5173
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, pick one of the five benchmark fields, or click anywhere on the
map of Malaysia to build a field live from NASA and global services.

```bash
cd backend  && python -m pytest       # 69 tests, fully offline
cd frontend && npm run build          # type-check and production build
```

Working in a team? Read **[docs/TEAM_CONTRIBUTING.md](docs/TEAM_CONTRIBUTING.md)** first.

---

## What It Does

1. **Reads the field.** 24 years of daily NASA POWER weather and GPM IMERG rainfall, MetMalaysia
   rain gauges (via NOAA GHCN), five years of Copernicus Sentinel-2 10 m greenness and the crop
   cycles it reveals, SRTM terrain, ISRIC SoilGrids soil, FAO GAEZ crop suitability (today and
   the 2050s) and, where available, MODIS surface temperature and evapotranspiration are fused
   onto one monthly grid. Each layer shows its pixel size next to the field and how it was
   obtained (live, curated, or a stand-in product).
2. **Asks what matters.** Five priorities in plain language (water, soil health, soil
   cover, pest break, income) and what the farm can do (irrigation, equipment, livestock,
   appetite for change, crops that are off the table).
3. **Compares rotations.** Hundreds of rotations are simulated month by month: crop
   calendar from the monsoons (crops are planted into the wettest window and chained two or
   three a year, as Malaysian paddy and vegetable growers do), soil cover, paddy flooding, water balance, erosion, soil carbon,
   nitrogen, pest break and economics. At least three strategies, always including the
   current rotation, are shown side by side, each with:
   1. **Why it was suggested**
   2. **Supporting evidence** (observed and modelled)
   3. **Expected benefits and costs**, quantified against the current rotation
   4. **Information gaps and model uncertainty**
   5. **Risks needing local review**, as a checklist tagged with who should review each item
4. **Stress-tests them.** Dials for temperature, rainfall, storm intensity and irrigation
   allocation re-run every rotation through the same models and the 2001-2024 weather record.

Also included: a bare-field vulnerability calendar (hazard × exposure by month), a
satellite-vs-ground rainfall comparison, a to-scale view of each dataset's pixel against the
field, a satellite check of the assumed crop calendar, a build-your-own rotation tool, a
45-term plain-language glossary, and a printable Agronomy Field Brief.

### Benchmark fields

Five real Malaysian coordinates with observations pulled from NASA and global services.
Baselines were checked against the crop cycles Sentinel-2 sees at each point. Money is in
ringgit (RM) per hectare.

| Field | Current rotation | The problem |
| --- | --- | --- |
| MADA paddy, Kedah | Paddy - paddy, two seasons a year | Off-season canal water in El Niño years, rice-after-rice pests |
| Cameron Highlands, Pahang | Cabbage - tomato on steep terraces | Erosion and sediment, clubroot and bacterial wilt |
| BRIS sands, Kelantan | Kenaf, then fallow | Sand that holds little water, nematodes, thin margins |
| Pekan Nanas peat, Johor | MD2 pineapple, replanted | Peat subsidence, carbon loss and fire risk |
| Hill paddy, Sarawak | Hill rice - bush fallow | Bare slopes under the heaviest rain in Malaysia |

### What is real and what is curated

| | |
| --- | --- |
| **Pulled live, no key** | NASA POWER (MERRA-2 meteorology), GPM IMERG rainfall, SRTM, Copernicus Sentinel-2 L2A (Microsoft Planetary Computer), ISRIC SoilGrids 2.0, FAO GAEZ v4, NOAA GHCN-Daily (MetMalaysia stations), MODIS NDVI / LST / ET (ORNL), NASA GIBS map tiles |
| **Stand-in products, labelled as such** | MERRA-2 root-zone wetness for SMAP L4; MODIS LST and ET for ECOSTRESS |
| **Curated from published sources** | Reference yields and costs (DOA, MARDI, MADA, LKTN, MPIB), FAMA farm-gate prices, local buyer notes, crop traits, surveyed soil corrections for peat and BRIS sand |

The full list of the challenge's datasets and how each is used is in the app under
**Data and methods** and at `GET /api/v1/nasa/sources`.

---

## Documentation

| Document | Contents |
| --- | --- |
| [docs/TEAM_CONTRIBUTING.md](docs/TEAM_CONTRIBUTING.md) | Run commands, who owns what, how to plug in layers, charts, panels, pages |
| [docs/architecture/README.md](docs/architecture/README.md) | System diagram, request flow, module map, design decisions |
| [docs/api-contracts/API.md](docs/api-contracts/API.md) | Endpoint reference; `openapi.json`; real example payloads |
| [docs/agronomy-models/models.md](docs/agronomy-models/models.md) | Every model's formulas, parameters, sources and weaknesses |
| [docs/agronomy-models/fusion-and-uncertainty.md](docs/agronomy-models/fusion-and-uncertainty.md) | Resolution harmonisation, rainfall fusion, confidence |
| [docs/agronomy-models/scoring.md](docs/agronomy-models/scoring.md) | Candidate search, scores, fit, strategy selection, the five explanations |

---

## Repository Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── middleware/             # Uniform JSON errors, request timing
│   │   │   └── routes/
│   │   │       ├── farms/              # Benchmark farms & custom field endpoints
│   │   │       ├── nasa/               # Live NASA POWER, GIBS layers, mission notes
│   │   │       ├── rotations/          # Multi-strategy rotation scoring & comparison
│   │   │       ├── scenarios/          # "What-if" stress tests and sweeps
│   │   │       └── soil-crops/         # Soil profile, crop catalogue, history, suitability, markets
│   │   ├── models/
│   │   │   ├── domain/                 # Core entities (re-exported from the engines)
│   │   │   └── schemas/                # Request/response models: the API contract
│   │   ├── services/
│   │   │   ├── fusion_engine/          # Monthly grid, rainfall fusion, resolution-gap confidence
│   │   │   ├── global_connectors/      # SoilGrids, FAO GAEZ, Sentinel-2, GHCN gauges, FAMA/DOA markets
│   │   │   ├── nasa_connectors/        # POWER, MODIS/VIIRS subsets, SRTM, GIBS, SMAP/ECOSTRESS/GRACE adapters
│   │   │   ├── rotation_engine/        # Calendar, simulation, search, scoring, 5 explanations
│   │   │   ├── scenario_simulator/     # Climate & water stress tests
│   │   │   └── vulnerability_analyzer/ # Field insights, hazard x exposure calendar
│   │   └── utils/                      # Cache, geospatial and statistics helpers
│   ├── scripts/                        # Benchmark data builder, contract exporter
│   └── tests/                          # Offline unit & integration tests
├── data/
│   ├── benchmark-farms/                # Farm definitions + observations/ pulled from NASA & global services
│   ├── cache/                          # Local runtime response cache (gitignored)
│   ├── crop-catalog/                   # Crop and cover-crop traits
│   └── soil-profiles/                  # SoilGrids profiles (with survey corrections) for the benchmark fields
├── docs/
│   ├── agronomy-models/                # Formulas, fusion, uncertainty, scoring
│   ├── api-contracts/                  # API.md, openapi.json, example payloads
│   ├── architecture/                   # System diagram and module map
│   └── TEAM_CONTRIBUTING.md            # How the three of us work in this repo
├── frontend/
│   ├── public/assets/                  # Static icons
│   └── src/
│       ├── components/
│       │   ├── common/                 # Shared UI, glossary/, export/
│       │   ├── farmer-controls/        # priority-sliders/, scenario-sliders/
│       │   ├── map/                    # layers/, controls/, overlays/
│       │   ├── rotation-explorer/      # cards/, evidence-panels/, sequence-builder/
│       │   └── timelines/              # Vulnerability calendar, climate record, satellite vs. ground
│       ├── hooks/                      # Data hooks, shared farmer state, units
│       ├── pages/                      # Explore, Field, Brief, Methods + page registry
│       ├── services/                   # Typed API client
│       ├── styles/                     # Design tokens, global styles, chart theme
│       └── types/                      # API contract types
├── .env.example                        # Optional configuration (nothing is required)
└── README.md
```

---

## Team Git & Branching Workflow

1. Never commit directly to `main`. Create feature branches off `main`:
   - Backend & data pipelines: `feat/backend-<topic>`
   - Geospatial map & timelines: `feat/map-<topic>`
   - Decision-support UI & controls: `feat/ui-<topic>`
2. `.env` is optional. Copy `.env.example` only to change ports or add optional keys (never commit `.env`).
3. Keep `docs/api-contracts/` updated before changing shared JSON payloads so backend and frontend stay aligned (`python -m scripts.export_contracts`).
4. Open a Pull Request into `main` for review once your module compiles and passes tests.

---

## Limits

FieldShift's models are monthly, single-field planning models built to rank rotations
against each other. They do not see compaction, tile lines, nematodes, varieties, contracts
or within-field variation, and their dollar figures are not a budget. Every result page says
so, and every strategy lists what to check with a County Extension agent or Certified Crop
Adviser before acting.
