# Agronomy models

Everything in `backend/app/services/rotation_engine/` and `vulnerability_analyzer/`.
The models run on a **monthly step** for one field. They are deliberately simple and
inspectable: their job is to **rank rotations against each other on one field**, not to
predict a yield or a soil test.

Code map: `schedule.py` (calendar) → `simulate.py` (cover, water, erosion, carbon,
nitrogen, pests, economics) → `scoring.py` → `explain.py`.

## 1. Crop calendar (`schedule.py`)

Planting and harvest months are derived from the field's own NASA POWER temperatures, so
they move with latitude, elevation and a warming scenario.

Monthly growing degree days for a crop with base temperature `Tb` (upper cut-off 30 °C):

```
GDD_m = max(0, (min(Tmax_m, 30) + max(Tmin_m, Tb)) / 2 - Tb) * days_m
```

- **Spring-sown crops** are planted in the first month with mean temperature ≥ the crop's
  planting temperature and mean minimum > -1 °C. They mature when accumulated GDD reaches
  the crop's requirement *and* a minimum season length has passed (a guard for
  photoperiod-sensitive crops in hot climates). Meeting a freezing month before maturity
  makes the crop infeasible.
- **Fall-sown crops** are planted in the first month from late summer with mean temperature
  ≤ the crop's fall threshold, and are infeasible if the coldest month's mean minimum is
  below the crop's hardiness limit.
- **Cover crops** fill the gap between the previous harvest and the next planting. Biomass
  fraction = `GDD accumulated in the window / GDD to maturity`, scaled by a moisture factor
  `clamp(P / (0.5 ET0), 0.25, 1)`. Winter-killed species stop growing in the first month
  with mean minimum < -4 °C and become mulch.
- **Overlaps** are resolved in time order: a crop is delayed until the previous one is off
  (up to 3 months for spring crops, 2 for fall-sown) and pays 8 % yield per month of delay.

## 2. Ground cover

Each month: `cover = 1 - (1 - canopy)(1 - residue_cover)`.

- Canopy ramps to full at 40 % of the crop's thermal time, holds to 80 %, then senesces.
- Residue is a set of pools `(mass, cover coefficient, decay rate)`:
  `residue_cover = 1 - exp(-Σ coef_i · mass_i)` (Gregory 1982), decaying monthly by
  `exp(-k · fT · fW)` with `fT = clamp(T/20, 0.03, 1.6)`, `fW = clamp(P / 0.5·ET0, 0.3, 1)`.
- Tillage removes surface residue at harvest and planting:

| System | Kept after harvest | Kept at planting | Fallow tillage (per warm month) |
| --- | ---: | ---: | ---: |
| Conventional | 14 % | 50 % | 80 % |
| Reduced / strip | 75 % | 60 % | 95 % |
| No-till | 100 % | 92 % | 100 % |

Fall tillage is skipped when a cover or winter crop is seeded within two months.
A month with cover < 30 % counts as **bare** (the NRCS conservation-tillage threshold).

## 3. Water balance (FAO-56 style bucket)

State: plant-available water `S` in the root zone, capacity
`TAW = AWC (SoilGrids) × root-zone depth`.

```
runoff   = wet_days · E[Q]                      (SCS curve number, see below)
S       += precip - runoff
evap     = min(Kc_soil · ET0 · (1 - canopy), 0.9·infiltration + 0.08·S)
T_pot    = Kc_mid · green · ET0
reach    = TAW · min(1, crop root depth / root-zone depth)     # water fills from the top
T_act    = T_pot                         if available ≥ (1-p)·reach + T_pot
         = T_pot · available / ((1-p)·reach + T_pot)   otherwise
drainage = max(0, S - TAW)
```

- `ET0` is Hargreaves-Samani from monthly Tmax/Tmin and extraterrestrial radiation, so it
  responds directly to a temperature scenario.
- `Kc_soil = clamp(0.12 + 0.04·wet_days, 0.12, 0.65) · (1 - 0.5·residue_cover)`: residue
  mulch cuts evaporation.
- **Runoff** uses the curve number, interpolated between bare fallow and dense cover by
  hydrologic soil group (A 77→51, B 86→67, C 91→76, D 94→80), minus 1.5 (reduced) or
  3 (no-till). Daily rain on wet days is taken as exponentially distributed with mean
  `P / wet_days`, and the expected runoff per wet day is integrated with 8-point
  Gauss-Laguerre quadrature:

  ```
  E[Q] = exp(-Ia/μ) · ∫₀^∞ (μt)² / (μt + S_ret) · e^-t dt,   Ia = 0.2·S_ret,  S_ret = 25400/CN - 254
  ```

  This is why the "storm intensity" dial matters: the same rain in fewer, heavier storms
  (larger `μ`, fewer wet days) produces more runoff.
- **Irrigation** (irrigated fields, harvested crops only) refills to the management-allowed
  depletion each month, limited by the annual allocation, application efficiency and
  330 mm/month system capacity. It stops in the crop's last growth month.
- **Yield response to water** (FAO-33): `Y/Ym = 1 - Ky · (1 - ΣT_act / ΣT_pot)`.

## 4. Other yield factors

Relative yield is the product of: water; heat (`loss % per day` × days above the crop's
critical Tmax during the middle of its season, from a normal distribution of daily Tmax);
late planting; crop sequence (0.90 for a crop after itself, 1.04 after a legume); and, **only
for crops without a local reference yield**, salinity, pH, drainage and humid-climate
disease.

> **Reference yields.** A local reference yield already reflects the field's fixed limits and
> today's normal heat, so for those crops only *extra* heat (a hot year, a warming scenario)
> costs yield. For the dryland Palouse farm reference yields are water-unlimited potentials,
> and the water balance applies the moisture limit (this is what separates wheat after fallow
> from wheat after a crop).

## 5. Erosion (RUSLE)

```
A = R · K · LS · C        [t/ha/yr]
```

- **R** from annual precipitation (Renard & Freimund 1994), scaled by `(1 + storm)^0.81`
  under a storm-intensity scenario. For the Palouse the NRCS equivalent R for the
  Northwestern Wheat and Range Region is used (`Req = -48.4 + 7.78·P_in`), because most
  erosion there comes from rain and snowmelt on thawing soil.
- Monthly distribution of R ∝ Σ(daily rain ≥ 12.7 mm)^1.81 from the 24-year daily record.
- **K** = Kw (Williams EPIC equation from SoilGrids texture and carbon) × 0.1317. **LS** from McCool et al. (1987/1989) using the soil survey's
  representative slope, blended with SRTM slope only where SRTM relief exceeds its noise.
- **C** is computed monthly as a soil-loss ratio and weighted by that month's share of R:
  `SLR = PLU · (1 - 0.85·canopy) · exp(-3.5·residue_cover)`, with
  PLU = 0.62 / 0.50 / 0.38 for conventional / reduced / no-till (×0.8 with living roots).

Reported against the soil survey's tolerable loss **T**.

## 6. Soil organic carbon (one pool)

```
dSOC/dt = h_shoot·C_shoot + h_root·C_root - k·SOC
k = 0.0075 · 2^((MAT-10)/10) · tillage · (1.1 - 0.008·clay%) · (0.55 + 0.45·wetness)
```

`h_shoot = 0.13`, `h_root = 0.30` (roots stabilise about 2.3× better than shoots; Rasse et
al. 2005). Tillage multiplier 1.25 / 1.05 / 0.88; perennial years count as untilled.
`SOC` (0-30 cm) comes from SoilGrids organic carbon and bulk density. Output is the yearly
change and the projected change in organic matter after 10 years.

## 7. Nitrogen

- Fertiliser need = crop N demand (scaled to local yield) minus the credit carried from the
  previous legume crop and legume cover crops (credit × cover biomass fraction).
- A residual-nitrate pool gains mineralised N (`2.5 · OM% · fT` kg/ha/month) and post-harvest
  leftovers, loses uptake by any living plant, and leaches as
  `pool · drainage / (drainage + 0.6·TAW)`.

## 8. Pest, weed and disease break

`score = 100 · (0.55·host + 0.27·groups + 0.18·seasons) - 6 · green bridges`

- **host**: for each crop and each pest group it hosts, `min(1, (interval - 1) / break years)`
  where interval is the years until the same group returns.
- **groups**: distinct functional groups (cool/warm × grass/broadleaf), covers count half.
- **seasons**: distinct planting seasons (fall, early spring, late spring, perennial).
- **green bridge**: a cover crop sharing a pest group with the crop that follows it.

## 9. Economics

Per acre: `revenue = yield × price`; `cost = operating cost + N × $1.20/kg + irrigation ×
field cost per mm + cover-crop seed`. Land cost is excluded. Grazing value is credited only
when livestock are available.

**Variability.** Each rotation is replayed through the actual 2001-2024 weather, once per
rotation phase offset so every crop meets every year. The standard deviation of yearly net
return is combined with price volatility (crop price CVs, pairwise correlation 0.5):

```
bad-year net = mean - 0.84 · sqrt(σ_weather² + σ_price²)        (about a 1-in-5 year)
```

## 10. Vulnerability calendar

`risk(month, hazard) = hazard(month) × exposure(month)`, each 0-1:

| Hazard | Hazard term | Exposure term |
| --- | --- | --- |
| Storm | month's share of annual erosivity ÷ peak share | `1 - ground cover` |
| Heat | days above the crop's critical Tmax ÷ 10 | cash crop at ≥ 60 % canopy × crop sensitivity |
| Frost | days below -1 °C ÷ 6 | spring-sown crop as seedling or in mid-season |
| Drought | unmet transpiration ÷ demand (from the water balance) | harvested crop growing |
| Leaching | monthly nitrate leached ÷ max(8 kg/ha, rotation peak) | — |

The baseline's modelled green cover is checked against observed MODIS NDVI
(`validate_against_ndvi`): correlation ≥ 0.8 is "strong", ≥ 0.55 "fair", else "weak".

## Known weaknesses

- Monthly steps miss single storms, short dry spells and exact frost dates.
- One soil bucket: no layered soil water, no capillary rise, no perched water tables.
- No explicit wind erosion (important on the High Plains), gully erosion or tile-flow routing.
- One generic variety per crop; no hybrid maturity groups or cultivar disease packages.
- Yield response is multiplicative and linear in water; it does not model timing of stress
  within a month.
- Soil carbon is a single pool with literature parameters; treat the sign and ranking as
  informative and the magnitude as approximate.
- Economics use multi-year average prices and generic budgets.

## Parameter sources

FAO Irrigation and Drainage Papers 56 and 33/66; USDA NRCS National Engineering Handbook
Part 630 (curve numbers); RUSLE (USDA Agriculture Handbook 703) and RUSLE2 crop database;
Renard & Freimund (1994); McCool et al. (1987, 1989); Richardson et al. (1983); Gregory
(1982); Saxton & Rawls (2006); Maas & Hoffman (1977); SARE *Managing Cover Crops
Profitably*; Rasse et al. (2005); MARDI crop technology packages; DOA Malaysia production-cost
tables; FAMA farm-gate prices; LKTN and MPIB price notes. Crop traits live in `data/crop-catalog/crops.json`.
