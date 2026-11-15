/**
 * "A year on this field": the seasonal rhythm from four sensors on one month axis.
 * Rain against the air's thirst, with satellite greenness and surface temperature underneath.
 *
 * OWNER: Member 2.
 * Actual ET (MOD16, field.evapotranspiration) is drawn as a dashed purple line, with the gap
 * above rainfall shaded as "water drawn from soil or irrigation". When that product was not
 * retrieved for a field, a short note says so instead of the chart silently looking unchanged.
 */
import { Term } from "@/components/common/glossary/Term";
import { useUnits } from "@/hooks/useUnits";
import { useMonths, useT } from "@/i18n/LanguageProvider";
import { CHART } from "@/styles/theme";
import type { FieldOverview } from "@/types/api";

import { box, extent, innerW, LegendRow, linePath, MonthAxis, niceTicks, scale, Svg, YAxis } from "./chartKit";
import { LocalAdviceNote, Takeaway } from "./Takeaway";

const ET_ACTUAL_COLOR = "#8a5a9e";

export function SeasonYear({ field }: { field: FieldOverview }) {
  const units = useUnits();
  const { t } = useT();
  const { months: MONTHS } = useMonths();
  const rain = field.fusion.precip.monthly_mm;
  const sigma = field.fusion.precip.relative_sigma;
  const et0 = field.climate.monthly.et0;
  const ndvi = field.vegetation?.monthly ?? null;
  // Cloud or water can push a monthly NDVI slightly below zero; draw those as zero.
  const ndviDraw = ndvi ? ndvi.map((v) => (v === null ? null : Math.max(0, v))) : null;
  const lst = field.surface_temperature?.monthly ?? null;
  const tmax = field.climate.monthly.tmax;
  const etAct = field.evapotranspiration?.monthly ?? null;

  const b = box(720, 250);
  const band = innerW(b) / 12;
  const x = (m: number) => b.left + band * (m + 0.5);
  const top = Math.max(
    ...et0,
    ...rain.map((r, i) => r * (1 + sigma[i])),
    ...(etAct ?? []).filter((v): v is number => v !== null),
  ) * 1.08;
  const y = scale(0, top, b.height - b.bottom, b.top);
  const ticks = niceTicks(0, top, 4);
  const deficitMonths = rain.map((r, i) => et0[i] - r).filter((d) => d > 0).length;
  const wettest = rain.reduce((bi, v, i) => (v > rain[bi] ? i : bi), 0);
  const lightest = rain.reduce((bi, v, i) => (v < rain[bi] ? i : bi), 0);
  const sentence = t("Rain is heaviest in {wet} and lightest in {dry} (about {r}).", { wet: MONTHS[wettest], dry: MONTHS[lightest], r: units.water(rain[lightest]) }) + " " +
    (deficitMonths > 0
      ? t(deficitMonths === 1 ? "In 1 month of the year the air can take more water than falls, so crops may need extra water then." : "In {n} months of the year the air can take more water than falls, so crops may need extra water then.", { n: deficitMonths })
      : t("Rain beats the air's thirst in every month, so rain alone rarely leaves crops short."));

  const b2 = box(720, 170, { right: 44 });
  const yN = scale(0, 1, b2.height - b2.bottom, b2.top);
  const [t0, t1] = extent([...(lst ?? []), ...tmax], 0.08);
  const yT = scale(t0, t1, b2.height - b2.bottom, b2.top);

  return (
    <div className="stack">
      <div>
        <h4>{t("Rain against the air's thirst")}</h4>
        <p className="small muted">
          {t("Bars are")} <Term id="fused_rain">{t("fused rainfall")}</Term> {t("with its uncertainty; the line is")} <Term id="et0">{t("reference evapotranspiration")}</Term>.
        </p>
        <Takeaway>{sentence}</Takeaway>
        <Svg b={b} label={t("Monthly rainfall, reference evapotranspiration and actual evapotranspiration")}>
          <YAxis b={b} ticks={ticks} y={y} format={(v) => units.waterValue(v).toFixed(units.system === "us" ? 1 : 0)} title={t("{u} per month", { u: units.waterUnit })} />
          {rain.map((r, m) => (
            <g key={m}>
              <rect x={x(m) - band * 0.32} y={y(r)} width={band * 0.64} height={Math.max(0, y(0) - y(r))} rx={3} fill={CHART.precip} opacity={0.85}>
                <title>{t("{m}: {r} of rain (±{s}%), air demand {e}", { m: MONTHS[m], r: units.water(r), s: Math.round(sigma[m] * 100), e: units.water(et0[m]) })}</title>
              </rect>
              <line x1={x(m)} x2={x(m)} y1={y(r * (1 + sigma[m]))} y2={y(r * (1 - sigma[m]))} stroke={CHART.ink} strokeWidth={1.2} opacity={0.6} />
            </g>
          ))}
          {etAct && etAct.map((e, m) => e !== null && e > rain[m] && (
            <rect key={`gap${m}`} x={x(m) - band * 0.32} y={y(e)} width={band * 0.64} height={Math.max(0, y(rain[m]) - y(e))} fill={ET_ACTUAL_COLOR} opacity={0.2}>
              <title>{t("{m}: crops and soil lost {e}, more than the {r} that fell. The difference comes from soil storage or irrigation.", { m: MONTHS[m], e: units.water(e), r: units.water(rain[m]) })}</title>
            </rect>
          ))}
          {etAct && <path d={linePath(etAct, x, y)} fill="none" stroke={ET_ACTUAL_COLOR} strokeWidth={2.2} strokeDasharray="6 4" strokeLinejoin="round" />}
          {etAct?.map((e, m) => e !== null && <circle key={`ea${m}`} cx={x(m)} cy={y(e)} r={2.8} fill={ET_ACTUAL_COLOR} />)}
          <path d={linePath(et0, x, y)} fill="none" stroke={CHART.et} strokeWidth={2.5} strokeLinejoin="round" />
          {et0.map((v, m) => <circle key={m} cx={x(m)} cy={y(v)} r={3} fill={CHART.et} />)}
          <MonthAxis b={b} x={x} />
        </Svg>
        <LegendRow items={[
          { color: CHART.precip, label: t("Rainfall (fused, with ± range)"), swatch: "box" },
          { color: CHART.et, label: t("What the air could evaporate (ET0)") },
          ...(etAct ? [
            { color: ET_ACTUAL_COLOR, label: t("What crops and soil actually lost (MODIS ET)"), dash: true },
            { color: ET_ACTUAL_COLOR, label: t("Gap: water taken from soil or irrigation"), swatch: "box" as const },
          ] : []),
        ]} />
        {!etAct && (
          <p className="xs faint" style={{ marginTop: 4 }}>
            {t("Actual evapotranspiration (MODIS ET) was not retrieved for this field, so only the air-demand line is shown.")}
          </p>
        )}
      </div>

      <div>
        <h4>{t("What the satellites see through the year")}</h4>
        <p className="small muted">
          <Term id="ndvi">{t("Greenness")}</Term> {t("from MODIS (250 m) shows when the field is growing or bare.")}{" "}
          <Term id="lst">{t("Surface temperature")}</Term> {t("running far above air temperature marks dry or bare ground.")}
        </p>
        {ndvi || lst ? (
          <>
            <Svg b={b2} label={t("Monthly satellite greenness and surface temperature")}>
              <YAxis b={b2} ticks={[0, 0.25, 0.5, 0.75, 1]} y={yN} title={t("Greenness (NDVI)")} color={CHART.ndvi} />
              <YAxis b={b2} ticks={niceTicks(t0, t1, 4)} y={yT} side="right" title={units.tempUnit} color={CHART.temp} format={(v) => units.tempValue(v).toFixed(0)} />
              <rect x={b2.left} y={yN(0.3)} width={innerW(b2)} height={yN(0) - yN(0.3)} fill="#b08a63" opacity={0.12} />
              <text x={b2.left + 6} y={yN(0.3) + 12} fontSize={9.5} fill="#8a6a45">{t("looks bare or dormant from orbit")}</text>
              <path d={linePath(tmax, x, yT)} fill="none" stroke={CHART.temp} strokeWidth={1.5} strokeDasharray="4 3" opacity={0.7} />
              {lst && <path d={linePath(lst, x, yT)} fill="none" stroke={CHART.temp} strokeWidth={2.2} />}
              {ndviDraw && <path d={linePath(ndviDraw, x, yN)} fill="none" stroke={CHART.ndvi} strokeWidth={2.8} strokeLinejoin="round" />}
              {ndviDraw?.map((v, m) => v !== null && (
                <circle key={m} cx={x(m)} cy={yN(v)} r={3.2} fill={CHART.ndvi}>
                  <title>{`${MONTHS[m]}: NDVI ${(ndvi?.[m] ?? v).toFixed(2)}`}</title>
                </circle>
              ))}
              <MonthAxis b={b2} x={x} />
            </Svg>
            <LegendRow items={[
              ...(ndvi ? [{ color: CHART.ndvi, label: t("Greenness (MODIS NDVI)") }] : []),
              ...(lst ? [{ color: CHART.temp, label: t("Ground surface, mid-morning (MODIS LST)") }] : []),
              { color: CHART.temp, label: t("Average daily high, air (NASA POWER)"), dash: true },
            ]} />
          </>
        ) : (
          <div className="notice notice-warn">
            {t("MODIS greenness and surface temperature were not retrieved for this field (the NASA ORNL subset service did not answer). The rest of the analysis does not depend on them; they are used as a cross-check.")}
          </div>
        )}
      </div>
      <p className="xs faint">{t("Monthly averages")}, {field.climate.years[0]}–{field.climate.years[field.climate.years.length - 1]}.</p>
      <LocalAdviceNote />
    </div>
  );
}