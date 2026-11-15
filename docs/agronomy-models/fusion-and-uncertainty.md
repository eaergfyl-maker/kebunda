# Data fusion, resolution harmonisation and uncertainty

Code: `backend/app/services/fusion_engine/` (`climate.py`, `harmonize.py`, `observe.py`).

## The problem

The sensors see the world at very different scales, and a field is a few hundred metres
across:

| Dataset | Pixel | Cadence |
| --- | ---: | --- |
| GRACE / GRACE-FO water storage | ~300 km | monthly |
| MERRA-2 meteorology and soil wetness (NASA POWER) | ~55 km | daily |
| GPM IMERG rainfall | ~10 km | 30 min (daily used) |
| SMAP soil moisture | 9-36 km | 2-3 days |
| FAO GAEZ v4 crop suitability | ~9 km | 30-year periods |
| NOAA GHCN-Daily rain gauge (MetMalaysia) | point, 10-150 km away | daily |
| MODIS land-surface temperature | 1 km | 8-day |
| MODIS evapotranspiration | 500 m | 8-day |
| MODIS NDVI | 250 m | 16-day |
| ISRIC SoilGrids soil | 250 m | static model |
| SRTM elevation | ~30 m | static |
| Copernicus Sentinel-2 NDVI and crop cycles | 10 m | 5-day (cloud permitting) |

**Target grid:** calendar months, referenced to the field (the 10-30 m scale of Sentinel-2,
Landsat and SRTM).

**Principle:** nothing invents sub-pixel detail. Where a coarse pixel cannot resolve the
field, the output is a *wider uncertainty*, shown to the user.

## Temporal harmonisation (`climate.py`)

Everything is resampled to calendar months, but extremes are counted from the daily record
**before** aggregation, because a monthly mean hides them:

- wet days (≥ 1 mm), erosive days (≥ 12.7 mm), 95th-percentile and maximum daily rain;
- frost days (Tmin < 0 °C), heat days (Tmax ≥ 32 and ≥ 35 °C);
- pooled within-month standard deviation of daily Tmax and Tmin (used to shift frost and
  heat-day counts analytically under a temperature scenario);
- erosivity share per month ∝ Σ(daily rain ≥ 12.7 mm)^1.81;
- last spring / first autumn frost dates per year (median and 1-in-10).

Composites (16-day NDVI, 8-day LST and ET) are averaged into months; cloudy or filled
composites are dropped, and the share of valid composites becomes the layer's completeness.

Trends use the **Theil-Sen slope with a Mann-Kendall test** (robust to outliers in a short
record). A trend is called "clear" only at p < 0.1.

The drought signal is the standardised root-zone wetness anomaly per calendar month
(`z ≤ -1` is a notably dry month).

## Fusing redundant estimates: rainfall

Three independent estimates of the same variable are blended by inverse-variance weighting:

```
P_fused = Σ w_k · P_k / Σ w_k,      w_k = 1 / σ_k²
```

`σ_k` for MERRA-2 and IMERG is **measured at the site**: the RMSE of that product's monthly
totals against the nearest MetMalaysia gauge (NOAA GHCN-Daily) over the overlapping record,
divided by the mean monthly total (clamped to 0.08-0.9). Gauge months with less than 70 % of
days reported are dropped. The gauge itself is assigned 0.10 plus 0.004 per km of distance from
the field, because tropical convective storms are only a few kilometres wide.
Without a ground record, defaults of 0.25 / 0.22 are used.

The reported relative uncertainty combines the formal error with half the spread between
sources: `σ = sqrt((1/Σw) + (0.5 · spread)²)`.

The ratio `P_fused / P_MERRA2` per month is applied as a bias correction to the 24-year
monthly series that drives the water balance and the weather replay.

## Downscaling: soil moisture

A coarse cell reports relative saturation for a generic soil. The field conversion uses the
field's own SoilGrids sand, clay and organic matter through the Saxton & Rawls (2006)
pedotransfer functions for wilting point, field capacity and saturation:

```
θ = wetness · θ_sat
plant-available fraction = clamp((θ - θ_wp) / (θ_fc - θ_wp))
```

Two fields in the same 55 km cell with different textures get different plant-available
water for the same reported wetness. This is a rescaling, not a prediction of
field-to-field differences in rainfall.

## Resolution-gap score per layer

For each layer:

```
representativeness = 1 / (1 + pixel_size / L)
confidence = access_weight × representativeness × completeness
```

`L` is the distance over which the variable typically stays similar: temperature 150 km,
monthly rainfall 40 km, soil moisture 15 km, groundwater 100 km, soil 0.1 km, terrain
0.05 km; for vegetation, surface temperature and ET it is the field's own width.

`access_weight`: live or cached 1.0, curated 0.8, proxy 0.7, unavailable 0.

The API returns `pixel_to_field_ratio` and `pixels_inside_field` so the UI can draw the gap
to scale (map overlay and the "resolution ladder").

## Confidence per decision dimension

Layer confidences roll up to data confidence for each dimension (for example water: best
rainfall source, temperature, soil survey, soil moisture). Each dimension also has a fixed
**model** confidence reflecting how well a monthly planning model can answer that question
at all:

| Dimension | Model confidence |
| --- | ---: |
| Water | 0.80 |
| Erosion | 0.65 |
| Pest break | 0.65 |
| Soil health | 0.55 |
| Income | 0.55 |

`combined = sqrt(data × model)`; ≥ 0.72 is "high", ≥ 0.55 "moderate", otherwise "low".

It is used three ways:

1. **Score uncertainty:** `± (1 - combined) × 22` points on that dimension.
2. **Benefit ranges:** each change against the baseline gets a plausible range of
   `delta × (1 ± 0.9·(1 - combined))`.
3. **Ties:** strategies within 3 fit points of the leader are reported as tied.

## Proxies and gaps, stated

| Wanted | Used | Why |
| --- | --- | --- |
| SMAP L4 root-zone moisture | MERRA-2 root-zone wetness via NASA POWER | SMAP L4 needs an Earthdata login; both are model-assimilated estimates |
| ECOSTRESS 70 m LST / ET | MODIS LST 1 km and MOD16 ET 500 m | ECOSTRESS needs AppEEARS auth; within-field hotspots are averaged out |
| GRACE-FO monthly mascons | Curated regional trends from published analyses | 300 km footprint; context only, never downscaled |
| MetMalaysia station network | NOAA GHCN-Daily copies of 16 MetMalaysia stations | The national archive has no keyless API; GHCN carries the synoptic stations |
| DOA detailed soil survey | ISRIC SoilGrids 250 m, with surveyed corrections for peat and BRIS sand on two benchmarks | No public point API for the Malaysian soil survey |

Every proxy is labelled `access: "proxy"` in the payload and appears under "What we cannot
see" in the UI.

## Validation built in

- **Rainfall:** correlation, bias and RMSE of each satellite/model product against gauges
  are computed per field and shown.
- **Crop calendar:** the baseline rotation's modelled green cover is correlated with the
  observed Sentinel-2 NDVI seasonal curve (MODIS where Sentinel-2 is unavailable). Weak agreement is raised as a high-severity gap.
- **Crop history:** the baseline rotation is checked against the number of green-up and
  harvest cycles a year that Sentinel-2 counts at the point (2020-2024). For a custom field
  this count proposes the baseline: two cycles on flat, heavy land is read as double-cropped paddy.
