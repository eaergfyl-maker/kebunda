# Team contributing guide

Three people, three areas, no merge conflicts. Each area has a **registry file**: you add
one entry there and your new piece appears in the app. You should rarely need to edit a
file outside your own folders.

## Run it locally

Needs Python 3.11+ and Node 20+. No API keys.

```bash
# terminal 1: backend on http://localhost:8000  (docs at /docs)
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# terminal 2: frontend on http://localhost:5173
cd frontend
npm install
npm run dev
```

The dev server proxies `/api` to the backend, so no `.env` is needed.

Before you push:

```bash
cd backend  && python -m pytest          # 66 tests, offline, about 10 s
cd frontend && npm run build             # type-check + production build
```

## Branches

Never commit to `main`. Branch, push, open a pull request.

| Who | Branch prefix | Folders you own |
| --- | --- | --- |
| Member 1 | `feat/backend-*` | `backend/`, `data/`, `docs/api-contracts/`, `docs/agronomy-models/`, `docs/architecture/` |
| Member 2 | `feat/map-*` | `frontend/src/components/map/`, `frontend/src/components/timelines/` |
| Member 3 | `feat/ui-*` | `frontend/src/components/rotation-explorer/`, `farmer-controls/`, `common/`, `frontend/src/pages/` |

**Shared files** (`frontend/src/types/`, `services/`, `hooks/`, `styles/tokens.css`,
`styles/global.css`, `App.tsx`): change them in a small, separate pull request and tell the
others, because everyone imports them.

## Member 2: map and timelines

Search your folders for `TODO (Member 2)` to see the suggested additions in context.

### Add a NASA map layer

Edit `frontend/src/components/map/layers/layerRegistry.ts` and append to `EXTRA_LAYERS`:

```ts
{
  id: "VIIRS_SNPP_L3_NDVI_Monthly", title: "Greenness (VIIRS)", group: "vegetation", mission: "VIIRS",
  tileUrl: gibsUrl("VIIRS_SNPP_L3_NDVI_Monthly", "GoogleMapsCompatible_Level7", "png"),
  temporal: "monthly", start: "2012-01-01", end: null, maxNativeZoom: 7, resolution_m: 1000,
  plain: "Same idea as MODIS greenness, from the newer VIIRS sensor.", legend: null,
},
```

The layer switcher, date scrubber, opacity slider and legend pick it up. Layer ids and tile
matrix sets are in NASA Worldview or the
[GIBS capabilities document](https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml).

### Add a map overlay (pins, polygons, probes)

1. Create `components/map/overlays/MyOverlay.tsx` exporting a component that takes
   `OverlayProps` and returns react-leaflet elements.
2. Add one entry to `OVERLAYS` in `overlays/overlayRegistry.tsx`.

It gets its own on/off toggle. `OverlayProps` gives you the farm list, the open field's full
overview, the clicked coordinate, and `onAnalyzePoint(lat, lon)` to build a custom field.

### Add a timeline chart

1. Create `components/timelines/MyChart.tsx` taking `TimelineProps` (`field`, `comparison`).
2. Add one entry to `TIMELINES` in `timelines/timelineRegistry.tsx`.

It becomes a tab. `chartKit.tsx` has scales, axes, line paths, legends and trend lines.
The registry file lists every data block available to a chart.

High-impact ideas already marked in the code: animated seasonal NDVI scrubber, CoCoRaHS
rain-gauge vs. GPM IMERG comparison, GRACE-FO groundwater trend view, field-boundary
drawing, within-field slope and soil overlays.

## Member 3: decision support and farmer experience

Search your folders for `TODO (Member 3)`.

### Add a glossary term

Append one object to `GLOSSARY` in `components/common/glossary/glossaryData.ts`. Then use it
anywhere: `<Term id="my_term">word</Term>`. The glossary drawer lists it automatically.

### Add an explanation panel

1. Create `components/rotation-explorer/evidence-panels/MyPanel.tsx` taking `PanelProps`
   (`strategy`, `baseline`, `comparison`, `field`).
2. Add one entry to `PANELS` in `evidence-panels/panelRegistry.tsx`.

Keep the first five entries (the challenge's five required explanations) in order.

### Add an export format

Append one object to `EXPORT_TEMPLATES` in `components/common/export/briefTemplates.ts`
(`id`, `label`, `filename`, `mime`, `build`). A download button appears on the field page
and the brief page.

### Add a page

Create `pages/MyPage.tsx` and add one entry to `PAGES` in `pages/pageRegistry.tsx`. Set
`nav` to show it in the header.

### Add a farmer control

Farmer inputs live in `hooks/useFieldShift.tsx` (`priorities`, `constraints`, `scenario`,
`customStrategies`, `baselineOverride`, `units`). Read and set them with `useFieldShift()`;
the comparison refetches by itself. A new constraint or scenario dial needs a backend field
first: ask Member 1, or add it to `backend/app/models/schemas/requests.py` in a
`feat/backend-*` pull request.

High-impact ideas already marked: drag-and-drop sequence builder, equipment and
herbicide-carryover filter drawer, county Extension PDF layout, multi-language and
voice-friendly summaries, crop market price sensitivity chart.

## Getting data into a component

Never call `fetch`. Use a hook from `hooks/useData.ts`:

```tsx
const { data: field } = useField(fieldId);            // FieldOverview
const { data: comparison, refreshing } = useComparison(fieldId);   // strategies + explanations
const { data: stress } = useStressTest(fieldId, comparison?.strategies ?? null);
const units = useUnits();                              // units.water(mm), units.temp(c), units.money(usd)
```

`data` keeps the last good result while a newer one loads. Types are in `types/api.ts`;
real payloads to read or mock against are in `docs/api-contracts/examples/`.

## Styling

- Use the CSS variables in `styles/tokens.css` (`--dim-water`, `--paper-raised`, `--s-4`).
- For colours in SVG or JS, import from `styles/theme.ts` (`DIM_COLOR`, `HAZARD_COLOR`,
  `GROUP_COLOR`, `ROLE_COLOR`).
- Each area has its own stylesheet (`map.css`, `timelines.css`, `rotation.css`,
  `controls.css`, `common.css`, `pages.css`). Add your rules there, not in `global.css`.
- Shared primitives (`Card`, `Tabs`, `Stat`, `Delta`, `ScoreBar`, `ProvenanceBadge`,
  `SupportNotJudgment`) are in `components/common/ui.tsx`.

## Writing for farmers

- Plain words first; wrap any technical term in `<Term>`.
- Say what a number means for a decision, not just the number.
- Always show where a number came from (`<ProvenanceBadge>`).
- Never present a recommendation without the "supports, never replaces" framing
  (`<SupportNotJudgment />`).

## Member 1: backend quick reference

```bash
cd backend
python -m pytest                              # tests
python -m scripts.export_contracts            # regenerate docs/api-contracts after schema changes
python -m scripts.build_benchmark_data        # re-pull real NASA and global data for the benchmark farms
python -m scripts.build_benchmark_data kedah-mada      # just one (add --no-modis if ORNL is down)
```

- New route group: add `app/api/routes/<name>/router.py` exposing `router`; it is mounted
  automatically.
- New benchmark farm: add `data/benchmark-farms/<id>.json` (copy an existing one), then run
  the build script for that id.
- New crop: add an entry to `data/crop-catalog/crops.json`.
- Contract changes: update the Pydantic schema, run `export_contracts`, update
  `frontend/src/types/api.ts`, all in one pull request.
