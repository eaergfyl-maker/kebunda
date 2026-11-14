# Scoring, candidate search and strategy selection

Code: `rotation_engine/generate.py`, `scoring.py`, `engine.py`, `explain.py`.

## Candidate search

1. **Crop screen.** Every harvestable crop is grown alone on the field in the model
   (`generate.suitability_screen`). It is rejected if it cannot mature or survive winter.
   Suitability is its relative yield after water, heat and site limits (in the spirit of
   FAO GAEZ classes: ≥ 0.80 very suitable, ≥ 0.62 suitable, ≥ 0.45 moderately suitable).
2. **Crop pool.** The baseline's crops plus the best others by
   `0.45·suitability + 0.30·market access + 0.25·min(1, net return / $400)`, up to 7.
   Unverified markets are discounted by 0.7. Crops needing equipment the farm lacks are
   dropped when custom hire is unavailable.
3. **Sequences.** All 2-4 year sequences from the pool with no crop following itself and no
   repeated pattern (ABAB = AB), de-duplicated up to rotation of the starting year. Fallow is
   allowed where the baseline already uses it. Perennials enter as 3-year stands.
4. **Stage 1.** Every sequence is simulated with the baseline tillage.
5. **Stage 2.** The top 10 sequences on each dimension and on the equal-weight total, plus
   the baseline's own sequence, are expanded with cover-crop and tillage variants.

The whole candidate set is cached per (field, scenario, constraints). Priorities are **not**
part of the cache key, so moving a priority slider only re-ranks.

Cover crops are chosen for what follows them: cereal rye before a legume, a
legume-containing cover before a nitrogen-hungry crop, sorghum-sudangrass in a long warm
gap before a fall-sown crop, winter triticale where a forage market exists.

## Dimension scores (0-100)

Scores use **fixed anchors**, not "best candidate = 100", so a number means the same thing
on every field. `lerp(x, worst, best)` maps linearly and clamps.

**Water**, irrigated:
`0.55·lerp(irrigation / sustainable allocation, 1.8, 0.4) + 0.25·lerp(stress %, 35, 3) + 0.20·lerp(productive water %, 30, 75)`

**Water**, rainfed:
`0.50·lerp(stress %, 45, 5) + 0.30·lerp(productive water %, 20, 65) + 0.20·lerp(infiltration %, 70, 98)`

**Soil health:**
`0.40·lerp(ΔSOC t/ha/yr, -0.35, 0.45) + 0.20·lerp(N self-sufficiency %, 0, 60) + 0.20·lerp(living-root months, 3.5, 11) + 0.10·lerp(N leached kg/ha, 40, 3) + 0.10·lerp(infiltration %, 70, 98)`

**Soil cover / erosion:**
`0.50·lerp(soil loss ÷ tolerable, 2.0, 0.15) + 0.30·lerp(bare months, 7.5, 0.5) + 0.20·lerp(erosive rain on exposed soil %, 80, 15)`

**Pest break:** the score from `models.md` §8.

**Income:**
`0.45·profit + 0.25·lerp(variability, 0.45, 0.10) + 0.20·lerp(market access, 0.3, 1.0) + 0.10·forage`

`profit = 50 + 50·clamp((net - baseline net) / scale / 0.6, -1, 1)` with
`scale = max($150, |baseline net|, 25 % of baseline gross)`. Profit is the one term measured
against the field's own baseline, because a good net return differs twentyfold between
dryland wheat and processing tomatoes. The baseline therefore always scores 50 on profit.

## Fit

```
fit = Σ w_d · score_d / Σ w_d  -  penalties
```

`w_d` are the farmer's 0-10 priorities. Penalties, scaled by risk tolerance
(low 1.0, medium 0.4, high 0):

| Penalty | Points |
| --- | --- |
| Equipment not on the farm | 3 per item (always applied) |
| Amount of change | 3 × risk × (new crops + cover crops added + tillage change + 0.5 per missing item) |
| Thin or unverified market | 10 × risk × (0.75 - market access) / 0.75 |

## Which strategies are shown

Always the **baseline**, then up to four that differ meaningfully:

| Role | Rule |
| --- | --- |
| `step` | Best fit among candidates with the baseline's own cash crops (covers and tillage only) |
| `match` | Best fit among candidates with different cash crops |
| `resilient` | Highest soil + erosion + pest + water among those with ≥ 3 cash crops and income ≥ 30 |
| `income` | Highest net return among those whose weighted score is at least the baseline's |
| `custom` | Rotations the farmer built |

Two strategies never share both crop sequence and tillage. Strategies within 3 fit points
of the leader are flagged as tied.

## The five explanations

All text is assembled from numbers the models produced; no free-text generation.

1. **Why suggested:** gains on the farmer's top two priorities, co-benefits, then climate,
   soil, pest and market hooks triggered by thresholds (for example: falling GRACE storage
   on an irrigated field and ≥ 15 mm less pumping).
2. **Evidence:** observed facts from `vulnerability_analyzer/insights.py` for the dimensions
   that changed most, plus model results with their method.
3. **Benefits:** twelve outcomes against the baseline with direction, range and confidence,
   plus bad-year income and income swing from the weather replay. Trade-offs are listed as
   prominently as gains.
4. **Gaps:** unavailable and proxy layers, coarse-pixel layers, missing local yields and
   buyers, weak cover-crop windows, the NDVI calendar check, and six standing blind spots
   (compaction, soil biology, drainage hardware, varieties, contracts, within-field variation),
   each with how to close it.
5. **Risks for local review:** rule-triggered checklist items (herbicide carryover into a
   sensitive follower, cover-crop termination timing, green bridges, equipment, buyers,
   insurance, fallow replacement, tillage transition, nitrogen credits, tight windows,
   allocation limits, salinity, perennials, grazing), each tagged with who should review it.
